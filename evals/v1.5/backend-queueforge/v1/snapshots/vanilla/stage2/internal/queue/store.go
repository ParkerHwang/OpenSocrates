package queue

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
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
	RunAtMS     int64           `json:"run_at_ms,omitempty"`
	RunAtSet    bool            `json:"run_at_specified,omitempty"`
	RetryBaseMS int64           `json:"retry_base_ms,omitempty"`
}
type Store struct {
	db                      *sql.DB
	MaxPending, MaxInflight int
}

var ErrNotFound = errors.New("not found")
var ErrLease = errors.New("lease conflict")
var ErrIdem = errors.New("idempotency conflict")
var ErrTransition = errors.New("invalid transition")
var ErrCapacity = errors.New("capacity")

const columns = "id,tenant,queue,payload,state,attempts,max_attempts,seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result,priority,retry_base_ms"

func Open(path string) (*Store, error) { return OpenWithLimits(path, 100000, 100000) }
func OpenWithLimits(path string, maxPending, maxInflight int) (*Store, error) {
	// A future-version file must be rejected before SQLite opens it: closing a
	// connection can checkpoint WAL and change the main database header.
	if f, e := os.Open(path); e == nil {
		var header [64]byte
		n, readErr := f.Read(header[:])
		f.Close()
		if readErr == nil && n == len(header) && string(header[:16]) == "SQLite format 3\x00" {
			v := binary.BigEndian.Uint32(header[60:64])
			if v > 2 {
				return nil, fmt.Errorf("unsupported schema version %d", v)
			}
		}
	}
	db, err := sql.Open(platform.SQLiteDriver, path)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	fail := func(e error) (*Store, error) { db.Close(); return nil, e }
	if _, err = db.Exec("PRAGMA busy_timeout=10000"); err != nil {
		return fail(err)
	}
	// Check before journal mode or any write: a future database must remain untouched.
	var version int
	if err = db.QueryRow("PRAGMA user_version").Scan(&version); err != nil {
		return fail(err)
	}
	if version > 2 {
		return fail(fmt.Errorf("unsupported schema version %d", version))
	}
	for attempt := 0; attempt < 100; attempt++ {
		_, err = db.Exec("BEGIN IMMEDIATE")
		if err == nil {
			break
		}
		if !busy(err) {
			return fail(err)
		}
		time.Sleep(50 * time.Millisecond)
	}
	if err != nil {
		return fail(err)
	}
	committed := false
	defer func() {
		if !committed {
			db.Exec("ROLLBACK")
		}
	}()
	if err = db.QueryRow("PRAGMA user_version").Scan(&version); err != nil {
		return fail(err)
	}
	if version > 2 {
		return fail(fmt.Errorf("unsupported schema version %d", version))
	}
	if version == 0 {
		for _, q := range []string{`CREATE TABLE jobs (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, tenant TEXT NOT NULL, queue TEXT NOT NULL,
 payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
 created_at_ms INTEGER NOT NULL, available_at_ms INTEGER NOT NULL, lease_until_ms INTEGER,
 lease_token TEXT, completed_token TEXT, last_error TEXT, result TEXT,
 priority INTEGER NOT NULL DEFAULT 0, retry_base_ms INTEGER NOT NULL DEFAULT 1000)`,
			`CREATE TABLE idempotency (tenant TEXT NOT NULL, endpoint TEXT NOT NULL, key TEXT NOT NULL, command TEXT NOT NULL, ids TEXT NOT NULL, PRIMARY KEY(tenant,endpoint,key))`} {
			if _, err = db.Exec(q); err != nil {
				return fail(err)
			}
		}
	} else if version == 1 {
		for _, q := range []string{`ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0`, `ALTER TABLE jobs ADD COLUMN retry_base_ms INTEGER NOT NULL DEFAULT 0`} {
			if _, err = db.Exec(q); err != nil {
				return fail(err)
			}
		}
	}
	for _, q := range []string{`CREATE INDEX IF NOT EXISTS jobs_claim_v2 ON jobs(tenant,queue,state,priority DESC,seq,available_at_ms)`,
		`CREATE INDEX IF NOT EXISTS jobs_expire ON jobs(tenant,queue,state,lease_until_ms)`,
		`CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(tenant,state)`,
		`PRAGMA user_version=2`} {
		if _, err = db.Exec(q); err != nil {
			return fail(err)
		}
	}
	if _, err = db.Exec("COMMIT"); err != nil {
		return fail(err)
	}
	committed = true
	if _, err = db.Exec("PRAGMA journal_mode=WAL"); err != nil {
		return fail(err)
	}
	if _, err = db.Exec("PRAGMA synchronous=FULL"); err != nil {
		return fail(err)
	}
	return &Store{db: db, MaxPending: maxPending, MaxInflight: maxInflight}, nil
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
	err := row.Scan(&j.ID, &j.Tenant, &j.Queue, &payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAtMS, &j.AvailableAtMS, &until, &last, &result, &j.Priority, &j.RetryBaseMS)
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
				// A v1 command lacked the new fields. Its defaults are equivalent to a
				// v2 request with default scheduling and retry settings.
				var legacy []struct {
					Queue       string          `json:"queue"`
					Payload     json.RawMessage `json:"payload"`
					MaxAttempts int             `json:"max_attempts"`
				}
				var shape []map[string]json.RawMessage
				if json.Unmarshal([]byte(old), &shape) != nil || len(shape) != len(inputs) {
					return ErrIdem
				}
				for _, entry := range shape {
					if len(entry) != 3 {
						return ErrIdem
					}
				}
				if json.Unmarshal([]byte(old), &legacy) != nil || len(legacy) != len(inputs) {
					return ErrIdem
				}
				for n, in := range inputs {
					if in.Queue != legacy[n].Queue || string(in.Payload) != string(legacy[n].Payload) || in.MaxAttempts != legacy[n].MaxAttempts || in.Priority != 0 || in.RunAtSet || in.RetryBaseMS != 1000 {
						return ErrIdem
					}
				}
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
		var pending int
		if err = c.QueryRowContext(ctx, "SELECT COUNT(*) FROM jobs WHERE tenant=? AND state IN ('ready','leased')", tenant).Scan(&pending); err != nil {
			return err
		}
		if pending+len(inputs) > s.MaxPending {
			return ErrCapacity
		}
		jobs = make([]Job, 0, len(inputs))
		ids := make([]string, 0, len(inputs))
		for _, in := range inputs {
			id, e := token()
			if e != nil {
				return e
			}
			_, e = c.ExecContext(ctx, `INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms,priority,retry_base_ms) VALUES(?,?,?,?,'ready',0,?,?,?,?,?)`, id, tenant, in.Queue, string(in.Payload), in.MaxAttempts, now, scheduled(in.RunAtMS, in.RunAtSet, now), in.Priority, in.RetryBaseMS)
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
func scheduled(runAt int64, set bool, now int64) int64 {
	if !set && runAt == 0 {
		return now
	}
	return runAt
}
func retryDelay(base int64, attempts int) int64 {
	d := base << (attempts - 1)
	if d > 60000 {
		return 60000
	}
	return d
}
func (s *Store) Claim(ctx context.Context, tenant, queue string, now, leaseMS int64) (*Job, *string, error) {
	var out *Job
	var tok *string
	e := s.write(ctx, func(c *sql.Conn) error {
		_, e := c.ExecContext(ctx, `UPDATE jobs SET state='dead',lease_until_ms=NULL,lease_token=NULL,last_error='lease_expired' WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=? AND attempts>=max_attempts`, tenant, queue, now)
		if e != nil {
			return e
		}
		_, e = c.ExecContext(ctx, `UPDATE jobs SET state='ready',available_at_ms=lease_until_ms+MIN(60000,retry_base_ms*(1 << (attempts-1))),lease_until_ms=NULL,lease_token=NULL,last_error='lease_expired' WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=? AND attempts<max_attempts`, tenant, queue, now)
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
		var id string
		e = c.QueryRowContext(ctx, `SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at_ms<=? ORDER BY priority DESC,seq LIMIT 1`, tenant, queue, now).Scan(&id)
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
		_, e = c.ExecContext(ctx, "UPDATE jobs SET state=?,available_at_ms=?,lease_until_ms=NULL,lease_token=NULL,last_error=? WHERE id=?", state, now+retryDelay(j.RetryBaseMS, j.Attempts), msg, id)
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

func (s *Store) Cancel(ctx context.Context, tenant, id string) (Job, error) {
	var out Job
	e := s.write(ctx, func(c *sql.Conn) error {
		j, e := getTx(ctx, c, tenant, id)
		if e != nil {
			return e
		}
		if j.State == "completed" || j.State == "dead" {
			return ErrTransition
		}
		if j.State != "cancelled" {
			if _, e = c.ExecContext(ctx, "UPDATE jobs SET state='cancelled',lease_until_ms=NULL,lease_token=NULL WHERE id=?", id); e != nil {
				return e
			}
			j, e = getTx(ctx, c, tenant, id)
			if e != nil {
				return e
			}
		}
		out = j
		return nil
	})
	return out, e
}
func (s *Store) List(ctx context.Context, tenant, queue string, after, upper int64, limit int) ([]Job, bool, error) {
	q := "SELECT " + columns + " FROM jobs WHERE tenant=? AND seq>? AND seq<=?"
	args := []any{tenant, after, upper}
	if queue != "" {
		q += " AND queue=?"
		args = append(args, queue)
	}
	q += " ORDER BY seq LIMIT ?"
	args = append(args, limit+1)
	rows, e := s.db.QueryContext(ctx, q, args...)
	if e != nil {
		return nil, false, e
	}
	defer rows.Close()
	out := make([]Job, 0, limit+1)
	for rows.Next() {
		j, e := scanJob(rows)
		if e != nil {
			return nil, false, e
		}
		out = append(out, j)
	}
	if e = rows.Err(); e != nil {
		return nil, false, e
	}
	more := len(out) > limit
	if more {
		out = out[:limit]
	}
	return out, more, nil
}
func (s *Store) MaxSeq(ctx context.Context) (int64, error) {
	var n int64
	e := s.db.QueryRowContext(ctx, "SELECT COALESCE(MAX(seq),0) FROM jobs").Scan(&n)
	return n, e
}
