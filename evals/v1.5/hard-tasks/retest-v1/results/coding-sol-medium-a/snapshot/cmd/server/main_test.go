package main

import (
	"auditledger/internal/platform"
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sync"
	"testing"
)

func request(t *testing.T, h http.Handler, method, path, tenant, key, body string) (int, map[string]any) {
	t.Helper()
	r := httptest.NewRequest(method, path, bytes.NewBufferString(body))
	if tenant != "" {
		r.Header.Set("X-Tenant", tenant)
	}
	if key != "" {
		r.Header.Set("Idempotency-Key", key)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	var v map[string]any
	if e := json.Unmarshal(w.Body.Bytes(), &v); e != nil {
		t.Fatalf("%s %s: %v / %s", method, path, e, w.Body.String())
	}
	return w.Code, v
}
func must(t *testing.T, h http.Handler, method, path, key, body string, want int) map[string]any {
	t.Helper()
	code, v := request(t, h, method, path, "tenant", key, body)
	if code != want {
		t.Fatalf("%s %s: got %d %v, want %d", method, path, code, v, want)
	}
	return v
}
func value(t *testing.T, v any, k string) any {
	t.Helper()
	m, ok := v.(map[string]any)
	if !ok {
		t.Fatalf("not an object: %v", v)
	}
	return m[k]
}
func TestLedgerFlowAndHistory(t *testing.T) {
	db, e := platform.Open(filepath.Join(t.TempDir(), "ledger.db"))
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	h := &api{db}
	must(t, h, "POST", "/accounts", "a", `{"name":"A","opening":100}`, 201)
	must(t, h, "POST", "/accounts", "b", `{"name":"B","opening":0}`, 201)
	batch := `{"transfers":[{"from":"A","to":"B","amount":20,"from_version":1,"to_version":1},{"from":"B","to":"A","amount":5,"from_version":2,"to_version":2}]}`
	v := must(t, h, "POST", "/batches", "batch", batch, 201)
	ids := value(t, v, "transfers").([]any)
	tid := value(t, ids[0], "id").(string)
	code, replay := request(t, h, "POST", "/batches", "tenant", "batch", ` { "transfers" : [ {"to":"B","from":"A","amount":20,"from_version":1,"to_version":1},{"to":"A","from":"B","amount":5,"from_version":2,"to_version":2} ] }`)
	if code != 201 || value(t, replay, "transfers").([]any)[0].(map[string]any)["id"] != tid {
		t.Fatal("replay changed result")
	}
	badBatch := `{"transfers":[{"from":"A","to":"B","amount":1},{"from":"A","to":"B","amount":999}]}`
	must(t, h, "POST", "/batches", "bad", badBatch, 409)
	unchanged := must(t, h, "GET", "/accounts/A", "", "", 200)
	if value(t, value(t, unchanged, "account"), "balance") != float64(85) || value(t, value(t, unchanged, "account"), "version") != float64(3) {
		t.Fatal("failed batch changed account", unchanged)
	}
	must(t, h, "POST", "/transfers", "bad-version", `{"from":"A","to":"B","amount":1,"from_version":2}`, 409)
	must(t, h, "POST", "/transfers", "bad-version", `{"from":"A","to":"B","amount":1,"from_version":0}`, 400)
	hist := must(t, h, "GET", "/summary?snapshot=2", "", "", 200)
	if value(t, hist, "totals").(map[string]any)["balance"] != float64(100) {
		t.Fatal(hist)
	}
	hold := must(t, h, "POST", "/holds", "hold", `{"account":"A","amount":10}`, 201)
	hid := value(t, value(t, hold, "hold"), "id").(string)
	must(t, h, "POST", "/holds/"+hid+"/capture", "capture", `{"to":"B"}`, 200)
	must(t, h, "POST", "/holds/"+hid+"/release", "terminal", `{}`, 409)
	releaseHold := must(t, h, "POST", "/holds", "release-hold", `{"account":"B","amount":2}`, 201)
	releaseID := value(t, value(t, releaseHold, "hold"), "id").(string)
	must(t, h, "POST", "/holds/"+releaseID+"/release", "release", `{}`, 200)
	must(t, h, "POST", "/transfers/"+tid+"/reverse", "reverse", `{}`, 200)
	must(t, h, "POST", "/transfers/"+tid+"/reverse", "different", `{}`, 409)
	old := must(t, h, "GET", "/summary?snapshot=2", "", "", 200)
	if value(t, old, "entry_count") != float64(2) {
		t.Fatal(old)
	}
	now := must(t, h, "GET", "/summary", "", "", 200)
	accounts := value(t, now, "accounts").([]any)
	if len(accounts) != 2 || value(t, now, "totals").(map[string]any)["reserved"] != float64(0) {
		t.Fatal(now)
	}
	entries := must(t, h, "GET", "/entries?limit=3", "", "", 200)
	if value(t, entries, "has_more") != true {
		t.Fatal(entries)
	}
	snap := value(t, entries, "snapshot").(float64)
	next := value(t, entries, "next_after").(float64)
	page := must(t, h, "GET", fmt.Sprintf("/entries?snapshot=%.0f&after=%.0f", snap, next), "", "", 200)
	if value(t, page, "snapshot") != snap {
		t.Fatal(page)
	}
	must(t, h, "POST", "/accounts", "a", `{"name":"C","opening":1}`, 409)
	must(t, h, "POST", "/accounts", "invalid", `{"name":"C","opening":null}`, 400)
	must(t, h, "POST", "/accounts", "invalid", `{"name":"C","opening":0}`, 201)
}
func TestConcurrentSharedDatabase(t *testing.T) {
	path := filepath.Join(t.TempDir(), "shared.db")
	a, e := platform.Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := platform.Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	h1, h2 := &api{a}, &api{b}
	must(t, h1, "POST", "/accounts", "a", `{"name":"A","opening":100}`, 201)
	must(t, h1, "POST", "/accounts", "b", `{"name":"B","opening":0}`, 201)
	var wg sync.WaitGroup
	results := make(chan map[string]any, 2)
	codes := make(chan int, 2)
	for _, h := range []http.Handler{h1, h2} {
		wg.Add(1)
		go func(h http.Handler) {
			defer wg.Done()
			c, v := request(t, h, "POST", "/transfers", "tenant", "same", `{"from":"A","to":"B","amount":9}`)
			codes <- c
			results <- v
		}(h)
	}
	wg.Wait()
	close(codes)
	close(results)
	var id string
	for c := range codes {
		if c != 201 {
			t.Fatalf("status %d", c)
		}
	}
	for v := range results {
		x := value(t, value(t, v, "transfer"), "id").(string)
		if id != "" && x != id {
			t.Fatal("duplicate transfer")
		}
		id = x
	}
	v := must(t, h1, "GET", "/accounts/A", "", "", 200)
	if value(t, value(t, v, "account"), "balance") != float64(91) {
		t.Fatal(v)
	}
}

func TestReplayPersistsAndTenantIsolation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "retry.db")
	db, e := platform.Open(path)
	if e != nil {
		t.Fatal(e)
	}
	h := &api{db}
	first := must(t, h, "POST", "/accounts", "create", `{"name":"A","opening":8}`, 201)
	if e = db.Close(); e != nil {
		t.Fatal(e)
	}
	db, e = platform.Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	h = &api{db}
	replayed := must(t, h, "POST", "/accounts", "create", ` {"opening":8,"name":"A"} `, 201)
	if value(t, first, "account").(map[string]any)["version"] != value(t, replayed, "account").(map[string]any)["version"] {
		t.Fatal("replay changed version")
	}
	code, result := request(t, h, "GET", "/accounts/A", "other", "", "")
	if code != 404 || value(t, result, "error").(map[string]any)["code"] != "not_found" {
		t.Fatal(code, result)
	}
	must(t, h, "POST", "/accounts", "create", `{"name":"A","opening":9}`, 409)
	must(t, h, "POST", "/accounts", "failed", `{"name":"A","opening":0}`, 409)
	must(t, h, "POST", "/accounts", "failed", `{"name":"B","opening":0}`, 201)
	for _, body := range []string{`{"name":"C","opening":1,"extra":1}`, `{"name":"C","opening":1.0}`, `{"name":"C","opening":1} {}`, `{"name":"C","opening":null}`} {
		must(t, h, "POST", "/accounts", "invalid", body, 400)
	}
	must(t, h, "GET", "/entries?limit=0", "", "", 400)
	must(t, h, "GET", "/summary?unknown=1", "", "", 400)
}
func TestMigration(t *testing.T) {
	path := filepath.Join(t.TempDir(), "old.db")
	raw, e := sql.Open("sqlite", path)
	if e != nil {
		t.Fatal(e)
	}
	statements := []string{`CREATE TABLE legacy_accounts(tenant TEXT,name TEXT,balance INTEGER,PRIMARY KEY(tenant,name))`, `CREATE TABLE legacy_movements(id INTEGER PRIMARY KEY,tenant TEXT,source TEXT,target TEXT,units INTEGER)`, `CREATE TABLE legacy_notes(key TEXT PRIMARY KEY,value TEXT)`, `INSERT INTO legacy_accounts VALUES('old','a',83),('old','b',37)`, `INSERT INTO legacy_movements VALUES(7,'old','a','b',20),(11,'old','b','a',3)`, `PRAGMA user_version=1`}
	for _, s := range statements {
		if _, e = raw.Exec(s); e != nil {
			t.Fatal(e)
		}
	}
	if _, e = raw.Exec(`INSERT INTO legacy_notes VALUES(?,?)`, "unicode", "保全 / preserved\nline two"); e != nil {
		t.Fatal(e)
	}
	raw.Close()
	db, e := platform.Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	h := &api{db}
	c, v := request(t, h, "GET", "/summary", "old", "", "")
	if c != 200 || value(t, v, "entry_count") != float64(6) {
		t.Fatalf("migration %d %v", c, v)
	}
	a := value(t, v, "accounts").([]any)[0]
	if value(t, a, "balance") != float64(83) {
		t.Fatal(a)
	}
	c, v = request(t, h, "GET", "/entries?limit=3", "old", "", "")
	if c != 200 {
		t.Fatal(v)
	}
	es := value(t, v, "entries").([]any)
	if value(t, es[0], "balance_delta") != float64(100) || value(t, es[2], "legacy_id") != float64(7) {
		t.Fatal(es)
	}
	var ver int
	db.QueryRow(`PRAGMA user_version`).Scan(&ver)
	if ver != 2 {
		t.Fatal(ver)
	}
	var note string
	db.QueryRow(`SELECT value FROM legacy_notes WHERE key='unicode'`).Scan(&note)
	if note != "保全 / preserved\nline two" {
		t.Fatal(note)
	}
	db2, e := platform.Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer db2.Close()
	var count int
	db2.QueryRow(`SELECT COUNT(*) FROM entries`).Scan(&count)
	if count != 6 {
		t.Fatal(count)
	}
}
