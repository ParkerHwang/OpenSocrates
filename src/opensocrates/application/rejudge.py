"""Pure application command for visible conflict re-judgment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain.contradiction import (
    ClaimVersionHistory,
    ConflictAction,
    ConflictAssessment,
    ConflictSignals,
    JudgmentVersionHistory,
    assess_conflict,
    hold_judgment_version,
    preserve_claim_version,
    preserve_judgment_version,
)
from ..domain.enums import ConflictResolution, JudgmentState
from ..domain.models import ClaimVersion, Conflict, JudgmentVersion
from ..errors import ValidationError


class RejudgeAction(StrEnum):
    """Closed action S14 may apply to the current task projection."""

    PUBLIC_CONFLICT = "public_conflict"
    REVISE = "revise"
    HOLD = "hold"


@dataclass(frozen=True, slots=True, kw_only=True)
class RejudgeRequest:
    """Public conflict plus optional new public judgment version."""

    current_version: JudgmentVersion
    conflict: Conflict
    signals: ConflictSignals | None = None
    revised_version: JudgmentVersion | None = None
    current_claim_versions: tuple[ClaimVersion, ...] = ()
    revised_claim_versions: tuple[ClaimVersion, ...] = ()
    hold_reason: str | None = None
    hold_requested: bool = False

    def __post_init__(self) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        if not isinstance(self.current_version, JudgmentVersion):
            raise ValidationError("rejudge current_version must be JudgmentVersion")
        if not isinstance(self.conflict, Conflict):
            raise ValidationError("rejudge conflict must be Conflict")
        if self.signals is not None and not isinstance(self.signals, ConflictSignals):
            raise ValidationError("rejudge signals must be ConflictSignals")
        if self.revised_version is not None and not isinstance(
            self.revised_version, JudgmentVersion
        ):
            raise ValidationError("rejudge revised_version must be JudgmentVersion")
        if not isinstance(self.current_claim_versions, tuple) or not isinstance(
            self.revised_claim_versions, tuple
        ):
            raise ValidationError("rejudge claim versions must be tuples")
        if any(
            not isinstance(claim, ClaimVersion)
            for claim in (*self.current_claim_versions, *self.revised_claim_versions)
        ):
            raise ValidationError("rejudge claim versions must be ClaimVersion values")
        if len({claim.claim_id for claim in self.current_claim_versions}) != len(
            self.current_claim_versions
        ):
            raise ValidationError("rejudge current claim versions must be unique")
        if len({claim.claim_id for claim in self.revised_claim_versions}) != len(
            self.revised_claim_versions
        ):
            raise ValidationError("rejudge revised claim versions must be unique")
        if self.hold_reason is not None:
            if (
                not isinstance(self.hold_reason, str)
                or not self.hold_reason.strip()
                or len(self.hold_reason) > 500
            ):
                raise ValidationError("rejudge hold_reason must be bounded public text")
        if not isinstance(self.hold_requested, bool):
            raise ValidationError("rejudge hold_requested must be boolean")


@dataclass(frozen=True, slots=True, kw_only=True)
class RejudgeResult:
    """Pure result carrying public conflict and preserved version history."""

    action: RejudgeAction
    assessment: ConflictAssessment
    conflict: Conflict
    prior_version: JudgmentVersion
    successor_version: JudgmentVersion | None = None
    history: JudgmentVersionHistory | None = None
    prior_claim_versions: tuple[ClaimVersion, ...] = ()
    claim_histories: tuple[ClaimVersionHistory, ...] = ()
    record_conflict: bool = True
    record_resolution: bool = False

    @property
    def blocked(self) -> bool:
        return self.action is RejudgeAction.HOLD

    @property
    def revised(self) -> bool:
        return self.action is RejudgeAction.REVISE

    @property
    def public(self) -> bool:
        return self.record_conflict


def _default_hold_reason(request: RejudgeRequest) -> str:
    if request.hold_reason is not None:
        return request.hold_reason
    summary = request.conflict.summary.strip()
    if summary and len(summary) <= 500:
        return summary
    return "A material conflict requires a visible hold before completion."


def _claim_histories(request: RejudgeRequest) -> tuple[ClaimVersionHistory, ...]:
    """Validate all supplied claim corrections and keep prior versions visible."""

    current_by_id = {claim.claim_id: claim for claim in request.current_claim_versions}
    histories: list[ClaimVersionHistory] = []
    for successor in request.revised_claim_versions:
        prior = current_by_id.get(successor.claim_id)
        if prior is None:
            raise ValidationError("revised claim references an unknown current claim")
        histories.append(preserve_claim_version(prior, successor))
    return tuple(histories)


def plan_rejudgment(request: RejudgeRequest) -> RejudgeResult:
    """Plan a revise/hold transition without mutating prior public versions."""

    if not isinstance(request, RejudgeRequest):
        raise ValidationError("plan_rejudgment requires RejudgeRequest")
    assessment = assess_conflict(
        request.conflict,
        request.signals,
        rejudgment_available=request.revised_version is not None,
        hold_requested=request.hold_requested,
    )
    if not assessment.material:
        return RejudgeResult(
            action=RejudgeAction.PUBLIC_CONFLICT,
            assessment=assessment,
            conflict=request.conflict,
            prior_version=request.current_version,
            prior_claim_versions=request.current_claim_versions,
            claim_histories=(),
            record_conflict=assessment.public,
            record_resolution=request.conflict.resolution is not ConflictResolution.UNRESOLVED,
        )

    if assessment.action is ConflictAction.REVISE_REQUIRED and request.revised_version is not None:
        successor = request.revised_version
        if successor.state is not JudgmentState.REVISED:
            raise ValidationError("a revise command requires JudgmentState.REVISED")
        history = preserve_judgment_version(request.current_version, successor)
        claim_histories = _claim_histories(request)
        return RejudgeResult(
            action=RejudgeAction.REVISE,
            assessment=assessment,
            conflict=request.conflict,
            prior_version=request.current_version,
            successor_version=successor,
            history=history,
            prior_claim_versions=request.current_claim_versions,
            claim_histories=claim_histories,
            record_conflict=True,
            record_resolution=assessment.resolution_recorded,
        )

    # A material conflict with no valid public revision is held in a new
    # version.  The prior conclusion remains available in history and is never
    # replaced in place.
    successor = hold_judgment_version(request.current_version, _default_hold_reason(request))
    history = preserve_judgment_version(request.current_version, successor)
    return RejudgeResult(
        action=RejudgeAction.HOLD,
        assessment=assessment,
        conflict=request.conflict,
        prior_version=request.current_version,
        successor_version=successor,
        history=history,
        prior_claim_versions=request.current_claim_versions,
        claim_histories=(),
        record_conflict=True,
        record_resolution=assessment.resolution_recorded,
    )


def rejudge(request: RejudgeRequest) -> RejudgeResult:
    """Compatibility entry point for the pure re-judgment planner."""

    return plan_rejudgment(request)


def handle_rejudgment(request: RejudgeRequest) -> RejudgeResult:
    """Application naming alias used by host-control callers."""

    return plan_rejudgment(request)


__all__ = [
    "RejudgeAction",
    "RejudgeRequest",
    "RejudgeResult",
    "handle_rejudgment",
    "plan_rejudgment",
    "rejudge",
]
