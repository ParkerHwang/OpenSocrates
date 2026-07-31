"""Public, bounded cross-examination command generation."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from ..domain.alternatives import (
    AlternativeRequirement,
    AlternativeSufficiency,
    assess_alternative_sufficiency,
    observable_flip_conditions,
)
from ..domain.models import Alternative, FlipCondition
from ..domain.record_event import CrossExamCompletedPayload
from ..errors import ValidationError

_MAX_FINDING_TEXT = 400
_HIDDEN_REASONING_MARKERS = (
    "chain of thought",
    "hidden reasoning",
    "private reasoning",
    "private thought",
    "scratchpad",
    "internal reasoning",
)


def _public_text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{name} must be bounded non-empty public text")
    lowered = value.casefold()
    if any(marker in lowered for marker in _HIDDEN_REASONING_MARKERS):
        raise ValidationError(f"{name} requests hidden reasoning")
    if "\x00" in value or any(ord(char) < 0x20 and char not in "\n\t" for char in value):
        raise ValidationError(f"{name} contains prohibited control characters")
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError(f"{name} must be NFC-normalized")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class CrossExamInput:
    """Public findings supplied by the host model after the cross-exam prompt."""

    strongest_objection: str
    weakest_link: str
    omitted_alternative: str
    flip_conditions: tuple[FlipCondition, ...]
    alternatives: tuple[Alternative, ...] = ()
    alternative_requirement: AlternativeRequirement | None = None
    completion_complete: bool = True
    stale_risk: str = "The conclusion may be stale if a material ground changed."
    affected_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _public_text(self.strongest_objection, "strongest_objection", _MAX_FINDING_TEXT)
        _public_text(self.weakest_link, "weakest_link", _MAX_FINDING_TEXT)
        _public_text(self.omitted_alternative, "omitted_alternative", _MAX_FINDING_TEXT)
        _public_text(self.stale_risk, "stale_risk", _MAX_FINDING_TEXT)
        if not isinstance(self.flip_conditions, tuple):
            raise ValidationError("cross-exam flip_conditions must be a tuple")
        if not self.flip_conditions:
            raise ValidationError("cross-exam requires at least one concrete flip condition")
        observable_flip_conditions(self.flip_conditions)
        if not isinstance(self.alternatives, tuple) or len(self.alternatives) > 3:
            raise ValidationError("cross-exam alternatives are bounded")
        for alternative in self.alternatives:
            if not isinstance(alternative, Alternative):
                raise ValidationError("cross-exam alternatives must be Alternative values")
        if self.alternative_requirement is not None and not isinstance(
            self.alternative_requirement, AlternativeRequirement
        ):
            raise ValidationError("cross-exam alternative_requirement is invalid")
        if not isinstance(self.completion_complete, bool):
            raise ValidationError("cross-exam completion_complete must be boolean")
        if not isinstance(self.affected_ids, tuple) or len(self.affected_ids) > 12:
            raise ValidationError("cross-exam affected IDs are bounded")
        for value in self.affected_ids:
            _public_text(value, "cross-exam affected ID", 32)


@dataclass(frozen=True, slots=True, kw_only=True)
class CrossExamResult:
    """Bounded public projections and completion consequences."""

    strongest_objection: str
    weakest_link: str
    omitted_alternative: str
    stale_risk: str
    flip_conditions: tuple[FlipCondition, ...]
    alternative_sufficiency: AlternativeSufficiency
    completion_complete: bool
    completion_ready: bool
    blocking_reasons: tuple[str, ...] = ()
    affected_ids: tuple[str, ...] = ()

    @property
    def public_summary(self) -> str:
        pieces = (
            f"Strongest objection: {self.strongest_objection}",
            f"Weakest link: {self.weakest_link}",
            f"Omitted alternative: {self.omitted_alternative}",
            f"Stale-risk check: {self.stale_risk}",
        )
        summary = "\n".join(pieces)
        return summary[:1000]

    def to_payload(self) -> CrossExamCompletedPayload:
        return CrossExamCompletedPayload(
            findings_summary=self.public_summary,
            affected_ids=self.affected_ids,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CrossExamCommand:
    """Pure command for S14 to append after the same findings were public."""

    result: CrossExamResult
    payload: CrossExamCompletedPayload


def run_cross_exam(values: CrossExamInput) -> CrossExamResult:
    """Project all required findings into a public completion decision."""

    if not isinstance(values, CrossExamInput):
        raise ValidationError("run_cross_exam requires CrossExamInput")
    requirement = values.alternative_requirement or AlternativeRequirement(choice_required=False)
    sufficiency = assess_alternative_sufficiency(values.alternatives, requirement)
    blocking: list[str] = []
    if not sufficiency.sufficient:
        blocking.append("missing_alternative")
    if not values.completion_complete:
        blocking.append("completion_gap")
    result = CrossExamResult(
        strongest_objection=values.strongest_objection,
        weakest_link=values.weakest_link,
        omitted_alternative=values.omitted_alternative,
        stale_risk=values.stale_risk,
        flip_conditions=observable_flip_conditions(values.flip_conditions),
        alternative_sufficiency=sufficiency,
        completion_complete=values.completion_complete,
        completion_ready=not blocking,
        blocking_reasons=tuple(blocking),
        affected_ids=values.affected_ids,
    )
    _public_text(result.public_summary, "cross-exam summary", 1000)
    return result


def build_cross_exam_command(values: CrossExamInput) -> CrossExamCommand:
    """Return a record-ready public cross-exam command."""

    result = run_cross_exam(values)
    return CrossExamCommand(result=result, payload=result.to_payload())


def cross_examine(values: CrossExamInput) -> CrossExamResult:
    """Compatibility alias for ``run_cross_exam``."""

    return run_cross_exam(values)


__all__ = [
    "CrossExamCommand",
    "CrossExamInput",
    "CrossExamResult",
    "build_cross_exam_command",
    "cross_examine",
    "run_cross_exam",
]
