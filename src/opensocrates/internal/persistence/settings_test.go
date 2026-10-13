package persistence

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func privateSettingsTestRoot(t *testing.T) string {
	t.Helper()
	// On Windows an elevated token's temporary directory can be owned by the
	// Administrators group. Create a new explicitly owned state directory;
	// existing foreign ownership must never be repaired by these fixtures.
	root := filepath.Join(t.TempDir(), "private-settings")
	if err := platform.Mkdir(root); err != nil {
		t.Fatal(err)
	}
	return root
}

func TestSettingsAtomicRevisionAndPreservation(t *testing.T) {
	root := privateSettingsTestRoot(t)
	store := SettingsStore{Root: root}
	first := store.Load()
	if first.Rigor() != "together" || first.Revision() != 1 {
		t.Fatal(first)
	}
	updated, e := store.Mutate(func(s domain.UserSettings) (domain.UserSettings, error) { return domain.SetRigor(s, "strict") })
	if e != nil || updated.Revision() != 2 {
		t.Fatal(updated, e)
	}
	again, e := store.Mutate(func(s domain.UserSettings) (domain.UserSettings, error) { return domain.SetRigor(s, "strict") })
	if e != nil || again.Revision() != 2 {
		t.Fatal("no-op advanced revision", again, e)
	}
	raw, e := platform.ReadFile(filepath.Join(root, "settings.json"), 128*1024)
	if e != nil {
		t.Fatal(e)
	}
	expected, e := contracts.CanonicalJSON(updated.Value)
	if e != nil || string(raw) != string(expected) {
		t.Fatal("state is not canonical")
	}
	v, _ := contracts.Decode(raw)
	v.(map[string]any)["schema"] = "opensocrates.user-settings/2.0.0"
	future, _ := contracts.CanonicalJSON(v)
	if e = platform.AtomicWrite(filepath.Join(root, "settings.json"), future, 0600); e != nil {
		t.Fatal(e)
	}
	if _, e = store.Mutate(func(s domain.UserSettings) (domain.UserSettings, error) { return domain.SetRigor(s, "quiet") }); e == nil {
		t.Fatal("overwrote future contract")
	}
	after, e := platform.ReadFile(filepath.Join(root, "settings.json"), 128*1024)
	if e != nil || string(after) != string(future) {
		t.Fatal("future state changed")
	}
}
func TestSettingsRefuseLinkedStateAndExport(t *testing.T) {
	root := privateSettingsTestRoot(t)
	foreign := filepath.Join(root, "foreign.json")
	if e := platform.ExclusiveWrite(foreign, []byte("keep"), 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.Symlink(foreign, filepath.Join(root, "settings.json")); e != nil {
		t.Skip("symlink unavailable")
	}
	if _, e := (SettingsStore{Root: root}).Mutate(func(s domain.UserSettings) (domain.UserSettings, error) { return domain.SetRigor(s, "strict") }); e == nil {
		t.Fatal("linked settings mutated")
	}
	destination := filepath.Join(root, "export.json")
	if e := SafeExport(destination, []byte("first"), false); e != nil {
		t.Fatal(e)
	}
	if e := SafeExport(destination, []byte("second"), false); e == nil {
		t.Fatal("overwrote existing export")
	}
	bytes, e := os.ReadFile(destination)
	if e != nil || string(bytes) != "first" {
		t.Fatal("export changed")
	}
	// Join cleans dot segments before the API receives them. Keep the original
	// spelling here to exercise SafeExport's lexical traversal boundary.
	traversal := root + string(os.PathSeparator) + ".." + string(os.PathSeparator) + "escape"
	if e := SafeExport(traversal, []byte("no"), false); e == nil {
		t.Fatal("lexical traversal accepted")
	}
}

func TestV152LocaleSettingsRoundTripAndUnrelatedRigorWrite(t *testing.T) {
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		t.Run(locale, func(t *testing.T) {
			root := privateSettingsTestRoot(t)
			original := domain.DefaultSettings()
			original.Value["locale_preference"] = locale
			original.Value["revision"] = contracts.Number(42)
			original.Value["recording_mode"] = "local_public_artifacts"
			original.Value["onboarding_version_seen"] = "1.0.0"
			original.Value["record_retention_days"] = contracts.Number(730)
			original.Value["record_size_limit_bytes"] = contracts.Number(250 * 1024 * 1024)
			original.Value["metrics_consent"] = "none"
			raw, e := contracts.CanonicalJSON(original.Value)
			if e != nil {
				t.Fatal(e)
			}
			path := filepath.Join(root, "settings.json")
			if e := platform.AtomicWrite(path, raw, 0600); e != nil {
				t.Fatal(e)
			}
			store := SettingsStore{Root: root}
			if got := store.Load(); !reflect.DeepEqual(got.Value, original.Value) {
				t.Fatal("released settings became fallback")
			}
			updated, e := store.Mutate(func(s domain.UserSettings) (domain.UserSettings, error) { return domain.SetRigor(s, "strict") })
			if e != nil {
				t.Fatal(e)
			}
			expected := original.Clone()
			expected.Value["revision"], expected.Value["default_rigor"] = contracts.Number(43), "strict"
			if !reflect.DeepEqual(updated.Value, expected.Value) {
				t.Fatal("unrelated settings changed")
			}
			before, e := platform.ReadFile(path, 128*1024)
			if e != nil {
				t.Fatal(e)
			}
			if _, e := store.Mutate(func(s domain.UserSettings) (domain.UserSettings, error) { return domain.SetLocale(s, &locale) }); e != nil {
				t.Fatal(e)
			}
			after, e := platform.ReadFile(path, 128*1024)
			if e != nil || string(before) != string(after) {
				t.Fatal("locale no-op rewrote settings")
			}
			if _, e := store.Mutate(func(s domain.UserSettings) (domain.UserSettings, error) { return domain.SetLocale(s, nil) }); e != nil {
				t.Fatal(e)
			}
			if got := store.Load(); got.LocalePreference() != nil || got.Revision() != 44 {
				t.Fatal("reset did not persist null")
			}
		})
	}
}
