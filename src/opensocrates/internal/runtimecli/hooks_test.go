package runtimecli

import (
	"bytes"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func codexEntryFixture(t *testing.T) string {
	t.Helper()
	home := t.TempDir()
	for _, key := range []string{"HOME", "USERPROFILE", "LOCALAPPDATA", "XDG_DATA_HOME"} {
		t.Setenv(key, home)
	}
	t.Setenv("OPENSOCRATES_SELECTOR_ACTIVE", "")
	t.Setenv("OPENSOCRATES_SELECTOR_MODE", "")
	previous := legacyFactory
	legacyFactory = func() (HookServices, error) {
		t.Fatal("native discovery constructed legacy services")
		return nil, nil
	}
	t.Cleanup(func() { legacyFactory = previous })
	return home
}

func codexHookFixture(t *testing.T, fields map[string]any) []byte {
	t.Helper()
	raw, err := json.Marshal(fields)
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func codexSizedSubmission(t *testing.T, size int) []byte {
	t.Helper()
	fields := map[string]any{"hook_event_name": "UserPromptSubmit", "session_id": "fixture", "prompt": ""}
	padding := size - len(codexHookFixture(t, fields))
	if padding < 0 {
		t.Fatal("requested envelope is smaller than its metadata")
	}
	fields["prompt"] = strings.Repeat("x", padding)
	return codexHookFixture(t, fields)
}

func codexEntryOutput(t *testing.T, raw []byte, lane string) string {
	t.Helper()
	var out bytes.Buffer
	if code := runHook([]string{"codex", lane}, bytes.NewReader(raw), &out); code != 0 {
		t.Fatal("hook did not fail open")
	}
	return out.String()
}

func TestCodexSubmissionEntryByteBoundariesAndContentIndependence(t *testing.T) {
	home := codexEntryFixture(t)
	expected := codexEntryOutput(t, codexSizedSubmission(t, 173), "user_prompt_submitted")
	value, err := contracts.Decode([]byte(expected))
	if err != nil || value.(map[string]any)["hookSpecificOutput"].(map[string]any)["additionalContext"] != EntryGuidance {
		t.Fatal("submission did not emit discovery guidance")
	}
	for _, size := range []int{32767, 32768, 32769, 96822, 256*1024 + 1, maxHookInputBytes - 1, maxHookInputBytes} {
		t.Run(strconv.Itoa(size), func(t *testing.T) {
			raw := codexSizedSubmission(t, size)
			if len(raw) != size || codexEntryOutput(t, raw, "user_prompt_submitted") != expected {
				t.Fatal("bounded submission changed or lost discovery guidance")
			}
		})
	}
	for _, prompt := range []string{strings.Repeat("한", 32244), strings.Repeat(`\"`, 24000)} {
		raw := codexHookFixture(t, map[string]any{"hook_event_name": "UserPromptSubmit", "session_id": "fixture", "prompt": prompt})
		if codexEntryOutput(t, raw, "user_prompt_submitted") != expected {
			t.Fatal("UTF-8 or escaped submission changed discovery guidance")
		}
	}
	if codexEntryOutput(t, codexSizedSubmission(t, maxHookInputBytes+1), "user_prompt_submitted") != "" {
		t.Fatal("over-bound submission emitted guidance")
	}
	reader := bytes.NewReader(codexSizedSubmission(t, maxHookInputBytes+2))
	var out bytes.Buffer
	if code := runHook([]string{"codex", "user_prompt_submitted"}, reader, &out); code != 0 || out.Len() != 0 || reader.Len() != 1 {
		t.Fatal("hook ingress did not stop after its finite bound plus one byte")
	}
	entries, err := os.ReadDir(home)
	if err != nil || len(entries) != 0 {
		t.Fatal("submission discovery initialized storage")
	}
}

func TestCodexSubmissionEntryProjectsOnlyCleanupIdentity(t *testing.T) {
	codexEntryFixture(t)
	fields := map[string]any{
		"hook_event_name": "UserPromptSubmit", "session_id": "fixture",
		"prompt":  strings.Repeat("SYNTHETIC_PRIVATE_SENTINEL", 8000),
		"turn_id": "SYNTHETIC_PRIVATE_SENTINEL", "cwd": "/SYNTHETIC_PRIVATE_SENTINEL",
		"transcript_path": "/SYNTHETIC_PRIVATE_SENTINEL", "model": "SYNTHETIC_PRIVATE_SENTINEL",
		"SYNTHETIC_PRIVATE_SENTINEL": map[string]any{"tool_response": "SYNTHETIC_PRIVATE_SENTINEL"},
	}
	projected, ok := codexSubmissionMetadata(codexHookFixture(t, fields), fields)
	if !ok || len(projected) != 2 || projected["hook_event_name"] != "UserPromptSubmit" || projected["session_id"] != "fixture" {
		t.Fatal("discovery retained fields beyond event and cleanup identity")
	}
	expected := codexEntryOutput(t, codexSizedSubmission(t, 173), "user_prompt_submitted")
	if output := codexEntryOutput(t, codexHookFixture(t, fields), "user_prompt_submitted"); output != expected || strings.Contains(output, "SYNTHETIC_PRIVATE_SENTINEL") {
		t.Fatal("discovery disclosed or routed on task content")
	}
	// Like main #128, discovery does not consume these fields. Their types do
	// not become new admission requirements; the bounded JSON shape still is.
	for _, key := range []string{"turn_id", "cwd", "transcript_path", "model", "version", "host_version"} {
		fields[key] = false
	}
	if codexEntryOutput(t, codexHookFixture(t, fields), "user_prompt_submitted") != expected {
		t.Fatal("unused metadata blocked discovery")
	}
}

func TestCodexSubmissionEntryPreservesShapeTypeAndEventGuards(t *testing.T) {
	codexEntryFixture(t)
	invalid := [][]byte{
		[]byte(`{`), []byte(`[]`), {0xff},
		[]byte(`{"hook_event_name":"UserPromptSubmit","prompt":null}`),
		[]byte(`{"hook_event_name":"UserPromptSubmit","prompt":1}`),
		[]byte(`{"hook_event_name":"UserPromptSubmit","prompt":["text"]}`),
		[]byte(`{"hook_event_name":"UserPromptSubmit"}`),
		[]byte(`{"hook_event_name":"user_prompt_submitted","prompt":"synthetic"}`),
		[]byte(`{"hook_event_name":"Stop","prompt":"synthetic"}`),
		[]byte(`{"hook_event_name":"UserPromptSubmit","prompt":"bad\u0000prompt"}`),
		[]byte(`{"hook_event_name":"UserPromptSubmit","prompt":"\ud800"}`),
		[]byte(`{"hook_event_name":"UserPromptSubmit","prompt":"x","prompt":"y"}`),
	}
	for _, session := range []any{false, 1, strings.Repeat("x", 257), "bad\x00id"} {
		invalid = append(invalid, codexHookFixture(t, map[string]any{"hook_event_name": "UserPromptSubmit", "prompt": "synthetic", "session_id": session}))
	}
	var nested any
	for i := 0; i < 13; i++ {
		nested = []any{nested}
	}
	wide := map[string]any{}
	for i := 0; i < 129; i++ {
		wide[strconv.Itoa(i)] = nil
	}
	for _, extra := range []any{nested, make([]any, 257), wide} {
		invalid = append(invalid, codexHookFixture(t, map[string]any{"hook_event_name": "UserPromptSubmit", "prompt": "synthetic", "extra": extra}))
	}
	for i, raw := range invalid {
		if codexEntryOutput(t, raw, "user_prompt_submitted") != "" {
			t.Fatal("malformed discovery envelope emitted output", i)
		}
	}
	valid := codexSizedSubmission(t, 173)
	if codexEntryOutput(t, valid, "completion_candidate") != "" {
		t.Fatal("mismatched event lane emitted guidance")
	}
	t.Setenv("OPENSOCRATES_SELECTOR_ACTIVE", "1")
	if codexEntryOutput(t, valid, "user_prompt_submitted") != "" {
		t.Fatal("recursive selector hook emitted guidance")
	}
}

type codexLegacyHookFixture struct {
	calls int
}

func (f *codexLegacyHookFixture) HandleLegacy(_ []byte, _ string) (map[string]any, error) {
	f.calls++
	return nil, nil
}

func (f *codexLegacyHookFixture) CleanupExisting(_ string) error { return nil }

func TestCodexSubmissionEntryKeepsLegacyAndOtherEventBounds(t *testing.T) {
	codexEntryFixture(t)
	legacy := &codexLegacyHookFixture{}
	constructions := 0
	legacyFactory = func() (HookServices, error) {
		constructions++
		return legacy, nil
	}
	t.Setenv("OPENSOCRATES_SELECTOR_MODE", "legacy")
	if codexEntryOutput(t, codexSizedSubmission(t, 32768), "user_prompt_submitted") != "" || legacy.calls != 1 || constructions != 1 {
		t.Fatal("bounded legacy submission changed")
	}
	if codexEntryOutput(t, codexSizedSubmission(t, 32769), "user_prompt_submitted") != "" || legacy.calls != 1 || constructions != 1 {
		t.Fatal("large discovery allowance leaked into legacy services")
	}
	t.Setenv("OPENSOCRATES_SELECTOR_MODE", "")
	for event, fields := range map[string]map[string]any{
		"SessionStart": {"source": "compact"}, "Stop": {},
		"PreToolUse": {"tool_name": "Bash"}, "PostToolUse": {"tool_name": "Bash"},
		"PreCompact": {"trigger": "manual"}, "PostCompact": {"trigger": "auto"},
		"SessionEnd": {"reason": "other"},
	} {
		fields["hook_event_name"], fields["extra"] = event, strings.Repeat("x", 32769)
		if codexEntryOutput(t, codexHookFixture(t, fields), nativeLanes[event]) != "" {
			t.Fatal("large submission allowance leaked into another event", event)
		}
	}
	fields := map[string]any{"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_response": ""}
	fields["tool_response"] = strings.Repeat("x", 2*1024*1024-len(codexHookFixture(t, fields)))
	if codexEntryOutput(t, codexHookFixture(t, fields), "tool_succeeded") == "" {
		t.Fatal("existing bounded Read callback rejected")
	}
	fields["tool_response"] = fields["tool_response"].(string) + "x"
	if codexEntryOutput(t, codexHookFixture(t, fields), "tool_succeeded") != "" {
		t.Fatal("oversized Read callback accepted")
	}
	for _, source := range []string{"startup", "resume", "clear"} {
		fields := map[string]any{"hook_event_name": "SessionStart", "source": source}
		if codexEntryOutput(t, codexHookFixture(t, fields), "session_started") != "" {
			t.Fatal("literal startup no-op changed")
		}
	}
}

func TestEntryGuidanceDefinesSubstantiveThinkingAndEvidenceBoundaries(t *testing.T) {
	if len(EntryGuidance) > 1600 {
		t.Fatal("entry guidance exceeds the upstream discovery cost guard")
	}
	for _, clause := range []string{
		"first needs substantive thought", "a fixed answer alone is not mechanical",
		"Reader guidance or no method may suffice", "user requests still require fit",
		"even when OpenSocrates is the subject", "full canonical read in the task locale",
		"not native grounding or application evidence", "Unverified application is a measurement limit",
	} {
		if !strings.Contains(EntryGuidance, clause) {
			t.Fatal("entry omitted a substantive-thinking or evidence boundary", clause)
		}
	}
}

func tenGuideFixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	references := []string{"skills/opensocrates/SKILL.md"}
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		references = append(references, "skills/opensocrates/references/decision/guide."+locale+".md")
	}
	for _, relative := range references {
		path := filepath.Join(root, filepath.FromSlash(relative))
		if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte("canonical installed reference"), 0600); err != nil {
			t.Fatal(err)
		}
	}
	return root
}

func TestClaudeNativeEntryRequiresEveryReleasedLocaleGuide(t *testing.T) {
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		t.Run(locale, func(t *testing.T) {
			root := tenGuideFixture(t)
			if err := os.Remove(filepath.Join(root, "skills", "opensocrates", "references", "decision", "guide."+locale+".md")); err != nil {
				t.Fatal(err)
			}
			for _, input := range []string{`{"hook_event_name":"SessionStart","source":"startup"}`, `{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL"}`} {
				var out bytes.Buffer
				if code := RunClaudeHookAtRoot(strings.NewReader(input), &out, root); code != 0 || out.Len() != 0 {
					t.Fatal("incomplete package must fail open without instructions")
				}
			}
		})
	}
}

func TestClaudeNativeEntryAdvertisesTenLocalesWithoutReadingPromptOrCreatingState(t *testing.T) {
	root, home := tenGuideFixture(t), t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)
	t.Setenv("LOCALAPPDATA", home)
	// Native discovery ignores preferences and language hints in host payloads.
	inputs := []string{
		`{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL english","transcript_path":"/PRIVATE_TRANSCRIPT","locale":"en"}`,
		`{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL 中文","transcript_path":"/PRIVATE_TRANSCRIPT","locale":"zh"}`,
		`{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL 日本語かな","transcript_path":"/PRIVATE_TRANSCRIPT","locale":"ja"}`,
		`{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL 한국어","transcript_path":"/PRIVATE_TRANSCRIPT","locale":"ko"}`,
		`{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL français","transcript_path":"/PRIVATE_TRANSCRIPT","locale":"fr"}`,
		`{"hook_event_name":"UserPromptSubmit","prompt":"PRIVATE_SENTINEL ภาษาไทย","transcript_path":"/PRIVATE_TRANSCRIPT","locale":"th"}`,
	}
	var previous string
	for _, input := range inputs {
		var out bytes.Buffer
		if code := RunClaudeHookAtRoot(strings.NewReader(input), &out, root); code != 0 || out.Len() == 0 {
			t.Fatal("complete installed package not advertised")
		}
		text := out.String()
		if strings.Contains(text, "PRIVATE_SENTINEL") || strings.Contains(text, "PRIVATE_TRANSCRIPT") {
			t.Fatal("native entry disclosed private host context")
		}
		for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
			if !strings.Contains(text, "guide."+locale+".md") {
				t.Fatal("native entry omitted installed guide", locale)
			}
		}
		if previous != "" && previous != text {
			t.Fatal("native discovery selected a locale from transient prompt or host hint")
		}
		previous = text
	}
	entries, err := os.ReadDir(home)
	if err != nil || len(entries) != 0 {
		t.Fatal("native entry initialized user settings or prompt storage")
	}
}

func TestClaudeNativeEntryRejectsLinkedAdditionalLocaleGuide(t *testing.T) {
	root := tenGuideFixture(t)
	path := filepath.Join(root, "skills", "opensocrates", "references", "decision", "guide.th.md")
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	outside := filepath.Join(t.TempDir(), "foreign.md")
	if err := os.WriteFile(outside, []byte("PRIVATE_FOREIGN_CONTEXT"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, path); err != nil {
		t.Skip("symbolic link unavailable on this test host")
	}
	var out bytes.Buffer
	if code := RunClaudeHookAtRoot(strings.NewReader(`{"hook_event_name":"SessionStart","source":"resume"}`), &out, root); code != 0 || out.Len() != 0 {
		t.Fatal("linked guide admitted")
	}
}
