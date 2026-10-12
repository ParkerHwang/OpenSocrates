//go:build windows

package platform

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"golang.org/x/sys/windows"
	"path/filepath"
)

// SystemExecutable is a closed list of external OS scheduler/trust tools. It
// never consults PATH or an environment-controlled Windows installation root.
func SystemExecutable(name string) (string, error) {
	switch name {
	case "schtasks.exe", "icacls.exe", "certutil.exe", "powershell.exe":
	default:
		return "", diagnostics.New(diagnostics.Unsupported, "system_tool")
	}
	root, e := windows.GetSystemDirectory()
	if e != nil {
		return "", failure()
	}
	if name == "powershell.exe" {
		return filepath.Join(root, "WindowsPowerShell", "v1.0", "powershell.exe"), nil
	}
	return filepath.Join(root, name), nil
}
