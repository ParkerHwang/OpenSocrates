// Package platform supplies the closed, owner-checked OS boundary. Errors are
// categorical: filesystem paths and process output are never diagnostic text.
package platform

import (
	"crypto/sha256"
	"encoding/hex"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"io"
	"os"
	"path/filepath"
	"strings"
)

type absentError struct{}

func (*absentError) Error() string { return "filesystem: permission" }
func (*absentError) Unwrap() []error {
	return []error{os.ErrNotExist, diagnostics.New(diagnostics.Permission, "filesystem")}
}
func missingError() error { return &absentError{} }

func failure() error        { return diagnostics.New(diagnostics.Permission, "filesystem") }
func invalidArchive() error { return diagnostics.New(diagnostics.Verification, "archive") }

// Guard permits a missing final object but validates every existing ancestor.
// Existing final objects must be private and owned by the current user.
func Guard(path string) error {
	c, err := Lease(path)
	if err != nil {
		return err
	}
	defer c.Close()
	return inspectLeaf(path)
}
func ValidatePath(path string) error { return Guard(path) }
func GuardOwned(path string) error {
	c, err := Lease(path)
	if err != nil {
		return err
	}
	defer c.Close()
	return inspectOwnedLeaf(path)
}
func Lease(path string) (io.Closer, error) { return leaseParents(path) }
func Mkdir(path string) error              { return privateMkdir(path) }
func AtomicWrite(path string, data []byte, mode os.FileMode) error {
	if mode.Perm()&0022 != 0 || mode & ^os.ModePerm != 0 {
		return failure()
	}
	return atomicWrite(path, data, mode)
}

// ExclusiveWrite creates a new owned object and durably writes its contents.
// A failed write preserves the owned partial object for explicit recovery.
func ExclusiveWrite(path string, data []byte, mode os.FileMode) error {
	if mode.Perm()&0022 != 0 || mode&^os.ModePerm != 0 {
		return failure()
	}
	f, e := openOwned(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, mode)
	if e != nil {
		return e
	}
	_, e = f.Write(data)
	if e == nil {
		e = f.Sync()
	}
	closeErr := f.Close()
	if e != nil || closeErr != nil {
		return failure()
	}
	return syncParent(path)
}
func ReadFile(path string, max int64) ([]byte, error) {
	if max < 0 || max > 2<<30 {
		return nil, failure()
	}
	f, err := openPrivate(path, os.O_RDONLY, 0)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	b, err := io.ReadAll(io.LimitReader(f, max+1))
	if err != nil || int64(len(b)) > max {
		return nil, failure()
	}
	return b, nil
}
func ReadOwnedFile(path string, max int64) ([]byte, error) {
	if max < 0 || max > 2<<30 {
		return nil, failure()
	}
	f, err := openOwned(path, os.O_RDONLY, 0)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	b, err := io.ReadAll(io.LimitReader(f, max+1))
	if err != nil || int64(len(b)) > max {
		return nil, failure()
	}
	return b, nil
}
func SHA256File(path string, max int64) (string, error) {
	b, err := ReadOwnedFile(path, max)
	if err != nil {
		return "", err
	}
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:]), nil
}
func Lock(path string) (io.Closer, error) {
	lock, e := acquireLock(path)
	if e != nil {
		return nil, e
	}
	return wrapKernelLock(path, lock), nil
}
func AcquireLock(path string) (func() error, error) {
	l, err := Lock(path)
	if err != nil {
		return nil, err
	}
	return l.Close, nil
}
func Remove(path string) error     { return removePrivate(path) }
func Rename(from, to string) error { return renamePrivate(from, to) }

// BackupVerified never overwrites a recovery copy: modified recovery data must
// remain available for a manual ownership-aware recovery decision.
func BackupVerified(from, to string, max int64) (string, error) {
	b, err := ReadFile(from, max)
	if err != nil {
		return "", err
	}
	if _, err = os.Lstat(to); !os.IsNotExist(err) {
		return "", failure()
	}
	f, err := openPrivate(to, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return "", err
	}
	_, err = f.Write(b)
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil || closeErr != nil {
		return "", failure()
	}
	if err = syncParent(to); err != nil {
		return "", err
	}
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:]), nil
}

// cleanPath intentionally rejects lexical aliases rather than silently
// normalizing them into a different owned object.
func cleanPath(value string) (string, error) {
	if value == "" || strings.ContainsRune(value, 0) || !filepath.IsAbs(value) {
		return "", failure()
	}
	clean := filepath.Clean(value)
	if clean != value && clean+string(os.PathSeparator) != value {
		return "", failure()
	}
	return clean, nil
}
