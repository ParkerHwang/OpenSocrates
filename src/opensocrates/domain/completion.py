"""Pure completion-criterion and outcome policy.

This module deliberately knows nothing about Markdown, hosts, persistence, or
locale text.  It turns already-public criterion observations into the closed
completion result used by the verifier and Stop boundary.  A required
criterion is satisfied only by the explicit ``met`` status; every other status
is a gap, including ``not_recorded`` and ``not_applicable``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..errors import ValidationError
from .enums import CriterionStatus, VerificationOutcome
from .models import CompletionCriterion, CompletionResult

MAX_COMPLETION_CRITERIA = 8


@dataclass(frozen=True, slots=True)
class RequiredCriterionGap:
    """A bounded, presentation-neutral description of one required gap."""

    criterion_id: str
    status: CriterionStatus | None
    reason: str


def _status(value: object) -> CriterionStatus | None:
    if value is None:
        return None
    if isinstance(value, CriterionStatus):
        return value
    try:
        return CriterionStatus(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _required(value: object) -> bool:
    return bool(value)


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def criterion_is_met(criterion: object) -> bool:
    """Return whether one criterion can satisfy completion.

    This intentionally does not infer truth from a missing or malformed
    status.  ``met`` is the sole passing status for required criteria.
    """

    if not _required(_field(criterion, "required", True)):
        return True
    return _status(_field(criterion, "status")) is CriterionStatus.MET


def criterion_blocks_pass(criterion: object) -> bool:
    """Return whether one criterion is a required completion blocker."""

    return _required(_field(criterion, "required", True)) and not criterion_is_met(criterion)


def _gap_reason(status: CriterionStatus | None) -> str:
    return {
        CriterionStatus.UNMET: "Required criterion is not met.",
        CriterionStatus.UNVERIFIED: "Required criterion is not verified.",
        CriterionStatus.NOT_RECORDED: "Required criterion was not recorded.",
        CriterionStatus.NOT_APPLICABLE: "Required criterion cannot be not applicable.",
        None: "Required criterion has no recorded status.",
    }.get(status, "Required criterion is not met.")


def required_criterion_gaps(criteria: Iterable[object]) -> tuple[RequiredCriterionGap, ...]:
    """Return all required criteria that are not explicitly met.

    Order follows the input framing order.  Duplicate criterion IDs are kept
    because the caller must be able to see that the framing itself is invalid;
    the verifier may add a separate structural violation for duplicates.
    """

    gaps: list[RequiredCriterionGap] = []
    for item in tuple(criteria):
        if not _required(_field(item, "required", True)):
            continue
        criterion_id = str(_field(item, "criterion_id", ""))
        status = _status(_field(item, "status"))
        if status is not CriterionStatus.MET:
            gaps.append(
                RequiredCriterionGap(
                    criterion_id=criterion_id,
                    status=status,
                    reason=_gap_reason(status),
                )
            )
    return tuple(gaps)


def all_required_criteria_met(criteria: Iterable[object]) -> bool:
    """Return true only when at least one required criterion exists and all pass."""

    items = tuple(criteria)
    required = tuple(item for item in items if _required(_field(item, "required", True)))
    return bool(required) and not required_criterion_gaps(required)


def _normalize_criterion(item: object, index: int) -> CompletionCriterion:
    criterion_id = _field(item, "criterion_id")
    if not isinstance(criterion_id, str) or not criterion_id:
        raise ValidationError(f"completion criterion {index} has no criterion_id")
    required = _required(_field(item, "required", True))
    status = _status(_field(item, "status"))
    if status is None:
        status = CriterionStatus.NOT_RECORDED
    raw_reason = _field(item, "reason")
    raw_text = _field(item, "text")
    if isinstance(raw_reason, str) and raw_reason.strip():
        reason = raw_reason
    elif isinstance(raw_text, str) and raw_text.strip():
        # Framing text is already public/injected; it is safer than creating
        # locale-bound prose in this pure domain layer.
        reason = raw_text
    else:
        reason = criterion_id
    # CompletionCriterion's scalar validator enforces the 400-scalar bound;
    # this explicit check keeps the policy deterministic before construction.
    if len(reason) > 400:
        reason = reason[:400]
    return CompletionCriterion(
        criterion_id=criterion_id,
        status=status,
        reason=reason,
        required=required,
    )


def normalize_criteria(criteria: Iterable[object]) -> tuple[CompletionCriterion, ...]:
    """Convert framing/evaluated criterion values to CompletionCriterion objects."""

    items = tuple(criteria)
    if len(items) > MAX_COMPLETION_CRITERIA:
        raise ValidationError("completion criteria exceed the bounded limit")
    return tuple(_normalize_criterion(item, index) for index, item in enumerate(items))


def completion_outcome(
    criteria: Iterable[object],
    *,
    blocking_violation_count: int = 0,
    repair_count_before: int = 0,
    has_required_criteria: bool | None = None,
) -> VerificationOutcome:
    """Classify a completion candidate without allowing required gaps to pass."""

    if not isinstance(blocking_violation_count, int) or isinstance(blocking_violation_count, bool):
        raise ValidationError("blocking_violation_count must be an integer")
    if blocking_violation_count < 0:
        raise ValidationError("blocking_violation_count cannot be negative")
    if not isinstance(repair_count_before, int) or isinstance(repair_count_before, bool):
        raise ValidationError("repair_count_before must be an integer")
    if repair_count_before < 0:
        raise ValidationError("repair_count_before cannot be negative")
    normalized = normalize_criteria(criteria)
    required = (
        any(item.required for item in normalized)
        if has_required_criteria is None
        else bool(has_required_criteria)
    )
    if not required or required_criterion_gaps(normalized):
        return VerificationOutcome.INSUFFICIENT
    if blocking_violation_count:
        return (
            VerificationOutcome.REPAIR if repair_count_before == 0 else VerificationOutcome.DEGRADED
        )
    return VerificationOutcome.PASS


def build_completion_result(
    *,
    judgment_id: str,
    candidate_sequence: int,
    criteria: Iterable[object],
    violations: Iterable[object] = (),
    repair_count_before: int = 0,
    blocking_violation_count: int | None = None,
    may_continue: bool | None = None,
    outcome: VerificationOutcome | str | None = None,
) -> CompletionResult:
    """Build the frozen CompletionResult used by verifier and Stop handlers."""

    normalized = normalize_criteria(criteria)
    violation_ids = tuple(
        item.rule_id if hasattr(item, "rule_id") else str(item) for item in violations
    )
    if blocking_violation_count is None:
        blocking_violation_count = len(violation_ids)
    computed = completion_outcome(
        normalized,
        blocking_violation_count=blocking_violation_count,
        repair_count_before=repair_count_before,
    )
    if outcome is not None:
        try:
            requested = (
                outcome
                if isinstance(outcome, VerificationOutcome)
                else VerificationOutcome(outcome)
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("completion outcome is not a closed value") from exc
        # Never permit a caller to override the required-gap safety rule.  A
        # required gap is held/insufficient, even if a caller also supplies a
        # generic blocking-violation outcome.
        if computed is VerificationOutcome.INSUFFICIENT:
            requested = computed
        elif requested is VerificationOutcome.PASS and computed is not VerificationOutcome.PASS:
            requested = computed
        computed = requested
    if may_continue is None:
        may_continue = computed is VerificationOutcome.REPAIR and repair_count_before == 0
    else:
        may_continue = (
            bool(may_continue)
            and computed is VerificationOutcome.REPAIR
            and repair_count_before == 0
        )
    return CompletionResult(
        judgment_id=judgment_id,
        candidate_sequence=candidate_sequence,
        outcome=computed,
        criteria=normalized,
        violations=violation_ids,
        repair_count_before=repair_count_before,
        may_continue=may_continue,
    )


# Compatibility names for adapters and focused walkthroughs.
required_gaps = required_criterion_gaps
completion_gaps = required_criterion_gaps
criteria_met = all_required_criteria_met
derive_completion_outcome = completion_outcome
make_completion_result = build_completion_result


__all__ = [
    "MAX_COMPLETION_CRITERIA",
    "RequiredCriterionGap",
    "all_required_criteria_met",
    "build_completion_result",
    "completion_gaps",
    "completion_outcome",
    "criterion_blocks_pass",
    "criterion_is_met",
    "criteria_met",
    "derive_completion_outcome",
    "make_completion_result",
    "normalize_criteria",
    "required_criterion_gaps",
    "required_gaps",
]
