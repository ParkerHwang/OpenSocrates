package platform

import (
	"os"
	"path/filepath"
)

// RemoveTree only removes owned, non-writable-by-others regular files and
// directories. A foreign or modified special entry stops removal in place.
// The lifecycle caller must compare its manifest before requesting deletion.
func RemoveTree(path string) error {
	if e := GuardOwned(path); e != nil {
		return e
	}
	info, e := os.Lstat(path)
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil {
		return failure()
	}
	if !info.IsDir() {
		return Remove(path)
	}
	lease, e := Lease(filepath.Join(path, ".lease"))
	if e != nil {
		return e
	}
	defer lease.Close()
	children, e := os.ReadDir(path)
	if e != nil {
		return failure()
	}
	for _, child := range children {
		if e = RemoveTree(filepath.Join(path, child.Name())); e != nil {
			return e
		}
	}
	lease.Close()
	return Remove(path)
}
