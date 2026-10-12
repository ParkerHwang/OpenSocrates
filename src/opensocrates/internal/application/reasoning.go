package application

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"strings"
)

type ClaimVersionHistory struct {
	Prior   domain.ClaimVersion
	Current domain.ClaimVersion
}
type RejudgeRequest struct {
	CurrentVersion domain.JudgmentVersion
	Conflict       domain.Conflict
	Signals        *domain.ConflictSignals
	RevisedVersion *domain.JudgmentVersion
	CurrentClaims  []domain.ClaimVersion
	RevisedClaims  []domain.ClaimVersion
	HoldReason     *string
	HoldRequested  bool
}
type RejudgeResult struct {
	Action           string
	Assessment       domain.ConflictAssessment
	Conflict         domain.Conflict
	PriorVersion     domain.JudgmentVersion
	SuccessorVersion *domain.JudgmentVersion
	History          *domain.JudgmentVersionHistory
	PriorClaims      []domain.ClaimVersion
	ClaimHistories   []ClaimVersionHistory
	RecordConflict   bool
	RecordResolution bool
}

func PlanRejudgment(r RejudgeRequest) (RejudgeResult, error) {
	result := RejudgeResult{Conflict: r.Conflict, PriorVersion: r.CurrentVersion, PriorClaims: append([]domain.ClaimVersion{}, r.CurrentClaims...), ClaimHistories: []ClaimVersionHistory{}}
	if r.HoldReason != nil && !domain.StrictPublicText(*r.HoldReason, 500) {
		return result, contracts.ErrInvalid
	}
	current := map[string]domain.ClaimVersion{}
	for _, c := range r.CurrentClaims {
		if _, ok := current[c.ID]; ok {
			return result, contracts.ErrInvalid
		}
		current[c.ID] = c
	}
	seen := map[string]bool{}
	for _, c := range r.RevisedClaims {
		if seen[c.ID] {
			return result, contracts.ErrInvalid
		}
		seen[c.ID] = true
	}
	assessment, e := domain.AssessConflict(r.Conflict, r.Signals, r.RevisedVersion != nil, r.HoldRequested)
	if e != nil {
		return result, e
	}
	result.Assessment = assessment
	result.RecordConflict = assessment.Public
	result.RecordResolution = assessment.ResolutionRecorded
	if !assessment.Material {
		result.Action = "public_conflict"
		return result, nil
	}
	var successor domain.JudgmentVersion
	if assessment.Action == "revise_required" && r.RevisedVersion != nil {
		if r.RevisedVersion.State != "revised" {
			return result, contracts.ErrInvalid
		}
		successor = *r.RevisedVersion
		result.Action = "revise"
		for _, c := range r.RevisedClaims {
			prior, ok := current[c.ID]
			if !ok {
				return result, contracts.ErrInvalid
			}
			if e := domain.PreserveClaimVersion(prior, c); e != nil {
				return result, e
			}
			result.ClaimHistories = append(result.ClaimHistories, ClaimVersionHistory{prior, c})
		}
	} else {
		reason := "A material conflict requires a visible hold before completion."
		if r.HoldReason != nil {
			reason = *r.HoldReason
		} else if strings.TrimSpace(r.Conflict.Summary) != "" && len([]rune(strings.TrimSpace(r.Conflict.Summary))) <= 500 {
			reason = strings.TrimSpace(r.Conflict.Summary)
		}
		successor, e = domain.HoldJudgmentVersion(r.CurrentVersion, reason)
		if e != nil {
			return result, e
		}
		result.Action = "hold"
	}
	history, e := domain.PreserveJudgmentVersion(r.CurrentVersion, successor)
	if e != nil {
		return result, e
	}
	result.SuccessorVersion = &successor
	result.History = &history
	result.RecordConflict = true
	return result, nil
}

type CrossExamInput struct {
	StrongestObjection     string
	WeakestLink            string
	OmittedAlternative     string
	StaleRisk              string
	FlipConditions         []domain.FlipCondition
	Alternatives           []domain.Alternative
	AlternativeRequirement *domain.AlternativeRequirement
	CompletionComplete     bool
	AffectedIDs            []string
}
type CrossExamResult struct {
	StrongestObjection     string
	WeakestLink            string
	OmittedAlternative     string
	StaleRisk              string
	FlipConditions         []domain.FlipCondition
	AlternativeSufficiency domain.AlternativeSufficiency
	CompletionComplete     bool
	CompletionReady        bool
	BlockingReasons        []string
	AffectedIDs            []string
	PublicSummary          string
}

func publicFinding(s string, max int) bool {
	if !domain.StrictPublicText(s, max) {
		return false
	}
	lower := strings.ToLower(s)
	for _, marker := range []string{"chain of thought", "hidden reasoning", "private reasoning", "private thought", "scratchpad", "internal reasoning"} {
		if strings.Contains(lower, marker) {
			return false
		}
	}
	return true
}
func RunCrossExam(r CrossExamInput) (CrossExamResult, error) {
	result := CrossExamResult{}
	if r.StaleRisk == "" {
		r.StaleRisk = "The conclusion may be stale if a material ground changed."
	}
	for _, s := range []string{r.StrongestObjection, r.WeakestLink, r.OmittedAlternative, r.StaleRisk} {
		if !publicFinding(s, 400) {
			return result, contracts.ErrInvalid
		}
	}
	if len(r.FlipConditions) == 0 || len(r.AffectedIDs) > 12 || len(r.Alternatives) > 3 {
		return result, contracts.ErrInvalid
	}
	if e := domain.ValidateFlipConditions(r.FlipConditions); e != nil {
		return result, e
	}
	for _, id := range r.AffectedIDs {
		if !publicFinding(id, 32) {
			return result, contracts.ErrInvalid
		}
	}
	requirement := domain.AlternativeRequirement{}
	if r.AlternativeRequirement != nil {
		requirement = *r.AlternativeRequirement
	}
	sufficiency := domain.AssessAlternativeSufficiency(r.Alternatives, requirement)
	blocking := []string{}
	if !domain.Has([]string{"not_required", "sufficient", "justified_binary"}, sufficiency.Status) {
		blocking = append(blocking, "missing_alternative")
	}
	if !r.CompletionComplete {
		blocking = append(blocking, "completion_gap")
	}
	summary := strings.Join([]string{"Strongest objection: " + r.StrongestObjection, "Weakest link: " + r.WeakestLink, "Omitted alternative: " + r.OmittedAlternative, "Stale-risk check: " + r.StaleRisk}, "\n")
	if len([]rune(summary)) > 1000 {
		summary = string([]rune(summary)[:1000])
	}
	if !publicFinding(summary, 1000) {
		return result, contracts.ErrInvalid
	}
	return CrossExamResult{r.StrongestObjection, r.WeakestLink, r.OmittedAlternative, r.StaleRisk, append([]domain.FlipCondition{}, r.FlipConditions...), sufficiency, r.CompletionComplete, len(blocking) == 0, blocking, append([]string{}, r.AffectedIDs...), summary}, nil
}

type StrictPassRequest struct {
	Packet             domain.StrictPacket
	PromptFragmentID   string
	SameHostSecondPass bool
}
type StrictPassApplicationResult struct {
	Request    StrictPassRequest
	SecondPass domain.StrictPassResult
	Comparison domain.StrictComparison
}

func PrepareStrictPass(packet domain.StrictPacket) (StrictPassRequest, error) {
	if e := domain.ValidateStrictPacket(packet); e != nil {
		return StrictPassRequest{}, e
	}
	if !packet.SameHostSecondPass {
		return StrictPassRequest{}, contracts.ErrInvalid
	}
	return StrictPassRequest{packet, "strict_second_pass", true}, nil
}
func CompleteStrictPass(request StrictPassRequest, first, second domain.StrictPassResult, firstSelectedID *string, reconciliation *domain.StrictReconciliation) (StrictPassApplicationResult, error) {
	if request.PromptFragmentID != "strict_second_pass" || !request.SameHostSecondPass || !request.Packet.SameHostSecondPass {
		return StrictPassApplicationResult{}, contracts.ErrInvalid
	}
	comparison, e := domain.CompareStrictPasses(first, second, firstSelectedID, reconciliation)
	if e != nil {
		return StrictPassApplicationResult{}, e
	}
	return StrictPassApplicationResult{request, second, comparison}, nil
}
