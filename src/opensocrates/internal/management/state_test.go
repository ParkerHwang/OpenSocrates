package management

import (
	"bytes"
	"encoding/json"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"path/filepath"
	"reflect"
	"testing"
)

func TestLegacyUnknownStatePreserved(t *testing.T) {
	dir := t.TempDir()
	data := []byte(`{"schema":"opensocrates.desired-state/1.0.0","channel":"stable","installedHosts":["codex"],"activeVersion":"1.5.0","updatePolicy":{"intervalHours":24,"allowMajor":false},"autoUpdate":{"enabled":false,"hosts":[],"nextCheckAt":null},"future":{"large":9007199254740993,"unicode":"한글😀"}}`)
	if e := platform.AtomicWrite(filepath.Join(dir, "desired-state.json"), data, 0600); e != nil {
		t.Fatal(e)
	}
	state, raw, e := ReadLegacy(dir)
	if e != nil || state.ActiveVersion == nil || *state.ActiveVersion != "1.5.0" {
		t.Fatal(e)
	}
	if string(raw) != string(data) {
		t.Fatal("legacy precision/unknown bytes changed")
	}
	s := State{Schema: StateSchema, Installations: map[string]Installation{}, UpdateOwner: "native", LegacyDesiredState: raw}
	b, e := StateBytes(s)
	if e != nil {
		t.Fatal(e)
	}
	var decoded map[string]json.RawMessage
	if json.Unmarshal(b, &decoded) != nil {
		t.Fatal("new state invalid")
	}
	var legacy map[string]json.RawMessage
	if json.Unmarshal(decoded["legacy_desired_state"], &legacy) != nil || string(legacy["future"]) != `{"large":9007199254740993,"unicode":"한글😀"}` { // JSON indentation can change, number semantics must not.
		var future struct {
			Large json.Number `json:"large"`
		}
		if json.Unmarshal(legacy["future"], &future) != nil || future.Large.String() != "9007199254740993" {
			t.Fatal("legacy number precision changed")
		}
	}
}
func TestLegacyNullBooleanRefused(t *testing.T) {
	dir := t.TempDir()
	b := []byte(`{"schema":"opensocrates.desired-state/1.0.0","channel":"stable","installedHosts":[],"updatePolicy":{"intervalHours":24,"allowMajor":null},"autoUpdate":{"enabled":false,"hosts":[]}}`)
	if e := platform.AtomicWrite(filepath.Join(dir, "desired-state.json"), b, 0600); e != nil {
		t.Fatal(e)
	}
	if _, _, e := ReadLegacy(dir); e == nil {
		t.Fatal("null boolean accepted")
	}
}
func TestRetireLegacyUpdateOwnerPreservesOpaqueNumbers(t *testing.T) {
	raw := json.RawMessage(`{"schema":"opensocrates.desired-state/1.0.0","channel":"stable","installedHosts":["codex"],"activeVersion":"1.5.0","updatePolicy":{"intervalHours":24,"allowMajor":false,"future":1.0000000000000000001},"autoUpdate":{"enabled":true,"hosts":["codex"],"nextCheckAt":"2026-10-13T00:00:00Z","future":9007199254740993},"opaque":{"unicode":"한글😀","decimal":0.1000000000000000000001}}`)
	b, e := RetireLegacyUpdater(raw)
	if e != nil {
		t.Fatal(e)
	}
	var before, after map[string]json.RawMessage
	json.Unmarshal(raw, &before)
	json.Unmarshal(b, &after)
	for _, key := range []string{"updatePolicy", "opaque", "installedHosts", "activeVersion", "channel"} {
		var a, z interface{}
		da := json.NewDecoder(bytes.NewReader(before[key]))
		da.UseNumber()
		dz := json.NewDecoder(bytes.NewReader(after[key]))
		dz.UseNumber()
		da.Decode(&a)
		dz.Decode(&z)
		if !reflect.DeepEqual(a, z) {
			t.Fatalf("unrelated field changed: %s", key)
		}
	}
	var auto map[string]json.RawMessage
	json.Unmarshal(after["autoUpdate"], &auto)
	if string(auto["enabled"]) != "false" || string(auto["hosts"]) != "[]" || string(auto["future"]) != "9007199254740993" {
		t.Fatal("owner not retired or future precision lost")
	}
}

func TestReleasedLegacyStatePreservesLocaleAndUnrelatedMetadata(t *testing.T) {
	for _, tc := range []struct {
		version  string
		revision int
		locales  []string
	}{
		{"1.5.1", 4, []string{"zh", "ja"}},
		{"1.5.2", 5, []string{"fr", "de", "it", "es", "pt", "th"}},
	} {
		for _, locale := range tc.locales {
			t.Run(tc.version+"/"+locale, func(t *testing.T) {
				dir := filepath.Join(t.TempDir(), "private-state")
				if e := platform.Mkdir(dir); e != nil {
					t.Fatal(e)
				}
				raw := []byte(fmt.Sprintf(`{"schema":"opensocrates.desired-state/1.0.0","channel":"stable","installedHosts":["codex"],"activeVersion":"%s","contentRevision":%d,"updatePolicy":{"intervalHours":24,"allowMajor":false},"autoUpdate":{"enabled":false,"hosts":[],"nextCheckAt":null},"future":{"locale_preference":"%s","large":9007199254740993,"unicode":"中文 日本語 한글😀","npm":{"unrelated":"keep"},"integrations":{"claude":false}}}`, tc.version, tc.revision, locale))
				if e := platform.AtomicWrite(filepath.Join(dir, "desired-state.json"), raw, 0600); e != nil {
					t.Fatal(e)
				}
				state, preserved, e := ReadLegacy(dir)
				if e != nil || state.ActiveVersion == nil || *state.ActiveVersion != tc.version || !bytes.Equal(raw, preserved) {
					t.Fatalf("released %s state changed: %v", tc.version, e)
				}
				retired, e := RetireLegacyUpdater(preserved)
				if e != nil {
					t.Fatal(e)
				}
				var before, after map[string]json.RawMessage
				if json.Unmarshal(raw, &before) != nil || json.Unmarshal(retired, &after) != nil {
					t.Fatal("invalid state")
				}
				for _, key := range []string{"activeVersion", "contentRevision", "future", "installedHosts", "updatePolicy"} {
					if !bytes.Equal(before[key], after[key]) {
						// Marshaling may change formatting, but must preserve every value
						// and arbitrary-precision number in opaque legacy fields.
						var a, z any
						d1 := json.NewDecoder(bytes.NewReader(before[key]))
						d2 := json.NewDecoder(bytes.NewReader(after[key]))
						d1.UseNumber()
						d2.UseNumber()
						if d1.Decode(&a) != nil || d2.Decode(&z) != nil || !reflect.DeepEqual(a, z) {
							t.Fatalf("unrelated %s field changed: %s", tc.version, key)
						}
					}
				}
				persisted, e := StateBytes(State{Schema: StateSchema, Installations: map[string]Installation{}, UpdateOwner: "native", LegacyDesiredState: retired})
				if e != nil {
					t.Fatal(e)
				}
				var native map[string]json.RawMessage
				var opaque map[string]json.RawMessage
				if json.Unmarshal(persisted, &native) != nil || json.Unmarshal(native["legacy_desired_state"], &opaque) != nil {
					t.Fatal("native migration state invalid")
				}
				var future map[string]json.RawMessage
				if json.Unmarshal(opaque["future"], &future) != nil || string(future["locale_preference"]) != `"`+locale+`"` || string(future["large"]) != "9007199254740993" {
					t.Fatal("locale/opaque precision lost in native migration state")
				}
			})
		}
	}
}
