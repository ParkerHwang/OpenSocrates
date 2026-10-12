package domain

import (
	"crypto/sha256"
	"encoding/hex"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
	"strings"
	"unicode/utf8"
)

type Criterion struct {
	ID               string   `json:"criterion_id"`
	Text             string   `json:"text"`
	Required         bool     `json:"required"`
	Kind             string   `json:"kind"`
	EvidenceClaimIDs []string `json:"evidence_claim_ids"`
}
type Assumption struct {
	Text     string `json:"text"`
	Material bool   `json:"material"`
}
type Framing struct {
	Schema             string       `json:"schema"`
	JudgmentID         string       `json:"judgment_id"`
	DecisionQuestion   string       `json:"decision_question"`
	Assumptions        []Assumption `json:"assumptions"`
	DecisiveEvidence   []string     `json:"decisive_evidence"`
	CompletionCriteria []Criterion  `json:"completion_criteria"`
}
type StrictGround struct {
	ClaimID       string        `json:"claim_id"`
	Text          string        `json:"text"`
	EvidenceState EvidenceState `json:"evidence_state"`
	Material      bool          `json:"material"`
}
type StrictAlternative struct {
	ID               string   `json:"alternative_id"`
	Name             string   `json:"name"`
	Reason           string   `json:"reason"`
	MaterialClaimIDs []string `json:"material_claim_ids"`
}
type StrictPacket struct {
	Schema             string              `json:"schema"`
	DecisionQuestion   string              `json:"decision_question"`
	PublicFraming      string              `json:"public_framing"`
	MaterialGrounds    []StrictGround      `json:"material_grounds"`
	Alternatives       []StrictAlternative `json:"alternatives"`
	CompletionCriteria []Criterion         `json:"completion_criteria"`
	SameHostSecondPass bool                `json:"same_host_second_pass"`
	PacketTag          *string             `json:"packet_tag,omitempty"`
}

func StrictPublicText(s string, max int) bool {
	if !utf8.ValidString(s) || strings.TrimSpace(s) == "" || utf8.RuneCountInString(s) > max || !norm.NFC.IsNormalString(s) {
		return false
	}
	for _, r := range s {
		if r < 32 && r != '\n' && r != '\t' {
			return false
		}
	}
	return true
}

var conclusionPhrases = []string{"current conclusion", "current recommendation", "the recommendation is", "our recommendation is", "we recommend", "recommended option", "selected disposition", "selected alternative", "final answer is", "final decision is", "therefore choose", "we chose", "we choose", "selected", "rejected", "deferred", "not comparable", "not_comparable"}

func conclusionLanguage(s string) bool {
	s = cases.Fold().String(strings.Join(strings.Fields(s), " "))
	for _, p := range conclusionPhrases {
		if strings.Contains(s, p) {
			return true
		}
	}
	return false
}
func BuildStrictPacket(question, framing string, claims []ClaimVersion, alternatives []Alternative, criteria []Criterion, currentConclusion *string, selectedIDs []string) (StrictPacket, error) {
	p := StrictPacket{Schema: "opensocrates.strict-packet/1.0.0", DecisionQuestion: question, PublicFraming: framing, MaterialGrounds: []StrictGround{}, Alternatives: []StrictAlternative{}, CompletionCriteria: append([]Criterion{}, criteria...), SameHostSecondPass: true}
	if !StrictPublicText(question, 500) || !StrictPublicText(framing, 1200) || conclusionLanguage(framing) || len(claims) > 5 || len(alternatives) > 3 || len(criteria) > 8 {
		return p, contracts.ErrInvalid
	}
	candidate := []string{question, framing}
	for _, c := range claims {
		if c.Materiality != "material" || !StrictPublicText(c.ID, 32) || !StrictPublicText(c.Text, 600) || !Has([]string{"verified", "computed", "inferred", "assumed", "unverified", "conflicted"}, string(c.EvidenceState)) {
			return p, contracts.ErrInvalid
		}
		p.MaterialGrounds = append(p.MaterialGrounds, StrictGround{c.ID, c.Text, c.EvidenceState, true})
		candidate = append(candidate, c.Text)
	}
	names := map[string]bool{}
	for _, a := range alternatives {
		key := cases.Fold().String(a.Name)
		if names[key] || !StrictPublicText(a.ID, 32) || !StrictPublicText(a.Name, 160) || !StrictPublicText(a.Reason, 400) || conclusionLanguage(a.Reason) || len(a.MaterialClaimIDs) > 5 || !uniqueStrings(a.MaterialClaimIDs) {
			return p, contracts.ErrInvalid
		}
		names[key] = true
		for _, id := range a.MaterialClaimIDs {
			if !StrictPublicText(id, 32) {
				return p, contracts.ErrInvalid
			}
		}
		p.Alternatives = append(p.Alternatives, StrictAlternative{a.ID, a.Name, a.Reason, append([]string{}, a.MaterialClaimIDs...)})
		candidate = append(candidate, a.Name, a.Reason)
	}
	for i, c := range criteria {
		if p.CompletionCriteria[i].EvidenceClaimIDs == nil {
			p.CompletionCriteria[i].EvidenceClaimIDs = []string{}
		}
		if !StrictPublicText(c.Text, 400) {
			return p, contracts.ErrInvalid
		}
		candidate = append(candidate, c.Text)
	}
	for _, id := range selectedIDs {
		if !StrictPublicText(id, 32) {
			return p, contracts.ErrInvalid
		}
	}
	if currentConclusion != nil {
		if !StrictPublicText(*currentConclusion, 500) {
			return p, contracts.ErrInvalid
		}
		normalized := cases.Fold().String(strings.Join(strings.Fields(*currentConclusion), " "))
		if len([]rune(normalized)) >= 8 && strings.Contains(cases.Fold().String(strings.Join(strings.Fields(strings.Join(candidate, " ")), " ")), normalized) {
			return p, contracts.ErrInvalid
		}
	}
	if e := ValidateStrictPacket(p); e != nil {
		return p, e
	}
	g, e := contracts.CanonicalJSON(p.MaterialGrounds)
	if e != nil {
		return p, e
	}
	a, e := contracts.CanonicalJSON(p.Alternatives)
	if e != nil {
		return p, e
	}
	c, e := contracts.CanonicalJSON(p.CompletionCriteria)
	if e != nil {
		return p, e
	}
	sum := sha256.Sum256([]byte(strings.Join([]string{question, framing, string(g), string(a), string(c)}, "\x1f")))
	tag := "sha256:" + hex.EncodeToString(sum[:])
	p.PacketTag = &tag
	return p, nil
}

type StrictFinding struct {
	Kind        string   `json:"kind"`
	Summary     string   `json:"summary"`
	AffectedIDs []string `json:"affected_ids"`
}
type StrictPassResult struct {
	Schema                string           `json:"schema"`
	Outcome               string           `json:"outcome"`
	PublicSummary         string           `json:"public_summary"`
	Strength              JudgmentStrength `json:"strength"`
	SelectedAlternativeID *string          `json:"selected_alternative_id"`
	Findings              []StrictFinding  `json:"findings"`
	FlipConditions        []FlipCondition  `json:"flip_conditions"`
}

func ValidateStrictPass(s StrictPassResult) error {
	if !Has([]string{"select", "revise", "hold"}, s.Outcome) || !Has([]string{"held", "provisional", "supported", "strongly_supported"}, string(s.Strength)) || !StrictPublicText(s.PublicSummary, 1200) || s.Outcome == "hold" && s.Strength != Held || s.Outcome != "hold" && s.Strength == Held || s.Outcome == "select" && s.SelectedAlternativeID == nil || len(s.Findings) > 5 {
		return contracts.ErrInvalid
	}
	if s.SelectedAlternativeID != nil && !StrictPublicText(*s.SelectedAlternativeID, 32) {
		return contracts.ErrInvalid
	}
	for _, f := range s.Findings {
		if !Has([]string{"strongest_objection", "weakest_link", "omitted_alternative", "stale_risk", "completion_check"}, f.Kind) || !StrictPublicText(f.Summary, 400) || len(f.AffectedIDs) > 5 {
			return contracts.ErrInvalid
		}
		for _, id := range f.AffectedIDs {
			if !StrictPublicText(id, 32) {
				return contracts.ErrInvalid
			}
		}
	}
	return ValidateFlipConditions(s.FlipConditions)
}

type StrictReconciliation struct {
	Action        string
	PublicSummary string
}
type StrictComparison struct {
	FirstOutcome           string
	SecondOutcome          string
	Agreement              bool
	ReconciliationRequired bool
	Reconciled             bool
	NextAction             string
	PublicSummary          string
	ReconciliationSummary  *string
}

func (c StrictComparison) CanComplete() bool { return !c.ReconciliationRequired || c.Reconciled }
func equalOptionalString(a, b *string) bool {
	return a == nil && b == nil || a != nil && b != nil && *a == *b
}
func CompareStrictPasses(first, second StrictPassResult, firstSelectedID *string, reconciliation *StrictReconciliation) (StrictComparison, error) {
	c := StrictComparison{FirstOutcome: first.Outcome, SecondOutcome: second.Outcome}
	if e := ValidateStrictPass(first); e != nil {
		return c, e
	}
	if e := ValidateStrictPass(second); e != nil {
		return c, e
	}
	if reconciliation != nil && (!Has([]string{"revise", "hold"}, reconciliation.Action) || !StrictPublicText(reconciliation.PublicSummary, 1200)) {
		return c, contracts.ErrInvalid
	}
	agreement := first.Outcome == second.Outcome
	if agreement && first.Outcome != "hold" {
		expected := first.SelectedAlternativeID
		if firstSelectedID != nil {
			expected = firstSelectedID
		}
		agreement = equalOptionalString(first.SelectedAlternativeID, second.SelectedAlternativeID) && equalOptionalString(first.SelectedAlternativeID, expected)
	}
	c.Agreement = agreement
	c.ReconciliationRequired = !agreement
	if agreement {
		c.NextAction = "publish"
		if second.Outcome == "hold" {
			c.NextAction = "hold"
		}
		c.PublicSummary = "the two same-host passes agree"
	} else if reconciliation == nil {
		c.NextAction = "reconcile"
		c.PublicSummary = "the two same-host passes disagree and require public reconciliation"
	} else {
		c.Reconciled = true
		c.NextAction = reconciliation.Action
		c.PublicSummary = "the disagreement has a public reconciliation action"
		c.ReconciliationSummary = &reconciliation.PublicSummary
	}
	return c, nil
}
func ValidateStrictPacket(p StrictPacket) error {
	if !StrictPublicText(p.DecisionQuestion, 500) || !StrictPublicText(p.PublicFraming, 1200) || conclusionLanguage(p.PublicFraming) || !p.SameHostSecondPass || len(p.MaterialGrounds) > 5 || len(p.Alternatives) > 3 || len(p.CompletionCriteria) > 8 {
		return contracts.ErrInvalid
	}
	if p.PacketTag != nil && !safeTag.MatchString(*p.PacketTag) {
		return contracts.ErrInvalid
	}
	for _, g := range p.MaterialGrounds {
		if !g.Material || !StrictPublicText(g.ClaimID, 32) || !StrictPublicText(g.Text, 600) || !Has([]string{"verified", "computed", "inferred", "assumed", "unverified", "conflicted"}, string(g.EvidenceState)) {
			return contracts.ErrInvalid
		}
	}
	names := map[string]bool{}
	for _, a := range p.Alternatives {
		key := cases.Fold().String(a.Name)
		if names[key] || !StrictPublicText(a.ID, 32) || !StrictPublicText(a.Name, 160) || !StrictPublicText(a.Reason, 400) || conclusionLanguage(a.Reason) || len(a.MaterialClaimIDs) > 5 || !uniqueStrings(a.MaterialClaimIDs) {
			return contracts.ErrInvalid
		}
		names[key] = true
		for _, id := range a.MaterialClaimIDs {
			if !StrictPublicText(id, 32) {
				return contracts.ErrInvalid
			}
		}
	}
	for _, c := range p.CompletionCriteria {
		if !StrictPublicText(c.ID, 32) || !StrictPublicText(c.Text, 400) || !Has([]string{"structural", "evidentiary", "user_constraint", "safety", "card_contract"}, c.Kind) {
			return contracts.ErrInvalid
		}
	}
	return nil
}
