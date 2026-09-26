package queue

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"
	"time"

	"queueforge/internal/platform"
)

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
type Store struct{ db *sql.DB }

var ErrNotFound = errors.New("not found")
var ErrLease = errors.New("lease conflict")
var ErrIdem = errors.New("idempotency conflict")
var ErrTransition = errors.New("invalid transition")

const columns = "id,tenant,queue,payload,state,attempts,max_attempts,seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result"

func Open(path string) (*Store, error) {
	db, err := sql.Open(platform.SQLiteDriver, path)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	for _, s := range []string{"PRAGMA busy_timeout=10000", "PRAGMA journal_mode=WAL", "PRAGMA synchronous=FULL", `CREATE TABLE IF NOT EXISTS jobs (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, tenant TEXT NOT NULL, queue TEXT NOT NULL,
 payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
 created_at_ms INTEGER NOT NULL, available_at_ms INTEGER NOT NULL, lease_until_ms INTEGER,
 lease_token TEXT, completed_token TEXT, last_error TEXT, result TEXT)`,
		`CREATE INDEX IF NOT EXISTS jobs_claim ON jobs(tenant,queue,state,available_at_ms,seq)`,
		`CREATE INDEX IF NOT EXISTS jobs_expire ON jobs(tenant,queue,state,lease_until_ms)`,
		`CREATE TABLE IF NOT EXISTS idempotency (tenant TEXT NOT NULL, endpoint TEXT NOT NULL, key TEXT NOT NULL, command TEXT NOT NULL, ids TEXT NOT NULL, PRIMARY KEY(tenant,endpoint,key))`,
		"PRAGMA user_version=1"} {
		for attempt := 0; attempt < 100; attempt++ {
			_, err = db.Exec(s)
			if err == nil || !busy(err) {
				break
			}
			time.Sleep(50 * time.Millisecond)
		}
		if err != nil {
			db.Close()
			return nil, err
		}
	}
	return &Store{db}, nil
}
func (s *Store) Close() error { return s.db.Close() }
func busy(err error) bool {
	message := strings.ToLower(err.Error())
	return strings.Contains(message, "busy") || strings.Contains(message, "locked")
}
func token() (string, error) {
	var b [24]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(b[:]), nil
}
func scanJob(row interface{ Scan(...any) error }) (Job, error) {
	var j Job
	var payload string
	var until sql.NullInt64
	var last, result sql.NullString
	err := row.Scan(&j.ID, &j.Tenant, &j.Queue, &payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAtMS, &j.AvailableAtMS, &until, &last, &result)
	if err != nil {
		return j, err
	}
	j.Payload = json.RawMessage(payload)
	if until.Valid {
		j.LeaseUntilMS = &until.Int64
	}
	if last.Valid {
		j.LastError = &last.String
	}
	if result.Valid {
		j.Result = json.RawMessage(result.String)
	}
	return j, nil
}
func (s *Store) Get(ctx context.Context, tenant, id string) (Job, error) {
	j, e := scanJob(s.db.QueryRowContext(ctx, "SELECT "+columns+" FROM jobs WHERE tenant=? AND id=?", tenant, id))
	if errors.Is(e, sql.ErrNoRows) {
		return j, ErrNotFound
	}
	return j, e
}
func getTx(ctx context.Context, c *sql.Conn, tenant, id string) (Job, error) {
	j, e := scanJob(c.QueryRowContext(ctx, "SELECT "+columns+" FROM jobs WHERE tenant=? AND id=?", tenant, id))
	if errors.Is(e, sql.ErrNoRows) {
		return j, ErrNotFound
	}
	return j, e
}
func (s *Store) write(ctx context.Context, fn func(*sql.Conn) error) error {
	c, e := s.db.Conn(ctx)
	if e != nil {
		return e
	}
	defer c.Close()
	for i := 0; i < 5; i++ {
		_, e = c.ExecContext(ctx, "BEGIN IMMEDIATE")
		if e == nil {
			break
		}
		if !busy(e) {
			return e
		}
		time.Sleep(time.Duration(i+1) * 20 * time.Millisecond)
	}
	if e != nil {
		return e
	}
	defer c.ExecContext(context.Background(), "ROLLBACK")
	if e = fn(c); e != nil {
		return e
	}
	_, e = c.ExecContext(ctx, "COMMIT")
	return e
}
func (s *Store) Submit(ctx context.Context, tenant, endpoint, key, command string, inputs []Input, now int64) ([]Job, bool, error) {
	var jobs []Job
	replay := false
	e := s.write(ctx, func(c *sql.Conn) error {
		var old, idsText string
		err := c.QueryRowContext(ctx, "SELECT command,ids FROM idempotency WHERE tenant=? AND endpoint=? AND key=?", tenant, endpoint, key).Scan(&old, &idsText)
		if err == nil {
			if old != command {
				return ErrIdem
			}
			var ids []string
			if e := json.Unmarshal([]byte(idsText), &ids); e != nil {
				return e
			}
			jobs = make([]Job, 0, len(ids))
			for _, id := range ids {
				j, e := getTx(ctx, c, tenant, id)
				if e != nil {
					return e
				}
				jobs = append(jobs, j)
			}
			replay = true
			return nil
		}
		if !errors.Is(err, sql.ErrNoRows) {
			return err
		}
		jobs = make([]Job, 0, len(inputs))
		ids := make([]string, 0, len(inputs))
		for _, in := range inputs {
			id, e := token()
			if e != nil {
				return e
			}
			_, e = c.ExecContext(ctx, `INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms) VALUES(?,?,?,?,'ready',0,?,?,?)`, id, tenant, in.Queue, string(in.Payload), in.MaxAttempts, now, now)
			if e != nil {
				return e
			}
			j, e := getTx(ctx, c, tenant, id)
			if e != nil {
				return e
			}
			jobs = append(jobs, j)
			ids = append(ids, id)
		}
		idsJSON, _ := json.Marshal(ids)
		_, err = c.ExecContext(ctx, "INSERT INTO idempotency(tenant,endpoint,key,command,ids) VALUES(?,?,?,?,?)", tenant, endpoint, key, command, string(idsJSON))
		return err
	})
	return jobs, replay, e
}
func (s *Store) Claim(ctx context.Context, tenant, queue string, now, leaseMS int64) (*Job, *string, error) {
	var out *Job
	var tok *string
	e := s.write(ctx, func(c *sql.Conn) error {
		_, e := c.ExecContext(ctx, `UPDATE jobs SET state='dead',lease_until_ms=NULL,lease_token=NULL,last_error='lease_expired' WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=? AND attempts>=max_attempts`, tenant, queue, now)
		if e != nil {
			return e
		}
		_, e = c.ExecContext(ctx, `UPDATE jobs SET state='ready',available_at_ms=?,lease_until_ms=NULL,lease_token=NULL,last_error='lease_expired' WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=? AND attempts<max_attempts`, now, tenant, queue, now)
		if e != nil {
			return e
		}
		var id string
		e = c.QueryRowContext(ctx, `SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at_ms<=? ORDER BY seq LIMIT 1`, tenant, queue, now).Scan(&id)
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
		_, e = c.ExecContext(ctx, `UPDATE jobs SET state='leased',attempts=attempts+1,lease_until_ms=?,lease_token=? WHERE id=?`, now+leaseMS, t, id)
		if e != nil {
			return e
		}
		j, e := getTx(ctx, c, tenant, id)
		if e != nil {
			return e
		}
		out = &j
		tok = &t
		return nil
	})
	return out, tok, e
}
func (s *Store) Heartbeat(ctx context.Context, tenant, id, tok string, now, leaseMS int64) (Job, error) {
	var out Job
	e := s.write(ctx, func(c *sql.Conn) error {
		j, e := getTx(ctx, c, tenant, id)
		if e != nil {
			return e
		}
		if j.State != "leased" || j.LeaseUntilMS == nil || now >= *j.LeaseUntilMS {
			return ErrLease
		}
		var actual string
		e = c.QueryRowContext(ctx, "SELECT lease_token FROM jobs WHERE id=?", id).Scan(&actual)
		if e != nil {
			return e
		}
		if actual != tok {
			return ErrLease
		}
		_, e = c.ExecContext(ctx, "UPDATE jobs SET lease_until_ms=? WHERE id=?", now+leaseMS, id)
		if e != nil {
			return e
		}
		out, e = getTx(ctx, c, tenant, id)
		return e
	})
	return out, e
}
func (s *Store) Complete(ctx context.Context, tenant, id, tok string, result json.RawMessage, now int64) (Job, error) {
	var out Job
	e := s.write(ctx, func(c *sql.Conn) error {
		j, e := getTx(ctx, c, tenant, id)
		if e != nil {
			return e
		}
		var live, completed sql.NullString
		e = c.QueryRowContext(ctx, "SELECT lease_token,completed_token FROM jobs WHERE id=?", id).Scan(&live, &completed)
		if e != nil {
			return e
		}
		if j.State == "completed" {
			if completed.Valid && completed.String == tok && string(j.Result) == string(result) {
				out = j
				return nil
			}
			return ErrLease
		}
		if j.State != "leased" || !live.Valid || live.String != tok || j.LeaseUntilMS == nil || now >= *j.LeaseUntilMS {
			return ErrLease
		}
		_, e = c.ExecContext(ctx, `UPDATE jobs SET state='completed',lease_until_ms=NULL,lease_token=NULL,completed_token=?,result=? WHERE id=?`, tok, string(result), id)
		if e != nil {
			return e
		}
		out, e = getTx(ctx, c, tenant, id)
		return e
	})
	return out, e
}
func (s *Store) Fail(ctx context.Context, tenant, id, tok, msg string, now int64) (Job, error) {
	var out Job
	e := s.write(ctx, func(c *sql.Conn) error {
		j, e := getTx(ctx, c, tenant, id)
		if e != nil {
			return e
		}
		if j.State != "leased" || j.LeaseUntilMS == nil || now >= *j.LeaseUntilMS {
			return ErrLease
		}
		var actual string
		e = c.QueryRowContext(ctx, "SELECT lease_token FROM jobs WHERE id=?", id).Scan(&actual)
		if e != nil {
			return e
		}
		if actual != tok {
			return ErrLease
		}
		state := "ready"
		if j.Attempts >= j.MaxAttempts {
			state = "dead"
		}
		_, e = c.ExecContext(ctx, "UPDATE jobs SET state=?,available_at_ms=?,lease_until_ms=NULL,lease_token=NULL,last_error=? WHERE id=?", state, now, msg, id)
		if e != nil {
			return e
		}
		out, e = getTx(ctx, c, tenant, id)
		return e
	})
	return out, e
}
func (s *Store) Stats(ctx context.Context, tenant, queue string) (map[string]int64, error) {
	q := "SELECT state,COUNT(*) FROM jobs WHERE tenant=?"
	args := []any{tenant}
	if queue != "" {
		q += " AND queue=?"
		args = append(args, queue)
	}
	q += " GROUP BY state"
	rows, e := s.db.QueryContext(ctx, q, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	m := map[string]int64{"total": 0, "ready": 0, "leased": 0, "completed": 0, "dead": 0, "cancelled": 0}
	for rows.Next() {
		var state string
		var n int64
		if e = rows.Scan(&state, &n); e != nil {
			return nil, e
		}
		m[state] = n
		m["total"] += n
	}
	if e = rows.Err(); e != nil {
		return nil, e
	}
	return m, nil
}
