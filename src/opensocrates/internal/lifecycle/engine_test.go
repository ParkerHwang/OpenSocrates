package lifecycle

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
)

func fixture(t *testing.T) (*Engine, string, string) {
	t.Helper()
	base := privateLifecycleTestDir(t)
	state := filepath.Join(base, "state")
	target := filepath.Join(base, "owned")
	source := filepath.Join(base, "candidate")
	for p, value := range map[string]string{target: "before", source: "after"} {
		if e := platform.AtomicWrite(p, []byte(value), 0600); e != nil {
			t.Fatal(e)
		}
	}
	return &Engine{StateDir: state, Registrations: map[string]registration.Adapter{}}, target, source
}
func TestTransactionCommitAndVerifiedRollback(t *testing.T) {
	e, target, source := fixture(t)
	before, err := Inspect(target)
	if err != nil {
		t.Fatal(err)
	}
	j, err := e.Execute(context.Background(), Plan{Action: "update", Host: "codex", Scope: "global", Mutations: []Mutation{{Target: target, Source: source, Expected: &before}}})
	if err != nil || j.Stage != "committed" {
		t.Fatalf("commit: %v %s", err, j.Stage)
	}
	b, err := platform.ReadFile(target, 100)
	if err != nil || string(b) != "after" {
		t.Fatal("activation not verified")
	}
	j, err = e.Recover(context.Background(), j.ID)
	if err != nil || j.Stage != "rolled-back" {
		t.Fatalf("recovery: %v %s", err, j.Stage)
	}
	b, err = platform.ReadFile(target, 100)
	if err != nil || string(b) != "before" {
		t.Fatal("rollback bytes not restored")
	}
}
func TestChangedTargetAndBackupPreserved(t *testing.T) {
	for _, changeBackup := range []bool{false, true} {
		t.Run(map[bool]string{false: "target", true: "backup"}[changeBackup], func(t *testing.T) {
			e, target, source := fixture(t)
			before, _ := Inspect(target)
			j, err := e.Execute(context.Background(), Plan{Action: "update", Host: "codex", Mutations: []Mutation{{Target: target, Source: source, Expected: &before}}})
			if err != nil {
				t.Fatal(err)
			}
			modified := target
			if changeBackup {
				modified = j.Files[0].Backup
			}
			if err := platform.AtomicWrite(modified, []byte("foreign modification"), 0600); err != nil {
				t.Fatal(err)
			}
			_, err = e.Recover(context.Background(), j.ID)
			var category *diagnostics.Error
			if !errors.As(err, &category) || category.Code != diagnostics.RollbackIncomplete {
				t.Fatalf("expected bounded conflict: %v", err)
			}
			b, err := platform.ReadFile(modified, 100)
			if err != nil || string(b) != "foreign modification" {
				t.Fatal("modified bytes destroyed")
			}
			if _, err := os.Lstat(j.Files[0].Backup); err != nil {
				t.Fatal("recovery backup discarded")
			}
		})
	}
}
func TestForeignExistingMutationRefused(t *testing.T) {
	e, target, source := fixture(t)
	_, err := e.Execute(context.Background(), Plan{Action: "install", Mutations: []Mutation{{Target: target, Source: source}}})
	if err == nil {
		t.Fatal("foreign target accepted")
	}
	b, _ := platform.ReadFile(target, 100)
	if string(b) != "before" {
		t.Fatal("foreign bytes altered")
	}
}
func TestInterruptedRenameRecoveredFromActualHashes(t *testing.T) {
	e, target, source := fixture(t)
	before, _ := Inspect(target)
	after, _ := Inspect(source)
	id := NewID()
	stem := filepath.Join(filepath.Dir(target), ".opensocrates-"+id+"-"+filepath.Base(target))
	j := Journal{Schema: JournalSchema, ID: id, Stage: "applying", Files: []FileChange{{Target: target, Staged: stem + "-candidate", Backup: stem + "-backup", Before: before, After: after, Phase: "activate-intent"}}}
	if err := platform.Mkdir(e.StateDir); err != nil {
		t.Fatal(err)
	}
	if err := platform.Mkdir(filepath.Join(e.StateDir, "transactions")); err != nil {
		t.Fatal(err)
	}
	if err := e.save(&j); err != nil {
		t.Fatal(err)
	}
	if err := platform.Rename(target, j.Files[0].Backup); err != nil {
		t.Fatal(err)
	}
	if _, err := e.Recover(context.Background(), id); err != nil {
		t.Fatal(err)
	}
	b, _ := platform.ReadFile(target, 100)
	if string(b) != "before" {
		t.Fatal("interrupted update not restored")
	}
}
func TestNestedTargetsRejected(t *testing.T) {
	e, target, source := fixture(t)
	_, err := e.Execute(context.Background(), Plan{Mutations: []Mutation{{Target: target, Source: source}, {Target: filepath.Join(target, "nested"), Source: source}}})
	if err == nil {
		t.Fatal("nested mutation accepted")
	}
}
func TestLegacyLockExcludedAndNeverEvicted(t *testing.T) {
	e, _, _ := fixture(t)
	if err := platform.Mkdir(e.StateDir); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(e.StateDir, "lifecycle.lock")
	if err := platform.AtomicWrite(path, []byte(`{"pid":0,"startedAt":"2000-01-01T00:00:00Z"}`), 0600); err != nil {
		t.Fatal(err)
	}
	_, err := e.Lock()
	if err == nil {
		t.Fatal("legacy lock evicted")
	}
	if _, err := os.Lstat(path); err != nil {
		t.Fatal("existing lock discarded")
	}
}

func privateLifecycleTestDir(t *testing.T) string {
	t.Helper()
	base := filepath.Join(t.TempDir(), "private-fixture")
	if err := platform.Mkdir(base); err != nil {
		t.Fatal(err)
	}
	return base
}
