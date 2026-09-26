package queueforge

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"queueforge/internal/platform"
)

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)
var errValidation = errors.New("validation")

type APIError struct {
	Status int
	Code   string
}

func bad() *APIError                 { return &APIError{400, "validation"} }
func missing() *APIError             { return &APIError{404, "not_found"} }
func conflict(code string) *APIError { return &APIError{409, code} }
func storage() *APIError             { return &APIError{503, "storage_unavailable"} }
func (e *APIError) Error() string    { return e.Code }

type Clock func() (int64, error)

func RealClock() (int64, error) { return time.Now().UnixMilli(), nil }
func FileClock(path string) Clock {
	return func() (int64, error) {
		b, e := os.ReadFile(path)
		if e != nil {
			return 0, e
		}
		return strconv.ParseInt(strings.TrimSpace(string(b)), 10, 64)
	}
}

type Service struct {
	DB          *sql.DB
	Clock       Clock
	MaxPending  int
	MaxInflight int
}

func Open(path string, clock Clock) (*Service, error) {
	return OpenWithLimits(path, clock, 100000, 100000)
}
func OpenWithLimits(path string, clock Clock, maxPending, maxInflight int) (*Service, error) {
	if maxPending <= 0 || maxInflight <= 0 {
		return nil, fmt.Errorf("limits must be positive")
	}
	db, e := sql.Open(platform.SQLiteDriver, path)
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	var version int
	for attempt := 0; attempt < 100; attempt++ {
		e = db.QueryRow(`PRAGMA user_version`).Scan(&version)
		if e == nil || (!strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy")) {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if e != nil {
		db.Close()
		return nil, e
	}
	if version > 2 {
		db.Close()
		return nil, fmt.Errorf("unsupported schema version %d", version)
	}
	for _, q := range []string{"PRAGMA busy_timeout=10000", "PRAGMA journal_mode=WAL", "PRAGMA synchronous=FULL"} {
		for attempt := 0; attempt < 100; attempt++ {
			_, e = db.Exec(q)
			if e == nil || (!strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy")) {
				break
			}
			time.Sleep(50 * time.Millisecond)
		}
		if e != nil {
			db.Close()
			return nil, e
		}
	}
	c, e := db.Conn(context.Background())
	if e != nil {
		db.Close()
		return nil, e
	}
	defer c.Close()
	for attempt := 0; attempt < 100; attempt++ {
		_, e = c.ExecContext(context.Background(), "BEGIN IMMEDIATE")
		if e == nil || (!strings.Contains(strings.ToLower(e.Error()), "locked") && !strings.Contains(strings.ToLower(e.Error()), "busy")) {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if e != nil {
		db.Close()
		return nil, e
	}
	committed := false
	defer func() {
		if !committed {
			c.ExecContext(context.Background(), "ROLLBACK")
		}
	}()
	if e = c.QueryRowContext(context.Background(), `PRAGMA user_version`).Scan(&version); e != nil {
		db.Close()
		return nil, e
	}
	if version > 2 {
		db.Close()
		return nil, fmt.Errorf("unsupported schema version %d", version)
	}
	var schema []string
	if version == 0 {
		schema = []string{`CREATE TABLE jobs (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, tenant TEXT NOT NULL, queue TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL, created_at_ms INTEGER NOT NULL, available_at_ms INTEGER NOT NULL, lease_until_ms INTEGER, lease_token TEXT, last_error TEXT, result TEXT, completed_token TEXT, priority INTEGER NOT NULL DEFAULT 0, retry_base_ms INTEGER NOT NULL DEFAULT 1000)`, `CREATE TABLE idempotency (tenant TEXT NOT NULL, endpoint TEXT NOT NULL, key TEXT NOT NULL, command TEXT NOT NULL, ids TEXT NOT NULL, PRIMARY KEY(tenant,endpoint,key))`}
	}
	if version == 1 {
		schema = []string{`ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0`, `ALTER TABLE jobs ADD COLUMN retry_base_ms INTEGER NOT NULL DEFAULT 0`}
	}
	if version < 2 {
		schema = append(schema, `CREATE INDEX jobs_claim_v2 ON jobs(tenant,queue,state,priority DESC,seq)`, `CREATE INDEX jobs_inflight_v2 ON jobs(tenant,queue,state,lease_until_ms)`, `CREATE INDEX jobs_pending_v2 ON jobs(tenant,state)`, `CREATE INDEX jobs_list_v2 ON jobs(tenant,queue,seq)`, `PRAGMA user_version=2`)
	}
	for _, q := range schema {
		if _, e = c.ExecContext(context.Background(), q); e != nil {
			db.Close()
			return nil, e
		}
	}
	if _, e = c.ExecContext(context.Background(), "COMMIT"); e != nil {
		db.Close()
		return nil, e
	}
	committed = true
	if clock == nil {
		clock = RealClock
	}
	return &Service{DB: db, Clock: clock, MaxPending: maxPending, MaxInflight: maxInflight}, nil
}
func (s *Service) Close() error { return s.DB.Close() }

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
type rowQuerier interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}

const jobCols = `id,tenant,queue,payload,state,attempts,max_attempts,priority,retry_base_ms,seq,created_at_ms,available_at_ms,lease_until_ms,last_error,result`

func getJob(ctx context.Context, q rowQuerier, tenant, id string) (Job, error) {
	var j Job
	var p string
	var res sql.NullString
	var lease sql.NullInt64
	var last sql.NullString
	e := q.QueryRowContext(ctx, `SELECT `+jobCols+` FROM jobs WHERE tenant=? AND id=?`, tenant, id).Scan(&j.ID, &j.Tenant, &j.Queue, &p, &j.State, &j.Attempts, &j.MaxAttempts, &j.Priority, &j.RetryBaseMS, &j.CreatedSeq, &j.CreatedAtMS, &j.AvailableAtMS, &lease, &last, &res)
	if e != nil {
		return j, e
	}
	j.Payload = json.RawMessage(p)
	if lease.Valid {
		j.LeaseUntilMS = &lease.Int64
	}
	if last.Valid {
		j.LastError = &last.String
	}
	if res.Valid {
		j.Result = json.RawMessage(res.String)
	}
	return j, nil
}
func token() (string, error) {
	b := make([]byte, 24)
	_, e := rand.Read(b)
	return hex.EncodeToString(b), e
}
func (s *Service) write(ctx context.Context, f func(*sql.Conn) *APIError) *APIError {
	c, e := s.DB.Conn(ctx)
	if e != nil {
		return storage()
	}
	defer c.Close()
	// PRAGMAs are connection-local. Reassert durability if database/sql replaced
	// the connection since startup.
	if _, e = c.ExecContext(ctx, "PRAGMA busy_timeout=10000"); e != nil {
		return storage()
	}
	if _, e = c.ExecContext(ctx, "PRAGMA synchronous=FULL"); e != nil {
		return storage()
	}
	if _, e = c.ExecContext(ctx, "BEGIN IMMEDIATE"); e != nil {
		return storage()
	}
	done := false
	defer func() {
		if !done {
			c.ExecContext(context.Background(), "ROLLBACK")
		}
	}()
	if x := f(c); x != nil {
		return x
	}
	if _, e = c.ExecContext(ctx, "COMMIT"); e != nil {
		return storage()
	}
	done = true
	return nil
}
func respond(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func sendErr(w http.ResponseWriter, e *APIError) {
	if e == nil {
		return
	}
	respond(w, e.Status, map[string]any{"error": map[string]string{"code": e.Code, "message": e.Code}})
}
func decode(r *http.Request, v any) *APIError {
	r.Body = http.MaxBytesReader(nil, r.Body, 1<<20)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if d.Decode(v) != nil {
		return bad()
	}
	var extra any
	if e := d.Decode(&extra); e != io.EOF {
		return bad()
	}
	return nil
}
func canonical(b json.RawMessage) (json.RawMessage, error) {
	var v any
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.UseNumber()
	if e := d.Decode(&v); e != nil {
		return nil, e
	}
	if _, ok := v.(map[string]any); !ok {
		return nil, errValidation
	}
	return json.Marshal(v)
}

type Input struct {
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	MaxAttempts json.RawMessage `json:"max_attempts,omitempty"`
	Priority    json.RawMessage `json:"priority,omitempty"`
	RunAtMS     json.RawMessage `json:"run_at_ms,omitempty"`
	RetryBaseMS json.RawMessage `json:"retry_base_ms,omitempty"`
}
type commandInput struct {
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	MaxAttempts int             `json:"max_attempts"`
	Priority    int             `json:"priority"`
	RunAtMS     *int64          `json:"run_at_ms,omitempty"`
	RetryBaseMS int64           `json:"retry_base_ms"`
}

func normalize(in Input) (commandInput, *APIError) {
	var x commandInput
	if !ident.MatchString(in.Queue) || len(in.Payload) == 0 || len(in.Payload) > 16*1024 {
		return x, bad()
	}
	p, e := canonical(in.Payload)
	if e != nil {
		return x, bad()
	}
	n := 3
	if len(in.MaxAttempts) != 0 {
		if string(in.MaxAttempts) == "null" || json.Unmarshal(in.MaxAttempts, &n) != nil {
			return x, bad()
		}
	}
	if n < 1 || n > 10 {
		return x, bad()
	}
	priority := 0
	retry := int64(1000)
	var runAt *int64
	if len(in.Priority) > 0 {
		if string(in.Priority) == "null" || json.Unmarshal(in.Priority, &priority) != nil {
			return x, bad()
		}
	}
	if len(in.RetryBaseMS) > 0 {
		if string(in.RetryBaseMS) == "null" || json.Unmarshal(in.RetryBaseMS, &retry) != nil {
			return x, bad()
		}
	}
	if len(in.RunAtMS) > 0 {
		var v int64
		if string(in.RunAtMS) == "null" || json.Unmarshal(in.RunAtMS, &v) != nil || v < 0 {
			return x, bad()
		}
		runAt = &v
	}
	if priority < -10 || priority > 10 || retry < 0 || retry > 60000 {
		return x, bad()
	}
	return commandInput{in.Queue, p, n, priority, runAt, retry}, nil
}
func idempotencyKey(r *http.Request) (string, *APIError) {
	k := r.Header.Get("Idempotency-Key")
	if len(k) == 0 || len(k) > 128 {
		return "", bad()
	}
	for _, c := range []byte(k) {
		if c < 32 || c > 126 {
			return "", bad()
		}
	}
	return k, nil
}
func (s *Service) submit(w http.ResponseWriter, r *http.Request, tenant string, batch bool) {
	key, x := idempotencyKey(r)
	if x != nil {
		sendErr(w, x)
		return
	}
	var inputs []Input
	if batch {
		var req struct {
			Jobs []Input `json:"jobs"`
		}
		if x = decode(r, &req); x != nil {
			sendErr(w, x)
			return
		}
		if len(req.Jobs) < 1 || len(req.Jobs) > 100 {
			sendErr(w, bad())
			return
		}
		inputs = req.Jobs
	} else {
		var in Input
		if x = decode(r, &in); x != nil {
			sendErr(w, x)
			return
		}
		inputs = []Input{in}
	}
	normalized := make([]commandInput, len(inputs))
	for i, in := range inputs {
		normalized[i], x = normalize(in)
		if x != nil {
			sendErr(w, x)
			return
		}
	}
	cmd, _ := json.Marshal(normalized)
	legacy := make([]struct {
		Queue       string          `json:"queue"`
		Payload     json.RawMessage `json:"payload"`
		MaxAttempts int             `json:"max_attempts"`
	}, len(normalized))
	legacyCompatible := true
	for i, in := range normalized {
		legacy[i].Queue, legacy[i].Payload, legacy[i].MaxAttempts = in.Queue, in.Payload, in.MaxAttempts
		if in.Priority != 0 || in.RunAtMS != nil || in.RetryBaseMS != 1000 {
			legacyCompatible = false
		}
	}
	legacyCmd, _ := json.Marshal(legacy)
	endpoint := "jobs"
	if batch {
		endpoint = "batch"
	}
	now, e := s.Clock()
	if e != nil {
		sendErr(w, storage())
		return
	}
	var jobs []Job
	replay := false
	x = s.write(r.Context(), func(c *sql.Conn) *APIError {
		var old, idsText string
		e := c.QueryRowContext(r.Context(), `SELECT command,ids FROM idempotency WHERE tenant=? AND endpoint=? AND key=?`, tenant, endpoint, key).Scan(&old, &idsText)
		if e == nil {
			if old != string(cmd) && !(legacyCompatible && old == string(legacyCmd)) {
				return conflict("idempotency_conflict")
			}
			var ids []string
			if json.Unmarshal([]byte(idsText), &ids) != nil {
				return storage()
			}
			for _, id := range ids {
				j, e := getJob(r.Context(), c, tenant, id)
				if e != nil {
					return storage()
				}
				jobs = append(jobs, j)
			}
			replay = true
			return nil
		}
		if e != sql.ErrNoRows {
			return storage()
		}
		var pending int
		if e = c.QueryRowContext(r.Context(), `SELECT count(*) FROM jobs WHERE tenant=? AND state IN ('ready','leased')`, tenant).Scan(&pending); e != nil {
			return storage()
		}
		if int64(pending)+int64(len(normalized)) > int64(s.MaxPending) {
			return &APIError{429, "capacity"}
		}
		ids := make([]string, len(normalized))
		for i, in := range normalized {
			id, e := token()
			if e != nil {
				return storage()
			}
			ids[i] = id
			available := now
			if in.RunAtMS != nil {
				available = *in.RunAtMS
			}
			_, e = c.ExecContext(r.Context(), `INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,priority,retry_base_ms,created_at_ms,available_at_ms) VALUES(?,?,?,?, 'ready',0,?,?,?,?,?)`, id, tenant, in.Queue, string(in.Payload), in.MaxAttempts, in.Priority, in.RetryBaseMS, now, available)
			if e != nil {
				return storage()
			}
			j, e := getJob(r.Context(), c, tenant, id)
			if e != nil {
				return storage()
			}
			jobs = append(jobs, j)
		}
		b, _ := json.Marshal(ids)
		if _, e = c.ExecContext(r.Context(), `INSERT INTO idempotency(tenant,endpoint,key,command,ids) VALUES(?,?,?,?,?)`, tenant, endpoint, key, string(cmd), string(b)); e != nil {
			return storage()
		}
		return nil
	})
	if x != nil {
		sendErr(w, x)
		return
	}
	status := 201
	if replay {
		status = 200
	}
	if batch {
		respond(w, status, map[string]any{"jobs": jobs, "replayed": replay})
	} else {
		respond(w, status, map[string]any{"job": jobs[0], "replayed": replay})
	}
}
func (s *Service) claim(w http.ResponseWriter, r *http.Request, tenant, queue string) {
	if !ident.MatchString(queue) {
		sendErr(w, bad())
		return
	}
	var req struct {
		WorkerID string `json:"worker_id"`
		LeaseMS  int64  `json:"lease_ms"`
	}
	if x := decode(r, &req); x != nil {
		sendErr(w, x)
		return
	}
	if !ident.MatchString(req.WorkerID) || req.LeaseMS < 10 || req.LeaseMS > 300000 {
		sendErr(w, bad())
		return
	}
	now, e := s.Clock()
	if e != nil {
		sendErr(w, storage())
		return
	}
	var job *Job
	var leaseToken string
	deadline := now + req.LeaseMS
	x := s.write(r.Context(), func(c *sql.Conn) *APIError {
		_, e := c.ExecContext(r.Context(), `UPDATE jobs SET state=CASE WHEN attempts>=max_attempts THEN 'dead' ELSE 'ready' END, available_at_ms=lease_until_ms+MIN(60000,retry_base_ms*(1 << (attempts-1))), lease_until_ms=NULL, lease_token=NULL, last_error='lease_expired' WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms<=?`, tenant, queue, now)
		if e != nil {
			return storage()
		}
		var inflight int
		if e = c.QueryRowContext(r.Context(), `SELECT count(*) FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until_ms>?`, tenant, queue, now).Scan(&inflight); e != nil {
			return storage()
		}
		if inflight >= s.MaxInflight {
			return nil
		}
		var id string
		e = c.QueryRowContext(r.Context(), `SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at_ms<=? ORDER BY priority DESC,seq LIMIT 1`, tenant, queue, now).Scan(&id)
		if e == sql.ErrNoRows {
			return nil
		}
		if e != nil {
			return storage()
		}
		leaseToken, e = token()
		if e != nil {
			return storage()
		}
		_, e = c.ExecContext(r.Context(), `UPDATE jobs SET state='leased',attempts=attempts+1,lease_until_ms=?,lease_token=? WHERE tenant=? AND id=?`, deadline, leaseToken, tenant, id)
		if e != nil {
			return storage()
		}
		j, e := getJob(r.Context(), c, tenant, id)
		if e != nil {
			return storage()
		}
		job = &j
		return nil
	})
	if x != nil {
		sendErr(w, x)
		return
	}
	if job == nil {
		respond(w, 200, map[string]any{"job": nil, "lease_token": nil, "lease_until_ms": nil})
		return
	}
	respond(w, 200, map[string]any{"job": job, "lease_token": leaseToken, "lease_until_ms": deadline})
}
func (s *Service) lifecycle(w http.ResponseWriter, r *http.Request, tenant, id, op string) {
	if op == "cancel" {
		var body struct{}
		if x := decode(r, &body); x != nil {
			sendErr(w, x)
			return
		}
		var j Job
		x := s.write(r.Context(), func(c *sql.Conn) *APIError {
			var e error
			j, e = getJob(r.Context(), c, tenant, id)
			if e == sql.ErrNoRows {
				return missing()
			}
			if e != nil {
				return storage()
			}
			if j.State == "completed" || j.State == "dead" {
				return conflict("invalid_transition")
			}
			if j.State != "cancelled" {
				if _, e = c.ExecContext(r.Context(), `UPDATE jobs SET state='cancelled',lease_token=NULL,lease_until_ms=NULL WHERE tenant=? AND id=?`, tenant, id); e != nil {
					return storage()
				}
				j, e = getJob(r.Context(), c, tenant, id)
				if e != nil {
					return storage()
				}
			}
			return nil
		})
		if x != nil {
			sendErr(w, x)
		} else {
			respond(w, 200, map[string]any{"job": j})
		}
		return
	}
	var req struct {
		LeaseToken string
		LeaseMS    int64
		Result     json.RawMessage
		Error      string
	}
	switch op {
	case "heartbeat":
		var body struct {
			LeaseToken string `json:"lease_token"`
			LeaseMS    int64  `json:"lease_ms"`
		}
		if x := decode(r, &body); x != nil {
			sendErr(w, x)
			return
		}
		req.LeaseToken, req.LeaseMS = body.LeaseToken, body.LeaseMS
	case "complete":
		var body struct {
			LeaseToken string          `json:"lease_token"`
			Result     json.RawMessage `json:"result"`
		}
		if x := decode(r, &body); x != nil {
			sendErr(w, x)
			return
		}
		req.LeaseToken, req.Result = body.LeaseToken, body.Result
	case "fail":
		var body struct {
			LeaseToken string `json:"lease_token"`
			Error      string `json:"error"`
		}
		if x := decode(r, &body); x != nil {
			sendErr(w, x)
			return
		}
		req.LeaseToken, req.Error = body.LeaseToken, body.Error
	}
	if req.LeaseToken == "" || len(req.LeaseToken) > 256 {
		sendErr(w, bad())
		return
	}
	var result json.RawMessage
	if op == "heartbeat" {
		if req.LeaseMS < 10 || req.LeaseMS > 300000 || len(req.Result) > 0 || req.Error != "" {
			sendErr(w, bad())
			return
		}
	} else if op == "complete" {
		if len(req.Result) == 0 {
			sendErr(w, bad())
			return
		}
		var e error
		result, e = canonical(req.Result)
		if e != nil {
			sendErr(w, bad())
			return
		}
	} else {
		if req.LeaseMS != 0 || len(req.Result) > 0 || len(req.Error) < 1 || len(req.Error) > 256 {
			sendErr(w, bad())
			return
		}
	}
	now, e := s.Clock()
	if e != nil {
		sendErr(w, storage())
		return
	}
	var job Job
	x := s.write(r.Context(), func(c *sql.Conn) *APIError {
		j, e := getJob(r.Context(), c, tenant, id)
		if e == sql.ErrNoRows {
			return missing()
		}
		if e != nil {
			return storage()
		}
		if op == "complete" && j.State == "completed" {
			var oldToken string
			var oldResult string
			e = c.QueryRowContext(r.Context(), `SELECT completed_token,result FROM jobs WHERE tenant=? AND id=?`, tenant, id).Scan(&oldToken, &oldResult)
			if e != nil {
				return storage()
			}
			if oldToken == req.LeaseToken && oldResult == string(result) {
				job = j
				return nil
			}
			return conflict("lease_conflict")
		}
		if j.State == "completed" {
			var completedToken sql.NullString
			if e := c.QueryRowContext(r.Context(), `SELECT completed_token FROM jobs WHERE tenant=? AND id=?`, tenant, id).Scan(&completedToken); e != nil {
				return storage()
			}
			if completedToken.Valid && completedToken.String == req.LeaseToken {
				return conflict("invalid_transition")
			}
		}
		var liveToken sql.NullString
		e = c.QueryRowContext(r.Context(), `SELECT lease_token FROM jobs WHERE tenant=? AND id=?`, tenant, id).Scan(&liveToken)
		if e != nil {
			return storage()
		}
		if j.State != "leased" || !liveToken.Valid || liveToken.String != req.LeaseToken || j.LeaseUntilMS == nil || now >= *j.LeaseUntilMS {
			return conflict("lease_conflict")
		}
		switch op {
		case "heartbeat":
			_, e = c.ExecContext(r.Context(), `UPDATE jobs SET lease_until_ms=? WHERE tenant=? AND id=?`, now+req.LeaseMS, tenant, id)
		case "complete":
			_, e = c.ExecContext(r.Context(), `UPDATE jobs SET state='completed',result=?,completed_token=?,lease_token=NULL,lease_until_ms=NULL WHERE tenant=? AND id=?`, string(result), req.LeaseToken, tenant, id)
		case "fail":
			state := "ready"
			if j.Attempts >= j.MaxAttempts {
				state = "dead"
			}
			_, e = c.ExecContext(r.Context(), `UPDATE jobs SET state=?,available_at_ms=?,last_error=?,lease_token=NULL,lease_until_ms=NULL WHERE tenant=? AND id=?`, state, now+backoff(j.RetryBaseMS, j.Attempts), req.Error, tenant, id)
		}
		if e != nil {
			return storage()
		}
		job, e = getJob(r.Context(), c, tenant, id)
		if e != nil {
			return storage()
		}
		return nil
	})
	if x != nil {
		sendErr(w, x)
		return
	}
	respond(w, 200, map[string]any{"job": job})
}
func backoff(base int64, attempts int) int64 {
	n := base << (attempts - 1)
	if n > 60000 {
		return 60000
	}
	return n
}

type pageCursor struct {
	Tenant string `json:"t"`
	Queue  string `json:"q"`
	After  int64  `json:"a"`
	Upper  int64  `json:"u"`
}

func (s *Service) list(w http.ResponseWriter, r *http.Request, tenant string) {
	params := r.URL.Query()
	for key := range params {
		if key != "queue" && key != "limit" && key != "cursor" {
			sendErr(w, bad())
			return
		}
		if len(params[key]) != 1 {
			sendErr(w, bad())
			return
		}
	}
	queue := params.Get("queue")
	if queue != "" && !ident.MatchString(queue) {
		sendErr(w, bad())
		return
	}
	limit := 50
	if _, ok := params["limit"]; ok {
		var e error
		limit, e = strconv.Atoi(params.Get("limit"))
		if e != nil || limit < 1 || limit > 100 {
			sendErr(w, bad())
			return
		}
	}
	cur := pageCursor{Tenant: tenant, Queue: queue}
	first := true
	if _, ok := params["cursor"]; ok {
		first = false
		encoded := params.Get("cursor")
		b, e := base64.RawURLEncoding.DecodeString(encoded)
		if e != nil || len(b) > 512 || len(b) == 0 || json.Unmarshal(b, &cur) != nil || cur.Tenant != tenant || cur.Queue != queue || cur.After < 0 || cur.Upper < 0 || cur.After >= cur.Upper {
			sendErr(w, bad())
			return
		}
	}
	ctx := r.Context()
	tx, e := s.DB.BeginTx(ctx, &sql.TxOptions{ReadOnly: true})
	if e != nil {
		sendErr(w, storage())
		return
	}
	defer tx.Rollback()
	if first {
		q := `SELECT COALESCE(max(seq),0) FROM jobs WHERE tenant=?`
		args := []any{tenant}
		if queue != "" {
			q += ` AND queue=?`
			args = append(args, queue)
		}
		if e = tx.QueryRowContext(ctx, q, args...).Scan(&cur.Upper); e != nil {
			sendErr(w, storage())
			return
		}
	}
	query := `SELECT id FROM jobs WHERE tenant=? AND seq>? AND seq<=?`
	args := []any{tenant, cur.After, cur.Upper}
	if queue != "" {
		query += ` AND queue=?`
		args = append(args, queue)
	}
	query += ` ORDER BY seq LIMIT ?`
	args = append(args, limit+1)
	rows, e := tx.QueryContext(ctx, query, args...)
	if e != nil {
		sendErr(w, storage())
		return
	}
	var ids []string
	for rows.Next() {
		var id string
		if e = rows.Scan(&id); e != nil {
			break
		}
		ids = append(ids, id)
	}
	if e == nil {
		e = rows.Err()
	}
	rows.Close()
	if e != nil {
		sendErr(w, storage())
		return
	}
	more := len(ids) > limit
	if more {
		ids = ids[:limit]
	}
	items := make([]Job, 0, len(ids))
	for _, id := range ids {
		j, err := getJob(ctx, tx, tenant, id)
		if err != nil {
			sendErr(w, storage())
			return
		}
		items = append(items, j)
	}
	if e = tx.Commit(); e != nil {
		sendErr(w, storage())
		return
	}
	var next any
	if more {
		cur.After = items[len(items)-1].CreatedSeq
		b, _ := json.Marshal(cur)
		next = base64.RawURLEncoding.EncodeToString(b)
	}
	respond(w, 200, map[string]any{"items": items, "next_cursor": next})
}
func (s *Service) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" && r.Method == "GET" {
		respond(w, 200, map[string]any{"ok": true, "schema_version": 2})
		return
	}
	tenant := r.Header.Get("X-Tenant-ID")
	if !ident.MatchString(tenant) {
		sendErr(w, bad())
		return
	}
	path := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	switch {
	case r.Method == "POST" && r.URL.Path == "/v1/jobs":
		s.submit(w, r, tenant, false)
	case r.Method == "POST" && r.URL.Path == "/v1/jobs/batch":
		s.submit(w, r, tenant, true)
	case r.Method == "GET" && r.URL.Path == "/v1/jobs":
		s.list(w, r, tenant)
	case len(path) == 3 && path[0] == "v1" && path[1] == "jobs" && r.Method == "GET":
		j, e := getJob(r.Context(), s.DB, tenant, path[2])
		if e == sql.ErrNoRows {
			sendErr(w, missing())
		} else if e != nil {
			sendErr(w, storage())
		} else {
			respond(w, 200, map[string]any{"job": j})
		}
	case len(path) == 4 && path[0] == "v1" && path[1] == "jobs" && r.Method == "POST" && (path[3] == "heartbeat" || path[3] == "complete" || path[3] == "fail" || path[3] == "cancel"):
		s.lifecycle(w, r, tenant, path[2], path[3])
	case len(path) == 4 && path[0] == "v1" && path[1] == "queues" && path[3] == "claim" && r.Method == "POST":
		s.claim(w, r, tenant, path[2])
	case r.URL.Path == "/v1/stats" && r.Method == "GET":
		q := r.URL.Query().Get("queue")
		if q != "" && !ident.MatchString(q) {
			sendErr(w, bad())
			return
		}
		query := `SELECT state,count(*) FROM jobs WHERE tenant=?`
		args := []any{tenant}
		if q != "" {
			query += ` AND queue=?`
			args = append(args, q)
		}
		query += ` GROUP BY state`
		rows, e := s.DB.QueryContext(r.Context(), query, args...)
		if e != nil {
			sendErr(w, storage())
			return
		}
		counts := map[string]int{"total": 0, "ready": 0, "leased": 0, "completed": 0, "dead": 0, "cancelled": 0}
		for rows.Next() {
			var state string
			var n int
			if rows.Scan(&state, &n) != nil {
				e = fmt.Errorf("scan")
				break
			}
			counts[state] = n
			counts["total"] += n
		}
		if rows.Err() != nil {
			e = rows.Err()
		}
		rows.Close()
		if e != nil {
			sendErr(w, storage())
		} else {
			respond(w, 200, counts)
		}
	default:
		sendErr(w, missing())
	}
}
