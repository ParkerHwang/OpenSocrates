package platform

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"
)

const LegacyLockSchema = "opensocrates.legacy-lock/1.0.0"

type legacyDocument struct {
	Schema    string `json:"schema"`
	Nonce     string `json:"nonce"`
	PID       int    `json:"pid"`
	StartedAt string `json:"startedAt"`
}

// LockIdentity is bound to a durable transaction journal before any mutation.
// SHA256 covers exact bytes, including fields ignored by the npm protocol.
type LockIdentity struct {
	Schema    string `json:"schema"`
	Nonce     string `json:"nonce"`
	PID       int    `json:"pid"`
	StartedAt string `json:"startedAt"`
	SHA256    string `json:"sha256"`
}

var heldLegacyLocks sync.Map

type legacyLock struct {
	path     string
	f        *os.File
	lease    io.Closer
	identity LockIdentity
	mu       sync.Mutex
	once     sync.Once
	err      error
}

func (l *legacyLock) readIdentity() (LockIdentity, error) {
	if _, e := l.f.Seek(0, io.SeekStart); e != nil {
		return LockIdentity{}, legacyFailure()
	}
	b, e := io.ReadAll(io.LimitReader(l.f, 4097))
	if e != nil || len(b) > 4096 {
		return LockIdentity{}, legacyFailure()
	}
	return lockIdentity(b)
}
func (l *legacyLock) Close() error {
	l.once.Do(func() {
		l.mu.Lock()
		defer l.mu.Unlock()
		actual, e := l.readIdentity()
		if e != nil || actual != l.identity {
			l.err = legacyFailure()
		} else {
			l.err = deleteOpened(l.path, l.f)
		}
		heldLegacyLocks.CompareAndDelete(l.path, l)
		l.f.Close()
		l.lease.Close()
	})
	return l.err
}
func legacyFailure() error { return diagnostics.New(diagnostics.Locked, "legacy_recovery") }

// LegacyLock speaks the npm installer's exclusive-create protocol. A
// preexisting lock is never removed, even if its PID appears stale or absent.
// The Go schema and nonce permit explicit journal-bound crash recovery later.
func identityBytes(identity LockIdentity) ([]byte, error) {
	b, e := json.Marshal(legacyDocument{identity.Schema, identity.Nonce, identity.PID, identity.StartedAt})
	if e != nil {
		return nil, legacyFailure()
	}
	return append(b, '\n'), nil
}
func NewLegacyLockIdentity() (LockIdentity, error) {
	nonce := make([]byte, 16)
	if _, e := rand.Read(nonce); e != nil {
		return LockIdentity{}, failure()
	}
	d := LockIdentity{Schema: LegacyLockSchema, Nonce: hex.EncodeToString(nonce), PID: os.Getpid(), StartedAt: time.Now().UTC().Format(time.RFC3339Nano)}
	b, e := identityBytes(d)
	if e != nil {
		return LockIdentity{}, e
	}
	return lockIdentity(b)
}
func LegacyLock(path string) (io.Closer, error) {
	identity, e := NewLegacyLockIdentity()
	if e != nil {
		return nil, e
	}
	return LegacyLockWithIdentity(path, identity)
}

// LegacyLockWithIdentity creates exact journal-prebound bytes. Recovery may
// persist a replacement identity BEFORE exclusive creation, so a second crash
// cannot strand a newly created lock with an unmatched journal identity.
func LegacyLockWithIdentity(path string, identity LockIdentity) (io.Closer, error) {
	if identity.PID != os.Getpid() {
		return nil, legacyFailure()
	}
	b, e := identityBytes(identity)
	if e != nil {
		return nil, e
	}
	checked, e := lockIdentity(b)
	if e != nil || checked != identity {
		return nil, legacyFailure()
	}
	lease, e := Lease(path)
	if e != nil {
		return nil, e
	}
	f, e := openLegacy(path)
	if e != nil {
		lease.Close()
		return nil, diagnostics.New(diagnostics.Locked, "legacy_lock")
	}
	l := &legacyLock{path: path, f: f, lease: lease, identity: identity}
	_, e = f.Write(b)
	if e == nil {
		e = f.Sync()
	}
	if e == nil {
		e = syncParent(path)
	}
	if e != nil {
		l.Close()
		return nil, failure()
	}
	heldLegacyLocks.Store(path, l)
	return l, nil
}
func lockIdentity(data []byte) (LockIdentity, error) {
	var d legacyDocument
	if decodeClosed(data, &d) != nil || d.Schema != LegacyLockSchema || !operationPattern.MatchString(d.Nonce) || d.PID < 1 {
		return LockIdentity{}, legacyFailure()
	}
	if parsed, e := time.Parse(time.RFC3339Nano, d.StartedAt); e != nil || parsed.IsZero() {
		return LockIdentity{}, legacyFailure()
	}
	h := sha256.Sum256(data)
	return LockIdentity{d.Schema, d.Nonce, d.PID, d.StartedAt, hex.EncodeToString(h[:])}, nil
}
func LegacyLockIdentity(path string) (LockIdentity, error) {
	if held, ok := heldLegacyLocks.Load(path); ok {
		l := held.(*legacyLock)
		l.mu.Lock()
		defer l.mu.Unlock()
		return l.readIdentity()
	}
	b, e := ReadFile(path, 4096)
	if e != nil {
		return LockIdentity{}, e
	}
	return lockIdentity(b)
}
func LegacyLockNonce(path string) (string, error) {
	identity, e := LegacyLockIdentity(path)
	return identity.Nonce, e
}

// RecoverLegacyLock is an explicit recovery action, never ordinary stale-lock
// cleanup. The caller must hold this installation's native-lifecycle.lock.
// Only exact private Go lock bytes matching a journal and a positively exited
// owner can be reclaimed. Old npm, live/unknown PIDs and changed files remain.
func RecoverLegacyLock(path string, expected LockIdentity) error {
	if !nativeLockHeld(filepath.Join(filepath.Dir(path), "native-lifecycle.lock")) {
		return legacyFailure()
	}
	if expected.Schema != LegacyLockSchema || !operationPattern.MatchString(expected.Nonce) || !digestPattern.MatchString(expected.SHA256) || expected.PID < 1 {
		return legacyFailure()
	}
	lease, e := Lease(path)
	if e != nil {
		return e
	}
	defer lease.Close()
	f, e := openLegacyRecovery(path)
	if e != nil {
		return legacyFailure()
	}
	defer f.Close()
	b, e := io.ReadAll(io.LimitReader(f, 4097))
	if e != nil || len(b) > 4096 {
		return legacyFailure()
	}
	actual, e := lockIdentity(b)
	if e != nil || actual != expected {
		return legacyFailure()
	}
	alive, e := ProcessAlive(actual.PID)
	if e != nil || alive {
		return legacyFailure()
	}
	// Re-read the same held object after the process check; content changes are
	// refused. deleteOpened additionally binds final namespace identity to fd.
	if _, e = f.Seek(0, io.SeekStart); e != nil {
		return legacyFailure()
	}
	b, e = io.ReadAll(io.LimitReader(f, 4097))
	if e != nil || len(b) > 4096 {
		return legacyFailure()
	}
	current, e := lockIdentity(b)
	if e != nil || current != actual {
		return legacyFailure()
	}
	if e = deleteOpened(path, f); e != nil {
		return legacyFailure()
	}
	return nil
}
