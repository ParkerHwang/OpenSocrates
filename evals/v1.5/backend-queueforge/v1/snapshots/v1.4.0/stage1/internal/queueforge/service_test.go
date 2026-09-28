package queueforge

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"path/filepath"
	"sync"
	"testing"
)

func TestQueueLifecycle(t *testing.T) {
	now := int64(1000)
	s, e := Open(filepath.Join(t.TempDir(), "q.sqlite"), func() (int64, error) { return now, nil })
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	call := func(method, path, tenant, key, body string) (int, map[string]any) {
		t.Helper()
		r := httptest.NewRequest(method, path, bytes.NewBufferString(body))
		if tenant != "" {
			r.Header.Set("X-Tenant-ID", tenant)
		}
		if key != "" {
			r.Header.Set("Idempotency-Key", key)
		}
		w := httptest.NewRecorder()
		s.ServeHTTP(w, r)
		var v map[string]any
		if e := json.Unmarshal(w.Body.Bytes(), &v); e != nil {
			t.Fatal(e, w.Body.String())
		}
		return w.Code, v
	}
	job := func(v map[string]any) map[string]any { return v["job"].(map[string]any) }
	status, v := call("POST", "/v1/jobs", "a", "key", `{"queue":"mail","payload":{"b":2,"a":1},"max_attempts":2}`)
	if status != 201 {
		t.Fatal(status, v)
	}
	id := job(v)["id"].(string)
	status, v = call("POST", "/v1/jobs", "a", "key", `{"payload":{"a":1,"b":2},"max_attempts":2,"queue":"mail"}`)
	if status != 200 || job(v)["id"] != id || v["replayed"] != true {
		t.Fatal(status, v)
	}
	status, _ = call("POST", "/v1/jobs", "a", "key", `{"queue":"mail","payload":{"a":9}}`)
	if status != 409 {
		t.Fatal(status)
	}
	status, _ = call("GET", "/v1/jobs/"+id, "b", "", "")
	if status != 404 {
		t.Fatal(status)
	}
	claim := func() (map[string]any, string) {
		t.Helper()
		st, v := call("POST", "/v1/queues/mail/claim", "a", "", `{"worker_id":"w","lease_ms":100}`)
		if st != 200 || v["job"] == nil {
			t.Fatal(st, v)
		}
		return job(v), v["lease_token"].(string)
	}
	j, tok := claim()
	if j["attempts"] != float64(1) {
		t.Fatal(j)
	}
	now = 1050
	status, v = call("POST", "/v1/jobs/"+id+"/heartbeat", "a", "", fmt.Sprintf(`{"lease_token":%q,"lease_ms":100}`, tok))
	if status != 200 || job(v)["lease_until_ms"] != float64(1150) {
		t.Fatal(status, v)
	}
	now = 1150
	j, tok2 := claim()
	if tok == tok2 || j["attempts"] != float64(2) {
		t.Fatal(j, tok, tok2)
	}
	status, _ = call("POST", "/v1/jobs/"+id+"/complete", "a", "", fmt.Sprintf(`{"lease_token":%q,"result":{}}`, tok))
	if status != 409 {
		t.Fatal(status)
	}
	status, v = call("POST", "/v1/jobs/"+id+"/complete", "a", "", fmt.Sprintf(`{"lease_token":%q,"result":{"x":1}}`, tok2))
	if status != 200 || job(v)["state"] != "completed" {
		t.Fatal(status, v)
	}
	now = 2000
	status, v = call("POST", "/v1/jobs/"+id+"/complete", "a", "", fmt.Sprintf(`{"lease_token":%q,"result":{"x":1}}`, tok2))
	if status != 200 {
		t.Fatal(status, v)
	}
	status, _ = call("POST", "/v1/jobs/"+id+"/complete", "a", "", fmt.Sprintf(`{"lease_token":%q,"result":{"x":2}}`, tok2))
	if status != 409 {
		t.Fatal(status)
	}
	status, v = call("POST", "/v1/jobs/"+id+"/heartbeat", "a", "", fmt.Sprintf(`{"lease_token":%q,"lease_ms":100}`, tok2))
	if status != 409 || v["error"].(map[string]any)["code"] != "invalid_transition" {
		t.Fatal(status, v)
	}
	status, v = call("GET", "/v1/stats", "a", "", "")
	if status != 200 || v["total"] != float64(1) || v["completed"] != float64(1) {
		t.Fatal(status, v)
	}
	status, v = call("GET", "/v1/jobs/"+id, "a", "", "")
	if status != 200 {
		t.Fatal(status, v)
	}
	if _, ok := job(v)["lease_token"]; ok {
		t.Fatal("token exposed")
	}
}
func TestConcurrentAndBatch(t *testing.T) {
	s, e := Open(filepath.Join(t.TempDir(), "q.sqlite"), nil)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	var wg sync.WaitGroup
	ids := make(chan string, 24)
	for i := 0; i < 24; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r := httptest.NewRequest("POST", "/v1/jobs", bytes.NewBufferString(`{"queue":"q","payload":{}}`))
			r.Header.Set("X-Tenant-ID", "t")
			r.Header.Set("Idempotency-Key", "same")
			w := httptest.NewRecorder()
			s.ServeHTTP(w, r)
			if w.Code != 200 && w.Code != 201 {
				ids <- fmt.Sprint("error:", w.Code, w.Body.String())
				return
			}
			var v struct {
				Job Job `json:"job"`
			}
			_ = json.Unmarshal(w.Body.Bytes(), &v)
			ids <- v.Job.ID
		}()
	}
	wg.Wait()
	close(ids)
	first := ""
	for id := range ids {
		if first == "" {
			first = id
		}
		if first != id {
			t.Fatal(first, id)
		}
	}
	r := httptest.NewRequest("POST", "/v1/jobs/batch", bytes.NewBufferString(`{"jobs":[{"queue":"q","payload":{}},{"queue":"bad!","payload":{}}]}`))
	r.Header.Set("X-Tenant-ID", "t")
	r.Header.Set("Idempotency-Key", "batch")
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	if w.Code != 400 {
		t.Fatal(w.Code, w.Body.String())
	}
	r = httptest.NewRequest("GET", "/v1/stats", nil)
	r.Header.Set("X-Tenant-ID", "t")
	w = httptest.NewRecorder()
	s.ServeHTTP(w, r)
	var counts map[string]int
	_ = json.Unmarshal(w.Body.Bytes(), &counts)
	if counts["total"] != 1 {
		t.Fatal(counts)
	}
}

func TestSharedDatabaseClaimAndMaxAttempts(t *testing.T) {
	path := filepath.Join(t.TempDir(), "shared.sqlite")
	now := int64(5000)
	clock := func() (int64, error) { return now, nil }
	a, e := Open(path, clock)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := Open(path, clock)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	request := func(s *Service, method, path, key, body string) (int, map[string]any) {
		t.Helper()
		r := httptest.NewRequest(method, path, bytes.NewBufferString(body))
		r.Header.Set("X-Tenant-ID", "t")
		if key != "" {
			r.Header.Set("Idempotency-Key", key)
		}
		w := httptest.NewRecorder()
		s.ServeHTTP(w, r)
		var v map[string]any
		if e := json.Unmarshal(w.Body.Bytes(), &v); e != nil {
			t.Fatal(e)
		}
		return w.Code, v
	}
	st, v := request(a, "POST", "/v1/jobs/batch", "batch", `{"jobs":[{"queue":"q","payload":{"x":1},"max_attempts":1},{"queue":"q","payload":{}}]}`)
	if st != 201 {
		t.Fatal(st, v)
	}
	jobs := v["jobs"].([]any)
	if jobs[0].(map[string]any)["created_seq"].(float64) >= jobs[1].(map[string]any)["created_seq"].(float64) {
		t.Fatal(jobs)
	}
	st, v = request(b, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":10}`)
	if st != 200 || v["job"].(map[string]any)["id"] != jobs[0].(map[string]any)["id"] {
		t.Fatal(st, v)
	}
	st, v = request(a, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w2","lease_ms":10}`)
	if st != 200 || v["job"].(map[string]any)["id"] != jobs[1].(map[string]any)["id"] {
		t.Fatal(st, v)
	}
	now = 5010
	st, v = request(b, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w3","lease_ms":10}`)
	if st != 200 || v["job"].(map[string]any)["id"] != jobs[1].(map[string]any)["id"] {
		t.Fatal(st, v)
	}
	st, v = request(a, "GET", "/v1/jobs/"+jobs[0].(map[string]any)["id"].(string), "", "")
	if st != 200 || v["job"].(map[string]any)["state"] != "dead" {
		t.Fatal(st, v)
	}
}
