//go:build !windows

package platform

import (
	"crypto/rand"
	"encoding/hex"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"golang.org/x/sys/unix"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

type unixLease struct {
	fds    []int
	parent int
	name   string
	once   sync.Once
}

func (l *unixLease) Close() error {
	l.once.Do(func() {
		for i := len(l.fds) - 1; i >= 0; i-- {
			unix.Close(l.fds[i])
		}
	})
	return nil
}
func systemAliases(path string) string {
	if runtime.GOOS == "darwin" {
		for _, p := range []string{"/tmp", "/var", "/etc"} {
			if path == p || strings.HasPrefix(path, p+"/") {
				if target, err := os.Readlink(p); err == nil && target == "private"+p {
					return "/private" + path
				}
			}
		}
	}
	return path
}
func unixParents(path string) (*unixLease, error) {
	path, err := cleanPath(path)
	if err != nil {
		return nil, err
	}
	path = systemAliases(path)
	parts := strings.Split(strings.TrimPrefix(filepath.Dir(path), "/"), "/")
	fd, err := unix.Open("/", unix.O_RDONLY|unix.O_DIRECTORY|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, failure()
	}
	l := &unixLease{fds: []int{fd}, parent: fd, name: filepath.Base(path)}
	for _, part := range parts {
		if part == "" {
			continue
		}
		child, e := unix.Openat(l.parent, part, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
		if e != nil {
			l.Close()
			if e == unix.ENOENT {
				return nil, missingError()
			}
			return nil, failure()
		}
		l.fds = append(l.fds, child)
		l.parent = child
		var st unix.Stat_t
		if unix.Fstat(child, &st) != nil || (st.Uid != 0 && st.Uid != uint32(os.Getuid())) || (st.Mode&0022 != 0 && !(st.Uid == 0 && st.Mode&unix.S_ISVTX != 0)) {
			l.Close()
			return nil, failure()
		}
	}
	return l, nil
}
func leaseParents(path string) (io.Closer, error) { return unixParents(path) }
func ownedStat(st *unix.Stat_t) bool {
	return st.Uid == uint32(os.Getuid()) && st.Mode&0022 == 0 && (st.Mode&unix.S_IFMT == unix.S_IFREG || st.Mode&unix.S_IFMT == unix.S_IFDIR) && (st.Mode&unix.S_IFMT != unix.S_IFREG || st.Nlink == 1)
}
func privateStat(st *unix.Stat_t) bool   { return ownedStat(st) && st.Mode&0077 == 0 }
func inspectLeaf(path string) error      { return inspectUnixLeaf(path, true) }
func inspectOwnedLeaf(path string) error { return inspectUnixLeaf(path, false) }
func inspectUnixLeaf(path string, private bool) error {
	l, err := unixParents(path)
	if err != nil {
		return err
	}
	defer l.Close()
	var st unix.Stat_t
	err = unix.Fstatat(l.parent, l.name, &st, unix.AT_SYMLINK_NOFOLLOW)
	if err == unix.ENOENT {
		return nil
	}
	if err != nil || !ownedStat(&st) || (private && !privateStat(&st)) {
		return failure()
	}
	return nil
}
func privateMkdir(path string) error {
	path, err := cleanPath(path)
	if err != nil {
		return err
	}
	path = systemAliases(path)
	if info, statErr := os.Lstat(path); statErr == nil {
		if !info.IsDir() {
			return failure()
		}
		return GuardOwned(path)
	} else if !os.IsNotExist(statErr) {
		return failure()
	}
	parent := filepath.Dir(path)
	if _, err = os.Lstat(parent); os.IsNotExist(err) {
		if err = privateMkdir(parent); err != nil {
			return err
		}
	}
	l, err := unixParents(path)
	if err != nil {
		return err
	}
	defer l.Close()
	if err = unix.Mkdirat(l.parent, l.name, 0700); err != nil && err != unix.EEXIST {
		return failure()
	}
	if err = inspectLeaf(path); err != nil {
		return err
	}
	if unix.Fsync(l.parent) != nil {
		return failure()
	}
	return nil
}
func openPrivate(path string, flags int, mode os.FileMode) (*os.File, error) {
	return unixOpen(path, flags, mode, true)
}
func openOwned(path string, flags int, mode os.FileMode) (*os.File, error) {
	return unixOpen(path, flags, mode, false)
}
func unixOpen(path string, flags int, mode os.FileMode, private bool) (*os.File, error) {
	l, err := unixParents(path)
	if err != nil {
		return nil, err
	}
	defer l.Close()
	fd, err := unix.Openat(l.parent, l.name, flags|unix.O_NOFOLLOW|unix.O_CLOEXEC, uint32(mode.Perm()))
	if err == unix.ENOENT {
		return nil, missingError()
	}
	if err != nil {
		return nil, failure()
	}
	var st unix.Stat_t
	if unix.Fstat(fd, &st) != nil || (!ownedStat(&st) || (private && !privateStat(&st))) || st.Mode&unix.S_IFMT != unix.S_IFREG {
		unix.Close(fd)
		return nil, failure()
	}
	return os.NewFile(uintptr(fd), "private"), nil
}
func atomicWrite(path string, b []byte, mode os.FileMode) error {
	l, err := unixParents(path)
	if err != nil {
		return err
	}
	defer l.Close()
	var st unix.Stat_t
	e := unix.Fstatat(l.parent, l.name, &st, unix.AT_SYMLINK_NOFOLLOW)
	if e != unix.ENOENT && (e != nil || !ownedStat(&st) || st.Mode&unix.S_IFMT != unix.S_IFREG) {
		return failure()
	}
	nonce := make([]byte, 16)
	if _, err = rand.Read(nonce); err != nil {
		return failure()
	}
	tmp := ".opensocrates-" + hex.EncodeToString(nonce) + ".tmp"
	fd, e := unix.Openat(l.parent, tmp, unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC, uint32(mode))
	if e != nil {
		return failure()
	}
	f := os.NewFile(uintptr(fd), "private")
	defer f.Close()
	defer unix.Unlinkat(l.parent, tmp, 0)
	if _, e = f.Write(b); e != nil {
		return failure()
	}
	if e = f.Sync(); e != nil {
		return failure()
	}
	var current unix.Stat_t
	e = unix.Fstatat(l.parent, l.name, &current, unix.AT_SYMLINK_NOFOLLOW)
	if e != unix.ENOENT && (e != nil || !ownedStat(&current) || current.Mode&unix.S_IFMT != unix.S_IFREG) {
		return failure()
	}
	if e == nil && (st.Ino != current.Ino || st.Dev != current.Dev) {
		return failure()
	}
	if e = unix.Renameat(l.parent, tmp, l.parent, l.name); e != nil {
		return failure()
	}
	if unix.Fsync(l.parent) != nil {
		return failure()
	}
	return nil
}
func syncParent(path string) error {
	l, err := unixParents(path)
	if err != nil {
		return err
	}
	defer l.Close()
	if unix.Fsync(l.parent) != nil {
		return failure()
	}
	return nil
}
func removePrivate(path string) error {
	l, err := unixParents(path)
	if err != nil {
		return err
	}
	defer l.Close()
	var st unix.Stat_t
	e := unix.Fstatat(l.parent, l.name, &st, unix.AT_SYMLINK_NOFOLLOW)
	if e == unix.ENOENT {
		return nil
	}
	if e != nil || !ownedStat(&st) {
		return failure()
	}
	flags := 0
	if st.Mode&unix.S_IFMT == unix.S_IFDIR {
		flags = unix.AT_REMOVEDIR
	}
	if unix.Unlinkat(l.parent, l.name, flags) != nil {
		return failure()
	}
	return syncParent(path)
}
func renamePrivate(from, to string) error {
	a, e := unixParents(from)
	if e != nil {
		return e
	}
	defer a.Close()
	b, e := unixParents(to)
	if e != nil {
		return e
	}
	defer b.Close()
	if GuardOwned(from) != nil {
		return failure()
	}
	var st unix.Stat_t
	if e = unix.Fstatat(b.parent, b.name, &st, unix.AT_SYMLINK_NOFOLLOW); e != unix.ENOENT {
		return failure()
	}
	if unix.Renameat(a.parent, a.name, b.parent, b.name) != nil {
		return failure()
	}
	if unix.Fsync(a.parent) != nil || unix.Fsync(b.parent) != nil {
		return failure()
	}
	return nil
}

type unixLock struct {
	f    *os.File
	once sync.Once
}

func (l *unixLock) Close() error {
	l.once.Do(func() { unix.Flock(int(l.f.Fd()), unix.LOCK_UN); l.f.Close() })
	return nil
}
func acquireLock(path string) (io.Closer, error) {
	f, e := openPrivate(path, os.O_RDWR|os.O_CREATE, 0600)
	if e != nil {
		return nil, e
	}
	until := time.Now().Add(500 * time.Millisecond)
	for {
		e = unix.Flock(int(f.Fd()), unix.LOCK_EX|unix.LOCK_NB)
		if e == nil {
			return &unixLock{f: f}, nil
		}
		if e != unix.EWOULDBLOCK && e != unix.EAGAIN {
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
	return openPrivate(path, os.O_RDWR|os.O_CREATE|os.O_EXCL, 0600)
}
func deleteOpened(path string, f *os.File) error {
	l, e := unixParents(path)
	if e != nil {
		return e
	}
	defer l.Close()
	var opened, current unix.Stat_t
	if unix.Fstat(int(f.Fd()), &opened) != nil || unix.Fstatat(l.parent, l.name, &current, unix.AT_SYMLINK_NOFOLLOW) != nil || opened.Dev != current.Dev || opened.Ino != current.Ino || !privateStat(&current) {
		return failure()
	}
	if unix.Unlinkat(l.parent, l.name, 0) != nil || unix.Fsync(l.parent) != nil {
		return failure()
	}
	return nil
}
func chmodOwned(path string, mode os.FileMode) error {
	if mode.Perm()&0022 != 0 {
		return failure()
	}
	l, e := unixParents(path)
	if e != nil {
		return e
	}
	defer l.Close()
	fd, e := unix.Openat(l.parent, l.name, unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if e != nil {
		return failure()
	}
	defer unix.Close(fd)
	var st unix.Stat_t
	if unix.Fstat(fd, &st) != nil || !ownedStat(&st) {
		return failure()
	}
	if unix.Fchmod(fd, uint32(mode.Perm())) != nil || unix.Fsync(fd) != nil {
		return failure()
	}
	return nil
}

func openLegacyRecovery(path string) (*os.File, error) { return openPrivate(path, os.O_RDWR, 0) }
