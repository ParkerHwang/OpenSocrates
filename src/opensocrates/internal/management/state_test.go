package management

import (
	"bytes"
	"encoding/json"
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
