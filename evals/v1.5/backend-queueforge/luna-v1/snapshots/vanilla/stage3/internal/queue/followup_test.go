package queue

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	_ "queueforge/internal/platform"
	"sync"
	"testing"
)

func TestSubmissionValidationDefaultsAndAtomicBatch(t *testing.T) {
	s, err := Open(filepath.Join(t.TempDir(), "queue.sqlite"), RealClock{})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	h := API{S: s}
	request := func(body string) int {
		r := httptest.NewRequest(http.MethodPost, "/v1/jobs", bytes.NewBufferString(body))
		r.Header.Set("X-Tenant-ID", "tenant")
		r.Header.Set("Idempotency-Key", "key-"+body)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		return w.Code
	}
	if got := request(`{"queue":"mail","payload":{},"max_attempts":0}`); got != http.StatusBadRequest {
		t.Fatalf("explicit zero max_attempts status = %d, want 400", got)
	}
	if got := request(`{"queue":"mail","payload":{}}`); got != http.StatusCreated {
		t.Fatalf("omitted max_attempts status = %d, want 201", got)
	}
	batch := httptest.NewRequest(http.MethodPost, "/v1/jobs/batch", bytes.NewBufferString(`{"jobs":[{"queue":"mail","payload":{}},{"queue":"mail","payload":{},"max_attempts":0}]}`))
	batch.Header.Set("X-Tenant-ID", "tenant")
	batch.Header.Set("Idempotency-Key", "invalid-batch")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, batch)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("invalid batch status = %d, want 400", w.Code)
	}
	stats, err := s.Stats(context.Background(), "tenant", "")
	if err != nil {
		t.Fatal(err)
	}
	if stats["total"] != 1 {
		t.Fatalf("invalid batch left side effects: total=%d, want 1", stats["total"])
	}
}

func TestV1ReplayUsesLegacyRetryDefault(t *testing.T) {
	path := filepath.Join(t.TempDir(), "v1.sqlite")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	_, err = db.Exec(`CREATE TABLE jobs(id TEXT NOT NULL UNIQUE,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload BLOB NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_seq INTEGER PRIMARY KEY AUTOINCREMENT,created_at_ms INTEGER NOT NULL,available_at_ms INTEGER NOT NULL,lease_until_ms INTEGER,lease_token TEXT,last_error TEXT,result BLOB,completed_token TEXT,completed_result BLOB);
CREATE TABLE idem(tenant TEXT,endpoint TEXT,key TEXT,input BLOB,ids BLOB,PRIMARY KEY(tenant,endpoint,key));
PRAGMA user_version=1;`)
	if err != nil {
		t.Fatal(err)
	}
	old := []map[string]any{{"queue": "mail", "payload": map[string]any{"n": 1}, "max_attempts": 3}}
	input, _ := json.Marshal(old)
	ids, _ := json.Marshal([]string{"legacy-job"})
	_, err = db.Exec(`INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms) VALUES('legacy-job','tenant','mail','{"n":1}','ready',0,3,100,100);
INSERT INTO idem(tenant,endpoint,key,input,ids) VALUES('tenant','jobs','legacy-key',?,?)`, input, ids)
	if err != nil {
		db.Close()
		t.Fatal(err)
	}
	if err = db.Close(); err != nil {
		t.Fatal(err)
	}
	s, err := Open(path, RealClock{})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	_, _, err = s.Submit(context.Background(), "tenant", "jobs", "legacy-key", []Input{{Queue: "mail", Payload: []byte(`{"n":1}`), Max: 3, Priority: 0, RunAt: 0, RetryBase: 1000}})
	if err != ErrIdempotency {
		t.Fatalf("v1 replay with changed retry default error=%v, want conflict", err)
	}
}

func TestSharedDatabaseContentionAcrossStores(t *testing.T) {
	path := filepath.Join(t.TempDir(), "shared.sqlite")
	a, err := Open(path, RealClock{})
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := Open(path, RealClock{})
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	stores := []*Store{a, b}
	var wg sync.WaitGroup
	errs := make(chan error, 20)
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			_, _, e := stores[i%len(stores)].Submit(context.Background(), "tenant", "jobs", "key-"+newID(), []Input{{Queue: "mail", Payload: []byte(`{}`), Max: 3, RetryBase: 1000}})
			if e != nil {
				errs <- e
			}
		}(i)
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Errorf("shared database submission: %v", err)
	}
	stats, err := a.Stats(context.Background(), "tenant", "")
	if err != nil {
		t.Fatal(err)
	}
	if stats["total"] != 20 {
		t.Fatalf("shared database total=%d, want 20", stats["total"])
	}
}
