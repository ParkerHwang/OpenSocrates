package devtools

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

var requiredPRSections = []string{"Summary", "Impact", "Tracking", "Validation", "Evidence level", "Remaining limitations", "Handoff"}
var meaningfulPlaceholders = map[string]bool{"": true, "n/a": true, "none": true, "todo": true, "tbd": true, "pending": true, "-": true}

func meaningfulPR(s string) bool {
	s = regexp.MustCompile(`(?s)<!--.*?-->`).ReplaceAllString(s, "")
	return !meaningfulPlaceholders[strings.ToLower(strings.TrimSpace(s))]
}
func prSections(body string) map[string]string {
	body = regexp.MustCompile(`(?s)<!--.*?-->`).ReplaceAllString(body, "")
	result := map[string]string{}
	name := ""
	for _, line := range strings.Split(body, "\n") {
		if strings.HasPrefix(line, "## ") {
			name = strings.TrimSpace(strings.TrimPrefix(line, "## "))
			if _, exists := result[name]; !exists {
				result[name] = ""
			}
			continue
		}
		if name != "" {
			result[name] += line + "\n"
		}
	}
	return result
}
func prField(section, name string) (string, bool) {
	re := regexp.MustCompile(`(?im)^[ \t]*(?:-\s*)?` + regexp.QuoteMeta(name) + `:[ \t]*([^\n]*)$`)
	m := re.FindStringSubmatch(section)
	if len(m) < 2 {
		return "", false
	}
	return m[1], true
}

// ValidatePullRequest preserves the existing durable handoff and draft rules.
func ValidatePullRequest(event map[string]any) []string {
	raw, present := event["pull_request"]
	if !present {
		return nil
	}
	pr, ok := raw.(map[string]any)
	if !ok {
		return []string{"pull_request_event_shape_invalid"}
	}
	body, bodyOK := pr["body"].(string)
	if !bodyOK && pr["body"] != nil {
		return []string{"pull_request_body_shape_invalid"}
	}
	draft, draftOK := pr["draft"].(bool)
	if !draftOK {
		return []string{"pull_request_draft_shape_invalid"}
	}
	s := prSections(body)
	codes := []string{}
	for _, heading := range requiredPRSections {
		v, exists := s[heading]
		if !exists {
			codes = append(codes, "section_missing:"+heading)
		} else if !meaningfulPR(v) {
			codes = append(codes, "section_empty:"+heading)
		}
	}
	tracking := regexp.MustCompile(`(?s)<!--.*?-->`).ReplaceAllString(s["Tracking"], "")
	issue := regexp.MustCompile(`(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#[0-9]+\b`).MatchString(tracking)
	explanation, ok := prField(tracking, "No issue")
	if !issue && (!ok || !meaningfulPR(explanation)) {
		codes = append(codes, "tracking_issue_missing")
	}
	for _, field := range []string{"Priority", "Workstream"} {
		v, ok := prField(tracking, field)
		if !ok || !meaningfulPR(v) {
			codes = append(codes, "tracking_field_missing:"+field)
		}
	}
	if !regexp.MustCompile(`(?im)^\s*-\s*\[[xX]\]\s*(?:Implemented|Locally validated|Release-validated|Live host receipt captured|Required evidence is unavailable)\b`).MatchString(s["Evidence level"]) {
		codes = append(codes, "evidence_level_unchecked")
	}
	for _, field := range []string{"Last verified commit", "Commands run", "Commands not run", "Remaining work", "Known limitations"} {
		v, ok := prField(s["Handoff"], field)
		if !ok {
			codes = append(codes, "handoff_field_missing:"+field)
		} else if !meaningfulPR(v) && !(draft && (field == "Last verified commit" || field == "Commands run")) {
			codes = append(codes, "handoff_field_empty:"+field)
		}
	}
	if !draft {
		for _, attestation := range []struct{ phrase, code string }{
			{"Relevant tests pass.", "ready_tests_unchecked"},
			{"Generated files were produced by their canonical generators or no generated inputs changed.", "ready_generated_unchecked"},
			{"English and Korean user-facing documentation remain aligned or no localized user-facing text changed.", "ready_localization_unchecked"},
			{"No credentials, private prompts, transcripts, sensitive paths, or local-only artifacts were added.", "ready_privacy_unchecked"},
			{"Required checks not run are explained below.", "ready_unavailable_checks_unexplained"},
		} {
			if !regexp.MustCompile(`(?im)^\s*-\s*\[[xX]\]\s*` + regexp.QuoteMeta(attestation.phrase) + `\s*$`).MatchString(s["Validation"]) {
				codes = append(codes, attestation.code)
			}
		}
	}
	return codes
}
func foldCheckText(s string) string { return strings.ToLower(strings.Join(strings.Fields(s), " ")) }
func checkGovernance(root, eventPath string) ([]string, any, error) {
	detail := map[string]any{"event_scope": "not_provided", "pull_request_checked": false}
	required := map[string][]string{"AGENTS.md": {"protected `main`", "hand-edit", "semantically aligned", "telemetry", "last verified commit", "plugin-src/<host>/", "retained legacy Codex selector", "Native Claude entry does not invoke that selector or read transcripts", "New Windows host qualification remains a separate stage"}, "CLAUDE.md": {"repository development", "AGENTS.md", "file is not the installed product controller"}, ".github/copilot-instructions.md": {"AGENTS.md", "protected `main`", "hand-edit"}, ".github/pull_request_template.md": {}}
	codes := []string{}
	for rel, phrases := range required {
		b, e := os.ReadFile(filepath.Join(root, rel))
		if e != nil {
			codes = append(codes, "governance_file_missing:"+rel)
			continue
		}
		folded := foldCheckText(string(b))
		for _, phrase := range phrases {
			if !strings.Contains(folded, foldCheckText(phrase)) {
				codes = append(codes, "governance_policy_missing:"+rel+":"+phrase)
			}
		}
		if rel == ".github/pull_request_template.md" {
			s := prSections(string(b))
			for _, heading := range requiredPRSections {
				if _, exists := s[heading]; !exists {
					codes = append(codes, "template_section_missing:"+heading)
				}
			}
		}
	}
	workflow, e := os.ReadFile(filepath.Join(root, ".github/workflows/ci.yml"))
	if e != nil || !(strings.Contains(string(workflow), "make governance-check") || strings.Contains(string(workflow), "check governance") || strings.Contains(string(workflow), "check all")) {
		codes = append(codes, "ci_governance_gate_missing")
	}
	if eventPath != "" {
		if !filepath.IsAbs(eventPath) {
			eventPath = filepath.Join(root, eventPath)
		}
		event, e := checkObject(eventPath)
		if e != nil {
			detail["event_scope"] = "unavailable"
			return codes, detail, e
		}
		switch {
		case event["pull_request"] != nil:
			detail["event_scope"] = "pull_request"
			detail["pull_request_checked"] = true
			codes = append(codes, ValidatePullRequest(event)...)
		case isGovernancePush(event):
			detail["event_scope"] = "push_source_only"
		case os.Getenv("GITHUB_EVENT_NAME") == "workflow_dispatch" && isGovernanceDispatch(event):
			detail["event_scope"] = "workflow_dispatch_source_only"
		default:
			detail["event_scope"] = "unrecognized"
			codes = append(codes, "github_event_shape_unrecognized")
		}
	}
	return codes, detail, nil
}

func isGovernancePush(event map[string]any) bool {
	if _, exists := event["pull_request"]; exists {
		return false
	}
	ref, ok := event["ref"].(string)
	if !ok || !(strings.HasPrefix(ref, "refs/heads/") || strings.HasPrefix(ref, "refs/tags/")) {
		return false
	}
	sha := regexp.MustCompile(`^[0-9a-f]{40}$`)
	before, beforeOK := event["before"].(string)
	after, afterOK := event["after"].(string)
	return beforeOK && afterOK && sha.MatchString(before) && sha.MatchString(after)
}

func isGovernanceDispatch(event map[string]any) bool {
	if _, exists := event["pull_request"]; exists {
		return false
	}
	_, ok := event["inputs"].(map[string]any)
	return ok
}
