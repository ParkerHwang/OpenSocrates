"""Deterministic risk-floor policy.

Risk cues are semantic closed booleans supplied by the host-model policy.  The
runtime does not classify a legal, medical, employment, or financial matter;
it only applies the frozen product floor and reason precedence.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ValidationError
from .enums import Participation, Rigor, RiskFloorReason
from .models import RigorDecision
from .rigor import build_rigor_decision


@dataclass(frozen=True, slots=True)
class RiskSignals:
    """Closed risk cues used by the pure floor function.

    ``ordinary_judgment=None`` means derive the ordinary floor from
    participation.  A caller may explicitly set it to ``False`` when a
    judgment segment is deliberately outside the ordinary recommendation/
    comparison/diagnosis class.
    """

    ordinary_judgment: bool | None = None
    externally_checkable_material_claims: bool = False
    material_consequence: bool = False
    irreversible_commitment: bool = False
    explicit_user_strict: bool = False

    def __post_init__(self) -> None:
        if self.ordinary_judgment is not None and not isinstance(self.ordinary_judgment, bool):
            raise ValidationError("risk signals: ordinary_judgment must be boolean or null")
        for name in (
            "externally_checkable_material_claims",
            "material_consequence",
            "irreversible_commitment",
            "explicit_user_strict",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValidationError(f"risk signals: {name} must be boolean")


RiskInputs = RiskSignals


def compute_risk_floor(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    participation: Participation,
    *,
    ordinary_judgment: bool | None = None,
    externally_checkable_material_claims: bool | None = None,
    material_consequence: bool | None = None,
    irreversible_commitment: bool | None = None,
    explicit_user_strict: bool | None = None,
    signals: RiskSignals | None = None,
) -> tuple[Rigor, RiskFloorReason]:
    """Return the exact risk floor and its highest-priority reason.

    Precedence is, from highest to lowest: mechanical restraint, explicit
    user strict, material consequence, irreversible commitment, ordinary
    judgment, externally checkable material claims, and no floor.  The first
    branch is a hard gate: mechanical work never receives a risk-driven
    engagement floor.
    """

    if not isinstance(participation, Participation):
        raise ValidationError("risk floor: unknown participation")
    if signals is not None:
        if not isinstance(signals, RiskSignals):
            raise ValidationError("risk floor: signals must be RiskSignals")
        if any(
            value is not None
            for value in (
                ordinary_judgment,
                externally_checkable_material_claims,
                material_consequence,
                irreversible_commitment,
                explicit_user_strict,
            )
        ):
            raise ValidationError("risk floor: use signals or keyword cues, not both")
        cues = signals
    else:
        cues = RiskSignals(
            ordinary_judgment=ordinary_judgment,
            externally_checkable_material_claims=bool(externally_checkable_material_claims),
            material_consequence=bool(material_consequence),
            irreversible_commitment=bool(irreversible_commitment),
            explicit_user_strict=bool(explicit_user_strict),
        )

    if participation is Participation.MECHANICAL:
        return Rigor.QUIET, RiskFloorReason.NONE

    ordinary = cues.ordinary_judgment
    if ordinary is None:
        ordinary = True

    if cues.explicit_user_strict:
        return Rigor.STRICT, RiskFloorReason.EXPLICIT_USER_STRICT
    if cues.material_consequence:
        return Rigor.STRICT, RiskFloorReason.MATERIAL_CONSEQUENCE
    if cues.irreversible_commitment:
        return Rigor.STRICT, RiskFloorReason.IRREVERSIBLE_COMMITMENT
    if ordinary:
        return Rigor.TOGETHER, RiskFloorReason.ORDINARY_JUDGMENT
    if cues.externally_checkable_material_claims:
        return Rigor.TOGETHER, RiskFloorReason.EXTERNALLY_CHECKABLE_MATERIAL_CLAIMS
    return Rigor.QUIET, RiskFloorReason.NONE


def risk_floor(
    participation: Participation,
    *,
    signals: RiskSignals | None = None,
    **cues: bool | None,
) -> Rigor:
    """Return only the floor level for callers that do not need the reason."""

    return compute_risk_floor(participation, signals=signals, **cues)[0]


def risk_floor_reason(
    participation: Participation,
    *,
    signals: RiskSignals | None = None,
    **cues: bool | None,
) -> RiskFloorReason:
    """Return only the exact closed reason for the computed floor."""

    return compute_risk_floor(participation, signals=signals, **cues)[1]


def build_rigor_from_risk(
    stored_rigor: Rigor,
    task_override: Rigor | None,
    participation: Participation,
    *,
    signals: RiskSignals | None = None,
    **cues: bool | None,
) -> RigorDecision:
    """Compute the floor and construct the raise-only rigor decision."""

    floor, reason = compute_risk_floor(participation, signals=signals, **cues)
    return build_rigor_decision(stored_rigor, task_override, floor, reason)


# Stable aliases for application-facing policy ports.
decide_risk_floor = compute_risk_floor
decide_rigor_from_risk = build_rigor_from_risk


__all__ = [
    "RiskFloorReason",
    "RiskInputs",
    "RiskSignals",
    "build_rigor_from_risk",
    "compute_risk_floor",
    "decide_risk_floor",
    "decide_rigor_from_risk",
    "risk_floor",
    "risk_floor_reason",
]
