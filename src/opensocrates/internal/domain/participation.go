package domain

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"golang.org/x/text/unicode/norm"
	"strings"
	"unicode/utf8"
)

type Participation string

const (
	Mechanical Participation = "mechanical"
	Judgment   Participation = "judgment"
	Mixed      Participation = "mixed"
)

type ParticipationDecision struct {
	Schema            string        `json:"schema"`
	Participation     Participation `json:"participation"`
	Reason            string        `json:"reason_code"`
	JudgmentTargets   []string      `json:"judgment_targets"`
	MechanicalTargets []string      `json:"mechanical_targets"`
	ConfidenceBasis   string        `json:"confidence_basis"`
	ExplicitMethod    *string       `json:"explicit_method"`
}
type ParticipationSignals struct {
	HasJudgmentTarget   bool
	HasMechanicalTarget bool
	JudgmentTargets     []string
	MechanicalTargets   []string
	ExplicitMethod      *string
	Reason              string
}

var mechanicalReasons = []string{"direct_transformation", "direct_artifact_action", "direct_retrieval", "explicit_method_without_judgment"}
var judgmentReasons = []string{"judgment_choice", "judgment_diagnosis", "judgment_evidence", "judgment_risk", "judgment_completion", "explicit_method_with_judgment"}
var mixedReasons = []string{"judgment_then_artifact", "artifact_with_judgment_segment", "explicit_method_with_judgment"}

func publicText(s string, max int) bool {
	if !utf8.ValidString(s) || !norm.NFC.IsNormalString(s) || strings.TrimSpace(s) == "" || utf8.RuneCountInString(s) > max {
		return false
	}
	for _, r := range s {
		if (r < 32 && r != '\n' && r != '\t') || r == 127 {
			return false
		}
	}
	return true
}
func ClassifyParticipation(s ParticipationSignals) (ParticipationDecision, error) {
	j := s.HasJudgmentTarget || len(s.JudgmentTargets) > 0
	m := s.HasMechanicalTarget || len(s.MechanicalTargets) > 0
	d := ParticipationDecision{Schema: "opensocrates.participation-decision/1.0.0", JudgmentTargets: append([]string{}, s.JudgmentTargets...), MechanicalTargets: append([]string{}, s.MechanicalTargets...), ConfidenceBasis: "rule_plus_model_policy", ExplicitMethod: s.ExplicitMethod, Reason: s.Reason}
	switch {
	case j && m:
		d.Participation = Mixed
		if d.Reason == "" {
			d.Reason = "judgment_then_artifact"
		}
	case j:
		d.Participation = Judgment
		if d.Reason == "" {
			d.Reason = "judgment_choice"
		}
	default:
		d.Participation = Mechanical
		if d.Reason == "" {
			d.Reason = "direct_transformation"
		}
	}
	if d.ExplicitMethod != nil {
		if j {
			d.Reason = "explicit_method_with_judgment"
		} else {
			d.Reason = "explicit_method_without_judgment"
		}
	}
	if len(d.JudgmentTargets) == 0 && s.HasJudgmentTarget {
		d.JudgmentTargets = []string{"judgment target"}
	}
	if len(d.MechanicalTargets) == 0 && s.HasMechanicalTarget {
		d.MechanicalTargets = []string{"mechanical target"}
	}
	return d, ValidateParticipationDecision(d)
}
func ValidateParticipationDecision(d ParticipationDecision) error {
	if d.Schema != "opensocrates.participation-decision/1.0.0" || d.ConfidenceBasis != "rule_plus_model_policy" || len(d.JudgmentTargets) > 3 || len(d.MechanicalTargets) > 3 {
		return contracts.ErrInvalid
	}
	for _, s := range append(append([]string{}, d.JudgmentTargets...), d.MechanicalTargets...) {
		if !publicText(s, 120) {
			return contracts.ErrInvalid
		}
	}
	j := len(d.JudgmentTargets) > 0
	m := len(d.MechanicalTargets) > 0
	switch d.Participation {
	case Mechanical:
		if j || !Has(mechanicalReasons, d.Reason) {
			return contracts.ErrInvalid
		}
	case Judgment:
		if !j || !Has(judgmentReasons, d.Reason) {
			return contracts.ErrInvalid
		}
	case Mixed:
		if !j || !m || !Has(mixedReasons, d.Reason) {
			return contracts.ErrInvalid
		}
	default:
		return contracts.ErrInvalid
	}
	if d.ExplicitMethod != nil {
		if !MethodID(*d.ExplicitMethod) || j && d.Reason != "explicit_method_with_judgment" || !j && d.Reason != "explicit_method_without_judgment" {
			return contracts.ErrInvalid
		}
	} else if d.Reason == "explicit_method_with_judgment" || d.Reason == "explicit_method_without_judgment" {
		return contracts.ErrInvalid
	}
	return nil
}
