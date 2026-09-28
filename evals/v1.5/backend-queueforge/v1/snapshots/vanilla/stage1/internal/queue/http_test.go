package queue

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestHTTPContract(t *testing.T) {
	path := filepath.Join(t.TempDir(), "queue.sqlite")
	store, e := Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer store.Close()
	clock := filepath.Join(t.TempDir(), "clock")
	if e = os.WriteFile(clock, []byte("1000"), 0600); e != nil {
		t.Fatal(e)
	}
	server := httptest.NewServer(&Server{Store: store, ClockFile: clock})
	defer server.Close()
	call := func(method, path, tenant, key, body string) (int, map[string]any) {
		t.Helper()
		req, e := http.NewRequest(method, server.URL+path, bytes.NewBufferString(body))
		if e != nil {
			t.Fatal(e)
		}
		if tenant != "" {
			req.Header.Set("X-Tenant-ID", tenant)
		}
		if key != "" {
			req.Header.Set("Idempotency-Key", key)
		}
		res, e := server.Client().Do(req)
		if e != nil {
			t.Fatal(e)
		}
		defer res.Body.Close()
		var v map[string]any
		if e = json.NewDecoder(res.Body).Decode(&v); e != nil {
			t.Fatal(e)
		}
		return res.StatusCode, v
	}
	code, v := call("GET", "/health", "", "", "")
	if code != 200 || v["schema_version"] != float64(1) {
		t.Fatal(code, v)
	}
	code, v = call("POST", "/v1/jobs/batch", "t", "invalid", `{"jobs":[{"queue":"q","payload":{}},{"queue":"!","payload":{}}]}`)
	if code != 400 || v["error"].(map[string]any)["code"] != "validation" {
		t.Fatal(code, v)
	}
	code, v = call("GET", "/v1/stats", "t", "", "")
	if code != 200 || v["total"] != float64(0) {
		t.Fatal(code, v)
	}
	code, v = call("POST", "/v1/jobs", "t", "key", `{"queue":"q","payload":{"b":2,"a":1}}`)
	if code != 201 || v["replayed"] != false {
		t.Fatal(code, v)
	}
	job := v["job"].(map[string]any)
	id := job["id"].(string)
	if _, ok := job["lease_token"]; ok {
		t.Fatal("token in job")
	}
	code, v = call("POST", "/v1/jobs", "t", "key", `{"payload":{"a":1,"b":2},"max_attempts":3,"queue":"q"}`)
	if code != 200 || v["job"].(map[string]any)["id"] != id {
		t.Fatal(code, v)
	}
	code, v = call("POST", "/v1/jobs", "t", "key", `{"queue":"q","payload":{"a":2}}`)
	if code != 409 || v["error"].(map[string]any)["code"] != "idempotency_conflict" {
		t.Fatal(code, v)
	}
	code, _ = call("GET", "/v1/jobs/"+id, "other", "", "")
	if code != 404 {
		t.Fatal(code)
	}
	code, v = call("POST", "/v1/queues/q/claim", "t", "", `{"worker_id":"worker","lease_ms":10}`)
	if code != 200 || v["lease_token"] == nil {
		t.Fatal(code, v)
	}
	token := v["lease_token"].(string)
	if e = os.WriteFile(clock, []byte("1010"), 0600); e != nil {
		t.Fatal(e)
	}
	code, v = call("POST", "/v1/jobs/"+id+"/heartbeat", "t", "", fmt.Sprintf(`{"lease_token":%q,"lease_ms":10}`, token))
	if code != 409 || v["error"].(map[string]any)["code"] != "lease_conflict" {
		t.Fatal(code, v)
	}
	code, v = call("POST", "/v1/queues/q/claim", "t", "", `{"worker_id":"worker","lease_ms":10}`)
	if code != 200 || v["lease_token"].(string) == token {
		t.Fatal(code, v)
	}
}
