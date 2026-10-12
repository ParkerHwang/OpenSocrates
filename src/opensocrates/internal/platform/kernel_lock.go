package platform

import (
	"io"
	"sync"
)

// A process-local capability records actual successfully acquired OS locks.
// Explicit npm-lock recovery cannot proceed merely on a caller's assertion.
var heldNativeLocks sync.Map

type kernelLock struct {
	inner io.Closer
	path  string
	once  sync.Once
	err   error
}

func (k *kernelLock) Close() error {
	k.once.Do(func() { heldNativeLocks.CompareAndDelete(k.path, k); k.err = k.inner.Close() })
	return k.err
}
func wrapKernelLock(path string, inner io.Closer) io.Closer {
	k := &kernelLock{path: path, inner: inner}
	heldNativeLocks.Store(path, k)
	return k
}
func nativeLockHeld(path string) bool { _, held := heldNativeLocks.Load(path); return held }
