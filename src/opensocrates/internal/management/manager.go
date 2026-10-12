// Package management assembles transport, lifecycle and external registrations.
// It does not approve host hooks or upload content to a Claude account.
package management

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/hosts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
)

type Request struct {
	Action, Host, Workspace, Package, Version, Output, Transaction, ExpectedContentRevision string
	NativeTrustPolicy                                                                       *platform.NativeTrustPolicy
	Purge, ResetTrust                                                                       bool
}
type Result struct {
	Host                string           `json:"host"`
	Action              string           `json:"action"`
	Scope               string           `json:"scope"`
	Installation        string           `json:"installation"`
	Version             string           `json:"version,omitempty"`
	ContentRevision     string           `json:"content_revision,omitempty"`
	Enabled             bool             `json:"enabled"`
	Integrity           string           `json:"integrity"`
	Registration        string           `json:"registration"`
	ObservedHostVersion string           `json:"observed_host_version,omitempty"`
	Activation          string           `json:"activation"`
	Transaction         string           `json:"transaction,omitempty"`
	AutomaticEntry      string           `json:"automatic_entry"`
	MethodApplication   string           `json:"method_application"`
	Reason              diagnostics.Code `json:"reason,omitempty"`
	Purge               *PurgeReport     `json:"purge,omitempty"`
}
type Manager struct {
	StateDir, Home, Version, GOOS, GOARCH string
	LookupEnv                             func(string) string
	Runner                                registration.Runner
	Scheduler                             *update.SchedulerAdapter
	Engine                                *lifecycle.Engine
	AfterCommit                           func(context.Context, Result) error
	TrustConfigValidator                  func(context.Context, string, []byte) error
	PackageProbe                          func(context.Context, transport.Package, string) error
}

func (m *Manager) Env(key, fallback string) string {
	lookup := m.LookupEnv
	if lookup == nil {
		lookup = os.Getenv
	}
	if v := lookup(key); v != "" {
		p, e := filepath.Abs(v)
		if e == nil {
			return filepath.Clean(p)
		}
	}
	return fallback
}
func (m *Manager) init() error {
	if m.Home == "" {
		home, e := os.UserHomeDir()
		if e != nil {
			return diagnostics.New(diagnostics.HostUnavailable, "home")
		}
		m.Home = home
	}
	if m.StateDir == "" {
		m.StateDir = m.Env("OPENSOCRATES_STATE_DIR", filepath.Join(m.Home, ".opensocrates"))
	}
	if m.GOOS == "" {
		m.GOOS = runtime.GOOS
	}
	if m.GOARCH == "" {
		m.GOARCH = runtime.GOARCH
	}
	if m.Version == "" {
		m.Version = "1.6.0"
	}
	if !filepath.IsAbs(m.Home) || !filepath.IsAbs(m.StateDir) {
		return diagnostics.New(diagnostics.Verification, "paths")
	}
	if m.Engine == nil {
		m.Engine = &lifecycle.Engine{StateDir: m.StateDir, Registrations: map[string]registration.Adapter{}}
	}
	if m.Engine.Registrations == nil {
		m.Engine.Registrations = map[string]registration.Adapter{}
	}
	for _, host := range []string{"codex", "claude"} {
		if m.Engine.Registrations[host] == nil {
			key := "CODEX_BIN"
			if host == "claude" {
				key = "CLAUDE_BIN"
			}
			binary := host
			lookup := m.LookupEnv
			if lookup == nil {
				lookup = os.Getenv
			}
			if v := lookup(key); v != "" {
				binary = v
			}
			m.Engine.Registrations[host] = &registration.Native{Host: host, Binary: binary, Runner: m.Runner}
		}
	}
	if m.Scheduler == nil {
		m.Scheduler = update.NewSchedulerAdapter(m.GOOS, m.Home, m.ManagerPath(), m.StateDir)
	}
	m.Engine.Registrations["scheduler"] = m.Scheduler
	return nil
}
func (m *Manager) ManagerPath() string {
	exe := "opensocrates"
	if m.GOOS == "windows" {
		exe += ".exe"
	}
	return filepath.Join(m.StateDir, "bin", exe)
}
func (m *Manager) Target() string { return hosts.DistributionTarget(m.GOOS, m.GOARCH) }
func scopeKey(host string, p Paths) string {
	h := sha256.Sum256([]byte(p.Root))
	return host + ":" + p.Scope + ":" + hex.EncodeToString(h[:8])
}
func defaultResult(r Request, p Paths) Result {
	return Result{Host: r.Host, Action: r.Action, Scope: p.Scope, Installation: "missing", Integrity: "not-installed", Registration: "absent", Activation: "not-installed", AutomaticEntry: "unverified", MethodApplication: "unverified"}
}
func (m *Manager) Handle(ctx context.Context, r Request) (Result, error) {
	if e := m.init(); e != nil {
		return Result{}, e
	}
	if r.Host == "" || r.Host == "all" {
		r.Host = "codex"
	}
	if r.Action == "uninstall" {
		r.Action = "remove"
	}
	if (r.Purge || r.ResetTrust) && (r.Action != "remove" || r.Host != "codex") || r.ResetTrust && !r.Purge {
		return Result{}, diagnostics.New(diagnostics.Unsupported, "purge-options")
	}
	if r.Action == "recover" {
		j, e := m.Engine.Recover(ctx, r.Transaction)
		result := Result{Host: j.Host, Action: "recover", Scope: j.Scope, Transaction: j.ID, Installation: j.Stage, Integrity: "verified", Activation: "fresh_session_or_host_reload", AutomaticEntry: "unverified", MethodApplication: "unverified"}
		return result, e
	}
	profile, e := hosts.Get(hosts.ID(r.Host))
	if e != nil {
		return Result{}, e
	}
	scope := hosts.Global
	if r.Workspace != "" {
		scope = hosts.Workspace
	}
	if r.Host == "claude-chat" {
		scope = hosts.Export
	}
	offline := r.Action == "verify" || r.Action == "export"
	if !offline && !profile.Supports(hosts.Platform(m.GOOS+"-"+m.GOARCH), scope, r.Action) {
		return Result{}, diagnostics.New(diagnostics.Unsupported, "profile")
	}
	if offline {
		if r.Action == "export" && r.Host != "claude-chat" {
			return Result{}, diagnostics.New(diagnostics.Unsupported, "export")
		}
		p, e := transport.Prepare(r.Package, r.Host, r.Version, m.Target())
		if e != nil {
			return Result{}, e
		}
		defer p.Close()
		if r.Action == "export" {
			if e := transport.Export(p, r.Output); e != nil {
				return Result{}, e
			}
		}
		return Result{Host: r.Host, Action: r.Action, Scope: "export", Installation: "verified-package", Version: p.Manifest.ProductVersion, ContentRevision: p.Manifest.ContentRevision, Integrity: "verified", Activation: profile.ActivationBoundary, Registration: "not-applicable", AutomaticEntry: "unverified", MethodApplication: "unverified"}, nil
	}
	if r.Action == "install" || r.Action == "update" || r.Action == "adopt" {
		return m.ApplyPackage(ctx, r)
	}
	return m.existing(ctx, r)
}

// ApplyPackage is shared by explicit and scheduled updates after trust verification.
func (m *Manager) ApplyPackage(ctx context.Context, r Request) (Result, error) {
	if e := m.init(); e != nil {
		return Result{}, e
	}
	if r.Host == "" || r.Host == "all" {
		r.Host = "codex"
	}
	profile, e := hosts.Get(hosts.ID(r.Host))
	if e != nil {
		return Result{}, e
	}
	scope := hosts.Global
	if r.Workspace != "" {
		scope = hosts.Workspace
	}
	if !profile.Supports(hosts.Platform(m.GOOS+"-"+m.GOARCH), scope, r.Action) {
		return Result{}, diagnostics.New(diagnostics.Unsupported, "profile")
	}
	pack, e := transport.Prepare(r.Package, r.Host, r.Version, m.Target())
	if e != nil {
		return Result{}, e
	}
	defer pack.Close()
	if r.ExpectedContentRevision != "" && pack.Manifest.ContentRevision != r.ExpectedContentRevision {
		return Result{}, diagnostics.New(diagnostics.Verification, "content-identity")
	}
	if r.NativeTrustPolicy != nil {
		if e := verifyCandidateExecutables(ctx, pack, m.Target(), *r.NativeTrustPolicy); e != nil {
			return Result{}, e
		}
	}
	probe := m.PackageProbe
	if probe == nil {
		probe = probePackage
	}
	if e := probe(ctx, pack, m.Target()); e != nil {
		return Result{}, e
	}
	p, e := m.Paths(r.Host, r.Workspace)
	if e != nil {
		return Result{}, e
	}
	result := defaultResult(r, p)
	unlock, e := m.Engine.Lock()
	if e != nil {
		return result, e
	}
	defer unlock()
	if pending, e := m.Engine.Pending(); e != nil {
		return result, e
	} else if len(pending) > 0 {
		return result, diagnostics.New(diagnostics.Locked, "recovery-required")
	}
	state, e := ReadState(m.StateDir)
	if e != nil {
		return result, e
	}
	marker, targets, e := owned(p, r.Host)
	if e != nil {
		return result, e
	}
	before := registration.State{Root: p.Root}
	if r.Host == "codex" || r.Host == "claude" {
		before, e = m.Engine.Registrations[r.Host].Inspect(ctx, p.Root)
		if e != nil {
			return result, e
		}
		if before.Registered && marker == nil {
			return result, diagnostics.New(diagnostics.Verification, "foreign-registration")
		}
	}
	key := scopeKey(r.Host, p)
	if previous, ok := state.Installations[key]; ok {
		for target, expected := range previous.Targets {
			actual, e := lifecycle.Inspect(target)
			if e != nil {
				return result, e
			}
			if !lifecycle.Equal(actual, expected) {
				return result, diagnostics.New(diagnostics.Verification, "owned-modified")
			}
		}
	}
	enabled := true
	if marker != nil {
		enabled = marker.Enabled
	}
	if before.Installed {
		enabled = before.Enabled
	}
	scratch, e := platform.MkdirTemp(m.StateDir, ".management-")
	if e != nil {
		return result, diagnostics.New(diagnostics.Permission, "stage")
	}
	defer platform.RemoveTree(scratch)
	sources, e := stageHost(scratch, p, r.Host, pack, enabled)
	if e != nil {
		return result, e
	}
	plan := lifecycle.Plan{Action: r.Action, Host: r.Host, Scope: p.Scope, Version: pack.Manifest.ProductVersion, Mutations: []lifecycle.Mutation{}}
	desired := before
	if r.Host == "claude" || r.Host == "codex" {
		desired.Registered = true
		desired.Installed = true
		desired.Enabled = enabled
		desired.Version = pack.Manifest.ProductVersion
		if r.Host == "codex" && before.Installed {
			desired = before
		}
		plan.Registrations = append(plan.Registrations, registration.Change{Host: r.Host, Before: before, After: desired})
		result.ObservedHostVersion = desired.Version
	}
	installation := Installation{Host: r.Host, Scope: p.Scope, Root: p.Root, Version: pack.Manifest.ProductVersion, ContentRevision: pack.Manifest.ContentRevision, Enabled: enabled, Integrity: "verified", Activation: profile.ActivationBoundary, UpdateOwner: "native", Targets: map[string]lifecycle.Snapshot{}}
	for _, target := range sortedKeys(sources) {
		source := sources[target]
		expected := targets[target]
		mutation := lifecycle.Mutation{Target: target, Source: source, Expected: &expected, Remove: source == ""}
		plan.Mutations = append(plan.Mutations, mutation)
		if source != "" {
			s, e := lifecycle.Inspect(source)
			if e != nil {
				return result, e
			}
			installation.Targets[target] = s
		} else {
			empty, e := lifecycle.Inspect(filepath.Join(scratch, "absent"))
			if e != nil {
				return result, e
			}
			installation.Targets[target] = empty
		}
	}
	// A full bundle retains an immutable version directory separately from settings.
	if pack.BundleRoot != "" {
		bundleSnapshot, e := lifecycle.Inspect(pack.BundleRoot)
		if e != nil {
			return result, e
		}
		bundleID := pack.Manifest.ProductVersion + "-" + m.Target() + "-" + bundleSnapshot.SHA256[:16]
		bundleTarget := filepath.Join(m.StateDir, "bundles", bundleID)
		previous, e := lifecycle.Inspect(bundleTarget)
		if e != nil {
			return result, e
		}
		if previous.Exists {
			if !lifecycle.Equal(previous, bundleSnapshot) {
				return result, diagnostics.New(diagnostics.Verification, "bundle-collision")
			}
		} else {
			plan.Mutations = append(plan.Mutations, lifecycle.Mutation{Target: bundleTarget, Source: pack.BundleRoot, Expected: &previous})
		}
		installation.Bundle = bundleID
		managerSource := filepath.Join(pack.BundleRoot, "bin", filepath.Base(m.ManagerPath()))
		managerSnapshot, e := lifecycle.Inspect(managerSource)
		if e != nil || !managerSnapshot.Exists {
			return result, diagnostics.New(diagnostics.Verification, "manager")
		}
		current, e := lifecycle.Inspect(m.ManagerPath())
		if e != nil {
			return result, e
		}
		if current.Exists {
			if state.ManagerVersion == "" {
				return result, diagnostics.New(diagnostics.Verification, "manager-ownership")
			}
			ownedManager := state.Installations["manager"].Targets[m.ManagerPath()]
			if !lifecycle.Equal(current, ownedManager) {
				return result, diagnostics.New(diagnostics.Verification, "manager-modified")
			}
		}
		stableSnapshot := managerSnapshot
		stableVersion := pack.Manifest.ProductVersion
		if m.GOOS == "windows" && current.Exists && !lifecycle.Equal(current, managerSnapshot) {
			// Windows keeps its tiny stable bootstrap callable while an older process
			// holds it. New management/updater code runs from the version-pinned bundle.
			stableSnapshot = current
			stableVersion = state.Installations["manager"].Version
			pending := map[string]any{"schema": "opensocrates.manager-replacement/1.0.0", "bundle": bundleID, "source": filepath.ToSlash(filepath.Join("bin", filepath.Base(m.ManagerPath()))), "before": current, "after": managerSnapshot}
			if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "manager-pending.json"), pending); e != nil {
				return result, e
			}
		} else if !lifecycle.Equal(current, managerSnapshot) {
			plan.Mutations = append(plan.Mutations, lifecycle.Mutation{Target: m.ManagerPath(), Source: managerSource, Expected: &current})
		}
		state.ManagerVersion = pack.Manifest.ProductVersion
		state.Installations["manager"] = Installation{Host: "manager", Version: stableVersion, Bundle: bundleID, Targets: map[string]lifecycle.Snapshot{m.ManagerPath(): stableSnapshot}}
		active := map[string]string{"schema": "opensocrates.active-bundle/1.0.0", "bundle": bundleID, "version": pack.Manifest.ProductVersion, "target": m.Target()}
		if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "active.json"), active); e != nil {
			return result, e
		}
	}
	legacy, raw, e := ReadLegacy(m.StateDir)
	if e != nil {
		return result, e
	}
	if legacy != nil && state.LegacyDesiredState == nil {
		if r.Host != "codex" && len(legacy.InstalledHosts) > 0 { // Addons do not acquire the Codex update owner.
		} else {
			state.LegacyDesiredState = raw
			if legacy.AutoUpdate.Enabled {
				retired, e := RetireLegacyUpdater(raw)
				if e != nil {
					return result, e
				}
				source := filepath.Join(scratch, "retired-desired-state.json")
				if e := platform.AtomicWrite(source, retired, 0600); e != nil {
					return result, e
				}
				oldDesiredPath := filepath.Join(m.StateDir, "desired-state.json")
				previous, e := lifecycle.Inspect(oldDesiredPath)
				if e != nil {
					return result, e
				}
				plan.Mutations = append(plan.Mutations, lifecycle.Mutation{Target: oldDesiredPath, Source: source, Expected: &previous})
			}
			if legacy.Channel != "stable" && legacy.AutoUpdate.Enabled {
				return result, diagnostics.New(diagnostics.Unsupported, "legacy-next-channel")
			}
			change, e := update.PrepareMigration(ctx, m.Scheduler, legacy.AutoUpdate.Enabled)
			if e != nil {
				return result, e
			}
			plan.Registrations = append(plan.Registrations, *change)
			policy := update.Policy{Schema: update.StateSchema, Enabled: legacy.AutoUpdate.Enabled, Channel: "stable", Owner: update.Owner, Hosts: []string{"codex"}, NextCheck: time.Now().UTC().Add(update.LoginDelay)}
			if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "update-policy.json"), policy); e != nil {
				return result, e
			}
		}
	}
	state.Schema = StateSchema
	if r.Host == "codex" || legacy == nil || state.LegacyDesiredState != nil {
		state.UpdateOwner = "native"
	} else {
		state.UpdateOwner = "npm"
	}
	state.Installations[key] = installation
	if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "native-state.json"), state); e != nil {
		return result, e
	}
	j, e := m.Engine.ExecuteHeld(ctx, plan)
	result.Transaction = j.ID
	if e != nil {
		return result, e
	}
	result.Installation = "installed"
	result.Version = installation.Version
	result.ContentRevision = installation.ContentRevision
	result.Enabled = enabled
	result.Integrity = "verified"
	result.Activation = installation.Activation
	result.Registration = "confirmed"
	if r.Host == "antigravity" {
		result.Registration = "files-confirmed"
	}
	if m.AfterCommit != nil {
		if e := m.AfterCommit(ctx, result); e != nil {
			result.Reason = diagnostics.Activation
		}
	}
	return result, nil
}
func appendJSONMutation(p *lifecycle.Plan, scratch, target string, value any) error {
	b, e := json.MarshalIndent(value, "", "  ")
	if e != nil {
		return diagnostics.New(diagnostics.Verification, "stage")
	}
	source := filepath.Join(scratch, "state-"+lifecycle.NewID())
	if e := platform.AtomicWrite(source, append(b, '\n'), 0600); e != nil {
		return e
	}
	before, e := lifecycle.Inspect(target)
	if e != nil {
		return e
	}
	p.Mutations = append(p.Mutations, lifecycle.Mutation{Target: target, Source: source, Expected: &before})
	return nil
}

// PinActiveBundle returns the verified bundle path once; callers retain it for
// their whole process rather than re-reading a mutable active reference.
func PinActiveBundle(dir string) (string, error) {
	b, e := platform.ReadFile(filepath.Join(dir, "active.json"), 64<<10)
	if e != nil {
		return "", e
	}
	var s struct {
		Schema string `json:"schema"`
		Bundle string `json:"bundle"`
	}
	if _, e := contracts.Decode(b); e != nil {
		return "", diagnostics.New(diagnostics.Verification, "active")
	}
	if json.Unmarshal(b, &s) != nil || s.Schema != "opensocrates.active-bundle/1.0.0" || s.Bundle == "" || strings.ContainsAny(s.Bundle, "/\\:") || s.Bundle == "." || s.Bundle == ".." {
		return "", diagnostics.New(diagnostics.Verification, "active")
	}
	path := filepath.Join(dir, "bundles", s.Bundle)
	if e := platform.GuardOwned(path); e != nil {
		return "", e
	}
	return path, nil
}
