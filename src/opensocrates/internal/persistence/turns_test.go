package persistence

import (
	"bytes"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

func testTurn(t *testing.T, store *TurnStore, token string) map[string]any {
	t.Helper()
	tag, e := store.TokenTag(token)
	if e != nil {
		t.Fatal(e)
	}
	return map[string]any{"schema": "opensocrates.ephemeral-turn-state/1.0.0", "token_tag": tag, "host_session_key": "sha256:" + strings.Repeat("1", 64), "host_turn_key": nil, "host": "codex_cli", "issued_at": "2026-10-12T00:00:00.000Z", "expires_at": "2026-10-12T06:00:00.000Z", "recording_eligible": false, "onboarding_disclosure_turn": false, "task_id": nil, "judgment_id": nil, "task_state": "new", "participation": nil, "effective_rigor": "together", "primary_method": nil, "secondary_method": nil, "repair_count": contracts.Number(0), "accepted_controls": []any{}, "observation_tags": []any{}}
}
func TestTurnStoreContentFreeAndCAS(t *testing.T) {
	root := t.TempDir()
	store, e := NewTurnStore(root)
	if e != nil {
		t.Fatal(e)
	}
	token := strings.Repeat("A", 43)
	state := testTurn(t, store, token)
	if e = store.Issue(state); e != nil {
		t.Fatal(e)
	}
	next, _ := domain.Normalize(state)
	next["task_state"] = "framing"
	if e = store.CompareAndSwap(state, next); e != nil {
		t.Fatal(e)
	}
	if e = store.CompareAndSwap(state, next); e == nil {
		t.Fatal("stale compare-and-swap accepted")
	}
	loaded, e := store.Load(token)
	if e != nil || loaded["task_state"] != "framing" {
		t.Fatal(e)
	}
	if bad, _ := store.Load(strings.Repeat("B", 43)); bad != nil {
		t.Fatal("foreign token accepted")
	}
	_ = filepath.Walk(root, func(path string, info os.FileInfo, e error) error {
		if e == nil && !info.IsDir() {
			raw, _ := os.ReadFile(path)
			if bytes.Contains(raw, []byte(token)) {
				t.Fatal("raw token reached disk")
			}
		}
		return nil
	})
	if e = store.Delete(next); e != nil {
		t.Fatal(e)
	}
}
func TestTurnStoreConcurrentMutation(t *testing.T) {
	store, e := NewTurnStore(t.TempDir())
	if e != nil {
		t.Fatal(e)
	}
	token := strings.Repeat("A", 43)
	if e = store.Issue(testTurn(t, store, token)); e != nil {
		t.Fatal(e)
	}
	var wg sync.WaitGroup
	errs := make(chan error, 4)
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			errs <- store.WithTurn(token, func(state map[string]any) (map[string]any, bool, error) {
				n, _ := contracts.Int(state["repair_count"])
				state["repair_count"] = contracts.Number(n)
				observations := state["observation_tags"].([]any)
				tag := "sha256:" + strings.Repeat(string(rune('a'+len(observations))), 64)
				return state, false, domain.AppendObservationTag(state, tag)
			})
		}()
	}
	wg.Wait()
	close(errs)
	for e := range errs {
		if e != nil {
			t.Fatal(e)
		}
	}
	state, e := store.Load(token)
	if e != nil || len(state["observation_tags"].([]any)) != 4 {
		t.Fatal("lost concurrent mutation", e)
	}
}
func TestTurnStatePrivacyAndUnknownFields(t *testing.T) {
	store, e := NewTurnStore(t.TempDir())
	if e != nil {
		t.Fatal(e)
	}
	state := testTurn(t, store, strings.Repeat("A", 43))
	state["transcript"] = "private"
	if e = store.Issue(state); e == nil {
		t.Fatal("unknown content accepted")
	}
	delete(state, "transcript")
	state["expires_at"] = "2026-10-12T06:00:00.001Z"
	if e = store.Issue(state); e == nil {
		t.Fatal("overlong lifetime accepted")
	}
}
func TestExistingTurnStoreDoesNotInitialize(t *testing.T) {
	root := t.TempDir()
	if _, e := ExistingTurnStore(root); e == nil {
		t.Fatal("missing existing key accepted")
	}
	entries, _ := os.ReadDir(root)
	if len(entries) != 0 {
		t.Fatal("reader initialized installation")
	}
}
