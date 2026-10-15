package runtimecli

import (
	"bytes"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestDiagnoseReportsNativeProcessArchitecture(t *testing.T) {
	code, output, stderr := invoke([]string{"diagnose", "--json"}, "")
	if code != 0 || stderr != "" {
		t.Fatal("native architecture diagnosis unavailable")
	}
	value, err := contracts.Decode([]byte(output))
	if err != nil {
		t.Fatal(err)
	}
	platform := value.(map[string]any)["platform"].(map[string]any)
	if platform["os"] != runtime.GOOS || platform["architecture"] != runtime.GOARCH {
		t.Fatal("diagnostic relabeled process architecture")
	}
}

func invoke(args []string, input string) (int, string, string) {
	var out, err bytes.Buffer
	code := Run(args, strings.NewReader(input), &out, &err)
	return code, out.String(), err.String()
}
func TestDecisionCLIHasNoStorageOrAuthenticationDependency(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("LOCALAPPDATA", home)
	t.Setenv("OPENSOCRATES_SELECTOR_MODE", "legacy")
	t.Setenv("OPENSOCRATES_CODEX_BINARY", filepath.Join(home, "missing"))
	code, out, stderr := invoke([]string{"decision"}, `{"operation":"catalog","locale":"ko"}`)
	if code != 0 || stderr != "" {
		t.Fatal(code, stderr)
	}
	v, e := contracts.Decode([]byte(out))
	if e != nil {
		t.Fatal(e)
	}
	m := v.(map[string]any)
	if m["status"] != "catalog" || len(m["methods"].([]any)) != 48 {
		t.Fatal(m)
	}
	entries, e := os.ReadDir(home)
	if e != nil || len(entries) != 0 {
		t.Fatal("decision initialized storage", entries, e)
	}
}
func TestNDJSONKeepsOneVolatileSessionAndBoundedInput(t *testing.T) {
	code, out, stderr := invoke([]string{"decision", "--stream"}, "{\"operation\":\"catalog\",\"locale\":\"en\"}\n{\"operation\":\"reset\"}\n")
	if code != 0 || stderr != "" || len(strings.Split(strings.TrimSpace(out), "\n")) != 2 {
		t.Fatal(code, stderr)
	}
	_, tooLarge, _ := invoke([]string{"decision"}, strings.Repeat(" ", 16385))
	if !strings.Contains(tooLarge, "request_too_large") {
		t.Fatal(tooLarge)
	}
	_, empty, _ := invoke([]string{"decision"}, "")
	if empty != "" {
		t.Fatal("empty input produced output")
	}
}
func TestCodexNativeHooksFailOpenAndNeverPersistPrompt(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("LOCALAPPDATA", home)
	t.Setenv("OPENSOCRATES_SELECTOR_MODE", "")
	for _, input := range []string{`{}`, `{"hook_event_name":"UserPromptSubmit","prompt":null}`, `{"hook_event_name":"UserPromptSubmit","prompt":"x","session_id":false}`, `{"hook_event_name":"UserPromptSubmit","prompt":"x","prompt":"y"}`} {
		code, out, err := invoke([]string{"hook", "codex", "user_prompt_submitted"}, input)
		if code != 0 || out != "" || err != "" {
			t.Fatalf("malformed native input emitted %q %q", out, err)
		}
	}
	code, out, err := invoke([]string{"hook", "codex", "user_prompt_submitted"}, `{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL","session_id":"session","turn_id":"turn"}`)
	if code != 0 || err != "" || !strings.Contains(out, "decision-point entry") || strings.Contains(out, "PRIVATE_SENTINEL") {
		t.Fatal(out, err)
	}
	entries, e := os.ReadDir(home)
	if e != nil || len(entries) != 0 {
		t.Fatal("native discovery created user state", entries, e)
	}
	_, out, _ = invoke([]string{"hook", "codex", "session_started"}, `{"hook_event_name":"SessionStart","source":"startup"}`)
	if out != "" {
		t.Fatal("startup wasn't literal no-op")
	}
	t.Setenv("OPENSOCRATES_SELECTOR_ACTIVE", "1")
	_, out, _ = invoke([]string{"hook", "codex", "user_prompt_submitted"}, `{"hook_event_name":"UserPromptSubmit","prompt":"private"}`)
	if out != "" {
		t.Fatal("recursive hook emitted")
	}
}
func TestClaudeNativeEntryUsesCompleteInstalledReferences(t *testing.T) {
	root := t.TempDir()
	for _, relative := range []string{"skills/opensocrates/SKILL.md", "skills/opensocrates/references/decision/guide.en.md", "skills/opensocrates/references/decision/guide.ko.md", "skills/opensocrates/references/decision/guide.zh.md", "skills/opensocrates/references/decision/guide.ja.md", "skills/opensocrates/references/decision/guide.fr.md", "skills/opensocrates/references/decision/guide.de.md", "skills/opensocrates/references/decision/guide.it.md", "skills/opensocrates/references/decision/guide.es.md", "skills/opensocrates/references/decision/guide.pt.md", "skills/opensocrates/references/decision/guide.th.md"} {
		path := filepath.Join(root, filepath.FromSlash(relative))
		if e := os.MkdirAll(filepath.Dir(path), 0700); e != nil {
			t.Fatal(e)
		}
		if e := os.WriteFile(path, []byte("canonical installed reference"), 0600); e != nil {
			t.Fatal(e)
		}
	}
	var out bytes.Buffer
	code := RunClaudeHookAtRoot(strings.NewReader(`{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL","transcript_path":"/unused"}`), &out, root)
	if code != 0 || !strings.Contains(out.String(), "Installed Claude controller") || strings.Contains(out.String(), "PRIVATE_SENTINEL") {
		t.Fatal(out.String())
	}
	if e := os.Remove(filepath.Join(root, "skills/opensocrates/references/decision/guide.ko.md")); e != nil {
		t.Fatal(e)
	}
	out.Reset()
	RunClaudeHookAtRoot(strings.NewReader(`{"hook_event_name":"SessionStart","source":"resume"}`), &out, root)
	if out.Len() != 0 {
		t.Fatal("incomplete locale references admitted")
	}
}
func TestDecisionRejectsWorkspaceContentFallback(t *testing.T) {
	dir := t.TempDir()
	if e := os.Mkdir(filepath.Join(dir, "content"), 0700); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(dir, "content", "compiled-content.bundle.json"), []byte("PRIVATE_WORKSPACE_CONTENT"), 0600); e != nil {
		t.Fatal(e)
	}
	old, e := os.Getwd()
	if e != nil {
		t.Fatal(e)
	}
	if e = os.Chdir(dir); e != nil {
		t.Fatal(e)
	}
	defer os.Chdir(old)
	code, out, err := invoke([]string{"decision"}, `{"operation":"catalog","locale":"en"}`)
	if code != 0 || err != "" || strings.Contains(out, "PRIVATE_WORKSPACE_CONTENT") || !strings.Contains(out, "critical-thinking") {
		t.Fatal(out, err)
	}
}
func TestInvalidRuntimeArgumentsDoNotReadInput(t *testing.T) {
	for _, args := range [][]string{{"decision", "--foreign"}, {"rigor", "set", "unknown"}, {"version", "--foreign"}, {"capabilities", "show", "--host", "claude"}, {"diagnose", "--markdown", "--json"}} {
		var out, stderr bytes.Buffer
		if code := Run(args, unreadable{}, &out, &stderr); code != 2 || out.Len() != 0 {
			t.Fatalf("arguments %v accepted", args)
		}
	}
}

type unreadable struct{}

func (unreadable) Read([]byte) (int, error) { return 0, io.ErrUnexpectedEOF }
func TestVersionIdentityTracksImmutableContent(t *testing.T) {
	bundle, err := content.Load()
	if err != nil {
		t.Fatal(err)
	}
	info := VersionInfo()
	if info["content_revision"] != bundle.Revision {
		t.Fatalf("version content identity differs from embedded bundle: %v", info)
	}
	future := versionInfoForBundle(&content.Bundle{Revision: 4})
	if future["content_revision"] != 4 {
		t.Fatalf("future content revision was replaced by release baseline: %v", future)
	}
	unavailable := versionInfoForBundle(nil)
	if unavailable["content_revision"] != nil || unavailable["content_status"] != "unavailable" {
		t.Fatalf("unavailable content reported a confirmed revision: %v", unavailable)
	}
}

func TestLocaleCLIChoicesResetAndClosedArguments(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("LOCALAPPDATA", home)
	t.Setenv("XDG_DATA_HOME", home)
	commands := [][]string{{"locale", "get"}}
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th", "follow"} {
		commands = append(commands, []string{"locale", "set", locale}, []string{"locale", "get"})
	}
	commands = append(commands, []string{"locale", "reset"}, []string{"locale", "get"})
	for _, args := range commands {
		code, out, err := invoke(args, "")
		if code != 0 || err != "" {
			t.Fatal(args, code, err)
		}
		value, e := contracts.Decode([]byte(out))
		if e != nil || value.(map[string]any)["status"] != "ok" {
			t.Fatal(args, out, e)
		}
		m := value.(map[string]any)
		if len(args) == 3 && m["locale"] != args[2] {
			t.Fatal("set response mismatch", m)
		}
		if args[1] == "reset" && m["locale"] != "follow" {
			t.Fatal("reset response mismatch", m)
		}
		if _, present := m["rigor"]; present {
			t.Fatal("locale leaked unrelated settings")
		}
	}
	for _, args := range [][]string{{"locale"}, {"locale", "codex", "get"}, {"locale", "get", "extra"}, {"locale", "reset", "extra"}, {"locale", "set"}, {"locale", "set", "zh", "extra"}} {
		if code, _, _ := invoke(args, ""); code != 2 {
			t.Fatal("invalid CLI shape accepted", args)
		}
	}
	for _, locale := range []string{"zh-CN", "jp", "JA", "fr-FR", "pt-BR", "th-TH", ""} {
		code, out, _ := invoke([]string{"locale", "set", locale}, "")
		if code != 2 || out != "" {
			t.Fatal("invalid choice not rejected", locale, out)
		}
	}
}

func TestDecisionCatalogAllLocalesRemainsStateless(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("LOCALAPPDATA", home)
	t.Setenv("XDG_DATA_HOME", home)
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		code, out, stderr := invoke([]string{"decision"}, `{"operation":"catalog","locale":"`+locale+`"}`)
		value, e := contracts.Decode([]byte(out))
		if code != 0 || stderr != "" || e != nil || value.(map[string]any)["status"] != "catalog" {
			t.Fatal(locale, out, stderr, e)
		}
	}
	entries, e := os.ReadDir(home)
	if e != nil || len(entries) != 0 {
		t.Fatal("locale decision created storage", entries, e)
	}
}

func TestMalformedDecisionJSONHasClosedRepairAndStreamContinues(t *testing.T) {
	for _, input := range []string{`{"PRIVATE_SYNTHETIC_VALUE":`, `{"operation":"reset","operation":"reset"}`, `{"operation":"catalog"}{"operation":"reset"}`} {
		for _, stream := range []bool{false, true} {
			args := []string{"decision"}
			if stream {
				args = append(args, "--stream")
				input += "\n" + `{"operation":"catalog","locale":"ko"}` + "\n"
			}
			code, output, stderr := invoke(args, input)
			if code != 0 || stderr != "" || strings.Contains(output, "PRIVATE_SYNTHETIC_VALUE") {
				t.Fatal("malformed input leaked or failed closed")
			}
			lines := strings.Split(strings.TrimSpace(output), "\n")
			v, err := contracts.Decode([]byte(lines[0]))
			if err != nil {
				t.Fatal(err)
			}
			m := v.(map[string]any)
			if m["reason"] != "invalid_decision_request" || m["field"] != "request" || m["error"] != "invalid_json" || m["repair"] != "correct_field_once" || m["applied"] != "unverified" {
				t.Fatal("malformed input lacks closed repair")
			}
			if stream && (len(lines) != 2 || !strings.Contains(lines[1], `"status":"catalog"`)) {
				t.Fatal("stream did not continue after malformed input")
			}
		}
	}
	var out bytes.Buffer
	runDecision(unreadable{}, &out, false)
	if !strings.Contains(out.String(), `"reason":"decision_unavailable"`) || strings.Contains(out.String(), "correct_field_once") {
		t.Fatal("reader failure was mislabeled as repairable JSON")
	}
}
