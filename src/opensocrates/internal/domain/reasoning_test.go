package domain

import (
	"strings"
	"testing"
)

func ptr[T any](v T) *T { return &v }
func TestRiskPrecedenceAndMechanicalRestraint(t *testing.T) {
	tests := []struct {
		p      Participation
		s      RiskSignals
		floor  Rigor
		reason RiskFloorReason
	}{{Mechanical, RiskSignals{ExplicitUserStrict: true, MaterialConsequence: true}, Quiet, RiskNone}, {Judgment, RiskSignals{}, Together, OrdinaryJudgment}, {Mixed, RiskSignals{ExplicitUserStrict: true, MaterialConsequence: true}, Strict, ExplicitStrict}, {Judgment, RiskSignals{MaterialConsequence: true, IrreversibleCommitment: true}, Strict, MaterialConsequence}, {Judgment, RiskSignals{IrreversibleCommitment: true}, Strict, IrreversibleCommitment}, {Judgment, RiskSignals{OrdinaryJudgment: ptr(false), ExternallyCheckableMaterialClaims: true}, Together, MaterialClaims}, {Judgment, RiskSignals{OrdinaryJudgment: ptr(false)}, Quiet, RiskNone}}
	for _, tt := range tests {
		f, r, e := ComputeRiskFloor(tt.p, tt.s)
		if e != nil || f != tt.floor || r != tt.reason {
			t.Fatalf("%+v: %v %v %v", tt, f, r, e)
		}
	}
	d, e := BuildRigorDecision(Strict, ptr(Quiet), Together, OrdinaryJudgment)
	if e != nil || d.Effective != Together || !d.ShowRaiseNotice {
		t.Fatal(d, e)
	}
	d.ShowRaiseNotice = false
	if ValidateRigorDecision(d) == nil {
		t.Fatal("accepted forged raise notice")
	}
}
func TestParticipationExplicitMethodCannotCreateJudgment(t *testing.T) {
	d, e := ClassifyParticipation(ParticipationSignals{ExplicitMethod: ptr("critical-thinking")})
	if e != nil || d.Participation != Mechanical || d.Reason != "explicit_method_without_judgment" {
		t.Fatal(d, e)
	}
	d, e = ClassifyParticipation(ParticipationSignals{HasJudgmentTarget: true, HasMechanicalTarget: true, ExplicitMethod: ptr("critical-thinking"), Reason: "direct_transformation"})
	if e != nil || d.Participation != Mixed || d.Reason != "explicit_method_with_judgment" || len(d.JudgmentTargets) != 1 {
		t.Fatal(d, e)
	}
	if _, e = ClassifyParticipation(ParticipationSignals{JudgmentTargets: []string{strings.Repeat("한", 121)}}); e == nil {
		t.Fatal("accepted oversized Unicode target")
	}
}
func TestCompletionRequiredGapsNeverPass(t *testing.T) {
	for _, s := range []CriterionStatus{Unmet, CriterionUnverified, NotRecorded, NotApplicable, ""} {
		criteria := []CompletionCriterion{{ID: "K1", Status: s, Reason: "Check", Required: true}}
		o, e := CompletionOutcome(criteria, 0, 0)
		if e != nil || o != Insufficient {
			t.Fatal(s, o, e)
		}
		requested := Pass
		r, e := BuildCompletionResult("J1", 1, criteria, nil, 0, 0, &requested, nil)
		if e != nil || r.Outcome != Insufficient || r.MayContinue {
			t.Fatal(r, e)
		}
	}
	met := []CompletionCriterion{{ID: "K1", Status: Met, Reason: "Check", Required: true}}
	for n, want := range []VerificationOutcome{Repair, Degraded} {
		o, e := CompletionOutcome(met, 1, n)
		if e != nil || o != want {
			t.Fatal(o, e)
		}
	}
	if AllRequiredCriteriaMet(nil) {
		t.Fatal("empty framing passed")
	}
}
func claim(id string, state EvidenceState) ClaimVersion {
	c := ClaimVersion{ID: id, Version: 1, Text: "A public ground", Materiality: "material", EvidenceState: state, Active: true, SourceIDs: []string{}, BasisClaimIDs: []string{}}
	if state == Verified {
		c.SourceIDs = []string{"E1"}
	}
	if state == Inferred {
		c.BasisClaimIDs = []string{"C1"}
	}
	return c
}
func TestClaimShapeHistoryAndStrength(t *testing.T) {
	c := claim("C1", Verified)
	retired, next, e := ReviseClaim(c, claim("C1", Assumed))
	if e != nil || retired.Active || next.Version != 2 || !c.Active {
		t.Fatal(retired, next, e)
	}
	current, e := CurrentClaims([]ClaimVersion{next, retired})
	if e != nil || current["C1"].Version != 2 {
		t.Fatal(current, e)
	}
	retired.Active = true
	if _, e = CurrentClaims([]ClaimVersion{retired, next}); e == nil {
		t.Fatal("multiple active claims accepted")
	}
	weak := claim("C1", Assumed)
	assessment, e := AssessStrengthEligibility([]ClaimVersion{weak}, Provisional, StrengthOptions{})
	if e != nil || !assessment.Eligible {
		t.Fatal(assessment, e)
	}
	assessment, e = AssessStrengthEligibility([]ClaimVersion{weak}, Supported, StrengthOptions{})
	if e != nil || assessment.Eligible {
		t.Fatal(assessment, e)
	}
	strong := claim("C1", Verified)
	assessment, e = AssessStrengthEligibility([]ClaimVersion{strong}, StronglySupported, StrengthOptions{RequiredCriteria: []CompletionCriterion{{ID: "K1", Status: NotRecorded, Required: true}}})
	if e != nil || assessment.Eligible {
		t.Fatal(assessment, e)
	}
}
func TestConflictResolutionStillRequiresNewVersion(t *testing.T) {
	reason := "New source corrects the definition"
	c := Conflict{Material: true, Resolution: "measurement_definition", ResolutionReason: &reason}
	a, e := AssessConflict(c, nil, true, false)
	if e != nil || a.Action != "revise_required" || !a.RequiresNewVersion || !a.Blocking {
		t.Fatal(a, e)
	}
	c.ResolutionReason = nil
	a, e = AssessConflict(c, nil, true, false)
	if e != nil || a.Action != "hold_required" {
		t.Fatal(a, e)
	}
	j := JudgmentVersion{JudgmentID: "J1", Version: 1, State: "active", Strength: Supported}
	next, e := HoldJudgmentVersion(j, "A conflict remains")
	if e != nil || next.Version != 2 || next.Strength != Held || j.Version != 1 {
		t.Fatal(next, e)
	}
	if _, e := PreserveJudgmentVersion(j, next); e != nil {
		t.Fatal(e)
	}
}
func TestAlternativeAndFlipPolicies(t *testing.T) {
	a := Alternative{ID: "A1", Name: "Use option", Disposition: "selected", Reason: "Meets objective"}
	r := AssessAlternativeSufficiency([]Alternative{a}, AlternativeRequirement{ChoiceRequired: true})
	if r.Status != "missing_non_selected" {
		t.Fatal(r)
	}
	r = AssessAlternativeSufficiency([]Alternative{a}, AlternativeRequirement{ChoiceRequired: true, GenuineBinary: true, NoAlternativeJustification: ptr("Only the binding option exists")})
	if r.Status != "justified_binary" {
		t.Fatal(r)
	}
	if ObservableFlipText("if new information emerges") {
		t.Fatal("vague condition accepted")
	}
	f := FlipCondition{Condition: "If cost exceeds 20 USD", Check: "Obtain a supplier quote", Direction: "reverse"}
	if e := ValidateFlipConditions([]FlipCondition{f, f}); e == nil {
		t.Fatal("duplicate flip accepted")
	}
}
func TestCapabilityUnknownCannotSupportTier(t *testing.T) {
	c := map[string]CapabilityEntry{}
	for _, key := range CapabilityKeys {
		c[key] = CapabilityEntry{Status: CapabilitySupported}
	}
	c["rich_card_widget"] = CapabilityEntry{Status: CapabilityUnavailable}
	tier, e := DeriveCapabilityTier(c)
	if e != nil || tier != "A" {
		t.Fatal(tier, e)
	}
	for _, key := range CapabilityKeys {
		c[key] = CapabilityEntry{Status: CapabilityUnknown}
	}
	tier, e = DeriveCapabilityTier(c)
	if e != nil || tier != "unsupported" {
		t.Fatal(tier, e)
	}
	c["method_skill_invocation"] = CapabilityEntry{Status: CapabilityDegraded}
	tier, e = DeriveCapabilityTier(c)
	if e != nil || tier != "C" {
		t.Fatal(tier, e)
	}
}
func TestObservationEmptyFailureAndDedupe(t *testing.T) {
	tag := "sha256:" + strings.Repeat("0", 64)
	m := ObservationMetadata{ActiveTaskTag: tag, ToolUseKey: tag, WindowTag: tag, SubjectTag: tag, ToolCategory: "search", ResultSizeBucket: "empty", ResultStatus: "failed", OccurredAt: "2026-10-12T00:00:00Z", RecordingEligible: true}
	task := TaskObservationContext{State: TaskWorking, CurrentJudgmentID: ptr("J1")}
	d, e := AssessObservation(m, &task, ObservationDedupeState{}, nil, "weak_evidence")
	if e != nil || d.Action != "inject" {
		t.Fatal(d, e)
	}
	duplicate, e := AssessObservation(m, &task, ObservationDedupeState{Fingerprints: d.NextFingerprints}, nil, "weak_evidence")
	if e != nil || duplicate.Reason != "duplicate" {
		t.Fatal(duplicate, e)
	}
	m.ResultStatus = "succeeded"
	empty, e := AssessObservation(m, &task, ObservationDedupeState{}, nil, "weak_evidence")
	if e != nil || empty.Reason != "empty_result" {
		t.Fatal(empty, e)
	}
}
func TestStrictPacketBlindnessAndReconciliation(t *testing.T) {
	a := Alternative{ID: "A1", Name: "Option one", Reason: "Fits the public criterion", Disposition: "selected"}
	p, e := BuildStrictPacket("Which option?", "Compare the cost", []ClaimVersion{claim("C1", Verified)}, []Alternative{a}, nil, ptr("The selected option is one"), []string{"A1"})
	if e != nil || p.PacketTag == nil || len(p.Alternatives) != 1 {
		t.Fatal(p, e)
	}
	if _, e := BuildStrictPacket("Which option?", "The selected alternative is one", nil, nil, nil, nil, nil); e == nil {
		t.Fatal("selection leaked")
	}
	first := StrictPassResult{Outcome: "select", PublicSummary: "Option one fits", Strength: Supported, SelectedAlternativeID: ptr("A1")}
	second := first
	second.SelectedAlternativeID = ptr("A2")
	c, e := CompareStrictPasses(first, second, nil, nil)
	if e != nil || c.CanComplete() || c.NextAction != "reconcile" {
		t.Fatal(c, e)
	}
	c, e = CompareStrictPasses(first, second, nil, &StrictReconciliation{Action: "hold", PublicSummary: "The alternatives need another check"})
	if e != nil || !c.CanComplete() || c.NextAction != "hold" {
		t.Fatal(c, e)
	}
}
func TestMetricsClosedAndRecordingOff(t *testing.T) {
	m, e := BuildLocalMetric("card_rendered", "codex_cli", "ko", Together, MetricAttributes{}, "2026-10-12", "1.6.0", nil, false, nil)
	if e != nil || m != nil {
		t.Fatal(m, e)
	}
	if e := ValidateMetricAttributes("rigor_changed", MetricAttributes{FromRigor: ptr(Quiet)}); e == nil {
		t.Fatal("missing required to_rigor accepted")
	}
	for _, tt := range []struct {
		n      float64
		bucket string
	}{{49.9, "under_50"}, {50, "50_99"}, {100, "100_249"}, {250, "250_999"}, {1000, "1000_plus"}} {
		b, e := DurationBucket(&tt.n)
		if e != nil || *b != tt.bucket {
			t.Fatal(b, e)
		}
	}
}
func TestStateTransitionsDoNotResurrectTerminalTasks(t *testing.T) {
	if LegalEvent("claim_published", TaskConcluded) {
		t.Fatal("terminal write accepted")
	}
	if !LegalEvent("recovered_from_torn_tail", TaskConcluded) {
		t.Fatal("recovery annotation rejected")
	}
	s, e := TransitionState(TaskWorking, "conflict_published", TransitionInput{})
	if e != nil || s != TaskRejudging {
		t.Fatal(s, e)
	}
	s, e = TransitionState(TaskVerifying, "task_concluded", TransitionInput{TerminalReason: "capability_missing"})
	if e != nil || s != TaskDegraded {
		t.Fatal(s, e)
	}
}
