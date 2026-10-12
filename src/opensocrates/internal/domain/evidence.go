package domain

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"net/url"
	"sort"
	"strings"
)

type EvidenceState string

const (
	Verified   EvidenceState = "verified"
	Computed   EvidenceState = "computed"
	Inferred   EvidenceState = "inferred"
	Assumed    EvidenceState = "assumed"
	Unverified EvidenceState = "unverified"
	Conflicted EvidenceState = "conflicted"
)

type JudgmentStrength string

const (
	Held              JudgmentStrength = "held"
	Provisional       JudgmentStrength = "provisional"
	Supported         JudgmentStrength = "supported"
	StronglySupported JudgmentStrength = "strongly_supported"
)

type SourceReference struct {
	Schema      string  `json:"schema"`
	ID          string  `json:"source_id"`
	Kind        string  `json:"kind"`
	DisplayName string  `json:"display_name"`
	URI         *string `json:"uri"`
	SafeLocator *string `json:"safe_locator"`
	PublishedAt *string `json:"published_at"`
	CheckedAt   string  `json:"checked_at"`
	ContentHash *string `json:"content_hash"`
}
type CalculationOperand struct {
	Name     string  `json:"name"`
	Value    string  `json:"value"`
	Unit     string  `json:"unit"`
	SourceID *string `json:"source_id"`
}
type Calculation struct {
	Schema     string               `json:"schema"`
	Expression string               `json:"expression"`
	Operands   []CalculationOperand `json:"operands"`
	Result     string               `json:"result"`
	Unit       string               `json:"unit"`
	Rounding   string               `json:"rounding"`
}
type Conflict struct {
	Schema           string   `json:"schema"`
	Summary          string   `json:"summary"`
	Subject          string   `json:"subject"`
	SourceIDs        []string `json:"source_ids"`
	AffectedClaimIDs []string `json:"affected_claim_ids"`
	Material         bool     `json:"material"`
	Resolution       string   `json:"resolution"`
	ResolutionReason *string  `json:"resolution_reason"`
}
type ClaimVersion struct {
	Schema        string        `json:"schema"`
	ID            string        `json:"claim_id"`
	Version       int           `json:"version"`
	Text          string        `json:"text"`
	Materiality   string        `json:"materiality"`
	EvidenceState EvidenceState `json:"evidence_state"`
	SourceIDs     []string      `json:"source_ids"`
	BasisClaimIDs []string      `json:"basis_claim_ids"`
	Calculation   *Calculation  `json:"calculation"`
	Conflict      *Conflict     `json:"conflict"`
	Active        bool          `json:"active"`
}

func uniqueStrings(values []string) bool {
	seen := map[string]bool{}
	for _, s := range values {
		if seen[s] {
			return false
		}
		seen[s] = true
	}
	return true
}
func ValidateClaimVersion(c ClaimVersion) error {
	if c.Version < 1 || !publicText(c.Text, 600) || c.ID == "" || !Has([]string{"material", "non_material"}, c.Materiality) || len(c.SourceIDs) > 8 || len(c.BasisClaimIDs) > 8 || !uniqueStrings(c.SourceIDs) || !uniqueStrings(c.BasisClaimIDs) {
		return contracts.ErrInvalid
	}
	switch c.EvidenceState {
	case Verified:
		if len(c.SourceIDs) == 0 || c.Calculation != nil || c.Conflict != nil {
			return contracts.ErrInvalid
		}
	case Computed:
		if c.Calculation == nil || c.Conflict != nil {
			return contracts.ErrInvalid
		}
	case Inferred:
		if len(c.BasisClaimIDs) == 0 || c.Calculation != nil || c.Conflict != nil {
			return contracts.ErrInvalid
		}
	case Assumed:
		if len(c.SourceIDs) > 0 || len(c.BasisClaimIDs) > 0 || c.Calculation != nil || c.Conflict != nil {
			return contracts.ErrInvalid
		}
	case Unverified:
		if c.Calculation != nil || c.Conflict != nil {
			return contracts.ErrInvalid
		}
	case Conflicted:
		if c.Conflict == nil || !(len(c.SourceIDs) >= 2 || len(c.SourceIDs) > 0 && (len(c.BasisClaimIDs) > 0 || c.Calculation != nil)) {
			return contracts.ErrInvalid
		}
	default:
		return contracts.ErrInvalid
	}
	return nil
}
func ReviseClaim(previous, next ClaimVersion) (ClaimVersion, ClaimVersion, error) {
	if e := ValidateClaimVersion(previous); e != nil {
		return ClaimVersion{}, ClaimVersion{}, e
	}
	if !previous.Active {
		return ClaimVersion{}, ClaimVersion{}, contracts.ErrInvalid
	}
	next.ID = previous.ID
	next.Version = previous.Version + 1
	next.Active = true
	next.Schema = "opensocrates.claim-version/1.0.0"
	if e := ValidateClaimVersion(next); e != nil {
		return ClaimVersion{}, ClaimVersion{}, e
	}
	previous.Active = false
	return previous, next, nil
}
func CurrentClaims(claims []ClaimVersion) (map[string]ClaimVersion, error) {
	grouped := map[string][]ClaimVersion{}
	for _, c := range claims {
		if e := ValidateClaimVersion(c); e != nil {
			return nil, e
		}
		grouped[c.ID] = append(grouped[c.ID], c)
	}
	current := map[string]ClaimVersion{}
	for id, versions := range grouped {
		sort.Slice(versions, func(i, j int) bool { return versions[i].Version < versions[j].Version })
		active := 0
		for i, c := range versions {
			if c.Version != i+1 {
				return nil, contracts.ErrInvalid
			}
			if c.Active {
				active++
				if i != len(versions)-1 {
					return nil, contracts.ErrInvalid
				}
				current[id] = c
			}
		}
		if active != 1 {
			return nil, contracts.ErrInvalid
		}
	}
	return current, nil
}

type StrengthOptions struct {
	RequiredCriteria            []CompletionCriterion
	RequiredCriterionUnverified bool
	MissingDecisiveEvidence     bool
	BlockingConflict            bool
	Conflicts                   []Conflict
}
type StrengthEligibility struct {
	Requested JudgmentStrength
	Eligible  bool
	Reasons   []string
}

func AssessStrengthEligibility(claims []ClaimVersion, strength JudgmentStrength, o StrengthOptions) (StrengthEligibility, error) {
	if !Has([]string{"held", "provisional", "supported", "strongly_supported"}, string(strength)) {
		return StrengthEligibility{}, contracts.ErrInvalid
	}
	material := []ClaimVersion{}
	for _, c := range claims {
		if e := ValidateClaimVersion(c); e != nil {
			return StrengthEligibility{}, e
		}
		if c.Materiality == "material" {
			material = append(material, c)
		}
	}
	r := StrengthEligibility{strength, true, []string{}}
	if len(material) == 0 {
		r.Reasons = append(r.Reasons, "missing_material_basis")
	}
	unresolved := o.BlockingConflict
	weak := false
	conflicted := false
	strongGrounds := true
	for _, c := range material {
		weak = weak || c.EvidenceState == Assumed || c.EvidenceState == Unverified
		conflicted = conflicted || c.EvidenceState == Conflicted
		unresolved = unresolved || c.EvidenceState == Conflicted && c.Conflict != nil && c.Conflict.Material && c.Conflict.Resolution == "unresolved"
		strongGrounds = strongGrounds && (c.EvidenceState == Verified || c.EvidenceState == Computed)
	}
	for _, c := range o.Conflicts {
		unresolved = unresolved || c.Material && c.Resolution == "unresolved"
	}
	if unresolved {
		r.Reasons = append(r.Reasons, "unresolved_material_conflict")
	}
	criterionBlocker := o.RequiredCriterionUnverified
	for _, c := range o.RequiredCriteria {
		criterionBlocker = criterionBlocker || c.Required && (!Has([]string{"met", "unmet", "unverified", "not_applicable", "not_recorded"}, string(c.Status)) || c.Status == Unmet || c.Status == CriterionUnverified || c.Status == NotRecorded)
	}
	if criterionBlocker {
		r.Reasons = append(r.Reasons, "required_criterion_unverified")
	}
	if o.MissingDecisiveEvidence {
		r.Reasons = append(r.Reasons, "missing_decisive_evidence")
	}
	if weak {
		r.Reasons = append(r.Reasons, "material_basis_is_assumed_or_unverified")
	}
	if conflicted {
		r.Reasons = append(r.Reasons, "material_claim_is_conflicted")
	}
	blocker := unresolved || o.MissingDecisiveEvidence || len(material) == 0 || conflicted
	switch strength {
	case Provisional:
		r.Eligible = weak && !blocker
	case Supported:
		r.Eligible = len(material) > 0 && !weak && !blocker
	case StronglySupported:
		r.Eligible = len(material) > 0 && !blocker && !criterionBlocker && strongGrounds
	}
	if !r.Eligible && len(r.Reasons) == 0 {
		r.Reasons = append(r.Reasons, "strength_requirements_not_met")
	}
	return r, nil
}
func ClaimCanRenderVerified(c ClaimVersion, sources map[string]SourceReference) bool {
	if !c.Active || c.EvidenceState != Verified || len(c.SourceIDs) == 0 || c.Calculation != nil || c.Conflict != nil {
		return false
	}
	if sources != nil {
		for _, id := range c.SourceIDs {
			if _, ok := sources[id]; !ok {
				return false
			}
		}
	}
	return true
}

// Unsafe credential-bearing URIs are omitted while their public source remains.
func SanitizeSourceURI(uri *string) *string { result, _ := ValidateStoredSourceURI(uri); return result }
func ValidateStoredSourceURI(uri *string) (*string, error) {
	if uri == nil {
		return nil, nil
	}
	u, e := url.Parse(*uri)
	if e != nil || u.User != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.Scheme == "http" && !Has([]string{"localhost", "127.0.0.1", "::1"}, u.Hostname()) {
		return nil, contracts.ErrInvalid
	}
	sensitive := []string{"token", "key", "secret", "signature", "sig", "auth", "code", "session"}
	for k := range u.Query() {
		if Has(sensitive, strings.ToLower(k)) {
			return nil, nil
		}
	}
	copy := *uri
	return &copy, nil
}
func MakeSourceReference(source SourceReference, publicFixture bool) (SourceReference, error) {
	if source.ContentHash != nil && !publicFixture || !publicText(source.DisplayName, 200) || !Has([]string{"web", "user_document", "host_connector", "dataset", "calculation_input", "user_statement"}, source.Kind) {
		return SourceReference{}, contracts.ErrInvalid
	}
	source.Schema = "opensocrates.source-reference/1.0.0"
	uri, e := ValidateStoredSourceURI(source.URI)
	if e != nil {
		return SourceReference{}, e
	}
	source.URI = uri
	return source, nil
}

type CardSourceReference struct {
	DisplayName string  `json:"display_name"`
	URI         *string `json:"uri"`
}
type ConclusionGround struct {
	ClaimID            string                `json:"claim_id"`
	Text               string                `json:"text"`
	State              EvidenceState         `json:"state"`
	SourceRefs         []CardSourceReference `json:"source_refs"`
	CalculationSummary *string               `json:"calculation_summary"`
}
type ConclusionCard struct {
	Schema              string             `json:"schema"`
	Locale              string             `json:"locale"`
	TaskID              string             `json:"task_id"`
	JudgmentID          string             `json:"judgment_id"`
	JudgmentVersion     int                `json:"judgment_version"`
	Conclusion          string             `json:"conclusion"`
	Strength            JudgmentStrength   `json:"strength"`
	Grounds             []ConclusionGround `json:"grounds"`
	Uncertainties       []string           `json:"uncertainties"`
	FlipConditions      []FlipCondition    `json:"flip_conditions"`
	AlternativesSummary string             `json:"alternatives_summary"`
	RenderedAt          string             `json:"rendered_at"`
}
