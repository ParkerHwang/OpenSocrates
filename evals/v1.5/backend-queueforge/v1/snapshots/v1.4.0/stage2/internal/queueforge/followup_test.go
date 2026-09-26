package queueforge

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"queueforge/internal/platform"
)

func api(t *testing.T, s *Service, method, path, key, body string) (int, map[string]any) {
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
		t.Fatal(e, w.Body.String())
	}
	return w.Code, v
}
func mustStatus(t *testing.T, code, want int, v map[string]any) {
	t.Helper()
	if code != want {
		t.Fatalf("status %d, want %d: %v", code, want, v)
	}
}
func TestSchedulingCapacityCancelAndListing(t *testing.T) {
	now := int64(1000)
	path := filepath.Join(t.TempDir(), "q.sqlite")
	clock := func() (int64, error) { return now, nil }
	a, e := OpenWithLimits(path, clock, 4, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := OpenWithLimits(path, clock, 4, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	st, v := api(t, a, "POST", "/v1/jobs/batch", "batch", `{"jobs":[{"queue":"q","payload":{"n":1},"priority":-1},{"queue":"q","payload":{"n":2},"priority":5},{"queue":"q","payload":{"n":3},"priority":5},{"queue":"q","payload":{"n":4},"priority":10,"run_at_ms":5000}]}`)
	mustStatus(t, st, 201, v)
	jobs := v["jobs"].([]any)
	id := func(i int) string { return jobs[i].(map[string]any)["id"].(string) }
	st, v = api(t, b, "POST", "/v1/jobs", "overflow", `{"queue":"q","payload":{}}`)
	mustStatus(t, st, 429, v)
	if v["error"].(map[string]any)["code"] != "capacity" {
		t.Fatal(v)
	}
	st, v = api(t, b, "POST", "/v1/jobs/batch", "batch", `{"jobs":[{"queue":"q","payload":{"n":1},"priority":-1},{"queue":"q","payload":{"n":2},"priority":5},{"queue":"q","payload":{"n":3},"priority":5},{"queue":"q","payload":{"n":4},"priority":10,"run_at_ms":5000}]}`)
	mustStatus(t, st, 200, v)
	st, v = api(t, a, "GET", "/v1/jobs?queue=q&limit=2", "", "")
	mustStatus(t, st, 200, v)
	first := v["items"].([]any)
	if len(first) != 2 {
		t.Fatal(v)
	}
	cursor := v["next_cursor"].(string)
	st, v = api(t, b, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	mustStatus(t, st, 200, v)
	if v["job"].(map[string]any)["id"] != id(1) {
		t.Fatal(v)
	}
	token := v["lease_token"].(string)
	st, v = api(t, a, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	mustStatus(t, st, 200, v)
	if v["job"] != nil {
		t.Fatal("inflight exceeded", v)
	}
	st, v = api(t, a, "POST", "/v1/jobs/"+id(1)+"/heartbeat", "", fmt.Sprintf(`{"lease_token":%q,"lease_ms":100}`, token))
	mustStatus(t, st, 200, v)
	st, v = api(t, b, "POST", "/v1/jobs/"+id(1)+"/cancel", "", `{}`)
	mustStatus(t, st, 200, v)
	if v["job"].(map[string]any)["state"] != "cancelled" {
		t.Fatal(v)
	}
	st, v = api(t, a, "POST", "/v1/jobs/"+id(1)+"/complete", "", fmt.Sprintf(`{"lease_token":%q,"result":{}}`, token))
	mustStatus(t, st, 409, v)
	st, v = api(t, b, "POST", "/v1/jobs/"+id(1)+"/cancel", "", `{}`)
	mustStatus(t, st, 200, v)
	st, v = api(t, b, "POST", "/v1/jobs", "later", `{"queue":"q","payload":{}}`)
	mustStatus(t, st, 201, v)
	st, v = api(t, b, "GET", "/v1/jobs?queue=q&limit=2&cursor="+cursor, "", "")
	mustStatus(t, st, 200, v)
	second := v["items"].([]any)
	if len(second) != 2 || second[0].(map[string]any)["id"] != id(2) || second[1].(map[string]any)["id"] != id(3) || v["next_cursor"] != nil {
		t.Fatal(v)
	}
	st, v = api(t, b, "GET", "/v1/jobs?queue=other&cursor="+cursor, "", "")
	mustStatus(t, st, 400, v)
	st, v = api(t, a, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	mustStatus(t, st, 200, v)
	if v["job"].(map[string]any)["id"] != id(2) {
		t.Fatal(v)
	}
}
func TestRetryBoundaries(t *testing.T) {
	now := int64(1000)
	s, e := Open(filepath.Join(t.TempDir(), "q.sqlite"), func() (int64, error) { return now, nil })
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	st, v := api(t, s, "POST", "/v1/jobs", "one", `{"queue":"q","payload":{},"retry_base_ms":1000,"max_attempts":3}`)
	mustStatus(t, st, 201, v)
	id := v["job"].(map[string]any)["id"].(string)
	claim := func() map[string]any {
		t.Helper()
		st, v := api(t, s, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
		mustStatus(t, st, 200, v)
		return v
	}
	v = claim()
	tok := v["lease_token"].(string)
	st, v = api(t, s, "POST", "/v1/jobs/"+id+"/fail", "", fmt.Sprintf(`{"lease_token":%q,"error":"retry"}`, tok))
	mustStatus(t, st, 200, v)
	if v["job"].(map[string]any)["available_at_ms"] != float64(2000) {
		t.Fatal(v)
	}
	now = 1999
	if v = claim(); v["job"] != nil {
		t.Fatal(v)
	}
	now = 2000
	v = claim()
	if v["job"] == nil {
		t.Fatal(v)
	}
	now = 2200
	if v = claim(); v["job"] != nil {
		t.Fatal(v)
	}
	st, v = api(t, s, "GET", "/v1/jobs/"+id, "", "")
	mustStatus(t, st, 200, v)
	if v["job"].(map[string]any)["available_at_ms"] != float64(4100) {
		t.Fatal(v)
	}
	now = 4099
	if v = claim(); v["job"] != nil {
		t.Fatal(v)
	}
	now = 4100
	if v = claim(); v["job"] == nil {
		t.Fatal(v)
	}
}
func TestMigrationAndFutureVersion(t *testing.T) {
	path := filepath.Join(t.TempDir(), "legacy.sqlite")
	db, e := sql.Open(platform.SQLiteDriver, path)
	if e != nil {
		t.Fatal(e)
	}
	for _, q := range []string{`PRAGMA journal_mode=WAL`, `CREATE TABLE jobs (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, tenant TEXT NOT NULL, queue TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL, created_at_ms INTEGER NOT NULL, available_at_ms INTEGER NOT NULL, lease_until_ms INTEGER, lease_token TEXT, last_error TEXT, result TEXT, completed_token TEXT)`, `CREATE TABLE idempotency (tenant TEXT NOT NULL, endpoint TEXT NOT NULL, key TEXT NOT NULL, command TEXT NOT NULL, ids TEXT NOT NULL, PRIMARY KEY(tenant,endpoint,key))`, `INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms,lease_until_ms,lease_token) VALUES('old','t','q','{}','leased',1,3,1000,1000,1100,'old-token')`, `INSERT INTO idempotency VALUES('t','jobs','key','[{"queue":"q","payload":{},"max_attempts":3}]','["old"]')`, `PRAGMA user_version=1`} {
		if _, e = db.Exec(q); e != nil {
			t.Fatal(e)
		}
	}
	db.Close()
	now := int64(1050)
	s, e := Open(path, func() (int64, error) { return now, nil })
	if e != nil {
		t.Fatal(e)
	}
	st, v := api(t, s, "POST", "/v1/jobs", "key", `{"queue":"q","payload":{}}`)
	mustStatus(t, st, 200, v)
	j := v["job"].(map[string]any)
	if j["id"] != "old" || j["attempts"] != float64(1) || j["retry_base_ms"] != float64(0) {
		t.Fatal(v)
	}
	st, v = api(t, s, "POST", "/v1/jobs", "key", `{"queue":"q","payload":{},"priority":1}`)
	mustStatus(t, st, 409, v)
	st, v = api(t, s, "POST", "/v1/jobs/old/heartbeat", "", `{"lease_token":"old-token","lease_ms":100}`)
	mustStatus(t, st, 200, v)
	s.Close()
	db, e = sql.Open(platform.SQLiteDriver, path)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = db.Exec(`PRAGMA wal_checkpoint(TRUNCATE)`); e != nil {
		t.Fatal(e)
	}
	if _, e = db.Exec(`PRAGMA journal_mode=DELETE`); e != nil {
		t.Fatal(e)
	}
	if _, e = db.Exec(`PRAGMA user_version=3`); e != nil {
		t.Fatal(e)
	}
	db.Close()
	before, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	if s, e = Open(path, nil); e == nil {
		s.Close()
		t.Fatal("future version accepted")
	}
	after, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.Equal(before, after) {
		t.Fatal("future database changed")
	}
}

func TestBatchCapacityRollbackAndCancelRace(t *testing.T) {
	path := filepath.Join(t.TempDir(), "q.sqlite")
	a, e := OpenWithLimits(path, func() (int64, error) { return 1000, nil }, 2, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := OpenWithLimits(path, func() (int64, error) { return 1000, nil }, 2, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	st, v := api(t, a, "POST", "/v1/jobs", "one", `{"queue":"q","payload":{}}`)
	mustStatus(t, st, 201, v)
	id := v["job"].(map[string]any)["id"].(string)
	st, v = api(t, b, "POST", "/v1/jobs/batch", "too-many", `{"jobs":[{"queue":"q","payload":{}},{"queue":"q","payload":{}}]}`)
	mustStatus(t, st, 429, v)
	st, v = api(t, a, "GET", "/v1/stats", "", "")
	mustStatus(t, st, 200, v)
	if v["total"] != float64(1) {
		t.Fatal("batch partial insert", v)
	}
	st, v = api(t, b, "POST", "/v1/queues/q/claim", "", `{"worker_id":"w","lease_ms":100}`)
	mustStatus(t, st, 200, v)
	token := v["lease_token"].(string)
	type outcome struct {
		op     string
		status int
		body   map[string]any
	}
	ch := make(chan outcome, 2)
	go func() { st, v := api(t, a, "POST", "/v1/jobs/"+id+"/cancel", "", `{}`); ch <- outcome{"cancel", st, v} }()
	go func() {
		st, v := api(t, b, "POST", "/v1/jobs/"+id+"/complete", "", fmt.Sprintf(`{"lease_token":%q,"result":{}}`, token))
		ch <- outcome{"complete", st, v}
	}()
	x, y := <-ch, <-ch
	if x.status == 200 && y.status == 200 {
		t.Fatal("both terminal transitions succeeded", x, y)
	}
	if (x.status != 200 && y.status != 200) || (x.status != 409 && y.status != 409) {
		t.Fatal(x, y)
	}
	st, v = api(t, a, "GET", "/v1/stats", "", "")
	mustStatus(t, st, 200, v)
	if v["total"] != float64(1) || v["ready"] != float64(0) || v["leased"] != float64(0) || v["completed"].(float64)+v["cancelled"].(float64) != float64(1) {
		t.Fatal(v)
	}
	st, v = api(t, b, "POST", "/v1/jobs/batch", "too-many", `{"jobs":[{"queue":"q","payload":{}},{"queue":"q","payload":{}}]}`)
	mustStatus(t, st, 201, v)
	if len(v["jobs"].([]any)) != 2 {
		t.Fatal(v)
	}
}
