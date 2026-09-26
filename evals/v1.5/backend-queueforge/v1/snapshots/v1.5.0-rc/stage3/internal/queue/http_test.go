package queue

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
)

type response struct {
	Job          Job     `json:"job"`
	Jobs         []Job   `json:"jobs"`
	Replayed     bool    `json:"replayed"`
	LeaseToken   *string `json:"lease_token"`
	LeaseUntilMS *int64  `json:"lease_until_ms"`
	Error        struct {
		Code string `json:"code"`
	} `json:"error"`
	Total int `json:"total"`
}

func call(t *testing.T, h http.Handler, tenant, method, path, key, body string) (int, response) {
	t.Helper()
	r := httptest.NewRequest(method, path, bytes.NewBufferString(body))
	if tenant != "" {
		r.Header.Set("X-Tenant-ID", tenant)
	}
	if key != "" {
		r.Header.Set("Idempotency-Key", key)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	var out response
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatal(err, w.Body.String())
	}
	return w.Code, out
}
func setup(t *testing.T, now *atomic.Int64, path string) *Store {
	t.Helper()
	s, e := New(path, func() (int64, error) { return now.Load(), nil })
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { s.Close() })
	return s
}
func TestLifecycleAndIsolation(t *testing.T) {
	var now atomic.Int64
	now.Store(1000)
	s := setup(t, &now, filepath.Join(t.TempDir(), "q.sqlite"))
	h := Handler{s}
	input := `{"queue":"mail","payload":{"n":1}}`
	code, a := call(t, h, "alpha", "POST", "/v1/jobs", "k", input)
	if code != 201 || a.Job.MaxAttempts != 3 || a.Job.State != "ready" {
		t.Fatalf("submit %d %+v", code, a)
	}
	id := a.Job.ID
	code, b := call(t, h, "alpha", "POST", "/v1/jobs", "k", `{"payload":{"n":1},"queue":"mail","max_attempts":3}`)
	if code != 200 || !b.Replayed || b.Job.ID != id {
		t.Fatalf("replay %d %+v", code, b)
	}
	if c, _ := call(t, h, "alpha", "POST", "/v1/jobs", "k", `{"queue":"mail","payload":{"n":2}}`); c != 409 {
		t.Fatal(c)
	}
	if c, _ := call(t, h, "beta", "GET", "/v1/jobs/"+id, "", ""); c != 404 {
		t.Fatal(c)
	}
	if c, _ := call(t, h, "beta", "GET", "/v1/stats", "", ""); c != 200 {
		t.Fatal(c)
	}
	claim := `{"worker_id":"w","lease_ms":100}`
	code, b = call(t, h, "alpha", "POST", "/v1/queues/mail/claim", "", claim)
	if code != 200 || b.LeaseToken == nil || b.Job.Attempts != 1 || *b.LeaseUntilMS != 1100 {
		t.Fatalf("claim %d %+v", code, b)
	}
	old := *b.LeaseToken
	now.Store(1050)
	code, b = call(t, h, "alpha", "POST", "/v1/jobs/"+id+"/heartbeat", "", fmt.Sprintf(`{"lease_token":%q,"lease_ms":100}`, old))
	if code != 200 || *b.Job.LeaseUntilMS != 1150 {
		t.Fatalf("heartbeat %d %+v", code, b)
	}
	now.Store(1150)
	if c, _ := call(t, h, "alpha", "POST", "/v1/jobs/"+id+"/complete", "", fmt.Sprintf(`{"lease_token":%q,"result":{}}`, old)); c != 409 {
		t.Fatal(c)
	}
	code, b = call(t, h, "alpha", "POST", "/v1/queues/mail/claim", "", claim)
	if code != 200 || b.Job.Attempts != 2 || b.Job.LastError == nil || *b.Job.LastError != "lease_expired" || *b.LeaseToken == old {
		t.Fatalf("reclaim %d %+v", code, b)
	}
	second := *b.LeaseToken
	if c, _ := call(t, h, "alpha", "POST", "/v1/jobs/"+id+"/fail", "", fmt.Sprintf(`{"lease_token":%q,"error":"oops"}`, old)); c != 409 {
		t.Fatal(c)
	}
	code, b = call(t, h, "alpha", "POST", "/v1/jobs/"+id+"/fail", "", fmt.Sprintf(`{"lease_token":%q,"error":"oops"}`, second))
	if code != 200 || b.Job.State != "ready" {
		t.Fatalf("fail %d %+v", code, b)
	}
	_, b = call(t, h, "alpha", "POST", "/v1/queues/mail/claim", "", claim)
	third := *b.LeaseToken
	if b.Job.Attempts != 3 {
		t.Fatal(b.Job.Attempts)
	}
	code, b = call(t, h, "alpha", "POST", "/v1/jobs/"+id+"/complete", "", fmt.Sprintf(`{"lease_token":%q,"result":{"ok":true}}`, third))
	if code != 200 || b.Job.State != "completed" {
		t.Fatalf("complete %d %+v", code, b)
	}
	now.Store(9999)
	if c, _ := call(t, h, "alpha", "POST", "/v1/jobs/"+id+"/complete", "", fmt.Sprintf(`{"lease_token":%q,"result":{"ok":true}}`, third)); c != 200 {
		t.Fatal(c)
	}
	if c, _ := call(t, h, "alpha", "POST", "/v1/jobs/"+id+"/complete", "", fmt.Sprintf(`{"lease_token":%q,"result":{"ok":false}}`, third)); c != 409 {
		t.Fatal(c)
	}
	_, b = call(t, h, "alpha", "GET", "/v1/jobs/"+id, "", "")
	raw, _ := json.Marshal(b.Job)
	if bytes.Contains(raw, []byte("lease_token")) {
		t.Fatal(string(raw))
	}
}
func TestConcurrentAndBatch(t *testing.T) {
	var now atomic.Int64
	now.Store(7)
	path := filepath.Join(t.TempDir(), "q.sqlite")
	s1 := setup(t, &now, path)
	s2 := setup(t, &now, path)
	h1, h2 := Handler{s1}, Handler{s2}
	var wg sync.WaitGroup
	ids := make(chan string, 30)
	statuses := make(chan int, 30)
	for i := 0; i < 30; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			h := http.Handler(h1)
			if i%2 == 0 {
				h = h2
			}
			c, r := call(t, h, "t", "POST", "/v1/jobs", "same", `{"queue":"q","payload":{"x":1}}`)
			statuses <- c
			ids <- r.Job.ID
		}(i)
	}
	wg.Wait()
	close(ids)
	close(statuses)
	first := ""
	created := 0
	for id := range ids {
		if first == "" {
			first = id
		}
		if id != first {
			t.Fatalf("duplicate IDs %q %q", id, first)
		}
	}
	for c := range statuses {
		if c == 201 {
			created++
		} else if c != 200 {
			t.Fatal(c)
		}
	}
	if created != 1 {
		t.Fatal(created)
	}
	claims := make(chan response, 2)
	for _, handler := range []http.Handler{h1, h2} {
		wg.Add(1)
		go func(h http.Handler) {
			defer wg.Done()
			c, r := call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
			if c != 200 {
				t.Errorf("claim status %d", c)
			}
			claims <- r
		}(handler)
	}
	wg.Wait()
	close(claims)
	owners := 0
	for r := range claims {
		if r.LeaseToken != nil {
			owners++
		}
	}
	if owners != 1 {
		t.Fatalf("simultaneous lease owners: %d", owners)
	}
	if c, _ := call(t, h1, "t", "POST", "/v1/jobs/batch", "bad", `{"jobs":[{"queue":"q","payload":{}},{"queue":"bad!","payload":{}}]}`); c != 400 {
		t.Fatal(c)
	}
	_, r := call(t, h1, "t", "GET", "/v1/stats", "", "")
	if r.Total != 1 {
		t.Fatal(r.Total)
	}
	c, r := call(t, h2, "t", "POST", "/v1/jobs/batch", "good", `{"jobs":[{"queue":"q","payload":{"a":1}},{"queue":"q","payload":{"a":2}}]}`)
	if c != 201 || len(r.Jobs) != 2 || r.Jobs[0].CreatedSeq >= r.Jobs[1].CreatedSeq {
		t.Fatalf("batch %d %+v", c, r)
	}
	// Reopen the same file to verify acknowledged rows survive a new connection.
	s3 := setup(t, &now, path)
	c, r = call(t, Handler{s3}, "t", "GET", "/v1/jobs/"+first, "", "")
	if c != 200 || r.Job.ID != first {
		t.Fatalf("restart read %d %+v", c, r)
	}
}
func TestMaxAttemptsExpiry(t *testing.T) {
	var now atomic.Int64
	now.Store(1)
	s := setup(t, &now, filepath.Join(t.TempDir(), "q.sqlite"))
	h := Handler{s}
	_, r := call(t, h, "t", "POST", "/v1/jobs", "one", `{"queue":"q","payload":{},"max_attempts":1}`)
	id := r.Job.ID
	_, r = call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":10}`)
	now.Store(11)
	_, r = call(t, h, "t", "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":10}`)
	if r.Job.ID != "" || r.LeaseToken != nil {
		t.Fatalf("expected empty claim %+v", r)
	}
	_, r = call(t, h, "t", "GET", "/v1/jobs/"+id, "", "")
	if r.Job.State != "dead" {
		t.Fatal(r.Job.State)
	}
}
