package devtools

import (
	"encoding/json"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/compat"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"path/filepath"
	"strings"
	"testing"
)

// These tests never call a model, read account credentials, or launch the host.
func TestLegacyAcceptanceRequiresExplicitAbsolutePaths(t *testing.T) {
	abs := filepath.Join(t.TempDir(), "synthetic-only")
	for _, paths := range [][2]string{{"", abs}, {abs, ""}, {"relative-host", abs}, {abs, "relative-home"}} {
		report, err := legacySelectorAcceptance(paths[0], paths[1])
		if err == nil || report["outcome"] != "request_rejected" || report["error_category"] != "permission" {
			t.Fatal("relative or defaulted host/account input accepted")
		}
		if _, ok := report["pass"]; ok {
			t.Fatal("unavailable prerequisite mislabeled as failed probe")
		}
		encoded, err := json.Marshal(report)
		if err != nil || strings.Contains(string(encoded), abs) || strings.Contains(string(encoded), "relative-") {
			t.Fatal("private input recorded")
		}
	}
}

func TestLegacyAcceptanceValidatedResultsOnly(t *testing.T) {
	known := []string{"first-principles"}
	for _, tc := range []struct {
		name      string
		candidate *compat.Candidate
		pass      bool
		shape     bool
		outcome   string
	}{
		{"nil", nil, false, false, "invalid_output"},
		{"invalid-shape", &compat.Candidate{Intervene: true, SelectedReasoningSystems: []string{}, Instructions: "private instructions"}, false, false, "invalid_output"},
		{"unknown-id", &compat.Candidate{Intervene: true, SelectedReasoningSystems: []string{"unknown-method"}, Instructions: "private instructions"}, false, true, "invalid_output"},
		{"duplicate-id", &compat.Candidate{Intervene: true, SelectedReasoningSystems: []string{"first-principles", "first-principles"}, Instructions: "private instructions"}, false, false, "invalid_output"},
		{"selected", &compat.Candidate{Intervene: true, SelectedReasoningSystems: known, Instructions: "private instructions"}, true, true, "selected"},
		{"no-intervention", &compat.Candidate{SelectedReasoningSystems: []string{}}, true, true, "no_intervention"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			report, err := legacyAcceptanceResult(map[string]any{"error_category": "none"}, tc.candidate, known, nil)
			if err != nil || report["pass"] != tc.pass || report["result_shape_valid"] != tc.shape || report["catalog_ids_valid"] != tc.pass || report["outcome"] != tc.outcome {
				t.Fatal("candidate qualification mismatch")
			}
			encoded, err := json.Marshal(report)
			if err != nil || strings.Contains(string(encoded), "private instructions") || strings.Contains(string(encoded), "first-principles") || strings.Contains(string(encoded), "unknown-method") {
				t.Fatal("model content or selected ID recorded")
			}
		})
	}
}

func TestLegacyAcceptanceClosedErrors(t *testing.T) {
	for _, tc := range []struct {
		err      error
		category string
		outcome  string
		failed   bool
	}{
		{&compat.OutcomeError{Code: diagnostics.HostUnavailable, Outcome: "timeout"}, "host_unavailable", "timeout", false},
		{&compat.OutcomeError{Code: diagnostics.HostUnavailable, Outcome: "private outcome"}, "host_unavailable", "spawn_failed", false},
		{&compat.OutcomeError{Code: diagnostics.Code("private category"), Outcome: "private outcome"}, "host_unavailable", "spawn_failed", false},
		{diagnostics.New(diagnostics.ProtocolIncompatible, "private stage"), "protocol_incompatible", "request_rejected", false},
		{diagnostics.New(diagnostics.Permission, "private stage"), "permission", "request_rejected", false},
		{diagnostics.New(diagnostics.Verification, "private stage"), "verification", "invalid_output", true},
		{errors.New("private error wording"), "host_unavailable", "spawn_failed", false},
	} {
		report, err := legacyAcceptanceResult(map[string]any{}, nil, nil, tc.err)
		if report["error_category"] != tc.category || report["outcome"] != tc.outcome || (err == nil) != tc.failed {
			t.Fatal("closed failure classification mismatch")
		}
		if tc.failed {
			if report["pass"] != false {
				t.Fatal("invalid output not marked failed")
			}
		} else if _, ok := report["pass"]; ok {
			t.Fatal("unavailable transport mislabeled as failed")
		}
		encoded, encodeErr := json.Marshal(report)
		if encodeErr != nil || strings.Contains(string(encoded), "private") || err != nil && strings.Contains(err.Error(), "private") {
			t.Fatal("private error content exposed")
		}
	}
}

func TestLegacyAcceptanceCommitIdentifierClosed(t *testing.T) {
	if !legacyAcceptanceCommitValid(strings.Repeat("a", 40)) || !legacyAcceptanceCommitValid(strings.Repeat("f", 64)) {
		t.Fatal("full source commit rejected")
	}
	for _, value := range []string{"", "short", strings.Repeat("a", 39), strings.Repeat("A", 40), strings.Repeat("a", 40) + "\nprivate"} {
		if legacyAcceptanceCommitValid(value) {
			t.Fatal("non-object-id source metadata accepted")
		}
	}
}
