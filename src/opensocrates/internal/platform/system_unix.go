//go:build !windows

package platform

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"runtime"
)

func SystemExecutable(name string) (string, error) {
	if runtime.GOOS == "darwin" {
		switch name {
		case "zsh":
			return "/bin/zsh", nil
		case "launchctl":
			return "/bin/launchctl", nil
		case "codesign":
			return "/usr/bin/codesign", nil
		case "spctl":
			return "/usr/sbin/spctl", nil
		}
	}
	return "", diagnostics.New(diagnostics.Unsupported, "system_tool")
}
