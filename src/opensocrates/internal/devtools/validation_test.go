package devtools

import (
	"bytes"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func validationTestObject(t *testing.T, s string) map[string]any {
	t.Helper()
	d := json.NewDecoder(strings.NewReader(s))
	d.UseNumber()
	var v map[string]any
	if e := d.Decode(&v); e != nil {
		t.Fatal(e)
	}
	return v
}
func TestStrictSchemaPrecisionUnicodeAndOptionalValues(t *testing.T) {
	s := validationTestObject(t, `{"type":"object","additionalProperties":false,"required":["integer","text","nullable"],"properties":{"integer":{"type":"integer","minimum":9007199254740993},"text":{"type":"string","minLength":2,"maxLength":2},"nullable":{"type":["string","null"]},"optional":{"type":"array","items":{"type":"string"}}}}`)
	valid := validationTestObject(t, `{"integer":9007199254740993,"text":"한국","nullable":null,"optional":[]}`)
	if found := ValidateSchema(valid, s); len(found) != 0 {
		t.Fatalf("valid input: %v", found)
	}
	for _, input := range []string{`{"integer":9007199254740992,"text":"한국","nullable":null}`, `{"integer":9007199254740993.1,"text":"한국","nullable":null}`, `{"integer":true,"text":"한국","nullable":null}`, `{"integer":9007199254740993,"text":"한국"}`, `{"integer":9007199254740993,"text":"한국","nullable":null,"foreign":0}`} {
		if found := ValidateSchema(validationTestObject(t, input), s); len(found) == 0 {
			t.Fatal("invalid input accepted")
		}
	}
}
func TestSchemaVocabularyFailsClosed(t *testing.T) {
	s := validationTestObject(t, `{"type":"object","properties":{"nested":{"unevaluatedProperties":false}}}`)
	if len(CheckSchema(s)) == 0 {
		t.Fatal("unsupported assertion ignored")
	}
	s = validationTestObject(t, `{"type":"string","format":"date-time"}`)
	if len(ValidateSchema("2026-99-99T25:01:00Z", s)) == 0 {
		t.Fatal("invalid date accepted")
	}
}
func TestSchemaUniqueNumbersCompareMathematically(t *testing.T) {
	s := validationTestObject(t, `{"type":"array","uniqueItems":true}`)
	if len(ValidateSchema([]any{json.Number("1"), json.Number("1.0")}, s)) == 0 {
		t.Fatal("duplicate numeric value accepted")
	}
	if len(ValidateSchema([]any{json.Number("9007199254740992"), json.Number("9007199254740993")}, s)) != 0 {
		t.Fatal("distinct precise values collapsed")
	}
}
func validTestPR() string {
	return "## Summary\nPort runtime to Go.\n## Impact\nNative installation preserves trust.\n## Tracking\nCloses #111\nPriority: P1\nWorkstream: Migration\n## Validation\n- [x] Relevant tests pass.\n- [x] Generated files were produced by their canonical generators or no generated inputs changed.\n- [x] English and Korean user-facing documentation remain aligned or no localized user-facing text changed.\n- [x] No credentials, private prompts, transcripts, sensitive paths, or local-only artifacts were added.\n- [x] Required checks not run are explained below.\n## Evidence level\n- [x] Implemented\n## Remaining limitations\nWindows live host evidence unavailable.\n## Handoff\nLast verified commit: 0123456789abcdef\nCommands run: go test ./... passed\nCommands not run: signed release unavailable\nRemaining work: obtain native receipts\nKnown limitations: pending live evidence\n"
}
func TestGovernanceBodyMutations(t *testing.T) {
	body := validTestPR()
	event := func(b string, draft bool) map[string]any {
		return map[string]any{"pull_request": map[string]any{"body": b, "draft": draft}}
	}
	if found := ValidatePullRequest(event(body, false)); len(found) != 0 {
		t.Fatal(found)
	}
	for _, change := range [][2]string{{"## Impact", "## Missing impact"}, {"Closes #111", "<!-- Closes #111 -->"}, {"Priority: P1", "Priority: TODO"}, {"Workstream: Migration", "Workstream:"}, {"- [x] Implemented", "- [ ] Implemented"}, {"Commands not run: signed release unavailable", "Commands not run: TBD"}, {"- [x] Relevant tests pass.", "- [ ] Relevant tests pass."}} {
		b := strings.Replace(body, change[0], change[1], 1)
		if len(ValidatePullRequest(event(b, false))) == 0 {
			t.Errorf("accepted mutation %s", change[0])
		}
	}
	draft := strings.Replace(body, "Last verified commit: 0123456789abcdef", "Last verified commit:", 1)
	if found := ValidatePullRequest(event(draft, true)); len(found) != 0 {
		t.Fatal(found)
	}
	if len(ValidatePullRequest(event(draft, false))) == 0 {
		t.Fatal("ready empty SHA accepted")
	}
}
func TestLinkFragmentAndEscape(t *testing.T) {
	root := t.TempDir()
	write := func(name, body string) {
		t.Helper()
		if e := os.WriteFile(filepath.Join(root, name), []byte(body), 0600); e != nil {
			t.Fatal(e)
		}
	}
	write("target.md", "# 한국 제목\n# Duplicate\n# Duplicate\n<a id=\"custom\"></a>\n")
	write("source.md", "[한글](target.md#"+headingSlug("한국 제목")+")\n[duplicate](target.md#duplicate-1)\n[html](target.md#custom)\n[external](https://example.test/missing)\n")
	codes, _, e := checkLinks(root, []string{"source.md"})
	if e != nil || len(codes) > 0 {
		t.Fatalf("valid links: %v %v", codes, e)
	}
	write("source.md", "[bad](target.md#missing)\n[escape](../outside.md)\n[script](javascript:alert)\n")
	codes, _, e = checkLinks(root, []string{"source.md"})
	if e != nil || len(codes) != 3 {
		t.Fatalf("bad links: %v %v", codes, e)
	}
}

func TestLinksResolveRootAliasesAndRejectExternalTargets(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "repository")
	if e := os.Mkdir(root, 0700); e != nil {
		t.Fatal(e)
	}
	alias := filepath.Join(base, "repository-alias")
	if e := os.Symlink(root, alias); e != nil {
		t.Skip("directory symlink requires native platform permission")
	}
	outside := filepath.Join(base, "outside.md")
	for path, body := range map[string]string{
		filepath.Join(root, "target.md"): "# Inside\n",
		outside:                          "# Outside\n",
		filepath.Join(root, "source.md"): "[inside](target.md#inside)\n[symlink](escaped.md#outside)\n[lexical](../outside.md#outside)\n",
	} {
		if e := os.WriteFile(path, []byte(body), 0600); e != nil {
			t.Fatal(e)
		}
	}
	if e := os.Symlink(outside, filepath.Join(root, "escaped.md")); e != nil {
		t.Fatal(e)
	}
	codes, _, e := checkLinks(alias, []string{"source.md"})
	if e != nil || len(codes) != 2 || !strings.Contains(strings.Join(codes, " "), "source.md:2:link_escapes_repository") || !strings.Contains(strings.Join(codes, " "), "source.md:3:link_escapes_repository") {
		t.Fatalf("root alias or external-target boundary failed: %v %v", codes, e)
	}
	if _, _, e := checkLinks(alias, []string{"escaped.md"}); e == nil {
		t.Fatal("selected document outside the canonical repository root was accepted")
	}
}
func TestGeneratedComparisonDetectsExtraAndChangedFiles(t *testing.T) {
	a, b := t.TempDir(), t.TempDir()
	if e := os.WriteFile(filepath.Join(a, "a.json"), []byte("{}\n"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(b, "a.json"), []byte("{ }\n"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(b, "foreign.json"), []byte("{}\n"), 0600); e != nil {
		t.Fatal(e)
	}
	codes, e := compareCheckTree(a, b)
	if e != nil || len(codes) != 2 {
		t.Fatal(codes, e)
	}
}
func TestPackageIntegrityAndClosedInventory(t *testing.T) {
	root := t.TempDir()
	readme := []byte("one-time interactive hook approval; non-interactive `codex exec` silently skips untrusted hooks; no live Codex hook-delivery receipt; teacher questions\n")
	hook := []byte(`{"hooks":{"SessionStart":[{"hooks":[{"command":"\"$PLUGIN_ROOT/runtime/darwin-arm64/opensocrates\" hook codex session_started","timeout":2}]}],"UserPromptSubmit":[{"hooks":[{"command":"\"$PLUGIN_ROOT/runtime/darwin-arm64/opensocrates\" hook codex user_prompt_submitted"}]}]}}`)
	files := map[string][]byte{"README.md": readme, "hooks/hooks.json": hook}
	canonical := []any{}
	fixed, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	for _, method := range fixed.Methods {
		for _, locale := range []string{"en", "ko"} {
			id := method.ID
			name := "references/" + locale + "/" + id + ".md"
			expected, e := fixed.Assemble([]string{id}, locale)
			if e != nil {
				t.Fatal(e)
			}
			body := []byte(expected)
			files[name] = body
			canonical = append(canonical, map[string]any{"method_id": id, "locale": locale, "path": name, "sha256": digest(body)})
		}
	}
	inventory := []any{}
	for name, b := range files {
		p := filepath.Join(root, name)
		if e := os.MkdirAll(filepath.Dir(p), 0700); e != nil {
			t.Fatal(e)
		}
		if e := os.WriteFile(p, b, 0600); e != nil {
			t.Fatal(e)
		}
		inventory = append(inventory, map[string]any{"path": name, "sha256": digest(b), "size": len(b)})
	}
	m := map[string]any{"host": "codex", "product_version": "1.6.0", "release_targets": []string{"darwin-arm64"}, "shell_requirement": "posix", "files": inventory, "canonical_methods": canonical, "source_tree_hash": "sha256:b8824656fc53d588cc6a570de102531266ef2a7b39f04694d058c8da5c2418a6", "normalized_semantic_hash": "sha256:e50af8296165a7c8e8a9a6e27d4881bbc816b7efe9e1c84ea798c80fb54efa48"}
	raw, _ := json.Marshal(m)
	if e := os.WriteFile(filepath.Join(root, "release-manifest.json"), raw, 0600); e != nil {
		t.Fatal(e)
	}
	if codes, e := checkPackageTree(root); e != nil || len(codes) > 0 {
		t.Fatalf("valid package: %v %v", codes, e)
	}
	if e := os.WriteFile(filepath.Join(root, "README.md"), append(readme, '!'), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(root, "foreign"), []byte("x"), 0600); e != nil {
		t.Fatal(e)
	}
	codes, e := checkPackageTree(root)
	if e != nil || !strings.Contains(strings.Join(codes, " "), "package_hash_mismatch") || !strings.Contains(strings.Join(codes, " "), "package_unlisted_file") {
		t.Fatalf("tampering accepted: %v %v", codes, e)
	}
}
func TestConfiguredHookCommandsAreClosedByPlatformAndEvent(t *testing.T) {
	for _, c := range []struct{ command, host, target, event string }{{`"$PLUGIN_ROOT/runtime/darwin-arm64/opensocrates" hook codex session_started`, "codex", "darwin-arm64", "SessionStart"}, {`& "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" hook codex session_started`, "codex", "windows-x64", "SessionStart"}, {`"$CLAUDE_PLUGIN_ROOT/runtime/darwin-arm64/opensocrates" hook claude session_started`, "claude", "darwin-arm64", "SessionStart"}} {
		if !configuredHookMatches(c.command, c.host, c.target, c.event) {
			t.Fatal("configured supported hook rejected")
		}
		for _, suffix := range []string{"; echo x", " | cat", " & malicious", " extra"} {
			if configuredHookMatches(c.command+suffix, c.host, c.target, c.event) {
				t.Fatal("configured command widened")
			}
		}
	}
	for _, command := range []string{`"$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" hook codex session_started`, `"${PLUGIN_ROOT}\runtime\windows-x64\opensocrates.exe" hook codex session_started`, `"%PLUGIN_ROOT%\runtime\windows-x64\opensocrates.exe" hook codex session_started`} {
		if configuredHookMatches(command, "codex", "windows-x64", "SessionStart") {
			t.Fatal("unqualified Windows shell accepted")
		}
	}
}

func TestTimingExactSourceContract(t *testing.T) {
	if !hookTimingResponse("startup", nil) || hookTimingResponse("startup", []byte("{}")) {
		t.Fatal("startup contract")
	}
	v := map[string]any{"hookSpecificOutput": map[string]any{"hookEventName": "SessionStart", "additionalContext": timingEntryGuidance}}
	b, _ := json.Marshal(v)
	if !hookTimingResponse("compact", b) || hookTimingResponse("compact", append(b, []byte(" {}")...)) || hookTimingResponse("compact", bytes.ReplaceAll(b, []byte("No initial method"), []byte("A method"))) {
		t.Fatal("compact contract")
	}
	values := make([]float64, 20)
	for i := range values {
		values[i] = float64(i + 1)
	}
	if timingPercentile(values, 95) != 19 {
		t.Fatal("wrong nearest rank p95")
	}
}

func TestPackageClaimBoundaryMutations(t *testing.T) {
	for _, claim := range []string{"This package verifies clean-machine installation.", "Automatic hook delivery was verified.", "Code signing is complete.", "The archive is validated for public release.", "This package is fully supported on all Codex platforms.", "The product is approved by OpenAI.", "This package is safe on managed machines."} {
		if len(packageClaimErrors(claim)) == 0 {
			t.Fatalf("overclaim accepted: %s", claim)
		}
	}
	for _, claim := range []string{"This package does not verify clean-machine installation.", "Code signing is not validated.", "This archive cannot verify clean-machine installation."} {
		if codes := packageClaimErrors(claim); len(codes) > 0 {
			t.Fatalf("limitation rejected: %v", codes)
		}
	}
	if len(packageClaimErrors("This package does not verify earlier data, but verifies clean-machine installation.")) == 0 {
		t.Fatal("earlier negation hid later claim")
	}
}
func TestBlindPacketsKeepOutcomesOutOfNestedData(t *testing.T) {
	v := map[string]any{"case": []any{map[string]any{"selected_reasoning_systems": []any{"critical-thinking"}}}}
	if len(forbiddenPacketFields(v, "$")) != 1 {
		t.Fatal("nested outcome leaked")
	}
	empty := map[string]any{"schema": "schema-id", "pair_id": "synthetic", "review": map[string]any{"rationale": nil, "methods": []any{}}}
	if !emptyBlindDecisionForm(empty, "$") {
		t.Fatal("empty decision form rejected")
	}
	empty["review"].(map[string]any)["rationale"] = "prefilled"
	if emptyBlindDecisionForm(empty, "$") {
		t.Fatal("prefilled decision accepted")
	}
}
func TestSourceBoundaryMutation(t *testing.T) {
	root := t.TempDir()
	p := filepath.Join(root, "src/opensocrates/internal/domain")
	if e := os.MkdirAll(p, 0700); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(p, "bad.go"), []byte("package domain\nimport \"os/exec\"\nvar _ = exec.Command\n"), 0600); e != nil {
		t.Fatal(e)
	}
	codes, e := checkBoundaries(root)
	if e != nil || len(codes) == 0 {
		t.Fatalf("domain process dependency accepted: %v %v", codes, e)
	}
}
