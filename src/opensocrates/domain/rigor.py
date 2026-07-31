"""Raise-only rigor arithmetic.

The policy has one precedence point: a valid one-task override replaces the
stored setting for this task; the deterministic risk floor then raises that
base value when necessary.  No policy branch can lower the selected floor.
"""

from __future__ import annotations

from ..errors import ValidationError
from .enums import Rigor, RiskFloorReason
from .models import RigorDecision

_RIGOR_ORDINAL = {
    Rigor.QUIET: 0,
    Rigor.TOGETHER: 1,
    Rigor.STRICT: 2,
}

_REASONS_BY_FLOOR = {
    Rigor.QUIET: frozenset({RiskFloorReason.NONE}),
    Rigor.TOGETHER: frozenset(
        {
            RiskFloorReason.ORDINARY_JUDGMENT,
            RiskFloorReason.EXTERNALLY_CHECKABLE_MATERIAL_CLAIMS,
        }
    ),
    Rigor.STRICT: frozenset(
        {
            RiskFloorReason.MATERIAL_CONSEQUENCE,
            RiskFloorReason.IRREVERSIBLE_COMMITMENT,
            RiskFloorReason.EXPLICIT_USER_STRICT,
        }
    ),
}


def rigor_ordinal(value: Rigor) -> int:
    """Return the frozen ordinal for a rigor level."""

    if not isinstance(value, Rigor):
        raise ValidationError("rigor: unknown level")
    return _RIGOR_ORDINAL[value]


def max_rigor(*values: Rigor) -> Rigor:
    """Return the greatest rigor level using the v1 ordinal order."""

    if not values:
        raise ValidationError("rigor: at least one level is required")
    if any(not isinstance(value, Rigor) for value in values):
        raise ValidationError("rigor: unknown level")
    return max(values, key=rigor_ordinal)


def effective_rigor(
    stored_rigor: Rigor,
    task_override: Rigor | None,
    risk_floor: Rigor,
) -> Rigor:
    """Compute ``max(stored_or_task_override, risk_floor)`` exactly."""

    if not isinstance(stored_rigor, Rigor) or not isinstance(risk_floor, Rigor):
        raise ValidationError("rigor: stored level and risk floor must be closed levels")
    if task_override is not None and not isinstance(task_override, Rigor):
        raise ValidationError("rigor: task override must be a closed level or null")
    base = task_override if task_override is not None else stored_rigor
    return max_rigor(base, risk_floor)


def build_rigor_decision(
    stored_rigor: Rigor,
    task_override: Rigor | None,
    risk_floor: Rigor,
    risk_reason: RiskFloorReason,
) -> RigorDecision:
    """Construct the closed decision and set the single raise-notice flag."""

    selected = effective_rigor(stored_rigor, task_override, risk_floor)
    if not isinstance(risk_reason, RiskFloorReason):
        raise ValidationError("rigor: unknown risk-floor reason")
    if risk_reason not in _REASONS_BY_FLOOR[risk_floor]:
        raise ValidationError("rigor: risk-floor reason does not match floor")
    decision = RigorDecision(
        stored_rigor=stored_rigor,
        task_override=task_override,
        risk_floor=risk_floor,
        risk_reason=risk_reason,
        effective_rigor=selected,
        show_raise_notice=rigor_ordinal(selected)
        > rigor_ordinal(task_override if task_override is not None else stored_rigor),
    )
    return validate_rigor_decision(decision)


def validate_rigor_decision(decision: RigorDecision) -> RigorDecision:
    """Recompute and validate all derived rigor fields."""

    if not isinstance(decision, RigorDecision):
        raise ValidationError("rigor decision: expected RigorDecision")
    if decision.risk_reason not in _REASONS_BY_FLOOR[decision.risk_floor]:
        raise ValidationError("rigor decision: risk-floor reason does not match floor")
    expected = effective_rigor(decision.stored_rigor, decision.task_override, decision.risk_floor)
    if decision.effective_rigor is not expected:
        raise ValidationError("rigor decision: effective level is not the raise-only maximum")
    requested = (
        decision.task_override if decision.task_override is not None else decision.stored_rigor
    )
    expected_notice = rigor_ordinal(expected) > rigor_ordinal(requested)
    if decision.show_raise_notice is not expected_notice:
        raise ValidationError(
            "rigor decision: raise notice must be emitted at most once when raised"
        )
    return decision


# Names used by application ports and older policy callers.
decide_rigor = build_rigor_decision
compute_effective_rigor = effective_rigor
validate_rigor = validate_rigor_decision


__all__ = [
    "build_rigor_decision",
    "compute_effective_rigor",
    "decide_rigor",
    "effective_rigor",
    "max_rigor",
    "rigor_ordinal",
    "validate_rigor",
    "validate_rigor_decision",
]
