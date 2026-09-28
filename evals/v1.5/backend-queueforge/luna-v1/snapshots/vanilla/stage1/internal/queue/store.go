package queue

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	_ "queueforge/internal/platform"
)

var ErrMissing = errors.New("missing")
var ErrLease = errors.New("lease")
var ErrIdempotency = errors.New("idempotency")
var ErrTransition = errors.New("transition")

type Clock interface{ NowMillis() int64 }
type RealClock struct{}

func (RealClock) NowMillis() int64 { return time.Now().UnixMilli() }

type FileClock struct{ Path string }

func (c FileClock) NowMillis() int64 {
	b, e := os.ReadFile(c.Path)
	if e != nil {
		return time.Now().UnixMilli()
	}
	n, e := strconv.ParseInt(strings.TrimSpace(string(b)), 10, 64)
	if e != nil {
		return time.Now().UnixMilli()
	}
	return n
}

type Store struct {
	DB    *sql.DB
	Clock Clock
}
type Job struct {
	ID          string          `json:"id"`
	Tenant      string          `json:"tenant"`
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	State       string          `json:"state"`
	Attempts    int             `json:"attempts"`
	MaxAttempts int             `json:"max_attempts"`
	CreatedSeq  int64           `json:"created_seq"`
	CreatedAt   int64           `json:"created_at_ms"`
	AvailableAt int64           `json:"available_at_ms"`
	LeaseUntil  *int64          `json:"lease_until_ms"`
	LastError   *string         `json:"last_error"`
	Result      json.RawMessage `json:"result"`
}

func Open(path string, c Clock) (*Store, error) {
	db, e := sql.Open("sqlite", path)
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(8)
	for _, q := range []string{"PRAGMA journal_mode=WAL", "PRAGMA synchronous=FULL", "PRAGMA busy_timeout=10000", "PRAGMA foreign_keys=ON"} {
		if _, e = db.Exec(q); e != nil {
			db.Close()
			return nil, e
		}
	}
	_, e = db.Exec(`CREATE TABLE IF NOT EXISTS jobs(id TEXT NOT NULL UNIQUE,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload BLOB NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_seq INTEGER PRIMARY KEY AUTOINCREMENT,created_at_ms INTEGER NOT NULL,available_at_ms INTEGER NOT NULL,lease_until_ms INTEGER,lease_token TEXT,last_error TEXT,result BLOB,completed_token TEXT,completed_result BLOB);
 CREATE INDEX IF NOT EXISTS jobs_claim ON jobs(tenant,queue,state,available_at_ms,created_seq);
 CREATE TABLE IF NOT EXISTS idem(tenant TEXT,endpoint TEXT,key TEXT,input BLOB,ids BLOB,PRIMARY KEY(tenant,endpoint,key)); PRAGMA user_version=1`)
	if e != nil {
		db.Close()
		return nil, e
	}
	if c == nil {
		c = RealClock{}
	}
	return &Store{db, c}, nil
}
func (s *Store) Close() error { return s.DB.Close() }
func (s *Store) now() int64   { return s.Clock.NowMillis() }
func (s *Store) get(ctx context.Context, tx *sql.Tx, tenant, id string) (Job, error) {
	var j Job
	var until sql.NullInt64
	var le sql.NullString
	var result []byte
	e := tx.QueryRowContext(ctx, `SELECT id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result FROM jobs WHERE tenant=? AND id=?`, tenant, id).Scan(&j.ID, &j.Tenant, &j.Queue, &j.Payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAt, &j.AvailableAt, &until, &le, &result)
	if e != nil {
		return j, e
	}
	if until.Valid {
		j.LeaseUntil = &until.Int64
	}
	if le.Valid {
		j.LastError = &le.String
	}
	if result != nil {
		j.Result = json.RawMessage(result)
	}
	return j, nil
}
func (s *Store) Get(ctx context.Context, t, id string) (Job, error) {
	tx, e := s.DB.BeginTx(ctx, &sql.TxOptions{ReadOnly: true})
	if e != nil {
		return Job{}, e
	}
	defer tx.Rollback()
	return s.get(ctx, tx, t, id)
}

type Input struct {
	Queue   string          `json:"queue"`
	Payload json.RawMessage `json:"payload"`
	Max     int             `json:"max_attempts"`
}

func (s *Store) Submit(ctx context.Context, tenant, endpoint, key string, ins []Input) ([]Job, bool, error) {
	raw, _ := json.Marshal(ins)
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return nil, false, e
	}
	defer tx.Rollback()
	if _, e = tx.ExecContext(ctx, `UPDATE idem SET key=key WHERE 0`); e != nil {
		return nil, false, e
	}
	var old, idsraw []byte
	e = tx.QueryRowContext(ctx, "SELECT input,ids FROM idem WHERE tenant=? AND endpoint=? AND key=?", tenant, endpoint, key).Scan(&old, &idsraw)
	if e == nil {
		if string(old) != string(raw) {
			return nil, false, ErrIdempotency
		}
		var ids []string
		json.Unmarshal(idsraw, &ids)
		js := make([]Job, 0, len(ids))
		for _, id := range ids {
			j, er := s.get(ctx, tx, tenant, id)
			if er != nil {
				return nil, false, er
			}
			js = append(js, j)
		}
		return js, true, tx.Commit()
	}
	if e != sql.ErrNoRows {
		return nil, false, e
	}
	now := s.now()
	jobs := make([]Job, 0, len(ins))
	ids := make([]string, 0, len(ins))
	for _, in := range ins {
		id := newID()
		res, e := tx.ExecContext(ctx, `INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms) VALUES(?,?,?,?, 'ready',0,?,?,?)`, id, tenant, in.Queue, in.Payload, in.Max, now, now)
		if e != nil {
			return nil, false, e
		}
		seq, _ := res.LastInsertId()
		jobs = append(jobs, Job{ID: id, Tenant: tenant, Queue: in.Queue, Payload: in.Payload, State: "ready", Attempts: 0, MaxAttempts: in.Max, CreatedSeq: seq, CreatedAt: now, AvailableAt: now})
		ids = append(ids, id)
	}
	ib, _ := json.Marshal(ids)
	if _, e = tx.ExecContext(ctx, "INSERT INTO idem(tenant,endpoint,key,input,ids) VALUES(?,?,?,?,?)", tenant, endpoint, key, raw, ib); e != nil {
		return nil, false, e
	}
	return jobs, false, tx.Commit()
}
func (s *Store) Claim(ctx context.Context, t, q, worker string, ms int) (*Job, string, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return nil, "", e
	}
	defer tx.Rollback()
	now := s.now()
	rows, e := tx.QueryContext(ctx, `SELECT id,attempts,max_attempts FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=?`, t, q, now)
	if e != nil {
		return nil, "", e
	}
	type expired struct {
		id   string
		a, m int
	}
	xs := []expired{}
	for rows.Next() {
		var x expired
		rows.Scan(&x.id, &x.a, &x.m)
		xs = append(xs, x)
	}
	rows.Close()
	for _, x := range xs {
		if x.a >= x.m {
			_, e = tx.ExecContext(ctx, "UPDATE jobs SET state='dead',lease_token=NULL,lease_until_ms=NULL WHERE id=?", x.id)
		} else {
			_, e = tx.ExecContext(ctx, "UPDATE jobs SET state='ready',lease_token=NULL,lease_until_ms=NULL,available_at_ms=?,last_error='lease_expired' WHERE id=?", now, x.id)
		}
		if e != nil {
			return nil, "", e
		}
	}
	var id string
	e = tx.QueryRowContext(ctx, `SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at_ms<=? ORDER BY created_seq LIMIT 1`, t, q, now).Scan(&id)
	if e == sql.ErrNoRows {
		return nil, "", tx.Commit()
	}
	if e != nil {
		return nil, "", e
	}
	token := newID()
	until := now + int64(ms)
	r, e := tx.ExecContext(ctx, "UPDATE jobs SET state='leased',attempts=attempts+1,lease_token=?,lease_until_ms=? WHERE id=? AND state='ready'", token, until, id)
	if e != nil {
		return nil, "", e
	}
	n, _ := r.RowsAffected()
	if n != 1 {
		return nil, "", ErrLease
	}
	j, e := s.get(ctx, tx, t, id)
	if e != nil {
		return nil, "", e
	}
	if e = tx.Commit(); e != nil {
		return nil, "", e
	}
	return &j, token, nil
}
func (s *Store) Mutate(ctx context.Context, t, id, token, op string, ms int, value json.RawMessage) (Job, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return Job{}, e
	}
	defer tx.Rollback()
	j, e := s.get(ctx, tx, t, id)
	if e == sql.ErrNoRows {
		return Job{}, ErrMissing
	}
	if e != nil {
		return Job{}, e
	}
	now := s.now()
	var current string
	tx.QueryRowContext(ctx, "SELECT coalesce(lease_token,'') FROM jobs WHERE id=?", id).Scan(&current)
	if op == "complete" && j.State == "completed" {
		var ct string
		var cr []byte
		tx.QueryRowContext(ctx, "SELECT coalesce(completed_token,''),completed_result FROM jobs WHERE id=?", id).Scan(&ct, &cr)
		if ct == token && string(cr) == string(value) {
			return j, tx.Commit()
		}
		return Job{}, ErrLease
	}
	if j.State != "leased" || current != token || j.LeaseUntil == nil || now >= *j.LeaseUntil {
		return Job{}, ErrLease
	}
	switch op {
	case "heartbeat":
		_, e = tx.ExecContext(ctx, "UPDATE jobs SET lease_until_ms=? WHERE id=?", now+int64(ms), id)
	case "complete":
		_, e = tx.ExecContext(ctx, "UPDATE jobs SET state='completed',lease_token=NULL,lease_until_ms=NULL,result=?,completed_token=?,completed_result=? WHERE id=?", value, token, value, id)
	case "fail":
		state := "ready"
		if j.Attempts >= j.MaxAttempts {
			state = "dead"
		}
		var msg string
		json.Unmarshal(value, &msg)
		_, e = tx.ExecContext(ctx, "UPDATE jobs SET state=?,lease_token=NULL,lease_until_ms=NULL,available_at_ms=?,last_error=? WHERE id=?", state, now, msg, id)
	}
	if e != nil {
		return Job{}, e
	}
	j, e = s.get(ctx, tx, t, id)
	if e != nil {
		return Job{}, e
	}
	return j, tx.Commit()
}
func (s *Store) Stats(ctx context.Context, t, q string) (map[string]int, error) {
	m := map[string]int{"total": 0, "ready": 0, "leased": 0, "completed": 0, "dead": 0, "cancelled": 0}
	query := `SELECT state,count(*) FROM jobs WHERE tenant=?`
	args := []any{t}
	if q != "" {
		query += " AND queue=?"
		args = append(args, q)
	}
	query += " GROUP BY state"
	rows, e := s.DB.QueryContext(ctx, query, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	for rows.Next() {
		var state string
		var n int
		if e = rows.Scan(&state, &n); e != nil {
			return nil, e
		}
		m[state] = n
		m["total"] += n
	}
	return m, nil
}
func newID() string { return fmt.Sprintf("%d-%s", time.Now().UnixNano(), randomHex()) }
