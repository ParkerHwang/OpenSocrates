package queue

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
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
	DB          *sql.DB
	Now         Clock
	MaxPending  int
	MaxInflight int
}
type Job struct {
	ID            string          `json:"id"`
	Tenant        string          `json:"tenant"`
	Queue         string          `json:"queue"`
	Payload       json.RawMessage `json:"payload"`
	State         string          `json:"state"`
	Attempts      int             `json:"attempts"`
	MaxAttempts   int             `json:"max_attempts"`
	Priority      int             `json:"priority"`
	RetryBaseMS   int64           `json:"retry_base_ms"`
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
	Priority    int             `json:"priority"`
	RunAtMS     int64           `json:"run_at_ms"`
	RetryBaseMS int64           `json:"retry_base_ms"`
}
type fault string

const (
	NotFound            fault = "not_found"
	LeaseConflict       fault = "lease_conflict"
	IdempotencyConflict fault = "idempotency_conflict"
	Capacity            fault = "capacity"
	InvalidTransition   fault = "invalid_transition"
	Validation          fault = "validation"
)

func (f fault) Error() string { return string(f) }
func Code(e error) string {
	var f fault
	if errors.As(e, &f) {
		return string(f)
	}
	return "storage_unavailable"
}
func New(path string, clock Clock, limits ...int) (*Store, error) {
	db, e := sql.Open(platform.SQLiteDriver, path)
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	db.Exec("PRAGMA busy_timeout=10000")
	var version int
	if e = db.QueryRow("PRAGMA user_version").Scan(&version); e != nil {
		db.Close()
		return nil, e
	}
	if version > 2 {
		db.Close()
		return nil, fmt.Errorf("unsupported schema version %d", version)
	}
	if _, e = db.Exec("BEGIN IMMEDIATE"); e != nil {
		db.Close()
		return nil, e
	}
	defer func() {
		if e != nil {
			db.Exec("ROLLBACK")
			db.Close()
		}
	}()
	if e = db.QueryRow("PRAGMA user_version").Scan(&version); e != nil {
		return nil, e
	}
	if version > 2 {
		e = fmt.Errorf("unsupported schema version %d", version)
		return nil, e
	}
	if version == 0 {
		_, e = db.Exec(`CREATE TABLE jobs (created_seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_at_ms INTEGER NOT NULL,available_at_ms INTEGER NOT NULL,lease_until_ms INTEGER,lease_token TEXT,last_error TEXT,result TEXT,completion_token TEXT,priority INTEGER NOT NULL DEFAULT 0,retry_base_ms INTEGER NOT NULL DEFAULT 0)`)
		if e != nil {
			return nil, e
		}
		_, e = db.Exec(`CREATE TABLE idempotency (tenant TEXT NOT NULL,endpoint TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,ids TEXT NOT NULL,PRIMARY KEY(tenant,endpoint,key))`)
		if e != nil {
			return nil, e
		}
	}
	if version == 1 {
		for _, q := range []string{`ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0`, `ALTER TABLE jobs ADD COLUMN retry_base_ms INTEGER NOT NULL DEFAULT 0`} {
			if _, e = db.Exec(q); e != nil {
				return nil, e
			}
		}
	}
	if version < 2 {
		for _, q := range []string{`CREATE INDEX jobs_priority ON jobs(tenant,queue,state,priority DESC,created_seq)`, `CREATE INDEX jobs_list ON jobs(tenant,created_seq)`, `CREATE INDEX jobs_queue_list ON jobs(tenant,queue,created_seq)`, `CREATE INDEX jobs_inflight ON jobs(tenant,queue,state,lease_until_ms)`, `PRAGMA user_version=2`} {
			if _, e = db.Exec(q); e != nil {
				return nil, e
			}
		}
	}
	if _, e = db.Exec("COMMIT"); e != nil {
		return nil, e
	}
	maxPending, maxInflight := 100000, 100000
	if len(limits) > 0 {
		maxPending = limits[0]
	}
	if len(limits) > 1 {
		maxInflight = limits[1]
	}
	if _, e = db.Exec("PRAGMA journal_mode=WAL"); e != nil {
		db.Close()
		return nil, e
	}
	if _, e = db.Exec("PRAGMA synchronous=FULL"); e != nil {
		db.Close()
		return nil, e
	}
	return &Store{db, clock, maxPending, maxInflight}, nil
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

const cols = "id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result,priority,retry_base_ms"

type scanner interface{ Scan(...any) error }

func scan(r scanner) (Job, error) {
	var j Job
	var payload string
	var result sql.NullString
	var deadline sql.NullInt64
	var last sql.NullString
	e := r.Scan(&j.ID, &j.Tenant, &j.Queue, &payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAtMS, &j.AvailableAtMS, &deadline, &last, &result, &j.Priority, &j.RetryBaseMS)
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
			legacy := make([]struct {
				Queue       string          `json:"queue"`
				Payload     json.RawMessage `json:"payload"`
				MaxAttempts int             `json:"max_attempts"`
			}, len(inputs))
			legacyOK := true
			for i, in := range inputs {
				legacy[i] = struct {
					Queue       string          `json:"queue"`
					Payload     json.RawMessage `json:"payload"`
					MaxAttempts int             `json:"max_attempts"`
				}{in.Queue, in.Payload, in.MaxAttempts}
				if in.Priority != 0 || in.RunAtMS != 0 || in.RetryBaseMS != 1000 {
					legacyOK = false
				}
			}
			var legacyFP string
			if endpoint == "/v1/jobs" {
				b, _ := json.Marshal(legacy[0])
				legacyFP = string(b)
			} else {
				b, _ := json.Marshal(legacy)
				legacyFP = string(b)
			}
			if old != fp && !(legacyOK && old == legacyFP) {
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
		var pending int
		if e = c.QueryRowContext(ctx, "SELECT COUNT(*) FROM jobs WHERE tenant=? AND state IN ('ready','leased')", tenant).Scan(&pending); e != nil {
			return e
		}
		if pending+len(inputs) > s.MaxPending {
			return Capacity
		}
		ids := make([]string, 0, len(inputs))
		for _, in := range inputs {
			id, e := token()
			if e != nil {
				return e
			}
			available := now
			if in.RunAtMS > 0 {
				available = in.RunAtMS
			}
			r, e := c.ExecContext(ctx, "INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms,priority,retry_base_ms) VALUES(?,?,?,?, 'ready',0,?,?,?,?,?)", id, tenant, in.Queue, string(in.Payload), in.MaxAttempts, now, available, in.Priority, in.RetryBaseMS)
			if e != nil {
				return e
			}
			seq, e := r.LastInsertId()
			if e != nil {
				return e
			}
			j := Job{ID: id, Tenant: tenant, Queue: in.Queue, Payload: in.Payload, State: "ready", MaxAttempts: in.MaxAttempts, CreatedSeq: seq, CreatedAtMS: now, AvailableAtMS: available, Priority: in.Priority, RetryBaseMS: in.RetryBaseMS}
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
		_, e := c.ExecContext(ctx, "UPDATE jobs SET state=CASE WHEN attempts>=max_attempts THEN 'dead' ELSE 'ready' END,available_at_ms=lease_until_ms+MIN(60000,retry_base_ms*(1 << MIN(attempts-1,16))),lease_until_ms=NULL,lease_token=NULL,last_error='lease_expired' WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=?", tenant, queue, now)
		if e != nil {
			return e
		}
		var inflight int
		if e = c.QueryRowContext(ctx, "SELECT COUNT(*) FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms>?", tenant, queue, now).Scan(&inflight); e != nil {
			return e
		}
		if inflight >= s.MaxInflight {
			return nil
		}
		j, e := scan(c.QueryRowContext(ctx, "SELECT "+cols+" FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at_ms<=? ORDER BY priority DESC,created_seq LIMIT 1", tenant, queue, now))
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
			delay := j.RetryBaseMS * (1 << min(j.Attempts-1, 16))
			if delay > 60000 {
				delay = 60000
			}
			_, e = c.ExecContext(ctx, "UPDATE jobs SET state=?,available_at_ms=?,lease_until_ms=NULL,lease_token=NULL,last_error=? WHERE id=?", state, now+delay, detail, id)
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

func (s *Store) Cancel(ctx context.Context, tenant, id string) (Job, error) {
	var out Job
	e := s.write(ctx, func(c *sql.Conn, now int64) error {
		j, e := get(ctx, c, tenant, id)
		if e != nil {
			return e
		}
		switch j.State {
		case "completed", "dead":
			return InvalidTransition
		case "cancelled":
			out = j
			return nil
		}
		_, e = c.ExecContext(ctx, "UPDATE jobs SET state='cancelled',lease_until_ms=NULL,lease_token=NULL WHERE tenant=? AND id=?", tenant, id)
		if e != nil {
			return e
		}
		out, e = get(ctx, c, tenant, id)
		return e
	})
	return out, e
}

type pageCursor struct {
	Tenant string `json:"t"`
	Queue  string `json:"q"`
	After  int64  `json:"a"`
	Upper  int64  `json:"u"`
}

func (s *Store) List(ctx context.Context, tenant, queue string, limit int, cursor string) ([]Job, *string, error) {
	p := pageCursor{Tenant: tenant, Queue: queue}
	if cursor != "" {
		b, e := base64.RawURLEncoding.DecodeString(cursor)
		p = pageCursor{}
		if e != nil || len(b) > 512 || json.Unmarshal(b, &p) != nil || p.Tenant != tenant || p.Queue != queue || p.After <= 0 || p.Upper < p.After {
			return nil, nil, Validation
		}
		canonical, _ := json.Marshal(p)
		if string(canonical) != string(b) || base64.RawURLEncoding.EncodeToString(b) != cursor {
			return nil, nil, Validation
		}
	}
	// One read transaction fixes the initial upper bound together with the page.
	c, e := s.DB.Conn(ctx)
	if e != nil {
		return nil, nil, e
	}
	defer c.Close()
	if _, e = c.ExecContext(ctx, "BEGIN"); e != nil {
		return nil, nil, e
	}
	defer c.ExecContext(context.Background(), "ROLLBACK")
	if cursor == "" {
		q := "SELECT COALESCE(MAX(created_seq),0) FROM jobs WHERE tenant=?"
		args := []any{tenant}
		if queue != "" {
			q += " AND queue=?"
			args = append(args, queue)
		}
		if e = c.QueryRowContext(ctx, q, args...).Scan(&p.Upper); e != nil {
			return nil, nil, e
		}
	}
	q := "SELECT " + cols + " FROM jobs WHERE tenant=? AND created_seq>? AND created_seq<=?"
	args := []any{tenant, p.After, p.Upper}
	if queue != "" {
		q += " AND queue=?"
		args = append(args, queue)
	}
	q += " ORDER BY created_seq LIMIT ?"
	args = append(args, limit+1)
	rows, e := c.QueryContext(ctx, q, args...)
	if e != nil {
		return nil, nil, e
	}
	items := make([]Job, 0, limit+1)
	for rows.Next() {
		j, err := scan(rows)
		if err != nil {
			rows.Close()
			return nil, nil, err
		}
		items = append(items, j)
	}
	e = rows.Err()
	rows.Close()
	if e != nil {
		return nil, nil, e
	}
	if _, e = c.ExecContext(ctx, "COMMIT"); e != nil {
		return nil, nil, e
	}
	var next *string
	if len(items) > limit {
		items = items[:limit]
		p.After = items[len(items)-1].CreatedSeq
		b, _ := json.Marshal(p)
		v := base64.RawURLEncoding.EncodeToString(b)
		next = &v
	}
	return items, next, nil
}
