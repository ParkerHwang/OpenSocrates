package main

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"

	"queueforge/internal/platform"
)

type app struct {
	db                      *sql.DB
	clock                   string
	maxPending, maxInflight int
}
type job struct {
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

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

func initialize(db *sql.DB) error {
	var initial int
	if err := db.QueryRow("PRAGMA user_version").Scan(&initial); err != nil {
		return err
	}
	if initial > 2 {
		return errors.New("future schema")
	}
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	var v int
	if initial > 0 {
		if err = lockTx(tx); err != nil {
			return err
		}
	}
	if err = tx.QueryRow("PRAGMA user_version").Scan(&v); err != nil {
		return err
	}
	if v > 2 {
		return errors.New("future schema")
	}
	if v == 0 {
		_, err = tx.Exec(`CREATE TABLE jobs(created_seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload BLOB NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_at INTEGER NOT NULL,available_at INTEGER NOT NULL,lease_until INTEGER,lease_token TEXT,last_error TEXT,result BLOB,completed_token TEXT,completed_result BLOB,priority INTEGER NOT NULL DEFAULT 0,retry_base_ms INTEGER NOT NULL DEFAULT 1000);
CREATE TABLE idem(tenant TEXT,endpoint TEXT,ikey TEXT,command BLOB,ids BLOB,PRIMARY KEY(tenant,endpoint,ikey));`)
	} else if v == 1 {
		_, err = tx.Exec("ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
		if err == nil {
			_, err = tx.Exec("ALTER TABLE jobs ADD COLUMN retry_base_ms INTEGER NOT NULL DEFAULT 0")
		}
	}
	if err != nil {
		return err
	}
	if _, err = tx.Exec("DROP INDEX IF EXISTS jobs_tenant_queue_state"); err != nil {
		return err
	}
	if _, err = tx.Exec("CREATE INDEX jobs_tenant_queue_state ON jobs(tenant,queue,state,priority DESC,created_seq)"); err != nil {
		return err
	}
	if _, err = tx.Exec("CREATE INDEX IF NOT EXISTS jobs_tenant_pending ON jobs(tenant,state)"); err != nil {
		return err
	}
	if _, err = tx.Exec("PRAGMA user_version=2"); err != nil {
		return err
	}
	return tx.Commit()
}
func retryDelay(base int64, attempts int) int64 {
	if base <= 0 {
		return 0
	}
	n := base
	for i := 1; i < attempts && n < 60000; i++ {
		if n > 30000 {
			n = 60000
		} else {
			n *= 2
		}
	}
	if n > 60000 {
		n = 60000
	}
	return n
}
func max64(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}
func lockTx(tx *sql.Tx) error { _, err := tx.Exec("UPDATE jobs SET state=state WHERE 0"); return err }

func main() {
	addr := flag.String("addr", "127.0.0.1:0", "")
	dbfile := flag.String("db", "", "database file")
	clock := flag.String("clock-file", "", "test clock")
	mp := flag.Int("max-pending", 100000, "tenant pending capacity")
	mi := flag.Int("max-inflight", 100000, "tenant queue inflight capacity")
	flag.Parse()
	if *dbfile == "" {
		log.Fatal("--db required")
	}
	if !strings.HasPrefix(*addr, "127.0.0.1:") {
		log.Fatal("address must use 127.0.0.1")
	}
	if err := os.MkdirAll(filepath.Dir(*dbfile), 0700); err != nil {
		log.Fatal(err)
	}
	if *mp <= 0 || *mi <= 0 {
		log.Fatal("capacity limits must be positive")
	}
	db, err := sql.Open(platform.SQLiteDriver, "file:"+*dbfile+"?_pragma=busy_timeout(10000)")
	if err != nil {
		log.Fatal(err)
	}
	db.SetMaxOpenConns(1)
	var version int
	if err = db.QueryRow("PRAGMA user_version").Scan(&version); err != nil {
		log.Fatal(err)
	}
	if version > 2 {
		log.Fatal("unsupported database schema version")
	}
	if _, err = db.Exec("PRAGMA journal_mode=WAL"); err != nil {
		log.Fatal(err)
	}
	if _, err = db.Exec("PRAGMA synchronous=FULL"); err != nil {
		log.Fatal(err)
	}
	if err = initialize(db); err != nil {
		log.Fatal("database initialization failed")
	}
	a := &app{db: db, clock: *clock, maxPending: *mp, maxInflight: *mi}
	ln, err := net.Listen("tcp", *addr)
	if err != nil {
		log.Fatal(err)
	}
	s := &http.Server{Handler: a, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if err := s.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatal(err)
		}
	}()
	fmt.Printf("{\"port\":%d}\n", ln.Addr().(*net.TCPAddr).Port)
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGTERM, os.Interrupt)
	<-ch
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	_ = s.Shutdown(ctx)
	_ = db.Close()
}
func (a *app) now() int64 {
	if a.clock != "" {
		if b, e := os.ReadFile(a.clock); e == nil {
			if n, e := strconv.ParseInt(strings.TrimSpace(string(b)), 10, 64); e == nil {
				return n
			}
		}
	}
	return time.Now().UnixMilli()
}
func write(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
func fail(w http.ResponseWriter, code int, c, m string) {
	write(w, code, map[string]any{"error": map[string]string{"code": c, "message": m}})
}
func decode(r *http.Request, v any) error {
	r.Body = http.MaxBytesReader(nil, r.Body, 1<<20)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return e
	}
	var x any
	if err := d.Decode(&x); err != io.EOF {
		return errors.New("extra data")
	}
	return nil
}
func (a *app) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" && r.Method == "GET" {
		write(w, 200, map[string]any{"ok": true, "schema_version": 2})
		return
	}
	tenant := r.Header.Get("X-Tenant-ID")
	if !ident.MatchString(tenant) {
		fail(w, 400, "validation", "valid X-Tenant-ID required")
		return
	}
	p := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if len(p) == 2 && p[0] == "v1" && p[1] == "jobs" && r.Method == "POST" {
		a.submit(w, r, tenant, false)
		return
	}
	if len(p) == 3 && p[0] == "v1" && p[1] == "jobs" && p[2] == "batch" && r.Method == "POST" {
		a.submit(w, r, tenant, true)
		return
	}
	if len(p) == 4 && p[0] == "v1" && p[1] == "queues" && p[2] != "" && p[3] == "claim" && r.Method == "POST" {
		if !ident.MatchString(p[2]) {
			fail(w, 400, "validation", "invalid queue")
			return
		}
		a.claim(w, r, tenant, p[2])
		return
	}
	if len(p) >= 3 && p[0] == "v1" && p[1] == "jobs" {
		id := p[2]
		if len(p) == 3 && r.Method == "GET" {
			a.get(w, tenant, id)
			return
		}
		if len(p) == 4 && r.Method == "POST" {
			switch p[3] {
			case "heartbeat":
				a.leaseOp(w, r, tenant, id, "heartbeat")
				return
			case "complete":
				a.leaseOp(w, r, tenant, id, "complete")
				return
			case "fail":
				a.leaseOp(w, r, tenant, id, "fail")
				return
			case "cancel":
				a.cancel(w, r, tenant, id)
				return
			}
		}
	}
	if len(p) == 2 && p[0] == "v1" && p[1] == "jobs" && r.Method == "GET" {
		a.list(w, r, tenant)
		return
	}
	if len(p) == 2 && p[0] == "v1" && p[1] == "stats" && r.Method == "GET" {
		a.stats(w, r, tenant)
		return
	}
	fail(w, 404, "not_found", "route not found")
}

type input struct {
	Queue     string          `json:"queue"`
	Payload   json.RawMessage `json:"payload"`
	Max       int             `json:"max_attempts"`
	Priority  int             `json:"priority"`
	RunAt     *int64          `json:"run_at_ms"`
	RetryBase *int64          `json:"retry_base_ms"`
}

func (a *app) submit(w http.ResponseWriter, r *http.Request, t string, batch bool) {
	key := r.Header.Get("Idempotency-Key")
	if len(key) == 0 || len(key) > 128 || !isASCII(key) {
		fail(w, 400, "validation", "invalid idempotency key")
		return
	}
	var in []input
	if batch {
		var x struct {
			Jobs []input `json:"jobs"`
		}
		if decode(r, &x) != nil || len(x.Jobs) < 1 || len(x.Jobs) > 100 {
			fail(w, 400, "validation", "invalid batch")
			return
		}
		in = x.Jobs
	} else {
		var x input
		if decode(r, &x) != nil {
			fail(w, 400, "validation", "invalid job")
			return
		}
		in = []input{x}
	}
	for i := range in {
		if in[i].Max == 0 {
			in[i].Max = 3
		}
		if in[i].RunAt == nil {
			z := int64(0)
			in[i].RunAt = &z
		}
		if in[i].RetryBase == nil {
			z := int64(1000)
			in[i].RetryBase = &z
		}
		var obj map[string]json.RawMessage
		if !ident.MatchString(in[i].Queue) || in[i].Max < 1 || in[i].Max > 10 || in[i].Priority < -10 || in[i].Priority > 10 || *in[i].RunAt < 0 || *in[i].RetryBase < 0 || *in[i].RetryBase > 60000 || len(in[i].Payload) > 16384 || json.Unmarshal(in[i].Payload, &obj) != nil || obj == nil {
			fail(w, 400, "validation", "invalid job input")
			return
		}
		in[i].Payload = compact(in[i].Payload)
	}
	endpoint := "single"
	if batch {
		endpoint = "batch"
	}
	cmd, _ := json.Marshal(in)
	tx, e := a.db.Begin()
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	defer tx.Rollback()
	if e = lockTx(tx); e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	var old, idsRaw []byte
	e = tx.QueryRow("SELECT command,ids FROM idem WHERE tenant=? AND endpoint=? AND ikey=?", t, endpoint, key).Scan(&old, &idsRaw)
	if e == nil {
		if string(old) != string(cmd) && !legacyCommandMatches(old, cmd) {
			fail(w, 409, "idempotency_conflict", "idempotency key conflicts")
			return
		}
		var ids []string
		_ = json.Unmarshal(idsRaw, &ids)
		jobs := a.jobsByIDs(tx, t, ids)
		write(w, 200, map[string]any{"jobs": jobs, "job": single(jobs), "replayed": true})
		return
	} else if e != sql.ErrNoRows {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	ids := make([]string, 0, len(in))
	var pending int
	if e = tx.QueryRow("SELECT count(*) FROM jobs WHERE tenant=? AND state IN ('ready','leased')", t).Scan(&pending); e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	if pending+len(in) > a.maxPending {
		fail(w, 429, "capacity", "tenant pending capacity reached")
		return
	}
	for _, v := range in {
		id := token()
		now := a.now()
		_, e = tx.Exec("INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at,available_at,priority,retry_base_ms) VALUES(?,?,?,?,'ready',0,?,?,?,?,?)", id, t, v.Queue, []byte(v.Payload), v.Max, now, max64(now, *v.RunAt), v.Priority, *v.RetryBase)
		if e != nil {
			fail(w, 503, "storage", "temporary storage failure")
			return
		}
		ids = append(ids, id)
	}
	idsRaw, _ = json.Marshal(ids)
	if _, e = tx.Exec("INSERT INTO idem VALUES(?,?,?,?,?)", t, endpoint, key, cmd, idsRaw); e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	if e = tx.Commit(); e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	tx2, e := a.db.Begin()
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	jobs := a.jobsByIDs(tx2, t, ids)
	_ = tx2.Commit()
	code := 201
	if batch {
		write(w, code, map[string]any{"jobs": jobs, "replayed": false})
	} else {
		write(w, code, map[string]any{"job": single(jobs), "replayed": false})
	}
}
func isASCII(s string) bool {
	for _, c := range s {
		if c > 127 {
			return false
		}
	}
	return true
}
func compact(b []byte) json.RawMessage {
	var x any
	if json.Unmarshal(b, &x) != nil {
		return b
	}
	o, _ := json.Marshal(x)
	return o
}
func token() string {
	b := make([]byte, 24)
	if _, err := rand.Read(b); err != nil {
		panic("secure random source unavailable")
	}
	return hex.EncodeToString(b)
}
func single(j []job) any {
	if len(j) == 0 {
		return nil
	}
	return j[0]
}
func legacyCommandMatches(old, current []byte) bool {
	var a, b []input
	if json.Unmarshal(old, &a) != nil || json.Unmarshal(current, &b) != nil || len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i].Queue != b[i].Queue || string(compact(a[i].Payload)) != string(compact(b[i].Payload)) || (a[i].Max != 0 && a[i].Max != b[i].Max) || a[i].Priority != b[i].Priority {
			return false
		}
		if a[i].RunAt != nil && *a[i].RunAt != *b[i].RunAt {
			return false
		}
		if a[i].RunAt == nil && *b[i].RunAt != 0 {
			return false
		}
		if a[i].RetryBase != nil && *a[i].RetryBase != *b[i].RetryBase {
			return false
		}
		if a[i].RetryBase == nil && *b[i].RetryBase != 1000 {
			return false
		}
	}
	return true
}
func scanJob(row interface{ Scan(...any) error }) (job, error) {
	var j job
	var payload, result []byte
	var until sql.NullInt64
	var le sql.NullString
	e := row.Scan(&j.CreatedSeq, &j.ID, &j.Tenant, &j.Queue, &payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedAt, &j.AvailableAt, &until, &le, &result, &j.Priority, &j.RetryBase)
	j.Payload = payload
	if until.Valid {
		j.LeaseUntil = &until.Int64
	}
	if le.Valid {
		j.LastError = &le.String
	}
	if result != nil {
		j.Result = result
	}
	return j, e
}

const cols = "created_seq,id,tenant,queue,payload,state,attempts,max_attempts,created_at,available_at,lease_until,last_error,result,priority,retry_base_ms"

func (a *app) jobsByIDs(tx *sql.Tx, t string, ids []string) []job {
	out := []job{}
	for _, id := range ids {
		j, e := scanJob(tx.QueryRow("SELECT "+cols+" FROM jobs WHERE tenant=? AND id=?", t, id))
		if e == nil {
			out = append(out, j)
		}
	}
	return out
}
func (a *app) get(w http.ResponseWriter, t, id string) {
	j, e := scanJob(a.db.QueryRow("SELECT "+cols+" FROM jobs WHERE tenant=? AND id=?", t, id))
	if e != nil {
		fail(w, 404, "not_found", "job not found")
		return
	}
	write(w, 200, map[string]any{"job": j})
}
func (a *app) claim(w http.ResponseWriter, r *http.Request, t, q string) {
	var x struct {
		Worker string `json:"worker_id"`
		Lease  int64  `json:"lease_ms"`
	}
	if decode(r, &x) != nil || !ident.MatchString(x.Worker) || x.Lease < 10 || x.Lease > 300000 {
		fail(w, 400, "validation", "invalid claim")
		return
	}
	now := a.now()
	tx, e := a.db.Begin()
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	defer tx.Rollback()
	if e = lockTx(tx); e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	rows, e := tx.Query("SELECT id,attempts,max_attempts,lease_until,retry_base_ms FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until<=?", t, q, now)
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	type expired struct {
		id             string
		attempts, max  int
		deadline, base int64
	}
	xs := []expired{}
	for rows.Next() {
		var z expired
		_ = rows.Scan(&z.id, &z.attempts, &z.max, &z.deadline, &z.base)
		xs = append(xs, z)
	}
	rows.Close()
	for _, z := range xs {
		if z.attempts >= z.max {
			_, _ = tx.Exec("UPDATE jobs SET state='dead',lease_until=NULL,lease_token=NULL,last_error='lease_expired' WHERE id=?", z.id)
		} else {
			_, _ = tx.Exec("UPDATE jobs SET state='ready',available_at=?,lease_until=NULL,lease_token=NULL,last_error='lease_expired' WHERE id=?", z.deadline+retryDelay(z.base, z.attempts), z.id)
		}
	}
	var id string
	e = tx.QueryRow("SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at<=? ORDER BY priority DESC,created_seq LIMIT 1", t, q, now).Scan(&id)
	var inflight int
	if e == nil {
		_ = tx.QueryRow("SELECT count(*) FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until>?", t, q, now).Scan(&inflight)
	}
	if e == sql.ErrNoRows || (e == nil && inflight >= a.maxInflight) {
		_ = tx.Commit()
		write(w, 200, map[string]any{"job": nil, "lease_token": nil, "lease_until_ms": nil})
		return
	}
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	tok := token()
	until := now + x.Lease
	_, e = tx.Exec("UPDATE jobs SET state='leased',attempts=attempts+1,lease_token=?,lease_until=? WHERE id=? AND state='ready'", tok, until, id)
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	if tx.Commit() != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	j, _ := scanJob(a.db.QueryRow("SELECT "+cols+" FROM jobs WHERE tenant=? AND id=?", t, id))
	write(w, 200, map[string]any{"job": j, "lease_token": tok, "lease_until_ms": until})
}
func (a *app) leaseOp(w http.ResponseWriter, r *http.Request, t, id, op string) {
	var x struct {
		Token  string          `json:"lease_token"`
		Lease  int64           `json:"lease_ms"`
		Result json.RawMessage `json:"result"`
		Error  string          `json:"error"`
	}
	if decode(r, &x) != nil || x.Token == "" {
		fail(w, 400, "validation", "invalid lease request")
		return
	}
	if op == "heartbeat" && (x.Lease < 10 || x.Lease > 300000) || op == "complete" && (len(x.Result) > 16384 || !isObject(x.Result)) || op == "fail" && (len(x.Error) < 1 || len(x.Error) > 256) {
		fail(w, 400, "validation", "invalid lease request")
		return
	}
	tx, e := a.db.Begin()
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	defer tx.Rollback()
	if e = lockTx(tx); e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	var state, live string
	var until sql.NullInt64
	var attempts, max int
	e = tx.QueryRow("SELECT state,COALESCE(lease_token,''),lease_until,attempts,max_attempts FROM jobs WHERE tenant=? AND id=?", t, id).Scan(&state, &live, &until, &attempts, &max)
	if e != nil {
		fail(w, 404, "not_found", "job not found")
		return
	}
	now := a.now()
	if op == "complete" && state == "completed" {
		var ct string
		var cr []byte
		_ = tx.QueryRow("SELECT COALESCE(completed_token,''),completed_result FROM jobs WHERE id=?", id).Scan(&ct, &cr)
		want := compact(x.Result)
		if ct == x.Token && string(cr) == string(want) {
			j, _ := scanJob(tx.QueryRow("SELECT "+cols+" FROM jobs WHERE id=?", id))
			write(w, 200, map[string]any{"job": j})
			return
		}
	}
	if state != "leased" || live != x.Token || !until.Valid || now >= until.Int64 {
		fail(w, 409, "lease_conflict", "lease is no longer current")
		return
	}
	switch op {
	case "heartbeat":
		_, e = tx.Exec("UPDATE jobs SET lease_until=? WHERE id=?", now+x.Lease, id)
	case "complete":
		res := compact(x.Result)
		_, e = tx.Exec("UPDATE jobs SET state='completed',lease_token=NULL,lease_until=NULL,result=?,completed_token=?,completed_result=? WHERE id=?", res, x.Token, res, id)
	case "fail":
		state = "ready"
		if attempts >= max {
			state = "dead"
		}
		var base int64
		_ = tx.QueryRow("SELECT retry_base_ms FROM jobs WHERE id=?", id).Scan(&base)
		_, e = tx.Exec("UPDATE jobs SET state=?,lease_token=NULL,lease_until=NULL,available_at=?,last_error=? WHERE id=?", state, now+retryDelay(base, attempts), x.Error, id)
	}
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	if tx.Commit() != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	j, _ := scanJob(a.db.QueryRow("SELECT "+cols+" FROM jobs WHERE tenant=? AND id=?", t, id))
	write(w, 200, map[string]any{"job": j})
}
func isObject(b []byte) bool {
	var x map[string]json.RawMessage
	return json.Unmarshal(b, &x) == nil && x != nil
}
func (a *app) stats(w http.ResponseWriter, r *http.Request, t string) {
	q := r.URL.Query().Get("queue")
	query := "SELECT state,count(*) FROM jobs WHERE tenant=?"
	args := []any{t}
	if q != "" {
		query += " AND queue=?"
		args = append(args, q)
	}
	query += " GROUP BY state"
	rows, e := a.db.Query(query, args...)
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	defer rows.Close()
	counts := map[string]int{"ready": 0, "leased": 0, "completed": 0, "dead": 0, "cancelled": 0}
	total := 0
	for rows.Next() {
		var s string
		var n int
		_ = rows.Scan(&s, &n)
		counts[s] = n
		total += n
	}
	write(w, 200, map[string]int{"total": total, "ready": counts["ready"], "leased": counts["leased"], "completed": counts["completed"], "dead": counts["dead"], "cancelled": counts["cancelled"]})
}

func (a *app) cancel(w http.ResponseWriter, r *http.Request, t, id string) {
	var x map[string]json.RawMessage
	if decode(r, &x) != nil || x == nil || len(x) != 0 {
		fail(w, 400, "validation", "expected empty object")
		return
	}
	tx, e := a.db.Begin()
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	defer tx.Rollback()
	if e = lockTx(tx); e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	var state string
	e = tx.QueryRow("SELECT state FROM jobs WHERE tenant=? AND id=?", t, id).Scan(&state)
	if e != nil {
		fail(w, 404, "not_found", "job not found")
		return
	}
	if state == "completed" || state == "dead" {
		fail(w, 409, "invalid_transition", "job cannot be cancelled")
		return
	}
	if state != "cancelled" {
		if _, e = tx.Exec("UPDATE jobs SET state='cancelled',lease_token=NULL,lease_until=NULL WHERE tenant=? AND id=?", t, id); e != nil {
			fail(w, 503, "storage", "temporary storage failure")
			return
		}
	}
	if tx.Commit() != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	j, _ := scanJob(a.db.QueryRow("SELECT "+cols+" FROM jobs WHERE tenant=? AND id=?", t, id))
	write(w, 200, map[string]any{"job": j})
}

type pageCursor struct {
	Tenant string `json:"t"`
	Queue  string `json:"q"`
	Upper  int64  `json:"u"`
	After  int64  `json:"a"`
}

func cursorEncode(c pageCursor) string {
	b, _ := json.Marshal(c)
	mac := hmac.New(sha256.New, []byte("queueforge-cursor-v2"))
	mac.Write(b)
	return base64.RawURLEncoding.EncodeToString(append(b, mac.Sum(nil)...))
}
func cursorDecode(s string) (pageCursor, bool) {
	var c pageCursor
	b, e := base64.RawURLEncoding.DecodeString(s)
	if e != nil || len(b) < 33 {
		return c, false
	}
	raw, sig := b[:len(b)-32], b[len(b)-32:]
	mac := hmac.New(sha256.New, []byte("queueforge-cursor-v2"))
	mac.Write(raw)
	if !hmac.Equal(sig, mac.Sum(nil)) || json.Unmarshal(raw, &c) != nil || c.Upper < 0 || c.After < 0 || c.After > c.Upper {
		return c, false
	}
	return c, true
}
func (a *app) list(w http.ResponseWriter, r *http.Request, t string) {
	q := r.URL.Query().Get("queue")
	if q != "" && !ident.MatchString(q) {
		fail(w, 400, "validation", "invalid queue")
		return
	}
	limit := 50
	if v := r.URL.Query().Get("limit"); v != "" {
		n, e := strconv.Atoi(v)
		if e != nil || n < 1 || n > 100 {
			fail(w, 400, "validation", "invalid limit")
			return
		}
		limit = n
	}
	c := pageCursor{Tenant: t, Queue: q}
	cur := r.URL.Query().Get("cursor")
	if r.URL.Query().Has("cursor") && cur == "" {
		fail(w, 400, "validation", "invalid cursor")
		return
	}
	if cur != "" {
		var ok bool
		c, ok = cursorDecode(cur)
		if !ok || c.Tenant != t || c.Queue != q {
			fail(w, 400, "validation", "invalid cursor")
			return
		}
	} else {
		if e := a.db.QueryRow("SELECT COALESCE(MAX(created_seq),0) FROM jobs WHERE tenant=?", t).Scan(&c.Upper); e != nil {
			fail(w, 503, "storage", "temporary storage failure")
			return
		}
	}
	query := "SELECT " + cols + " FROM jobs WHERE tenant=? AND created_seq>? AND created_seq<=?"
	args := []any{t, c.After, c.Upper}
	if q != "" {
		query += " AND queue=?"
		args = append(args, q)
	}
	query += " ORDER BY created_seq LIMIT ?"
	args = append(args, limit+1)
	rows, e := a.db.Query(query, args...)
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	defer rows.Close()
	items := []job{}
	for rows.Next() {
		j, e := scanJob(rows)
		if e != nil {
			fail(w, 503, "storage", "temporary storage failure")
			return
		}
		items = append(items, j)
	}
	if rows.Err() != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	var next any = nil
	if len(items) > limit {
		items = items[:limit]
		c.After = items[len(items)-1].CreatedSeq
		next = cursorEncode(c)
	}
	write(w, 200, map[string]any{"items": items, "next_cursor": next})
}
