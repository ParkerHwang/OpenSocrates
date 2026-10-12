package runtimecli

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/version"
	"os"
	"path/filepath"
	"runtime"
)

// RuntimeIntegrity discovers only an immutable package ancestor of this
// executable. Source runs and absent manifests remain explicitly unavailable.
func RuntimeIntegrity(host string) map[string]any {
	result := map[string]any{"status": "unavailable", "version": nil, "checksum_status": "unavailable"}
	executable, e := os.Executable()
	if e != nil {
		return result
	}
	executable, e = filepath.EvalSymlinks(executable)
	if e != nil {
		return result
	}
	current := filepath.Dir(executable)
	target := runtime.GOOS + "-" + runtime.GOARCH
	if runtime.GOARCH == "amd64" {
		target = runtime.GOOS + "-x64"
	}
	for i := 0; i < 7; i++ {
		manifest := filepath.Join(current, "release-manifest.json")
		if _, e := os.Lstat(manifest); e == nil {
			p, e := transport.Verify(current, host, version.ProductVersion, target)
			if e != nil {
				result["status"], result["checksum_status"] = "mismatch", "mismatch"
				return result
			}
			result["status"], result["checksum_status"], result["version"] = "verified", "verified", p.Manifest.ProductVersion
			return result
		}
		if _, e := os.Lstat(filepath.Join(current, "bundle-manifest.json")); e == nil {
			p, e := transport.Prepare(current, host, version.ProductVersion, target)
			if e != nil {
				result["status"], result["checksum_status"] = "mismatch", "mismatch"
				return result
			}
			result["status"], result["checksum_status"], result["version"] = "verified", "verified", p.Manifest.ProductVersion
			return result
		}
		parent := filepath.Dir(current)
		if parent == current {
			break
		}
		current = parent
	}
	return result
}
