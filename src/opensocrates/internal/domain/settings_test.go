package domain

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"reflect"
	"testing"
)

func TestFeedbackReductionAndRecoveryPreserveMonotonicSequence(t *testing.T) {
	s := DefaultSettings()
	var e error
	for i := 0; i < 2; i++ {
		s, e = ApplyFeedback(s, "reframe", "dismissed", "2026-10-12")
		if e != nil {
			t.Fatal(e)
		}
	}
	pref := s.Value["intervention_preferences"].(map[string]any)["reframe"].(map[string]any)
	if pref["reduced_until"] != "2026-11-11" {
		t.Fatal(pref)
	}
	for i := 0; i < 3; i++ {
		s, e = ApplyFeedback(s, "reframe", "accepted", "2026-10-13")
		if e != nil {
			t.Fatal(e)
		}
	}
	pref = s.Value["intervention_preferences"].(map[string]any)["reframe"].(map[string]any)
	if pref["reduced_until"] != nil || len(pref["recent_feedback"].([]any)) != 0 {
		t.Fatal(pref)
	}
	sequence, _ := contracts.Int(pref["next_sequence"])
	if sequence != 6 {
		t.Fatal("sequence rewound", pref)
	}
	s, e = ResetPreferences(s)
	if e != nil {
		t.Fatal(e)
	}
	pref = s.Value["intervention_preferences"].(map[string]any)["reframe"].(map[string]any)
	sequence, _ = contracts.Int(pref["next_sequence"])
	if sequence != 6 {
		t.Fatal("reset rewound sequence")
	}
}
func TestLargeSettingsRevisionKeepsPrecision(t *testing.T) {
	s := DefaultSettings()
	s.Value["revision"] = json.Number("123456789012345678901234567890")
	parsed, e := ParseSettings(s.Value)
	if e != nil {
		t.Fatal(e)
	}
	updated, e := SetRigor(parsed, "strict")
	if e != nil || updated.Value["revision"] != json.Number("123456789012345678901234567891") {
		t.Fatal("revision precision lost", updated, e)
	}
}
func TestSettingsPresenceAndUnknownContracts(t *testing.T) {
	for _, mutate := range []func(map[string]any){func(m map[string]any) { delete(m, "locale_preference") }, func(m map[string]any) { m["foreign"] = true }, func(m map[string]any) { m["revision"] = true }, func(m map[string]any) { m["recording_mode"] = "local_public_artifacts" }, func(m map[string]any) { m["intervention_preferences"] = nil }} {
		s := DefaultSettings()
		mutate(s.Value)
		if _, e := ParseSettings(s.Value); e == nil {
			t.Fatal("invalid settings accepted", s)
		}
	}
}

func TestLocaleMutationsPreserveReleasedSettingsAndRevision(t *testing.T) {
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		s := DefaultSettings()
		s.Value["revision"] = json.Number("123456789012345678901234567890")
		s.Value["recording_mode"] = "local_public_artifacts"
		s.Value["onboarding_version_seen"] = "1.0.0"
		s.Value["record_retention_days"] = contracts.Number(365)
		s.Value["metrics_consent"] = "none"
		s.Value["locale_preference"] = locale
		if _, e := ParseSettings(s.Value); e != nil {
			t.Fatal(locale, e)
		}
		updated, e := SetRigor(s, "strict")
		if e != nil {
			t.Fatal(e)
		}
		expected := s.Clone()
		expected.Value["default_rigor"], expected.Value["revision"] = "strict", s.NextRevision()
		if !reflect.DeepEqual(updated.Value, expected.Value) {
			t.Fatal("rigor mutation lost released settings", locale)
		}
		unchanged, e := SetLocale(updated, &locale)
		if e != nil || !reflect.DeepEqual(unchanged.Value, updated.Value) {
			t.Fatal("locale no-op changed state", e)
		}
		reset, e := SetLocale(updated, nil)
		if e != nil || reset.LocalePreference() != nil || reset.Value["revision"] != updated.NextRevision() {
			t.Fatal("reset failed", e)
		}
		again, e := SetLocale(reset, nil)
		if e != nil || !reflect.DeepEqual(again.Value, reset.Value) {
			t.Fatal("reset no-op changed state", e)
		}
		bad := "follow"
		if _, e := SetLocale(updated, &bad); e == nil {
			t.Fatal("wire alias accepted")
		}
	}
}
