package queue

import (
	"database/sql"
	"path/filepath"
	"testing"

	"queueforge/internal/platform"
)

// Stage 1 fingerprints predate scheduling fields. Explicitly supplying one of
// those fields changes the command even when its value equals a version 2 default.
func TestMigratedIdempotencyRejectsExplicitSchedulingFields(t *testing.T) {
	path := filepath.Join(t.TempDir(), "stage1.sqlite")
	db, err := sql.Open(platform.SQLiteDriver, path)
	if err != nil {
		t.Fatal(err)
	}
	for _, q := range []string{
		`CREATE TABLE jobs (created_seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_at_ms INTEGER NOT NULL,available_at_ms INTEGER NOT NULL,lease_until_ms INTEGER,lease_token TEXT,last_error TEXT,result TEXT,completion_token TEXT)`,
		`CREATE TABLE idempotency (tenant TEXT NOT NULL,endpoint TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,ids TEXT NOT NULL,PRIMARY KEY(tenant,endpoint,key))`,
		`INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms) VALUES('old','t','q','{}','ready',0,3,100,100)`,
		`INSERT INTO idempotency(tenant,endpoint,key,fingerprint,ids) VALUES('t','/v1/jobs','key','{"queue":"q","payload":{},"max_attempts":3}','["old"]')`,
		`PRAGMA user_version=1`,
	} {
		if _, err := db.Exec(q); err != nil {
			t.Fatal(err)
		}
	}
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}
	s, err := New(path, func() (int64, error) { return 200, nil })
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	h := Handler{s}
	if code, r := call(t, h, "t", "POST", "/v1/jobs", "key", `{"queue":"q","payload":{}}`); code != 200 || !r.Replayed || r.Job.ID != "old" {
		t.Fatalf("original replay: %d %+v", code, r)
	}
	for _, body := range []string{
		`{"queue":"q","payload":{},"priority":0}`,
		`{"queue":"q","payload":{},"run_at_ms":0}`,
		`{"queue":"q","payload":{},"retry_base_ms":1000}`,
	} {
		if code, _ := call(t, h, "t", "POST", "/v1/jobs", "key", body); code != 409 {
			t.Fatalf("explicit scheduling field accepted: %s: %d", body, code)
		}
	}
}
