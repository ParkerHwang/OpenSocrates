package application

import (
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"strings"
	"testing"
)

type localeSettingsRepository struct {
	settings  domain.UserSettings
	fail      bool
	mutations int
}

func (r *localeSettingsRepository) Load() domain.UserSettings { return r.settings }
func (r *localeSettingsRepository) Mutate(change func(domain.UserSettings) (domain.UserSettings, error)) (domain.UserSettings, error) {
	r.mutations++
	if r.fail {
		return r.settings, errors.New("private settings detail")
	}
	s, e := change(r.settings)
	if e == nil {
		r.settings = s
	}
	return s, e
}
func TestLocaleCommandsAreClosedAndPreserveNoops(t *testing.T) {
	r := &localeSettingsRepository{settings: domain.DefaultSettings()}
	if got := LocaleGet(r); got["locale"] != "follow" {
		t.Fatal(got)
	}
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th", "follow"} {
		got := LocaleSet(r, locale)
		if got["status"] != "ok" || got["locale"] != locale {
			t.Fatal(got)
		}
		revision := r.settings.Value["revision"]
		if got := LocaleSet(r, locale); got["revision"] != revision {
			t.Fatal("no-op advanced revision")
		}
	}
	if got := LocaleReset(r); got["locale"] != "follow" {
		t.Fatal(got)
	}
	mutations := r.mutations
	for _, locale := range []string{"", "zh-CN", "jp", "JA", "fr-FR", "pt-BR", "th-TH", "ru"} {
		if got := LocaleSet(r, locale); got["error_code"] != "invalid_locale" {
			t.Fatal(got)
		}
	}
	if r.mutations != mutations {
		t.Fatal("invalid locale reached persistence")
	}
	if got := LocaleGet(nil); got["error_code"] != "settings_store_unavailable" {
		t.Fatal(got)
	}
	r.fail = true
	if got := LocaleSet(r, "zh"); got["error_code"] != "settings_write_unavailable" || len(got) != 2 {
		t.Fatal(got)
	}
}

func TestControlPublicEventsPreserveAllReleasedLocales(t *testing.T) {
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		a := ControlApplication{Locale: locale}
		state := map[string]any{"task_id": domain.NewTaskID(), "host": "codex_cli"}
		event := a.event(state, ControlRequest{}, 1, "task_cancelled", map[string]any{"reason": "user_cancelled"})
		if err := domain.ValidateRecord(event); event["locale"] != locale || err != nil {
			t.Fatal("public event locale rejected", locale, err, event)
		}
		metric, e := domain.BuildLocalMetric("card_rendered", "codex_cli", locale, domain.Together, domain.MetricAttributes{}, "2026-10-12", "1.6.0", nil, false, nil)
		if e != nil || metric != nil {
			t.Fatal("locale enabled recording")
		}
	}
	a := ControlApplication{Locale: "invalid"}
	event := a.event(map[string]any{"task_id": domain.NewTaskID(), "host": "codex_cli"}, ControlRequest{}, 1, "task_cancelled", map[string]any{"reason": "user_cancelled"})
	if event["locale"] != "en" {
		t.Fatal("unknown locale fallback changed")
	}
	if strings.Contains(event["locale"].(string), "invalid") {
		t.Fatal("invalid locale persisted")
	}
}
