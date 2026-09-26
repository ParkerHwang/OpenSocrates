package queue

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/http/httptest"
	"os"
	"path/filepath"
	_ "queueforge/internal/platform"
	"strings"
	"sync"
	"testing"
)

type testClock struct {
	mu sync.Mutex
	n  int64
}

func (c *testClock) Now() int64  { c.mu.Lock(); defer c.mu.Unlock(); return c.n }
func (c *testClock) set(n int64) { c.mu.Lock(); c.n = n; c.mu.Unlock() }
func setup(t *testing.T) (*Service, *testClock) {
	t.Helper()
	db, e := sql.Open("sqlite", filepath.Join(t.TempDir(), "q.sqlite")+"?_txlock=immediate&_busy_timeout=5000")
	if e != nil {
		t.Fatal(e)
	}
	db.SetMaxOpenConns(1)
	t.Cleanup(func() { db.Close() })
	c := &testClock{n: 100}
	s := &Service{DB: db, Clock: c}
	if e = s.Init(context.Background()); e != nil {
		t.Fatal(e)
	}
	return s, c
}
func TestSubmissionConcurrencyAndIsolation(t *testing.T) {
	s, _ := setup(t)
	in := Input{Queue: "mail", Payload: json.RawMessage(`{"n":1}`)}
	var wg sync.WaitGroup
	ids := make(chan string, 20)
	errs := make(chan error, 20)
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			js, _, e := s.Submit(context.Background(), "tenant", "single", "same", []Input{in})
			if e != nil {
				errs <- e
				return
			}
			ids <- js[0].ID
		}()
	}
	wg.Wait()
	close(ids)
	close(errs)
	for e := range errs {
		t.Fatal(e)
	}
	var first string
	for id := range ids {
		if first != "" && id != first {
			t.Fatalf("duplicate created: %s %s", first, id)
		}
		first = id
	}
	if _, _, e := s.Submit(context.Background(), "tenant", "single", "same", []Input{{Queue: "mail", Payload: json.RawMessage(`{"n":2}`)}}); e != ErrIdempotency {
		t.Fatalf("conflict: %v", e)
	}
	if _, e := s.Get(context.Background(), "other", first); e != sql.ErrNoRows {
		t.Fatalf("tenant leak: %v", e)
	}
}
func TestLeaseLifecycleDeadlineAndAttempts(t *testing.T) {
	s, c := setup(t)
	ctx := context.Background()
	jobs, _, e := s.Submit(ctx, "t", "single", "a", []Input{{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 2, RetryBase: 0, retrySet: true}})
	if e != nil {
		t.Fatal(e)
	}
	j, tok, until, e := s.Claim(ctx, "t", "q", "w", 10)
	if e != nil || j == nil || j.Attempts != 1 {
		t.Fatalf("claim: %#v %v", j, e)
	}
	if _, e = s.Heartbeat(ctx, "t", j.ID, tok, 20); e != nil {
		t.Fatal(e)
	}
	c.set(*until + 10)
	j2, _, _, e := s.Claim(ctx, "t", "q", "w2", 10)
	if e != nil || j2 == nil || j2.Attempts != 2 || *j2.LeaseUntil != c.Now()+10 {
		t.Fatalf("reclaim: %#v %v", j2, e)
	}
	if _, e = s.Heartbeat(ctx, "t", j2.ID, tok, 10); e != ErrLease {
		t.Fatalf("stale token accepted: %v", e)
	}
	c.set(*j2.LeaseUntil)
	j3, _, _, e := s.Claim(ctx, "t", "q", "w3", 10)
	if e != nil || j3 != nil {
		t.Fatalf("max attempts did not die: %#v %v", j3, e)
	}
	got, e := s.Get(ctx, "t", jobs[0].ID)
	if e != nil || got.State != "dead" {
		t.Fatalf("state: %#v %v", got, e)
	}
}
func TestCompleteRepeatAndBatchAtomicValidation(t *testing.T) {
	s, _ := setup(t)
	ctx := context.Background()
	_, _, e := s.Submit(ctx, "t", "batch", "bad", []Input{{Queue: "q", Payload: json.RawMessage(`{}`)}, {Queue: "!", Payload: json.RawMessage(`{}`)}})
	if e == nil {
		t.Fatal("invalid batch accepted")
	}
	st, _ := s.Stats(ctx, "t", "")
	if st["total"] != 0 {
		t.Fatalf("partial batch persisted: %v", st)
	}
	js, _, e := s.Submit(ctx, "t", "single", "ok", []Input{{Queue: "q", Payload: json.RawMessage(`{}`)}})
	if e != nil {
		t.Fatal(e)
	}
	j, tok, _, e := s.Claim(ctx, "t", "q", "w", 100)
	if e != nil || j == nil {
		t.Fatal(e)
	}
	res := json.RawMessage(`{"ok":true}`)
	done, e := s.Complete(ctx, "t", j.ID, tok, res)
	if e != nil || done.State != "completed" {
		t.Fatalf("complete %v %#v", e, done)
	}
	if _, e = s.Complete(ctx, "t", j.ID, tok, res); e != nil {
		t.Fatalf("repeat: %v", e)
	}
	if _, e = s.Complete(ctx, "t", j.ID, tok, json.RawMessage(`{"ok":false}`)); e != ErrLease {
		t.Fatalf("changed repeat: %v", e)
	}
	if _, e = s.Get(ctx, "t", js[0].ID); e != nil {
		t.Fatal(e)
	}
}
func TestHTTPStrictAndHealth(t *testing.T) {
	s, _ := setup(t)
	h := &API{S: s}
	r := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 200 || !strings.Contains(w.Body.String(), `"schema_version":2`) {
		t.Fatal(w.Code, w.Body.String())
	}
	r = httptest.NewRequest("POST", "/v1/jobs", strings.NewReader(`{"queue":"q","payload":{},"surprise":1}`))
	r.Header.Set("X-Tenant-ID", "t")
	r.Header.Set("Idempotency-Key", "x")
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 400 {
		t.Fatalf("unknown field status %d: %s", w.Code, w.Body.String())
	}
	r = httptest.NewRequest("POST", "/v1/jobs", strings.NewReader(`{"queue":"q","payload":{},"max_attempts":0}`))
	r.Header.Set("X-Tenant-ID", "t")
	r.Header.Set("Idempotency-Key", "zero")
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 400 {
		t.Fatalf("explicit zero max_attempts status %d: %s", w.Code, w.Body.String())
	}
}
func TestDatabaseSequenceUnique(t *testing.T) {
	s, _ := setup(t)
	for i := 0; i < 2; i++ {
		_, _, e := s.Submit(context.Background(), "t", "single", fmt.Sprint(i), []Input{{Queue: "q", Payload: json.RawMessage(`{}`)}})
		if e != nil {
			t.Fatal(e)
		}
	}
	var n int
	if e := s.DB.QueryRow(`SELECT count(DISTINCT created_seq) FROM jobs`).Scan(&n); e != nil || n != 2 {
		t.Fatalf("sequence %d %v", n, e)
	}
}

func TestSchedulingPriorityRetryCancelAndList(t *testing.T) {
	s, c := setup(t)
	ctx := context.Background()
	inputs := []Input{
		{Queue: "q", Payload: json.RawMessage(`{"x":1}`), Priority: 9, prioritySet: true, RunAt: 200, runSet: true, RetryBase: 10, retrySet: true},
		{Queue: "q", Payload: json.RawMessage(`{"x":2}`), Priority: 2, prioritySet: true, RetryBase: 10, retrySet: true},
		{Queue: "q", Payload: json.RawMessage(`{"x":3}`), Priority: 2, prioritySet: true, RetryBase: 10, retrySet: true},
	}
	jobs, _, e := s.Submit(ctx, "t", "batch", "scheduled", inputs)
	if e != nil {
		t.Fatal(e)
	}
	first, _, _, e := s.Claim(ctx, "t", "q", "w", 10)
	if e != nil || first.ID != jobs[1].ID {
		t.Fatalf("eligible priority/FIFO claim %#v %v", first, e)
	}
	_, _, _, _ = s.Claim(ctx, "t", "q", "w", 10) // keep second tie leased
	if _, e = s.Cancel(ctx, "t", jobs[2].ID); e != nil {
		t.Fatal(e)
	}
	if _, e = s.Cancel(ctx, "t", jobs[2].ID); e != nil {
		t.Fatal("cancel replay", e)
	}
	// Complete the lease, then release the other tie and check the delayed job boundary.
	if _, e = s.Fail(ctx, "t", first.ID, func() string {
		var v string
		_ = s.DB.QueryRow(`SELECT lease_token FROM jobs WHERE id=?`, first.ID).Scan(&v)
		return v
	}(), "retry"); e != nil {
		t.Fatal(e)
	}
	// The failure is delayed by ten milliseconds from operation time.
	c.set(109)
	got, _, _, e := s.Claim(ctx, "t", "q", "w", 10)
	if e != nil || got != nil {
		t.Fatalf("early retry %#v %v", got, e)
	}
	c.set(110)
	got, _, _, e = s.Claim(ctx, "t", "q", "w", 10)
	if e != nil || got == nil || got.ID != jobs[1].ID {
		t.Fatalf("retry boundary %#v %v", got, e)
	}
	items, next, e := s.List(ctx, "t", "q", 1, "")
	if e != nil || len(items) != 1 || next == "" {
		t.Fatalf("list first %#v %q %v", items, next, e)
	}
	// New inserts are outside the cursor's captured upper sequence.
	_, _, e = s.Submit(ctx, "t", "single", "later", []Input{{Queue: "q", Payload: json.RawMessage(`{}`)}})
	if e != nil {
		t.Fatal(e)
	}
	page, _, e := s.List(ctx, "t", "q", 10, next)
	if e != nil {
		t.Fatal(e)
	}
	for _, j := range page {
		if j.CreatedSeq > jobs[2].CreatedSeq {
			t.Fatal("snapshot included later insert")
		}
	}
	if _, _, e = s.List(ctx, "other", "q", 1, next); e == nil {
		t.Fatal("cross-tenant cursor accepted")
	}
}

func TestExpiredLeaseRetryIsAnchoredToDeadline(t *testing.T) {
	s, c := setup(t)
	ctx := context.Background()
	jobs, _, e := s.Submit(ctx, "t", "single", "expiry-backoff", []Input{{Queue: "q", Payload: json.RawMessage(`{}`), RetryBase: 10, retrySet: true}})
	if e != nil {
		t.Fatal(e)
	}
	first, _, deadline, e := s.Claim(ctx, "t", "q", "w", 10)
	if e != nil || first == nil {
		t.Fatal(first, e)
	}
	c.set(*deadline + 5)
	stats, e := s.Stats(ctx, "t", "")
	if e != nil || stats["leased"] != 1 {
		t.Fatalf("passive stats reconciled expiry: %v %v", stats, e)
	}
	j, _, _, e := s.Claim(ctx, "t", "q", "w2", 10)
	if e != nil || j != nil {
		t.Fatalf("early expired retry %#v %v", j, e)
	}
	stored, e := s.Get(ctx, "t", jobs[0].ID)
	if e != nil || stored.AvailableAt != *deadline+10 {
		t.Fatalf("retry deadline %#v %v", stored, e)
	}
	c.set(*deadline + 9)
	j, _, _, e = s.Claim(ctx, "t", "q", "w3", 10)
	if e != nil || j != nil {
		t.Fatalf("retry eligible early %#v %v", j, e)
	}
	c.set(*deadline + 10)
	j, _, _, e = s.Claim(ctx, "t", "q", "w4", 10)
	if e != nil || j == nil || j.Attempts != 2 {
		t.Fatalf("retry deadline claim %#v %v", j, e)
	}
}

func TestCapacityReplayAndInflight(t *testing.T) {
	s, _ := setup(t)
	s.MaxPending = 1
	s.MaxInflight = 1
	ctx := context.Background()
	in := Input{Queue: "q", Payload: json.RawMessage(`{}`)}
	js, _, e := s.Submit(ctx, "t", "single", "a", []Input{in})
	if e != nil {
		t.Fatal(e)
	}
	if _, replay, e := s.Submit(ctx, "t", "single", "a", []Input{in}); e != nil || !replay {
		t.Fatalf("full capacity replay %v %v", replay, e)
	}
	if _, _, e = s.Submit(ctx, "t", "single", "b", []Input{in}); e != ErrCapacity {
		t.Fatalf("capacity error %v", e)
	}
	if j, _, _, e := s.Claim(ctx, "t", "q", "w", 10); e != nil || j == nil {
		t.Fatal(j, e)
	}
	if j, _, _, e := s.Claim(ctx, "t", "q", "w2", 10); e != nil || j != nil {
		t.Fatal("inflight limit", j, e)
	}
	if _, e = s.Cancel(ctx, "t", js[0].ID); e != nil {
		t.Fatal(e)
	}
	if _, _, e = s.Submit(ctx, "t", "single", "c", []Input{in}); e != nil {
		t.Fatal("terminal did not release pending", e)
	}
}

func TestVersionOneMigrationPreservesLeaseAndReplay(t *testing.T) {
	path := filepath.Join(t.TempDir(), "v1.sqlite")
	db, e := sql.Open("sqlite", path)
	if e != nil {
		t.Fatal(e)
	}
	db.SetMaxOpenConns(1)
	_, e = db.Exec(`PRAGMA journal_mode=WAL; CREATE TABLE jobs(id TEXT UNIQUE NOT NULL,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload BLOB NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_seq INTEGER PRIMARY KEY AUTOINCREMENT,created_at INTEGER NOT NULL,available_at INTEGER NOT NULL,lease_until INTEGER,lease_token TEXT,worker TEXT,last_error TEXT,result BLOB,completed_token TEXT,completed_result BLOB); CREATE INDEX jobs_claim ON jobs(tenant,queue,state,available_at,created_seq); CREATE TABLE idempotency(tenant TEXT,endpoint TEXT,key TEXT,command BLOB,ids BLOB,PRIMARY KEY(tenant,endpoint,key)); PRAGMA user_version=1`)
	if e != nil {
		t.Fatal(e)
	}
	old := Input{Queue: "q", Payload: json.RawMessage(`{"n":1}`), MaxAttempts: 3}
	command, _ := json.Marshal([]Input{old})
	ids, _ := json.Marshal([]string{"legacy-id"})
	_, e = db.Exec(`INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at,available_at,lease_until,lease_token,worker) VALUES('legacy-id','t','q','{"n":1}','leased',1,3,41,10,10,500,'legacy-token','worker'); INSERT INTO idempotency VALUES('t','single','legacy-key',?,?)`, command, ids)
	if e != nil {
		t.Fatal(e)
	}
	_, e = db.Exec(`INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_seq,created_at,available_at,result,completed_token,completed_result) VALUES('legacy-done','t','q','{}','completed',2,3,42,11,11,'{"ok":true}','done-token','{"ok":true}')`)
	if e != nil {
		t.Fatal(e)
	}
	c := &testClock{n: 100}
	s := &Service{DB: db, Clock: c, MaxPending: 100, MaxInflight: 100}
	if e = s.Init(context.Background()); e != nil {
		t.Fatal(e)
	}
	var v int
	if e = db.QueryRow(`PRAGMA user_version`).Scan(&v); e != nil || v != 2 {
		t.Fatalf("version %d %v", v, e)
	}
	got, replay, e := s.Submit(context.Background(), "t", "single", "legacy-key", []Input{old})
	if e != nil || !replay || len(got) != 1 || got[0].ID != "legacy-id" || got[0].Priority != 0 || got[0].RetryBase != 0 {
		t.Fatalf("legacy replay %#v %v %v", got, replay, e)
	}
	if _, e = s.Heartbeat(context.Background(), "t", "legacy-id", "legacy-token", 100); e != nil {
		t.Fatalf("legacy lease lost: %v", e)
	}
	done, e := s.Get(context.Background(), "t", "legacy-done")
	if e != nil || done.State != "completed" || string(done.Result) != `{"ok":true}` {
		t.Fatalf("legacy result changed: %#v %v", done, e)
	}
	if _, e = s.Complete(context.Background(), "t", "legacy-done", "done-token", json.RawMessage(`{"ok":true}`)); e != nil {
		t.Fatalf("legacy completion replay lost: %v", e)
	}
}

func TestReplayRejectsChangedSchedulingCommand(t *testing.T) {
	s, _ := setup(t)
	ctx := context.Background()
	original := Input{
		Queue: "q", Payload: json.RawMessage(`{"n":1}`), MaxAttempts: 3, maxSet: true,
		Priority: 4, prioritySet: true, RunAt: 123, runSet: true, RetryBase: 8, retrySet: true,
	}
	if _, replay, err := s.Submit(ctx, "tenant", "single", "changed-scheduling", []Input{original}); err != nil || replay {
		t.Fatalf("initial submit replay=%v err=%v", replay, err)
	}
	if _, replay, err := s.Submit(ctx, "tenant", "single", "changed-scheduling", []Input{original}); err != nil || !replay {
		t.Fatalf("identical replay replay=%v err=%v", replay, err)
	}
	changed := original
	changed.Priority, changed.RunAt, changed.RetryBase = 0, 0, 1000
	changed.prioritySet, changed.runSet, changed.retrySet = false, false, false
	if _, _, err := s.Submit(ctx, "tenant", "single", "changed-scheduling", []Input{changed}); !errors.Is(err, ErrIdempotency) {
		t.Fatalf("changed scheduling command error=%v, want idempotency conflict", err)
	}
}

func TestConcurrentVersionOneStartup(t *testing.T) {
	path := filepath.Join(t.TempDir(), "shared-v1.sqlite")
	db, e := sql.Open("sqlite", path)
	if e != nil {
		t.Fatal(e)
	}
	_, e = db.Exec(`CREATE TABLE jobs(id TEXT UNIQUE NOT NULL,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload BLOB NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_seq INTEGER PRIMARY KEY AUTOINCREMENT,created_at INTEGER NOT NULL,available_at INTEGER NOT NULL,lease_until INTEGER,lease_token TEXT,worker TEXT,last_error TEXT,result BLOB,completed_token TEXT,completed_result BLOB); CREATE TABLE idempotency(tenant TEXT,endpoint TEXT,key TEXT,command BLOB,ids BLOB,PRIMARY KEY(tenant,endpoint,key)); PRAGMA user_version=1`)
	if e != nil {
		t.Fatal(e)
	}
	_ = db.Close()
	start := make(chan struct{})
	errs := make(chan error, 2)
	var wg sync.WaitGroup
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			d, x := sql.Open("sqlite", path+"?_txlock=immediate&_busy_timeout=5000")
			if x == nil {
				d.SetMaxOpenConns(1)
				<-start
				x = (&Service{DB: d}).Init(context.Background())
				_ = d.Close()
			}
			errs <- x
		}()
	}
	close(start)
	wg.Wait()
	close(errs)
	for x := range errs {
		if x != nil {
			t.Fatal(x)
		}
	}
	db, e = sql.Open("sqlite", path)
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	var v int
	if e = db.QueryRow(`PRAGMA user_version`).Scan(&v); e != nil || v != 2 {
		t.Fatalf("concurrent migration version=%d error=%v", v, e)
	}
	var n int
	if e = db.QueryRow(`SELECT count(*) FROM pragma_table_info('jobs') WHERE name IN ('priority','retry_base_ms')`).Scan(&n); e != nil || n != 2 {
		t.Fatalf("migrated columns=%d error=%v", n, e)
	}
}

func TestUnknownSchemaVersionDoesNotModifyDatabase(t *testing.T) {
	path := filepath.Join(t.TempDir(), "future.sqlite")
	db, e := sql.Open("sqlite", path)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = db.Exec(`CREATE TABLE sentinel(x); PRAGMA user_version=99`); e != nil {
		t.Fatal(e)
	}
	if e = db.Close(); e != nil {
		t.Fatal(e)
	}
	before, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	db, e = sql.Open("sqlite", path)
	if e != nil {
		t.Fatal(e)
	}
	s := &Service{DB: db}
	e = s.Init(context.Background())
	_ = db.Close()
	if e == nil {
		t.Fatal("future version accepted")
	}
	after, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	if string(before) != string(after) {
		t.Fatal("future-version startup changed database bytes")
	}
}

func TestCancelCompleteRaceFencesOneWinner(t *testing.T) {
	s, _ := setup(t)
	ctx := context.Background()
	jobs, _, e := s.Submit(ctx, "t", "single", "race", []Input{{Queue: "q", Payload: json.RawMessage(`{}`)}})
	if e != nil {
		t.Fatal(e)
	}
	j, tok, _, e := s.Claim(ctx, "t", "q", "w", 100)
	if e != nil || j == nil {
		t.Fatal(e)
	}
	start := make(chan struct{})
	errs := make(chan error, 2)
	go func() { <-start; _, x := s.Cancel(ctx, "t", jobs[0].ID); errs <- x }()
	go func() { <-start; _, x := s.Complete(ctx, "t", j.ID, tok, json.RawMessage(`{"ok":true}`)); errs <- x }()
	close(start)
	e1, e2 := <-errs, <-errs
	wins := 0
	if e1 == nil {
		wins++
	}
	if e2 == nil {
		wins++
	}
	if wins != 1 {
		t.Fatalf("expected one terminal transition, errors %v / %v", e1, e2)
	}
	got, e := s.Get(ctx, "t", j.ID)
	if e != nil || (got.State != "cancelled" && got.State != "completed") {
		t.Fatalf("final state %#v %v", got, e)
	}
}
