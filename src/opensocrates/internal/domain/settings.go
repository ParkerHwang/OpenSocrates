package domain

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"math/big"
	"reflect"
	"time"
)

// UserSettings preserves the released closed wire contract without converting
// optional nulls, empty arrays or arbitrarily precise integers into zero values.
type UserSettings struct{ Value map[string]any }

var InterventionClasses = []string{"reframe", "conflict", "weak_evidence", "missing_alternative", "completion_gap"}

func Preference() map[string]any {
	return map[string]any{"next_sequence": contracts.Number(1), "recent_feedback": []any{}, "reduced_since_sequence": nil, "reduced_until": nil}
}
func DefaultSettings() UserSettings {
	prefs := map[string]any{}
	for _, key := range InterventionClasses {
		prefs[key] = Preference()
	}
	return UserSettings{map[string]any{"schema": "opensocrates.user-settings/1.0.0", "revision": contracts.Number(1), "default_rigor": "together", "locale_preference": nil, "recording_mode": "off", "record_retention_days": contracts.Number(90), "record_size_limit_bytes": contracts.Number(100 * 1024 * 1024), "onboarding_version_seen": nil, "intervention_preferences": prefs, "metrics_consent": "none"}}
}
func ParseSettings(value any) (UserSettings, error) {
	if e := contracts.Validate("user-settings", value); e != nil {
		return UserSettings{}, e
	}
	m, ok := value.(map[string]any)
	if !ok {
		return UserSettings{}, contracts.ErrInvalid
	}
	return UserSettings{m}, nil
}
func (s UserSettings) Revision() int64 { n, _ := contracts.Int(s.Value["revision"]); return n }
func (s UserSettings) RevisionBig() *big.Int {
	n, ok := contracts.Integer(s.Value["revision"])
	if !ok {
		return new(big.Int)
	}
	return n
}
func (s UserSettings) NextRevision() json.Number {
	return json.Number(new(big.Int).Add(s.RevisionBig(), big.NewInt(1)).String())
}
func (s UserSettings) Rigor() string { r, _ := s.Value["default_rigor"].(string); return r }
func (s UserSettings) Clone() UserSettings {
	raw, _ := contracts.CanonicalJSON(s.Value)
	v, _ := contracts.Decode(raw)
	return UserSettings{v.(map[string]any)}
}
func (s UserSettings) Normalize() UserSettings {
	n := s.Clone()
	prefs, _ := n.Value["intervention_preferences"].(map[string]any)
	if prefs == nil {
		prefs = map[string]any{}
	}
	for _, key := range InterventionClasses {
		if _, ok := prefs[key]; !ok {
			prefs[key] = Preference()
		}
	}
	n.Value["intervention_preferences"] = prefs
	return n
}
func SetRigor(current UserSettings, level string) (UserSettings, error) {
	if !contracts.Is(level, "quiet", "together", "strict") {
		return current, contracts.ErrInvalid
	}
	candidate := current.Normalize()
	candidate.Value["default_rigor"] = level
	if reflect.DeepEqual(candidate.Value, current.Value) {
		return current, nil
	}
	candidate.Value["revision"] = current.NextRevision()
	return candidate, nil
}
func ResetPreferences(current UserSettings) (UserSettings, error) {
	candidate := current.Normalize()
	prefs := candidate.Value["intervention_preferences"].(map[string]any)
	for key, raw := range prefs {
		old := raw.(map[string]any)
		cleared := Preference()
		cleared["next_sequence"] = old["next_sequence"]
		prefs[key] = cleared
	}
	if reflect.DeepEqual(candidate.Value, current.Value) {
		return current, nil
	}
	candidate.Value["revision"] = current.NextRevision()
	return candidate, nil
}
func ExpireReducedPreferences(current UserSettings, day string) (UserSettings, error) {
	today, e := time.Parse("2006-01-02", day)
	if e != nil {
		return current, e
	}
	candidate := current.Normalize()
	prefs := candidate.Value["intervention_preferences"].(map[string]any)
	changed := false
	for key, raw := range prefs {
		old := raw.(map[string]any)
		until, ok := old["reduced_until"].(string)
		if !ok {
			continue
		}
		expiry, e := time.Parse("2006-01-02", until)
		if e != nil {
			return current, e
		}
		if !today.Before(expiry) {
			cleared := Preference()
			cleared["next_sequence"] = old["next_sequence"]
			prefs[key] = cleared
			changed = true
		}
	}
	if !changed {
		return current, nil
	}
	candidate.Value["revision"] = current.NextRevision()
	return candidate, nil
}
func ApplyFeedback(current UserSettings, class, outcome, day string) (UserSettings, error) {
	if !Has(InterventionClasses, class) || !contracts.Is(outcome, "accepted", "dismissed") {
		return current, contracts.ErrInvalid
	}
	date, e := time.Parse("2006-01-02", day)
	if e != nil {
		return current, e
	}
	candidate := current.Normalize()
	prefs := candidate.Value["intervention_preferences"].(map[string]any)
	pref := prefs[class].(map[string]any)
	next, ok := contracts.Int(pref["next_sequence"])
	if !ok {
		return current, contracts.ErrInvalid
	}
	ring, _ := pref["recent_feedback"].([]any)
	ring = append(ring, map[string]any{"sequence": contracts.Number(next), "day": day, "outcome": outcome})
	if len(ring) > 20 {
		ring = ring[len(ring)-20:]
	}
	pref["next_sequence"] = contracts.Number(next + 1)
	pref["recent_feedback"] = ring
	if outcome == "dismissed" {
		dismissed := 0
		for _, raw := range ring {
			if raw.(map[string]any)["outcome"] == "dismissed" {
				dismissed++
			}
		}
		if dismissed >= 2 {
			pref["reduced_since_sequence"] = contracts.Number(next)
			pref["reduced_until"] = date.AddDate(0, 0, 30).Format("2006-01-02")
		}
	} else if since, ok := contracts.Int(pref["reduced_since_sequence"]); ok {
		accepted := 0
		for _, raw := range ring {
			item := raw.(map[string]any)
			sequence, _ := contracts.Int(item["sequence"])
			if item["outcome"] == "accepted" && sequence > since {
				accepted++
			}
		}
		if accepted >= 3 {
			pref["recent_feedback"] = []any{}
			pref["reduced_since_sequence"], pref["reduced_until"] = nil, nil
		}
	}
	candidate.Value["revision"] = current.NextRevision()
	return candidate, nil
}

// LocalePreference preserves null as follow instead of inventing a locale alias.
func (s UserSettings) LocalePreference() *string {
	locale, ok := s.Value["locale_preference"].(string)
	if !ok {
		return nil
	}
	return &locale
}
func SetLocale(current UserSettings, locale *string) (UserSettings, error) {
	if locale != nil && !SupportedLocale(*locale) {
		return current, contracts.ErrInvalid
	}
	candidate := current.Normalize()
	candidate.Value["locale_preference"] = nil
	if locale != nil {
		candidate.Value["locale_preference"] = *locale
	}
	if reflect.DeepEqual(candidate.Value, current.Value) {
		return current, nil
	}
	candidate.Value["revision"] = current.NextRevision()
	return candidate, nil
}
