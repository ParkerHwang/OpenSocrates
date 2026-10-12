package domain

import "github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"

type RiskSignals struct {
	OrdinaryJudgment                  *bool `json:"ordinary_judgment"`
	ExternallyCheckableMaterialClaims bool  `json:"externally_checkable_material_claims"`
	MaterialConsequence               bool  `json:"material_consequence"`
	IrreversibleCommitment            bool  `json:"irreversible_commitment"`
	ExplicitUserStrict                bool  `json:"explicit_user_strict"`
}

func ComputeRiskFloor(participation Participation, s RiskSignals) (Rigor, RiskFloorReason, error) {
	if participation != Mechanical && participation != Judgment && participation != Mixed {
		return "", "", contracts.ErrInvalid
	}
	if participation == Mechanical {
		return Quiet, RiskNone, nil
	}
	if s.ExplicitUserStrict {
		return Strict, ExplicitStrict, nil
	}
	if s.MaterialConsequence {
		return Strict, MaterialConsequence, nil
	}
	if s.IrreversibleCommitment {
		return Strict, IrreversibleCommitment, nil
	}
	if s.OrdinaryJudgment == nil || *s.OrdinaryJudgment {
		return Together, OrdinaryJudgment, nil
	}
	if s.ExternallyCheckableMaterialClaims {
		return Together, MaterialClaims, nil
	}
	return Quiet, RiskNone, nil
}
func RigorFromRisk(stored Rigor, override *Rigor, p Participation, s RiskSignals) (RigorDecision, error) {
	floor, reason, e := ComputeRiskFloor(p, s)
	if e != nil {
		return RigorDecision{}, e
	}
	return BuildRigorDecision(stored, override, floor, reason)
}
