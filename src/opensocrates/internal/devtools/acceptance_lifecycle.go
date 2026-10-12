package devtools

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/management"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

func nativeLifecycleAcceptance(o acceptanceOptions) (map[string]any, error) {
	target := nativeAcceptanceTarget()
	report := map[string]any{"target": target, "evidence_scope": "isolated_native_fixture", "live_host_delivery_claimed": false, "user_installation_modified": false, "production_signing_claimed": false, "cases": map[string]any{}, "required_external_evidence": []string{"real_host_trust_and_activation", "production_signing_and_timestamping", "actual_clean_machine", "native_scheduler_activation", "signed_network_update_and_self_update"}}
	if target == "unsupported" || o.binary == "" || o.hostBinary == "" {
		return report, errors.New("native binary and native host fixture required")
	}
	binary, e := filepath.Abs(o.binary)
	if e != nil {
		return report, e
	}
	fixture, e := filepath.Abs(o.hostBinary)
	if e != nil {
		return report, e
	}
	if !acceptanceExecutableMatchesTarget(binary, target) || !acceptanceExecutableMatchesTarget(fixture, target) {
		return report, errors.New("native_acceptance_executable_architecture_mismatch")
	}
	report["executed_artifact_architecture_verified"] = true
	report["runtime_goos"] = runtime.GOOS
	report["runtime_goarch"] = runtime.GOARCH
	packageRoot, e := filepath.Abs(o.packagePath)
	if e != nil {
		return report, e
	}
	tmp, e := platform.MkdirTemp("", "opensocrates-native-acceptance-")
	if e != nil {
		return report, e
	}
	defer os.RemoveAll(tmp)
	ownedPackage := filepath.Join(tmp, "candidate-bundle")
	if e = copyAcceptanceTree(packageRoot, ownedPackage); e != nil {
		return report, e
	}
	packageRoot = ownedPackage
	bundle, e := checkObject(filepath.Join(packageRoot, "bundle-manifest.json"))
	if e != nil {
		return report, e
	}
	if bundle["target"] != target {
		return report, errors.New("native bundle target mismatch")
	}
	report["source_git_commit"] = bundle["source_git_commit"]
	report["artifact_identity"] = digest(mustAcceptanceRead(filepath.Join(packageRoot, "bundle-manifest.json")))
	report["package_preparation"] = "private_owned_copy_of_explicit_developer_fixture"
	env, work, e := isolatedAcceptanceEnvironment(tmp)
	if e != nil {
		return report, e
	}
	env = append(env, "CODEX_BIN="+fixture)
	codexRoot := filepath.Join(tmp, "codex")
	home := filepath.Join(tmp, "home")
	unrelated := filepath.Join(codexRoot, "foreign-owned.txt")
	sentinel := []byte("unrelated synthetic state\n")
	if e = platform.ExclusiveWrite(unrelated, sentinel, 0600); e != nil {
		return report, e
	}
	cases := report["cases"].(map[string]any)
	allPass := true
	run := func(name string, args ...string) bool {
		commandContext, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		started := time.Now()
		child, e := platform.Run(commandContext, binary, args, platform.RunOptions{Env: env, Dir: work, Stdin: bytes.NewReader(nil), OutputLimit: 8 << 20})
		deadlineExceeded := commandContext.Err() == context.DeadlineExceeded
		cancel()
		passed := e == nil && len(child.Stderr) == 0
		result := map[string]any{"pass": passed}
		if e != nil {
			result["failure_stage"] = "command_exit_or_deadline"
		} else if len(child.Stderr) != 0 {
			result["failure_stage"] = "unexpected_content_free_diagnostic"
		}
		if !passed {
			result["diagnostic"] = acceptanceLifecycleCommandDiagnostic(child, e, time.Since(started), deadlineExceeded, name)
		}
		cases[name] = result
		allPass = allPass && passed
		return passed
	}
	if !run("native_install", "install", "--host", "codex", "--package", packageRoot) {
		report["pass"] = false
		return report, nil
	}
	run("native_status", "status", "--host", "codex")
	run("native_diagnose", "diagnose", "--host", "codex")
	_, stderr, hostErr := runAcceptanceProcess(fixture, []string{"plugin", "disable", "opensocrates@opensocrates"}, nil, env, work, 10*time.Second)
	disabled := hostErr == nil && len(stderr) == 0
	cases["host_disabled_before_update"] = map[string]any{"pass": disabled}
	allPass = allPass && disabled
	run("offline_update_same_bundle", "update", "--host", "codex", "--package", packageRoot)
	state, e := checkObject(filepath.Join(home, ".opensocrates/native-state.json"))
	preserved := e == nil && acceptanceStateDisabled(state)
	cases["disabled_state_preserved_after_update"] = map[string]any{"pass": preserved}
	allPass = allPass && preserved
	run("owned_remove", "remove", "--host", "codex")
	b, e := os.ReadFile(unrelated)
	foreignPreserved := e == nil && bytes.Equal(b, sentinel)
	cases["foreign_file_preserved"] = map[string]any{"pass": foreignPreserved}
	allPass = allPass && foreignPreserved
	// Do not label this a clean machine or live host receipt. Every artifact was
	// created beneath a disposable test home; registration is an external fixture.
	migrationPass := acceptanceMigrationCase(tmp, packageRoot, fixture, cases)
	allPass = allPass && migrationPass
	recoveryPass := acceptanceRecoveryCases(home, binary, env, work, cases)
	allPass = allPass && recoveryPass
	if windowsAcceptanceTarget(target) {
		allPass = acceptanceWindowsNativeHelper(tmp, packageRoot, fixture, target, cases) && allPass
	}
	report["pass"] = allPass
	return report, nil
}

// Process output is reduced to bounded metadata and closed first-party error
// enums. No OS error wording, path, account identifier or arbitrary stage text
// may enter a public native receipt.
func acceptanceLifecycleCommandDiagnostic(child platform.Result, err error, elapsed time.Duration, deadlineExceeded bool, commandStage string) map[string]any {
	category := "none"
	if err != nil {
		category = string(diagnostics.CodeOf(err))
	}
	stdoutHash, stderrHash := sha256.Sum256(child.Stdout), sha256.Sum256(child.Stderr)
	report := map[string]any{"error_category": category, "child_exit_code": child.ExitCode, "deadline_exceeded": deadlineExceeded, "elapsed_ms": elapsed.Milliseconds(), "stdout_len": len(child.Stdout), "stderr_len": len(child.Stderr), "stdout_sha256": hex.EncodeToString(stdoutHash[:]), "stderr_sha256": hex.EncodeToString(stderrHash[:]), "command_stage": commandStage, "cli_error_code": "unrecognized", "cli_stage": "unrecognized"}
	// Management errors use one line `stage: error_code`. Match the complete
	// closed code token, rather than searching private output for substrings.
	if len(child.Stderr) <= 512 {
		parts := strings.Split(strings.TrimSpace(string(child.Stderr)), ": ")
		if len(parts) == 2 && !strings.ContainsAny(parts[0], "\r\n") {
			for _, code := range []diagnostics.Code{diagnostics.Verification, diagnostics.Network, diagnostics.Permission, diagnostics.Locked, diagnostics.HostUnavailable, diagnostics.ProtocolIncompatible, diagnostics.Activation, diagnostics.RollbackIncomplete, diagnostics.Unsupported} {
				if parts[1] == string(code) {
					report["cli_error_code"] = string(code)
				}
			}
			for _, stage := range strings.Fields("management arguments checksum filesystem process bundle package registration host lifecycle install candidate package_identity scheduler replacement manager-parent probe") {
				if parts[0] == stage {
					report["cli_stage"] = stage
				}
			}
		}
	}
	return report
}
func mustAcceptanceRead(p string) []byte { b, _ := os.ReadFile(p); return b }
func acceptanceStateDisabled(state map[string]any) bool {
	installations, ok := state["installations"].(map[string]any)
	if !ok || len(installations) == 0 {
		return false
	}
	found := false
	for _, raw := range installations {
		m := obj(raw)
		if m["host"] == "codex" {
			enabled, ok := m["enabled"].(bool)
			if !ok || enabled {
				return false
			}
			found = true
		}
	}
	return found
}

// AcceptanceHostFixture is a synthetic external Codex protocol implementation.
// It stores no prompts or credentials and refuses non-isolated fixture homes.
func AcceptanceHostFixture(args []string, out interface{ Write([]byte) (int, error) }) int {
	if len(args) > 0 && args[0] == "--scheduler-receipt" {
		if len(args) != 2 {
			return 2
		}
		return schedulerReceipt(args[1])
	}
	root := os.Getenv("CODEX_HOME")
	if root == "" || !strings.Contains(filepath.Clean(root), "opensocrates-native-acceptance-") {
		return 2
	}
	if len(args) == 1 && args[0] == "--version" {
		out.Write([]byte("codex-cli 0.144.4\n"))
		return 0
	}
	statePath := filepath.Join(root, "host-fixture.json")
	state := map[string]any{"marketplace": "", "installed": false, "enabled": true}
	if _, e := os.Lstat(statePath); e == nil {
		b, e := platform.ReadFile(statePath, 8<<20)
		if e != nil || json.Unmarshal(b, &state) != nil {
			return 2
		}
	} else if !os.IsNotExist(e) {
		return 2
	}
	if len(args) < 2 || args[0] != "plugin" {
		return 2
	}
	save := func() int {
		b, e := json.Marshal(state)
		if e != nil {
			return 2
		}
		var writeErr error
		if _, e := os.Lstat(statePath); os.IsNotExist(e) {
			writeErr = platform.ExclusiveWrite(statePath, b, 0600)
		} else if e == nil {
			writeErr = platform.AtomicWrite(statePath, b, 0600)
		} else {
			return 2
		}
		if writeErr != nil {
			return 2
		}
		return 0
	}
	args = args[1:]
	switch args[0] {
	case "list":
		version := "1.6.0"
		root, _ := state["marketplace"].(string)
		if root != "" {
			m, e := checkObject(filepath.Join(root, "build/generated/plugins/codex/release-manifest.json"))
			if e == nil {
				version = str(m["product_version"])
			}
		}
		entry := map[string]any{"pluginId": "opensocrates@opensocrates", "name": "opensocrates", "marketplaceName": "opensocrates", "version": version, "enabled": state["enabled"], "marketplaceRoot": root}
		installed := []any{}
		if state["installed"] == true {
			cached := clone(entry)
			if cachedVersion, ok := state["version"].(string); ok && cachedVersion != "" {
				cached["version"] = cachedVersion
			}
			installed = append(installed, cached)
		}
		available := []any{}
		if root != "" {
			available = append(available, entry)
		}
		b, _ := json.Marshal(map[string]any{"installed": installed, "available": available})
		out.Write(append(b, '\n'))
		return 0
	case "marketplace":
		if len(args) < 2 {
			return 2
		}
		switch args[1] {
		case "add":
			if len(args) < 3 {
				return 2
			}
			state["marketplace"] = args[2]
			return save()
		case "remove":
			state["marketplace"] = ""
			return save()
		case "list":
			entries := []any{}
			if root, ok := state["marketplace"].(string); ok && root != "" {
				entries = append(entries, map[string]any{"name": "opensocrates", "root": root})
			}
			b, _ := json.Marshal(entries)
			out.Write(append(b, '\n'))
			return 0
		}
		return 2
	case "install", "add":
		state["installed"] = true
		state["enabled"] = true
		// A local package replacement does not refresh the host's installed cache
		// until its next session. Keep that activation boundary in the fixture.
		marketplaceRoot, _ := state["marketplace"].(string)
		manifest, e := checkObject(filepath.Join(marketplaceRoot, "build/generated/plugins/codex/release-manifest.json"))
		if e != nil || str(manifest["product_version"]) == "" {
			return 2
		}
		state["version"] = manifest["product_version"]
		return save()
	case "uninstall", "remove":
		state["installed"] = false
		return save()
	case "enable":
		state["enabled"] = true
		return save()
	case "disable":
		state["enabled"] = false
		return save()
	}
	return 2
}

func acceptanceRecoveryCases(home, binary string, env []string, work string, cases map[string]any) bool {
	passed := true
	record := func(name string, ok bool) { cases[name] = map[string]any{"pass": ok}; passed = passed && ok }
	target := filepath.Join(home, "recovery-fixture")
	source := filepath.Join(home, "recovery-candidate")
	old := []byte("old synthetic bytes\n")
	candidate := []byte("new synthetic bytes\n")
	if platform.AtomicWrite(target, old, 0600) != nil || platform.AtomicWrite(source, candidate, 0600) != nil {
		record("interrupted_transaction_recovery", false)
		return false
	}
	before, e := lifecycle.Inspect(target)
	if e != nil {
		record("interrupted_transaction_recovery", false)
		return false
	}
	engine := lifecycle.Engine{StateDir: filepath.Join(home, ".opensocrates"), Fault: func(stage string) error {
		if stage == "prepared" {
			return errors.New("synthetic_interruption")
		}
		return nil
	}}
	journal, e := engine.Execute(context.Background(), lifecycle.Plan{Action: "acceptance-interruption", Host: "codex", Scope: "global", Mutations: []lifecycle.Mutation{{Target: target, Source: source, Expected: &before}}})
	if e == nil || journal.ID == "" {
		record("interrupted_transaction_recovery", false)
		return false
	}
	_, stderr, e := runAcceptanceProcess(binary, []string{"recover", "--transaction", journal.ID}, nil, env, work, 30*time.Second)
	b, readErr := os.ReadFile(target)
	record("interrupted_transaction_recovery", e == nil && len(stderr) == 0 && readErr == nil && bytes.Equal(b, old))
	engine.Fault = nil
	before, e = lifecycle.Inspect(target)
	if e != nil {
		return false
	}
	journal, e = engine.Execute(context.Background(), lifecycle.Plan{Action: "acceptance-rollback", Host: "codex", Scope: "global", Mutations: []lifecycle.Mutation{{Target: target, Source: source, Expected: &before}}})
	if e != nil {
		record("committed_transaction_verified_rollback", false)
		return false
	}
	activated, readErr := os.ReadFile(target)
	record("transaction_candidate_activated", readErr == nil && bytes.Equal(activated, candidate))
	_, stderr, e = runAcceptanceProcess(binary, []string{"recover", "--transaction", journal.ID}, nil, env, work, 30*time.Second)
	b, readErr = os.ReadFile(target)
	record("committed_transaction_verified_rollback", e == nil && len(stderr) == 0 && readErr == nil && bytes.Equal(b, old))
	return passed
}

type acceptanceRegistrationRunner struct {
	environment []string
	work        string
}

func (r acceptanceRegistrationRunner) Run(_ context.Context, binary string, args []string) ([]byte, error) {
	out, stderr, e := runAcceptanceProcess(binary, args, nil, r.environment, r.work, 20*time.Second)
	if len(stderr) > 0 {
		return nil, errors.New("fixture_host_diagnostic")
	}
	return out, e
}
func acceptanceMigrationCase(tmp, packageRoot, fixture string, cases map[string]any) bool {
	stage := "prepare_environment"
	failureCode := diagnostics.Verification
	record := func(passed bool) bool {
		result := map[string]any{"pass": passed, "evidence_scope": "synthetic_legacy_marker_state_and_registration; native_scheduler_commands_mocked; not_real_npm_release", "legacy_runtime_execution_claimed": false}
		if !passed {
			result["failure_stage"] = stage
			result["error_code"] = failureCode
		}
		cases["npm_owned_state_adoption_fixture"] = result
		return passed
	}
	root := filepath.Join(tmp, "migration")
	env, work, e := isolatedAcceptanceEnvironment(root)
	if e != nil {
		return record(false)
	}
	env = append(env, "CODEX_BIN="+fixture)
	home := filepath.Join(root, "home")
	stateDir := filepath.Join(home, ".opensocrates")
	legacyPackage := filepath.Join(root, "legacy-package")
	stage = "copy_legacy_payload_fixture"
	if e := copyAcceptanceTree(filepath.Join(packageRoot, "packages/codex"), legacyPackage); e != nil {
		return record(false)
	}
	// Freeze the original desired-state and three-field ownership marker formats.
	// The payload is a synthetic released-content fixture, not a live npm binary.
	stage = "prepare_legacy_plugin_identity"
	pluginPath := filepath.Join(legacyPackage, ".codex-plugin/plugin.json")
	plugin, e := checkObject(pluginPath)
	if e != nil {
		return record(false)
	}
	plugin["version"] = "1.5.0"
	pluginBytes, e := Canonical(plugin)
	if e != nil || platform.AtomicWrite(pluginPath, pluginBytes, 0644) != nil {
		return record(false)
	}
	manifestPath := filepath.Join(legacyPackage, "release-manifest.json")
	stage = "prepare_legacy_manifest_identity"
	manifest, e := checkObject(manifestPath)
	if e != nil {
		return record(false)
	}
	manifest["product_version"] = "1.5.0"
	for _, raw := range arr(manifest["files"]) {
		entry := obj(raw)
		if entry["path"] == ".codex-plugin/plugin.json" {
			entry["sha256"] = digest(pluginBytes)
			entry["size"] = len(pluginBytes)
		}
	}
	data, e := Canonical(manifest)
	if e != nil || platform.AtomicWrite(manifestPath, data, 0600) != nil {
		return record(false)
	}
	values := map[string]string{}
	for _, item := range env {
		parts := strings.SplitN(item, "=", 2)
		values[parts[0]] = parts[1]
	}
	manager := management.Manager{Home: home, StateDir: stateDir, Version: "1.6.0", GOOS: runtime.GOOS, GOARCH: runtime.GOARCH, LookupEnv: func(key string) string { return values[key] }, Runner: acceptanceRegistrationRunner{environment: env, work: work}}
	scheduler := update.NewSchedulerAdapter(runtime.GOOS, home, filepath.Join(stateDir, "bin", filepath.Base(fixture)), stateDir)
	scheduler.Command = func(_ context.Context, _ string, _ ...string) ([]byte, error) { return []byte{}, nil }
	manager.Scheduler = scheduler
	// Simulate the previous installer's already-owned layout directly. Running a
	// new install here would correctly reject the synthetic 1.5 identity because
	// its copied Go executable is 1.6. Only the actual new adoption candidate is
	// executed by the production preactivation/version probe below.
	hostRoot := filepath.Join(root, "codex/managed-marketplaces/opensocrates")
	stage = "prepare_legacy_owned_layout"
	if e := copyAcceptanceTree(legacyPackage, filepath.Join(hostRoot, "build/generated/plugins/codex")); e != nil {
		return record(false)
	}
	marketplacePath := filepath.Join(hostRoot, ".agents/plugins/marketplace.json")
	if platform.Mkdir(filepath.Dir(marketplacePath)) != nil || platform.Mkdir(stateDir) != nil {
		return record(false)
	}
	marketplace := []byte(`{"name":"opensocrates","interface":{"displayName":"OpenSocrates"},"plugins":[{"name":"opensocrates","source":{"source":"local","path":"./build/generated/plugins/codex"},"policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"Productivity"}]}` + "\n")
	if platform.AtomicWrite(marketplacePath, marketplace, 0600) != nil {
		return record(false)
	}
	marker := []byte("{\"schemaVersion\":1,\"marketplaceName\":\"opensocrates\",\"pluginName\":\"opensocrates\"}\n")
	if platform.AtomicWrite(filepath.Join(hostRoot, management.MarkerName), marker, 0600) != nil {
		return record(false)
	}
	// Unknown fields and disabled integrations belong to the user. Adoption keeps
	// the full prior JSON in the new state and never deletes an npm package.
	desired := []byte(`{"schema":"opensocrates.desired-state/1.0.0","channel":"stable","installedHosts":["codex"],"activeVersion":"1.5.0","updatePolicy":{"intervalHours":24,"allowMajor":false},"autoUpdate":{"enabled":false,"hosts":[],"nextCheckAt":null},"future_user_owned_field":{"unicode":"한국","exact_integer":9007199254740993}}` + "\n")
	stage = "prepare_legacy_desired_state"
	if platform.AtomicWrite(filepath.Join(stateDir, "desired-state.json"), desired, 0600) != nil {
		return record(false)
	}
	npmSentinel := filepath.Join(root, "npm-user-owned.json")
	npmBytes := []byte("{\"do_not_remove\":true}\n")
	stage = "prepare_foreign_npm_state"
	if platform.AtomicWrite(npmSentinel, npmBytes, 0600) != nil {
		return record(false)
	}
	stage = "prepare_legacy_registration"
	for _, args := range [][]string{{"plugin", "marketplace", "add", hostRoot, "--json"}, {"plugin", "add", "opensocrates@opensocrates", "--json"}, {"plugin", "disable", "opensocrates@opensocrates"}} {
		if _, stderr, e := runAcceptanceProcess(fixture, args, nil, env, work, 10*time.Second); e != nil || len(stderr) != 0 {
			return record(false)
		}
	}
	stage = "adopt_actual_native_candidate"
	if _, e := manager.Handle(context.Background(), management.Request{Action: "adopt", Host: "codex", Package: packageRoot}); e != nil {
		failureCode = diagnostics.CodeOf(e)
		return record(false)
	}
	state, e := checkObject(filepath.Join(stateDir, "native-state.json"))
	stage = "verify_update_owner_and_disabled_state"
	if e != nil || state["update_owner"] != "native" || !acceptanceStateDisabled(state) {
		return record(false)
	}
	old, e := checkJSON(filepath.Join(stateDir, "desired-state.json"))
	stage = "verify_preserved_legacy_state"
	if e != nil {
		return record(false)
	}
	stored := state["legacy_desired_state"]
	a, _ := Canonical(old)
	b, _ := Canonical(stored)
	npmAfter, e := os.ReadFile(npmSentinel)
	if e != nil || !bytes.Equal(npmBytes, npmAfter) || !bytes.Equal(a, b) {
		return record(false)
	}
	policy, e := checkObject(filepath.Join(stateDir, "update-policy.json"))
	stage = "verify_disabled_update_policy"
	if e != nil || policy["enabled"] != false {
		return record(false)
	}
	return record(true)
}

// copyAcceptanceTree prepares newly created fixture objects with explicit
// current-user ownership. It never repairs source ACLs or overwrites a target.
func copyAcceptanceTree(from, to string) error {
	var count int
	var total int64
	return filepath.WalkDir(from, func(path string, entry os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return errors.New("linked_acceptance_source")
		}
		relative, e := filepath.Rel(from, path)
		if e != nil {
			return e
		}
		destination := filepath.Join(to, relative)
		info, e := entry.Info()
		if e != nil {
			return e
		}
		count++
		if count > lifecycle.MaxFiles {
			return errors.New("acceptance_source_inventory_limit")
		}
		if info.IsDir() {
			lease, e := platform.Lease(filepath.Join(path, ".acceptance-source-validation"))
			if e != nil {
				return e
			}
			lease.Close()
			return platform.Mkdir(destination)
		}
		if !info.Mode().IsRegular() {
			return errors.New("nonregular_acceptance_source")
		}
		total += info.Size()
		if info.Size() > lifecycle.MaxFileBytes || total > lifecycle.MaxTotalBytes {
			return errors.New("acceptance_source_size_limit")
		}
		data, e := readAcceptanceSource(path, lifecycle.MaxFileBytes)
		if e != nil {
			return e
		}
		if int64(len(data)) != info.Size() {
			return errors.New("acceptance_source_changed")
		}
		if e = platform.Mkdir(filepath.Dir(destination)); e != nil {
			return e
		}
		mode := info.Mode().Perm() &^ 0022
		return platform.ExclusiveWrite(destination, data, mode)
	})
}
