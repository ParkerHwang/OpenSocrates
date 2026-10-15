package devtools

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func governanceEntryFixture(t *testing.T) string {
	t.Helper()
	source := generatorRepository(t)
	root := t.TempDir()
	for _, relative := range []string{"AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", ".github/pull_request_template.md", ".github/workflows/ci.yml"} {
		if e := os.MkdirAll(filepath.Dir(filepath.Join(root, relative)), 0700); e != nil {
			t.Fatal(e)
		}
		if e := copyCheckTree(filepath.Join(source, relative), filepath.Join(root, relative)); e != nil {
			t.Fatal(e)
		}
	}
	return root
}
func writeGovernanceEvent(t *testing.T, root, name string, event any) string {
	t.Helper()
	b, e := json.Marshal(event)
	if e != nil {
		t.Fatal(e)
	}
	path := filepath.Join(root, name)
	if e = os.WriteFile(path, b, 0600); e != nil {
		t.Fatal(e)
	}
	return path
}
func TestGovernanceEntryDefaultsToActionsEventAndChecksPRBody(t *testing.T) {
	root := governanceEntryFixture(t)
	event := map[string]any{"pull_request": map[string]any{"body": validTestPR(), "draft": false}}
	path := writeGovernanceEvent(t, root, "event.json", event)
	t.Setenv("GITHUB_EVENT_PATH", path)
	t.Setenv("GITHUB_EVENT_NAME", "pull_request")
	reportPath := filepath.Join(root, "report.json")
	var out, diagnostics bytes.Buffer
	if code := RunChecks([]string{"governance", "--root", root, "--report", reportPath}, &out, &diagnostics); code != 0 {
		t.Fatalf("valid Actions PR rejected: %d %s", code, diagnostics.String())
	}
	report, e := checkObject(reportPath)
	if e != nil {
		t.Fatal(e)
	}
	detail := obj(obj(obj(report["checks"])["governance"])["detail"])
	if detail["pull_request_checked"] != true || detail["event_scope"] != "pull_request" {
		t.Fatal("Actions PR body check was not recorded")
	}
	event["pull_request"].(map[string]any)["body"] = strings.Replace(validTestPR(), "## Impact", "## Missing impact", 1)
	writeGovernanceEvent(t, root, "event.json", event)
	diagnostics.Reset()
	if code := RunChecks([]string{"governance", "--root", root}, &out, &diagnostics); code != 1 || !strings.Contains(diagnostics.String(), "section_missing:Impact") {
		t.Fatalf("Actions event bypassed missing PR section: %d %s", code, diagnostics.String())
	}
	override := writeGovernanceEvent(t, root, "explicit-event.json", map[string]any{"pull_request": map[string]any{"body": validTestPR(), "draft": false}})
	if code := RunChecks([]string{"governance", "--root", root, "--event", override}, &out, &diagnostics); code != 0 {
		t.Fatal("explicit event override did not replace Actions default")
	}
}
func TestGovernanceEntryRecordsPushSourceScopeAndRejectsUnknownShapes(t *testing.T) {
	root := governanceEntryFixture(t)
	t.Setenv("GITHUB_EVENT_NAME", "push")
	event := map[string]any{"ref": "refs/heads/main", "before": strings.Repeat("a", 40), "after": strings.Repeat("b", 40)}
	path := writeGovernanceEvent(t, root, "event.json", event)
	t.Setenv("GITHUB_EVENT_PATH", path)
	reportPath := filepath.Join(root, "report.json")
	var out, diagnostics bytes.Buffer
	if code := RunChecks([]string{"governance", "--root", root, "--report", reportPath}, &out, &diagnostics); code != 0 {
		t.Fatalf("push source governance failed: %d %s", code, diagnostics.String())
	}
	report, e := checkObject(reportPath)
	if e != nil {
		t.Fatal(e)
	}
	detail := obj(obj(obj(report["checks"])["governance"])["detail"])
	if detail["pull_request_checked"] != false || detail["event_scope"] != "push_source_only" {
		t.Fatal("push was not recorded as source-only validation")
	}
	for _, bad := range []any{map[string]any{}, map[string]any{"pull_request": nil}, map[string]any{"pull_request": []any{}}, map[string]any{"pull_request": map[string]any{"body": validTestPR(), "draft": "false"}}, map[string]any{"ref": "refs/heads/main", "after": "bad"}} {
		writeGovernanceEvent(t, root, "event.json", bad)
		if code := RunChecks([]string{"governance", "--root", root}, &out, &diagnostics); code != 1 {
			t.Fatalf("unknown/malformed event accepted: %d", code)
		}
	}
}
func TestGovernanceReadyPRRequiresEveryTemplateAttestation(t *testing.T) {
	for _, phrase := range []string{"Relevant tests pass.", "Generated files were produced by their canonical generators or no generated inputs changed.", "English and Korean user-facing documentation remain aligned or no localized user-facing text changed.", "No credentials, private prompts, transcripts, sensitive paths, or local-only artifacts were added.", "Required checks not run are explained below."} {
		body := strings.Replace(validTestPR(), "- [x] "+phrase, "- [ ] "+phrase, 1)
		event := map[string]any{"pull_request": map[string]any{"body": body, "draft": false}}
		if len(ValidatePullRequest(event)) == 0 {
			t.Fatalf("mandatory attestation unchecked: %s", phrase)
		}
		event["pull_request"].(map[string]any)["draft"] = true
		if codes := ValidatePullRequest(event); len(codes) != 0 {
			t.Fatalf("draft incomplete-check allowance removed: %v", codes)
		}
	}
	commented := strings.Replace(validTestPR(), "- [x] Relevant tests pass.", "<!-- - [x] Relevant tests pass. -->", 1)
	if len(ValidatePullRequest(map[string]any{"pull_request": map[string]any{"body": commented, "draft": false}})) == 0 {
		t.Fatal("hidden comment counted as ready attestation")
	}
}
