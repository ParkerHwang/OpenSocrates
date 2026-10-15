package domain

import "github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"

type ConflictSignals struct {
	ChangesConclusion         bool
	ChangesAlternativeOrder   bool
	ChangesHighSeverityRisk   bool
	BlocksCompletionCriterion bool
	ChangesStrength           bool
	ExplicitlyMaterial        bool
	PubliclyRelevant          bool
}

func (s ConflictSignals) Material() bool {
	return s.ChangesConclusion || s.ChangesAlternativeOrder || s.ChangesHighSeverityRisk || s.BlocksCompletionCriterion || s.ChangesStrength || s.ExplicitlyMaterial
}

type ConflictAssessment struct {
	Material           bool
	Action             string
	Public             bool
	Blocking           bool
	ResolutionRecorded bool
	RequiresNewVersion bool
}

func AssessConflict(c Conflict, s *ConflictSignals, rejudgmentAvailable, holdRequested bool) (ConflictAssessment, error) {
	if !Has([]string{"unresolved", "source_precedence", "recency", "measurement_definition", "calculation_correction", "scope_split", "user_decision"}, c.Resolution) {
		return ConflictAssessment{}, contracts.ErrInvalid
	}
	material := c.Material || s != nil && s.Material()
	if !material {
		public := true
		if s != nil {
			public = s.PubliclyRelevant
		}
		return ConflictAssessment{false, "public_only", public, false, c.Resolution != "unresolved", false}, nil
	}
	recorded := c.Resolution != "unresolved"
	public := recorded && c.ResolutionReason != nil && publicText(*c.ResolutionReason, 600)
	action := "revise_required"
	if holdRequested || !rejudgmentAvailable || recorded && !public {
		action = "hold_required"
	}
	return ConflictAssessment{true, action, true, true, public, true}, nil
}
func ResolveConflictPublicly(c Conflict, reason string) (Conflict, error) {
	if c.Resolution == "unresolved" || !publicText(reason, 600) {
		return Conflict{}, contracts.ErrInvalid
	}
	c.ResolutionReason = &reason
	return c, nil
}

type JudgmentVersion struct {
	JudgmentID          string           `json:"judgment_id"`
	Version             int              `json:"version"`
	State               string           `json:"state"`
	Conclusion          *string          `json:"conclusion"`
	Strength            JudgmentStrength `json:"strength"`
	SupersedesVersion   *int             `json:"supersedes_version"`
	ChangeReason        *string          `json:"change_reason"`
	GroundClaimIDs      []string         `json:"ground_claim_ids"`
	UncertaintyClaimIDs []string         `json:"uncertainty_claim_ids"`
	FlipConditions      []FlipCondition  `json:"flip_conditions"`
	AlternativeIDs      []string         `json:"alternative_ids"`
}
type JudgmentVersionHistory struct {
	Prior   JudgmentVersion
	Current JudgmentVersion
}

func PreserveJudgmentVersion(prior, current JudgmentVersion) (JudgmentVersionHistory, error) {
	if prior.JudgmentID != current.JudgmentID || current.Version != prior.Version+1 || current.SupersedesVersion == nil || *current.SupersedesVersion != prior.Version || !Has([]string{"revised", "held"}, current.State) {
		return JudgmentVersionHistory{}, contracts.ErrInvalid
	}
	return JudgmentVersionHistory{prior, current}, nil
}
func HoldJudgmentVersion(current JudgmentVersion, reason string) (JudgmentVersion, error) {
	if !publicText(reason, 500) || current.Version < 1 {
		return JudgmentVersion{}, contracts.ErrInvalid
	}
	prior := current.Version
	current.Version++
	current.State = "held"
	current.Strength = Held
	current.SupersedesVersion = &prior
	current.ChangeReason = &reason
	return current, nil
}
func PreserveClaimVersion(prior, current ClaimVersion) error {
	if prior.ID != current.ID || current.Version != prior.Version+1 || !prior.Active || !current.Active {
		return contracts.ErrInvalid
	}
	return nil
}
