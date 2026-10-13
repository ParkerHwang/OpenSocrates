package devtools

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

const installProfileTimeout = 120 * time.Second
const originalInstallBudget = 30 * time.Second
const installProfileFixturePrefix = "opensocrates-native-acceptance-install-profile-"

// nativeInstallProfile is an independent single-install timing diagnostic. Its
// success cannot qualify nativeLifecycleAcceptance; the 30-second comparison
// records the historical generic command window independently of qualification.
// As in that gate, all developer inputs are copied into a newly owned private
// fixture before the timed install. Source cache state is not measured.
func nativeInstallProfile(o acceptanceOptions) (report map[string]any, profileError error) {
	target := nativeAcceptanceTarget()
	report = map[string]any{
		"schema": "opensocrates.native-install-profile/1.0.0", "target": target,
		"diagnostic_status": "unavailable", "qualification_claimed": false,
		"native_lifecycle_gate_pass_claimed": false, "production_signing_claimed": false,
		"user_installation_modified": false, "live_host_delivery_claimed": false,
		"evidence_scope":                 "single_initial_install_in_fresh_private_synthetic_fixture",
		"timing_scope":                   "actual_install_command_only; fixture_copy_excluded; source_cache_state_unmeasured",
		"original_install_budget_ms":     originalInstallBudget.Milliseconds(),
		"diagnostic_timeout_ms":          installProfileTimeout.Milliseconds(),
		"within_original_install_budget": false, "install_completed": false,
		"install_attempt_count": 0,
		"profile_setup_stage":   "arguments", "cleanup_status": "not_created", "cleanup_verified": false,
	}
	unavailable := errors.New("install_profile_unavailable")
	if target == "unsupported" || o.binary == "" || o.hostBinary == "" || o.packagePath == "" || o.codexHome != "" || o.fixtureID != "" {
		return report, unavailable
	}
	report["profile_setup_stage"] = "architecture"
	binary, err := filepath.Abs(o.binary)
	if err != nil {
		return report, unavailable
	}
	fixture, err := filepath.Abs(o.hostBinary)
	if err != nil {
		return report, unavailable
	}
	if !acceptanceExecutableMatchesTarget(binary, target) || !acceptanceExecutableMatchesTarget(fixture, target) {
		return report, unavailable
	}
	report["executed_artifact_architecture_verified"] = true
	report["runtime_goos"], report["runtime_goarch"] = runtime.GOOS, runtime.GOARCH
	source, err := filepath.Abs(o.packagePath)
	if err != nil {
		return report, unavailable
	}
	report["profile_setup_stage"] = "fixture"
	root, err := platform.MkdirTemp("", installProfileFixturePrefix)
	if err != nil {
		return report, unavailable
	}
	report["cleanup_status"] = "pending"
	defer func() {
		if cleanupInstallProfileFixture(root) == nil {
			report["cleanup_status"], report["cleanup_verified"] = "verified", true
		} else {
			report["cleanup_status"] = "unavailable"
			report["diagnostic_status"] = "unavailable"
			profileError = unavailable
		}
	}()
	report["profile_setup_stage"] = "package_copy"
	candidate := filepath.Join(root, "candidate-bundle")
	if err = copyAcceptanceTree(source, candidate); err != nil {
		return report, unavailable
	}
	report["profile_setup_stage"] = "bundle_identity"
	raw, err := platform.ReadOwnedFile(filepath.Join(candidate, "bundle-manifest.json"), 8<<20)
	if err != nil {
		return report, unavailable
	}
	value, err := contracts.Decode(raw)
	if err != nil {
		return report, unavailable
	}
	if err = installProfileBundleIdentity(obj(value), target, raw, report); err != nil {
		return report, unavailable
	}
	report["package_preparation"] = "private_owned_copy_of_explicit_developer_fixture"
	report["profile_setup_stage"] = "environment"
	env, work, err := isolatedAcceptanceEnvironment(root)
	if err != nil {
		return report, unavailable
	}
	env = append(env, "CODEX_BIN="+fixture)
	sentinel := filepath.Join(root, "codex/foreign-owned.txt")
	sentinelBytes := []byte("unrelated synthetic state\n")
	if err = platform.ExclusiveWrite(sentinel, sentinelBytes, 0600); err != nil {
		return report, unavailable
	}
	report["profile_setup_stage"] = "install"
	report["install_attempt_count"] = 1
	ctx, cancel := context.WithTimeout(context.Background(), installProfileTimeout)
	started := time.Now()
	child, runError := platform.Run(ctx, binary, []string{"install", "--host", "codex", "--package", candidate}, platform.RunOptions{Env: env, Dir: work, Stdin: bytes.NewReader(nil), OutputLimit: 8 << 20})
	elapsed := time.Since(started)
	deadlineExceeded := ctx.Err() == context.DeadlineExceeded
	cancel()
	// platform.Run joins the child and owns cancellation of its descendants.
	// Observe before cleanup; never recover, retry, authenticate, or activate a
	// real scheduler/host as part of this independent measurement.
	installProfileCommandOutcome(child, runError, elapsed, deadlineExceeded, report)
	report["owned_fixture_observation"] = acceptanceInstallFailureObservation(root)
	after, readError := platform.ReadFile(sentinel, 4096)
	report["foreign_fixture_preserved"] = readError == nil && bytes.Equal(after, sentinelBytes)
	report["profile_setup_stage"] = "complete"
	return report, nil
}

func installProfileCommandOutcome(child platform.Result, err error, elapsed time.Duration, deadlineExceeded bool, report map[string]any) {
	report["elapsed_ms"] = elapsed.Milliseconds()
	report["within_original_install_budget"] = elapsed <= originalInstallBudget
	completed := err == nil && child.ExitCode == 0 && len(child.Stderr) == 0 && !deadlineExceeded
	report["install_completed"] = completed
	report["diagnostic_status"] = "failed"
	if completed {
		report["diagnostic_status"] = "completed"
	}
	report["command_diagnostic"] = acceptanceLifecycleCommandDiagnostic(child, err, elapsed, deadlineExceeded, "native_install")
}

// Artifact identities are validated before exporting values supplied by an
// explicit developer bundle. Inventory paths and row contents are never emitted.
func installProfileBundleIdentity(bundle map[string]any, target string, raw []byte, report map[string]any) error {
	invalid := errors.New("install_profile_bundle_unavailable")
	if bundle["schema"] != "opensocrates.native-bundle/1.0.0" || bundle["target"] != target || !publicationCommitPattern.MatchString(str(bundle["source_git_commit"])) {
		return invalid
	}
	for _, key := range []string{"source_tree_hash", "normalized_semantic_hash"} {
		value := str(bundle[key])
		if len(value) != 71 || !strings.HasPrefix(value, "sha256:") {
			return invalid
		}
		for _, r := range value[7:] {
			if !(r >= '0' && r <= '9') && !(r >= 'a' && r <= 'f') {
				return invalid
			}
		}
	}
	files, ok := bundle["files"].([]any)
	if !ok || len(files) == 0 || len(files) > lifecycle.MaxFiles {
		return invalid
	}
	var total int64
	for _, raw := range files {
		entry, ok := raw.(map[string]any)
		if !ok {
			return invalid
		}
		size, ok := contracts.Int(entry["size"])
		if !ok || size < 0 || size > lifecycle.MaxFileBytes || total > lifecycle.MaxTotalBytes-size {
			return invalid
		}
		total += size
	}
	report["source_git_commit"] = bundle["source_git_commit"]
	report["source_tree_hash"], report["normalized_semantic_hash"] = bundle["source_tree_hash"], bundle["normalized_semantic_hash"]
	report["artifact_identity"] = digest(raw)
	report["inventory_file_count"], report["inventory_declared_bytes"] = len(files), total
	report["inventory_evidence_scope"] = "declared_native_bundle_manifest"
	return nil
}

func cleanupInstallProfileFixture(root string) error {
	if !filepath.IsAbs(root) || !strings.HasPrefix(filepath.Base(filepath.Clean(root)), installProfileFixturePrefix) || len(filepath.Base(filepath.Clean(root))) <= len(installProfileFixturePrefix) || acceptanceObserverPresence(root, true) != "present" {
		return errors.New("install_profile_cleanup_unavailable")
	}
	if err := platform.RemoveTree(root); err != nil {
		return errors.New("install_profile_cleanup_unavailable")
	}
	if _, err := os.Lstat(root); !errors.Is(err, os.ErrNotExist) {
		return errors.New("install_profile_cleanup_unavailable")
	}
	return nil
}

func runInstallProfile(o acceptanceOptions, out, errout io.Writer) int {
	report, err := nativeInstallProfile(o)
	report["generated_at"] = time.Now().UTC().Format(time.RFC3339)
	report["privacy"] = map[string]bool{"environment_recorded": false, "absolute_paths_recorded": false, "process_output_recorded": false, "prompt_recorded": false}
	if err != nil {
		report["diagnostic_status"] = "unavailable"
	}
	status := str(report["diagnostic_status"])
	report["status"] = status
	if o.report != "" {
		reportPath, pathError := filepath.Abs(o.report)
		data, writeError := json.MarshalIndent(report, "", "  ")
		if pathError != nil || writeError != nil || platform.Mkdir(filepath.Dir(reportPath)) != nil || platform.AtomicWrite(reportPath, append(data, '\n'), 0600) != nil {
			fmt.Fprintln(errout, "install-profile: evidence unavailable")
			return 2
		}
	}
	fmt.Fprintf(out, "install-profile: %s diagnostic-only target=%s\n", strings.ToUpper(status), nativeAcceptanceTarget())
	if status == "completed" {
		return 0
	}
	if status == "failed" {
		return 1
	}
	return 2
}
