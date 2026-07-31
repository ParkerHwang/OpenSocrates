"""Material-conflict and re-judgment policy.

Conflicts are public artifacts, not transient model annotations.  The policy
therefore never treats a new observation as permission to overwrite a claim or
judgment version.  A material conflict always produces a visible revise-or-
hold obligation; a non-material conflict can remain public without changing
the conclusion strength.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from ..errors import ValidationError
from .enums import ConflictResolution, JudgmentState, JudgmentStrength
from .models import ClaimVersion, Conflict, JudgmentVersion


class ConflictAction(StrEnum):
    """Closed next action after comparing a conflict with current judgment."""

    PUBLIC_ONLY = "public_only"
    REVISE_REQUIRED = "revise_required"
    HOLD_REQUIRED = "hold_required"


class ConflictMateriality(StrEnum):
    """Closed materiality projection used by application callers."""

    MATERIAL = "material"
    NON_MATERIAL = "non_material"


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictSignals:
    """Public consequence signals for the normative materiality test."""

    changes_conclusion: bool = False
    changes_alternative_order: bool = False
    changes_high_severity_risk: bool = False
    blocks_completion_criterion: bool = False
    changes_strength: bool = False
    explicitly_material: bool = False
    publicly_relevant: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("changes_conclusion", self.changes_conclusion),
            ("changes_alternative_order", self.changes_alternative_order),
            ("changes_high_severity_risk", self.changes_high_severity_risk),
            ("blocks_completion_criterion", self.blocks_completion_criterion),
            ("changes_strength", self.changes_strength),
            ("explicitly_material", self.explicitly_material),
            ("publicly_relevant", self.publicly_relevant),
        ):
            if not isinstance(value, bool):
                raise ValidationError(f"conflict signal {name} must be boolean")

    @property
    def material(self) -> bool:
        """Whether any normative consequence makes the conflict material."""

        return self.explicitly_material or any(
            (
                self.changes_conclusion,
                self.changes_alternative_order,
                self.changes_high_severity_risk,
                self.blocks_completion_criterion,
                self.changes_strength,
            )
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictAssessment:
    """Public conflict decision consumed by re-judgment application code."""

    materiality: ConflictMateriality
    action: ConflictAction
    public: bool
    blocking: bool
    resolution_recorded: bool
    requires_new_version: bool

    @property
    def material(self) -> bool:
        return self.materiality is ConflictMateriality.MATERIAL

    @property
    def requires_rejudgment(self) -> bool:
        return self.action in {ConflictAction.REVISE_REQUIRED, ConflictAction.HOLD_REQUIRED}


@dataclass(frozen=True, slots=True, kw_only=True)
class JudgmentVersionHistory:
    """Immutable prior/current pair proving that a revision preserved history."""

    prior: JudgmentVersion
    current: JudgmentVersion

    def __post_init__(self) -> None:
        _validate_version_relation(self.prior, self.current)

    @property
    def versions(self) -> tuple[JudgmentVersion, JudgmentVersion]:
        return self.prior, self.current


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaimVersionHistory:
    """Immutable prior/current pair for an affected public claim."""

    prior: ClaimVersion
    current: ClaimVersion

    def __post_init__(self) -> None:
        _validate_claim_version_relation(self.prior, self.current)

    @property
    def versions(self) -> tuple[ClaimVersion, ClaimVersion]:
        return self.prior, self.current


def _ensure_conflict(conflict: Conflict) -> Conflict:
    if not isinstance(conflict, Conflict):
        raise ValidationError("conflict policy requires a Conflict")
    if not isinstance(conflict.resolution, ConflictResolution):
        raise ValidationError("conflict resolution is not closed")
    return conflict


def assess_materiality(
    conflict: Conflict,
    signals: ConflictSignals | None = None,
) -> ConflictMateriality:
    """Apply the public materiality test without inspecting conflict prose."""

    conflict = _ensure_conflict(conflict)
    if signals is not None and not isinstance(signals, ConflictSignals):
        raise ValidationError("conflict signals must be ConflictSignals")
    material = conflict.material or (signals.material if signals is not None else False)
    return ConflictMateriality.MATERIAL if material else ConflictMateriality.NON_MATERIAL


def assess_conflict(
    conflict: Conflict,
    signals: ConflictSignals | None = None,
    *,
    rejudgment_available: bool = True,
    hold_requested: bool = False,
) -> ConflictAssessment:
    """Return the required visible consequence of a public conflict.

    A resolved material conflict is still not silently cleared: its public
    resolution may be recorded, but the affected claim/judgment needs a new
    version before the current conclusion can become authoritative again.
    """

    conflict = _ensure_conflict(conflict)
    if not isinstance(rejudgment_available, bool) or not isinstance(hold_requested, bool):
        raise ValidationError("conflict action flags must be boolean")
    materiality = assess_materiality(conflict, signals)
    if materiality is ConflictMateriality.NON_MATERIAL:
        return ConflictAssessment(
            materiality=materiality,
            action=ConflictAction.PUBLIC_ONLY,
            public=signals.publicly_relevant if signals is not None else True,
            blocking=False,
            resolution_recorded=conflict.resolution is not ConflictResolution.UNRESOLVED,
            requires_new_version=False,
        )

    resolution_recorded = conflict.resolution is not ConflictResolution.UNRESOLVED
    # An unresolved conflict can be revised directly.  A selected resolution
    # basis, however, is authoritative only when its public reason exists;
    # otherwise the safe result is a hold rather than silent resolution.
    resolution_is_public = resolution_recorded and bool(
        conflict.resolution_reason and conflict.resolution_reason.strip()
    )
    missing_resolution_reason = resolution_recorded and not resolution_is_public
    action = (
        ConflictAction.HOLD_REQUIRED
        if hold_requested or not rejudgment_available or missing_resolution_reason
        else ConflictAction.REVISE_REQUIRED
    )
    return ConflictAssessment(
        materiality=materiality,
        action=action,
        public=True,
        blocking=True,
        resolution_recorded=resolution_is_public,
        requires_new_version=True,
    )


def requires_rejudgment(
    conflict: Conflict,
    signals: ConflictSignals | None = None,
) -> bool:
    """Return whether a conflict blocks the current judgment version."""

    return assess_conflict(conflict, signals).requires_rejudgment


def resolve_conflict_publicly(conflict: Conflict, public_reason: str) -> Conflict:
    """Attach a public reason to an already-selected closed resolution basis."""

    conflict = _ensure_conflict(conflict)
    if conflict.resolution is ConflictResolution.UNRESOLVED:
        raise ValidationError("an unresolved conflict cannot be marked resolved")
    if not isinstance(public_reason, str) or not public_reason.strip() or len(public_reason) > 600:
        raise ValidationError("public conflict resolution reason must be bounded text")
    return replace(conflict, resolution_reason=public_reason)


def _validate_version_relation(prior: JudgmentVersion, successor: JudgmentVersion) -> None:
    if not isinstance(prior, JudgmentVersion) or not isinstance(successor, JudgmentVersion):
        raise ValidationError("judgment version history requires JudgmentVersion values")
    if prior.judgment_id != successor.judgment_id:
        raise ValidationError("judgment versions must belong to one judgment")
    if successor.version != prior.version + 1:
        raise ValidationError("successor judgment version must increment by one")
    if successor.supersedes_version != prior.version:
        raise ValidationError("successor must identify its superseded version")
    if successor.state not in {JudgmentState.REVISED, JudgmentState.HELD}:
        raise ValidationError("successor must be revised or held")


def preserve_judgment_version(
    prior: JudgmentVersion,
    successor: JudgmentVersion,
) -> JudgmentVersionHistory:
    """Validate the immutable version relation and return a history pair.

    The function does not mutate either frozen model.  A successor must point
    explicitly at the prior version, which makes silent replacement
    impossible for callers that use the returned pair as their command.
    """

    _validate_version_relation(prior, successor)
    return JudgmentVersionHistory(prior=prior, current=successor)


def _validate_claim_version_relation(prior: ClaimVersion, successor: ClaimVersion) -> None:
    if not isinstance(prior, ClaimVersion) or not isinstance(successor, ClaimVersion):
        raise ValidationError("claim version history requires ClaimVersion values")
    if prior.claim_id != successor.claim_id:
        raise ValidationError("claim versions must belong to one claim")
    if successor.version != prior.version + 1:
        raise ValidationError("successor claim version must increment by one")
    if not prior.active or not successor.active:
        raise ValidationError("claim version relation requires active public versions")


def preserve_claim_version(prior: ClaimVersion, successor: ClaimVersion) -> ClaimVersionHistory:
    """Validate a public claim correction without mutating the prior version."""

    _validate_claim_version_relation(prior, successor)
    return ClaimVersionHistory(prior=prior, current=successor)


def hold_judgment_version(
    current: JudgmentVersion,
    public_reason: str,
) -> JudgmentVersion:
    """Create a new held version while preserving the current version."""

    if not isinstance(current, JudgmentVersion):
        raise ValidationError("current judgment must be JudgmentVersion")
    if not isinstance(public_reason, str) or not public_reason.strip() or len(public_reason) > 500:
        raise ValidationError("hold reason must be bounded public text")
    return JudgmentVersion(
        judgment_id=current.judgment_id,
        version=current.version + 1,
        state=JudgmentState.HELD,
        conclusion=current.conclusion,
        strength=JudgmentStrength.HELD,
        supersedes_version=current.version,
        change_reason=public_reason,
        ground_claim_ids=current.ground_claim_ids,
        uncertainty_claim_ids=current.uncertainty_claim_ids,
        flip_conditions=current.flip_conditions,
        alternative_ids=current.alternative_ids,
    )


def version_history(prior: JudgmentVersion, successor: JudgmentVersion) -> JudgmentVersionHistory:
    """Public alias that returns the immutable prior/current pair."""

    _validate_version_relation(prior, successor)
    return JudgmentVersionHistory(prior=prior, current=successor)


__all__ = [
    "ConflictAction",
    "ConflictAssessment",
    "ConflictMateriality",
    "ConflictSignals",
    "ClaimVersionHistory",
    "JudgmentVersionHistory",
    "assess_conflict",
    "assess_materiality",
    "hold_judgment_version",
    "preserve_judgment_version",
    "preserve_claim_version",
    "requires_rejudgment",
    "resolve_conflict_publicly",
    "version_history",
]
