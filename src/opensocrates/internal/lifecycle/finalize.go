package lifecycle

import (
	"context"
	"encoding/json"
	"path/filepath"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

// FinalizeCommitted irreversibly discards only verified owned recovery payload.
// Callers use this for an explicitly requested purge, never ordinary updates.
func (e *Engine) FinalizeCommitted(ctx context.Context, id string) error {
	if !validID.MatchString(id) {
		return diagnostics.New(diagnostics.Verification, "cleanup")
	}
	unlock, err := e.lock()
	if err != nil {
		return err
	}
	defer unlock()
	b, err := platform.ReadFile(e.journalPath(id), 8<<20)
	if err != nil {
		return err
	}
	if _, err := contracts.Decode(b); err != nil {
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	var j Journal
	if json.Unmarshal(b, &j) != nil || j.ID != id || j.Schema != JournalSchema || e.validateJournal(j) != nil {
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	return e.finalizeHeld(ctx, &j)
}
func (e *Engine) finalizeHeld(ctx context.Context, j *Journal) error {
	if j.Stage == "finalized" {
		return nil
	}
	if j.Stage != "committed" && j.Stage != "cleaning" {
		return diagnostics.New(diagnostics.Verification, "cleanup-stage")
	}
	// Check all targets and remaining recovery copies before deleting anything.
	for _, f := range j.Files {
		actual, err := Inspect(f.Target)
		if err != nil {
			return err
		}
		if !Equal(actual, f.After) {
			return diagnostics.New(diagnostics.Verification, "cleanup-target")
		}
		backup, err := Inspect(f.Backup)
		if err != nil {
			return err
		}
		if backup.Exists && !Equal(backup, f.Before) {
			return diagnostics.New(diagnostics.Verification, "cleanup-backup")
		}
		if f.Before.Exists && !backup.Exists && f.Phase != "cleanup-intent" && f.Phase != "cleaned" {
			return diagnostics.New(diagnostics.Verification, "cleanup-backup")
		}
		staged, err := Inspect(f.Staged)
		if err != nil {
			return err
		}
		if staged.Exists && !Equal(staged, f.After) {
			return diagnostics.New(diagnostics.Verification, "cleanup-candidate")
		}
	}
	j.Stage = "cleaning"
	if err := e.save(j); err != nil {
		return err
	}
	for i := range j.Files {
		if ctx.Err() != nil {
			return diagnostics.New(diagnostics.Activation, "cleanup-cancelled")
		}
		f := &j.Files[i]
		if f.Phase == "cleaned" {
			continue
		}
		lease, err := platform.Lease(filepath.Join(filepath.Dir(f.Target), ".lease"))
		if err != nil {
			return err
		}
		err = func() error {
			defer lease.Close()
			f.Phase = "cleanup-intent"
			if err := e.save(j); err != nil {
				return err
			}
			for _, object := range []struct {
				path     string
				expected Snapshot
			}{{f.Backup, f.Before}, {f.Staged, f.After}} {
				actual, err := Inspect(object.path)
				if err != nil {
					return err
				}
				if actual.Exists {
					if !Equal(actual, object.expected) {
						return diagnostics.New(diagnostics.Verification, "cleanup-modified")
					}
					if err := platform.RemoveTree(object.path); err != nil {
						return err
					}
				}
			}
			f.Phase = "cleaned"
			return e.save(j)
		}()
		if err != nil {
			return err
		}
	}
	j.Stage = "finalized"
	return e.save(j)
}

// FinalizeCommittedHeld is for a compound explicitly authorized purge that
// already holds Engine.Lock. It must finish one config operation before an
// external host operation legitimately changes that same configuration.
func (e *Engine) FinalizeCommittedHeld(ctx context.Context, id string) error {
	if !validID.MatchString(id) {
		return diagnostics.New(diagnostics.Verification, "cleanup")
	}
	b, err := platform.ReadFile(e.journalPath(id), 8<<20)
	if err != nil {
		return err
	}
	if _, err := contracts.Decode(b); err != nil {
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	var j Journal
	if json.Unmarshal(b, &j) != nil || j.ID != id || j.Schema != JournalSchema || e.validateJournal(j) != nil {
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	return e.finalizeHeld(ctx, &j)
}
