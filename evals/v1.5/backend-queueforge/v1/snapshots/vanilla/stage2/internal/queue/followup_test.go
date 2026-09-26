package queue

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"queueforge/internal/platform"
)

func TestSchedulingCapacityAndCancellation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "queue.sqlite")
	a, e := OpenWithLimits(path, 3, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := OpenWithLimits(path, 3, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	ctx := context.Background()
	mk := func(priority int, at, base int64) Input {
		return Input{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 3, Priority: priority, RunAtMS: at, RunAtSet: true, RetryBaseMS: base}
	}
	in := []Input{mk(0, 1000, 100), mk(10, 2000, 100), mk(0, 1000, 0)}
	jobs, _, e := a.Submit(ctx, "t", "jobs/batch", "a", "a", in, 1000)
	if e != nil {
		t.Fatal(e)
	}
	if _, _, e = b.Submit(ctx, "t", "jobs", "full", "full", in[:1], 1000); !errors.Is(e, ErrCapacity) {
		t.Fatalf("capacity: %v", e)
	}
	if replayed, was, e := b.Submit(ctx, "t", "jobs/batch", "a", "a", in, 1000); e != nil || !was || replayed[0].ID != jobs[0].ID {
		t.Fatalf("replay: %v %v", was, e)
	}
	j, tok, e := a.Claim(ctx, "t", "q", 1000, 10)
	if e != nil || j == nil || j.ID != jobs[0].ID {
		t.Fatalf("first claim: %v %v", j, e)
	}
	j2, _, e := b.Claim(ctx, "t", "q", 1000, 10)
	if e != nil || j2 != nil {
		t.Fatalf("inflight: %v %v", j2, e)
	}
	if _, e = a.Fail(ctx, "t", j.ID, *tok, "retry", 1001); e != nil {
		t.Fatal(e)
	}
	j, _, e = b.Claim(ctx, "t", "q", 1001, 10)
	if e != nil || j == nil || j.ID != jobs[2].ID {
		t.Fatalf("delayed retry: %v %v", j, e)
	}
	if _, e = b.Cancel(ctx, "t", j.ID); e != nil {
		t.Fatal(e)
	}
	if _, e = b.Cancel(ctx, "t", j.ID); e != nil {
		t.Fatal(e)
	}
	j, _, e = a.Claim(ctx, "t", "q", 1079, 10)
	if e != nil || j != nil {
		t.Fatalf("early retry: %v %v", j, e)
	}
	j, _, e = a.Claim(ctx, "t", "q", 1101, 10)
	if e != nil || j == nil || j.ID != jobs[0].ID {
		t.Fatalf("retry boundary: %v %v", j, e)
	}
	if _, e = a.Cancel(ctx, "t", j.ID); e != nil {
		t.Fatal(e)
	}
	j, _, e = b.Claim(ctx, "t", "q", 2000, 10)
	if e != nil || j == nil || j.ID != jobs[1].ID {
		t.Fatalf("future priority: %v %v", j, e)
	}
	if _, e = b.Cancel(ctx, "t", j.ID); e != nil {
		t.Fatal(e)
	}
	counts, e := a.Stats(ctx, "t", "")
	if e != nil || counts["cancelled"] != 3 || counts["total"] != 3 {
		t.Fatalf("stats: %v %v", counts, e)
	}
}

func TestVersionOneMigrationAndFutureGuard(t *testing.T) {
	path := filepath.Join(t.TempDir(), "legacy.sqlite")
	db, e := sql.Open(platform.SQLiteDriver, path)
	if e != nil {
		t.Fatal(e)
	}
	for _, q := range []string{`CREATE TABLE jobs (seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,tenant TEXT NOT NULL,queue TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,created_at_ms INTEGER NOT NULL,available_at_ms INTEGER NOT NULL,lease_until_ms INTEGER,lease_token TEXT,completed_token TEXT,last_error TEXT,result TEXT)`,
		`CREATE TABLE idempotency (tenant TEXT NOT NULL,endpoint TEXT NOT NULL,key TEXT NOT NULL,command TEXT NOT NULL,ids TEXT NOT NULL,PRIMARY KEY(tenant,endpoint,key))`,
		`INSERT INTO jobs(id,tenant,queue,payload,state,attempts,max_attempts,created_at_ms,available_at_ms,lease_until_ms,lease_token) VALUES('legacy','t','q','{}','leased',1,3,1000,1000,1100,'old-token')`,
		`INSERT INTO idempotency VALUES('t','jobs','old','[{"queue":"q","payload":{},"max_attempts":3}]','["legacy"]')`,
		`PRAGMA user_version=1`} {
		if _, e = db.Exec(q); e != nil {
			t.Fatal(e)
		}
	}
	db.Close()
	a, e := Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	ctx := context.Background()
	in := []Input{{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 3, RetryBaseMS: 1000}}
	got, replay, e := b.Submit(ctx, "t", "jobs", "old", `[{"queue":"q","payload":{},"max_attempts":3,"priority":0,"retry_base_ms":1000}]`, in, 1050)
	if e != nil || !replay || got[0].ID != "legacy" || got[0].RetryBaseMS != 0 {
		t.Fatalf("legacy replay: %v %v", got, e)
	}
	if _, e = a.Heartbeat(ctx, "t", "legacy", "old-token", 1050, 100); e != nil {
		t.Fatal(e)
	}
	if _, e = a.Complete(ctx, "t", "legacy", "old-token", json.RawMessage(`{}`), 1051); e != nil {
		t.Fatal(e)
	}
	if _, e = a.Cancel(ctx, "t", "legacy"); !errors.Is(e, ErrTransition) {
		t.Fatalf("terminal cancel: %v", e)
	}
}

func TestConcurrentAdmissionAndBatchRollback(t *testing.T) {
	path := filepath.Join(t.TempDir(), "queue.sqlite")
	a, e := OpenWithLimits(path, 1, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := OpenWithLimits(path, 1, 1)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	ctx := context.Background()
	input := []Input{{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 3, RetryBaseMS: 1000}}
	results := make(chan error, 2)
	go func() { _, _, e := a.Submit(ctx, "t", "jobs", "a", "a", input, 1000); results <- e }()
	go func() { _, _, e := b.Submit(ctx, "t", "jobs", "b", "b", input, 1000); results <- e }()
	x, y := <-results, <-results
	if (x == nil) == (y == nil) || (x != nil && !errors.Is(x, ErrCapacity)) || (y != nil && !errors.Is(y, ErrCapacity)) {
		t.Fatalf("admission: %v %v", x, y)
	}
	counts, e := a.Stats(ctx, "t", "")
	if e != nil || counts["total"] != 1 {
		t.Fatalf("total: %v %v", counts, e)
	}
	// A failure during the second insert must roll back both the first insert and key.
	c, e := OpenWithLimits(filepath.Join(t.TempDir(), "rollback.sqlite"), 10, 10)
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	if _, e = c.db.Exec(`CREATE TRIGGER reject_second BEFORE INSERT ON jobs WHEN NEW.payload='{"reject":true}' BEGIN SELECT RAISE(ABORT,'reject'); END`); e != nil {
		t.Fatal(e)
	}
	batch := []Input{input[0], {Queue: "q", Payload: json.RawMessage(`{"reject":true}`), MaxAttempts: 3}}
	if _, _, e = c.Submit(ctx, "t", "jobs/batch", "batch", "batch", batch, 1000); e == nil {
		t.Fatal("expected insert failure")
	}
	counts, e = c.Stats(ctx, "t", "")
	if e != nil || counts["total"] != 0 {
		t.Fatalf("partial batch: %v %v", counts, e)
	}
	if _, _, e = c.Submit(ctx, "t", "jobs/batch", "batch", "batch", input, 1000); e != nil {
		t.Fatalf("idempotency key survived rollback: %v", e)
	}
}

func TestExpiryBackoffFromDeadline(t *testing.T) {
	s, e := Open(filepath.Join(t.TempDir(), "queue.sqlite"))
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	ctx := context.Background()
	in := []Input{{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 3, RetryBaseMS: 20}}
	jobs, _, e := s.Submit(ctx, "t", "jobs", "key", "key", in, 1000)
	if e != nil {
		t.Fatal(e)
	}
	j, _, e := s.Claim(ctx, "t", "q", 1000, 10)
	if e != nil || j == nil {
		t.Fatalf("claim: %v", e)
	}
	j, _, e = s.Claim(ctx, "t", "q", 1029, 10)
	if e != nil || j != nil {
		t.Fatalf("early expiry retry: %v %v", j, e)
	}
	stored, e := s.Get(ctx, "t", jobs[0].ID)
	if e != nil || stored.AvailableAtMS != 1030 || stored.State != "ready" {
		t.Fatalf("deadline backoff: %v %v", stored, e)
	}
	j, _, e = s.Claim(ctx, "t", "q", 1030, 10)
	if e != nil || j == nil || j.Attempts != 2 {
		t.Fatalf("retry: %v %v", j, e)
	}
	j, _, e = s.Claim(ctx, "t", "q", 1079, 10)
	if e != nil || j != nil {
		t.Fatalf("second expiry wait: %v %v", j, e)
	}
	stored, e = s.Get(ctx, "t", jobs[0].ID)
	if e != nil || stored.AvailableAtMS != 1080 {
		t.Fatalf("second deadline backoff: %v %v", stored, e)
	}
}

func TestFutureSchemaDoesNotChangeFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "future.sqlite")
	db, e := sql.Open(platform.SQLiteDriver, path)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = db.Exec("PRAGMA user_version=9"); e != nil {
		t.Fatal(e)
	}
	db.Close()
	before, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	if s, e := Open(path); e == nil {
		s.Close()
		t.Fatal("future version opened")
	}
	after, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.Equal(before, after) {
		t.Fatal("future database bytes changed")
	}
}
