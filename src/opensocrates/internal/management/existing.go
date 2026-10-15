package management

import (
	"context"
	"encoding/json"
	"errors"
	"path/filepath"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
)

func (m *Manager) existing(ctx context.Context, r Request) (Result, error) {
	if r.Purge {
		return m.purge(ctx, r)
	}
	p, e := m.Paths(r.Host, r.Workspace)
	if e != nil {
		return Result{}, e
	}
	result := defaultResult(r, p)
	inspect := r.Action == "status" || r.Action == "diagnose"
	if inspect {
		return m.status(ctx, r, p)
	}
	if r.Action != "remove" && r.Action != "enable" && r.Action != "disable" {
		return result, diagnostics.New(diagnostics.Unsupported, "action")
	}
	if r.Host == "codex" && r.Action != "remove" {
		return result, diagnostics.New(diagnostics.Unsupported, "codex-enabled-control")
	}
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
	if marker == nil && !before.Registered {
		return result, nil
	}
	if marker == nil {
		return result, diagnostics.New(diagnostics.Verification, "ownership")
	}
	state, e := ReadState(m.StateDir)
	if e != nil {
		return result, e
	}
	scratch, e := platform.MkdirTemp(m.StateDir, ".management-")
	if e != nil {
		return result, diagnostics.New(diagnostics.Permission, "stage")
	}
	defer platform.RemoveTree(scratch)
	plan := lifecycle.Plan{Action: r.Action, Host: r.Host, Scope: p.Scope, Version: marker.Version, Mutations: []lifecycle.Mutation{}}
	if r.Action == "remove" {
		plan.RegistrationBeforeFiles = true
		for _, target := range sortedKeys(targets) {
			expected := targets[target]
			plan.Mutations = append(plan.Mutations, lifecycle.Mutation{Target: target, Remove: true, Expected: &expected})
		}
		if r.Host == "codex" || r.Host == "claude" {
			after := registration.State{Root: p.Root}
			if r.Host == "codex" {
				after.Data = map[string]string{"codex_plugin_settings": ""}
			}
			plan.Registrations = append(plan.Registrations, registration.Change{Host: r.Host, Before: before, After: after})
		}
		delete(state.Installations, scopeKey(r.Host, p))
		if r.Host == "codex" {
			policy, e := (update.Engine{StateDir: m.StateDir}).Policy()
			if e != nil {
				return result, e
			}
			if policy.Enabled {
				change, e := update.PrepareMigration(ctx, m.Scheduler, false)
				if e != nil {
					return result, e
				}
				plan.Registrations = append(plan.Registrations, *change)
				policy.Enabled = false
				if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "update-policy.json"), policy); e != nil {
					return result, e
				}
			}
		}
		result.Installation = "missing"
		result.Activation = "removed_requires_host_reload"
		result.Registration = "absent"
	} else {
		enabled := r.Action == "enable"
		var sources map[string]string
		if r.Host == "claude" {
			if !before.Installed {
				return result, diagnostics.New(diagnostics.Verification, "registration-required")
			}
			source := filepath.Join(scratch, "host")
			if e := copyTree(p.Root, source); e != nil {
				return result, e
			}
			marker.Enabled = enabled
			if e := writeJSON(filepath.Join(source, MarkerName), marker); e != nil {
				return result, e
			}
			sources = map[string]string{p.Root: source}
			after := before
			after.Enabled = enabled
			plan.Registrations = append(plan.Registrations, registration.Change{Host: r.Host, Before: before, After: after})
		} else {
			source := filepath.Join(scratch, "package")
			if e := platform.Mkdir(source); e != nil {
				return result, e
			}
			for _, name := range sortedKeys(marker.Hashes) {
				physical, e := antiPhysical(p, name, marker.Enabled)
				if e != nil {
					return result, e
				}
				if e := copyTree(physical, filepath.Join(source, filepath.FromSlash(name))); e != nil {
					return result, e
				}
			}
			pack, e := transport.Verify(source, "antigravity", marker.Version, m.Target())
			if e != nil {
				return result, e
			}
			sources, e = stageHost(scratch, p, r.Host, pack, enabled)
			if e != nil {
				return result, e
			}
		}
		targetsAfter := map[string]lifecycle.Snapshot{}
		for _, target := range sortedKeys(sources) {
			source := sources[target]
			expected := targets[target]
			plan.Mutations = append(plan.Mutations, lifecycle.Mutation{Target: target, Source: source, Remove: source == "", Expected: &expected})
			if source != "" {
				targetsAfter[target], e = lifecycle.Inspect(source)
			} else {
				targetsAfter[target], e = lifecycle.Inspect(filepath.Join(scratch, "absent"))
			}
			if e != nil {
				return result, e
			}
		}
		key := scopeKey(r.Host, p)
		installation := state.Installations[key]
		installation.Host = r.Host
		installation.Scope = p.Scope
		installation.Root = p.Root
		installation.Version = marker.Version
		installation.Enabled = enabled
		installation.Targets = targetsAfter
		installation.Integrity = "verified"
		installation.Activation = "fresh_session_or_host_reload"
		state.Installations[key] = installation
		result.Installation = "installed"
		result.Version = marker.Version
		result.Enabled = enabled
		result.Activation = "fresh_session_or_host_reload"
		result.Registration = "confirmed"
	}
	if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "native-state.json"), state); e != nil {
		return result, e
	}
	j, e := m.Engine.ExecuteHeld(ctx, plan)
	result.Transaction = j.ID
	result.Integrity = "verified"
	return result, e
}
func (m *Manager) status(ctx context.Context, r Request, p Paths) (Result, error) {
	result := defaultResult(r, p)
	marker, _, e := owned(p, r.Host)
	if e != nil {
		var category *diagnostics.Error
		result.Installation = "unavailable"
		result.Integrity = "unverified"
		result.Activation = "unknown"
		result.Reason = diagnostics.Verification
		if errors.As(e, &category) {
			result.Reason = category.Code
		}
		return result, nil
	}
	if marker != nil {
		result.Installation = "installed"
		result.Version = marker.Version
		result.Enabled = marker.Enabled
		result.Integrity = "verified"
		result.Activation = "fresh_session_or_host_reload"
	}
	if r.Host == "codex" || r.Host == "claude" {
		observed, e := m.Engine.Registrations[r.Host].Inspect(ctx, p.Root)
		if e != nil {
			var category *diagnostics.Error
			result.Registration = "unavailable"
			result.Reason = diagnostics.HostUnavailable
			if errors.As(e, &category) {
				result.Reason = category.Code
			}
			return result, nil
		}
		if observed.Registered {
			result.Registration = "confirmed"
		}
		if observed.Installed {
			result.Enabled = observed.Enabled
			result.ObservedHostVersion = observed.Version
		}
		if observed.Registered && marker == nil {
			result.Installation = "unavailable"
			result.Integrity = "unverified"
			result.Reason = diagnostics.Verification
		}
	} else {
		result.Registration = "files-confirmed"
	}
	return result, nil
}

// ApplyRegistrationChange uses the same durable file/registration journal for
// scheduler configuration. A marker records only the operation identity.
func (m *Manager) ApplyRegistrationChange(ctx context.Context, change registration.Change) error {
	if e := m.init(); e != nil {
		return e
	}
	unlock, e := m.Engine.Lock()
	if e != nil {
		return e
	}
	defer unlock()
	scratch, e := platform.MkdirTemp(m.StateDir, ".management-")
	if e != nil {
		return diagnostics.New(diagnostics.Permission, "stage")
	}
	defer platform.RemoveTree(scratch)
	plan := lifecycle.Plan{Action: "scheduler", Host: "codex", Scope: "global", Registrations: []registration.Change{change}, Mutations: []lifecycle.Mutation{}}
	if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "scheduler-owner.json"), map[string]string{"schema": "opensocrates.scheduler-owner/1.0.0", "owner": update.Owner}); e != nil {
		return e
	}
	_, e = m.Engine.ExecuteHeld(ctx, plan)
	return e
}

// ApplyUpdateConfiguration commits policy and OS registration in one recovery
// journal. Scheduler opt-in never creates or enables a host installation.
func (m *Manager) ApplyUpdateConfiguration(ctx context.Context, configuration update.Configuration) error {
	if e := m.init(); e != nil {
		return e
	}
	if filepath.Clean(configuration.PolicyPath) != filepath.Join(m.StateDir, "update-policy.json") {
		return diagnostics.New(diagnostics.Verification, "policy-path")
	}
	var policy update.Policy
	if json.Unmarshal(configuration.PolicyJSON, &policy) != nil || policy.Schema != update.StateSchema || policy.Owner != update.Owner || policy.Channel != "stable" || len(policy.Hosts) != 1 || policy.Hosts[0] != "codex" {
		return diagnostics.New(diagnostics.Verification, "policy")
	}
	unlock, e := m.Engine.Lock()
	if e != nil {
		return e
	}
	defer unlock()
	p, e := m.Paths("codex", "")
	if e != nil {
		return e
	}
	marker, _, e := owned(p, "codex")
	if e != nil {
		return e
	}
	if policy.Enabled && marker == nil {
		return diagnostics.New(diagnostics.Verification, "codex-installation-required")
	}
	if pending, e := m.Engine.Pending(); e != nil {
		return e
	} else if len(pending) > 0 {
		return diagnostics.New(diagnostics.Locked, "recovery-required")
	}
	scratch, e := platform.MkdirTemp(m.StateDir, ".management-")
	if e != nil {
		return diagnostics.New(diagnostics.Permission, "stage")
	}
	defer platform.RemoveTree(scratch)
	plan := lifecycle.Plan{Action: "auto-update-policy", Host: "codex", Scope: "global", Registrations: []registration.Change{configuration.Registration}, Mutations: []lifecycle.Mutation{}}
	if e := appendJSONMutation(&plan, scratch, configuration.PolicyPath, policy); e != nil {
		return e
	}
	if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "scheduler-owner.json"), map[string]string{"schema": "opensocrates.scheduler-owner/1.0.0", "owner": update.Owner}); e != nil {
		return e
	}
	_, e = m.Engine.ExecuteHeld(ctx, plan)
	return e
}
