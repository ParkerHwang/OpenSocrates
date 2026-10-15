//go:build darwin || linux

package compat

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"golang.org/x/sys/unix"
	"os"
	"path/filepath"
)

func systemTempDirectory() string { return "/tmp" }
func existingOAuth(home string) ([]byte, error) {
	if !filepath.IsAbs(home) {
		return nil, failure(diagnostics.Permission)
	}
	d, err := openExactContext(home, true)
	if err != nil {
		return nil, failure(diagnostics.Permission)
	}
	defer d.Close()
	var st unix.Stat_t
	if unix.Fstat(int(d.Fd()), &st) != nil || st.Uid != uint32(os.Geteuid()) || st.Mode&0022 != 0 {
		return nil, failure(diagnostics.Permission)
	}
	fd, err := unix.Openat(int(d.Fd()), "auth.json", contextFlags(false), 0)
	if err != nil {
		return nil, failure(diagnostics.HostUnavailable)
	}
	f, err := checkContextFile(fd, "auth.json", false)
	if err != nil {
		return nil, failure(diagnostics.Permission)
	}
	defer f.Close()
	if unix.Fstat(fd, &st) != nil || st.Uid != uint32(os.Geteuid()) || st.Mode&0077 != 0 || st.Mode&0400 == 0 || st.Nlink != 1 || st.Size > 1<<20 {
		return nil, failure(diagnostics.Permission)
	}
	b := make([]byte, int(st.Size))
	n, err := f.ReadAt(b, 0)
	if err != nil || n != len(b) {
		return nil, failure(diagnostics.Permission)
	}
	return b, nil
}
