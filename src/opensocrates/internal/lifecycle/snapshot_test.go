package lifecycle

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
)

type zeroPayload struct{}

func (zeroPayload) Read(p []byte) (int, error) {
	clear(p)
	return len(p), nil
}

func TestCopyVerifiedAcceptsReleasedWindowsRuntimeSize(t *testing.T) {
	// Exact size of codex.exe inside the published v1.5 Windows x64 archive.
	const size int64 = 341142832
	root := privateLifecycleTestDir(t)
	source, target := filepath.Join(root, "legacy.exe"), filepath.Join(root, "backup.exe")
	if e := platform.ExclusiveWrite(source, nil, 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.Truncate(source, size); e != nil {
		t.Fatal(e)
	}
	expected, e := Inspect(source)
	if e != nil || len(expected.Entries) != 1 || expected.Entries[0].Size != size {
		t.Fatalf("released runtime size rejected: %v", e)
	}
	h := sha256.New()
	if _, e := io.CopyN(h, zeroPayload{}, size); e != nil {
		t.Fatal(e)
	}
	if expected.Entries[0].SHA256 != hex.EncodeToString(h.Sum(nil)) {
		t.Fatal("large payload hash differs")
	}
	if e := CopyVerified(source, target, expected); e != nil {
		t.Fatal(e)
	}
	actual, e := Inspect(target)
	if e != nil || !Equal(expected, actual) {
		t.Fatalf("large recovery copy differs: %v", e)
	}
}

func TestInspectRejectsFileBeyondLifecycleLimit(t *testing.T) {
	root := privateLifecycleTestDir(t)
	p := filepath.Join(root, "oversized.exe")
	if e := platform.ExclusiveWrite(p, nil, 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.Truncate(p, MaxFileBytes+1); e != nil {
		t.Fatal(e)
	}
	if _, e := Inspect(p); e == nil {
		t.Fatal("unbounded file accepted")
	}
}

func TestPortableInventoryModePreservesWindowsReadonly(t *testing.T) {
	cases := []struct {
		path      string
		mode      os.FileMode
		directory bool
		want      os.FileMode
	}{
		{"file.md", 0666, false, 0644}, {"file.md", 0444, false, 0444},
		{"opensocrates.exe", 0666, false, 0644}, {"opensocrates.EXE", 0444, false, 0444},
		{".opensocrates-id-opensocrates.exe-candidate", 0666, false, 0644},
		{".opensocrates-id-opensocrates.exe-backup", 0444, false, 0444},
		{"directory", 0777, true, 0755}, {"directory", 0555, true, 0555},
	}
	for _, c := range cases {
		got := portableInventoryMode("windows", c.path, c.mode, c.directory)
		if got != c.want || got&0022 != 0 {
			t.Fatalf("portable mode %s %o: got %o want %o", c.path, c.mode, got, c.want)
		}
	}
	for _, mode := range []os.FileMode{0600, 0644, 0700, 0755, 0400, 0555} {
		if got := portableInventoryMode("darwin", "file.exe", mode, false); got != mode {
			t.Fatalf("Unix mode changed: %o -> %o", mode, got)
		}
	}
}
func TestCopyVerifiedPreservesNativeReadonlyWithoutMutatingSource(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("native Windows readonly attributes and DACL evidence required")
	}
	root := privateLifecycleTestDir(t)
	source := filepath.Join(root, "source")
	destination := filepath.Join(root, "destination")
	if e := platform.Mkdir(source); e != nil {
		t.Fatal(e)
	}
	for _, name := range []string{"guide.md", "opensocrates.exe"} {
		path := filepath.Join(source, name)
		if e := platform.AtomicWrite(path, []byte("synthetic owned bytes"), 0644); e != nil {
			t.Fatal(e)
		}
		if e := platform.SetOwnedMode(path, 0444); e != nil {
			t.Fatal(e)
		}
		defer platform.SetOwnedMode(path, 0600)
	}
	if e := platform.SetOwnedMode(source, 0555); e != nil {
		t.Fatal(e)
	}
	defer platform.SetOwnedMode(source, 0700)
	before, e := Inspect(source)
	if e != nil {
		t.Fatal(e)
	}
	if e := CopyVerified(source, destination, before); e != nil {
		t.Fatal(e)
	}
	defer platform.SetOwnedMode(destination, 0700)
	after, e := Inspect(destination)
	if e != nil || !Equal(before, after) {
		t.Fatalf("readonly copy inventory differs: %v", e)
	}
	unchanged, e := Inspect(source)
	if e != nil || !Equal(before, unchanged) {
		t.Fatal("source attributes or bytes changed")
	}
	for _, name := range []string{"guide.md", "opensocrates.exe"} {
		path := filepath.Join(destination, name)
		info, e := os.Lstat(path)
		if e != nil || info.Mode().Perm()&0200 != 0 {
			t.Fatal("destination readonly attribute lost")
		}
		if e := platform.GuardOwned(path); e != nil {
			t.Fatal("destination native DACL ownership lost")
		}
		defer platform.SetOwnedMode(path, 0600)
	}
}

func TestWindowsExecutableAliasesKeepSingleFileSnapshot(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("native Windows alias, readonly and ACL evidence required")
	}
	for _, readonly := range []bool{false, true} {
		t.Run(map[bool]string{false: "writable", true: "readonly"}[readonly], func(t *testing.T) {
			root := privateLifecycleTestDir(t)
			source := filepath.Join(root, "opensocrates.exe")
			candidate := filepath.Join(root, ".opensocrates-id-opensocrates.exe-candidate")
			backup := filepath.Join(root, ".opensocrates-id-opensocrates.exe-backup")
			restored := filepath.Join(root, "restored.exe")
			mode := os.FileMode(0755)
			if readonly {
				mode = 0555
			}
			if err := platform.ExclusiveWrite(source, []byte("synthetic native payload"), mode); err != nil {
				t.Fatal(err)
			}
			expected, err := Inspect(source)
			if err != nil {
				t.Fatal(err)
			}
			if err := CopyVerified(source, candidate, expected); err != nil {
				t.Fatal(err)
			}
			for _, pair := range [][2]string{{candidate, backup}, {backup, restored}} {
				if err := platform.Rename(pair[0], pair[1]); err != nil {
					t.Fatal(err)
				}
				actual, err := Inspect(pair[1])
				if err != nil || !Equal(actual, expected) {
					t.Fatalf("alias changed single-file identity: %v", err)
				}
				if err := platform.GuardOwned(pair[1]); err != nil {
					t.Fatal("alias lost native ownership")
				}
			}
			defer platform.SetOwnedMode(source, 0644)
			defer platform.SetOwnedMode(restored, 0644)
		})
	}
}

func TestWindowsInterruptedExecutableActivationRollback(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("native Windows executable replacement and rollback evidence required")
	}
	root := privateLifecycleTestDir(t)
	target := filepath.Join(root, "opensocrates.exe")
	source := filepath.Join(root, "candidate.exe")
	if err := platform.ExclusiveWrite(target, []byte("before"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := platform.ExclusiveWrite(source, []byte("after"), 0755); err != nil {
		t.Fatal(err)
	}
	before, err := Inspect(target)
	if err != nil {
		t.Fatal(err)
	}
	after, err := Inspect(source)
	if err != nil {
		t.Fatal(err)
	}
	engine := &Engine{StateDir: filepath.Join(root, "state"), Registrations: map[string]registration.Adapter{}}
	if err := platform.Mkdir(filepath.Join(engine.StateDir, "transactions")); err != nil {
		t.Fatal(err)
	}
	id := NewID()
	stem := filepath.Join(root, ".opensocrates-"+id+"-opensocrates.exe")
	journal := Journal{Schema: JournalSchema, ID: id, Host: "manager", Scope: "global", Stage: "applying", Files: []FileChange{{Target: target, Staged: stem + "-candidate", Backup: stem + "-backup", Before: before, After: after, Phase: "activate-intent"}}}
	if err := engine.save(&journal); err != nil {
		t.Fatal(err)
	}
	if err := CopyVerified(source, journal.Files[0].Staged, after); err != nil {
		t.Fatal(err)
	}
	if err := platform.Rename(target, journal.Files[0].Backup); err != nil {
		t.Fatal(err)
	}
	backup, err := Inspect(journal.Files[0].Backup)
	if err != nil || !Equal(backup, before) {
		t.Fatal("backup alias changed executable identity")
	}
	if err := platform.Rename(journal.Files[0].Staged, target); err != nil {
		t.Fatal(err)
	}
	// The durable intent remains pre-rename: recovery must inspect real bytes,
	// distinguish the completed activation, and restore its verified backup.
	result, err := engine.Recover(context.Background(), id)
	if err != nil || result.Stage != "rolled-back" {
		t.Fatalf("interrupted executable activation not recovered: %v", err)
	}
	restored, err := Inspect(target)
	if err != nil || !Equal(restored, before) {
		t.Fatal("original executable snapshot not restored")
	}
	bytes, err := platform.ReadOwnedFile(target, 100)
	if err != nil || string(bytes) != "before" {
		t.Fatal("original executable bytes not restored")
	}
}
