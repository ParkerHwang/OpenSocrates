//go:build !windows

package platform

import (
	"golang.org/x/sys/unix"
	"os"
)

func mkdirExclusive(path string) error {
	l, e := unixParents(path)
	if e != nil {
		return e
	}
	defer l.Close()
	if e = unix.Mkdirat(l.parent, l.name, 0700); e == unix.EEXIST {
		return os.ErrExist
	} else if e != nil {
		return failure()
	}
	var st unix.Stat_t
	if unix.Fstatat(l.parent, l.name, &st, unix.AT_SYMLINK_NOFOLLOW) != nil || !privateStat(&st) || st.Mode&unix.S_IFMT != unix.S_IFDIR {
		return failure()
	}
	if unix.Fsync(l.parent) != nil {
		return failure()
	}
	return nil
}
func createExclusiveTemp(path string) (*os.File, error) {
	l, e := unixParents(path)
	if e != nil {
		return nil, e
	}
	defer l.Close()
	fd, e := unix.Openat(l.parent, l.name, unix.O_RDWR|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0600)
	if e == unix.EEXIST {
		return nil, os.ErrExist
	}
	if e != nil {
		return nil, failure()
	}
	var st unix.Stat_t
	if unix.Fstat(fd, &st) != nil || !privateStat(&st) || st.Mode&unix.S_IFMT != unix.S_IFREG {
		unix.Close(fd)
		return nil, failure()
	}
	f := os.NewFile(uintptr(fd), path)
	if f.Sync() != nil || unix.Fsync(l.parent) != nil {
		f.Close()
		return nil, failure()
	}
	return f, nil
}
