// Package compat implements only the opt-in legacy Codex selector. The normal
// decision path does not call this package, start a model, or require auth.
package compat

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"io"
	"strings"
	"time"
	"unicode/utf8"
)

const CodexVersion = "0.144.4"
const ProtocolCommit = "8c68d4c87dc54d38861f5114e920c3de2efa5876"
const RecursionEnvironment = "OPENSOCRATES_SELECTOR_ACTIVE"
const MaxPromptBytes = 256 * 1024
const MaxCatalogBytes = 512 * 1024
const MaxResponseBytes = 256 * 1024
const MaxContextCalls = 8
const MaxContextReadBytes = 32 * 1024
const MaxContextTotalBytes = 256 * 1024
const MaxDirectoryEntries = 128

type Handles struct {
	TranscriptPath          string
	WorkspacePath           string
	ReferencedFiles         []string
	TranscriptAccessEnabled bool
}

func (Handles) String() string { return "SelectorContextHandles(<transient-redacted>)" }

type Request struct {
	Prompt          string
	Catalog         string
	Context         Handles
	Deadline        time.Duration
	ReasoningEffort string
	// TrustedExplicitLocale is supplied by a trusted caller, never by prompt text.
	// Nil means absent; a non-nil unsupported value rejects the request.
	TrustedExplicitLocale *string
	StoredPreference      *string
}

func (Request) String() string { return "SelectorRequest(<transient-redacted>)" }

type Candidate struct {
	Intervene                bool     `json:"intervene"`
	SelectedReasoningSystems []string `json:"selected_reasoning_systems"`
	Instructions             string   `json:"instructions"`
}

func (Candidate) String() string          { return "RawSelectorCandidate(<transient-redacted>)" }
func failure(code diagnostics.Code) error { return diagnostics.New(code, "legacy_selector") }

type OutcomeError struct {
	Code    diagnostics.Code
	Outcome string
}

func (e *OutcomeError) Error() string { return "legacy_selector: " + e.Outcome }
func outcomeFailure(code diagnostics.Code, outcome string) error {
	return &OutcomeError{Code: code, Outcome: outcome}
}

func validText(s string, max int, nonempty bool) bool {
	return (!nonempty || s != "") && len(s) <= max && utf8.ValidString(s) && !strings.ContainsRune(s, 0)
}
func validMethodID(id string) bool {
	if len(id) < 1 {
		return false
	}
	for _, part := range strings.Split(id, "-") {
		if part == "" {
			return false
		}
		for _, r := range part {
			if !(r >= 'a' && r <= 'z' || r >= '0' && r <= '9') {
				return false
			}
		}
	}
	return true
}

// DecodeCandidate distinguishes null from empty arrays and omitted from false,
// rejects unknown fields, and never exposes a decoder error containing content.
func DecodeCandidate(data []byte) (*Candidate, error) {
	if len(data) > MaxResponseBytes || !utf8.Valid(data) {
		return nil, failure(diagnostics.Verification)
	}
	if _, err := contracts.Decode(data); err != nil {
		return nil, failure(diagnostics.Verification)
	}
	var fields map[string]json.RawMessage
	dec := json.NewDecoder(strings.NewReader(string(data)))
	if dec.Decode(&fields) != nil || len(fields) != 3 {
		return nil, failure(diagnostics.Verification)
	}
	var tail any
	if dec.Decode(&tail) != io.EOF {
		return nil, failure(diagnostics.Verification)
	}
	for _, k := range []string{"intervene", "selected_reasoning_systems", "instructions"} {
		if len(fields[k]) == 0 || string(fields[k]) == "null" {
			return nil, failure(diagnostics.Verification)
		}
	}
	var c Candidate
	if json.Unmarshal(fields["intervene"], &c.Intervene) != nil || json.Unmarshal(fields["selected_reasoning_systems"], &c.SelectedReasoningSystems) != nil || json.Unmarshal(fields["instructions"], &c.Instructions) != nil {
		return nil, failure(diagnostics.Verification)
	}
	if c.SelectedReasoningSystems == nil || !validText(c.Instructions, MaxResponseBytes, false) {
		return nil, failure(diagnostics.Verification)
	}
	seen := map[string]bool{}
	for _, id := range c.SelectedReasoningSystems {
		if !validMethodID(id) || seen[id] {
			return nil, failure(diagnostics.Verification)
		}
		seen[id] = true
	}
	if c.Intervene {
		if len(seen) == 0 || strings.TrimSpace(c.Instructions) == "" {
			return nil, failure(diagnostics.Verification)
		}
	} else if len(seen) > 0 || c.Instructions != "" {
		return nil, failure(diagnostics.Verification)
	}
	return &c, nil
}

// ValidateCandidate is required before authored assembly. The model's
// instructions are an untrusted marker and are never injectable content.
func ValidateCandidate(c *Candidate, knownIDs []string) error {
	if c == nil {
		return failure(diagnostics.Verification)
	}
	b, err := json.Marshal(c)
	if err != nil {
		return failure(diagnostics.Verification)
	}
	if _, err = DecodeCandidate(b); err != nil {
		return err
	}
	known := map[string]bool{}
	for _, id := range knownIDs {
		if !validMethodID(id) {
			return failure(diagnostics.Verification)
		}
		known[id] = true
	}
	for _, id := range c.SelectedReasoningSystems {
		if !known[id] {
			return failure(diagnostics.Verification)
		}
	}
	return nil
}

// Locale preserves the released selector's current-prompt script policy,
// including ASCII letters without digits and English for ties.
func Locale(prompt string) string { return domain.DetectLocale(prompt, false) }
