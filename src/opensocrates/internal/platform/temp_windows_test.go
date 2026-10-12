//go:build windows

package platform

import (
	"golang.org/x/sys/windows"
	"path/filepath"
	"testing"
)

func TestWindowsTemporaryOwnerDiagnostics(t *testing.T) {
	base := t.TempDir()
	path, _ := windows.UTF16PtrFromString(nativePath(base))
	h, e := windows.CreateFile(path, windows.READ_CONTROL|windows.FILE_READ_ATTRIBUTES, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if e != nil {
		t.Fatal(e)
	}
	sd, e := windows.GetSecurityInfo(h, windows.SE_FILE_OBJECT, windows.OWNER_SECURITY_INFORMATION|windows.DACL_SECURITY_INFORMATION)
	windows.CloseHandle(h)
	if e != nil {
		t.Fatal(e)
	}
	owner, _, e := sd.Owner()
	if e != nil {
		t.Fatal(e)
	}
	sid, e := currentSID()
	if e != nil {
		t.Fatal(e)
	}
	control, _, e := sd.Control()
	if e != nil {
		t.Fatal(e)
	}
	t.Logf("default temporary owner_current_user=%t dacl_protected=%t", owner != nil && owner.Equals(sid), control&windows.SE_DACL_PROTECTED != 0)
	child, e := MkdirTemp(base, "owned-")
	if e != nil {
		t.Fatal(e)
	}
	if e = Guard(child); e != nil {
		t.Fatal("explicit owner/private directory contract failed")
	}
	f, e := CreateTemp(child, "owned-")
	if e != nil {
		t.Fatal(e)
	}
	name := f.Name()
	f.Close()
	if filepath.Dir(name) != child || Guard(name) != nil {
		t.Fatal("explicit owner/private file contract failed")
	}
}
