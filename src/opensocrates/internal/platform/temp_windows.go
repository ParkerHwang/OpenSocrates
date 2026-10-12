//go:build windows

package platform

import (
	"errors"
	"golang.org/x/sys/windows"
	"os"
)

func windowsExists(e error) bool {
	return errors.Is(e, windows.ERROR_FILE_EXISTS) || errors.Is(e, windows.ERROR_ALREADY_EXISTS) || e == windows.STATUS_OBJECT_NAME_COLLISION
}
func mkdirExclusive(path string) error {
	l, e := windowsParents(path)
	if e != nil {
		return e
	}
	defer l.Close()
	h, e := relativeOpen(l, l.name, windows.GENERIC_READ, windows.FILE_CREATE, true)
	if windowsExists(e) {
		return os.ErrExist
	}
	if e != nil {
		return failure()
	}
	defer windows.CloseHandle(h)
	return nil
}
func createExclusiveTemp(path string) (*os.File, error) {
	l, e := windowsParents(path)
	if e != nil {
		return nil, e
	}
	defer l.Close()
	h, e := relativeOpen(l, l.name, windows.GENERIC_READ|windows.GENERIC_WRITE, windows.FILE_CREATE, false)
	if windowsExists(e) {
		return nil, os.ErrExist
	}
	if e != nil {
		return nil, failure()
	}
	f := os.NewFile(uintptr(h), path)
	if f.Sync() != nil {
		f.Close()
		return nil, failure()
	}
	return f, nil
}
