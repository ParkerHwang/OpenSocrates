"""Application orchestration for the same-host Strict second pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..domain.models import Alternative, ClaimVersion, Criterion
from ..domain.strict import (
    StrictComparison,
    StrictNextAction,
    StrictPacket,
    StrictPassResult,
    StrictReconciliation,
    build_strict_packet,
    compare_strict_passes,
)
from ..errors import ValidationError


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictPassRequest:
    """Host instruction carrying only the blinded packet and fixed fragment ID."""

    packet: StrictPacket
    prompt_fragment_id: str = "strict_second_pass"
    same_host_second_pass: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.packet, StrictPacket):
            raise ValidationError("strict pass request requires StrictPacket")
        if self.prompt_fragment_id != "strict_second_pass":
            raise ValidationError("strict pass fragment ID is closed")
        if self.same_host_second_pass is not True:
            raise ValidationError("Strict must be described as a same-host second pass")


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictPassApplicationResult:
    """Comparison plus the public action required before completion."""

    request: StrictPassRequest
    second_pass: StrictPassResult
    comparison: StrictComparison

    @property
    def next_action(self) -> StrictNextAction:
        return self.comparison.next_action

    @property
    def completion_allowed(self) -> bool:
        return self.comparison.can_complete and (
            self.comparison.next_action is not StrictNextAction.RECONCILE
        )

    @property
    def reconciliation_required(self) -> bool:
        return self.comparison.reconciliation_required and not self.comparison.reconciled


def prepare_strict_pass(packet: StrictPacket) -> StrictPassRequest:
    """Prepare a same-host request; no model call is made here."""

    return StrictPassRequest(packet=packet)


def prepare_blinded_strict_pass(
    decision_question: str,
    public_framing: str,
    material_grounds: Iterable[ClaimVersion],
    alternatives: Iterable[Alternative],
    completion_criteria: Iterable[Criterion],
    *,
    current_conclusion: str | None = None,
    selected_alternative_ids: Iterable[str] = (),
) -> StrictPassRequest:
    """Build a conclusion-blinded packet and wrap it for the host."""

    packet = build_strict_packet(
        decision_question,
        public_framing,
        material_grounds,
        alternatives,
        completion_criteria,
        current_conclusion=current_conclusion,
        selected_alternative_ids=selected_alternative_ids,
    )
    return prepare_strict_pass(packet)


def complete_strict_pass(
    request: StrictPassRequest,
    first_pass: StrictPassResult,
    second_pass: StrictPassResult,
    *,
    first_selected_alternative_id: str | None = None,
    reconciliation: StrictReconciliation | None = None,
) -> StrictPassApplicationResult:
    """Compare two public pass results and enforce visible reconciliation."""

    if not isinstance(request, StrictPassRequest):
        raise ValidationError("complete_strict_pass requires StrictPassRequest")
    comparison = compare_strict_passes(
        first_pass,
        second_pass,
        first_selected_alternative_id=first_selected_alternative_id,
        reconciliation=reconciliation,
    )
    return StrictPassApplicationResult(
        request=request,
        second_pass=second_pass,
        comparison=comparison,
    )


def evaluate_strict_pass(
    request: StrictPassRequest,
    first_pass: StrictPassResult,
    second_pass: StrictPassResult,
    *,
    first_selected_alternative_id: str | None = None,
    reconciliation: StrictReconciliation | None = None,
) -> StrictPassApplicationResult:
    """Compatibility alias for the application comparison step."""

    return complete_strict_pass(
        request,
        first_pass,
        second_pass,
        first_selected_alternative_id=first_selected_alternative_id,
        reconciliation=reconciliation,
    )


run_strict_pass = complete_strict_pass


__all__ = [
    "StrictPassApplicationResult",
    "StrictPassRequest",
    "complete_strict_pass",
    "evaluate_strict_pass",
    "prepare_blinded_strict_pass",
    "prepare_strict_pass",
    "run_strict_pass",
]
