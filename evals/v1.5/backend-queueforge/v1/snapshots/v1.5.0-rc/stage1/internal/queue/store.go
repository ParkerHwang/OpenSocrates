package queue

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"queueforge/internal/platform"
)

type Clock func() (int64, error)

func RealClock() (int64, error) { return time.Now().UnixMilli(), nil }
func FileClock(path string) Clock {
	return func() (int64, error) {
		b, e := os.ReadFile(path)
		if e != nil {
			return 0, e
		}
		n, e := strconv.ParseInt(strings.TrimSpace(string(b)), 10, 64)
		return n, e
	}
}

type Store struct {
	DB  *sql.DB
	Now Clock
}
type Job struct {
	ID            string          `json:"id"`
	Tenant        string          `json:"tenant"`
	Queue         string          `json:"queue"`
	Payload       json.RawMessage `json:"payload"`
	State         string          `json:"state"`
	Attempts      int             `json:"attempts"`
	MaxAttempts   int             `json:"max_attempts"`
	CreatedSeq    int64           `json:"created_seq"`
	CreatedAtMS   int64           `json:"created_at_ms"`
	AvailableAtMS int64           `json:"available_at_ms"`
	LeaseUntilMS  *int64          `json:"lease_until_ms"`
	LastError     *string         `json:"last_error"`
	Result        json.RawMessage `json:"result"`
}
type Input struct {
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	MaxAttempts int             `json:"max_attempts"`
}
type fault string

const (
	NotFound            fault = "not_found"
	LeaseConflict       fault = "lease_conflict"
	IdempotencyConflict fault = "idempotency_conflict"
)

func (f fault) Error() string { return string(f) }
func Code(e error) string {
	var f fault
	if errors.As(e, &f) {
		return string(f)
	}
	return "storage_unavailable"
}
func New(path string, clock Clock) (*Store, error) {
	db, e := sql.Open(platform.SQLiteDriver, path)
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	for _, q := range []string{"PRAGMA busy_timeout=10000", "PRAGMA journal_mode=WAL", "PRAGMA synchronous=FULL", `CREATE TABLE IF NOT EXISTS jobs (created_seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_at_ms INTEGER NOT NULL,available_at_ms INTEGER NOT NULL,lease_until_ms INTEGER,lease_token TEXT,last_error TEXT,result TEXT,completion_token TEXT)`, `CREATE INDEX IF NOT EXISTS jobs_claim ON jobs(tenant,queue,state,available_at_ms,created_seq)`, `CREATE TABLE IF NOT EXISTS idempotency (tenant TEXT NOT NULL,endpoint TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,ids TEXT NOT NULL,PRIMARY KEY(tenant,endpoint,key))`, `PRAGMA user_version=1`} {
		if _, e = db.Exec(q); e != nil {
			db.Close()
			return nil, e
		}
	}
	return &Store{db, clock}, nil
}
func (s *Store) Close() error { return s.DB.Close() }
func token() (string, error) {
	var b [24]byte
	_, e := rand.Read(b[:])
	return hex.EncodeToString(b[:]), e
}
func (s *Store) write(ctx context.Context, fn func(*sql.Conn, int64) error) error {
	now, e := s.Now()
	if e != nil {
		return e
	}
	c, e := s.DB.Conn(ctx)
	if e != nil {
		return e
	}
	defer c.Close()
	if _, e = c.ExecContext(ctx, "BEGIN IMMEDIATE"); e != nil {
		return e
	}
	committed := false
	defer func() {
		if !committed {
			c.ExecContext(context.Background(), "ROLLBACK")
		}
	}()
	if e = fn(c, now); e != nil {
		return e
	}
	if _, e = c.ExecContext(ctx, "COMMIT"); e != nil {
		return e
	}
	committed = true
	return nil
}

const cols = "id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result"

type scanner interface{ Scan(...any) error }

func scan(r scanner) (Job, error) {
	var j Job
	var payload string
	var result sql.NullString
	var deadline sql.NullInt64
	var last sql.NullString
	e := r.Scan(&j.ID, &j.Tenant, &j.Queue, &payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAtMS, &j.AvailableAtMS, &deadline, &last, &result)
	if e != nil {
		return j, e
	}
	j.Payload = json.RawMessage(payload)
	if deadline.Valid {
		j.LeaseUntilMS = &deadline.Int64
	}
	if last.Valid {
		j.LastError = &last.String
	}
	if result.Valid {
		j.Result = json.RawMessage(result.String)
	}
	return j, nil
}
func get(ctx context.Context, c *sql.Conn, tenant, id string) (Job, error) {
	j, e := scan(c.QueryRowContext(ctx, "SELECT "+cols+" FROM jobs WHERE tenant=? AND id=?", tenant, id))
	if errors.Is(e, sql.ErrNoRows) {
		return j, NotFound
	}
	return j, e
}
func (s *Store) Get(ctx context.Context, tenant, id string) (Job, error) {
	c, e := s.DB.Conn(ctx)
	if e != nil {
		return Job{}, e
	}
	defer c.Close()
	return get(ctx, c, tenant, id)
}
func (s *Store) Submit(ctx context.Context, tenant, endpoint, key, fp string, inputs []Input) ([]Job, bool, error) {
	var out []Job
	replayed := false
	e := s.write(ctx, func(c *sql.Conn, now int64) error {
		var old, idsJSON string
		e := c.QueryRowContext(ctx, "SELECT fingerprint,ids FROM idempotency WHERE tenant=? AND endpoint=? AND key=?", tenant, endpoint, key).Scan(&old, &idsJSON)
		if e == nil {
			if old != fp {
				return IdempotencyConflict
			}
			var ids []string
			if e = json.Unmarshal([]byte(idsJSON), &ids); e != nil {
				return e
			}
			for _, id := range ids {
				j, e := get(ctx, c, tenant, id)
				if e != nil {
					return e
				}
				out = append(out, j)
			}
			replayed = true
			return nil
		}
		if !errors.Is(e, sql.ErrNoRows) {
			return e
		}
		ids := make([]string, 0, len(inputs))
		for _, in := range inputs {
			id, e := token()
			if e != nil {
				return e
			}
			r, e := c.ExecContext(ctx, "INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms) VALUES(?,?,?,?, 'ready',0,?,?,?)", id, tenant, in.Queue, string(in.Payload), in.MaxAttempts, now, now)
			if e != nil {
				return e
			}
			seq, e := r.LastInsertId()
			if e != nil {
				return e
			}
			j := Job{ID: id, Tenant: tenant, Queue: in.Queue, Payload: in.Payload, State: "ready", MaxAttempts: in.MaxAttempts, CreatedSeq: seq, CreatedAtMS: now, AvailableAtMS: now}
			out = append(out, j)
			ids = append(ids, id)
		}
		b, _ := json.Marshal(ids)
		_, e = c.ExecContext(ctx, "INSERT INTO idempotency(tenant,endpoint,key,fingerprint,ids) VALUES(?,?,?,?,?)", tenant, endpoint, key, fp, string(b))
		return e
	})
	return out, replayed, e
}
func (s *Store) Claim(ctx context.Context, tenant, queue string, leaseMS int64) (*Job, *string, error) {
	var job *Job
	var tok *string
	e := s.write(ctx, func(c *sql.Conn, now int64) error {
		_, e := c.ExecContext(ctx, "UPDATE jobs SET state=CASE WHEN attempts>=max_attempts THEN 'dead' ELSE 'ready' END,available_at_ms=?,lease_until_ms=NULL,lease_token=NULL,last_error='lease_expired' WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=?", now, tenant, queue, now)
		if e != nil {
			return e
		}
		j, e := scan(c.QueryRowContext(ctx, "SELECT "+cols+" FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at_ms<=? ORDER BY created_seq LIMIT 1", tenant, queue, now))
		if errors.Is(e, sql.ErrNoRows) {
			return nil
		}
		if e != nil {
			return e
		}
		t, e := token()
		if e != nil {
			return e
		}
		until := now + leaseMS
		_, e = c.ExecContext(ctx, "UPDATE jobs SET state='leased',attempts=attempts+1,lease_until_ms=?,lease_token=? WHERE id=?", until, t, j.ID)
		if e != nil {
			return e
		}
		j.State = "leased"
		j.Attempts++
		j.LeaseUntilMS = &until
		job = &j
		tok = &t
		return nil
	})
	return job, tok, e
}
func (s *Store) LeaseAction(ctx context.Context, tenant, id, action, tok string, leaseMS int64, detail string) (Job, error) {
	var out Job
	e := s.write(ctx, func(c *sql.Conn, now int64) error {
		j, e := get(ctx, c, tenant, id)
		if e != nil {
			return e
		}
		var live, completed sql.NullString
		e = c.QueryRowContext(ctx, "SELECT lease_token,completion_token FROM jobs WHERE id=?", id).Scan(&live, &completed)
		if e != nil {
			return e
		}
		if action == "complete" && j.State == "completed" && completed.Valid && completed.String == tok && string(j.Result) == detail {
			out = j
			return nil
		}
		if j.State != "leased" || !live.Valid || live.String != tok || j.LeaseUntilMS == nil || now >= *j.LeaseUntilMS {
			return LeaseConflict
		}
		switch action {
		case "heartbeat":
			until := now + leaseMS
			_, e = c.ExecContext(ctx, "UPDATE jobs SET lease_until_ms=? WHERE id=?", until, id)
		case "complete":
			_, e = c.ExecContext(ctx, "UPDATE jobs SET state='completed',result=?,lease_until_ms=NULL,lease_token=NULL,completion_token=? WHERE id=?", detail, tok, id)
		case "fail":
			state := "ready"
			if j.Attempts >= j.MaxAttempts {
				state = "dead"
			}
			_, e = c.ExecContext(ctx, "UPDATE jobs SET state=?,available_at_ms=?,lease_until_ms=NULL,lease_token=NULL,last_error=? WHERE id=?", state, now, detail, id)
		default:
			return fmt.Errorf("unknown action")
		}
		if e != nil {
			return e
		}
		out, e = get(ctx, c, tenant, id)
		return e
	})
	return out, e
}
func (s *Store) Stats(ctx context.Context, tenant, queue string) (map[string]int64, error) {
	m := map[string]int64{"total": 0, "ready": 0, "leased": 0, "completed": 0, "dead": 0, "cancelled": 0}
	q := "SELECT state,COUNT(*) FROM jobs WHERE tenant=?"
	args := []any{tenant}
	if queue != "" {
		q += " AND queue=?"
		args = append(args, queue)
	}
	q += " GROUP BY state"
	rows, e := s.DB.QueryContext(ctx, q, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	for rows.Next() {
		var state string
		var n int64
		if e = rows.Scan(&state, &n); e != nil {
			return nil, e
		}
		m[state] = n
		m["total"] += n
	}
	return m, rows.Err()
}
