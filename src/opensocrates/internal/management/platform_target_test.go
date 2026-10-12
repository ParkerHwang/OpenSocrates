package management

import (
	"debug/pe"
	"encoding/binary"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"path/filepath"
	"runtime/debug"
	"testing"
)

func TestNativeManagerTargetAndGoBuildArchitecture(t *testing.T) {
	for _, row := range []struct{ os, arch, target string }{{"darwin", "arm64", "darwin-arm64"}, {"windows", "amd64", "windows-x64"}, {"windows", "arm64", "windows-arm64"}} {
		t.Run(row.target, func(t *testing.T) {
			m := Manager{GOOS: row.os, GOARCH: row.arch}
			if m.Target() != row.target {
				t.Fatal("manager selected wrong native distribution")
			}
			info := &debug.BuildInfo{Settings: []debug.BuildSetting{{Key: "GOOS", Value: row.os}, {Key: "GOARCH", Value: row.arch}}}
			if e := verifyGoBuildTarget(info, row.target); e != nil {
				t.Fatal(e)
			}
			info.Settings[1].Value = "386"
			if verifyGoBuildTarget(info, row.target) == nil {
				t.Fatal("wrong Go architecture accepted")
			}
			info.Settings[1].Value = row.arch
			info.Settings = append(info.Settings, debug.BuildSetting{Key: "GOARCH", Value: row.arch})
			if verifyGoBuildTarget(info, row.target) == nil {
				t.Fatal("ambiguous Go architecture accepted")
			}
		})
	}
}
func TestNativeWindowsPEArchitectureGate(t *testing.T) {
	dir, e := platform.MkdirTemp(t.TempDir(), "pe-")
	if e != nil {
		t.Fatal(e)
	}
	writePE := func(name string, machine uint16) string {
		t.Helper()
		data := make([]byte, 0x80+24)
		copy(data, []byte("MZ"))
		binary.LittleEndian.PutUint32(data[0x3c:], 0x80)
		copy(data[0x80:], []byte{'P', 'E', 0, 0})
		binary.LittleEndian.PutUint16(data[0x84:], machine)
		path := filepath.Join(dir, name+".exe")
		if e := platform.ExclusiveWrite(path, data, 0600); e != nil {
			t.Fatal(e)
		}
		return path
	}
	arm := writePE("arm", pe.IMAGE_FILE_MACHINE_ARM64)
	amd := writePE("amd", pe.IMAGE_FILE_MACHINE_AMD64)
	ec := writePE("arm64ec", 0xa641)
	if e = verifyNativeImage(arm, "windows-arm64"); e != nil {
		t.Fatal(e)
	}
	if e = verifyNativeImage(amd, "windows-x64"); e != nil {
		t.Fatal(e)
	}
	if verifyNativeImage(amd, "windows-arm64") == nil || verifyNativeImage(arm, "windows-x64") == nil || verifyNativeImage(ec, "windows-arm64") == nil {
		t.Fatal("foreign or hybrid PE architecture accepted as native")
	}
}
