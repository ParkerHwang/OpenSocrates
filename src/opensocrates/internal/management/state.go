package management

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

const StateSchema = "opensocrates.native-state/1.0.0"
const MarkerName = ".opensocrates-managed.json"
const MarkerSchema = "opensocrates.managed-host/1.0.0"

type Installation struct {
	Host            string                        `json:"host"`
	Scope           string                        `json:"scope"`
	Root            string                        `json:"root"`
	Version         string                        `json:"version"`
	ContentRevision string                        `json:"content_revision"`
	Enabled         bool                          `json:"enabled"`
	Bundle          string                        `json:"bundle"`
	Integrity       string                        `json:"integrity"`
	Activation      string                        `json:"activation"`
	UpdateOwner     string                        `json:"update_owner,omitempty"`
	Targets         map[string]lifecycle.Snapshot `json:"targets"`
}
type State struct {
	Schema             string                  `json:"schema"`
	ManagerVersion     string                  `json:"manager_version"`
	UpdateOwner        string                  `json:"update_owner"`
	Installations      map[string]Installation `json:"installations"`
	LegacyDesiredState json.RawMessage         `json:"legacy_desired_state,omitempty"`
}

func ReadState(dir string) (State, error) {
	s := State{Schema: StateSchema, UpdateOwner: "native", Installations: map[string]Installation{}}
	p := filepath.Join(dir, "native-state.json")
	if _, e := os.Lstat(p); os.IsNotExist(e) {
		return s, nil
	}
	b, e := platform.ReadFile(p, 8<<20)
	if e != nil {
		return s, e
	}
	value, e := contracts.Decode(b)
	if e != nil {
		return State{}, diagnostics.New(diagnostics.Verification, "native-state")
	}
	obj, ok := value.(map[string]any)
	if !ok {
		return State{}, diagnostics.New(diagnostics.Verification, "native-state")
	}
	for k := range obj {
		switch k {
		case "schema", "manager_version", "update_owner", "installations", "legacy_desired_state":
		default:
			return State{}, diagnostics.New(diagnostics.ProtocolIncompatible, "native-state")
		}
	}
	if json.Unmarshal(b, &s) != nil || s.Schema != StateSchema || s.Installations == nil || (s.UpdateOwner != "native" && s.UpdateOwner != "npm") {
		return State{}, diagnostics.New(diagnostics.Verification, "native-state")
	}
	return s, nil
}
func StateBytes(s State) ([]byte, error) {
	b, e := json.MarshalIndent(s, "", "  ")
	if e != nil {
		return nil, diagnostics.New(diagnostics.Verification, "native-state")
	}
	return append(b, '\n'), nil
}

type LegacyDesired struct {
	Schema         string   `json:"schema"`
	Channel        string   `json:"channel"`
	InstalledHosts []string `json:"installedHosts"`
	ActiveVersion  *string  `json:"activeVersion"`
	UpdatePolicy   struct {
		IntervalHours int  `json:"intervalHours"`
		AllowMajor    bool `json:"allowMajor"`
	} `json:"updatePolicy"`
	AutoUpdate struct {
		Enabled     bool     `json:"enabled"`
		Hosts       []string `json:"hosts"`
		NextCheckAt *string  `json:"nextCheckAt"`
	} `json:"autoUpdate"`
}

// ReadLegacy preserves the exact source JSON, including future/unknown fields.
func ReadLegacy(dir string) (*LegacyDesired, json.RawMessage, error) {
	p := filepath.Join(dir, "desired-state.json")
	if _, e := os.Lstat(p); os.IsNotExist(e) {
		return nil, nil, nil
	}
	b, e := platform.ReadFile(p, 8<<20)
	if e != nil {
		return nil, nil, e
	}
	var raw map[string]json.RawMessage
	var s LegacyDesired
	if _, e := contracts.Decode(b); e != nil {
		return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-state")
	}
	if json.Unmarshal(b, &raw) != nil || json.Unmarshal(b, &s) != nil || s.Schema != "opensocrates.desired-state/1.0.0" || (s.Channel != "stable" && s.Channel != "next") || s.UpdatePolicy.IntervalHours < 1 || s.UpdatePolicy.IntervalHours > 168 {
		return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-state")
	}
	var policy, auto map[string]json.RawMessage
	if json.Unmarshal(raw["updatePolicy"], &policy) != nil || json.Unmarshal(raw["autoUpdate"], &auto) != nil || (string(policy["allowMajor"]) != "true" && string(policy["allowMajor"]) != "false") || (string(auto["enabled"]) != "true" && string(auto["enabled"]) != "false") {
		return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-state")
	}
	if s.InstalledHosts == nil {
		return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-state")
	}
	seen := map[string]bool{}
	for _, h := range s.InstalledHosts {
		if h != "codex" || seen[h] {
			return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-hosts")
		}
		seen[h] = true
	}
	if auto["hosts"] == nil && s.AutoUpdate.Enabled {
		s.AutoUpdate.Hosts = append([]string{}, s.InstalledHosts...)
	}
	autoSeen := map[string]bool{}
	for _, h := range s.AutoUpdate.Hosts {
		if !seen[h] || autoSeen[h] {
			return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-hosts")
		}
		autoSeen[h] = true
	}
	if s.AutoUpdate.Enabled != (len(autoSeen) > 0) {
		return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-policy")
	}
	return &s, json.RawMessage(b), nil
}

type Marker struct {
	Schema  string            `json:"schema"`
	Host    string            `json:"host"`
	Scope   string            `json:"scope"`
	Version string            `json:"version"`
	Hashes  map[string]string `json:"hashes"`
	Enabled bool              `json:"enabled"`
}

func readMarker(root, host, scope string) (Marker, error) {
	b, e := platform.ReadOwnedFile(filepath.Join(root, MarkerName), 8<<20)
	if e != nil {
		return Marker{}, e
	}
	var raw map[string]json.RawMessage
	var marker Marker
	if _, e := contracts.Decode(b); e != nil {
		return Marker{}, diagnostics.New(diagnostics.Verification, "ownership")
	}
	if json.Unmarshal(b, &marker) != nil || json.Unmarshal(b, &raw) != nil || len(raw) != 6 || marker.Schema != MarkerSchema || marker.Host != host || marker.Scope != scope || marker.Version == "" || len(marker.Hashes) == 0 || (string(raw["enabled"]) != "true" && string(raw["enabled"]) != "false") {
		return Marker{}, diagnostics.New(diagnostics.Verification, "ownership")
	}
	return marker, nil
}
func files(s lifecycle.Snapshot) map[string]string {
	result := map[string]string{}
	for _, r := range s.Entries {
		if !r.Directory {
			result[r.Path] = r.SHA256
		}
	}
	return result
}
func eqHashes(a, b map[string]string) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if b[k] != v {
			return false
		}
	}
	return true
}
func sortedKeys[V any](m map[string]V) []string {
	r := make([]string, 0, len(m))
	for k := range m {
		r = append(r, k)
	}
	sort.Strings(r)
	return r
}

// RetireLegacyUpdater edits only the old owner's scheduling fields. RawMessage
// keeps every unrelated unknown number (including fractions) and field intact.
func RetireLegacyUpdater(raw json.RawMessage) ([]byte, error) {
	var state, automatic map[string]json.RawMessage
	if json.Unmarshal(raw, &state) != nil || json.Unmarshal(state["autoUpdate"], &automatic) != nil {
		return nil, diagnostics.New(diagnostics.Verification, "legacy-state")
	}
	automatic["enabled"] = json.RawMessage("false")
	automatic["hosts"] = json.RawMessage("[]")
	automatic["nextCheckAt"] = json.RawMessage("null")
	b, e := json.Marshal(automatic)
	if e != nil {
		return nil, diagnostics.New(diagnostics.Verification, "legacy-state")
	}
	state["autoUpdate"] = b
	b, e = json.MarshalIndent(state, "", "  ")
	if e != nil {
		return nil, diagnostics.New(diagnostics.Verification, "legacy-state")
	}
	return append(b, '\n'), nil
}
