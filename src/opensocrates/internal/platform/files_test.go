package platform

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

func privateTestDir(t *testing.T) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "private")
	if e := Mkdir(p); e != nil {
		t.Fatal(e)
	}
	return p
}
func TestOwnedAndPrivateFiles(t *testing.T) {
	root := privateTestDir(t)
	p := filepath.Join(root, "한글-é.json")
	want := []byte("{\"value\":\"\U0001f600\"}\n")
	if e := AtomicWrite(p, want, 0600); e != nil {
		t.Fatal(e)
	}
	got, e := ReadFile(p, 1000)
	if e != nil || !bytes.Equal(got, want) {
		t.Fatalf("bounded read failed: %v", e)
	}
	if _, e = ReadFile(p, 2); e == nil {
		t.Fatal("oversize accepted")
	}
	if e = AtomicWrite(p, []byte("replaced"), 0600); e != nil {
		t.Fatal(e)
	}
	if runtime.GOOS != "windows" {
		if e = AtomicWrite(p, []byte("public package"), 0644); e != nil {
			t.Fatal(e)
		}
		if Guard(p) == nil {
			t.Fatal("private state accepted readable content")
		}
		if GuardOwned(p) != nil {
			t.Fatal("safe package content rejected")
		}
		if _, e = ReadOwnedFile(p, 100); e != nil {
			t.Fatal(e)
		}
	}
	if AtomicWrite(filepath.Join(root, "bad"), nil, 0666) == nil {
		t.Fatal("unsafe write mode accepted")
	}
}
func TestSymlinkAndHardlinkRejection(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Windows reparse test uses native junction test")
	}
	root := privateTestDir(t)
	owned := filepath.Join(root, "owned")
	if e := AtomicWrite(owned, []byte("sentinel"), 0600); e != nil {
		t.Fatal(e)
	}
	link := filepath.Join(root, "link")
	if e := os.Symlink(owned, link); e != nil {
		t.Fatal(e)
	}
	if Guard(link) == nil || AtomicWrite(link, []byte("bad"), 0600) == nil {
		t.Fatal("symlink accepted")
	}
	dir := filepath.Join(root, "dirlink")
	if e := os.Symlink(root, dir); e != nil {
		t.Fatal(e)
	}
	if AtomicWrite(filepath.Join(dir, "new"), nil, 0600) == nil {
		t.Fatal("ancestor symlink accepted")
	}
	hard := filepath.Join(root, "hard")
	if e := os.Link(owned, hard); e != nil {
		t.Fatal(e)
	}
	if GuardOwned(hard) == nil || Remove(hard) == nil {
		t.Fatal("hardlink accepted")
	}
}
func TestOSLockAndLegacyLock(t *testing.T) {
	root := privateTestDir(t)
	p := filepath.Join(root, "native.lock")
	one, e := Lock(p)
	if e != nil {
		t.Fatal(e)
	}
	start := time.Now()
	if two, e := Lock(p); e == nil {
		two.Close()
		t.Fatal("concurrent native lock acquired")
	}
	if time.Since(start) > 2*time.Second {
		t.Fatal("unbounded lock wait")
	}
	one.Close()
	two, e := Lock(p)
	if e != nil {
		t.Fatal(e)
	}
	two.Close()
	if _, e = os.Stat(p); e != nil {
		t.Fatal("native lock file must persist")
	}
	legacyPath := filepath.Join(root, "lifecycle.lock")
	legacy, e := LegacyLock(legacyPath)
	if e != nil {
		t.Fatal(e)
	}
	identity, e := LegacyLockIdentity(legacyPath)
	if e != nil {
		t.Fatal(e)
	}
	b, e := identityBytes(identity)
	if e != nil {
		t.Fatal(e)
	}
	var document map[string]any
	if json.Unmarshal(b, &document) != nil || document["pid"] != float64(os.Getpid()) || document["startedAt"] == nil {
		t.Fatal("npm lock protocol differs")
	}
	if second, e := LegacyLock(legacyPath); e == nil {
		second.Close()
		t.Fatal("legacy lock reacquired")
	}
	legacy.Close()
	if _, e = os.Lstat(legacyPath); !os.IsNotExist(e) {
		t.Fatal("owned legacy lock remains")
	}
	if e = AtomicWrite(legacyPath, []byte("{\"pid\":-1}"), 0600); e != nil {
		t.Fatal(e)
	}
	if _, e = LegacyLock(legacyPath); e == nil {
		t.Fatal("stale lock replaced")
	}
	if _, e = os.Stat(legacyPath); e != nil {
		t.Fatal("stale lock removed")
	}
}
func TestBackupCannotOverwrite(t *testing.T) {
	root := privateTestDir(t)
	source, backup := filepath.Join(root, "source"), filepath.Join(root, "backup")
	if e := AtomicWrite(source, []byte("one"), 0600); e != nil {
		t.Fatal(e)
	}
	hash, e := BackupVerified(source, backup, 100)
	if e != nil || !hashEquals(backup, hash) {
		t.Fatal("verified backup failed")
	}
	if _, e = BackupVerified(source, backup, 100); e == nil {
		t.Fatal("backup overwritten")
	}
}
func TestTreeRemovalPreservesForeignEntry(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Windows ACL mutation has native test")
	}
	root := privateTestDir(t)
	foreign := filepath.Join(root, "foreign")
	if e := os.WriteFile(foreign, []byte("foreign"), 0666); e != nil {
		t.Fatal(e)
	}
	if e := os.Chmod(foreign, 0666); e != nil {
		t.Fatal(e)
	}
	if RemoveTree(root) == nil {
		t.Fatal("foreign entry removed")
	}
	if _, e := os.Stat(foreign); e != nil {
		t.Fatal("foreign file lost")
	}
}
func TestMissingStateIsTypedAndExportIsExclusive(t *testing.T) {
	root := privateTestDir(t)
	p := filepath.Join(root, "fresh.json")
	if _, e := ReadFile(p, 100); !errors.Is(e, os.ErrNotExist) {
		t.Fatalf("missing leaf is not typed: %v", e)
	}
	if _, e := ReadFile(filepath.Join(root, "missing-parent", "fresh.json"), 100); !errors.Is(e, os.ErrNotExist) {
		t.Fatalf("missing ancestry is not typed: %v", e)
	}
	if e := ExclusiveWrite(p, []byte("original"), 0600); e != nil {
		t.Fatal(e)
	}
	if ExclusiveWrite(p, []byte("foreign"), 0600) == nil {
		t.Fatal("exclusive export overwrote existing file")
	}
	got, e := ReadFile(p, 100)
	if e != nil || string(got) != "original" {
		t.Fatal("owned original lost")
	}
	if Mkdir(p) == nil {
		t.Fatal("file accepted as directory")
	}
}
func TestMissingProductionTrustIsClosed(t *testing.T) {
	p := filepath.Join(privateTestDir(t), "unsigned")
	if e := AtomicWrite(p, []byte("unsigned"), 0700); e != nil {
		t.Fatal(e)
	}
	if VerifyNativeSignature(context.Background(), p, NativeTrustPolicy{}) == nil {
		t.Fatal("empty signing identity accepted")
	}
}
