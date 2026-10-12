package verification

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"sort"
	"strings"
	"time"
)

type TaskContext struct {
	TaskID              string
	Locale              string
	State               domain.TaskState
	CurrentJudgmentID   *string
	AnswerShape         string
	RequiresAlternative bool
}
type VerificationRequest struct {
	Card                    *domain.ConclusionCard
	Markdown                *string
	Locale                  string
	Messages                map[string]string
	Context                 TrustedCardContext
	Task                    *TaskContext
	Framing                 *domain.Framing
	CurrentJudgment         *domain.JudgmentVersion
	Claims                  []domain.ClaimVersion
	Sources                 map[string]domain.SourceReference
	CriterionStatuses       map[string]domain.CompletionCriterion
	Alternatives            []domain.Alternative
	Conflicts               []domain.Conflict
	CapabilityProfile       *domain.CapabilityProfile
	CandidateSequence       int
	RepairCountBefore       int
	PublicClaimChanged      bool
	MissingDecisiveEvidence bool
}
type VerificationResult struct {
	Schema           string                     `json:"schema"`
	Outcome          domain.VerificationOutcome `json:"outcome"`
	VerifierVersion  string                     `json:"verifier_version"`
	RulesetVersion   string                     `json:"ruleset_version"`
	Violations       []Violation                `json:"violations"`
	ParsedCard       *domain.ConclusionCard     `json:"parsed_card"`
	CompletionResult *domain.CompletionResult   `json:"completion_result"`
	DurationMS       int64                      `json:"duration_ms"`
}

func EvaluateCompletionCriteria(framing *domain.Framing, cardValid bool, claims []domain.ClaimVersion, statuses map[string]domain.CompletionCriterion, privacy bool) []domain.CompletionCriterion {
	result := []domain.CompletionCriterion{}
	if framing == nil {
		return result
	}
	current, e := domain.CurrentClaims(claims)
	if e != nil {
		current = map[string]domain.ClaimVersion{}
	}
	for i, c := range framing.CompletionCriteria {
		if i >= 8 {
			break
		}
		if c.ID == "" {
			continue
		}
		status := domain.NotRecorded
		reason := c.Text
		if strings.TrimSpace(reason) == "" {
			reason = c.ID
		}
		if len([]rune(reason)) > 400 {
			reason = string([]rune(reason)[:400])
		}
		if override, ok := statuses[c.ID]; ok {
			if contains([]string{"met", "unmet", "unverified", "not_applicable", "not_recorded"}, string(override.Status)) {
				status = override.Status
			}
			if strings.TrimSpace(override.Reason) != "" {
				reason = override.Reason
			}
		} else if c.Kind == "card_contract" {
			if cardValid {
				status = domain.Met
			} else {
				status = domain.Unmet
			}
		} else if c.Kind == "evidentiary" {
			if len(c.EvidenceClaimIDs) > 0 {
				status = domain.Met
				missing, conflict, weak := false, false, false
				for _, id := range c.EvidenceClaimIDs {
					claim, ok := current[id]
					missing = missing || !ok
					conflict = conflict || claim.EvidenceState == domain.Conflicted
					weak = weak || claim.EvidenceState == domain.Unverified || claim.EvidenceState == domain.Assumed
				}
				switch {
				case missing:
					status = domain.NotRecorded
				case conflict:
					status = domain.Unmet
				case weak:
					status = domain.CriterionUnverified
				}
			}
		} else if privacy {
			status = domain.Unmet
		}
		result = append(result, domain.CompletionCriterion{ID: c.ID, Status: status, Reason: reason, Required: c.Required})
	}
	return result
}
func stableViolations(values []Violation) []Violation {
	seen := map[string]bool{}
	result := []Violation{}
	for _, v := range values {
		if v.RepairHintKey == nil || !strings.HasPrefix(*v.RepairHintKey, "repair.") {
			hint := "repair.group"
			v.RepairHintKey = &hint
		}
		field := ""
		if v.Field != nil {
			field = *v.Field
		}
		key := v.RuleID + "\x00" + v.Severity + "\x00" + field + "\x00" + v.MessageKey
		if !seen[key] {
			seen[key] = true
			result = append(result, v)
		}
	}
	sort.SliceStable(result, func(i, j int) bool {
		a, b := result[i], result[j]
		if a.RuleID != b.RuleID {
			return a.RuleID < b.RuleID
		}
		af, bf := "", ""
		if a.Field != nil {
			af = *a.Field
		}
		if b.Field != nil {
			bf = *b.Field
		}
		if af != bf {
			return af < bf
		}
		if a.MessageKey != b.MessageKey {
			return a.MessageKey < b.MessageKey
		}
		return a.Severity < b.Severity
	})
	if len(result) > 64 {
		result = result[:64]
	}
	return result
}
func CompletionViolations(card domain.ConclusionCard, r VerificationRequest, criteria []domain.CompletionCriterion, incoming []Violation) []Violation {
	v := append([]Violation{}, incoming...)
	add := func(id, message, field string) { v = append(v, violation(id, message, field)) }
	if r.Task == nil {
		add("OSV-CAPABILITY-001", "capability.current_projection_missing", "/task_projection")
	} else {
		if card.TaskID != r.Task.TaskID {
			add("OSV-CARD-011", "card.task_mismatch", "/task_id")
		}
		if card.Locale != r.Task.Locale {
			add("OSV-LOCALE-002", "locale.card_task_mismatch", "/locale")
		}
		if r.Task.State == domain.TaskBypassed || r.Task.State == domain.TaskCancelled {
			add("OSV-CAPABILITY-004", "capability.task_not_judgment", "/task_projection.state")
		}
	}
	if r.CurrentJudgment == nil {
		add("OSV-CAPABILITY-002", "capability.current_judgment_missing", "/current_judgment")
	} else {
		j := r.CurrentJudgment
		if r.Task != nil && r.Task.CurrentJudgmentID != nil && *r.Task.CurrentJudgmentID != j.JudgmentID || card.JudgmentID != j.JudgmentID {
			add("OSV-CARD-012", "card.judgment_mismatch", "/judgment_id")
		}
		if card.JudgmentVersion != j.Version {
			add("OSV-CARD-013", "card.version_stale", "/judgment_version")
		}
		if j.Conclusion != nil && *j.Conclusion != "" && card.Conclusion != *j.Conclusion {
			add("OSV-CARD-014", "card.conclusion_stale", "/conclusion")
		}
		if card.Strength != j.Strength {
			add("OSV-CARD-015", "card.strength_mismatch", "/strength")
		}
		ids := []string{}
		for _, g := range card.Grounds {
			ids = append(ids, g.ClaimID)
		}
		if strings.Join(ids, "\x00") != strings.Join(j.GroundClaimIDs, "\x00") {
			key := "card.ground_ids_mismatch"
			if len(j.GroundClaimIDs) == 0 {
				key = "card.ground_ids_missing"
			}
			add("OSV-CARD-016", key, "/grounds")
		}
	}
	current, e := domain.CurrentClaims(r.Claims)
	if e != nil {
		add("OSV-EVIDENCE-012", "evidence.current_claim_invalid", "/claims")
		current = map[string]domain.ClaimVersion{}
	}
	for i, g := range card.Grounds {
		c, ok := current[g.ClaimID]
		field := fmt.Sprintf("/grounds/%d", i)
		if !ok {
			add("OSV-EVIDENCE-010", "evidence.current_claim_missing", field+"/claim_id")
			continue
		}
		if c.EvidenceState != g.State {
			add("OSV-EVIDENCE-011", "evidence.state_mismatch", field+"/state")
		}
		if c.Text != "" && c.Text != g.Text {
			add("OSV-EVIDENCE-014", "evidence.claim_text_stale", field+"/text")
		}
	}
	for _, c := range r.Conflicts {
		if c.Material && c.Resolution == "unresolved" {
			add("OSV-CONFLICT-003", "conflict.material_unresolved", "/conflicts")
		}
	}
	for _, c := range current {
		if c.EvidenceState == domain.Conflicted && c.Conflict != nil && c.Conflict.Material && c.Conflict.Resolution == "unresolved" {
			add("OSV-CONFLICT-003", "conflict.material_unresolved", "/claims")
		}
	}
	if r.PublicClaimChanged {
		add("OSV-COMPLETION-006", "completion.new_candidate_required", "/candidate")
	}
	choice := r.Task != nil && (r.Task.RequiresAlternative || strings.Contains(r.Task.AnswerShape, "decision") || strings.Contains(r.Task.AnswerShape, "choice")) || r.CurrentJudgment != nil && len(r.CurrentJudgment.AlternativeIDs) > 0
	if choice {
		nonSelected := false
		for _, a := range r.Alternatives {
			nonSelected = nonSelected || a.Disposition != "selected"
		}
		if !nonSelected {
			add("OSV-COMPLETION-007", "completion.alternative_required", "/alternatives")
		}
	}
	if r.Framing != nil {
		if len(r.Framing.CompletionCriteria) > 8 {
			add("OSV-COMPLETION-008", "completion.criteria_limit", "/completion_criteria")
		}
		seen := map[string]bool{}
		for i, c := range r.Framing.CompletionCriteria {
			if i >= 8 {
				break
			}
			if c.ID == "" {
				add("OSV-COMPLETION-008", "completion.criterion_id_invalid", fmt.Sprintf("/completion_criteria/%d/criterion_id", i))
			} else if seen[c.ID] {
				add("OSV-COMPLETION-008", "completion.criterion_id_duplicate", fmt.Sprintf("/completion_criteria/%d/criterion_id", i))
			}
			seen[c.ID] = true
		}
	}
	required := false
	for _, c := range criteria {
		required = required || c.Required
	}
	if len(criteria) == 0 {
		add("OSV-COMPLETION-005", "completion.criteria_missing", "/completion_criteria")
	} else if !required {
		add("OSV-COMPLETION-005", "completion.required_criterion_missing", "/completion_criteria")
	}
	for _, g := range domain.RequiredCriterionGaps(criteria) {
		ids := map[domain.CriterionStatus]string{domain.Unmet: "OSV-COMPLETION-001", domain.CriterionUnverified: "OSV-COMPLETION-002", domain.NotRecorded: "OSV-COMPLETION-003", domain.NotApplicable: "OSV-COMPLETION-004"}
		messages := map[domain.CriterionStatus]string{domain.Unmet: "completion.required_unmet", domain.CriterionUnverified: "completion.required_unverified", domain.NotRecorded: "completion.required_not_recorded", domain.NotApplicable: "completion.required_not_applicable"}
		id := ids[g.Status]
		if id == "" {
			id = "OSV-COMPLETION-003"
		}
		message := messages[g.Status]
		if message == "" {
			message = "completion.required_not_recorded"
		}
		add(id, message, "/completion_criteria/"+g.ID)
	}
	if r.CapabilityProfile != nil {
		status := r.CapabilityProfile.Capabilities["completion_candidate_observation"].Status
		if status != domain.CapabilitySupported && status != domain.CapabilityDegraded {
			warning := violation("OSV-CAPABILITY-003", "capability.completion_observation_unavailable", "/capability_profile")
			warning.Severity = "warning"
			v = append(v, warning)
		}
	}
	return stableViolations(v)
}
func VerifyCompletion(r VerificationRequest) VerificationResult {
	started := time.Now()
	result := VerificationResult{Schema: "opensocrates.verification-result/1.0.0", VerifierVersion: "1.0.0", RulesetVersion: "1.0.0", Violations: []Violation{}}
	card := r.Card
	if card == nil && r.Markdown != nil {
		parsed, e := ParseCard(*r.Markdown, r.Locale, r.Messages, r.Context)
		if e == nil {
			card = &parsed
		}
	}
	if card == nil {
		result.Outcome = domain.VerificationError
		result.Violations = []Violation{violation("OSV-CARD-011", "card.parse_failed", "/card")}
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}
	cardRules := CardViolations(*card, r.Markdown)
	privacy := false
	for _, v := range cardRules {
		privacy = privacy || strings.HasPrefix(v.RuleID, "OSV-PRIVACY-")
	}
	criteria := EvaluateCompletionCriteria(r.Framing, len(cardRules) == 0, r.Claims, r.CriterionStatuses, privacy)
	evidence := EvidenceViolations(r.Claims, r.Sources, card.Strength, domain.StrengthOptions{RequiredCriteria: criteria, MissingDecisiveEvidence: r.MissingDecisiveEvidence, Conflicts: r.Conflicts})
	result.Violations = CompletionViolations(*card, r, criteria, append(cardRules, evidence...))
	blocking := 0
	ids := []string{}
	for _, v := range result.Violations {
		if v.Severity == "error" {
			blocking++
		}
		ids = append(ids, v.RuleID)
	}
	outcome, e := domain.CompletionOutcome(criteria, blocking, r.RepairCountBefore)
	if e != nil {
		outcome = domain.VerificationError
	}
	result.Outcome = outcome
	completion, e := domain.BuildCompletionResult(card.JudgmentID, r.CandidateSequence, criteria, ids, blocking, r.RepairCountBefore, &outcome, nil)
	if e != nil {
		result.Outcome = domain.VerificationError
		result.Violations = stableViolations(append(result.Violations, violation("OSV-CAPABILITY-004", "capability.completion_result_failed", "/completion_result")))
	} else {
		result.CompletionResult = &completion
		result.ParsedCard = card
	}
	result.DurationMS = time.Since(started).Milliseconds()
	return result
}
