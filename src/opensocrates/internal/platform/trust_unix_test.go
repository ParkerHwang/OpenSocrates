//go:build !windows

package platform

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"testing"
	"time"
)

func TestDarwinNotarizedCLIUsesPinnedCodeAssessment(t *testing.T) {
	policy := NativeTrustPolicy{DarwinTeamID: "ABCDEFGHIJ"}
	requirement := `=anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists and certificate leaf[field.1.2.840.113635.100.6.1.13] exists and certificate leaf[subject.OU] = "ABCDEFGHIJ" and notarized`
	want := []string{"--verify", "--deep", "--strict", "--check-notarization", "-R", requirement, "/owned/bare-cli"}
	calls := 0
	run := func(ctx context.Context, executable string, args []string, options RunOptions) (Result, error) {
		calls++
		if executable != "/usr/bin/codesign" || !reflect.DeepEqual(args, want) {
			t.Fatal("bare CLI did not use the pinned Developer ID and notarization requirement")
		}
		deadline, ok := ctx.Deadline()
		if !ok || time.Until(deadline) > 30*time.Second || options.OutputLimit != 64<<10 {
			t.Fatal("native trust assessment is not bounded")
		}
		// Apple accepts the code requirement for a notarized bare CLI, while the
		// app-only assessor would reject it. No app-only assessment may follow.
		return Result{}, nil
	}
	if err := verifyDarwinSignature(context.Background(), "/owned/bare-cli", policy, run); err != nil || calls != 1 {
		t.Fatalf("notarized bare CLI was rejected: %v (calls %d)", err, calls)
	}
}

func TestDarwinCodeAssessmentRejectsVerifierFailures(t *testing.T) {
	// These are verifier failure propagation tests. Real Apple signatures and
	// notarization acceptance require native qualification evidence separately.
	for _, reason := range []string{"unsigned", "ad-hoc", "wrong-team", "not-notarized", "replaced-code", "offline-unavailable"} {
		t.Run(reason, func(t *testing.T) {
			run := func(context.Context, string, []string, RunOptions) (Result, error) {
				return Result{ExitCode: 1}, errors.New(reason)
			}
			if err := verifyDarwinSignature(context.Background(), "/owned/cli", NativeTrustPolicy{DarwinTeamID: "ABCDEFGHIJ"}, run); err == nil {
				t.Fatal("failed Apple code assessment accepted")
			}
		})
	}
}

func TestDarwinCodeAssessmentRejectsMissingPolicyAndCanceledContext(t *testing.T) {
	run := func(context.Context, string, []string, RunOptions) (Result, error) {
		t.Fatal("invalid trust policy or canceled operation launched a verifier")
		return Result{}, nil
	}
	for _, team := range []string{"", "short", `ABCDEFGHIJ" or true`, "abcdefghij"} {
		if err := verifyDarwinSignature(context.Background(), "/owned/cli", NativeTrustPolicy{DarwinTeamID: team}, run); err == nil {
			t.Fatal("invalid publisher policy accepted")
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := verifyDarwinSignature(ctx, "/owned/cli", NativeTrustPolicy{DarwinTeamID: "ABCDEFGHIJ"}, run); err == nil {
		t.Fatal("canceled assessment accepted")
	}
}

func TestDarwinNativeTrustRejectsAdHocAndUnsignedMachO(t *testing.T) {
	if runtime.GOOS != "darwin" {
		t.Skip("requires native Apple code-signing tools")
	}
	self, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(self)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(privateTestDir(t), "bare-cli")
	if err = AtomicWrite(path, data, 0755); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if _, err = Run(ctx, "/usr/bin/codesign", []string{"--force", "--sign", "-", path}, RunOptions{OutputLimit: 64 << 10}); err != nil {
		t.Fatal("could not prepare ad-hoc Mach-O fixture")
	}
	policy := NativeTrustPolicy{DarwinTeamID: "ABCDEFGHIJ"}
	if err = VerifyNativeSignature(ctx, path, policy); err == nil {
		t.Fatal("ad-hoc Mach-O counted as production trust")
	}
	if _, err = Run(ctx, "/usr/bin/codesign", []string{"--remove-signature", path}, RunOptions{OutputLimit: 64 << 10}); err != nil {
		t.Fatal("could not prepare unsigned Mach-O fixture")
	}
	if err = VerifyNativeSignature(ctx, path, policy); err == nil {
		t.Fatal("unsigned Mach-O counted as production trust")
	}
	link := path + "-link"
	if err = os.Symlink(path, link); err != nil {
		t.Fatal(err)
	}
	if err = VerifyNativeSignature(ctx, link, policy); err == nil {
		t.Fatal("symlink bypassed the owned-file trust guard")
	}
}
