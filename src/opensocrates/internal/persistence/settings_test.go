package persistence

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
	"testing"
)

func TestSettingsAtomicRevisionAndPreservation(t *testing.T) {
	root := t.TempDir()
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
	root := t.TempDir()
	foreign := filepath.Join(root, "foreign.json")
	if e := os.WriteFile(foreign, []byte("keep"), 0600); e != nil {
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
	if e := SafeExport(filepath.Join(root, "..", "escape"), []byte("no"), false); e == nil {
		t.Fatal("lexical traversal accepted")
	}
}
