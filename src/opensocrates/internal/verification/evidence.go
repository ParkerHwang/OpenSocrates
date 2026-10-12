package verification

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"
)

type SourceURIDecision struct {
	StoredURI          *string
	RemovedCredentials bool
	Rejected           bool
	FailureCode        string
}

func InspectSourceURI(uri *string) SourceURIDecision {
	d := SourceURIDecision{StoredURI: uri}
	if uri == nil {
		return d
	}
	reject := func(code string) SourceURIDecision { return SourceURIDecision{Rejected: true, FailureCode: code} }
	if utf8.RuneCountInString(*uri) > 2048 {
		return reject("uri_too_long")
	}
	if !normText(*uri, false) || strings.ContainsAny(*uri, " \t\n\r") {
		return reject("uri_whitespace")
	}
	u, e := url.Parse(*uri)
	if e != nil {
		return reject("invalid_uri")
	}
	if u.User != nil {
		return reject("url_userinfo")
	}
	if (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
		return reject("unsupported_scheme")
	}
	if u.Scheme == "http" && !contains([]string{"localhost", "127.0.0.1", "::1"}, strings.ToLower(u.Hostname())) {
		return reject("http_non_localhost")
	}
	for k := range u.Query() {
		if contains([]string{"token", "key", "secret", "signature", "sig", "auth", "code", "session"}, normalKey(k)) {
			return SourceURIDecision{RemovedCredentials: true}
		}
	}
	return d
}
func SourceViolations(s domain.SourceReference, publicFixture bool) []Violation {
	v := []Violation{}
	if e := ValidateScalarText(s.DisplayName, 200, false); e != nil {
		v = append(v, violation("OSV-SOURCE-001", "source.display_invalid", "display_name"))
	}
	if utf8.RuneCountInString(s.DisplayName) > 200 {
		v = append(v, violation("OSV-SOURCE-002", "source.display_too_long", "display_name"))
	}
	if s.SafeLocator != nil {
		if strings.ContainsAny(*s.SafeLocator, "/\\") || strings.HasPrefix(*s.SafeLocator, "~") || privateDisplay.MatchString(*s.SafeLocator) || *s.SafeLocator == "." || *s.SafeLocator == ".." || regexp.MustCompile(`^[A-Za-z]:`).MatchString(*s.SafeLocator) {
			v = append(v, violation("OSV-SOURCE-003", "source.locator_path", "safe_locator"))
		} else if e := ValidateScalarText(*s.SafeLocator, 200, false); e != nil {
			v = append(v, violation("OSV-SOURCE-004", "source.locator_invalid", "safe_locator"))
		}
	}
	if d := InspectSourceURI(s.URI); d.Rejected {
		ids := map[string]string{"url_userinfo": "OSV-SOURCE-006", "http_non_localhost": "OSV-SOURCE-007", "unsupported_scheme": "OSV-SOURCE-008", "uri_too_long": "OSV-SOURCE-009", "uri_whitespace": "OSV-SOURCE-010"}
		id := ids[d.FailureCode]
		if id == "" {
			id = "OSV-SOURCE-005"
		}
		message := map[string]string{"url_userinfo": "source.url_userinfo", "http_non_localhost": "source.http_localhost_only", "unsupported_scheme": "source.scheme_unsupported", "uri_too_long": "source.uri_too_long", "uri_whitespace": "source.uri_whitespace"}[d.FailureCode]
		if message == "" {
			message = "source.uri_invalid"
		}
		v = append(v, violation(id, message, "uri"))
	}
	if s.ContentHash != nil && !publicFixture {
		v = append(v, violation("OSV-SOURCE-011", "source.content_hash_forbidden", "content_hash"))
	}
	return v
}
func ClaimViolations(c domain.ClaimVersion, sources map[string]domain.SourceReference, known map[string]domain.ClaimVersion) []Violation {
	v := []Violation{}
	add := func(id, message, field string) {
		if len(v) < 32 {
			v = append(v, violation(id, message, field))
		}
	}
	if e := ValidateScalarText(c.Text, 600, false); e != nil {
		add("OSV-EVIDENCE-001", "evidence.claim_text_invalid", "text")
	}
	if c.Version < 1 {
		add("OSV-EVIDENCE-006", "evidence.version_positive", "version")
	}
	if len(c.SourceIDs) > 8 {
		add("OSV-SOURCE-012", "source.reference_limit", "source_ids")
	}
	seen := map[string]bool{}
	for i, id := range c.SourceIDs {
		if seen[id] {
			add("OSV-SOURCE-013", "source.reference_unique", "source_ids")
		}
		seen[id] = true
		if sources != nil {
			s, ok := sources[id]
			if !ok {
				add("OSV-SOURCE-014", "source.reference_unknown", fmt.Sprintf("source_ids[%d]", i))
			} else {
				v = append(v, SourceViolations(s, false)...)
			}
		}
	}
	if len(c.BasisClaimIDs) > 8 {
		add("OSV-EVIDENCE-002", "evidence.basis_limit", "basis_claim_ids")
	}
	seen = map[string]bool{}
	for i, id := range c.BasisClaimIDs {
		if seen[id] {
			add("OSV-EVIDENCE-003", "evidence.basis_unique", "basis_claim_ids")
		}
		seen[id] = true
		if id == c.ID {
			add("OSV-EVIDENCE-004", "evidence.basis_self", fmt.Sprintf("basis_claim_ids[%d]", i))
		}
		if known != nil {
			if _, ok := known[id]; !ok {
				add("OSV-EVIDENCE-005", "evidence.basis_unknown", fmt.Sprintf("basis_claim_ids[%d]", i))
			}
		}
	}
	if e := domain.ValidateClaimVersion(c); e != nil {
		add("OSV-EVIDENCE-008", "evidence.state_invariant", "")
	}
	switch c.EvidenceState {
	case domain.Verified:
		if len(c.SourceIDs) == 0 {
			add("OSV-EVIDENCE-011", "evidence.verified_source_required", "source_ids")
		}
		if c.Calculation != nil || c.Conflict != nil {
			add("OSV-EVIDENCE-012", "evidence.verified_no_derived_support", "")
		}
		if c.Active && sources != nil && !domain.ClaimCanRenderVerified(c, sources) {
			add("OSV-EVIDENCE-013", "evidence.verified_source_invalid", "source_ids")
		}
	case domain.Computed:
		if c.Calculation == nil {
			add("OSV-EVIDENCE-014", "evidence.computed_calculation_required", "calculation")
		}
		if c.Conflict != nil {
			add("OSV-EVIDENCE-015", "evidence.computed_no_conflict", "conflict")
		}
	case domain.Inferred:
		if len(c.BasisClaimIDs) == 0 {
			add("OSV-EVIDENCE-016", "evidence.inferred_basis_required", "basis_claim_ids")
		}
		if c.Calculation != nil || c.Conflict != nil {
			add("OSV-EVIDENCE-017", "evidence.inferred_no_derived_support", "")
		}
	case domain.Assumed:
		if len(c.SourceIDs) > 0 || len(c.BasisClaimIDs) > 0 || c.Calculation != nil || c.Conflict != nil {
			add("OSV-EVIDENCE-018", "evidence.assumed_empty_support", "")
		}
	case domain.Unverified:
		if c.Calculation != nil || c.Conflict != nil {
			add("OSV-EVIDENCE-019", "evidence.unverified_bounded", "")
		}
	case domain.Conflicted:
		if c.Conflict == nil {
			add("OSV-CONFLICT-001", "conflict.required", "conflict")
		}
		if !(len(c.SourceIDs) >= 2 || len(c.SourceIDs) > 0 && (len(c.BasisClaimIDs) > 0 || c.Calculation != nil)) {
			add("OSV-CONFLICT-002", "conflict.source_or_basis_required", "")
		}
	default:
		add("OSV-EVIDENCE-009", "evidence.state_unknown", "evidence_state")
	}
	if c.Materiality != "material" && c.Materiality != "non_material" {
		add("OSV-EVIDENCE-010", "evidence.materiality_unknown", "materiality")
	}
	if c.EvidenceState == domain.Computed && c.Calculation != nil {
		v = append(v, CalculationViolations(*c.Calculation, sources)...)
	}
	if c.EvidenceState == domain.Conflicted && c.Conflict != nil {
		if c.Conflict.Resolution == "unresolved" && !c.Conflict.Material && c.Materiality == "material" {
			add("OSV-CONFLICT-003", "conflict.materiality_mismatch", "conflict.material")
		}
		for _, id := range c.Conflict.SourceIDs {
			if !contains(c.SourceIDs, id) {
				add("OSV-CONFLICT-004", "conflict.sources_not_claimed", "conflict.source_ids")
				break
			}
		}
	}
	if len(v) > 32 {
		v = v[:32]
	}
	return v
}
func EvidenceViolations(claims []domain.ClaimVersion, sources map[string]domain.SourceReference, strength domain.JudgmentStrength, options domain.StrengthOptions) []Violation {
	v := []Violation{}
	if len(claims) == 0 {
		return []Violation{violation("OSV-EVIDENCE-021", "evidence.claim_required", "claims")}
	}
	current, e := domain.CurrentClaims(claims)
	if e != nil {
		v = append(v, violation("OSV-EVIDENCE-020", "evidence.current_version_projection", "claim_history"))
		current = map[string]domain.ClaimVersion{}
	}
	for _, c := range claims {
		v = append(v, ClaimViolations(c, sources, current)...)
	}
	strengthClaims := claims
	if e == nil {
		strengthClaims = []domain.ClaimVersion{}
		ids := []string{}
		for id := range current {
			ids = append(ids, id)
		}
		sort.Strings(ids)
		for _, id := range ids {
			strengthClaims = append(strengthClaims, current[id])
		}
	}
	assessment, e := domain.AssessStrengthEligibility(strengthClaims, strength, options)
	if e != nil {
		v = append(v, violation("OSV-STRENGTH-000", "evidence.strength_invalid", "strength"))
	} else if !assessment.Eligible {
		ids := map[string]string{"missing_material_basis": "OSV-STRENGTH-001", "unresolved_material_conflict": "OSV-STRENGTH-002", "required_criterion_unverified": "OSV-STRENGTH-003", "missing_decisive_evidence": "OSV-STRENGTH-004", "material_basis_is_assumed_or_unverified": "OSV-STRENGTH-005", "material_claim_is_conflicted": "OSV-STRENGTH-006", "strength_requirements_not_met": "OSV-STRENGTH-007"}
		for _, r := range assessment.Reasons {
			messages := map[string]string{"missing_material_basis": "evidence.material_basis_required", "unresolved_material_conflict": "conflict.must_hold_or_lower", "required_criterion_unverified": "completion.required_criterion_unverified", "missing_decisive_evidence": "evidence.decisive_missing", "material_basis_is_assumed_or_unverified": "evidence.strong_support_required", "material_claim_is_conflicted": "conflict.must_resolve_or_hold", "strength_requirements_not_met": "evidence.strength_requirements"}
			v = append(v, violation(ids[r], messages[r], "strength"))
		}
	}
	if len(v) > 32 {
		v = v[:32]
	}
	return v
}
