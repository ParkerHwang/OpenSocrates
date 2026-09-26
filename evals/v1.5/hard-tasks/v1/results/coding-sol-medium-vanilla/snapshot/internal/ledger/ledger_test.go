package ledger

import (
	"auditledger/internal/platform"
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func call(t *testing.T, l *DB, method, path, tenant, key string, body any) (int, map[string]any) {
	t.Helper()
	var data []byte
	if body != nil {
		var e error
		data, e = json.Marshal(body)
		if e != nil {
			t.Fatal(e)
		}
	}
	r := httptest.NewRequest(method, path, bytes.NewReader(data))
	r.Header.Set("X-Tenant", tenant)
	if key != "" {
		r.Header.Set("Idempotency-Key", key)
	}
	w := httptest.NewRecorder()
	l.ServeHTTP(w, r)
	var result map[string]any
	if e := json.Unmarshal(w.Body.Bytes(), &result); e != nil {
		t.Fatal(e, w.Body.String())
	}
	return w.Code, result
}
func requireStatus(t *testing.T, got, want int, result map[string]any) {
	t.Helper()
	if got != want {
		t.Fatalf("status %d, want %d: %v", got, want, result)
	}
}
func TestLedgerReplayBatchAndHistory(t *testing.T) {
	path := filepath.Join(t.TempDir(), "ledger.sqlite")
	l, e := Open(path)
	if e != nil {
		t.Fatal(e)
	}
	for i, x := range []struct {
		name    string
		opening int
	}{{"A", 100}, {"B", 0}} {
		status, v := call(t, l, "POST", "/accounts", "tenant", string(rune('a'+i)), map[string]any{"name": x.name, "opening": x.opening})
		requireStatus(t, status, 201, v)
	}
	batch := map[string]any{"transfers": []any{map[string]any{"from": "A", "to": "B", "amount": 20, "from_version": 1, "to_version": 1}, map[string]any{"from": "B", "to": "A", "amount": 5, "from_version": 2, "to_version": 2}}}
	status, first := call(t, l, "POST", "/batches", "tenant", "batch", batch)
	requireStatus(t, status, 201, first)
	accounts := first["accounts"].([]any)
	if accounts[0].(map[string]any)["balance"] != float64(85) || accounts[0].(map[string]any)["version"] != float64(3) {
		t.Fatal(first)
	}
	status, replay := call(t, l, "POST", "/batches", "tenant", "batch", batch)
	requireStatus(t, status, 201, replay)
	if !bytes.Equal(mustMarshal(first), mustMarshal(replay)) {
		t.Fatalf("replay changed: %v %v", first, replay)
	}
	status, _ = call(t, l, "POST", "/batches", "tenant", "batch", map[string]any{"transfers": []any{map[string]any{"from": "A", "to": "B", "amount": 1}}})
	requireStatus(t, status, 409, nil)
	failed := map[string]any{"transfers": []any{map[string]any{"from": "A", "to": "B", "amount": 1}, map[string]any{"from": "B", "to": "A", "amount": 1, "from_version": 1}}}
	status, v := call(t, l, "POST", "/batches", "tenant", "failed", failed)
	requireStatus(t, status, 409, v)
	status, v = call(t, l, "GET", "/summary", "tenant", "", nil)
	requireStatus(t, status, 200, v)
	if v["entry_count"] != float64(6) {
		t.Fatal(v)
	}
	status, v = call(t, l, "POST", "/holds", "tenant", "failed", map[string]any{"account": "A", "amount": 10})
	requireStatus(t, status, 201, v)
	status, historical := call(t, l, "GET", "/summary?snapshot=6", "tenant", "", nil)
	requireStatus(t, status, 200, historical)
	if historical["totals"].(map[string]any)["reserved"] != float64(0) {
		t.Fatal(historical)
	}
	l.Close()
	l, e = Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer l.Close()
	status, replay = call(t, l, "POST", "/batches", "tenant", "batch", batch)
	requireStatus(t, status, 201, replay)
	if !bytes.Equal(mustMarshal(first), mustMarshal(replay)) {
		t.Fatal("restart replay changed")
	}
	status, v = call(t, l, "GET", "/entries?after=0&limit=2&snapshot=6", "tenant", "", nil)
	requireStatus(t, status, 200, v)
	if v["has_more"] != true || len(v["entries"].([]any)) != 2 {
		t.Fatal(v)
	}
	status, v = call(t, l, "GET", "/accounts/A", "other", "", nil)
	requireStatus(t, status, 404, v)
}
func mustMarshal(v any) []byte { b, _ := json.Marshal(v); return b }

var _ http.Handler = (*DB)(nil)

func TestLegacyMigrationPreservesRows(t *testing.T) {
	path := filepath.Join(t.TempDir(), "legacy.sqlite")
	raw, e := platform.Open(path)
	if e != nil {
		t.Fatal(e)
	}
	stmts := []string{
		`CREATE TABLE legacy_accounts(tenant TEXT,name TEXT,balance INTEGER,PRIMARY KEY(tenant,name))`,
		`CREATE TABLE legacy_movements(id INTEGER PRIMARY KEY,tenant TEXT,source TEXT,target TEXT,units INTEGER)`,
		`CREATE TABLE legacy_notes(key TEXT PRIMARY KEY,value TEXT)`,
		`INSERT INTO legacy_accounts VALUES('x','A',7),('x','B',13)`,
		`INSERT INTO legacy_movements VALUES(9,'x','A','B',3)`,
		`INSERT INTO legacy_notes VALUES('unicode','保全
line two')`,
		`PRAGMA user_version=1`,
	}
	for _, s := range stmts {
		if _, e = raw.Exec(s); e != nil {
			t.Fatal(e)
		}
	}
	raw.Close()
	l, e := Open(path)
	if e != nil {
		t.Fatal(e)
	}
	status, v := call(t, l, "GET", "/entries", "x", "", nil)
	requireStatus(t, status, 200, v)
	entries := v["entries"].([]any)
	if len(entries) != 4 || entries[0].(map[string]any)["balance_delta"] != float64(10) || entries[1].(map[string]any)["balance_delta"] != float64(10) || entries[2].(map[string]any)["legacy_id"] != float64(9) {
		t.Fatal(v)
	}
	status, v = call(t, l, "GET", "/summary", "x", "", nil)
	requireStatus(t, status, 200, v)
	if v["totals"].(map[string]any)["balance"] != float64(20) {
		t.Fatal(v)
	}
	var note string
	if e = l.QueryRow(`SELECT value FROM legacy_notes WHERE key='unicode'`).Scan(&note); e != nil || note != "保全\nline two" {
		t.Fatal(e, note)
	}
	l.Close()
	l, e = Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer l.Close()
	status, v = call(t, l, "GET", "/entries", "x", "", nil)
	requireStatus(t, status, 200, v)
	if len(v["entries"].([]any)) != 4 {
		t.Fatal("migration repeated")
	}
}
