package runtimecli

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

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
