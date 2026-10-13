package devtools

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

func TestInstallProfileCompletionNeverQualifiesThirtySecondGate(t *testing.T) {
	for _, scenario := range []struct {
		name                        string
		elapsed                     time.Duration
		child                       platform.Result
		err                         error
		deadline, completed, within bool
	}{
		{"long-completion", 45 * time.Second, platform.Result{ExitCode: 0}, nil, false, true, false},
		{"short-completion", 29 * time.Second, platform.Result{ExitCode: 0}, nil, false, true, true},
		{"deadline", installProfileTimeout, platform.Result{ExitCode: -1}, diagnostics.New(diagnostics.HostUnavailable, "process"), true, false, false},
		{"early-error", 5 * time.Second, platform.Result{ExitCode: 1}, diagnostics.New(diagnostics.HostUnavailable, "process"), false, false, true},
		{"unexpected-diagnostic", 5 * time.Second, platform.Result{ExitCode: 0, Stderr: []byte("PRIVATE-ERROR-ACCOUNT")}, nil, false, false, true},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			report := map[string]any{"qualification_claimed": false, "native_lifecycle_gate_pass_claimed": false}
			installProfileCommandOutcome(scenario.child, scenario.err, scenario.elapsed, scenario.deadline, report)
			if report["install_completed"] != scenario.completed || report["within_original_install_budget"] != scenario.within {
				t.Fatal("diagnostic completion and original budget conflated")
			}
			if _, ok := report["pass"]; ok || report["qualification_claimed"] != false || report["native_lifecycle_gate_pass_claimed"] != false {
				t.Fatal("independent diagnostic promoted to native qualification")
			}
			data, err := json.Marshal(report)
			if err != nil || bytes.Contains(data, []byte("PRIVATE-ERROR-ACCOUNT")) {
				t.Fatal("private diagnostic output exported")
			}
		})
	}
	if installProfileTimeout != 120*time.Second || originalInstallBudget != 30*time.Second {
		t.Fatal("diagnostic or original budget changed")
	}
}

func TestInstallProfileBundleIdentityDoesNotExportRowsOrUnvalidatedIdentities(t *testing.T) {
	bundle := map[string]any{"schema": "opensocrates.native-bundle/1.0.0", "target": "windows-arm64", "source_git_commit": strings.Repeat("a", 40), "source_tree_hash": "sha256:" + strings.Repeat("b", 64), "normalized_semantic_hash": "sha256:" + strings.Repeat("c", 64), "files": []any{map[string]any{"path": "PRIVATE-ABSOLUTE-USER-PATH", "size": contracts.Number(50), "token": "PRIVATE-TOKEN"}, map[string]any{"path": "PRIVATE-SECOND-PATH", "size": contracts.Number(7)}}, "unknown_private_field": "PRIVATE-PROMPT"}
	raw, _ := json.Marshal(bundle)
	report := map[string]any{}
	if err := installProfileBundleIdentity(bundle, "windows-arm64", raw, report); err != nil {
		t.Fatal(err)
	}
	if report["inventory_file_count"] != 2 || report["inventory_declared_bytes"] != int64(57) || report["artifact_identity"] != digest(raw) {
		t.Fatal("bounded declared inventory identity missing")
	}
	data, _ := json.Marshal(report)
	if bytes.Contains(data, []byte("PRIVATE-")) {
		t.Fatal("artifact rows or unknown fields exported")
	}
	tooMany := make([]any, lifecycle.MaxFiles+1)
	tooLarge := []any{}
	for i := 0; i < 5; i++ {
		tooLarge = append(tooLarge, map[string]any{"size": contracts.Number(lifecycle.MaxFileBytes)})
	}
	for _, change := range []struct {
		key   string
		value any
	}{
		{"source_git_commit", "PRIVATE-ACCOUNT"},
		{"source_tree_hash", "sha256:PRIVATE-PATH"},
		{"normalized_semantic_hash", "PRIVATE-PROMPT"},
		{"target", "windows-x64"},
		{"files", []any{map[string]any{"size": contracts.Number(-1)}}},
		{"files", []any{map[string]any{"size": contracts.Number(lifecycle.MaxFileBytes + 1)}}},
		{"files", []any{map[string]any{"size": json.Number("9007199254740993")}}},
		{"files", tooMany},
		{"files", tooLarge},
		{"files", []any{}},
	} {
		modified := clone(bundle)
		modified[change.key] = change.value
		rejected := map[string]any{}
		if installProfileBundleIdentity(modified, "windows-arm64", raw, rejected) == nil || len(rejected) != 0 {
			t.Fatal("unvalidated artifact identity entered public diagnostic")
		}
	}
}

func TestInstallProfileRejectsAuthenticatedStateAndUsesDiagnosticOnlySchema(t *testing.T) {
	var out, errout bytes.Buffer
	reportRoot, err := platform.MkdirTemp("", "opensocrates-install-profile-report-test-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(reportRoot) })
	reportPath := filepath.Join(reportRoot, "diagnostic.json")
	// No child is started: the diagnostic rejects a real/authenticated home before
	// any artifact lookup or fixture creation. Do not echo that path in output.
	result := RunAcceptance([]string{"install-profile", "--binary", "not-executed", "--host-binary", "not-executed", "--codex-home", "PRIVATE-REAL-AUTH-HOME", "--report", reportPath}, &out, &errout)
	if result != 2 || bytes.Contains(out.Bytes(), []byte("PASS")) || bytes.Contains(out.Bytes(), []byte("PRIVATE-")) || bytes.Contains(errout.Bytes(), []byte("PRIVATE-")) {
		t.Fatal("diagnostic authentication rejection or status unsafe")
	}
	raw, err := platform.ReadFile(reportPath, 8<<20)
	if err != nil {
		t.Fatal(err)
	}
	var report map[string]any
	if json.Unmarshal(raw, &report) != nil || report["schema"] != "opensocrates.native-install-profile/1.0.0" || report["qualification_claimed"] != false || report["production_signing_claimed"] != false || report["user_installation_modified"] != false || report["install_attempt_count"] != float64(0) {
		t.Fatal("diagnostic receipt claims qualification or real-user mutation")
	}
	if _, ok := report["pass"]; ok || bytes.Contains(raw, []byte("PRIVATE-")) {
		t.Fatal("native pass or private arguments recorded")
	}
}

func TestInstallProfileCleanupDeletesOnlyItsOwnedFixture(t *testing.T) {
	root, err := platform.MkdirTemp("", installProfileFixturePrefix)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(root) })
	path := filepath.Join(root, "synthetic.json")
	if err = platform.AtomicWrite(path, []byte("synthetic private fixture"), 0600); err != nil {
		t.Fatal(err)
	}
	if err = cleanupInstallProfileFixture(root); err != nil {
		t.Fatal("owned diagnostic fixture cleanup unavailable")
	}
	if _, err = os.Lstat(root); !os.IsNotExist(err) {
		t.Fatal("owned fixture retained")
	}
	foreign := t.TempDir()
	sentinel := filepath.Join(foreign, "user-owned.txt")
	if err = os.WriteFile(sentinel, []byte("preserve"), 0600); err != nil {
		t.Fatal(err)
	}
	if cleanupInstallProfileFixture(foreign) == nil {
		t.Fatal("foreign cleanup scope accepted")
	}
	if raw, err := os.ReadFile(sentinel); err != nil || string(raw) != "preserve" {
		t.Fatal("foreign fixture modified")
	}
}

func TestInstallProfileDispatcherSavesPrivateRelativeAndAbsoluteUnavailableReports(t *testing.T) {
	cwd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	// Create a new private same-volume fixture so the relative form works on
	// Windows too. The report writer does not normalize existing directory ACLs.
	root, err := platform.MkdirTemp(cwd, ".opensocrates-install-profile-output-test-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(root) })
	for _, mode := range []string{"relative", "absolute"} {
		t.Run(mode, func(t *testing.T) {
			absolute := filepath.Join(root, mode, "diagnostic.json")
			argument := absolute
			if mode == "relative" {
				argument, err = filepath.Rel(cwd, absolute)
				if err != nil || filepath.IsAbs(argument) {
					t.Fatal("relative report fixture unavailable")
				}
			}
			var out, errout bytes.Buffer
			result := RunAcceptance([]string{"install-profile", "--codex-home", "PRIVATE-AUTH-HOME", "--report", argument}, &out, &errout)
			if result != 2 || errout.Len() != 0 || !strings.Contains(out.String(), "install-profile: UNAVAILABLE diagnostic-only") {
				t.Fatal("unavailable diagnostic report was not saved")
			}
			raw, readError := platform.ReadFile(absolute, 8<<20)
			if readError != nil {
				t.Fatal("private unavailable report missing")
			}
			var report map[string]any
			if json.Unmarshal(raw, &report) != nil || report["schema"] != "opensocrates.native-install-profile/1.0.0" || report["status"] != "unavailable" || report["install_attempt_count"] != float64(0) || report["qualification_claimed"] != false {
				t.Fatal("saved diagnostic claimed install qualification")
			}
			encodedRoot, _ := json.Marshal(root)
			if bytes.Contains(raw, encodedRoot) || bytes.Contains(raw, []byte("PRIVATE-AUTH-HOME")) || bytes.Contains(out.Bytes(), []byte(root)) || bytes.Contains(errout.Bytes(), []byte(root)) {
				t.Fatal("private output path or authentication argument disclosed")
			}
		})
	}
}
