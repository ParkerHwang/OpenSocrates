package domain

import "github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"

type Rigor string

const (
	Quiet    Rigor = "quiet"
	Together Rigor = "together"
	Strict   Rigor = "strict"
)

type RiskFloorReason string

const (
	RiskNone               RiskFloorReason = "none"
	OrdinaryJudgment       RiskFloorReason = "ordinary_judgment"
	MaterialClaims         RiskFloorReason = "externally_checkable_material_claims"
	MaterialConsequence    RiskFloorReason = "material_consequence"
	IrreversibleCommitment RiskFloorReason = "irreversible_commitment"
	ExplicitStrict         RiskFloorReason = "explicit_user_strict"
)

type RigorDecision struct {
	Schema          string          `json:"schema"`
	Stored          Rigor           `json:"stored_rigor"`
	Override        *Rigor          `json:"task_override"`
	Floor           Rigor           `json:"risk_floor"`
	Reason          RiskFloorReason `json:"risk_reason"`
	Effective       Rigor           `json:"effective_rigor"`
	ShowRaiseNotice bool            `json:"show_raise_notice"`
}

func RigorOrdinal(r Rigor) (int, error) {
	switch r {
	case Quiet:
		return 0, nil
	case Together:
		return 1, nil
	case Strict:
		return 2, nil
	}
	return 0, contracts.ErrInvalid
}
func MaxRigor(values ...Rigor) (Rigor, error) {
	if len(values) == 0 {
		return "", contracts.ErrInvalid
	}
	best := Quiet
	for _, v := range values {
		n, e := RigorOrdinal(v)
		if e != nil {
			return "", e
		}
		b, _ := RigorOrdinal(best)
		if n > b {
			best = v
		}
	}
	return best, nil
}
func EffectiveRigor(stored Rigor, override *Rigor, floor Rigor) (Rigor, error) {
	if _, e := RigorOrdinal(stored); e != nil {
		return "", e
	}
	base := stored
	if override != nil {
		base = *override
	}
	return MaxRigor(base, floor)
}
func BuildRigorDecision(stored Rigor, override *Rigor, floor Rigor, reason RiskFloorReason) (RigorDecision, error) {
	effective, e := EffectiveRigor(stored, override, floor)
	if e != nil {
		return RigorDecision{}, e
	}
	valid := floor == Quiet && reason == RiskNone || floor == Together && (reason == OrdinaryJudgment || reason == MaterialClaims) || floor == Strict && (reason == MaterialConsequence || reason == IrreversibleCommitment || reason == ExplicitStrict)
	if !valid {
		return RigorDecision{}, contracts.ErrInvalid
	}
	base := stored
	if override != nil {
		base = *override
	}
	b, _ := RigorOrdinal(base)
	n, _ := RigorOrdinal(effective)
	return RigorDecision{"opensocrates.rigor-decision/1.0.0", stored, override, floor, reason, effective, n > b}, nil
}
func ValidateRigorDecision(d RigorDecision) error {
	expected, e := BuildRigorDecision(d.Stored, d.Override, d.Floor, d.Reason)
	if e != nil {
		return e
	}
	if d.Schema != expected.Schema || d.Effective != expected.Effective || d.ShowRaiseNotice != expected.ShowRaiseNotice {
		return contracts.ErrInvalid
	}
	return nil
}
