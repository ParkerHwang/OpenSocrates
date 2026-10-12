package management

import (
	"context"
	"path/filepath"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

func verifyCandidateExecutables(ctx context.Context, p transport.Package, target string, policy platform.NativeTrustPolicy) error {
	paths := map[string]bool{}
	for _, row := range p.Manifest.Files {
		if strings.HasPrefix(row.Path, "runtime/"+target+"/") && (row.Mode&0111 != 0 || strings.HasSuffix(row.Path, ".exe") || filepath.Base(row.Path) == "opensocrates") {
			paths[filepath.Join(p.Root, filepath.FromSlash(row.Path))] = true
		}
	}
	if p.BundleManifest != nil {
		for _, row := range p.BundleManifest.Files {
			if strings.HasPrefix(row.Path, "bin/") {
				name := filepath.Base(row.Path)
				if name == "opensocrates" || name == "opensocrates.exe" || name == "opensocrates-update-helper" || name == "opensocrates-update-helper.exe" {
					paths[filepath.Join(p.BundleRoot, filepath.FromSlash(row.Path))] = true
				}
			}
		}
	}
	if p.Manifest.Host == "codex" || p.Manifest.Host == "claude" {
		if len(paths) == 0 {
			return diagnostics.New(diagnostics.Verification, "native-signature")
		}
	}
	for _, path := range sortedKeys(paths) {
		if e := platform.VerifyNativeSignature(ctx, path, policy); e != nil {
			return e
		}
	}
	return nil
}
