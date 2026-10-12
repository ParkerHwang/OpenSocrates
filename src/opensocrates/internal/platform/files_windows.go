//go:build windows

package platform

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"golang.org/x/sys/windows"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
	"unsafe"
)

type windowsLease struct {
	handles []windows.Handle
	parent  windows.Handle
	name    string
	once    sync.Once
}

func (l *windowsLease) Close() error {
	l.once.Do(func() {
		for i := len(l.handles) - 1; i >= 0; i-- {
			windows.CloseHandle(l.handles[i])
		}
	})
	return nil
}
func windowsMissing(e error) bool {
	return errors.Is(e, windows.ERROR_FILE_NOT_FOUND) || errors.Is(e, windows.ERROR_PATH_NOT_FOUND) || e == windows.STATUS_OBJECT_NAME_NOT_FOUND || e == windows.STATUS_OBJECT_PATH_NOT_FOUND
}
func currentSID() (*windows.SID, error) {
	t, e := windows.OpenCurrentProcessToken()
	if e != nil {
		return nil, e
	}
	defer t.Close()
	u, e := t.GetTokenUser()
	if e != nil {
		return nil, e
	}
	return u.User.Sid.Copy()
}
func nativePath(p string) string { return `\\?\` + p }
func windowsPath(path string) (string, error) {
	p, e := cleanPath(path)
	if e != nil {
		return "", e
	}
	v := filepath.VolumeName(p)
	if len(v) != 2 || v[1] != ':' || strings.HasPrefix(p, `\\`) {
		return "", failure()
	}
	root, e := windows.UTF16PtrFromString(v + `\`)
	if e != nil || windows.GetDriveType(root) != windows.DRIVE_FIXED {
		return "", failure()
	}
	for _, s := range strings.Split(p[len(v)+1:], `\`) {
		if strings.ContainsAny(s, ":<>\"|?*") || strings.TrimRight(s, " .") != s || s == "" {
			return "", failure()
		}
		if reservedName(s) {
			return "", failure()
		}
	}
	return p, nil
}
func windowsParents(path string) (*windowsLease, error) {
	p, e := windowsPath(path)
	if e != nil {
		return nil, e
	}
	parent := filepath.Dir(p)
	volume := filepath.VolumeName(p) + `\`
	l := &windowsLease{name: filepath.Base(p)}
	current := volume
	parts := strings.Split(strings.TrimPrefix(parent, volume), `\`)
	for i := -1; i < len(parts); i++ {
		if i >= 0 {
			if parts[i] == "" {
				continue
			}
			current = filepath.Join(current, parts[i])
		}
		u, e := windows.UTF16PtrFromString(nativePath(current))
		if e != nil {
			l.Close()
			return nil, failure()
		}
		h, e := windows.CreateFile(u, windows.READ_CONTROL|windows.FILE_READ_ATTRIBUTES, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
		if e != nil {
			l.Close()
			if windowsMissing(e) {
				return nil, missingError()
			}
			return nil, failure()
		}
		l.handles = append(l.handles, h)
		l.parent = h
		var info windows.ByHandleFileInformation
		if windows.GetFileInformationByHandle(h, &info) != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY == 0 {
			l.Close()
			return nil, failure()
		}
	}
	return l, nil
}
func leaseParents(path string) (io.Closer, error) { return windowsParents(path) }
func inspectHandle(h windows.Handle) error        { return inspectWindowsHandle(h, true) }
func inspectOwnedHandle(h windows.Handle) error   { return inspectWindowsHandle(h, false) }
func inspectWindowsHandle(h windows.Handle, private bool) error {
	var info windows.ByHandleFileInformation
	if windows.GetFileInformationByHandle(h, &info) != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || info.NumberOfLinks > 1 {
		return failure()
	}
	sd, e := windows.GetSecurityInfo(h, windows.SE_FILE_OBJECT, windows.OWNER_SECURITY_INFORMATION|windows.DACL_SECURITY_INFORMATION)
	if e != nil {
		return failure()
	}
	owner, _, e := sd.Owner()
	if e != nil {
		return failure()
	}
	sid, e := currentSID()
	if e != nil || owner == nil || !owner.Equals(sid) {
		return failure()
	}
	control, _, e := sd.Control()
	if e != nil || (private && control&windows.SE_DACL_PROTECTED == 0) {
		return failure()
	}
	acl, _, e := sd.DACL()
	if e != nil || acl == nil {
		return failure()
	}
	userAllow := false
	for i := uint32(0); i < uint32(acl.AceCount); i++ {
		var ace *windows.ACCESS_ALLOWED_ACE
		if windows.GetAce(acl, i, &ace) != nil || ace == nil {
			return failure()
		}
		if ace.Header.AceType == windows.ACCESS_DENIED_ACE_TYPE {
			continue
		}
		if ace.Header.AceType != windows.ACCESS_ALLOWED_ACE_TYPE {
			return failure()
		}
		principal := (*windows.SID)(unsafe.Pointer(&ace.SidStart))
		text := principal.String()
		if text != sid.String() && text != "S-1-5-18" && text != "S-1-5-32-544" {
			writeMask := uint32(windows.FILE_WRITE_DATA | windows.FILE_APPEND_DATA | windows.FILE_WRITE_EA | windows.FILE_WRITE_ATTRIBUTES | windows.DELETE | windows.WRITE_DAC | windows.WRITE_OWNER | windows.GENERIC_WRITE | windows.GENERIC_ALL)
			if private || uint32(ace.Mask)&writeMask != 0 {
				return failure()
			}
		}
		if text == sid.String() && uint32(ace.Mask)&windows.FILE_GENERIC_READ == windows.FILE_GENERIC_READ {
			userAllow = true
		}
	}
	if !userAllow {
		return failure()
	}
	return nil
}
func descriptor(directory bool) (*windows.SECURITY_DESCRIPTOR, error) {
	sid, e := currentSID()
	if e != nil {
		return nil, e
	}
	inherit := ""
	if directory {
		inherit = "OICI"
	}
	return windows.SecurityDescriptorFromString("O:" + sid.String() + "D:P(A;" + inherit + ";FA;;;" + sid.String() + ")(A;" + inherit + ";FA;;;SY)(A;" + inherit + ";FA;;;BA)")
}
func relativeOpen(l *windowsLease, name string, access, disposition uint32, directory bool) (windows.Handle, error) {
	return relativeOpenPolicy(l, name, access, disposition, directory, true)
}
func relativeOpenPolicy(l *windowsLease, name string, access, disposition uint32, directory, private bool) (windows.Handle, error) {
	s, e := windows.NewNTUnicodeString(name)
	if e != nil {
		return 0, failure()
	}
	sd, e := descriptor(directory)
	if e != nil {
		return 0, failure()
	}
	oa := windows.OBJECT_ATTRIBUTES{Length: uint32(unsafe.Sizeof(windows.OBJECT_ATTRIBUTES{})), RootDirectory: l.parent, ObjectName: s, Attributes: windows.OBJ_CASE_INSENSITIVE, SecurityDescriptor: sd}
	options := uint32(windows.FILE_SYNCHRONOUS_IO_NONALERT | windows.FILE_OPEN_REPARSE_POINT)
	if directory {
		options |= windows.FILE_DIRECTORY_FILE
	} else {
		options |= windows.FILE_NON_DIRECTORY_FILE
	}
	var h windows.Handle
	var status windows.IO_STATUS_BLOCK
	e = windows.NtCreateFile(&h, access|windows.SYNCHRONIZE|windows.READ_CONTROL|windows.FILE_READ_ATTRIBUTES, &oa, &status, nil, windows.FILE_ATTRIBUTE_NORMAL, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, disposition, options, 0, 0)
	if e != nil {
		return 0, e
	}
	if e = inspectWindowsHandle(h, private); e != nil {
		windows.CloseHandle(h)
		return 0, e
	}
	return h, nil
}
func inspectOwnedLeaf(path string) error { return inspectWindowsLeaf(path, false) }
func inspectLeaf(path string) error      { return inspectWindowsLeaf(path, true) }
func inspectWindowsLeaf(path string, private bool) error {
	p, e := windowsPath(path)
	if e != nil {
		return e
	}
	l, e := windowsParents(p)
	if e != nil {
		return e
	}
	defer l.Close()
	u, _ := windows.UTF16PtrFromString(nativePath(p))
	h, e := windows.CreateFile(u, windows.READ_CONTROL|windows.FILE_READ_ATTRIBUTES, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if e == windows.ERROR_FILE_NOT_FOUND || e == windows.ERROR_PATH_NOT_FOUND {
		return nil
	}
	if e != nil {
		return failure()
	}
	defer windows.CloseHandle(h)
	return inspectWindowsHandle(h, private)
}
func privateMkdir(path string) error {
	p, e := windowsPath(path)
	if e != nil {
		return e
	}
	if info, statErr := os.Lstat(p); statErr == nil {
		if !info.IsDir() {
			return failure()
		}
		return GuardOwned(p)
	} else if !os.IsNotExist(statErr) {
		return failure()
	}
	if _, e = os.Lstat(filepath.Dir(p)); os.IsNotExist(e) {
		if e = privateMkdir(filepath.Dir(p)); e != nil {
			return e
		}
	}
	l, e := windowsParents(p)
	if e != nil {
		return e
	}
	defer l.Close()
	h, e := relativeOpen(l, l.name, windows.GENERIC_READ, windows.FILE_CREATE, true)
	if e != nil {
		return failure()
	}
	defer windows.CloseHandle(h)
	return nil
}
func openOwned(path string, flags int, mode os.FileMode) (*os.File, error) {
	return windowsOpen(path, flags, mode, false)
}
func openPrivate(path string, flags int, mode os.FileMode) (*os.File, error) {
	return windowsOpen(path, flags, mode, true)
}
func windowsOpen(path string, flags int, mode os.FileMode, private bool) (*os.File, error) {
	l, e := windowsParents(path)
	if e != nil {
		return nil, e
	}
	defer l.Close()
	access := uint32(windows.GENERIC_READ)
	if flags&os.O_WRONLY != 0 {
		access = windows.GENERIC_WRITE
	}
	if flags&os.O_RDWR != 0 {
		access = windows.GENERIC_READ | windows.GENERIC_WRITE
	}
	disposition := uint32(windows.FILE_OPEN)
	if flags&os.O_CREATE != 0 {
		disposition = windows.FILE_OPEN_IF
	}
	if flags&os.O_EXCL != 0 {
		disposition = windows.FILE_CREATE
	}
	h, e := relativeOpenPolicy(l, l.name, access, disposition, false, private)
	if windowsMissing(e) {
		return nil, missingError()
	}
	if e != nil {
		return nil, failure()
	}
	return os.NewFile(uintptr(h), "private"), nil
}
func renameHandle(h windows.Handle, parent windows.Handle, name string, replace bool) error {
	utf, e := windows.UTF16FromString(name)
	if e != nil {
		return failure()
	}
	utf = utf[:len(utf)-1]
	// FILE_RENAME_INFORMATION has native pointer alignment before RootDirectory.
	type header struct {
		Replace byte
		Root    windows.Handle
		Length  uint32
		Name    uint16
	}
	offset := int(unsafe.Offsetof(header{}.Name))
	b := make([]byte, offset+len(utf)*2)
	x := (*header)(unsafe.Pointer(&b[0]))
	if replace {
		x.Replace = 1
	}
	x.Root = parent
	x.Length = uint32(len(utf) * 2)
	copy(unsafe.Slice((*uint16)(unsafe.Pointer(&b[offset])), len(utf)), utf)
	var status windows.IO_STATUS_BLOCK
	if windows.NtSetInformationFile(h, &status, &b[0], uint32(len(b)), 10) != nil {
		return failure()
	}
	return nil
}
func atomicWrite(path string, b []byte, mode os.FileMode) error {
	l, e := windowsParents(path)
	if e != nil {
		return e
	}
	defer l.Close()
	if inspectOwnedLeaf(path) != nil {
		return failure()
	}
	nonce := make([]byte, 16)
	if _, e = rand.Read(nonce); e != nil {
		return failure()
	}
	name := ".opensocrates-" + hex.EncodeToString(nonce) + ".tmp"
	h, e := relativeOpen(l, name, windows.GENERIC_WRITE|windows.DELETE, windows.FILE_CREATE, false)
	if e != nil {
		return failure()
	}
	f := os.NewFile(uintptr(h), "private")
	defer f.Close()
	renamed := false
	defer func() {
		if !renamed {
			deleteHandle(h)
		}
	}()
	if _, e = f.Write(b); e != nil {
		return failure()
	}
	if e = f.Sync(); e != nil {
		return failure()
	}
	if inspectOwnedLeaf(path) != nil {
		return failure()
	}
	if e = renameHandle(h, l.parent, l.name, true); e != nil {
		return e
	}
	renamed = true
	if e = f.Sync(); e != nil {
		return failure()
	}
	return nil
}
func deleteHandle(h windows.Handle) error {
	b := byte(1)
	if windows.SetFileInformationByHandle(h, windows.FileDispositionInfo, &b, 1) != nil {
		return failure()
	}
	return nil
}
func syncParent(path string) error {
	l, e := windowsParents(path)
	if e != nil {
		return e
	}
	defer l.Close()
	return nil
} // Directory handles do not support FlushFileBuffers. Transaction durability uses write-ahead journal files flushed both before and after handle-relative namespace changes; native forced-interruption qualification remains required.
func removePrivate(path string) error {
	l, e := windowsParents(path)
	if e != nil {
		return e
	}
	defer l.Close()
	u, _ := windows.UTF16PtrFromString(nativePath(path))
	h, e := windows.CreateFile(u, windows.DELETE|windows.READ_CONTROL|windows.FILE_READ_ATTRIBUTES, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if e == windows.ERROR_FILE_NOT_FOUND {
		return nil
	}
	if e != nil {
		return failure()
	}
	defer windows.CloseHandle(h)
	if inspectOwnedHandle(h) != nil {
		return failure()
	}
	return deleteHandle(h)
}
func renamePrivate(from, to string) error {
	a, e := windowsParents(from)
	if e != nil {
		return e
	}
	defer a.Close()
	b, e := windowsParents(to)
	if e != nil {
		return e
	}
	defer b.Close()
	if _, e = os.Lstat(to); !os.IsNotExist(e) {
		return failure()
	}
	u, _ := windows.UTF16PtrFromString(nativePath(from))
	h, e := windows.CreateFile(u, windows.GENERIC_WRITE|windows.DELETE|windows.READ_CONTROL|windows.FILE_READ_ATTRIBUTES, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if e != nil {
		return failure()
	}
	defer windows.CloseHandle(h)
	if inspectOwnedHandle(h) != nil {
		return failure()
	}
	if e = renameHandle(h, b.parent, b.name, false); e != nil {
		return e
	}
	var info windows.ByHandleFileInformation
	if windows.GetFileInformationByHandle(h, &info) != nil {
		return failure()
	}
	if info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY == 0 && windows.FlushFileBuffers(h) != nil {
		return failure()
	}
	return nil
}

type windowsLock struct {
	f       *os.File
	overlap windows.Overlapped
	once    sync.Once
}

func (l *windowsLock) Close() error {
	l.once.Do(func() { windows.UnlockFileEx(windows.Handle(l.f.Fd()), 0, 1, 0, &l.overlap); l.f.Close() })
	return nil
}
func acquireLock(path string) (io.Closer, error) {
	f, e := openPrivate(path, os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		return nil, e
	}
	l := &windowsLock{f: f}
	until := time.Now().Add(500 * time.Millisecond)
	for {
		e = windows.LockFileEx(windows.Handle(f.Fd()), windows.LOCKFILE_EXCLUSIVE_LOCK|windows.LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, &l.overlap)
		if e == nil {
			return l, nil
		}
		if e != windows.ERROR_LOCK_VIOLATION {
			f.Close()
			return nil, failure()
		}
		if time.Now().After(until) {
			f.Close()
			return nil, diagnostics.New(diagnostics.Locked, "lock")
		}
		time.Sleep(10 * time.Millisecond)
	}
}
func openLegacy(path string) (*os.File, error) {
	l, e := windowsParents(path)
	if e != nil {
		return nil, e
	}
	defer l.Close()
	h, e := relativeOpen(l, l.name, windows.GENERIC_READ|windows.GENERIC_WRITE|windows.DELETE, windows.FILE_CREATE, false)
	if e != nil {
		return nil, e
	}
	return os.NewFile(uintptr(h), "private"), nil
}
func deleteOpened(path string, f *os.File) error     { return deleteHandle(windows.Handle(f.Fd())) }
func chmodOwned(path string, mode os.FileMode) error { return GuardOwned(path) } // Windows access is defined by the protected DACL, not POSIX mode bits.

func openLegacyRecovery(path string) (*os.File, error) {
	l, e := windowsParents(path)
	if e != nil {
		return nil, e
	}
	defer l.Close()
	h, e := relativeOpen(l, l.name, windows.GENERIC_READ|windows.GENERIC_WRITE|windows.DELETE, windows.FILE_OPEN, false)
	if e != nil {
		return nil, e
	}
	return os.NewFile(uintptr(h), "private"), nil
}
