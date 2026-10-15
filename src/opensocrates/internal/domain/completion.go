package domain

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"unicode/utf8"
)

type CriterionStatus string

const (
	Met                 CriterionStatus = "met"
	Unmet               CriterionStatus = "unmet"
	CriterionUnverified CriterionStatus = "unverified"
	NotApplicable       CriterionStatus = "not_applicable"
	NotRecorded         CriterionStatus = "not_recorded"
)

type VerificationOutcome string

const (
	Pass              VerificationOutcome = "pass"
	Repair            VerificationOutcome = "repair"
	Insufficient      VerificationOutcome = "insufficient"
	Degraded          VerificationOutcome = "degraded"
	VerificationError VerificationOutcome = "error"
)

type CompletionCriterion struct {
	ID       string          `json:"criterion_id"`
	Status   CriterionStatus `json:"status"`
	Reason   string          `json:"reason"`
	Required bool            `json:"required"`
}
type RequiredCriterionGap struct {
	ID     string
	Status CriterionStatus
	Reason string
}
type CompletionResult struct {
	Schema            string                `json:"schema"`
	JudgmentID        string                `json:"judgment_id"`
	CandidateSequence int                   `json:"candidate_sequence"`
	Outcome           VerificationOutcome   `json:"outcome"`
	Criteria          []CompletionCriterion `json:"criteria"`
	Violations        []string              `json:"violations"`
	RepairCountBefore int                   `json:"repair_count_before"`
	MayContinue       bool                  `json:"may_continue"`
}

func CriterionIsMet(c CompletionCriterion) bool { return !c.Required || c.Status == Met }
func RequiredCriterionGaps(criteria []CompletionCriterion) []RequiredCriterionGap {
	gaps := []RequiredCriterionGap{}
	reasons := map[CriterionStatus]string{Unmet: "Required criterion is not met.", CriterionUnverified: "Required criterion is not verified.", NotRecorded: "Required criterion was not recorded.", NotApplicable: "Required criterion cannot be not applicable.", "": "Required criterion has no recorded status."}
	for _, c := range criteria {
		if c.Required && c.Status != Met {
			reason := reasons[c.Status]
			if reason == "" {
				reason = "Required criterion is not met."
			}
			gaps = append(gaps, RequiredCriterionGap{c.ID, c.Status, reason})
		}
	}
	return gaps
}
func AllRequiredCriteriaMet(criteria []CompletionCriterion) bool {
	required := false
	for _, c := range criteria {
		required = required || c.Required
		if !CriterionIsMet(c) {
			return false
		}
	}
	return required
}
func NormalizeCriteria(criteria []CompletionCriterion) ([]CompletionCriterion, error) {
	if len(criteria) > 8 {
		return nil, contracts.ErrInvalid
	}
	result := append([]CompletionCriterion{}, criteria...)
	for i := range result {
		c := &result[i]
		if c.ID == "" {
			return nil, contracts.ErrInvalid
		}
		if !Has([]string{"met", "unmet", "unverified", "not_applicable", "not_recorded"}, string(c.Status)) {
			c.Status = NotRecorded
		}
		if !publicText(c.Reason, 1<<20) {
			c.Reason = c.ID
		}
		if utf8.RuneCountInString(c.Reason) > 400 {
			c.Reason = string([]rune(c.Reason)[:400])
		}
	}
	return result, nil
}
func CompletionOutcome(criteria []CompletionCriterion, blockingViolations, repairCountBefore int) (VerificationOutcome, error) {
	if blockingViolations < 0 || repairCountBefore < 0 {
		return "", contracts.ErrInvalid
	}
	normal, e := NormalizeCriteria(criteria)
	if e != nil {
		return "", e
	}
	if !AllRequiredCriteriaMet(normal) {
		return Insufficient, nil
	}
	if blockingViolations > 0 {
		if repairCountBefore == 0 {
			return Repair, nil
		}
		return Degraded, nil
	}
	return Pass, nil
}
func BuildCompletionResult(judgmentID string, candidateSequence int, criteria []CompletionCriterion, violations []string, blockingViolations, repairCountBefore int, requested *VerificationOutcome, continueRequested *bool) (CompletionResult, error) {
	normal, e := NormalizeCriteria(criteria)
	if e != nil {
		return CompletionResult{}, e
	}
	outcome, e := CompletionOutcome(normal, blockingViolations, repairCountBefore)
	if e != nil {
		return CompletionResult{}, e
	}
	if requested != nil {
		if !Has([]string{"pass", "repair", "insufficient", "degraded", "error"}, string(*requested)) {
			return CompletionResult{}, contracts.ErrInvalid
		}
		if outcome != Insufficient && !(*requested == Pass && outcome != Pass) {
			outcome = *requested
		}
	}
	mayContinue := outcome == Repair && repairCountBefore == 0
	if continueRequested != nil {
		mayContinue = mayContinue && *continueRequested
	}
	if judgmentID == "" || candidateSequence < 1 {
		return CompletionResult{}, contracts.ErrInvalid
	}
	return CompletionResult{"opensocrates.completion-result/1.0.0", judgmentID, candidateSequence, outcome, normal, append([]string{}, violations...), repairCountBefore, mayContinue}, nil
}
