package queue

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http/httptest"
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
	db, e := sql.Open("sqlite", filepath.Join(t.TempDir(), "q.sqlite"))
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
	jobs, _, e := s.Submit(ctx, "t", "single", "a", []Input{{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 2}})
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
	if w.Code != 200 || !strings.Contains(w.Body.String(), `"schema_version":1`) {
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
