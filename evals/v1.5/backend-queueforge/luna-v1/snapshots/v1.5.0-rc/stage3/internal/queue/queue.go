package queue

import (
	"bytes"
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type Clock interface{ Now() int64 }
type RealClock struct{}

func (RealClock) Now() int64 { return time.Now().UnixMilli() }

type FileClock string

func (f FileClock) Now() int64 {
	b, e := osReadFile(string(f))
	if e != nil {
		return time.Now().UnixMilli()
	}
	n, e := strconvParse(strings.TrimSpace(string(b)))
	if e != nil {
		return time.Now().UnixMilli()
	}
	return n
}

var osReadFile = func(p string) ([]byte, error) { return os.ReadFile(p) }
var strconvParse = func(s string) (int64, error) { return strconv.ParseInt(s, 10, 64) }

type Service struct {
	DB          *sql.DB
	Clock       Clock
	MaxPending  int
	MaxInflight int
}
type Input struct {
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	MaxAttempts int             `json:"max_attempts"`
	maxSet      bool
	Priority    int `json:"priority"`
	prioritySet bool
	RunAt       int64 `json:"run_at_ms"`
	runSet      bool
	RetryBase   int `json:"retry_base_ms"`
	retrySet    bool
}

func (in *Input) UnmarshalJSON(data []byte) error {
	type plain Input
	var decoded plain
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(&decoded); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	if raw, ok := fields["max_attempts"]; ok {
		if bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
			return errors.New("invalid max_attempts")
		}
		in.maxSet = true
	}
	if raw, ok := fields["priority"]; ok {
		if bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
			return errors.New("invalid priority")
		}
		in.prioritySet = true
	}
	if raw, ok := fields["run_at_ms"]; ok {
		if bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
			return errors.New("invalid run_at_ms")
		}
		in.runSet = true
	}
	if raw, ok := fields["retry_base_ms"]; ok {
		if bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
			return errors.New("invalid retry_base_ms")
		}
		in.retrySet = true
	}
	in.Queue, in.Payload, in.MaxAttempts = decoded.Queue, decoded.Payload, decoded.MaxAttempts
	in.Priority, in.RunAt, in.RetryBase = decoded.Priority, decoded.RunAt, decoded.RetryBase
	return nil
}

type Job struct {
	ID          string          `json:"id"`
	Tenant      string          `json:"tenant"`
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	State       string          `json:"state"`
	Attempts    int             `json:"attempts"`
	MaxAttempts int             `json:"max_attempts"`
	Priority    int             `json:"priority"`
	RetryBase   int             `json:"retry_base_ms"`
	CreatedSeq  int64           `json:"created_seq"`
	CreatedAt   int64           `json:"created_at_ms"`
	AvailableAt int64           `json:"available_at_ms"`
	LeaseUntil  *int64          `json:"lease_until_ms"`
	LastError   *string         `json:"last_error"`
	Result      json.RawMessage `json:"result"`
}

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

func validObject(p json.RawMessage) bool {
	if len(p) == 0 {
		return false
	}
	var m map[string]json.RawMessage
	return json.Unmarshal(p, &m) == nil && m != nil
}
func validPayload(p json.RawMessage) bool { return len(p) <= 16384 && validObject(p) }
func (s *Service) Init(ctx context.Context) error {
	var version int
	if e := s.DB.QueryRowContext(ctx, `PRAGMA user_version`).Scan(&version); e != nil {
		return e
	}
	if version > 2 {
		return errors.New("unsupported schema version")
	}
	if version == 0 || version == 1 {
		for attempt := 0; attempt < 10; attempt++ {
			_, e := s.DB.ExecContext(ctx, `PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL`)
			if e == nil {
				tx, x := s.DB.BeginTx(ctx, nil)
				if x != nil {
					e = x
				} else {
					var current int
					x = tx.QueryRowContext(ctx, `PRAGMA user_version`).Scan(&current)
					if x == nil && current > 2 {
						x = errors.New("unsupported schema version")
					}
					if x == nil && current == 0 {
						_, x = tx.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS jobs(id TEXT UNIQUE NOT NULL,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload BLOB NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_seq INTEGER PRIMARY KEY AUTOINCREMENT,created_at INTEGER NOT NULL,available_at INTEGER NOT NULL,lease_until INTEGER,lease_token TEXT,worker TEXT,last_error TEXT,result BLOB,completed_token TEXT,completed_result BLOB,priority INTEGER NOT NULL DEFAULT 0,retry_base_ms INTEGER NOT NULL DEFAULT 1000)`)
						if x == nil {
							_, x = tx.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT,endpoint TEXT,key TEXT,command BLOB,ids BLOB,PRIMARY KEY(tenant,endpoint,key))`)
						}
					}
					if x == nil && current == 1 {
						_, x = tx.ExecContext(ctx, `ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0; ALTER TABLE jobs ADD COLUMN retry_base_ms INTEGER NOT NULL DEFAULT 0`)
					}
					if x == nil {
						_, x = tx.ExecContext(ctx, `DROP INDEX IF EXISTS jobs_claim; CREATE INDEX jobs_claim ON jobs(tenant,queue,state,priority DESC,created_seq,available_at); CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(tenant,state); CREATE INDEX IF NOT EXISTS jobs_inflight ON jobs(tenant,queue,state,lease_until); PRAGMA user_version=2`)
					}
					if x == nil {
						x = tx.Commit()
					} else {
						_ = tx.Rollback()
					}
					e = x
				}
				if e == nil {
					return nil
				}
			}
			if !strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy") {
				return e
			}
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(time.Duration(attempt+1) * 50 * time.Millisecond):
			}
		}
		return errors.New("database initialization busy")
	}
	for attempt := 0; attempt < 10; attempt++ {
		_, e := s.DB.ExecContext(ctx, `PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL`)
		if e == nil {
			return nil
		}
		if !strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy") {
			return e
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(time.Duration(attempt+1) * 50 * time.Millisecond):
		}
	}
	return errors.New("database initialization busy")
}
func token() string { b := make([]byte, 24); _, _ = rand.Read(b); return hex.EncodeToString(b) }
func retryDelay(base, attempts int) int64 {
	d := int64(base)
	for i := 1; i < attempts && d < 60000; i++ {
		if d > 30000 {
			d = 60000
		} else {
			d *= 2
		}
	}
	if d > 60000 {
		return 60000
	}
	return d
}
func retryAt(deadline int64, base, attempts int) int64 { return deadline + retryDelay(base, attempts) }
func (s *Service) now() int64 {
	if s.Clock == nil {
		return time.Now().UnixMilli()
	}
	return s.Clock.Now()
}
func (s *Service) scan(row interface{ Scan(...any) error }) (Job, error) {
	var j Job
	var pay, result []byte
	var until sql.NullInt64
	var le sql.NullString
	e := row.Scan(&j.ID, &j.Tenant, &j.Queue, &pay, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedSeq, &j.CreatedAt, &j.AvailableAt, &until, &le, &result, &j.Priority, &j.RetryBase)
	j.Payload = pay
	if result != nil {
		j.Result = result
	}
	if until.Valid {
		j.LeaseUntil = &until.Int64
	}
	if le.Valid {
		j.LastError = &le.String
	}
	return j, e
}

const cols = `id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at,available_at,lease_until,last_error,result,priority,retry_base_ms`

func (s *Service) get(ctx context.Context, tx *sql.Tx, t, id string) (Job, error) {
	return s.scan(tx.QueryRowContext(ctx, `SELECT `+cols+` FROM jobs WHERE tenant=? AND id=?`, t, id))
}
func normalize(in Input) (Input, error) {
	if !ident.MatchString(in.Queue) || !validPayload(in.Payload) {
		return in, errors.New("invalid input")
	}
	if !in.maxSet && in.MaxAttempts == 0 {
		in.MaxAttempts = 3
	}
	if in.MaxAttempts < 1 || in.MaxAttempts > 10 {
		return in, errors.New("invalid attempts")
	}
	if !in.prioritySet && in.Priority == 0 {
		in.Priority = 0
	}
	if in.Priority < -10 || in.Priority > 10 {
		return in, errors.New("invalid priority")
	}
	if in.RunAt < 0 {
		return in, errors.New("invalid run_at_ms")
	}
	if !in.runSet {
		in.RunAt = 0
	}
	if !in.retrySet && in.RetryBase == 0 {
		in.RetryBase = 1000
	}
	if in.RetryBase < 0 || in.RetryBase > 60000 {
		return in, errors.New("invalid retry_base_ms")
	}
	var v any
	if json.Unmarshal(in.Payload, &v) != nil {
		return in, errors.New("invalid payload")
	}
	in.Payload, _ = json.Marshal(v)
	return in, nil
}
func (s *Service) create(ctx context.Context, tx *sql.Tx, t string, in Input) (Job, error) {
	id := token()
	now := s.now()
	available := now
	if in.runSet {
		available = in.RunAt
	}
	r, e := tx.ExecContext(ctx, `INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at,available_at,priority,retry_base_ms) VALUES(?,?,?,?, 'ready',0,?,?,?,?,?)`, id, t, in.Queue, in.Payload, in.MaxAttempts, now, available, in.Priority, in.RetryBase)
	if e != nil {
		return Job{}, e
	}
	seq, _ := r.LastInsertId()
	return Job{ID: id, Tenant: t, Queue: in.Queue, Payload: in.Payload, State: "ready", MaxAttempts: in.MaxAttempts, CreatedSeq: seq, CreatedAt: now, AvailableAt: available, Priority: in.Priority, RetryBase: in.RetryBase}, nil
}
func (s *Service) Submit(ctx context.Context, t, endpoint, key string, ins []Input) ([]Job, bool, error) {
	if len(ins) < 1 || len(ins) > 100 {
		return nil, false, errors.New("invalid batch size")
	}
	norm := make([]Input, len(ins))
	for i := range ins {
		n, e := normalize(ins[i])
		if e != nil {
			return nil, false, e
		}
		norm[i] = n
	}
	cmd, _ := json.Marshal(norm)
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return nil, false, e
	}
	defer tx.Rollback()
	var old, idsRaw []byte
	e = tx.QueryRowContext(ctx, `SELECT command,ids FROM idempotency WHERE tenant=? AND endpoint=? AND key=?`, t, endpoint, key).Scan(&old, &idsRaw)
	if e == nil {
		match := string(old) == string(cmd)
		if !match {
			var previous []Input
			if json.Unmarshal(old, &previous) == nil && len(previous) == len(norm) {
				match = true
				for i := range previous {
					previous[i].maxSet = true
					p, x := normalize(previous[i])
					// Version-one command encodings may contain the newly introduced
					// retry field with its zero Go value even though callers omitted it.
					if p.RetryBase == 0 && !norm[i].retrySet && norm[i].RetryBase == 1000 {
						p.RetryBase = 1000
					}
					if x != nil || p.Queue != norm[i].Queue || string(p.Payload) != string(norm[i].Payload) || p.MaxAttempts != norm[i].MaxAttempts || p.Priority != norm[i].Priority || p.RunAt != norm[i].RunAt || p.RetryBase != norm[i].RetryBase {
						match = false
						break
					}
				}
			}
		}
		if !match {
			return nil, false, ErrIdempotency
		}
		var ids []string
		_ = json.Unmarshal(idsRaw, &ids)
		jobs := make([]Job, 0, len(ids))
		for _, id := range ids {
			j, x := s.get(ctx, tx, t, id)
			if x != nil {
				return nil, false, x
			}
			jobs = append(jobs, j)
		}
		return jobs, true, tx.Commit()
	}
	if e != sql.ErrNoRows {
		return nil, false, e
	}
	var pending int
	if e = tx.QueryRowContext(ctx, `SELECT count(*) FROM jobs WHERE tenant=? AND state IN ('ready','leased')`, t).Scan(&pending); e != nil {
		return nil, false, e
	}
	limit := s.MaxPending
	if limit <= 0 {
		limit = 100000
	}
	if pending+len(norm) > limit {
		return nil, false, ErrCapacity
	}
	jobs := make([]Job, 0, len(norm))
	ids := make([]string, 0, len(norm))
	for _, in := range norm {
		j, x := s.create(ctx, tx, t, in)
		if x != nil {
			return nil, false, x
		}
		jobs = append(jobs, j)
		ids = append(ids, j.ID)
	}
	ib, _ := json.Marshal(ids)
	if _, e = tx.ExecContext(ctx, `INSERT INTO idempotency VALUES(?,?,?,?,?)`, t, endpoint, key, cmd, ib); e != nil {
		return nil, false, e
	}
	return jobs, false, tx.Commit()
}

var ErrIdempotency = errors.New("idempotency conflict")
var ErrCapacity = errors.New("capacity")

func (s *Service) Get(ctx context.Context, t, id string) (Job, error) {
	return s.scan(s.DB.QueryRowContext(ctx, `SELECT `+cols+` FROM jobs WHERE tenant=? AND id=?`, t, id))
}

type cursorData struct {
	Tenant string `json:"t"`
	Queue  string `json:"q"`
	After  int64  `json:"a"`
	Upper  int64  `json:"u"`
}

func encodeCursor(c cursorData) string {
	b, _ := json.Marshal(c)
	return base64.RawURLEncoding.EncodeToString(b)
}
func decodeCursor(v, t, q string) (cursorData, error) {
	var c cursorData
	b, e := base64.RawURLEncoding.DecodeString(v)
	if e != nil {
		return c, ErrCursor
	}
	if json.Unmarshal(b, &c) != nil || c.Tenant != t || c.Queue != q || c.After < 0 || c.Upper < c.After {
		return c, ErrCursor
	}
	return c, nil
}

var ErrCursor = errors.New("invalid cursor")

func (s *Service) List(ctx context.Context, t, q string, limit int, cursor string) ([]Job, string, error) {
	c := cursorData{Tenant: t, Queue: q}
	if cursor != "" {
		var e error
		c, e = decodeCursor(cursor, t, q)
		if e != nil {
			return nil, "", e
		}
	} else {
		if e := s.DB.QueryRowContext(ctx, `SELECT COALESCE(MAX(created_seq),0) FROM jobs`).Scan(&c.Upper); e != nil {
			return nil, "", e
		}
	}
	query := `SELECT ` + cols + ` FROM jobs WHERE tenant=? AND created_seq>? AND created_seq<=?`
	args := []any{t, c.After, c.Upper}
	if q != "" {
		query += ` AND queue=?`
		args = append(args, q)
	}
	query += ` ORDER BY created_seq LIMIT ?`
	args = append(args, limit+1)
	rows, e := s.DB.QueryContext(ctx, query, args...)
	if e != nil {
		return nil, "", e
	}
	defer rows.Close()
	out := []Job{}
	for rows.Next() {
		j, x := s.scan(rows)
		if x != nil {
			return nil, "", x
		}
		out = append(out, j)
	}
	if e = rows.Err(); e != nil {
		return nil, "", e
	}
	next := ""
	if len(out) > limit {
		out = out[:limit]
		last := out[len(out)-1].CreatedSeq
		c.After = last
		next = encodeCursor(c)
	}
	return out, next, nil
}
func (s *Service) Cancel(ctx context.Context, t, id string) (Job, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return Job{}, e
	}
	defer tx.Rollback()
	j, e := s.get(ctx, tx, t, id)
	if e != nil {
		return Job{}, e
	}
	if j.State == "cancelled" {
		_ = tx.Commit()
		return j, nil
	}
	if j.State != "ready" && j.State != "leased" {
		return Job{}, ErrTransition
	}
	_, e = tx.ExecContext(ctx, `UPDATE jobs SET state='cancelled',lease_token=NULL,lease_until=NULL,worker=NULL WHERE tenant=? AND id=? AND state IN ('ready','leased')`, t, id)
	if e != nil {
		return Job{}, e
	}
	j, e = s.get(ctx, tx, t, id)
	if e == nil {
		e = tx.Commit()
	}
	return j, e
}

var ErrTransition = errors.New("invalid transition")

func (s *Service) Claim(ctx context.Context, t, q, worker string, ms int) (*Job, string, *int64, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return nil, "", nil, e
	}
	defer tx.Rollback()
	now := s.now()
	rows, e := tx.QueryContext(ctx, `SELECT id,attempts,max_attempts,lease_until FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until<=?`, t, q, now)
	if e != nil {
		return nil, "", nil, e
	}
	type expired struct {
		id       string
		a, m     int
		deadline int64
	}
	xs := []expired{}
	for rows.Next() {
		var x expired
		_ = rows.Scan(&x.id, &x.a, &x.m, &x.deadline)
		xs = append(xs, x)
	}
	rows.Close()
	for _, x := range xs {
		if x.a >= x.m {
			_, e = tx.ExecContext(ctx, `UPDATE jobs SET state='dead',lease_until=NULL,lease_token=NULL,worker=NULL,last_error='lease_expired' WHERE id=?`, x.id)
		} else {
			var base int
			_ = tx.QueryRowContext(ctx, `SELECT retry_base_ms FROM jobs WHERE id=?`, x.id).Scan(&base)
			at := retryAt(x.deadline, base, x.a)
			_, e = tx.ExecContext(ctx, `UPDATE jobs SET state='ready',available_at=?,lease_until=NULL,lease_token=NULL,worker=NULL,last_error='lease_expired' WHERE id=?`, at, x.id)
		}
		if e != nil {
			return nil, "", nil, e
		}
	}
	var inflight int
	if e = tx.QueryRowContext(ctx, `SELECT count(*) FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until>?`, t, q, now).Scan(&inflight); e != nil {
		return nil, "", nil, e
	}
	limit := s.MaxInflight
	if limit <= 0 {
		limit = 100000
	}
	if inflight >= limit {
		if e = tx.Commit(); e != nil {
			return nil, "", nil, e
		}
		return nil, "", nil, nil
	}
	j, e := s.scan(tx.QueryRowContext(ctx, `SELECT `+cols+` FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at<=? ORDER BY priority DESC,created_seq LIMIT 1`, t, q, now))
	if e == sql.ErrNoRows {
		if e = tx.Commit(); e != nil {
			return nil, "", nil, e
		}
		return nil, "", nil, nil
	}
	if e != nil {
		return nil, "", nil, e
	}
	tok := token()
	deadline := now + int64(ms)
	_, e = tx.ExecContext(ctx, `UPDATE jobs SET state='leased',attempts=attempts+1,lease_until=?,lease_token=?,worker=? WHERE id=? AND state='ready'`, deadline, tok, worker, j.ID)
	if e != nil {
		return nil, "", nil, e
	}
	j, e = s.get(ctx, tx, t, j.ID)
	if e != nil {
		return nil, "", nil, e
	}
	if e = tx.Commit(); e != nil {
		return nil, "", nil, e
	}
	return &j, tok, &deadline, nil
}
func (s *Service) Heartbeat(ctx context.Context, t, id, tok string, ms int) (Job, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return Job{}, e
	}
	defer tx.Rollback()
	now := s.now()
	r, e := tx.ExecContext(ctx, `UPDATE jobs SET lease_until=? WHERE tenant=? AND id=? AND state='leased' AND lease_token=? AND lease_until>?`, now+int64(ms), t, id, tok, now)
	if e != nil {
		return Job{}, e
	}
	n, _ := r.RowsAffected()
	if n != 1 {
		return Job{}, ErrLease
	}
	j, e := s.get(ctx, tx, t, id)
	if e == nil {
		e = tx.Commit()
	}
	return j, e
}

var ErrLease = errors.New("lease conflict")

func (s *Service) Complete(ctx context.Context, t, id, tok string, result json.RawMessage) (Job, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return Job{}, e
	}
	defer tx.Rollback()
	var state, oldtok string
	var oldres []byte
	e = tx.QueryRowContext(ctx, `SELECT state,COALESCE(completed_token,''),completed_result FROM jobs WHERE tenant=? AND id=?`, t, id).Scan(&state, &oldtok, &oldres)
	if e != nil {
		return Job{}, e
	}
	if state == "completed" {
		if oldtok == tok && string(oldres) == string(result) {
			return s.get(ctx, tx, t, id)
		}
		return Job{}, ErrLease
	}
	now := s.now()
	r, e := tx.ExecContext(ctx, `UPDATE jobs SET state='completed',result=?,lease_token=NULL,lease_until=NULL,worker=NULL,completed_token=?,completed_result=? WHERE tenant=? AND id=? AND state='leased' AND lease_token=? AND lease_until>?`, result, tok, result, t, id, tok, now)
	if e != nil {
		return Job{}, e
	}
	n, _ := r.RowsAffected()
	if n != 1 {
		return Job{}, ErrLease
	}
	j, e := s.get(ctx, tx, t, id)
	if e == nil {
		e = tx.Commit()
	}
	return j, e
}
func (s *Service) Fail(ctx context.Context, t, id, tok, msg string) (Job, error) {
	tx, e := s.DB.BeginTx(ctx, nil)
	if e != nil {
		return Job{}, e
	}
	defer tx.Rollback()
	now := s.now()
	j, e := s.get(ctx, tx, t, id)
	if e != nil {
		return Job{}, e
	}
	state := "ready"
	if j.Attempts >= j.MaxAttempts {
		state = "dead"
	}
	at := now
	if state == "ready" {
		at = retryAt(now, j.RetryBase, j.Attempts)
	}
	r, e := tx.ExecContext(ctx, `UPDATE jobs SET state=?,available_at=?,last_error=?,lease_token=NULL,lease_until=NULL,worker=NULL WHERE tenant=? AND id=? AND state='leased' AND lease_token=? AND lease_until>?`, state, at, msg, t, id, tok, now)
	if e != nil {
		return Job{}, e
	}
	n, _ := r.RowsAffected()
	if n != 1 {
		return Job{}, ErrLease
	}
	j, e = s.get(ctx, tx, t, id)
	if e == nil {
		e = tx.Commit()
	}
	return j, e
}
func (s *Service) Stats(ctx context.Context, t, q string) (map[string]int, error) {
	out := map[string]int{"total": 0, "ready": 0, "leased": 0, "completed": 0, "dead": 0, "cancelled": 0}
	query := `SELECT state,count(*) FROM jobs WHERE tenant=?`
	args := []any{t}
	if q != "" {
		query += ` AND queue=?`
		args = append(args, q)
	}
	query += ` GROUP BY state`
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
		out[state] = n
		out["total"] += n
	}
	return out, nil
}
func ErrorString(e error) string { return fmt.Sprint(e) }
