//go:build windows

package platform

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestReplacementWorkerFixture(t *testing.T) {
	request := os.Getenv("OPENSOCRATES_REPLACEMENT_TEST_REQUEST")
	if request == "" {
		return
	}
	if e := ReplaceExecutable(context.Background(), request); e != nil {
		os.Exit(3)
	}
	os.Exit(0)
}
func replacementFixture(t *testing.T) (ReplacementRequest, string, string) {
	t.Helper()
	root := privateTestDir(t)
	self, e := os.Executable()
	if e != nil {
		t.Fatal(e)
	}
	raw, e := os.ReadFile(self)
	if e != nil {
		t.Fatal(e)
	}
	target := filepath.Join(root, "opensocrates.exe")
	candidate := filepath.Join(root, "versions", "candidate", "opensocrates.exe")
	helper := filepath.Join(root, "versions", "candidate", "opensocrates-update-helper.exe")
	if e = Mkdir(filepath.Dir(candidate)); e != nil {
		t.Fatal(e)
	}
	if e = AtomicWrite(target, raw, 0700); e != nil {
		t.Fatal(e)
	}
	if e = AtomicWrite(candidate, append(append([]byte{}, raw...), []byte("new-version")...), 0700); e != nil {
		t.Fatal(e)
	}
	if e = AtomicWrite(helper, raw, 0700); e != nil {
		t.Fatal(e)
	}
	previous, _ := SHA256File(target, 128<<20)
	next, _ := SHA256File(candidate, 128<<20)
	helperHash, _ := SHA256File(helper, 128<<20)
	r := ReplacementRequest{Schema: 1, OperationID: "0123456789abcdef0123456789abcdef", Target: target, Candidate: candidate, Backup: filepath.Join(root, "opensocrates.exe.previous"), PreviousSHA256: previous, CandidateSHA256: next, HelperSHA256: helperHash, TimeoutSeconds: 2}
	request := filepath.Join(root, "replacement.json")
	b, _ := json.Marshal(r)
	if e = AtomicWrite(request, append(b, '\n'), 0600); e != nil {
		t.Fatal(e)
	}
	return r, request, helper
}
func runReplacementWorker(ctx context.Context, helper, request string) (Result, error) {
	return Run(ctx, helper, []string{"-test.run=^TestReplacementWorkerFixture$"}, RunOptions{Env: append(os.Environ(), "OPENSOCRATES_REPLACEMENT_TEST_REQUEST="+request)})
}
func TestWindowsExecutableReplacementAndVerifiedBackup(t *testing.T) {
	r, request, helper := replacementFixture(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if _, e := runReplacementWorker(ctx, helper, request); e != nil {
		t.Fatal(e)
	}
	if !hashEquals(r.Target, r.CandidateSHA256) || !hashEquals(r.Backup, r.PreviousSHA256) {
		t.Fatal("replacement or backup mismatch")
	}
	if _, e := runReplacementWorker(ctx, helper, request); e != nil {
		t.Fatal("retry not idempotent")
	}
	if e := AtomicWrite(r.Backup, []byte("changed backup"), 0600); e != nil {
		t.Fatal(e)
	}
	if _, e := runReplacementWorker(ctx, helper, request); e == nil {
		t.Fatal("modified backup accepted")
	}
	if !hashEquals(r.Target, r.CandidateSHA256) {
		t.Fatal("active executable changed after modified backup")
	}
}
func TestWindowsInterruptedReplacementRestoresPrevious(t *testing.T) {
	r, request, helper := replacementFixture(t)
	if e := Rename(r.Target, r.Backup); e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if _, e := runReplacementWorker(ctx, helper, request); e == nil {
		t.Fatal("verified rollback reported as activation")
	}
	if !hashEquals(r.Target, r.PreviousSHA256) || !hashEquals(r.Candidate, r.CandidateSHA256) {
		t.Fatal("interrupted activation not safely recovered")
	}
}
func TestWindowsReplacementWaitsForOwnedPID(t *testing.T) {
	r, request, helper := replacementFixture(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	sleeper, e := Start(ctx, r.Target, []string{"-test.run=^TestProcessFixture$"}, fixtureOptions("wait"))
	if e != nil {
		t.Fatal(e)
	}
	defer sleeper.Close()
	r.PID = sleeper.Cmd.Process.Pid
	r.TimeoutSeconds = 1
	b, _ := json.Marshal(r)
	if e = AtomicWrite(request, append(b, '\n'), 0600); e != nil {
		t.Fatal(e)
	}
	start := time.Now()
	if _, e = runReplacementWorker(ctx, helper, request); e == nil {
		t.Fatal("running executable replaced")
	}
	if time.Since(start) > 4*time.Second {
		t.Fatal("helper wait unbounded")
	}
	if !hashEquals(r.Target, r.PreviousSHA256) {
		t.Fatal("active executable lost on timeout")
	}
	if _, e = os.Lstat(r.Backup); !os.IsNotExist(e) {
		t.Fatal("backup created before process exit")
	}
}
