package update

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/hosts"
)

// MetadataTarget uses Go architecture names. Asset spelling windows-x64 stays
// distinct from the retained stable/windows-amd64 signed metadata contract.
func MetadataTarget(goos, goarch string) (string, error) {
	if !hosts.NativePlatformSupported(goos, goarch) {
		return "", closed(diagnostics.Unsupported, "platform")
	}
	return "stable/" + goos + "-" + goarch + "/opensocrates.archive", nil
}
func metadataPlatform(target string) (goos, goarch string, ok bool) {
	for _, pair := range [][2]string{{"darwin", "arm64"}, {"windows", "amd64"}, {"windows", "arm64"}} {
		name, _ := MetadataTarget(pair[0], pair[1])
		if target == name {
			return pair[0], pair[1], true
		}
	}
	return "", "", false
}
