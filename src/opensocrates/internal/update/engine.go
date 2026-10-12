package update

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type Engine struct {
	StateDir, Version, OS, Arch string
	Repository                  Repository
	Apply                       Apply
	Now                         func() time.Time
}

func (e Engine) now() time.Time {
	if e.Now != nil {
		return e.Now().UTC()
	}
	return time.Now().UTC()
}
func (e Engine) Policy() (Policy, error) {
	p := Policy{Schema: StateSchema, Channel: "stable", Owner: Owner, Hosts: []string{"codex"}}
	b, err := platform.ReadFile(filepath.Join(e.StateDir, "update-policy.json"), 64<<10)
	if err != nil {
		if _, stat := os.Lstat(filepath.Join(e.StateDir, "update-policy.json")); os.IsNotExist(stat) {
			return p, nil
		}
		return p, err
	}
	if strict(b, &p) != nil || p.Schema != StateSchema || p.Owner != Owner || p.Channel != "stable" || len(p.Hosts) != 1 || p.Hosts[0] != "codex" {
		return p, closed(diagnostics.Verification, "policy")
	}
	return p, nil
}
func (e Engine) savePolicy(p Policy) error {
	b, err := json.Marshal(p)
	if err != nil {
		return closed(diagnostics.Verification, "policy")
	}
	return platform.AtomicWrite(filepath.Join(e.StateDir, "update-policy.json"), append(b, '\n'), 0600)
}
func (e Engine) receipt(r Receipt) error {
	b, err := json.Marshal(r)
	if err != nil {
		return closed(diagnostics.Verification, "receipt")
	}
	return platform.AtomicWrite(filepath.Join(e.StateDir, "update-receipt.json"), append(b, '\n'), 0600)
}

// Run is shared by explicit update and OS-scheduled auto-update run. Policy is
// re-read under one update lock; the lifecycle callback obtains mutation lock.
func (e Engine) Run(ctx context.Context, scheduled, force bool) (Receipt, error) {
	r := Receipt{Schema: "opensocrates.native-update-receipt/1.0.0", CheckedAt: e.now(), Host: "codex", Scope: "user", Phase: "check", Result: "unchanged"}
	if _, err := MetadataTarget(e.OS, e.Arch); err != nil {
		return r, err
	}
	if err := platform.Mkdir(e.StateDir); err != nil {
		return r, err
	}
	lock, err := platform.Lock(filepath.Join(e.StateDir, "update.lock"))
	if err != nil {
		return r, err
	}
	defer lock.Close()
	p, err := e.Policy()
	if err != nil {
		return r, err
	}
	if scheduled && !p.Enabled {
		r.Result = "disabled"
		return r, nil
	}
	if scheduled && !force && r.CheckedAt.Before(p.NextCheck) {
		r.Result = "not_due"
		return r, nil
	}
	// Record the attempt before network IO: crashes and offline conditions do
	// not create a login retry storm. A force/manual check is always explicit.
	p.LastCheck = r.CheckedAt
	p.NextCheck = r.CheckedAt.Add(Interval)
	if err = e.savePolicy(p); err != nil {
		return r, err
	}
	target, _ := MetadataTarget(e.OS, e.Arch)
	candidate, err := e.Repository.Fetch(ctx, filepath.Join(e.StateDir, "trust"), target)
	if err != nil {
		r.Result = "unavailable"
		var d *diagnostics.Error
		if errors.As(err, &d) {
			r.ErrorCategory = d.Code
		} else {
			r.ErrorCategory = diagnostics.Verification
		}
		if se := e.receipt(r); se != nil {
			return r, se
		}
		return r, err
	}
	r.Version = candidate.Release.Version
	p.AvailableVersion = r.Version
	if err = e.savePolicy(p); err != nil {
		return r, err
	}
	policy, err := Compatible(candidate.Release, e.Version, e.OS, e.Arch, scheduled)
	if err != nil {
		r.Result = "incompatible"
		r.ErrorCategory = diagnostics.ProtocolIncompatible
		_ = e.receipt(r)
		return r, err
	}
	if policy == "current" {
		r.Result = "current"
		return r, e.receipt(r)
	}
	if policy == "prepare_only" {
		r.Result = "prepared_requires_approval"
		r.Phase = "pending"
		return r, e.receipt(r)
	}
	if e.Apply == nil {
		return r, closed(diagnostics.HostUnavailable, "lifecycle")
	}
	r.Phase = "apply"
	applied, err := e.Apply(ctx, candidate)
	if err != nil {
		r.Result = "failed"
		var d *diagnostics.Error
		if errors.As(err, &d) {
			r.ErrorCategory = d.Code
		} else {
			r.ErrorCategory = diagnostics.Activation
		}
		_ = e.receipt(r)
		return r, err
	}
	r.Phase = "complete"
	r.Result = "updated"
	if applied.Pending {
		r.Phase = "pending"
		r.Result = "pending_fresh_session"
	}
	return r, e.receipt(r)
}
func Compatible(r Release, current, osName, arch string, scheduled bool) (string, error) {
	v, ok := version(r.Version)
	c, cok := version(current)
	min, mok := version(r.MinimumManager)
	if !ok || !cok || !mok || r.ContentRevision == "" || r.Channel != "stable" || r.OS != osName || r.Arch != arch || !validTarget(r.PackagePath) || r.DataSchema < 1 || r.MigrationVersion < 0 {
		return "", closed(diagnostics.ProtocolIncompatible, "compatibility")
	}
	codex := false
	for _, p := range r.Profiles {
		if p == "codex" {
			codex = true
		}
	}
	if !codex {
		return "", closed(diagnostics.ProtocolIncompatible, "profile")
	}
	if compare(v, c) <= 0 {
		return "current", nil
	}
	if compare(c, min) < 0 || r.DataSchema != 1 || r.MigrationVersion != 0 || scheduled && v[0] != c[0] {
		return "prepare_only", nil
	}
	return "apply", nil
}
func version(s string) ([3]int, bool) {
	var result [3]int
	parts := strings.Split(strings.TrimPrefix(s, "v"), ".")
	if len(parts) != 3 {
		return result, false
	}
	for i, p := range parts {
		if p == "" || len(p) > 1 && p[0] == '0' {
			return result, false
		}
		n, e := strconv.Atoi(p)
		if e != nil || n < 0 {
			return result, false
		}
		result[i] = n
	}
	return result, true
}
func compare(a, b [3]int) int {
	for i := range a {
		if a[i] < b[i] {
			return -1
		}
		if a[i] > b[i] {
			return 1
		}
	}
	return 0
}

// Status reports actual OS registration independently of opt-in policy. Private
// task documents and filesystem paths remain in recovery state, never output.
type Status struct {
	Policy              Policy `json:"policy"`
	SchedulerInstalled  bool   `json:"scheduler_installed"`
	SchedulerRegistered bool   `json:"scheduler_registered"`
	Consistent          bool   `json:"consistent"`
	TrustAvailable      bool   `json:"trust_available"`
}

func (e Engine) Status(ctx context.Context, a *SchedulerAdapter) (Status, error) {
	p, err := e.Policy()
	if err != nil {
		return Status{}, err
	}
	s, err := a.Inspect(ctx, a.Root())
	if err != nil {
		return Status{Policy: p}, err
	}
	return Status{Policy: p, SchedulerInstalled: s.Installed, SchedulerRegistered: s.Registered, Consistent: p.Enabled == s.Installed && p.Enabled == s.Registered, TrustAvailable: ValidateProductionRoot(e.Repository.BootstrapRoot, e.now()) == nil}, nil
}
