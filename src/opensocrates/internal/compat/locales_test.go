package compat

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

func localePointer(value string) *string { return &value }

func TestReleasedSelectorLocaleScriptPolicy(t *testing.T) {
	for _, test := range []struct{ prompt, locale string }{
		{"English", "en"}, {"한국어", "ko"}, {"中文", "zh"}, {"漢字", "zh"},
		{"日本語かな", "ja"}, {"カタカナabc한국語", "ja"}, {"ｶ", "ja"},
		{"가a", "en"}, {"中a", "en"}, {"가中", "en"}, {"가123456789", "ko"},
		{"中123456789", "zh"}, {"123456789", "en"}, {"Ж", "en"},
		{"\U00020000", "zh"}, {"\u3041", "ja"}, {"\u3096", "ja"},
		{"\u30a1", "ja"}, {"\u30fa", "ja"}, {"\uff66", "ja"}, {"\uff9d", "ja"},
	} {
		if actual := Locale(test.prompt); actual != test.locale {
			t.Fatalf("selector locale: want %s, got %s", test.locale, actual)
		}
	}
}

type countingLocaleSelector struct {
	calls     int
	candidate *Candidate
}

func (s *countingLocaleSelector) Select(context.Context, Request) (*Candidate, error) {
	s.calls++
	return s.candidate, nil
}
func localeApplication(t *testing.T) (Application, *countingLocaleSelector) {
	t.Helper()
	store, bundle, _ := artifactFixture(t)
	selector := &countingLocaleSelector{candidate: &Candidate{Intervene: true, SelectedReasoningSystems: []string{bundle.IDs[0]}, Instructions: "PRIVATE_MODEL_MARKER"}}
	return Application{Selector: selector, Bundle: bundle, Artifacts: store}, selector
}
func TestLegacyRequestLocalePrecedenceAndInvalidFailOpen(t *testing.T) {
	for i, test := range []struct {
		explicit, preference *string
		prompt, want         string
	}{
		{nil, nil, "中文", "zh"}, {nil, localePointer("ja"), "English", "ja"},
		{localePointer("ko"), localePointer("zh"), "English", "ko"},
		{localePointer("en"), localePointer("invalid"), "한국어", "en"},
		{localePointer(""), localePointer("ja"), "中文", ""},
		{localePointer("zh-CN"), nil, "English", ""}, {nil, localePointer("follow"), "English", ""},
	} {
		app, selector := localeApplication(t)
		outcomes := []string{}
		app.OnOutcome = func(value string) { outcomes = append(outcomes, value) }
		request := Request{Prompt: test.prompt, TrustedExplicitLocale: test.explicit, StoredPreference: test.preference}
		session := fmt.Sprintf("locale-session-%d", i)
		decision := app.Select(context.Background(), request, session, "turn-locale")
		if test.want == "" {
			if decision != nil || selector.calls != 0 || len(outcomes) != 1 || outcomes[0] != "request_rejected" {
				t.Fatal("invalid trusted locale reached selector or failed closed incorrectly")
			}
			if app.Artifacts.Latest(session) != nil {
				t.Fatal("invalid request persisted an artifact")
			}
			continue
		}
		artifact := app.Artifacts.Latest(session)
		if decision == nil || selector.calls != 1 || artifact == nil || artifact.Locale != test.want {
			t.Fatal("released trusted preference precedence changed")
		}
		raw, err := os.ReadFile(artifact.Path)
		if err != nil || strings.Contains(string(raw), "PRIVATE_MODEL_MARKER") || strings.Contains(decision.Instructions, "PRIVATE_MODEL_MARKER") {
			t.Fatal("untrusted model instructions retained")
		}
	}
}

func TestFourLocaleArtifactsRequireCompleteReadAndRepair(t *testing.T) {
	labels := map[string][]string{
		"en": {"Questions to settle before you act:", "Grounding gate:", "a complete read receipt", "the final grounding audit line"},
		"ko": {"행동하기 전에 스스로 정리할 질문:", "접지(grounding) 게이트:", "전체 읽기 영수증", "최종 답변의 접지 감사 줄"},
		"zh": {"行动前须自行理清的问题：", "依据读取门槛：", "所选思考体系文件的完整读取凭证", "最终答复的依据确认行"},
		"ja": {"行動前に自分で整理する問い：", "根拠資料の読み取り条件：", "選択された思考体系ファイルの完全な読み取り記録", "最終回答の根拠確認行"},
	}
	for _, locale := range []string{"en", "ko", "zh", "ja"} {
		t.Run(locale, func(t *testing.T) {
			store, bundle, _ := artifactFixture(t)
			artifact, err := store.Create("locale-session", "locale-turn", []string{bundle.IDs[0]}, locale, bundle)
			if err != nil {
				t.Fatal(err)
			}
			latest := store.Latest("locale-session")
			if latest == nil || latest.Locale != locale {
				t.Fatal("four-language metadata not recovered")
			}
			reference, err := artifact.ReferenceMessage()
			if err != nil || !strings.Contains(reference, labels[locale][0]) || !strings.Contains(reference, labels[locale][1]) || !strings.Contains(reference, AttributionFooter) {
				t.Fatal("translated reference delivery incomplete")
			}
			raw, err := os.ReadFile(artifact.Path)
			body, bodyErr := bundle.Assemble(artifact.IDs, locale)
			if err != nil || bodyErr != nil || !strings.Contains(string(raw), body) || len(artifact.Questions) != 3 {
				t.Fatal("canonical localized procedure/questions missing")
			}
			partial := int64(1)
			cb := ReadCallback{Session: "locale-session", Turn: "locale-turn", FilePath: artifact.Path, ToolUseID: "read-localized", Limit: &partial, EndMarkerSeen: true}
			if store.RecordCompleteRead(cb) {
				t.Fatal("partial read accepted as complete")
			}
			repair := artifact.GroundingRepairMessage(true, true)
			if !strings.Contains(repair, labels[locale][2]) || !strings.Contains(repair, labels[locale][3]) || !strings.HasSuffix(repair, AttributionFooter) {
				t.Fatal("localized repair missing exact read/footer requirements")
			}
			cb.Limit = nil
			if !store.RecordCompleteRead(cb) || !store.HasCompleteReadReceipt(artifact) {
				t.Fatal("localized complete read receipt rejected")
			}
			hook := &HookServices{Application: Application{Bundle: bundle, Artifacts: store}}
			stop, _ := contracts.CanonicalCompact(map[string]any{"hook_event_name": "Stop", "session_id": "locale-session", "turn_id": "locale-turn", "last_assistant_message": "answer\n" + AttributionFooter})
			result, err := hook.HandleLegacy(stop, "Stop")
			if err != nil || result != nil || store.Latest("locale-session") != nil {
				t.Fatal("successful localized grounding did not retire artifacts")
			}
		})
	}
}

func TestLegacyWholeSelectionEnglishFallback(t *testing.T) {
	_, bundle, _ := artifactFixture(t)
	for _, locale := range []string{"ko", "zh", "ja"} {
		copied := *bundle
		copied.Projections = map[string]content.Injectable{}
		for key, value := range bundle.Projections {
			copied.Projections[key] = value
		}
		ids := []string{bundle.IDs[0], bundle.IDs[1]}
		delete(copied.Projections, ids[1]+":"+locale)
		artifact, body, err := assembledArtifact(&copied, ids, locale)
		expected, expectedErr := bundle.Assemble(ids, "en")
		if err != nil || expectedErr != nil || artifact.Locale != "en" || body != expected {
			t.Fatal("partial locale projection did not fallback for whole selection")
		}
		for i, id := range ids {
			if artifact.Names[i] != bundle.Projections[id+":en"].Name {
				t.Fatal("fallback mixed localized names")
			}
		}
		delete(copied.Projections, ids[1]+":en")
		if _, _, err := assembledArtifact(&copied, ids, locale); err == nil {
			t.Fatal("incomplete English fallback accepted")
		}
	}
	if _, _, err := assembledArtifact(bundle, []string{bundle.IDs[0]}, "zh-CN"); err == nil {
		t.Fatal("locale alias accepted")
	}
}

func TestLegacyHookReadsStoredLocaleWithoutRetainingPromptOrChangingSettings(t *testing.T) {
	app, _ := localeApplication(t)
	// A POSIX mode on an ordinary temporary file does not establish a protected
	// Windows DACL. Use the same owned state creation boundary as production.
	root := filepath.Join(privateDirectory(t), "private-settings")
	if err := platform.Mkdir(root); err != nil {
		t.Fatal(err)
	}
	settings := domain.DefaultSettings()
	settings.Value["locale_preference"] = "ja"
	raw, err := contracts.CanonicalCompact(settings.Value)
	if err != nil {
		t.Fatal(err)
	}
	settingsPath := filepath.Join(root, "settings.json")
	if err := platform.AtomicWrite(settingsPath, raw, 0600); err != nil {
		t.Fatal(err)
	}
	hook := &HookServices{Application: app, SettingsRoot: root}
	prompt := "PRIVATE_TRANSIENT_PROMPT_123456789"
	payload, _ := contracts.CanonicalCompact(map[string]any{"hook_event_name": "UserPromptSubmit", "session_id": "hook-locale-session", "turn_id": "hook-locale-turn", "prompt": prompt, "locale": "zh"})
	result, err := hook.HandleLegacy(payload, "UserPromptSubmit")
	artifact := app.Artifacts.Latest("hook-locale-session")
	if err != nil || result == nil || artifact == nil || artifact.Locale != "ja" {
		t.Fatal("legacy hook ignored stored locale or trusted payload locale")
	}
	stored, _ := os.ReadFile(settingsPath)
	artifactBytes, _ := os.ReadFile(artifact.Path)
	if string(stored) != string(raw) || strings.Contains(string(artifactBytes), prompt) || strings.Contains(fmt.Sprint(result), prompt) {
		t.Fatal("hook retained prompt or changed preference settings")
	}
	hook.TrustedExplicitLocale = localePointer("ko")
	if _, err := hook.HandleLegacy(payload, "UserPromptSubmit"); err != nil {
		t.Fatal(err)
	}
	if artifact := app.Artifacts.Latest("hook-locale-session"); artifact == nil || artifact.Locale != "ko" {
		t.Fatal("trusted explicit hook preference did not override stored locale")
	}
	request := Request{Prompt: prompt, TrustedExplicitLocale: localePointer("SECRET_EXPLICIT_VALUE"), StoredPreference: localePointer("SECRET_STORED_VALUE")}
	for _, output := range []string{fmt.Sprint(request), fmt.Sprintf("%+v", request)} {
		if strings.Contains(output, prompt) || strings.Contains(output, "SECRET_") {
			t.Fatal("transient request diagnostics exposed locale metadata or prompt")
		}
	}
}

func TestLegacyLocaleRequestFailsOpenOnUnsupportedSelectorPlatform(t *testing.T) {
	if contextAvailable() {
		t.Skip("unsupported legacy selector boundary is exercised on non-POSIX hosts")
	}
	app, _ := localeApplication(t)
	root := filepath.Join(privateDirectory(t), "private-settings")
	if err := platform.Mkdir(root); err != nil {
		t.Fatal(err)
	}
	settings := domain.DefaultSettings()
	settings.Value["locale_preference"] = "ja"
	raw, err := contracts.CanonicalCompact(settings.Value)
	if err != nil {
		t.Fatal(err)
	}
	settingsPath := filepath.Join(root, "settings.json")
	if err := platform.AtomicWrite(settingsPath, raw, 0600); err != nil {
		t.Fatal(err)
	}
	// No executable or auth home exists. The unsupported-platform guard must
	// reject before either is inspected and before any credential copying.
	absentHome := filepath.Join(root, "absent-codex-home")
	selector := &Selector{Binary: filepath.Join(root, "absent-codex"), CodexHome: absentHome}
	request := Request{Prompt: "PRIVATE_UNSUPPORTED_PROMPT", Catalog: app.Bundle.SelectionCatalog, StoredPreference: localePointer("ja"), Deadline: 3 * time.Second, ReasoningEffort: "medium"}
	candidate, err := selector.Select(context.Background(), request)
	outcome, ok := err.(*OutcomeError)
	if candidate != nil || !ok || outcome.Outcome != "request_rejected" {
		t.Fatal("unsupported platform reached selector process/auth work")
	}
	app.Selector = selector
	hook := &HookServices{Application: app, SettingsRoot: root}
	payload, _ := contracts.CanonicalCompact(map[string]any{"hook_event_name": "UserPromptSubmit", "session_id": "unsupported-locale-session", "turn_id": "unsupported-locale-turn", "prompt": request.Prompt})
	result, err := hook.HandleLegacy(payload, "UserPromptSubmit")
	if err != nil || result != nil || app.Artifacts.Latest("unsupported-locale-session") != nil {
		t.Fatal("unsupported selector hook failed to continue ordinary work without an artifact")
	}
	stored, err := platform.ReadFile(settingsPath, 128<<10)
	if err != nil || string(stored) != string(raw) {
		t.Fatal("unsupported selector changed stored locale settings")
	}
	if _, err := os.Stat(absentHome); !os.IsNotExist(err) {
		t.Fatal("unsupported selector created an auth home")
	}
}
