"""Alternative sufficiency and observable flip-condition rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ..constants import MAX_CARD_FLIP_CONDITIONS
from ..errors import ValidationError
from .enums import AlternativeDisposition, FlipDirection
from .models import Alternative, FlipCondition


class AlternativeSufficiencyStatus(StrEnum):
    """Closed outcome for the choice/recommendation alternative check."""

    NOT_REQUIRED = "not_required"
    SUFFICIENT = "sufficient"
    JUSTIFIED_BINARY = "justified_binary"
    MISSING_SELECTED = "missing_selected"
    MISSING_NON_SELECTED = "missing_non_selected"
    INVALID = "invalid"


class AlternativeDispositionStatus(StrEnum):
    """Closed validation outcome for a public disposition set."""

    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True, kw_only=True)
class AlternativeRequirement:
    """Framing facts that determine whether a non-selected alternative is required."""

    choice_required: bool = True
    genuine_binary: bool = False
    no_alternative_justification: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.choice_required, bool) or not isinstance(self.genuine_binary, bool):
            raise ValidationError("alternative requirement flags must be boolean")
        if self.no_alternative_justification is not None:
            _bounded_public_text(
                self.no_alternative_justification,
                "no_alternative_justification",
                400,
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class AlternativeSufficiency:
    """Bounded public result of the alternative sufficiency check."""

    status: AlternativeSufficiencyStatus
    selected_count: int
    non_selected_count: int
    public_reason: str

    @property
    def sufficient(self) -> bool:
        return self.status in {
            AlternativeSufficiencyStatus.NOT_REQUIRED,
            AlternativeSufficiencyStatus.SUFFICIENT,
            AlternativeSufficiencyStatus.JUSTIFIED_BINARY,
        }


class FlipConditionError(ValidationError):
    """Raised when a flip condition is vague or not externally observable."""


_VAGUE_PATTERNS = (
    "if circumstances change",
    "if the circumstances change",
    "if new information emerges",
    "if new information appears",
    "if new information comes",
    "if the analysis is wrong",
    "if things change",
    "if the situation changes",
    "if the conditions change",
    "if the facts change",
    "if more information becomes available",
    "if more information emerges",
    "if more data becomes available",
    "if more data emerges",
    "if something changes",
)
_OBSERVABLE_MARKERS = (
    "measure",
    "measured",
    "measurement",
    "check",
    "checked",
    "monitor",
    "observe",
    "observed",
    "obtain",
    "quote",
    "quoted",
    "threshold",
    "exceed",
    "exceeds",
    "above",
    "below",
    "under",
    "over",
    "at least",
    "at most",
    "falls",
    "drops",
    "rises",
    "reaches",
    "remains",
    "reports",
    "shows",
    "confirm",
    "validate",
    "test",
    "review",
    "compare",
    "metric",
    "renewal",
    "contract",
    "매출",
    "비용",
    "측정",
    "확인",
    "검증",
    "기준",
)
_NUMBER_OR_DATE = re.compile(
    r"(?:\d|%|\$|€|£|¥|\b(?:usd|krw|eur|gbp|days?|weeks?|months?|quarters?|years?)\b)",
    re.IGNORECASE,
)


def _bounded_public_text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{name} must be bounded non-empty public text")
    if "\x00" in value or any(ord(char) < 0x20 and char not in "\n\t" for char in value):
        raise ValidationError(f"{name} contains prohibited control characters")
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError(f"{name} must be NFC-normalized")
    return value


def validate_alternative_disposition(alternative: Alternative) -> Alternative:
    """Validate one public alternative without changing its disposition."""

    if not isinstance(alternative, Alternative):
        raise ValidationError("alternative must be the canonical Alternative model")
    if not isinstance(alternative.disposition, AlternativeDisposition):
        raise ValidationError("alternative disposition is not closed")
    _bounded_public_text(alternative.name, "alternative.name", 160)
    _bounded_public_text(alternative.reason, "alternative.reason", 400)
    return alternative


def validate_alternatives(alternatives: Iterable[Alternative]) -> tuple[Alternative, ...]:
    """Validate a bounded, distinct public alternative set."""

    values = tuple(alternatives)
    if len(values) > 3:
        raise ValidationError("at most three alternatives are allowed")
    names: set[str] = set()
    selected = 0
    for alternative in values:
        validate_alternative_disposition(alternative)
        key = alternative.name.strip().casefold()
        if key in names:
            raise ValidationError("alternative names must be distinct")
        names.add(key)
        if alternative.disposition is AlternativeDisposition.SELECTED:
            selected += 1
    if selected > 1:
        raise ValidationError("at most one alternative may be selected")
    return values


def assess_alternative_sufficiency(
    alternatives: Iterable[Alternative],
    requirement: AlternativeRequirement | None = None,
    *,
    choice_required: bool | None = None,
    genuine_binary: bool | None = None,
    no_alternative_justification: str | None = None,
) -> AlternativeSufficiency:
    """Require a real non-selected alternative unless framing proves a binary.

    The explicit keyword arguments are compatibility conveniences for callers
    that do not yet construct ``AlternativeRequirement``.  They are converted
    to the same closed requirement before evaluation.
    """

    if requirement is not None and not isinstance(requirement, AlternativeRequirement):
        raise ValidationError("alternative requirement must be AlternativeRequirement")
    if requirement is None:
        requirement = AlternativeRequirement(
            choice_required=True if choice_required is None else choice_required,
            genuine_binary=False if genuine_binary is None else genuine_binary,
            no_alternative_justification=no_alternative_justification,
        )
    elif any(
        value is not None
        for value in (choice_required, genuine_binary, no_alternative_justification)
    ):
        raise ValidationError("alternative requirement supplied twice")

    try:
        values = validate_alternatives(alternatives)
    except ValidationError:
        return AlternativeSufficiency(
            status=AlternativeSufficiencyStatus.INVALID,
            selected_count=0,
            non_selected_count=0,
            public_reason="invalid alternative set",
        )
    selected_count = sum(item.disposition is AlternativeDisposition.SELECTED for item in values)
    non_selected_count = sum(
        item.disposition is not AlternativeDisposition.SELECTED for item in values
    )

    if not requirement.choice_required:
        return AlternativeSufficiency(
            status=AlternativeSufficiencyStatus.NOT_REQUIRED,
            selected_count=selected_count,
            non_selected_count=non_selected_count,
            public_reason="a choice/recommendation comparison is not required",
        )
    if selected_count != 1:
        return AlternativeSufficiency(
            status=AlternativeSufficiencyStatus.MISSING_SELECTED,
            selected_count=selected_count,
            non_selected_count=non_selected_count,
            public_reason="exactly one selected alternative is required",
        )
    if non_selected_count > 0:
        return AlternativeSufficiency(
            status=AlternativeSufficiencyStatus.SUFFICIENT,
            selected_count=selected_count,
            non_selected_count=non_selected_count,
            public_reason="at least one real non-selected alternative is present",
        )
    if requirement.genuine_binary and requirement.no_alternative_justification:
        return AlternativeSufficiency(
            status=AlternativeSufficiencyStatus.JUSTIFIED_BINARY,
            selected_count=selected_count,
            non_selected_count=non_selected_count,
            public_reason="framing records a genuine binary/no-alternative judgment",
        )
    return AlternativeSufficiency(
        status=AlternativeSufficiencyStatus.MISSING_NON_SELECTED,
        selected_count=selected_count,
        non_selected_count=non_selected_count,
        public_reason="a real non-selected alternative or public binary justification is required",
    )


def has_real_nonselected_alternative(alternatives: Iterable[Alternative]) -> bool:
    """Return whether at least one public alternative is not selected."""

    values = validate_alternatives(alternatives)
    return any(item.disposition is not AlternativeDisposition.SELECTED for item in values)


def _is_vague(text: str) -> bool:
    lowered = " ".join(text.casefold().split())
    return any(pattern in lowered for pattern in _VAGUE_PATTERNS)


def _is_observable(text: str) -> bool:
    lowered = text.casefold()
    return bool(_NUMBER_OR_DATE.search(lowered)) or any(
        marker in lowered for marker in _OBSERVABLE_MARKERS
    )


def validate_flip_condition(flip_condition: FlipCondition) -> FlipCondition:
    """Reject vague conditions and require an observable check/threshold."""

    if not isinstance(flip_condition, FlipCondition):
        raise FlipConditionError("flip condition must be the canonical FlipCondition model")
    if not isinstance(flip_condition.direction, FlipDirection):
        raise FlipConditionError("flip condition direction is not closed")
    condition = _bounded_public_text(flip_condition.condition, "flip condition", 300)
    check = _bounded_public_text(flip_condition.check, "flip condition check", 240)
    if flip_condition.affected_conclusion is not None:
        _bounded_public_text(flip_condition.affected_conclusion, "affected conclusion", 240)
    if _is_vague(condition) or _is_vague(check):
        raise FlipConditionError("vague flip conditions are not observable")
    if not _is_observable(condition) or not _is_observable(check):
        raise FlipConditionError(
            "flip condition must name an observable measure, threshold, or check"
        )
    return flip_condition


def observable_flip_conditions(
    flip_conditions: Iterable[FlipCondition],
) -> tuple[FlipCondition, ...]:
    """Validate the bounded card set of concrete flip conditions."""

    values = tuple(flip_conditions)
    if len(values) > MAX_CARD_FLIP_CONDITIONS:
        raise FlipConditionError("at most two flip conditions are allowed")
    normalized: list[str] = []
    for condition in values:
        validate_flip_condition(condition)
        key = f"{condition.condition.casefold()}\x1f{condition.check.casefold()}"
        if key in normalized:
            raise FlipConditionError("flip conditions must be distinct")
        normalized.append(key)
    return values


# Compatibility aliases for application and verifier callers.
check_alternative_sufficiency = assess_alternative_sufficiency
alternative_sufficiency = assess_alternative_sufficiency
validate_dispositions = validate_alternatives


def is_observable_flip_condition(value: str) -> bool:
    """Return whether text is concrete enough to be used as a flip condition."""

    if not isinstance(value, str):
        return False
    return _is_observable(value) and not _is_vague(value)


validate_flip_conditions = observable_flip_conditions


__all__ = [
    "AlternativeDispositionStatus",
    "AlternativeRequirement",
    "AlternativeSufficiency",
    "AlternativeSufficiencyStatus",
    "FlipConditionError",
    "alternative_sufficiency",
    "assess_alternative_sufficiency",
    "check_alternative_sufficiency",
    "has_real_nonselected_alternative",
    "is_observable_flip_condition",
    "observable_flip_conditions",
    "validate_alternative_disposition",
    "validate_alternatives",
    "validate_dispositions",
    "validate_flip_condition",
    "validate_flip_conditions",
]
