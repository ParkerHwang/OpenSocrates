//go:build windows

package platform

import (
	"encoding/binary"
	"golang.org/x/sys/windows"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unsafe"
)

func TestWindowsProtectedDACLAndAncestorLease(t *testing.T) {
	root := privateTestDir(t)
	path := filepath.Join(root, "state.json")
	if e := AtomicWrite(path, []byte("private"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := Guard(path); e != nil {
		t.Fatal("created file DACL not protected")
	}
	lease, e := Lease(path)
	if e != nil {
		t.Fatal(e)
	}
	if e = os.Rename(root, root+"-moved"); e == nil {
		t.Fatal("held parent could be renamed")
	}
	lease.Close()
	sd, e := windows.SecurityDescriptorFromString("D:P(A;;FA;;;WD)")
	if e != nil {
		t.Fatal(e)
	}
	acl, _, e := sd.DACL()
	if e != nil {
		t.Fatal(e)
	}
	if e = windows.SetNamedSecurityInfo(path, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION|windows.PROTECTED_DACL_SECURITY_INFORMATION, nil, nil, acl, nil); e != nil {
		t.Fatal(e)
	}
	if Guard(path) == nil || AtomicWrite(path, []byte("unsafe"), 0600) == nil {
		t.Fatal("broad ACL accepted")
	}
}
func TestWindowsLongUnicodePathAndReparseAncestor(t *testing.T) {
	root := privateTestDir(t)
	long := root
	for i := 0; i < 18; i++ {
		long = filepath.Join(long, "유니코드-long-segment")
	}
	if e := Mkdir(long); e != nil {
		t.Fatal(e)
	}
	p := filepath.Join(long, "state.json")
	if e := AtomicWrite(p, []byte("long"), 0600); e != nil {
		t.Fatal(e)
	}
	if _, e := ReadFile(p, 100); e != nil {
		t.Fatal(e)
	}
	target := filepath.Join(root, "target")
	if e := Mkdir(target); e != nil {
		t.Fatal(e)
	}
	junction := filepath.Join(root, "junction")
	if e := Mkdir(junction); e != nil {
		t.Fatal(e)
	}
	u, _ := windows.UTF16PtrFromString(nativePath(junction))
	h, e := windows.CreateFile(u, windows.GENERIC_WRITE, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if e != nil {
		t.Fatal(e)
	}
	substitute := windows.StringToUTF16(`\??\` + target)
	printName := windows.StringToUTF16(target)
	data := make([]byte, 16+len(substitute)*2+len(printName)*2)
	binary.LittleEndian.PutUint32(data, 0xa0000003)
	binary.LittleEndian.PutUint16(data[4:], uint16(len(data)-8))
	binary.LittleEndian.PutUint16(data[10:], uint16((len(substitute)-1)*2))
	binary.LittleEndian.PutUint16(data[12:], uint16(len(substitute)*2))
	binary.LittleEndian.PutUint16(data[14:], uint16((len(printName)-1)*2))
	offset := 16
	for _, r := range append(substitute, printName...) {
		binary.LittleEndian.PutUint16(data[offset:], r)
		offset += 2
	}
	var returned uint32
	e = windows.DeviceIoControl(h, windows.FSCTL_SET_REPARSE_POINT, &data[0], uint32(len(data)), nil, 0, &returned, nil)
	windows.CloseHandle(h)
	if e != nil {
		t.Fatal(e)
	}
	if e = GuardOwned(junction); e == nil {
		t.Fatal("junction accepted")
	}
	if e = AtomicWrite(filepath.Join(junction, "new.json"), nil, 0600); e == nil {
		t.Fatal("reparse ancestor accepted")
	}
}
func TestWindowsRejectsRemoteAndADS(t *testing.T) {
	for _, p := range []string{`\\server\share\state`, `C:\private\file:stream`, `C:\private\trailing.`, `C:\private\NUL`} {
		if _, e := windowsPath(p); e == nil {
			t.Fatalf("unsafe Windows path accepted: %s", strings.ReplaceAll(p, "private", "managed"))
		}
	}
}

// Compile-time alignment assertion for the native FILE_RENAME_INFORMATION
// RootDirectory field used by executable and journal replacement.
func TestWindowsNativeRenameAlignment(t *testing.T) {
	type header struct {
		Replace byte
		Root    windows.Handle
		Length  uint32
		Name    uint16
	}
	if unsafe.Offsetof(header{}.Root)%unsafe.Alignof(windows.Handle(0)) != 0 {
		t.Fatal("native rename layout misaligned")
	}
}
