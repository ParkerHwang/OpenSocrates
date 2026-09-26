package queue

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"
	"sync"
	"testing"
)

func TestDurableQueue(t *testing.T) {
	path := filepath.Join(t.TempDir(), "queue.sqlite")
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
	inputs := []Input{{Queue: "mail", Payload: json.RawMessage(`{"n":1}`), MaxAttempts: 2}}
	command := `same`
	var wg sync.WaitGroup
	ids := make(chan string, 20)
	errs := make(chan error, 20)
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			s := a
			if i%2 == 1 {
				s = b
			}
			jobs, _, e := s.Submit(ctx, "tenant", "jobs", "key", command, inputs, 1000)
			if e != nil {
				errs <- e
				return
			}
			ids <- jobs[0].ID
		}(i)
	}
	wg.Wait()
	close(ids)
	close(errs)
	for e := range errs {
		t.Error(e)
	}
	var id string
	for x := range ids {
		if id == "" {
			id = x
		} else if id != x {
			t.Fatalf("duplicate jobs: %s %s", id, x)
		}
	}
	if id == "" {
		t.Fatal("no job")
	}
	if _, _, e := b.Submit(ctx, "tenant", "jobs", "key", "changed", inputs, 1000); !errors.Is(e, ErrIdem) {
		t.Fatalf("conflict: %v", e)
	}
	if _, e := b.Get(ctx, "other", id); !errors.Is(e, ErrNotFound) {
		t.Fatalf("isolation: %v", e)
	}
	j, tok, e := a.Claim(ctx, "tenant", "mail", 1000, 100)
	if e != nil || j == nil || j.ID != id || j.Attempts != 1 {
		t.Fatalf("claim: %+v %v", j, e)
	}
	if _, e := b.Heartbeat(ctx, "tenant", id, *tok, 1100, 100); !errors.Is(e, ErrLease) {
		t.Fatalf("deadline equality: %v", e)
	}
	j, tok2, e := b.Claim(ctx, "tenant", "mail", 1100, 100)
	if e != nil || j == nil || j.Attempts != 2 || *tok2 == *tok {
		t.Fatalf("reclaim: %+v %v", j, e)
	}
	if _, e := a.Complete(ctx, "tenant", id, *tok, json.RawMessage(`{}`), 1100); !errors.Is(e, ErrLease) {
		t.Fatalf("old token: %v", e)
	}
	updated, e := b.Heartbeat(ctx, "tenant", id, *tok2, 1199, 100)
	if e != nil || *updated.LeaseUntilMS != 1299 {
		t.Fatalf("heartbeat: %+v %v", updated, e)
	}
	result := json.RawMessage(`{"ok":true}`)
	updated, e = a.Complete(ctx, "tenant", id, *tok2, result, 1200)
	if e != nil || updated.State != "completed" {
		t.Fatalf("complete: %+v %v", updated, e)
	}
	if _, e := b.Complete(ctx, "tenant", id, *tok2, result, 5000); e != nil {
		t.Fatalf("repeat complete: %v", e)
	}
	if _, e := b.Complete(ctx, "tenant", id, *tok2, json.RawMessage(`{"ok":false}`), 5000); !errors.Is(e, ErrLease) {
		t.Fatalf("changed result: %v", e)
	}
	if e := a.Close(); e != nil {
		t.Fatal(e)
	}
	c, e := Open(path)
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	updated, e = c.Get(ctx, "tenant", id)
	if e != nil || updated.State != "completed" {
		t.Fatalf("restart: %+v %v", updated, e)
	}
	stats, e := c.Stats(ctx, "tenant", "")
	if e != nil || stats["total"] != 1 || stats["completed"] != 1 {
		t.Fatal(stats, e)
	}
}

func TestBatchOrderingAndExpiry(t *testing.T) {
	s, e := Open(filepath.Join(t.TempDir(), "queue.sqlite"))
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	ctx := context.Background()
	inputs := []Input{{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 1}, {Queue: "q", Payload: json.RawMessage(`{"n":2}`), MaxAttempts: 2}}
	jobs, _, e := s.Submit(ctx, "t", "jobs/batch", "batch", "command", inputs, 1000)
	if e != nil {
		t.Fatal(e)
	}
	if len(jobs) != 2 || jobs[0].CreatedSeq >= jobs[1].CreatedSeq {
		t.Fatal(jobs)
	}
	j, tok, e := s.Claim(ctx, "t", "q", 1000, 10)
	if e != nil || j.ID != jobs[0].ID {
		t.Fatal(j, e)
	}
	if _, e := s.Fail(ctx, "t", j.ID, *tok, "failed", 1001); e != nil {
		t.Fatal(e)
	}
	if _, e := s.Heartbeat(ctx, "t", j.ID, *tok, 1001, 10); !errors.Is(e, ErrLease) {
		t.Fatal(e)
	}
	j, tok, e = s.Claim(ctx, "t", "q", 1001, 10)
	if e != nil || j.ID != jobs[1].ID {
		t.Fatal(j, e)
	}
	j2, tok2, e := s.Claim(ctx, "t", "q", 1011, 10)
	if e != nil || j2 == nil || *tok2 == *tok || j2.Attempts != 2 {
		t.Fatal(j2, e)
	}
	j3, _, e := s.Claim(ctx, "t", "q", 1021, 10)
	if e != nil || j3 != nil {
		t.Fatal(j3, e)
	}
	stored, e := s.Get(ctx, "t", jobs[1].ID)
	if e != nil || stored.State != "dead" || *stored.LastError != "lease_expired" {
		t.Fatal(stored, e)
	}
	if _, e := s.Get(ctx, "other", jobs[0].ID); !errors.Is(e, ErrNotFound) {
		t.Fatal(fmt.Sprint(e))
	}
}

func TestConcurrentClaimsAcrossHandles(t *testing.T) {
	path := filepath.Join(t.TempDir(), "queue.sqlite")
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
	_, _, e = a.Submit(ctx, "t", "jobs", "one", "command", []Input{{Queue: "q", Payload: json.RawMessage(`{}`), MaxAttempts: 3}}, 1000)
	if e != nil {
		t.Fatal(e)
	}
	start := make(chan struct{})
	var wg sync.WaitGroup
	claimed := make(chan string, 2)
	errs := make(chan error, 2)
	for _, store := range []*Store{a, b} {
		wg.Add(1)
		go func(s *Store) {
			defer wg.Done()
			<-start
			job, _, err := s.Claim(ctx, "t", "q", 1000, 100)
			if err != nil {
				errs <- err
				return
			}
			if job != nil {
				claimed <- job.ID
			}
		}(store)
	}
	close(start)
	wg.Wait()
	close(claimed)
	close(errs)
	for err := range errs {
		t.Error(err)
	}
	count := 0
	for range claimed {
		count++
	}
	if count != 1 {
		t.Fatalf("got %d claims for one job", count)
	}
}
