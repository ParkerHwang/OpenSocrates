package lifecycle

import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
)

// This fixture deliberately exits without deferred lock cleanup. It runs in
// the native test binary on both macOS ARM64 and Windows x64, not a shell shim.
func TestLifecycleCrashFixtureChild(t *testing.T) {
	mode := os.Getenv("OPENSOCRATES_TEST_LIFECYCLE_CRASH")
	if mode == "" {
		return
	}
	root := os.Getenv("OPENSOCRATES_TEST_LIFECYCLE_DIR")
	engine := &Engine{StateDir: filepath.Join(root, "state"), Registrations: map[string]registration.Adapter{}}
	if mode == "apply" {
		calls := 0
		engine.Fault = func(stage string) error {
			if stage == "applying" {
				calls++
				if calls == 3 {
					os.Exit(79)
				}
			}
			return nil
		}
		target := filepath.Join(root, "owned")
		before, e := Inspect(target)
		if e != nil {
			os.Exit(81)
		}
		_, e = engine.Execute(context.Background(), Plan{Action: "update", Host: "codex", Scope: "global", Mutations: []Mutation{{Target: target, Source: filepath.Join(root, "candidate"), Expected: &before}}})
		if e != nil {
			os.Exit(82)
		}
		os.Exit(83)
	}
	if mode == "recover" {
		engine.Fault = func(stage string) error {
			if stage == "rolling-back" {
				os.Exit(79)
			}
			return nil
		}
		if _, e := engine.Recover(context.Background(), os.Getenv("OPENSOCRATES_TEST_LIFECYCLE_ID")); e != nil {
			os.Exit(84)
		}
		os.Exit(85)
	}
	os.Exit(86)
}
func crashChild(t *testing.T, root, mode, id string) {
	t.Helper()
	cmd := exec.Command(os.Args[0], "-test.run=^TestLifecycleCrashFixtureChild$")
	cmd.Env = append(os.Environ(), "OPENSOCRATES_TEST_LIFECYCLE_CRASH="+mode, "OPENSOCRATES_TEST_LIFECYCLE_DIR="+root, "OPENSOCRATES_TEST_LIFECYCLE_ID="+id)
	err := cmd.Run()
	exit, ok := err.(*exec.ExitError)
	if !ok || exit.ExitCode() != 79 {
		t.Fatalf("crash fixture did not reach requested durable phase: %v", err)
	}
}
func TestActualProcessDeathRecoversBoundLockAndFiles(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "owned")
	if e := platform.AtomicWrite(target, []byte("before"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := platform.AtomicWrite(filepath.Join(root, "candidate"), []byte("after"), 0600); e != nil {
		t.Fatal(e)
	}
	crashChild(t, root, "apply", "")
	engine := &Engine{StateDir: filepath.Join(root, "state"), Registrations: map[string]registration.Adapter{}}
	pending, e := engine.Pending()
	if e != nil || len(pending) != 1 {
		t.Fatalf("interrupted journal absent: %v", e)
	}
	j := pending[0]
	if j.LockIdentity == nil {
		t.Fatal("crash journal has no exclusive lock identity")
	}
	actual, e := platform.LegacyLockIdentity(filepath.Join(engine.StateDir, "lifecycle.lock"))
	if e != nil || actual != *j.LockIdentity {
		t.Fatal("journal and abandoned lock not exactly bound")
	}
	if _, e := engine.Lock(); e == nil {
		t.Fatal("ordinary operation reclaimed abandoned lock")
	}
	crashChild(t, root, "recover", j.ID)
	b, e := platform.ReadFile(engine.journalPath(j.ID), 8<<20)
	if e != nil {
		t.Fatal(e)
	}
	var second Journal
	if json.Unmarshal(b, &second) != nil || second.LockIdentity == nil || second.LockIdentity.Nonce == j.LockIdentity.Nonce {
		t.Fatal("second death did not retain replacement identity")
	}
	actual, e = platform.LegacyLockIdentity(filepath.Join(engine.StateDir, "lifecycle.lock"))
	if e != nil || actual != *second.LockIdentity {
		t.Fatal("recovery replacement lock not bound before mutation")
	}
	if _, e := engine.Recover(context.Background(), j.ID); e != nil {
		t.Fatal(e)
	}
	restored, e := platform.ReadFile(target, 100)
	if e != nil || string(restored) != "before" {
		t.Fatal("actual interrupted replacement not rolled back")
	}
	if _, e := os.Lstat(filepath.Join(engine.StateDir, "lifecycle.lock")); !os.IsNotExist(e) {
		t.Fatal("recovered known lock not released")
	}
}
func TestRecoverNeverReclaimsLiveOrUnboundLock(t *testing.T) {
	engine, target, source := fixture(t)
	before, _ := Inspect(target)
	j, e := engine.Execute(context.Background(), Plan{Host: "codex", Mutations: []Mutation{{Target: target, Source: source, Expected: &before}}})
	if e != nil {
		t.Fatal(e)
	}
	lock, e := platform.LegacyLock(filepath.Join(engine.StateDir, "lifecycle.lock"))
	if e != nil {
		t.Fatal(e)
	}
	defer lock.Close()
	identity, e := platform.LegacyLockIdentity(filepath.Join(engine.StateDir, "lifecycle.lock"))
	if e != nil {
		t.Fatal(e)
	}
	j.LockIdentity = &identity
	b, e := json.Marshal(j)
	if e != nil {
		t.Fatal(e)
	}
	if e := platform.AtomicWrite(engine.journalPath(j.ID), b, 0600); e != nil {
		t.Fatal(e)
	}
	if _, e := engine.Recover(context.Background(), j.ID); e == nil {
		t.Fatal("live bound lock reclaimed")
	}
	actual, e := platform.LegacyLockIdentity(filepath.Join(engine.StateDir, "lifecycle.lock"))
	if e != nil || actual != identity {
		t.Fatal("live lock changed")
	}
}
