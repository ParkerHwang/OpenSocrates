package queue

import (
	"fmt"
	"net/http"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
)

func TestSchedulingCancellationAndPages(t *testing.T) {
	var now atomic.Int64
	now.Store(1000)
	s := setup(t, &now, filepath.Join(t.TempDir(), "q.sqlite"))
	h := Handler{s}
	put := func(key, body string) string {
		t.Helper()
		c, r := call(t, h, "t", "POST", "/v1/jobs", key, body)
		if c != 201 {
			t.Fatalf("put %d %+v", c, r)
		}
		return r.Job.ID
	}
	low := put("low", `{"queue":"q","payload":{},"priority":-1}`)
	future := put("future", `{"queue":"q","payload":{},"priority":10,"run_at_ms":2000}`)
	high := put("high", `{"queue":"q","payload":{},"priority":3,"retry_base_ms":100}`)
	tie := put("tie", `{"queue":"q","payload":{},"priority":3}`)
	claim := func() response {
		t.Helper()
		c, r := call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
		if c != 200 {
			t.Fatal(c)
		}
		return r
	}
	r := claim()
	if r.Job.ID != high {
		t.Fatal(r.Job.ID)
	}
	c, _ := call(t, h, "t", "POST", "/v1/jobs/"+high+"/fail", "", fmt.Sprintf(`{"lease_token":%q,"error":"retry"}`, *r.LeaseToken))
	if c != 200 {
		t.Fatal(c)
	}
	r = claim()
	if r.Job.ID != tie {
		t.Fatal("tie", r.Job.ID)
	}
	c, _ = call(t, h, "t", "POST", "/v1/jobs/"+tie+"/cancel", "", `{}`)
	if c != 200 {
		t.Fatal(c)
	}
	c, _ = call(t, h, "t", "POST", "/v1/jobs/"+tie+"/heartbeat", "", fmt.Sprintf(`{"lease_token":%q,"lease_ms":100}`, *r.LeaseToken))
	if c != 409 {
		t.Fatal(c)
	}
	now.Store(1099)
	r = claim()
	if r.Job.ID != low {
		t.Fatal("low", r.Job.ID)
	}
	now.Store(1100)
	r = claim()
	if r.Job.ID != high {
		t.Fatal("retry boundary", r.Job.ID)
	}
	c, _ = call(t, h, "t", "POST", "/v1/jobs/"+high+"/cancel", "", `{}`)
	if c != 200 {
		t.Fatal(c)
	}
	c, _ = call(t, h, "t", "POST", "/v1/jobs/"+high+"/cancel", "", `{}`)
	if c != 200 {
		t.Fatal(c)
	}
	c, _ = call(t, h, "t", "GET", "/v1/jobs?queue=q&limit=2", "", "")
	if c != 200 {
		t.Fatal(c)
	}
	items, next, e := s.List(t.Context(), "t", "q", 2, "")
	if e != nil || len(items) != 2 || next == nil {
		t.Fatal(items, next, e)
	}
	put("inserted", `{"queue":"q","payload":{}}`)
	other, next2, e := s.List(t.Context(), "t", "q", 2, *next)
	if e != nil || len(other) != 2 || next2 != nil || other[0].ID != high || other[1].ID != tie {
		t.Fatal(other, next2, e)
	}
	if _, _, e = s.List(t.Context(), "foreign", "q", 2, *next); e == nil {
		t.Fatal("foreign cursor")
	}
	if c, _ = call(t, h, "t", "GET", "/v1/jobs?cursor=e30", "", ""); c != 400 {
		t.Fatal(c)
	}
	if c, _ = call(t, h, "t", "POST", "/v1/jobs", "null", `{"queue":"q","payload":{},"retry_base_ms":null}`); c != 400 {
		t.Fatal(c)
	}
	now.Store(2000)
	r = claim()
	if r.Job.ID != future {
		t.Fatal("future", r.Job.ID)
	}
}

func TestCapacityAcrossStores(t *testing.T) {
	var now atomic.Int64
	now.Store(100)
	path := filepath.Join(t.TempDir(), "q.sqlite")
	s1, e := New(path, func() (int64, error) { return now.Load(), nil }, 2, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer s1.Close()
	s2, e := New(path, func() (int64, error) { return now.Load(), nil }, 2, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer s2.Close()
	hs := []http.Handler{Handler{s1}, Handler{s2}}
	var wg sync.WaitGroup
	codes := make(chan int, 2)
	winner := make(chan string, 1)
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			c, _ := call(t, hs[i], "t", "POST", "/v1/jobs/batch", fmt.Sprintf("k%d", i), `{"jobs":[{"queue":"q","payload":{}},{"queue":"q","payload":{}}]}`)
			codes <- c
			if c == 201 {
				winner <- fmt.Sprintf("k%d", i)
			}
		}(i)
	}
	wg.Wait()
	close(codes)
	created, full := 0, 0
	for c := range codes {
		if c == 201 {
			created++
		}
		if c == 429 {
			full++
		}
	}
	if created != 1 || full != 1 {
		t.Fatal(created, full)
	}
	c, r := call(t, hs[0], "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	if c != 200 || r.LeaseToken == nil {
		t.Fatal(c, r)
	}
	c, r = call(t, hs[1], "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	if c != 200 || r.LeaseToken != nil {
		t.Fatal(c, r)
	}
	if c, _ = call(t, hs[0], "t", "POST", "/v1/jobs", "extra", `{"queue":"q","payload":{}}`); c != 429 {
		t.Fatal(c)
	}
	winningKey := <-winner
	c, replay := call(t, hs[0], "t", "POST", "/v1/jobs/batch", winningKey, `{"jobs":[{"queue":"q","payload":{}},{"queue":"q","payload":{}}]}`)
	if c != 200 {
		t.Fatal(c)
	}
	_, stats := call(t, hs[0], "t", "GET", "/v1/stats", "", "")
	if stats.Total != 2 {
		t.Fatal(stats.Total)
	}
	for _, job := range replay.Jobs {
		if c, _ = call(t, hs[1], "t", "POST", "/v1/jobs/"+job.ID+"/cancel", "", `{}`); c != 200 {
			t.Fatal(c)
		}
	}
	loserKey := "k0"
	if winningKey == "k0" {
		loserKey = "k1"
	}
	if c, _ = call(t, hs[1], "t", "POST", "/v1/jobs/batch", loserKey, `{"jobs":[{"queue":"q","payload":{}},{"queue":"q","payload":{}}]}`); c != 201 {
		t.Fatal(c)
	}
}

func TestExpiryUsesDeadlineAndBatchRollback(t *testing.T) {
	var now atomic.Int64
	now.Store(1000)
	s := setup(t, &now, filepath.Join(t.TempDir(), "q.sqlite"))
	h := Handler{s}
	c, r := call(t, h, "t", "POST", "/v1/jobs", "exp", `{"queue":"q","payload":{},"retry_base_ms":100,"max_attempts":2}`)
	if c != 201 {
		t.Fatal(c)
	}
	id := r.Job.ID
	c, r = call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	if c != 200 || r.Job.ID != id {
		t.Fatal(c, r)
	}
	now.Store(1199)
	c, r = call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	if c != 200 || r.LeaseToken != nil {
		t.Fatal(c, r)
	}
	c, r = call(t, h, "t", "GET", "/v1/jobs/"+id, "", "")
	if c != 200 || r.Job.AvailableAtMS != 1200 || r.Job.State != "ready" {
		t.Fatal(c, r)
	}
	now.Store(1200)
	c, r = call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	if c != 200 || r.Job.ID != id || r.Job.Attempts != 2 {
		t.Fatal(c, r)
	}
	now.Store(1300)
	c, r = call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	if c != 200 || r.LeaseToken != nil {
		t.Fatal(c, r)
	}
	c, r = call(t, h, "t", "GET", "/v1/jobs/"+id, "", "")
	if r.Job.State != "dead" {
		t.Fatal(c, r)
	}
	c, _ = call(t, h, "t", "POST", "/v1/jobs/"+id+"/cancel", "", `{}`)
	if c != 409 {
		t.Fatal(c)
	}
	c, _ = call(t, h, "t", "POST", "/v1/jobs/batch", "bad", `{"jobs":[{"queue":"q","payload":{}},{"queue":"!","payload":{}}]}`)
	if c != 400 {
		t.Fatal(c)
	}
	c, r = call(t, h, "t", "GET", "/v1/stats", "", "")
	if c != 200 || r.Total != 1 {
		t.Fatal(c, r)
	}
}

func TestCancelCompleteRace(t *testing.T) {
	var now atomic.Int64
	now.Store(100)
	path := filepath.Join(t.TempDir(), "q.sqlite")
	a := setup(t, &now, path)
	b := setup(t, &now, path)
	ha, hb := Handler{a}, Handler{b}
	_, r := call(t, ha, "t", "POST", "/v1/jobs", "race", `{"queue":"q","payload":{}}`)
	id := r.Job.ID
	_, r = call(t, ha, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	tok := *r.LeaseToken
	var wg sync.WaitGroup
	codes := make(chan int, 2)
	wg.Add(2)
	go func() {
		defer wg.Done()
		c, _ := call(t, ha, "t", "POST", "/v1/jobs/"+id+"/cancel", "", `{}`)
		codes <- c
	}()
	go func() {
		defer wg.Done()
		c, _ := call(t, hb, "t", "POST", "/v1/jobs/"+id+"/complete", "", fmt.Sprintf(`{"lease_token":%q,"result":{}}`, tok))
		codes <- c
	}()
	wg.Wait()
	close(codes)
	success, conflict := 0, 0
	for c := range codes {
		if c == 200 {
			success++
		} else if c == 409 {
			conflict++
		} else {
			t.Fatal(c)
		}
	}
	if success != 1 || conflict != 1 {
		t.Fatal(success, conflict)
	}
	_, r = call(t, ha, "t", "GET", "/v1/jobs/"+id, "", "")
	if r.Job.State != "completed" && r.Job.State != "cancelled" {
		t.Fatal(r.Job.State)
	}
}
