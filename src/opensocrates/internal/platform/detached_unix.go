//go:build !windows

package platform

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
)

func SpawnReplacementHelper(executable, requestPath, expectedSHA256 string) (int, error) {
	return 0, diagnostics.New(diagnostics.Unsupported, "windows_replacement")
}
func SpawnManagerActivationHelper(executable, stateDir string, parentPID int, expectedSHA256 string, parentExecutable ...string) (int, error) {
	return 0, diagnostics.New(diagnostics.Unsupported, "windows_replacement")
}
