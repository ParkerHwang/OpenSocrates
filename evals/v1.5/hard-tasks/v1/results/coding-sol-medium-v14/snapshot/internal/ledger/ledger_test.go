package ledger_test

import (
	"auditledger/internal/ledger"
	"auditledger/internal/platform"
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestHTTPPostingAndSnapshots(t *testing.T) {
	db, e := platform.Open(filepath.Join(t.TempDir(), "ledger.db"))
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	app := &ledger.Ledger{DB: db}
	if e = app.Init(context.Background()); e != nil {
		t.Fatal(e)
	}
	serve := func(method, path, tenant, key, body string) (int, map[string]any) {
		t.Helper()
		req := httptest.NewRequest(method, path, bytes.NewBufferString(body))
		if tenant != "" {
			req.Header.Set("X-Tenant", tenant)
		}
		if key != "" {
			req.Header.Set("Idempotency-Key", key)
		}
		w := httptest.NewRecorder()
		app.ServeHTTP(w, req)
		out := map[string]any{}
		if e := json.Unmarshal(w.Body.Bytes(), &out); e != nil {
			t.Fatalf("response: %v: %s", e, w.Body.String())
		}
		return w.Code, out
	}
	must := func(status int, got int, v map[string]any) {
		t.Helper()
		if got != status {
			t.Fatalf("status %d, expected %d: %v", got, status, v)
		}
	}
	s, a := serve("POST", "/accounts", "t", "a", `{"name":"A","opening":100}`)
	must(201, s, a)
	s, b := serve("POST", "/accounts", "t", "b", `{"name":"B","opening":0}`)
	must(201, s, b)
	s, one := serve("POST", "/transfers", "t", "x", `{"from":"A","to":"B","amount":10,"from_version":1,"to_version":1}`)
	must(201, s, one)
	s, replay := serve("POST", "/transfers", "t", "x", `{"to_version":1,"amount":10,"to":"B","from_version":1,"from":"A"}`)
	must(201, s, replay)
	if !bytes.Equal(mustJSON(t, one), mustJSON(t, replay)) {
		t.Fatalf("replay changed: %v / %v", one, replay)
	}
	s, conflict := serve("POST", "/holds", "t", "x", `{"account":"A","amount":1}`)
	must(409, s, conflict)
	if code(conflict) != "idempotency_conflict" {
		t.Fatal(conflict)
	}
	s, invalid := serve("POST", "/transfers", "t", "bad", `{"from":"A","to":"B","amount":1,"from_version":null}`)
	must(400, s, invalid)
	s, stale := serve("POST", "/transfers", "t", "large-version", `{"from":"A","to":"B","amount":1,"from_version":999999999999999999999999999999}`)
	must(409, s, stale)
	if code(stale) != "version_conflict" {
		t.Fatal(stale)
	}
	s, batch := serve("POST", "/batches", "t", "batch", `{"transfers":[{"from":"A","to":"B","amount":1},{"from":"A","to":"B","amount":999}]}`)
	must(409, s, batch)
	if code(batch) != "insufficient" {
		t.Fatal(batch)
	}
	s, current := serve("GET", "/accounts/A", "t", "", "")
	must(200, s, current)
	if current["account"].(map[string]any)["balance"] != float64(90) {
		t.Fatal(current)
	}
	s, history := serve("GET", "/summary?snapshot=2", "t", "", "")
	must(200, s, history)
	if history["entry_count"] != float64(2) || history["totals"].(map[string]any)["balance"] != float64(100) {
		t.Fatal(history)
	}
	s, isolated := serve("GET", "/accounts/A", "other", "", "")
	must(404, s, isolated)
	s, entries := serve("GET", "/entries?limit=1", "t", "", "")
	must(200, s, entries)
	if entries["has_more"] != true || len(entries["entries"].([]any)) != 1 {
		t.Fatal(entries)
	}
	s, held := serve("POST", "/holds", "t", "hold", `{"account":"A","amount":20,"version":2}`)
	must(201, s, held)
	holdID := held["hold"].(map[string]any)["id"].(string)
	s, historicHold := serve("GET", "/summary?snapshot=5", "t", "", "")
	must(200, s, historicHold)
	if historicHold["totals"].(map[string]any)["reserved"] != float64(20) {
		t.Fatal(historicHold)
	}
	s, released := serve("POST", "/holds/"+holdID+"/release", "t", "release", `{"version":3}`)
	must(200, s, released)
	if released["account"].(map[string]any)["reserved"] != float64(0) {
		t.Fatal(released)
	}
	s, replayRelease := serve("POST", "/holds/"+holdID+"/release", "t", "release", `{"version":3}`)
	must(200, s, replayRelease)
	if !bytes.Equal(mustJSON(t, released), mustJSON(t, replayRelease)) {
		t.Fatal("release replay changed")
	}
	s, terminal := serve("POST", "/holds/"+holdID+"/release", "t", "another-release", `{}`)
	must(409, s, terminal)
	if code(terminal) != "terminal" {
		t.Fatal(terminal)
	}
}
func code(v map[string]any) string { return v["error"].(map[string]any)["code"].(string) }
func mustJSON(t *testing.T, v any) []byte {
	t.Helper()
	b, e := json.Marshal(v)
	if e != nil {
		t.Fatal(e)
	}
	return b
}

var _ http.Handler = (*ledger.Ledger)(nil)
