// Package persistence provides bounded, owner-protected state adapters.
package persistence

import (
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"strings"
)

func Root() string {
	home, e := os.UserHomeDir()
	if e != nil {
		return ""
	}
	switch runtime.GOOS {
	case "darwin":
		return filepath.Join(home, "Library", "Application Support", "OpenSocrates")
	case "windows":
		base := os.Getenv("LOCALAPPDATA")
		if base == "" {
			base = filepath.Join(home, "AppData", "Local")
		}
		return filepath.Join(base, "OpenSocrates")
	default:
		base := os.Getenv("XDG_DATA_HOME")
		if base == "" {
			base = filepath.Join(home, ".local", "share")
		}
		return filepath.Join(base, "opensocrates")
	}
}
func Ensure(root string) error {
	if root == "" || !filepath.IsAbs(root) {
		return contracts.ErrInvalid
	}
	if e := platform.Mkdir(root); e != nil {
		return e
	}
	for _, dir := range []string{"capabilities", "runtime", "runtime/turns", "records", "metrics", "quarantine", "diagnostics"} {
		if e := platform.Mkdir(filepath.Join(root, filepath.FromSlash(dir))); e != nil {
			return e
		}
	}
	return nil
}

type SettingsStore struct{ Root string }

func (s SettingsStore) Load() domain.UserSettings {
	data, e := platform.ReadFile(filepath.Join(s.Root, "settings.json"), 128*1024)
	if e != nil {
		return domain.DefaultSettings()
	}
	value, e := contracts.Decode(data)
	if e != nil {
		return domain.DefaultSettings()
	}
	settings, e := domain.ParseSettings(value)
	if e != nil {
		return domain.DefaultSettings()
	}
	return settings
}
func (s SettingsStore) Mutate(change func(domain.UserSettings) (domain.UserSettings, error)) (domain.UserSettings, error) {
	if e := Ensure(s.Root); e != nil {
		return domain.UserSettings{}, e
	}
	lock, e := platform.Lock(filepath.Join(s.Root, "settings.lock"))
	if e != nil {
		return domain.UserSettings{}, e
	}
	defer lock.Close()
	current := s.Load()
	path := filepath.Join(s.Root, "settings.json")
	// An unknown, newer, or malformed existing contract is never overwritten by
	// a write using the read fallback; preserve it for explicit recovery.
	if raw, e := platform.ReadFile(path, 128*1024); e == nil {
		v, e := contracts.Decode(raw)
		if e != nil {
			return current, e
		}
		if _, e = domain.ParseSettings(v); e != nil {
			return current, e
		}
	} else if !errors.Is(e, os.ErrNotExist) {
		return current, e
	}
	candidate, e := change(current)
	if e != nil {
		return current, e
	}
	if reflect.DeepEqual(candidate.Value, current.Value) {
		return current, nil
	}
	if candidate.Value["revision"] != current.NextRevision() {
		return current, contracts.ErrInvalid
	}
	if _, e = domain.ParseSettings(candidate.Value); e != nil {
		return current, e
	}
	raw, e := contracts.CanonicalJSON(candidate.Value)
	if e != nil {
		return current, e
	}
	if e = platform.AtomicWrite(path, raw, 0600); e != nil {
		return current, e
	}
	return candidate, nil
}
func SafeExport(destination string, payload []byte, overwrite bool) error {
	if destination == "" || len(payload) > 8*1024*1024 {
		return contracts.ErrInvalid
	}
	for _, part := range strings.FieldsFunc(destination, func(r rune) bool { return r == '/' || r == '\\' }) {
		if part == ".." || part == "." {
			return contracts.ErrInvalid
		}
	}
	if strings.HasPrefix(destination, "~/") {
		home, e := os.UserHomeDir()
		if e != nil {
			return e
		}
		destination = filepath.Join(home, destination[2:])
	}
	absolute, e := filepath.Abs(destination)
	if e != nil {
		return e
	}
	if e = platform.GuardOwned(absolute); e != nil {
		return e
	}
	if !overwrite {
		return platform.ExclusiveWrite(absolute, payload, 0600)
	}
	return platform.AtomicWrite(absolute, payload, 0600)
}
