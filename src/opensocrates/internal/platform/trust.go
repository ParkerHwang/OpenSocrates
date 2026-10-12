package platform

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
)

// NativeTrustPolicy must come from the installer's pinned release policy, not
// an unsigned archive. Empty identity keeps production activation unavailable.
type NativeTrustPolicy struct {
	DarwinTeamID             string `json:"darwin_team_id"`
	WindowsCertificateSHA256 string `json:"windows_certificate_sha256"`
}

func VerifyNativeSignature(ctx context.Context, path string, policy NativeTrustPolicy) error {
	if e := GuardOwned(path); e != nil {
		return e
	}
	if ctx.Err() != nil {
		return diagnostics.New(diagnostics.Verification, "native_trust")
	}
	return verifyNativeSignature(ctx, path, policy)
}
