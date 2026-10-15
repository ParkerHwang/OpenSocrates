//go:build darwin || linux

package compat

import (
	"golang.org/x/sys/unix"
	"os"
	"path/filepath"
)

func contextAvailable() bool { return true }
func contextFlags(directory bool) int {
	flags := unix.O_RDONLY | unix.O_CLOEXEC | unix.O_NOFOLLOW | unix.O_NONBLOCK
	if directory {
		flags |= unix.O_DIRECTORY
	}
	return flags
}
func checkContextFile(fd int, name string, directory bool) (*os.File, error) {
	f := os.NewFile(uintptr(fd), name)
	info, err := f.Stat()
	if err != nil || directory && !info.IsDir() || !directory && !info.Mode().IsRegular() {
		f.Close()
		return nil, os.ErrPermission
	}
	return f, nil
}
func openExactContext(path string, directory bool) (*os.File, error) {
	if !filepath.IsAbs(path) || len(path) > 32768 {
		return nil, os.ErrPermission
	}
	// Resolve only the authorized handle's parent. The leaf is always opened
	// relative to a retained parent descriptor with O_NOFOLLOW.
	parent, err := filepath.EvalSymlinks(filepath.Dir(path))
	if err != nil {
		return nil, os.ErrPermission
	}
	p, err := unix.Open(parent, contextFlags(true), 0)
	if err != nil {
		return nil, os.ErrPermission
	}
	defer unix.Close(p)
	fd, err := unix.Openat(p, filepath.Base(path), contextFlags(directory), 0)
	if err != nil {
		return nil, os.ErrPermission
	}
	return checkContextFile(fd, path, directory)
}
func openBeneathContext(root string, parts []string, directory bool) (*os.File, error) {
	if filepath.Clean(root) == string(os.PathSeparator) {
		return nil, os.ErrPermission
	}
	f, err := openExactContext(root, true)
	if err != nil {
		return nil, err
	}
	for i, p := range parts {
		fd, err := unix.Openat(int(f.Fd()), p, contextFlags(directory || i < len(parts)-1), 0)
		f.Close()
		if err != nil {
			return nil, os.ErrPermission
		}
		f, err = checkContextFile(fd, p, directory || i < len(parts)-1)
		if err != nil {
			return nil, err
		}
	}
	return f, nil
}
