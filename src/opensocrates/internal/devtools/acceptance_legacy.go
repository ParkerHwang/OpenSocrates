package devtools

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/compat"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// This fixed fixture contains no caller prompt or workspace content. Qualification
// deliberately invokes the production legacy transport without installing hooks,
// modifying model defaults, or initiating an authentication flow.
const legacyAcceptancePrompt = "A fictional team must decide between repairing its existing scheduling tool and replacing it. The team has limited time, uncertain maintenance costs, and no measured reliability data. Select any useful reasoning methods from the canonical catalog for this synthetic decision."

func legacySelectorAcceptance(binary, codexHome string) (map[string]any, error) {
	report := map[string]any{
		"target":                     nativeAcceptanceTarget(),
		"runtime_goos":               runtime.GOOS,
		"runtime_goarch":             runtime.GOARCH,
		"evidence_scope":             "authenticated_legacy_synthetic_probe",
		"live_host_delivery_claimed": false,
		"answer_quality_claimed":     false,
		"user_installation_modified": false,
		"production_signing_claimed": false,
		"transcript_access_enabled":  false,
		"result_shape_valid":         false,
		"catalog_ids_valid":          false,
		"elapsed_ms":                 int64(0),
		"error_category":             "none",
		"outcome":                    "not_run",
		"required_external_evidence": []string{"real_host_trust_and_activation", "answer_quality", "production_signing_and_timestamping"},
	}
	if !filepath.IsAbs(binary) || !filepath.IsAbs(codexHome) {
		return report, legacyAcceptanceUnavailable(report, diagnostics.Permission, "request_rejected")
	}
	if nativeAcceptanceTarget() == "unsupported" || runtime.GOOS == "windows" {
		return report, legacyAcceptanceUnavailable(report, diagnostics.Unsupported, "request_rejected")
	}
	bundle, err := content.Load()
	if err != nil {
		return report, legacyAcceptanceUnavailable(report, diagnostics.Verification, "catalog_unavailable")
	}
	// The receipt identifies the checkout supplying this developer command. Only
	// a full hexadecimal object ID is emitted; Git output and errors stay private.
	commit, err := gitOutput(".", "rev-parse", "HEAD")
	commit = strings.TrimSpace(commit)
	if err != nil || !legacyAcceptanceCommitValid(commit) {
		return report, legacyAcceptanceUnavailable(report, diagnostics.Verification, "source_unavailable")
	}
	report["source_git_commit"] = commit
	selector := &compat.Selector{Binary: binary, CodexHome: codexHome}
	defer selector.Close()
	started := time.Now()
	candidate, err := selector.Select(context.Background(), compat.Request{
		Prompt: legacyAcceptancePrompt, Catalog: bundle.SelectionCatalog,
		Context:  compat.Handles{TranscriptAccessEnabled: false},
		Deadline: 30 * time.Second, ReasoningEffort: "medium",
	})
	report["elapsed_ms"] = time.Since(started).Milliseconds()
	return legacyAcceptanceResult(report, candidate, bundle.IDs, err)
}

func legacyAcceptanceCommitValid(commit string) bool {
	if len(commit) != 40 && len(commit) != 64 {
		return false
	}
	for _, c := range commit {
		if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f') {
			return false
		}
	}
	return true
}

func legacyAcceptanceUnavailable(report map[string]any, code diagnostics.Code, outcome string) error {
	report["error_category"] = string(code)
	report["outcome"] = outcome
	// Absence of pass:false preserves the acceptance runner's unavailable state.
	return diagnostics.New(code, "legacy_acceptance")
}

// Reduce the result to closed codes and booleans. No selected IDs, model-authored
// instructions, private error wording, account fields, or credential digests are
// included in the receipt.
func legacyAcceptanceResult(report map[string]any, candidate *compat.Candidate, knownIDs []string, err error) (map[string]any, error) {
	if err != nil {
		code := diagnostics.HostUnavailable
		outcome := "spawn_failed"
		var legacy *compat.OutcomeError
		var category *diagnostics.Error
		if errors.As(err, &legacy) {
			code = legacy.Code
			switch legacy.Outcome {
			case "request_rejected", "selector_closed", "executable_missing", "timeout":
				outcome = legacy.Outcome
			}
		} else if errors.As(err, &category) {
			code = category.Code
		}
		switch code {
		case diagnostics.Verification:
			report["pass"] = false
			report["error_category"] = string(code)
			report["outcome"] = "invalid_output"
			return report, nil
		case diagnostics.ProtocolIncompatible, diagnostics.Unsupported, diagnostics.Permission:
			outcome = "request_rejected"
		case diagnostics.HostUnavailable, diagnostics.Network:
		default:
			code = diagnostics.HostUnavailable
		}
		return report, legacyAcceptanceUnavailable(report, code, outcome)
	}
	shapeValid := false
	if candidate != nil {
		encoded, encodeErr := json.Marshal(candidate)
		if encodeErr == nil {
			_, decodeErr := compat.DecodeCandidate(encoded)
			shapeValid = decodeErr == nil
		}
	}
	idsValid := shapeValid && compat.ValidateCandidate(candidate, knownIDs) == nil
	report["result_shape_valid"] = shapeValid
	report["catalog_ids_valid"] = idsValid
	report["pass"] = shapeValid && idsValid
	if !shapeValid || !idsValid {
		report["error_category"] = string(diagnostics.Verification)
		report["outcome"] = "invalid_output"
	} else if candidate.Intervene {
		report["outcome"] = "selected"
	} else {
		report["outcome"] = "no_intervention"
	}
	return report, nil
}
