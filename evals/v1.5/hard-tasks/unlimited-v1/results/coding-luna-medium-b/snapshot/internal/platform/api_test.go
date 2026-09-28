package platform

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func TestLedgerHTTPFlow(t *testing.T) {
	db, err := Open(t.TempDir() + "/ledger.db")
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err = Initialize(db); err != nil {
		t.Fatal(err)
	}
	s := httptest.NewServer(&API{DB: db})
	defer s.Close()
	call := func(method, path, body, key string) (int, map[string]any) {
		req, _ := http.NewRequest(method, s.URL+path, strings.NewReader(body))
		req.Header.Set("X-Tenant", "tenant")
		if key != "" {
			req.Header.Set("Idempotency-Key", key)
		}
		res, e := http.DefaultClient.Do(req)
		if e != nil {
			t.Fatal(e)
		}
		defer res.Body.Close()
		var obj map[string]any
		if e = json.NewDecoder(res.Body).Decode(&obj); e != nil {
			t.Fatal(e)
		}
		return res.StatusCode, obj
	}
	if n, _ := call("POST", "/accounts", `{"name":"A","opening":50}`, "a"); n != 201 {
		t.Fatalf("create A: %d", n)
	}
	if n, _ := call("POST", "/accounts", `{"name":"B","opening":4}`, "b"); n != 201 {
		t.Fatalf("create B: %d", n)
	}
	status, created := call("POST", "/transfers", `{"from":"A","to":"B","amount":7}`, "move")
	if status != 201 {
		t.Fatalf("transfer: %d %#v", status, created)
	}
	if n, replay := call("POST", "/transfers", `{ "amount":7,"to":"B","from":"A"}`, "move"); n != 201 || replay["transfer"].(map[string]any)["id"] != created["transfer"].(map[string]any)["id"] {
		t.Fatalf("replay mismatch: %d %#v", n, replay)
	}
	if n, _ := call("POST", "/transfers", `{"from":"A","to":"B","amount":8}`, "move"); n != 409 {
		t.Fatalf("key conflict: %d", n)
	}
	if n, _ := call("POST", "/batches", `{"transfers":[{"from":"A","to":"B","amount":1},{"from":"B","to":"A","amount":999}]}`, "batch"); n != 409 {
		t.Fatalf("batch failure: %d", n)
	}
	if n, x := call("GET", "/summary", ``, ""); n != 200 || x["entry_count"].(float64) != 4 {
		t.Fatalf("atomic summary: %d %#v", n, x)
	}
	_, hold := call("POST", "/holds", `{"account":"A","amount":5}`, "hold")
	hid := hold["hold"].(map[string]any)["id"].(string)
	status, capture := call("POST", "/holds/"+hid+"/capture", `{"to":"B"}`, "capture")
	if status != 200 {
		t.Fatalf("capture: %d %#v", status, capture)
	}
	tid := capture["transfer"].(map[string]any)["id"].(string)
	if n, _ := call("POST", "/transfers/"+tid+"/reverse", `{}`, "reverse"); n != 200 {
		t.Fatalf("reverse: %d", n)
	}
	if n, x := call("GET", "/summary", ``, ""); n != 200 || x["totals"].(map[string]any)["balance"].(float64) != 54 || x["totals"].(map[string]any)["reserved"].(float64) != 0 {
		t.Fatalf("final summary: %d %#v", n, x)
	}
	if n, _ := call("POST", "/holds/"+hid+"/release", `{}`, "terminal"); n != 409 {
		t.Fatalf("terminal hold: %d", n)
	}
	if n, _ := call("GET", "/entries?limit=2", ``, ""); n != 200 {
		t.Fatalf("entries: %d", n)
	}
}

func TestConcurrentIdempotentWriters(t *testing.T) {
	db, err := Open(t.TempDir() + "/ledger.db")
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err = Initialize(db); err != nil {
		t.Fatal(err)
	}
	s := httptest.NewServer(&API{DB: db})
	defer s.Close()
	for i, body := range []string{`{"name":"A","opening":100}`, `{"name":"B","opening":0}`} {
		req, _ := http.NewRequest("POST", s.URL+"/accounts", strings.NewReader(body))
		req.Header.Set("X-Tenant", "t")
		req.Header.Set("Idempotency-Key", []string{"seed-a", "seed-b"}[i])
		res, e := http.DefaultClient.Do(req)
		if e != nil {
			t.Fatal(e)
		}
		res.Body.Close()
		if res.StatusCode != 201 {
			t.Fatalf("seed status: %d", res.StatusCode)
		}
	}
	var wg sync.WaitGroup
	statuses := make(chan int, 16)
	ids := make(chan string, 16)
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			req, _ := http.NewRequest("POST", s.URL+"/transfers", strings.NewReader(`{"from":"A","to":"B","amount":7}`))
			req.Header.Set("X-Tenant", "t")
			req.Header.Set("Idempotency-Key", "shared")
			res, e := http.DefaultClient.Do(req)
			if e != nil {
				statuses <- 0
				return
			}
			defer res.Body.Close()
			var x map[string]any
			_ = json.NewDecoder(res.Body).Decode(&x)
			statuses <- res.StatusCode
			if tr, ok := x["transfer"].(map[string]any); ok {
				ids <- tr["id"].(string)
			}
		}()
	}
	wg.Wait()
	close(statuses)
	close(ids)
	for s := range statuses {
		if s != 201 {
			t.Fatalf("concurrent status %d", s)
		}
	}
	first := ""
	for x := range ids {
		if first == "" {
			first = x
		} else if x != first {
			t.Fatalf("different replay IDs %s and %s", first, x)
		}
	}
	var n int
	if err = db.QueryRow(`SELECT COUNT(*) FROM entries WHERE tenant='t' AND kind='transfer'`).Scan(&n); err != nil || n != 2 {
		t.Fatalf("concurrent effects: %d (%v)", n, err)
	}
}
