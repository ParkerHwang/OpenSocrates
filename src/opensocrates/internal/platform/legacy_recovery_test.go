package platform

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Deliberately exit without deferred cleanup: the OS closes descriptors but
// the npm-compatible exclusive-create file remains, as in a killed updater.
func TestLegacyCrashFixture(t *testing.T) {
	path := os.Getenv("OPENSOCRATES_LEGACY_CRASH_PATH")
	if path == "" {
		return
	}
	identity, e := NewLegacyLockIdentity()
	if e != nil {
		os.Exit(20)
	}
	if _, e = LegacyLockWithIdentity(path, identity); e != nil {
		os.Exit(21)
	}
	os.Exit(23)
}
func crashedLegacyLock(t *testing.T) (string, LockIdentity) {
	t.Helper()
	path := filepath.Join(privateTestDir(t), "lifecycle.lock")
	exe, e := os.Executable()
	if e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	r, e := Run(ctx, exe, []string{"-test.run=^TestLegacyCrashFixture$"}, RunOptions{Env: append(os.Environ(), "OPENSOCRATES_LEGACY_CRASH_PATH="+path)})
	if e == nil || r.ExitCode != 23 {
		t.Fatalf("fixture did not exit at crash boundary: %d %v", r.ExitCode, e)
	}
	identity, e := LegacyLockIdentity(path)
	if e != nil {
		t.Fatal(e)
	}
	return path, identity
}
func TestJournalBoundDeadLegacyRecovery(t *testing.T) {
	path, identity := crashedLegacyLock(t)
	if RecoverLegacyLock(path, identity) == nil {
		t.Fatal("recovered without actual native kernel lock")
	}
	native, e := Lock(filepath.Join(filepath.Dir(path), "native-lifecycle.lock"))
	if e != nil {
		t.Fatal(e)
	}
	defer native.Close()
	bad := identity
	bad.Nonce = "00000000000000000000000000000000"
	if RecoverLegacyLock(path, bad) == nil {
		t.Fatal("foreign nonce reclaimed")
	}
	if _, e = os.Stat(path); e != nil {
		t.Fatal("mismatched lock was removed")
	}
	if e = RecoverLegacyLock(path, identity); e != nil {
		t.Fatal(e)
	}
	next, e := NewLegacyLockIdentity()
	if e != nil {
		t.Fatal(e)
	}
	lock, e := LegacyLockWithIdentity(path, next)
	if e != nil {
		t.Fatal(e)
	}
	defer lock.Close()
	actual, e := LegacyLockIdentity(path)
	if e != nil || actual != next {
		t.Fatal("prebound replacement identity differs")
	}
	if RecoverLegacyLock(path, next) == nil {
		t.Fatal("live owner reclaimed")
	}
}
func TestLegacyRecoveryRejectsModifiedBytesAndNpm(t *testing.T) {
	path, identity := crashedLegacyLock(t)
	native, e := Lock(filepath.Join(filepath.Dir(path), "native-lifecycle.lock"))
	if e != nil {
		t.Fatal(e)
	}
	defer native.Close()
	original, e := ReadFile(path, 4096)
	if e != nil {
		t.Fatal(e)
	}
	changed := append(append([]byte{}, original...), byte(' '))
	if e = AtomicWrite(path, changed, 0600); e != nil {
		t.Fatal(e)
	}
	if RecoverLegacyLock(path, identity) == nil {
		t.Fatal("modified lock bytes reclaimed")
	}
	got, e := ReadFile(path, 4096)
	if e != nil || string(got) != string(changed) {
		t.Fatal("modified lock not preserved")
	}
	if e = AtomicWrite(path, []byte("{\"pid\":-1,\"startedAt\":\"2000-01-01T00:00:00Z\"}\n"), 0600); e != nil {
		t.Fatal(e)
	}
	if RecoverLegacyLock(path, identity) == nil {
		t.Fatal("old npm stale lock reclaimed")
	}
	if _, e = LegacyLockIdentity(path); e == nil {
		t.Fatal("unknown npm identity accepted")
	}
}
func TestLegacyPreboundIdentityCannotBeForged(t *testing.T) {
	path := filepath.Join(privateTestDir(t), "lifecycle.lock")
	identity, e := NewLegacyLockIdentity()
	if e != nil {
		t.Fatal(e)
	}
	identity.PID++
	if lock, e := LegacyLockWithIdentity(path, identity); e == nil {
		lock.Close()
		t.Fatal("other owner PID accepted")
	}
	identity, e = NewLegacyLockIdentity()
	if e != nil {
		t.Fatal(e)
	}
	identity.SHA256 = "0000000000000000000000000000000000000000000000000000000000000000"
	if lock, e := LegacyLockWithIdentity(path, identity); e == nil {
		lock.Close()
		t.Fatal("unbound hash accepted")
	}
	if _, e = os.Lstat(path); !os.IsNotExist(e) {
		t.Fatal("invalid prebinding created file")
	}
}
