package main

import (
	"context"
	"crypto/rand"
	"database/sql"
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
	db    *sql.DB
	clock string
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
}

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

func main() {
	addr := flag.String("addr", "127.0.0.1:0", "")
	dbfile := flag.String("db", "", "database file")
	clock := flag.String("clock-file", "", "test clock")
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
	db, err := sql.Open(platform.SQLiteDriver, "file:"+*dbfile+"?_pragma=busy_timeout(10000)&_pragma=journal_mode(WAL)&_pragma=synchronous(FULL)")
	if err != nil {
		log.Fatal(err)
	}
	db.SetMaxOpenConns(1)
	schema := `CREATE TABLE IF NOT EXISTS jobs(created_seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL, tenant TEXT NOT NULL, queue TEXT NOT NULL, payload BLOB NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL, created_at INTEGER NOT NULL, available_at INTEGER NOT NULL, lease_until INTEGER, lease_token TEXT, last_error TEXT, result BLOB, completed_token TEXT, completed_result BLOB); CREATE INDEX IF NOT EXISTS jobs_tenant_queue_state ON jobs(tenant,queue,state,created_seq); CREATE TABLE IF NOT EXISTS idem(tenant TEXT, endpoint TEXT, ikey TEXT, command BLOB, ids BLOB, PRIMARY KEY(tenant,endpoint,ikey)); PRAGMA user_version=1;`
	if _, err = db.Exec(schema); err != nil {
		log.Fatal(err)
	}
	a := &app{db, *clock}
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
		write(w, 200, map[string]any{"ok": true, "schema_version": 1})
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
			}
		}
	}
	if len(p) == 2 && p[0] == "v1" && p[1] == "stats" && r.Method == "GET" {
		a.stats(w, r, tenant)
		return
	}
	fail(w, 404, "not_found", "route not found")
}

type input struct {
	Queue   string          `json:"queue"`
	Payload json.RawMessage `json:"payload"`
	Max     int             `json:"max_attempts"`
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
		var obj map[string]json.RawMessage
		if !ident.MatchString(in[i].Queue) || in[i].Max < 1 || in[i].Max > 10 || len(in[i].Payload) > 16384 || json.Unmarshal(in[i].Payload, &obj) != nil || obj == nil {
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
	var old, idsRaw []byte
	e = tx.QueryRow("SELECT command,ids FROM idem WHERE tenant=? AND endpoint=? AND ikey=?", t, endpoint, key).Scan(&old, &idsRaw)
	if e == nil {
		if string(old) != string(cmd) {
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
	for _, v := range in {
		id := token()
		now := a.now()
		_, e = tx.Exec("INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at,available_at) VALUES(?,?,?,?,'ready',0,?,?,?)", id, t, v.Queue, []byte(v.Payload), v.Max, now, now)
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
	tx2, _ := a.db.Begin()
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
func scanJob(row interface{ Scan(...any) error }) (job, error) {
	var j job
	var payload, result []byte
	var until sql.NullInt64
	var le sql.NullString
	e := row.Scan(&j.CreatedSeq, &j.ID, &j.Tenant, &j.Queue, &payload, &j.State, &j.Attempts, &j.MaxAttempts, &j.CreatedAt, &j.AvailableAt, &until, &le, &result)
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

const cols = "created_seq,id,tenant,queue,payload,state,attempts,max_attempts,created_at,available_at,lease_until,last_error,result"

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
	rows, e := tx.Query("SELECT id,attempts,max_attempts FROM jobs WHERE tenant=? AND queue=? AND state='leased' AND lease_until<=?", t, q, now)
	if e != nil {
		fail(w, 503, "storage", "temporary storage failure")
		return
	}
	type expired struct {
		id            string
		attempts, max int
	}
	xs := []expired{}
	for rows.Next() {
		var z expired
		_ = rows.Scan(&z.id, &z.attempts, &z.max)
		xs = append(xs, z)
	}
	rows.Close()
	for _, z := range xs {
		if z.attempts >= z.max {
			_, _ = tx.Exec("UPDATE jobs SET state='dead',lease_until=NULL,lease_token=NULL,last_error='lease_expired' WHERE id=?", z.id)
		} else {
			_, _ = tx.Exec("UPDATE jobs SET state='ready',available_at=?,lease_until=NULL,lease_token=NULL,last_error='lease_expired' WHERE id=?", now, z.id)
		}
	}
	var id string
	e = tx.QueryRow("SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND available_at<=? ORDER BY created_seq LIMIT 1", t, q, now).Scan(&id)
	if e == sql.ErrNoRows {
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
		_, e = tx.Exec("UPDATE jobs SET state=?,lease_token=NULL,lease_until=NULL,available_at=?,last_error=? WHERE id=?", state, now, x.Error, id)
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
	counts := map[string]int{"ready": 0, "leased": 0, "completed": 0, "dead": 0}
	total := 0
	for rows.Next() {
		var s string
		var n int
		_ = rows.Scan(&s, &n)
		counts[s] = n
		total += n
	}
	write(w, 200, map[string]int{"total": total, "ready": counts["ready"], "leased": counts["leased"], "completed": counts["completed"], "dead": counts["dead"], "cancelled": 0})
}
