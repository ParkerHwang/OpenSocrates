// Package application wires pure transitions to typed persistence ports.
package application

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
)

type SettingsRepository interface {
	Load() domain.UserSettings
	Mutate(func(domain.UserSettings) (domain.UserSettings, error)) (domain.UserSettings, error)
}

func RigorGet(store SettingsRepository) map[string]any {
	if store == nil {
		return unavailable("settings_store_unavailable")
	}
	return settingsProjection(store.Load())
}
func settingsProjection(s domain.UserSettings) map[string]any {
	return map[string]any{"status": "ok", "rigor": s.Rigor(), "revision": s.Value["revision"]}
}
func unavailable(code string) map[string]any {
	return map[string]any{"status": "unavailable", "error_code": code}
}
func RigorSet(store SettingsRepository, level string, once bool) map[string]any {
	if !contracts.Is(level, "quiet", "together", "strict") {
		return map[string]any{"status": "rejected", "error_code": "invalid_rigor"}
	}
	if store == nil {
		return unavailable("settings_store_unavailable")
	}
	if once {
		result := settingsProjection(store.Load())
		result["status"], result["scope"], result["rigor"] = "accepted", "next_task", level
		return result
	}
	s, e := store.Mutate(func(current domain.UserSettings) (domain.UserSettings, error) { return domain.SetRigor(current, level) })
	if e != nil {
		return unavailable("settings_write_unavailable")
	}
	result := settingsProjection(s)
	result["scope"] = "default"
	return result
}
func RigorReset(store SettingsRepository) map[string]any {
	if store == nil {
		return unavailable("settings_store_unavailable")
	}
	s, e := store.Mutate(func(current domain.UserSettings) (domain.UserSettings, error) {
		return domain.SetRigor(current, "together")
	})
	if e != nil {
		return unavailable("settings_write_unavailable")
	}
	if reset, e := store.Mutate(domain.ResetPreferences); e == nil {
		s = reset
	}
	result := settingsProjection(s)
	result["scope"] = "default"
	return result
}
