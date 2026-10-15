package lifecycle

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

func (e *Engine) readJournal(id string) (Journal, error) {
	b, err := platform.ReadFile(e.journalPath(id), 8<<20)
	if err != nil {
		return Journal{}, err
	}
	var j Journal
	if _, err := contracts.Decode(b); err != nil {
		return j, diagnostics.New(diagnostics.Verification, "journal")
	}
	if json.Unmarshal(b, &j) != nil || j.Schema != JournalSchema || j.ID != id || e.validateJournal(j) != nil {
		return j, diagnostics.New(diagnostics.Verification, "journal")
	}
	return j, nil
}

// Recover reclaims only the exact dead Go lock bound to this private journal.
// Unknown npm locks and live/modified Go locks remain untouched. Normal
// operations never reclaim locks; this path requires explicit recovery.
func (e *Engine) Recover(ctx context.Context, id string) (Journal, error) {
	if !validID.MatchString(id) {
		return Journal{}, diagnostics.New(diagnostics.Verification, "recovery")
	}
	if err := platform.Mkdir(e.StateDir); err != nil {
		return Journal{}, err
	}
	if err := platform.Mkdir(filepath.Join(e.StateDir, "transactions")); err != nil {
		return Journal{}, err
	}
	unlock, err := platform.AcquireLock(filepath.Join(e.StateDir, "native-lifecycle.lock"))
	if err != nil {
		return Journal{}, err
	}
	defer unlock()
	j, err := e.readJournal(id)
	if err != nil {
		return j, err
	}
	path := filepath.Join(e.StateDir, "lifecycle.lock")
	if _, err := os.Lstat(path); err == nil {
		if j.LockIdentity == nil {
			return j, diagnostics.New(diagnostics.Locked, "unbound-legacy-lock")
		}
		if err := platform.RecoverLegacyLock(path, *j.LockIdentity); err != nil {
			return j, err
		}
	} else if !os.IsNotExist(err) {
		return j, diagnostics.New(diagnostics.Permission, "legacy-lock")
	}
	// Bind the replacement before creating it, so a second forced death during
	// recovery cannot strand a new nonce without a corresponding journal.
	identity, err := platform.NewLegacyLockIdentity()
	if err != nil {
		return j, err
	}
	j.LockIdentity = &identity
	if err := e.save(&j); err != nil {
		return j, err
	}
	lock, err := platform.LegacyLockWithIdentity(path, identity)
	if err != nil {
		return j, err
	}
	defer lock.Close()
	if j.Stage == "rolled-back" {
		return j, nil
	}
	if j.Stage == "cleaning" {
		return j, e.finalizeHeld(ctx, &j)
	}
	if j.Stage == "finalized" {
		return j, diagnostics.New(diagnostics.Unsupported, "recovery-finalized")
	}
	return j, e.rollback(ctx, &j)
}
