//go:build !windows

package platform

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"regexp"
	"runtime"
	"time"
)

func verifyNativeSignature(ctx context.Context, path string, p NativeTrustPolicy) error {
	if runtime.GOOS != "darwin" {
		return diagnostics.New(diagnostics.Unsupported, "native_trust")
	}
	return verifyDarwinSignature(ctx, path, p, Run)
}

// codesign's notarization requirement applies to bare Mach-O tools. spctl's
// execute assessor requires an app bundle and rejects valid notarized CLI tools.
// The runner parameter is a test seam; production always uses the bounded Run.
func verifyDarwinSignature(ctx context.Context, path string, p NativeTrustPolicy, run func(context.Context, string, []string, RunOptions) (Result, error)) error {
	if !regexp.MustCompile(`^[A-Z0-9]{10}$`).MatchString(p.DarwinTeamID) {
		return diagnostics.New(diagnostics.Unsupported, "native_trust")
	}
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()
	if ctx.Err() != nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	requirement := `=anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists and certificate leaf[field.1.2.840.113635.100.6.1.13] exists and certificate leaf[subject.OU] = "` + p.DarwinTeamID + `" and notarized`
	if _, e := run(ctx, "/usr/bin/codesign", []string{"--verify", "--deep", "--strict", "--check-notarization", "-R", requirement, path}, RunOptions{OutputLimit: 64 << 10}); e != nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	return nil
}
