//go:build !windows

package devtools

import "github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"

func readAcceptanceSource(path string, max int64) ([]byte, error) {
	return platform.ReadOwnedFile(path, max)
}
