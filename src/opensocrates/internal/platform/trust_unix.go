//go:build !windows

package platform

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"regexp"
	"runtime"
)

func verifyNativeSignature(ctx context.Context, path string, p NativeTrustPolicy) error {
	if runtime.GOOS != "darwin" || !regexp.MustCompile(`^[A-Z0-9]{10}$`).MatchString(p.DarwinTeamID) {
		return diagnostics.New(diagnostics.Unsupported, "native_trust")
	}
	requirement := `=anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists and certificate leaf[field.1.2.840.113635.100.6.1.13] exists and certificate leaf[subject.OU] = "` + p.DarwinTeamID + `" and notarized`
	if _, e := Run(ctx, "/usr/bin/codesign", []string{"--verify", "--deep", "--strict", "-R", requirement, path}, RunOptions{OutputLimit: 64 << 10}); e != nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	if _, e := Run(ctx, "/usr/sbin/spctl", []string{"--assess", "--type", "execute", path}, RunOptions{OutputLimit: 64 << 10}); e != nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	return nil
}
