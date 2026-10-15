// Package lifecycle implements durable install, update and removal transactions.
package lifecycle

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
)

const JournalSchema = "opensocrates.lifecycle-journal/1.0.0"

var validID = regexp.MustCompile(`^[a-f0-9]{32}$`)

type Mutation struct {
	Target   string    `json:"target"`
	Source   string    `json:"source,omitempty"`
	Remove   bool      `json:"remove,omitempty"`
	Expected *Snapshot `json:"expected,omitempty"`
}
type Plan struct {
	ID                      string                `json:"id"`
	Action                  string                `json:"action"`
	Host                    string                `json:"host"`
	Scope                   string                `json:"scope"`
	Version                 string                `json:"version,omitempty"`
	Mutations               []Mutation            `json:"mutations"`
	Registrations           []registration.Change `json:"registrations,omitempty"`
	RegistrationBeforeFiles bool                  `json:"registration_before_files"`
}
type FileChange struct {
	Target string   `json:"target"`
	Staged string   `json:"staged"`
	Backup string   `json:"backup"`
	Before Snapshot `json:"before"`
	After  Snapshot `json:"after"`
	Phase  string   `json:"phase"`
}
type Journal struct {
	Schema                  string                 `json:"schema"`
	ID                      string                 `json:"id"`
	Action                  string                 `json:"action"`
	Host                    string                 `json:"host"`
	Scope                   string                 `json:"scope"`
	Version                 string                 `json:"version,omitempty"`
	Stage                   string                 `json:"stage"`
	Files                   []FileChange           `json:"files"`
	Registrations           []registration.Change  `json:"registrations,omitempty"`
	LockIdentity            *platform.LockIdentity `json:"lock_identity,omitempty"`
	RegistrationBeforeFiles bool                   `json:"registration_before_files"`
	RegistrationStarted     bool                   `json:"registration_started"`
	CreatedAt               string                 `json:"created_at"`
}
type Engine struct {
	StateDir      string
	Registrations map[string]registration.Adapter // Fault is reserved for deterministic interruption acceptance fixtures.
	Fault         func(string) error
}

func NewID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}
func (e *Engine) journalPath(id string) string {
	return filepath.Join(e.StateDir, "transactions", id+".json")
}
func (e *Engine) save(j *Journal) error {
	path := filepath.Join(e.StateDir, "lifecycle.lock")
	if _, stat := os.Lstat(path); stat == nil {
		identity, err := platform.LegacyLockIdentity(path)
		if err != nil {
			return err
		}
		if identity.PID != os.Getpid() {
			return diagnostics.New(diagnostics.Locked, "journal-owner")
		}
		j.LockIdentity = &identity
	} else if !os.IsNotExist(stat) {
		return diagnostics.New(diagnostics.Permission, "journal-owner")
	}
	b, err := json.MarshalIndent(j, "", "  ")
	if err != nil {
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	b = append(b, '\n')
	if err := platform.AtomicWrite(e.journalPath(j.ID), b, 0600); err != nil {
		return err
	}
	if e.Fault != nil {
		return e.Fault(j.Stage)
	}
	return nil
}
func (e *Engine) lock() (func() error, error) {
	if err := platform.Mkdir(e.StateDir); err != nil {
		return nil, err
	}
	if err := platform.Mkdir(filepath.Join(e.StateDir, "transactions")); err != nil {
		return nil, err
	}
	unlock, err := platform.AcquireLock(filepath.Join(e.StateDir, "native-lifecycle.lock"))
	if err != nil {
		return nil, err
	}
	legacy, err := platform.LegacyLock(filepath.Join(e.StateDir, "lifecycle.lock"))
	if err != nil {
		unlock()
		return nil, err
	}
	return func() error {
		a := legacy.Close()
		b := unlock()
		if a != nil {
			return a
		}
		return b
	}, nil
}
func (e *Engine) Execute(ctx context.Context, p Plan) (Journal, error) {
	unlock, err := e.lock()
	if err != nil {
		return Journal{}, err
	}
	defer unlock()
	return e.executeHeld(ctx, p)
}

// ExecuteHeld is for adoption that already owns the same installation lock.
func (e *Engine) ExecuteHeld(ctx context.Context, p Plan) (Journal, error) {
	return e.executeHeld(ctx, p)
}
func (e *Engine) executeHeld(ctx context.Context, p Plan) (Journal, error) {
	if p.ID == "" {
		p.ID = NewID()
	}
	if !validID.MatchString(p.ID) || len(p.Mutations) == 0 {
		return Journal{}, diagnostics.New(diagnostics.Verification, "plan")
	}
	if _, err := os.Lstat(e.journalPath(p.ID)); err == nil {
		return Journal{}, diagnostics.New(diagnostics.Locked, "journal")
	}
	j := Journal{Schema: JournalSchema, ID: p.ID, Action: p.Action, Host: p.Host, Scope: p.Scope, Version: p.Version, Stage: "preparing", CreatedAt: time.Now().UTC().Format(time.RFC3339), Registrations: p.Registrations, RegistrationBeforeFiles: p.RegistrationBeforeFiles, Files: []FileChange{}}
	// Targets must be disjoint: a nested rename could invalidate another mutation.
	for i, m := range p.Mutations {
		if !filepath.IsAbs(m.Target) || m.Source == m.Target {
			return j, diagnostics.New(diagnostics.Verification, "plan")
		}
		for k := 0; k < i; k++ {
			a := p.Mutations[k].Target
			if contained(a, m.Target) || contained(m.Target, a) {
				return j, diagnostics.New(diagnostics.Verification, "plan")
			}
		}
	}
	for _, change := range j.Registrations {
		a := e.Registrations[change.Host]
		if a == nil {
			return j, diagnostics.New(diagnostics.Unsupported, "registration")
		}
		if err := a.Verify(ctx, change.Before); err != nil {
			return j, err
		}
	}
	for _, m := range p.Mutations {
		before, err := Inspect(m.Target)
		if err != nil {
			return j, err
		}
		if m.Expected == nil && before.Exists {
			return j, diagnostics.New(diagnostics.Verification, "ownership")
		}
		if m.Expected != nil && !Equal(before, *m.Expected) {
			return j, diagnostics.New(diagnostics.Verification, "ownership")
		}
		after := snapshot(false, []Entry{})
		if !m.Remove {
			if m.Source == "" {
				return j, diagnostics.New(diagnostics.Verification, "plan")
			}
			after, err = Inspect(m.Source)
			if err != nil {
				return j, err
			}
			if !after.Exists {
				return j, diagnostics.New(diagnostics.Verification, "source")
			}
		}
		sibling := filepath.Join(filepath.Dir(m.Target), ".opensocrates-"+p.ID+"-"+filepath.Base(m.Target))
		j.Files = append(j.Files, FileChange{Target: m.Target, Staged: sibling + "-candidate", Backup: sibling + "-backup", Before: before, After: after, Phase: "planned"})
	}
	if err := e.save(&j); err != nil {
		return j, err
	}
	for i, m := range p.Mutations {
		if !m.Remove {
			if err := platform.Mkdir(filepath.Dir(m.Target)); err != nil {
				return j, err
			}
			if err := copyVerified(m.Source, j.Files[i].Staged, j.Files[i].After); err != nil {
				return j, err
			}
		}
		j.Files[i].Phase = "prepared"
		if err := e.save(&j); err != nil {
			return j, err
		}
	}
	j.Stage = "prepared"
	if err := e.save(&j); err != nil {
		return j, err
	}
	err := e.apply(ctx, &j)
	if err != nil {
		if rollback := e.rollback(ctx, &j); rollback != nil {
			return j, rollback
		}
		return j, err
	}
	return j, nil
}
func contained(a, b string) bool {
	r, e := filepath.Rel(a, b)
	return e == nil && (r == "." || r != ".." && !filepath.IsAbs(r) && len(r) > 0 && r[:min(3, len(r))] != "../" && r[:min(3, len(r))] != "..\\")
}
func (e *Engine) apply(ctx context.Context, j *Journal) error {
	j.Stage = "applying"
	if err := e.save(j); err != nil {
		return err
	}
	if j.RegistrationBeforeFiles {
		if err := e.applyRegistrations(ctx, j); err != nil {
			return err
		}
	}
	for i := range j.Files {
		if err := ctx.Err(); err != nil {
			return diagnostics.New(diagnostics.Activation, "cancelled")
		}
		f := &j.Files[i]
		if err := platform.Mkdir(filepath.Dir(f.Target)); err != nil {
			return err
		}
		lease, err := platform.Lease(filepath.Join(filepath.Dir(f.Target), ".lease"))
		if err != nil {
			return err
		}
		err = func() error {
			defer lease.Close()
			current, err := Inspect(f.Target)
			if err != nil {
				return err
			}
			if !Equal(current, f.Before) {
				return diagnostics.New(diagnostics.Verification, "apply")
			}
			backup, err := Inspect(f.Backup)
			if err != nil {
				return err
			}
			if backup.Exists {
				return diagnostics.New(diagnostics.Verification, "backup")
			}
			f.Phase = "backup-intent"
			if err := e.save(j); err != nil {
				return err
			}
			if f.Before.Exists {
				if err := platform.Rename(f.Target, f.Backup); err != nil {
					return err
				}
			}
			f.Phase = "activate-intent"
			if err := e.save(j); err != nil {
				return err
			}
			if f.After.Exists {
				staged, err := Inspect(f.Staged)
				if err != nil {
					return err
				}
				if !Equal(staged, f.After) {
					return diagnostics.New(diagnostics.Verification, "candidate")
				}
				if err := platform.Rename(f.Staged, f.Target); err != nil {
					return err
				}
			}
			f.Phase = "applied"
			return e.save(j)
		}()
		if err != nil {
			return err
		}
	}
	if !j.RegistrationBeforeFiles {
		if err := e.applyRegistrations(ctx, j); err != nil {
			return err
		}
	}
	j.Stage = "verifying"
	if err := e.save(j); err != nil {
		return err
	}
	for _, f := range j.Files {
		actual, err := Inspect(f.Target)
		if err != nil {
			return err
		}
		if !Equal(actual, f.After) {
			return diagnostics.New(diagnostics.Verification, "verify")
		}
		if f.Before.Exists {
			backup, err := Inspect(f.Backup)
			if err != nil {
				return err
			}
			if !Equal(backup, f.Before) {
				return diagnostics.New(diagnostics.Verification, "backup")
			}
		}
	}
	for _, change := range j.Registrations {
		if err := e.Registrations[change.Host].Verify(ctx, change.After); err != nil {
			return err
		}
	}
	j.Stage = "committed"
	return e.save(j)
}

// Committed backups intentionally remain recoverable. Cleanup is a separate verified action.
func (e *Engine) rollback(ctx context.Context, j *Journal) error {
	j.Stage = "rolling-back"
	if err := e.save(j); err != nil {
		return diagnostics.New(diagnostics.RollbackIncomplete, "journal")
	}
	// First refuse any foreign replacements or changed recovery bytes, before mutation.
	for _, f := range j.Files {
		actual, err := Inspect(f.Target)
		if err != nil {
			return diagnostics.New(diagnostics.RollbackIncomplete, "target")
		}
		backup, err := Inspect(f.Backup)
		if err != nil {
			return diagnostics.New(diagnostics.RollbackIncomplete, "backup")
		}
		if actual.Exists && !Equal(actual, f.Before) && !Equal(actual, f.After) {
			return diagnostics.New(diagnostics.RollbackIncomplete, "modified-target")
		}
		if backup.Exists && !Equal(backup, f.Before) {
			return diagnostics.New(diagnostics.RollbackIncomplete, "modified-backup")
		}
		if f.Before.Exists && !Equal(actual, f.Before) && !Equal(backup, f.Before) {
			return diagnostics.New(diagnostics.RollbackIncomplete, "missing-backup")
		}
	}
	for i := len(j.Files) - 1; i >= 0; i-- {
		f := &j.Files[i]
		lease, err := platform.Lease(filepath.Join(filepath.Dir(f.Target), ".lease"))
		if err != nil {
			return diagnostics.New(diagnostics.RollbackIncomplete, "lease")
		}
		err = func() error {
			defer lease.Close()
			actual, err := Inspect(f.Target)
			if err != nil {
				return err
			}
			if Equal(actual, f.Before) {
				return nil
			}
			if actual.Exists {
				if !Equal(actual, f.After) {
					return diagnostics.New(diagnostics.Verification, "rollback")
				}
				if err := platform.RemoveTree(f.Target); err != nil {
					return err
				}
			}
			if f.Before.Exists {
				backup, err := Inspect(f.Backup)
				if err != nil {
					return err
				}
				if !Equal(backup, f.Before) {
					return diagnostics.New(diagnostics.Verification, "backup")
				}
				if err := platform.Rename(f.Backup, f.Target); err != nil {
					return err
				}
			}
			restored, err := Inspect(f.Target)
			if err != nil {
				return err
			}
			if !Equal(restored, f.Before) {
				return diagnostics.New(diagnostics.Verification, "rollback")
			}
			return nil
		}()
		if err != nil {
			return diagnostics.New(diagnostics.RollbackIncomplete, "files")
		}
		f.Phase = "restored"
		if err := e.save(j); err != nil {
			return diagnostics.New(diagnostics.RollbackIncomplete, "journal")
		}
	}
	if j.RegistrationStarted {
		for i := len(j.Registrations) - 1; i >= 0; i-- {
			c := j.Registrations[i]
			adapter := e.Registrations[c.Host]
			if adapter == nil {
				return diagnostics.New(diagnostics.RollbackIncomplete, "adapter")
			}
			if err := adapter.Replace(ctx, c.After, c.Before); err != nil {
				return diagnostics.New(diagnostics.RollbackIncomplete, "registration")
			}
			if err := adapter.Verify(ctx, c.Before); err != nil {
				return diagnostics.New(diagnostics.RollbackIncomplete, "registration")
			}
		}
	}
	j.Stage = "rolled-back"
	return e.save(j)
}

func (e *Engine) validateJournal(j Journal) error {
	switch j.Stage {
	case "preparing", "prepared", "applying", "verifying", "committed", "rolling-back", "rolled-back", "cleaning", "finalized":
	default:
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	switch j.Host {
	case "", "codex", "claude", "antigravity", "manager":
	default:
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	switch j.Scope {
	case "", "global", "workspace", "export":
	default:
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	if len(j.Files) == 0 || len(j.Files) > MaxFiles {
		return diagnostics.New(diagnostics.Verification, "journal")
	}
	for _, f := range j.Files {
		prefix := filepath.Join(filepath.Dir(f.Target), ".opensocrates-"+j.ID+"-"+filepath.Base(f.Target))
		if !filepath.IsAbs(f.Target) || f.Staged != prefix+"-candidate" || f.Backup != prefix+"-backup" {
			return diagnostics.New(diagnostics.Verification, "journal")
		}
		for _, s := range []Snapshot{f.Before, f.After} {
			if !Equal(s, snapshot(s.Exists, s.Entries)) {
				return diagnostics.New(diagnostics.Verification, "journal")
			}
		}
	}
	return nil
}
func (e *Engine) Pending() ([]Journal, error) {
	entries, err := os.ReadDir(filepath.Join(e.StateDir, "transactions"))
	if os.IsNotExist(err) {
		return []Journal{}, nil
	}
	if err != nil {
		return nil, diagnostics.New(diagnostics.Permission, "journal")
	}
	var result []Journal
	for _, entry := range entries {
		id := entry.Name()
		if len(id) != 37 || !validID.MatchString(id[:32]) || id[32:] != ".json" {
			continue
		}
		b, err := platform.ReadFile(e.journalPath(id[:32]), 8<<20)
		if err != nil {
			return nil, err
		}
		var j Journal
		if _, err := contracts.Decode(b); err != nil {
			return nil, diagnostics.New(diagnostics.Verification, "journal")
		}
		if json.Unmarshal(b, &j) != nil || e.validateJournal(j) != nil {
			return nil, diagnostics.New(diagnostics.Verification, "journal")
		}
		if j.Stage != "committed" && j.Stage != "rolled-back" && j.Stage != "finalized" {
			result = append(result, j)
		}
	}
	return result, nil
}

// Lock holds native exclusion and the npm-compatible exclusive lock together.
func (e *Engine) Lock() (func() error, error) { return e.lock() }

func (e *Engine) applyRegistrations(ctx context.Context, j *Journal) error {
	j.RegistrationStarted = true
	if err := e.save(j); err != nil {
		return err
	}
	for _, change := range j.Registrations {
		if err := e.Registrations[change.Host].Replace(ctx, change.Before, change.After); err != nil {
			return err
		}
	}
	return nil
}
