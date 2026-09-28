package queue

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
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
var ErrCapacity = errors.New("capacity")

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
	DB          *sql.DB
	Clock       Clock
	MaxPending  int
	MaxInflight int
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
	Priority    int             `json:"priority"`
	RetryBase   int64           `json:"retry_base_ms"`
}

func Open(path string, c Clock) (*Store, error) {
	db, e := sql.Open("sqlite", path)
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	var version int
	readDeadline := time.Now().Add(12 * time.Second)
	for {
		e = db.QueryRow("PRAGMA user_version").Scan(&version)
		if e == nil {
			break
		}
		if (!strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy")) || time.Now().After(readDeadline) {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if e != nil {
		db.Close()
		return nil, fmt.Errorf("read schema version: %w", e)
	}
	if version > 2 {
		db.Close()
		return nil, fmt.Errorf("unsupported schema version")
	}
	if _, e = db.Exec("PRAGMA busy_timeout=10000"); e != nil {
		db.Close()
		return nil, fmt.Errorf("set busy timeout: %w", e)
	}
	for _, q := range []string{"PRAGMA journal_mode=WAL", "PRAGMA synchronous=FULL", "PRAGMA foreign_keys=ON"} {
		deadline := time.Now().Add(12 * time.Second)
		for {
			_, e = db.Exec(q)
			if e == nil {
				break
			}
			if q == "PRAGMA journal_mode=WAL" {
				var mode string
				if x := db.QueryRow("PRAGMA journal_mode").Scan(&mode); x == nil && strings.EqualFold(mode, "wal") {
					e = nil
					break
				}
			}
			if !strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy") {
				db.Close()
				return nil, fmt.Errorf("startup pragma failed: %w", e)
			}
			if time.Now().After(deadline) {
				db.Close()
				return nil, fmt.Errorf("%s failed: %w", q, e)
			}
			time.Sleep(50 * time.Millisecond)
		}
	}
	deadline := time.Now().Add(12 * time.Second)
	for {
		tx, be := db.Begin()
		e = be
		if e != nil {
			if time.Now().Before(deadline) {
				time.Sleep(50 * time.Millisecond)
				continue
			}
			break
		}
		// This transactional DDL serializes first-open and migration decisions across processes.
		if _, e = tx.Exec(`CREATE TABLE IF NOT EXISTS _queueforge_schema_lock (id INTEGER PRIMARY KEY)`); e == nil {
			e = tx.QueryRow("PRAGMA user_version").Scan(&version)
		}
		if e == nil && version > 2 {
			e = fmt.Errorf("unsupported schema version")
		}
		if e == nil && version == 0 {
			_, e = tx.Exec(`CREATE TABLE IF NOT EXISTS jobs(id TEXT NOT NULL UNIQUE,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload BLOB NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_seq INTEGER PRIMARY KEY AUTOINCREMENT,created_at_ms INTEGER NOT NULL,available_at_ms INTEGER NOT NULL,lease_until_ms INTEGER,lease_token TEXT,last_error TEXT,result BLOB,completed_token TEXT,completed_result BLOB,priority INTEGER NOT NULL DEFAULT 0,retry_base_ms INTEGER NOT NULL DEFAULT 0); CREATE INDEX IF NOT EXISTS jobs_claim ON jobs(tenant,queue,state,available_at_ms,priority DESC,created_seq); CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(tenant,state); CREATE INDEX IF NOT EXISTS jobs_inflight ON jobs(tenant,queue,state,lease_until_ms); CREATE INDEX IF NOT EXISTS jobs_list ON jobs(tenant,created_seq); CREATE INDEX IF NOT EXISTS jobs_list_queue ON jobs(tenant,queue,created_seq); CREATE TABLE IF NOT EXISTS idem(tenant TEXT,endpoint TEXT,key TEXT,input BLOB,ids BLOB,PRIMARY KEY(tenant,endpoint,key));`)
		} else if e == nil && version == 1 {
			_, e = tx.Exec(`ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0; ALTER TABLE jobs ADD COLUMN retry_base_ms INTEGER NOT NULL DEFAULT 0; DROP INDEX IF EXISTS jobs_claim; CREATE INDEX jobs_claim ON jobs(tenant,queue,state,available_at_ms,priority DESC,created_seq); CREATE INDEX jobs_pending ON jobs(tenant,state); CREATE INDEX jobs_inflight ON jobs(tenant,queue,state,lease_until_ms); CREATE INDEX jobs_list ON jobs(tenant,created_seq); CREATE INDEX jobs_list_queue ON jobs(tenant,queue,created_seq);`)
		}
		if e == nil {
			_, e = tx.Exec("PRAGMA user_version=2")
		}
		if e == nil {
			e = tx.Commit()
		} else {
			tx.Rollback()
		}
		if e == nil {
			break
		}
		if !strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy") {
			break
		}
		if time.Now().After(deadline) {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if e != nil {
		db.Close()
		return nil, fmt.Errorf("schema transaction failed: %w", e)
	}
	if c == nil {
		c = RealClock{}
	}
	db.SetMaxOpenConns(8)
	return &Store{DB: db, Clock: c, MaxPending: 100000, MaxInflight: 100000}, nil
}
func (s *Store) Close() error { return s.DB.Close() }
func (s *Store) now() int64   { return s.Clock.NowMillis() }
func (s *Store) get(ctx context.Context, tx *sql.Tx, tenant, id string) (Job, error) {
	var j Job
	var until sql.NullInt64
	var le sql.NullString
	var result []byte
	e := tx.QueryRowContext(ctx, `SELECT id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result,priority,retry_base_ms FROM jobs WHERE tenant=? AND id=?`, tenant, id).Scan(&j.ID, &j.Tenant, &j.Queue, &j.Payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAt, &j.AvailableAt, &until, &le, &result, &j.Priority, &j.RetryBase)
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
	Queue     string          `json:"queue"`
	Payload   json.RawMessage `json:"payload"`
	Max       int             `json:"max_attempts"`
	Priority  int             `json:"priority"`
	RunAt     int64           `json:"run_at_ms"`
	RetryBase int64           `json:"retry_base_ms"`
	RetrySet  bool            `json:"-"`
}

func (x *Input) UnmarshalJSON(b []byte) error {
	var fields map[string]json.RawMessage
	if e := json.Unmarshal(b, &fields); e != nil {
		return e
	}
	for k, v := range fields {
		switch k {
		case "queue", "payload", "max_attempts", "priority", "run_at_ms", "retry_base_ms":
		default:
			return fmt.Errorf("unknown field")
		}
		if (k == "max_attempts" || k == "priority" || k == "run_at_ms" || k == "retry_base_ms") && string(v) == "null" {
			return fmt.Errorf("integer field cannot be null")
		}
	}
	type wire struct {
		Queue     string          `json:"queue"`
		Payload   json.RawMessage `json:"payload"`
		Max       int             `json:"max_attempts"`
		Priority  int             `json:"priority"`
		RunAt     int64           `json:"run_at_ms"`
		RetryBase *int64          `json:"retry_base_ms"`
	}
	var w wire
	if e := json.Unmarshal(b, &w); e != nil {
		return e
	}
	x.Queue = w.Queue
	x.Payload = w.Payload
	x.Max = w.Max
	x.Priority = w.Priority
	x.RunAt = w.RunAt
	if w.RetryBase != nil {
		x.RetryBase = *w.RetryBase
		x.RetrySet = true
	}
	return nil
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
		if string(old) != string(raw) && !legacyEquivalent(old, ins) {
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
	var pending int
	if e = tx.QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE tenant=? AND state IN ('ready','leased')", tenant).Scan(&pending); e != nil {
		return nil, false, e
	}
	limit := s.MaxPending
	if pending+len(ins) > limit {
		return nil, false, ErrCapacity
	}
	now := s.now()
	jobs := make([]Job, 0, len(ins))
	ids := make([]string, 0, len(ins))
	for _, in := range ins {
		id := newID()
		available := in.RunAt
		if available == 0 {
			available = now
		}
		res, e := tx.ExecContext(ctx, `INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms,priority,retry_base_ms) VALUES(?,?,?,?, 'ready',0,?,?,?,?,?)`, id, tenant, in.Queue, in.Payload, in.Max, now, available, in.Priority, in.RetryBase)
		if e != nil {
			return nil, false, e
		}
		seq, _ := res.LastInsertId()
		jobs = append(jobs, Job{ID: id, Tenant: tenant, Queue: in.Queue, Payload: in.Payload, State: "ready", Attempts: 0, MaxAttempts: in.Max, CreatedSeq: seq, CreatedAt: now, AvailableAt: available, Priority: in.Priority, RetryBase: in.RetryBase})
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
	if _, e = tx.ExecContext(ctx, `UPDATE idem SET key=key WHERE 0`); e != nil {
		return nil, "", e
	}
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
		var deadline int64
		tx.QueryRowContext(ctx, "SELECT lease_until_ms FROM jobs WHERE id=?", x.id).Scan(&deadline)
		if x.a >= x.m {
			_, e = tx.ExecContext(ctx, "UPDATE jobs SET state='dead',lease_token=NULL,lease_until_ms=NULL WHERE id=?", x.id)
		} else {
			var base int64
			tx.QueryRowContext(ctx, "SELECT retry_base_ms FROM jobs WHERE id=?", x.id).Scan(&base)
			_, e = tx.ExecContext(ctx, "UPDATE jobs SET state='ready',lease_token=NULL,lease_until_ms=NULL,available_at_ms=?,last_error='lease_expired' WHERE id=?", retryAt(deadline, base, x.a), x.id)
		}
		if e != nil {
			return nil, "", e
		}
	}
	var inflight int
	if e = tx.QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms>?", t, q, now).Scan(&inflight); e != nil {
		return nil, "", e
	}
	if inflight >= s.MaxInflight {
		return nil, "", tx.Commit()
	}
	var id string
	e = tx.QueryRowContext(ctx, `SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at_ms<=? ORDER BY priority DESC,created_seq LIMIT 1`, t, q, now).Scan(&id)
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
	if _, e = tx.ExecContext(ctx, `UPDATE idem SET key=key WHERE 0`); e != nil {
		return Job{}, e
	}
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
		available := int64(0)
		if state == "ready" {
			available = retryAt(now, j.RetryBase, j.Attempts)
		}
		_, e = tx.ExecContext(ctx, "UPDATE jobs SET state=?,lease_token=NULL,lease_until_ms=NULL,available_at_ms=?,last_error=? WHERE id=?", state, available, msg, id)
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

func retryAt(at, base int64, attempt int) int64 {
	if base <= 0 {
		return at
	}
	mult := int64(1)
	for i := 1; i < attempt && mult < 60000; i++ {
		if mult > 30000 {
			mult = 60000
		} else {
			mult *= 2
		}
	}
	delay := base * mult
	if base > 0 && delay/base != mult {
		delay = 60000
	}
	if delay > 60000 {
		delay = 60000
	}
	return at + delay
}
func legacyEquivalent(old []byte, in []Input) bool {
	var xs []map[string]json.RawMessage
	if json.Unmarshal(old, &xs) != nil || len(xs) != len(in) {
		return false
	}
	for i := range xs {
		var queue string
		var payload json.RawMessage
		max := 3
		var priority, run int
		var retry int64
		json.Unmarshal(xs[i]["queue"], &queue)
		json.Unmarshal(xs[i]["payload"], &payload)
		if v := xs[i]["max_attempts"]; v != nil {
			json.Unmarshal(v, &max)
		}
		json.Unmarshal(xs[i]["priority"], &priority)
		json.Unmarshal(xs[i]["run_at_ms"], &run)
		json.Unmarshal(xs[i]["retry_base_ms"], &retry)
		b := in[i]
		var oldPayload, newPayload any
		json.Unmarshal(payload, &oldPayload)
		json.Unmarshal(b.Payload, &newPayload)
		ob, _ := json.Marshal(oldPayload)
		nb, _ := json.Marshal(newPayload)
		if queue != b.Queue || string(ob) != string(nb) || max != b.Max || priority != b.Priority || int64(run) != b.RunAt || (xs[i]["retry_base_ms"] == nil && b.RetryBase != 1000) || (xs[i]["retry_base_ms"] != nil && retry != b.RetryBase) {
			return false
		}
	}
	return true
}

type Cursor struct {
	Tenant string `json:"t"`
	Queue  string `json:"q"`
	Upper  int64  `json:"u"`
	Last   int64  `json:"l"`
}

func (s *Store) List(ctx context.Context, t, q string, limit int, cursor string) ([]Job, string, error) {
	var c Cursor
	if cursor != "" {
		b, e := base64.RawURLEncoding.DecodeString(cursor)
		valid := false
		if e == nil {
			d := json.NewDecoder(bytes.NewReader(b))
			d.DisallowUnknownFields()
			valid = d.Decode(&c) == nil && d.Decode(new(any)) == io.EOF
		}
		if !valid || c.Tenant != t || c.Queue != q || c.Upper < 0 || c.Last < 0 || c.Last > c.Upper {
			return nil, "", ErrValidation
		}
	} else {
		c.Tenant = t
		c.Queue = q
		query := "SELECT coalesce(max(created_seq),0) FROM jobs WHERE tenant=?"
		args := []any{t}
		if q != "" {
			query += " AND queue=?"
			args = append(args, q)
		}
		if e := s.DB.QueryRowContext(ctx, query, args...).Scan(&c.Upper); e != nil {
			return nil, "", e
		}
	}
	query := `SELECT id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result,priority,retry_base_ms FROM jobs WHERE tenant=? AND created_seq<=? AND created_seq>?`
	args := []any{t, c.Upper, c.Last}
	if q != "" {
		query += " AND queue=?"
		args = append(args, q)
	}
	query += " ORDER BY created_seq LIMIT ?"
	args = append(args, limit+1)
	rows, e := s.DB.QueryContext(ctx, query, args...)
	if e != nil {
		return nil, "", e
	}
	defer rows.Close()
	jobs := []Job{}
	for rows.Next() {
		var j Job
		var until sql.NullInt64
		var le sql.NullString
		var result []byte
		if e = rows.Scan(&j.ID, &j.Tenant, &j.Queue, &j.Payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAt, &j.AvailableAt, &until, &le, &result, &j.Priority, &j.RetryBase); e != nil {
			return nil, "", e
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
		jobs = append(jobs, j)
	}
	if e = rows.Err(); e != nil {
		return nil, "", e
	}
	next := ""
	if len(jobs) > limit {
		jobs = jobs[:limit]
		c.Last = jobs[len(jobs)-1].CreatedSeq
		b, _ := json.Marshal(c)
		next = base64.RawURLEncoding.EncodeToString(b)
	}
	return jobs, next, nil
}
func (s *Store) Cancel(ctx context.Context, t, id string) (Job, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return Job{}, e
	}
	defer tx.Rollback()
	if _, e = tx.ExecContext(ctx, `UPDATE idem SET key=key WHERE 0`); e != nil {
		return Job{}, e
	}
	j, e := s.get(ctx, tx, t, id)
	if e == sql.ErrNoRows {
		return Job{}, ErrMissing
	}
	if e != nil {
		return Job{}, e
	}
	if j.State == "cancelled" {
		return j, tx.Commit()
	}
	if j.State != "ready" && j.State != "leased" {
		return Job{}, ErrTransition
	}
	_, e = tx.ExecContext(ctx, "UPDATE jobs SET state='cancelled',lease_token=NULL,lease_until_ms=NULL WHERE tenant=? AND id=?", t, id)
	if e != nil {
		return Job{}, e
	}
	j, e = s.get(ctx, tx, t, id)
	if e != nil {
		return Job{}, e
	}
	return j, tx.Commit()
}
func (s *Store) SetLimits(p, i int) { s.MaxPending = p; s.MaxInflight = i }
