package management

import (
	"context"
	"encoding/json"
	"math/big"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
)

type PurgeComponent struct {
	Component    string `json:"component"`
	Status       string `json:"status"`
	Detail       string `json:"detail,omitempty"`
	RemovedCount int    `json:"removed_count,omitempty"`
}
type PurgeReport struct {
	Schema           string           `json:"schema"`
	Status           string           `json:"status"`
	TrustTransaction string           `json:"trust_transaction,omitempty"`
	Components       []PurgeComponent `json:"components"`
}

const purgeSchema = "opensocrates.purge-result/1.0.0"

var legacyResidueName = regexp.MustCompile(`^\.opensocrates\.(?:staging|backup|removed)-[A-Za-z0-9-]+$`)
var legacyStateResidue = regexp.MustCompile(`^(?:\.(?:desired-state|auto-update-receipt)\.json\.[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.tmp|\.purge-finalize-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}-(?:desired-state\.json|auto-update-receipt\.json|\.(?:desired-state|auto-update-receipt)\.json\.[0-9a-f-]+\.tmp))$`)
var purgeChecksum = regexp.MustCompile(`^([a-fA-F0-9]{64})\s+\*?(.+)$`)
var cachePID = regexp.MustCompile(`^[1-9][0-9]*$`)
var journalName = regexp.MustCompile(`^[a-f0-9]{32}\.json$`)
var positiveRevision = regexp.MustCompile(`^[1-9][0-9]*$`)

func appendPurgeRemoval(plan *lifecycle.Plan, target string, expected lifecycle.Snapshot) {
	if expected.Exists {
		plan.Mutations = append(plan.Mutations, lifecycle.Mutation{Target: target, Remove: true, Expected: &expected})
	}
}

// purge uses the ordinary lifecycle engine: exact payload ownership is proven
// before preparing its removal journal, registrations and scheduler changes
// roll back together, and cleanup is a separate durable terminal phase. The
// optional trust reset commits first under the same lock, matching the legacy
// contract: a later purge failure does not undo an explicitly verified reset.
// This separates the host CLI's plugin settings edit from the trust edit in
// the same configuration file. Unknown state, conversations, npm installations
// and shared management tools are preserved.
func (m *Manager) purge(ctx context.Context, r Request) (Result, error) {
	p, e := m.Paths(r.Host, r.Workspace)
	if e != nil {
		return Result{}, e
	}
	result := defaultResult(r, p)
	result.Purge = &PurgeReport{Schema: purgeSchema, Status: "partial", Components: []PurgeComponent{{Component: "user-history", Status: "preserved"}, {Component: "management-tooling", Status: "preserved"}}}
	if r.Host != "codex" || r.Workspace != "" {
		return result, diagnostics.New(diagnostics.Unsupported, "purge-profile")
	}
	unlock, e := m.Engine.Lock()
	if e != nil {
		return result, e
	}
	locked := true
	defer func() {
		if locked {
			unlock()
		}
	}()
	if pending, e := m.Engine.Pending(); e != nil {
		return result, e
	} else if len(pending) > 0 {
		return result, diagnostics.New(diagnostics.Locked, "recovery-required")
	}
	scratch, e := platform.MkdirTemp(m.StateDir, ".management-")
	if e != nil {
		return result, diagnostics.New(diagnostics.Permission, "stage")
	}
	defer platform.RemoveTree(scratch)
	plan := lifecycle.Plan{Action: "purge", Host: r.Host, Scope: p.Scope, Mutations: []lifecycle.Mutation{}, RegistrationBeforeFiles: true}
	if r.ResetTrust {
		trustPlan := lifecycle.Plan{Action: "trust-reset", Host: "codex", Scope: p.Scope, Mutations: []lifecycle.Mutation{}}
		reset, e := m.prepareTrustReset(ctx, p, scratch, &trustPlan)
		if e != nil {
			result.Purge.Status = "partial"
			result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "host-security-trust", Status: "failed"})
			return result, e
		}
		status := "absent"
		if len(reset.RemovedEvents) > 0 {
			j, e := m.Engine.ExecuteHeld(ctx, trustPlan)
			result.Purge.TrustTransaction = j.ID
			if e != nil {
				result.Purge.Status = "partial"
				result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "host-security-trust", Status: "failed"})
				return result, e
			}
			status = "removed"
			result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "host-security-trust", Status: status, RemovedCount: len(reset.RemovedEvents)})
			if e := m.Engine.FinalizeCommittedHeld(ctx, j.ID); e != nil {
				result.Purge.Status = "partial"
				return result, e
			}
		} else {
			result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "host-security-trust", Status: status})
		}
	} else {
		result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "host-security-trust", Status: "preserved"})
	}
	marker, targets, e := owned(p, "codex")
	if e != nil {
		return result, e
	}
	before, e := m.Engine.Registrations["codex"].Inspect(ctx, p.Root)
	if e != nil {
		return result, e
	}
	if before.Registered && before.Root != p.Root {
		return result, diagnostics.New(diagnostics.Verification, "foreign-registration")
	}
	for _, target := range sortedKeys(targets) {
		appendPurgeRemoval(&plan, target, targets[target])
	}
	rootStatus := "absent"
	if marker != nil {
		rootStatus = "planned"
		plan.Version = marker.Version
	}
	result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "managed-root", Status: rootStatus})
	plan.Registrations = append(plan.Registrations, registration.Change{Host: "codex", Before: before, After: registration.State{Root: p.Root, Data: map[string]string{"codex_plugin_settings": ""}}})
	cacheMutationStart := len(plan.Mutations)
	pendingCache, e := m.prepareCachePurge(p, &plan)
	if e != nil {
		return result, e
	}
	cacheStatus := "absent"
	if len(plan.Mutations) > cacheMutationStart {
		cacheStatus = "planned"
	}
	if pendingCache {
		cacheStatus = "pending"
	}
	result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "plugin-cache", Status: cacheStatus, Detail: func() string {
		if pendingCache {
			return "host-in-use"
		}
		return ""
	}()})
	if e := prepareLegacyPayloadResidue(p, &plan); e != nil {
		return result, e
	}
	if e := m.preparePriorPayloadBackups(p, &plan); e != nil {
		return result, e
	}
	state, e := ReadState(m.StateDir)
	if e != nil {
		return result, e
	}
	delete(state.Installations, scopeKey("codex", p))
	legacy, legacyRaw, e := ReadLegacy(m.StateDir)
	if e != nil {
		return result, e
	}
	schedulerChange, e := update.PrepareMigration(ctx, m.Scheduler, false)
	if e != nil {
		return result, e
	}
	plan.Registrations = append(plan.Registrations, *schedulerChange)
	policy, e := (update.Engine{StateDir: m.StateDir}).Policy()
	if e != nil {
		return result, e
	}
	policy.Enabled = false
	if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "update-policy.json"), policy); e != nil {
		return result, e
	}
	if !pendingCache && (legacy == nil || len(legacy.InstalledHosts) <= 1) {
		if e := m.prepareLegacyStatePurge(&plan); e != nil {
			return result, e
		}
		state.LegacyDesiredState = nil
	} else if legacy != nil { // Partial purge keeps the exact recovery state, with only activation disabled.
		var desired map[string]json.RawMessage
		if json.Unmarshal(legacyRaw, &desired) != nil {
			return result, diagnostics.New(diagnostics.Verification, "legacy-state")
		}
		if desired != nil {
			desired["installedHosts"] = json.RawMessage(`[]`)
			desired["activeVersion"] = json.RawMessage(`null`)
			desired["autoUpdate"] = json.RawMessage(`{"enabled":false,"hosts":[],"nextCheckAt":null}`)
			if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "desired-state.json"), desired); e != nil {
				return result, e
			}
		}
	}
	if e := appendJSONMutation(&plan, scratch, filepath.Join(m.StateDir, "native-state.json"), state); e != nil {
		return result, e
	}
	j, e := m.Engine.ExecuteHeld(ctx, plan)
	result.Transaction = j.ID
	if e != nil {
		result.Purge.Status = "partial"
		return result, e
	}
	result.Installation = "missing"
	result.Registration = "absent"
	result.Activation = "removed_requires_host_reload"
	result.Integrity = "verified"
	if e := unlock(); e != nil {
		locked = false
		return result, e
	}
	locked = false
	if e := m.Engine.FinalizeCommitted(ctx, j.ID); e != nil {
		result.Purge.Status = "partial"
		return result, e
	}
	for i := range result.Purge.Components {
		if result.Purge.Components[i].Status == "planned" {
			result.Purge.Components[i].Status = "removed"
		}
	}
	result.Purge.Components = append(result.Purge.Components, PurgeComponent{Component: "transaction-residue", Status: "removed-or-absent"})
	if pendingCache {
		result.Purge.Status = "partial"
		return result, diagnostics.New(diagnostics.Activation, "purge-host-in-use")
	}
	result.Purge.Status = "complete"
	return result, nil
}

// verifyPurgePackage accepts the released legacy cache format and the native
// package format. Checksums bind every file; only host-owned orphan/use markers
// may lie outside that inventory. No unknown executable or file is removable.
func verifyPurgePackage(root, version string) (lifecycle.Snapshot, error) {
	s, e := lifecycle.Inspect(root)
	if e != nil {
		return s, e
	}
	if !s.Exists || len(s.Entries) == 0 || !s.Entries[0].Directory {
		return s, trustFailure()
	}
	release, e := platform.ReadOwnedFile(filepath.Join(root, "release-manifest.json"), 8<<20)
	if e != nil {
		return s, e
	}
	var identity struct {
		Schema, Host string
		Version      string          `json:"product_version"`
		Revision     json.RawMessage `json:"content_revision"`
	}
	if _, e := contracts.Decode(release); e != nil {
		return s, trustFailure()
	}
	if json.Unmarshal(release, &identity) != nil || identity.Schema != "opensocrates.plugin-release-manifest/1.0.0" || identity.Host != "codex" || identity.Version != version {
		return s, trustFailure()
	}
	number := string(identity.Revision)
	if strings.HasPrefix(number, `"`) {
		if json.Unmarshal(identity.Revision, &number) != nil {
			return s, trustFailure()
		}
	}
	revision, valid := new(big.Int).SetString(number, 10)
	if !valid || revision.Sign() < 1 || !positiveRevision.MatchString(number) {
		return s, trustFailure()
	}
	plugin, e := platform.ReadOwnedFile(filepath.Join(root, ".codex-plugin", "plugin.json"), 8<<20)
	if e != nil {
		return s, e
	}
	var pi struct{ Name, Version string }
	if _, e := contracts.Decode(plugin); e != nil {
		return s, trustFailure()
	}
	if json.Unmarshal(plugin, &pi) != nil || pi.Name != "opensocrates" || pi.Version != version {
		return s, trustFailure()
	}
	checks, e := platform.ReadOwnedFile(filepath.Join(root, "checksums.sha256"), 8<<20)
	if e != nil {
		return s, e
	}
	declared := map[string]string{}
	for _, line := range strings.Split(string(checks), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		match := purgeChecksum.FindStringSubmatch(line)
		if len(match) != 3 {
			return s, trustFailure()
		}
		name := strings.TrimSpace(match[2])
		if !transport.SafeRelative(name) || name == "checksums.sha256" || declared[name] != "" {
			return s, trustFailure()
		}
		declared[name] = strings.ToLower(match[1])
	}
	if len(declared) == 0 || declared["release-manifest.json"] == "" || declared[".codex-plugin/plugin.json"] == "" {
		return s, trustFailure()
	}
	actual := files(s)
	for name, hash := range declared {
		if actual[name] != hash {
			return s, trustFailure()
		}
	}
	for name := range actual {
		if name == "checksums.sha256" || declared[name] != "" || name == ".orphaned_at" || strings.HasPrefix(name, ".in_use/") {
			continue
		}
		return s, trustFailure()
	}
	return s, nil
}

func cacheInUse(root string) (bool, error) {
	marker := filepath.Join(root, ".in_use")
	if e := platform.GuardOwned(marker); e != nil {
		return false, e
	}
	entries, e := os.ReadDir(marker)
	if os.IsNotExist(e) {
		return false, nil
	}
	if e != nil {
		return false, trustFailure()
	}
	alive := false
	for _, entry := range entries {
		if !entry.Type().IsRegular() || !cachePID.MatchString(entry.Name()) {
			return false, trustFailure()
		}
		pid, e := strconv.ParseInt(entry.Name(), 10, 32)
		if e != nil || pid < 1 {
			return false, trustFailure()
		}
		if e := platform.GuardOwned(filepath.Join(marker, entry.Name())); e != nil {
			return false, e
		}
		live, e := platform.ProcessAlive(int(pid))
		if e != nil {
			return false, e
		}
		alive = alive || live
	}
	return alive, nil
}
func (m *Manager) prepareCachePurge(p Paths, plan *lifecycle.Plan) (bool, error) {
	market := filepath.Join(p.Base, "plugins", "cache", "opensocrates")
	root := filepath.Join(market, "opensocrates")
	ms, e := lifecycle.Inspect(market)
	if e != nil {
		return false, e
	}
	if !ms.Exists {
		return false, nil
	}
	entries, e := os.ReadDir(market)
	if e != nil {
		return false, trustFailure()
	}
	if len(entries) == 0 {
		appendPurgeRemoval(plan, market, ms)
		return false, nil
	}
	if len(entries) != 1 || entries[0].Name() != "opensocrates" || !entries[0].IsDir() {
		return false, trustFailure()
	}
	versions, e := os.ReadDir(root)
	if e != nil {
		return false, trustFailure()
	}
	pending := false
	var removable []lifecycle.Mutation
	for _, version := range versions {
		if !version.IsDir() || version.Type()&os.ModeSymlink != 0 {
			return false, trustFailure()
		}
		path := filepath.Join(root, version.Name())
		s, e := verifyPurgePackage(path, version.Name())
		if e != nil {
			return false, e
		}
		live, e := cacheInUse(path)
		if e != nil {
			return false, e
		}
		if live {
			pending = true
		} else {
			removable = append(removable, lifecycle.Mutation{Target: path, Remove: true, Expected: &s})
		}
	}
	if pending {
		plan.Mutations = append(plan.Mutations, removable...)
	} else {
		appendPurgeRemoval(plan, market, ms)
	}
	return pending, nil
}
func prepareLegacyPayloadResidue(p Paths, plan *lifecycle.Plan) error {
	parent := filepath.Dir(p.Root)
	if e := platform.GuardOwned(parent); e != nil {
		if os.IsNotExist(e) {
			return nil
		}
		return e
	}
	entries, e := os.ReadDir(parent)
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil {
		return trustFailure()
	}
	for _, entry := range entries {
		if !legacyResidueName.MatchString(entry.Name()) {
			continue
		}
		candidate := p
		candidate.Root = filepath.Join(parent, entry.Name())
		s, e := lifecycle.Inspect(candidate.Root)
		if e != nil {
			return e
		}
		if len(s.Entries) == 1 && s.Entries[0].Directory {
			appendPurgeRemoval(plan, candidate.Root, s)
			continue
		}
		_, targets, e := owned(candidate, "codex")
		if e != nil {
			return e
		}
		for target, s := range targets {
			appendPurgeRemoval(plan, target, s)
		}
	}
	return nil
}
func (m *Manager) preparePriorPayloadBackups(p Paths, plan *lifecycle.Plan) error {
	dir := filepath.Join(m.StateDir, "transactions")
	entries, e := os.ReadDir(dir)
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil {
		return trustFailure()
	}
	for _, entry := range entries {
		if !journalName.MatchString(entry.Name()) {
			continue
		}
		b, e := platform.ReadFile(filepath.Join(dir, entry.Name()), 8<<20)
		if e != nil {
			return e
		}
		var j lifecycle.Journal
		if _, e := contracts.Decode(b); e != nil {
			return trustFailure()
		}
		if json.Unmarshal(b, &j) != nil || j.Schema != lifecycle.JournalSchema || entry.Name() != j.ID+".json" {
			return trustFailure()
		}
		if j.Host != "codex" || (j.Stage != "committed" && j.Stage != "rolled-back") {
			continue
		}
		for _, f := range j.Files {
			if f.Target != p.Root {
				continue
			}
			prefix := filepath.Join(filepath.Dir(p.Root), ".opensocrates-"+j.ID+"-"+filepath.Base(p.Root))
			if f.Backup != prefix+"-backup" || f.Staged != prefix+"-candidate" {
				return trustFailure()
			}
			for _, object := range []struct {
				path     string
				expected lifecycle.Snapshot
			}{{f.Backup, f.Before}, {f.Staged, f.After}} {
				s, e := lifecycle.Inspect(object.path)
				if e != nil {
					return e
				}
				if s.Exists && !lifecycle.Equal(s, object.expected) {
					return trustFailure()
				}
				appendPurgeRemoval(plan, object.path, s)
			}
		}
	}
	return nil
}
func (m *Manager) prepareLegacyStatePurge(plan *lifecycle.Plan) error {
	entries, e := os.ReadDir(m.StateDir)
	if e != nil {
		return trustFailure()
	}
	for _, entry := range entries {
		name := entry.Name()
		if name != "desired-state.json" && name != "auto-update-receipt.json" && !legacyStateResidue.MatchString(name) {
			continue
		}
		path := filepath.Join(m.StateDir, name)
		s, e := lifecycle.Inspect(path)
		if e != nil {
			return e
		}
		if len(s.Entries) != 1 || s.Entries[0].Directory {
			return trustFailure()
		}
		data, e := platform.ReadFile(path, 8<<20)
		if e != nil {
			return e
		}
		if _, e := contracts.Decode(data); e != nil {
			return trustFailure()
		}
		var value map[string]json.RawMessage
		if json.Unmarshal(data, &value) != nil {
			return trustFailure()
		}
		var schema string
		json.Unmarshal(value["schema"], &schema)
		if schema != "opensocrates.desired-state/1.0.0" && schema != "opensocrates.auto-update-receipt/1.0.0" && schema != "opensocrates.auto-update-receipt/1.1.0" {
			return trustFailure()
		}
		appendPurgeRemoval(plan, path, s)
	}
	return nil
}
