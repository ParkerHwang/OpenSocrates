package management

import (
	"encoding/json"
	"path/filepath"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

type ManagerReplacement struct {
	Schema string             `json:"schema"`
	Bundle string             `json:"bundle"`
	Source string             `json:"source"`
	Before lifecycle.Snapshot `json:"before"`
	After  lifecycle.Snapshot `json:"after"`
}

func ReadPendingManager(dir string) (ManagerReplacement, error) {
	b, e := platform.ReadFile(filepath.Join(dir, "manager-pending.json"), 8<<20)
	if e != nil {
		return ManagerReplacement{}, e
	}
	var p ManagerReplacement
	value, e := contracts.Decode(b)
	if e != nil {
		return p, diagnostics.New(diagnostics.Verification, "manager-pending")
	}
	if _, e := contracts.Object(value, "schema", "bundle", "source", "before", "after"); e != nil {
		return p, diagnostics.New(diagnostics.Verification, "manager-pending")
	}
	if json.Unmarshal(b, &p) != nil || p.Schema != "opensocrates.manager-replacement/1.0.0" || (p.Bundle == "" || p.Bundle == "." || p.Bundle == "..") || strings.ContainsAny(p.Bundle, "/\\:") || p.Source != "bin/opensocrates.exe" || !p.Before.Exists || !p.After.Exists {
		return p, diagnostics.New(diagnostics.Verification, "manager-pending")
	}
	return p, nil
}
