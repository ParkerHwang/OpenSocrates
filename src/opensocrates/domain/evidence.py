"""Pure evidence contracts and conclusion-strength policy.

The models in :mod:`opensocrates.domain.models` are intentionally small frozen
records.  This module contains the construction and projection rules that are
too semantic to express in the dataclass declarations, while remaining free of
I/O, host adapters, persistence, and model calls.

The deterministic verifier lives in ``opensocrates.verification``.  Domain
helpers here therefore establish shape and lifecycle invariants, but do not
claim that a source semantically supports a proposition.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from ..errors import ValidationError
from .enums import (
    ClaimMateriality,
    ConflictResolution,
    CriterionStatus,
    EvidenceState,
    JudgmentStrength,
    SourceKind,
)
from .models import (
    Calculation,
    ClaimVersion,
    CompletionResult,
    Conflict,
    SourceReference,
)

MAX_CLAIM_SOURCES = 8
MAX_CLAIM_BASIS = 8


@dataclass(frozen=True, slots=True)
class StrengthEligibility:
    """The pure result of checking a requested conclusion strength.

    ``reason_codes`` are stable domain codes.  Presentation-layer verification
    maps them to localized ``Violation`` objects; no user-facing prose is
    generated here.
    """

    requested: JudgmentStrength
    eligible: bool
    reason_codes: tuple[str, ...] = ()


def _as_tuple(values: Iterable[Any] | None) -> tuple[Any, ...]:
    return tuple(values or ())


def _as_state(value: EvidenceState | str) -> EvidenceState:
    if isinstance(value, EvidenceState):
        return value
    try:
        return EvidenceState(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("evidence_state: unknown closed value") from exc


def _as_materiality(value: ClaimMateriality | str) -> ClaimMateriality:
    if isinstance(value, ClaimMateriality):
        return value
    try:
        return ClaimMateriality(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("materiality: unknown closed value") from exc


def _as_resolution(value: ConflictResolution | str) -> ConflictResolution:
    if isinstance(value, ConflictResolution):
        return value
    try:
        return ConflictResolution(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("resolution: unknown closed value") from exc


def make_source_reference(
    *,
    source_id: str,
    kind: Any,
    display_name: str,
    uri: str | None = None,
    safe_locator: str | None = None,
    published_at: str | None = None,
    checked_at: str,
    content_hash: str | None = None,
    allow_public_fixture_hash: bool = False,
) -> SourceReference:
    """Construct a source reference using the frozen source model.

    Credential-like query parameters are converted to ``None`` by the frozen
    model's persistence sanitizer.  A non-null content hash is deliberately
    rejected unless the caller explicitly identifies a public fixture; normal
    user evidence never carries one.
    """

    if content_hash is not None and not allow_public_fixture_hash:
        raise ValidationError("source content_hash is reserved for public fixtures")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValidationError("source display_name must be non-empty")
    if not isinstance(kind, SourceKind):
        try:
            kind = SourceKind(kind)
        except (TypeError, ValueError) as exc:
            raise ValidationError("source kind: unknown closed value") from exc
    return SourceReference(
        source_id=source_id,
        kind=kind,
        display_name=display_name,
        uri=uri,
        safe_locator=safe_locator,
        published_at=published_at,
        checked_at=checked_at,
        content_hash=content_hash,
    )


def construct_source_reference(**kwargs: Any) -> SourceReference:
    """Compatibility alias for :func:`make_source_reference`."""

    return make_source_reference(**kwargs)


def make_conflict(
    *,
    summary: str,
    subject: str,
    source_ids: Iterable[str] = (),
    affected_claim_ids: Iterable[str] = (),
    material: bool,
    resolution: ConflictResolution | str = ConflictResolution.UNRESOLVED,
    resolution_reason: str | None = None,
) -> Conflict:
    """Construct a public conflict without resolving it implicitly."""

    if not isinstance(material, bool):
        raise ValidationError("conflict material must be boolean")
    return Conflict(
        summary=summary,
        subject=subject,
        source_ids=tuple(source_ids),
        affected_claim_ids=tuple(affected_claim_ids),
        material=material,
        resolution=_as_resolution(resolution),
        resolution_reason=resolution_reason,
    )


def construct_conflict(**kwargs: Any) -> Conflict:
    """Compatibility alias for :func:`make_conflict`."""

    return make_conflict(**kwargs)


def _validate_claim_shape(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    *,
    evidence_state: EvidenceState,
    source_ids: tuple[str, ...],
    basis_claim_ids: tuple[str, ...],
    calculation: Calculation | None,
    conflict: Conflict | None,
) -> None:
    """Apply the exact six-state cross-field contract before construction."""

    if len(source_ids) > MAX_CLAIM_SOURCES:
        raise ValidationError("claim source_ids exceed the bounded evidence limit")
    if len(basis_claim_ids) > MAX_CLAIM_BASIS:
        raise ValidationError("claim basis_claim_ids exceed the bounded evidence limit")
    if len(set(source_ids)) != len(source_ids):
        raise ValidationError("claim source_ids must be unique")
    if len(set(basis_claim_ids)) != len(basis_claim_ids):
        raise ValidationError("claim basis_claim_ids must be unique")

    if evidence_state is EvidenceState.VERIFIED:
        if not source_ids:
            raise ValidationError("verified claim requires at least one source")
        if calculation is not None or conflict is not None:
            raise ValidationError("verified claim cannot carry calculation or conflict")
    elif evidence_state is EvidenceState.COMPUTED:
        if calculation is None:
            raise ValidationError("computed claim requires a calculation")
        if conflict is not None:
            raise ValidationError("computed claim cannot carry conflict")
    elif evidence_state is EvidenceState.INFERRED:
        if not basis_claim_ids:
            raise ValidationError("inferred claim requires at least one basis claim")
        if calculation is not None or conflict is not None:
            raise ValidationError("inferred claim cannot carry calculation or conflict")
    elif evidence_state is EvidenceState.ASSUMED:
        if source_ids or basis_claim_ids or calculation is not None or conflict is not None:
            raise ValidationError(
                "assumed claim must have empty evidence, basis, calculation, and conflict"
            )
    elif evidence_state is EvidenceState.UNVERIFIED:
        if calculation is not None or conflict is not None:
            raise ValidationError("unverified claim cannot carry calculation or conflict")
    elif evidence_state is EvidenceState.CONFLICTED:
        if conflict is None:
            raise ValidationError("conflicted claim requires conflict")
        has_two_sources = len(source_ids) >= 2
        has_source_and_basis = bool(source_ids) and bool(basis_claim_ids or calculation is not None)
        if not (has_two_sources or has_source_and_basis):
            raise ValidationError(
                "conflicted claim requires two sources or one source plus calculation/basis"
            )


def make_claim_version(
    *,
    claim_id: str,
    version: int,
    text: str,
    materiality: ClaimMateriality | str,
    evidence_state: EvidenceState | str,
    source_ids: Iterable[str] = (),
    basis_claim_ids: Iterable[str] = (),
    calculation: Calculation | None = None,
    conflict: Conflict | None = None,
    active: bool = True,
) -> ClaimVersion:
    """Construct an immutable claim version with exact state invariants."""

    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValidationError("claim version must be a positive integer")
    state = _as_state(evidence_state)
    material = _as_materiality(materiality)
    sources = tuple(source_ids)
    basis = tuple(basis_claim_ids)
    _validate_claim_shape(
        evidence_state=state,
        source_ids=sources,
        basis_claim_ids=basis,
        calculation=calculation,
        conflict=conflict,
    )
    return ClaimVersion(
        claim_id=claim_id,
        version=version,
        text=text,
        materiality=material,
        evidence_state=state,
        source_ids=sources,
        basis_claim_ids=basis,
        calculation=calculation,
        conflict=conflict,
        active=active,
    )


def construct_claim_version(**kwargs: Any) -> ClaimVersion:
    """Compatibility alias for :func:`make_claim_version`."""

    return make_claim_version(**kwargs)


def validate_claim_version_shape(claim: ClaimVersion) -> ClaimVersion:
    """Re-apply the six-state shape rules to an existing frozen claim."""

    if not isinstance(claim, ClaimVersion):
        raise ValidationError("claim: expected ClaimVersion")
    if not isinstance(claim.version, int) or isinstance(claim.version, bool) or claim.version < 1:
        raise ValidationError("claim version must be a positive integer")
    _validate_claim_shape(
        evidence_state=claim.evidence_state,
        source_ids=claim.source_ids,
        basis_claim_ids=claim.basis_claim_ids,
        calculation=claim.calculation,
        conflict=claim.conflict,
    )
    return claim


def revise_claim_version(
    previous: ClaimVersion,
    *,
    text: str,
    materiality: ClaimMateriality | str,
    evidence_state: EvidenceState | str,
    source_ids: Iterable[str] = (),
    basis_claim_ids: Iterable[str] = (),
    calculation: Calculation | None = None,
    conflict: Conflict | None = None,
) -> tuple[ClaimVersion, ClaimVersion]:
    """Create an inactive prior version and a new active version.

    The prior object is never mutated.  The returned pair is suitable for a
    projection containing one current active version per claim.
    """

    validate_claim_version_shape(previous)
    if not previous.active:
        raise ValidationError("only the active current claim can be revised")
    retired = replace(previous, active=False)
    current = make_claim_version(
        claim_id=previous.claim_id,
        version=previous.version + 1,
        text=text,
        materiality=materiality,
        evidence_state=evidence_state,
        source_ids=source_ids,
        basis_claim_ids=basis_claim_ids,
        calculation=calculation,
        conflict=conflict,
        active=True,
    )
    return retired, current


def _group_claims(claims: Iterable[ClaimVersion]) -> dict[str, list[ClaimVersion]]:
    grouped: dict[str, list[ClaimVersion]] = {}
    for claim in claims:
        validate_claim_version_shape(claim)
        grouped.setdefault(str(claim.claim_id), []).append(claim)
    return grouped


def project_current_claim_versions(
    claims: Iterable[ClaimVersion],
) -> dict[str, ClaimVersion]:
    """Project one active, highest-version claim for every claim ID.

    Duplicate versions, gaps, inactive latest versions, and multiple active
    versions are rejected instead of being guessed through.
    """

    grouped = _group_claims(claims)
    result: dict[str, ClaimVersion] = {}
    for claim_id, versions in grouped.items():
        ordered = sorted(versions, key=lambda item: item.version)
        numbers = [item.version for item in ordered]
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            raise ValidationError(f"claim {claim_id}: versions must be contiguous from one")
        active = [item for item in ordered if item.active]
        if len(active) != 1:
            raise ValidationError(
                f"claim {claim_id}: exactly one active current version is required"
            )
        current = active[0]
        if current.version != ordered[-1].version:
            raise ValidationError(f"claim {claim_id}: only the highest version may be active")
        result[claim_id] = current
    return result


def current_claim_version(claims: Iterable[ClaimVersion], claim_id: str) -> ClaimVersion:
    """Return one current version, failing closed for an invalid projection."""

    current = project_current_claim_versions(claims)
    try:
        return current[str(claim_id)]
    except KeyError as exc:
        raise ValidationError("claim_id is not present in the projection") from exc


def validate_claim_history(claims: Iterable[ClaimVersion]) -> tuple[ClaimVersion, ...]:
    """Validate and return a stable version-first history ordering."""

    grouped = _group_claims(claims)
    project_current_claim_versions(tuple(item for values in grouped.values() for item in values))
    return tuple(
        sorted(
            (item for values in grouped.values() for item in values),
            key=lambda item: (str(item.claim_id), item.version),
        )
    )


def _criterion_is_blocking(criterion: Any) -> bool:
    if isinstance(criterion, CompletionResult):
        return False
    if isinstance(criterion, Mapping):
        required = bool(criterion.get("required", True))
        status = criterion.get("status")
    else:
        required = bool(getattr(criterion, "required", True))
        status = getattr(criterion, "status", None)
    if not required:
        return False
    if status is None:
        return True
    if not isinstance(status, CriterionStatus):
        try:
            status = CriterionStatus(status)
        except (TypeError, ValueError):
            return True
    return status in {
        CriterionStatus.UNVERIFIED,
        CriterionStatus.UNMET,
        CriterionStatus.NOT_RECORDED,
    }


def _criterion_blockers(criteria: Iterable[Any]) -> bool:
    return any(_criterion_is_blocking(item) for item in criteria)


def _claim_is_material(claim: ClaimVersion) -> bool:
    return claim.materiality is ClaimMateriality.MATERIAL


def _unresolved_material_conflict(claim: ClaimVersion) -> bool:
    conflict = claim.conflict
    return bool(
        claim.evidence_state is EvidenceState.CONFLICTED
        and conflict is not None
        and conflict.material
        and conflict.resolution is ConflictResolution.UNRESOLVED
    )


def assess_strength_eligibility(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    claims: Iterable[ClaimVersion],
    strength: JudgmentStrength | str | None = None,
    *,
    requested_strength: JudgmentStrength | str | None = None,
    required_criteria: Iterable[Any] = (),
    required_criterion_unverified: bool = False,
    missing_decisive_evidence: bool = False,
    blocking_conflict: bool = False,
    conflicts: Iterable[Conflict] = (),
) -> StrengthEligibility:
    """Determine whether a conclusion strength is honest for current claims.

    Material claims drive strength.  Non-material caveats remain visible but do
    not silently downgrade a conclusion.  A blocking issue always requires a
    held conclusion; a provisional conclusion is only appropriate for a
    bounded assumed/unverified material basis without a blocking issue.
    """

    if strength is None:
        strength = requested_strength
    elif requested_strength is not None and str(strength) != str(requested_strength):
        raise ValidationError("strength and requested_strength disagree")
    if strength is None:
        raise ValidationError("strength: a requested level is required")
    if not isinstance(strength, JudgmentStrength):
        try:
            strength = JudgmentStrength(strength)
        except (TypeError, ValueError) as exc:
            raise ValidationError("strength: unknown closed value") from exc
    current = tuple(claims)
    for claim in current:
        validate_claim_version_shape(claim)
    material = tuple(claim for claim in current if _claim_is_material(claim))
    reasons: list[str] = []
    if not material:
        reasons.append("missing_material_basis")
    supplied_conflicts = tuple(conflicts)
    unresolved_conflict = blocking_conflict or any(
        _unresolved_material_conflict(claim) for claim in material
    )
    unresolved_conflict = unresolved_conflict or any(
        getattr(conflict, "material", False)
        and getattr(conflict, "resolution", None) is ConflictResolution.UNRESOLVED
        for conflict in supplied_conflicts
    )
    if unresolved_conflict:
        reasons.append("unresolved_material_conflict")
    criterion_blocker = required_criterion_unverified or _criterion_blockers(required_criteria)
    if criterion_blocker:
        reasons.append("required_criterion_unverified")
    if missing_decisive_evidence:
        reasons.append("missing_decisive_evidence")

    weak_material = tuple(
        claim
        for claim in material
        if claim.evidence_state in {EvidenceState.ASSUMED, EvidenceState.UNVERIFIED}
    )
    if weak_material:
        reasons.append("material_basis_is_assumed_or_unverified")
    if any(claim.evidence_state is EvidenceState.CONFLICTED for claim in material):
        reasons.append("material_claim_is_conflicted")

    material_conflicted = any(
        claim.evidence_state is EvidenceState.CONFLICTED for claim in material
    )
    blocking_issue = (
        unresolved_conflict or missing_decisive_evidence or not material or material_conflicted
    )
    strong_blocker = blocking_issue or criterion_blocker
    eligible = True
    if strength is JudgmentStrength.HELD:
        # A user may explicitly hold even when no current blocker exists.
        eligible = True
    elif strength is JudgmentStrength.PROVISIONAL:
        eligible = bool(weak_material) and not blocking_issue
    elif strength is JudgmentStrength.SUPPORTED:
        eligible = bool(material) and not weak_material and not blocking_issue
    elif strength is JudgmentStrength.STRONGLY_SUPPORTED:
        eligible = (
            bool(material)
            and not strong_blocker
            and all(
                claim.evidence_state in {EvidenceState.VERIFIED, EvidenceState.COMPUTED}
                for claim in material
            )
        )
    if not eligible and not reasons:
        reasons.append("strength_requirements_not_met")
    # Keep deterministic order while avoiding duplicate reasons from multiple
    # independent checks.
    return StrengthEligibility(
        requested=strength,
        eligible=eligible,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def conclusion_strength_eligibility(
    claims: Iterable[ClaimVersion],
    strength: JudgmentStrength | str | None = None,
    **kwargs: Any,
) -> StrengthEligibility:
    """Compatibility alias for :func:`assess_strength_eligibility`."""

    return assess_strength_eligibility(claims, strength, **kwargs)


def is_strength_eligible(
    claims: Iterable[ClaimVersion],
    strength: JudgmentStrength | str,
    **kwargs: Any,
) -> bool:
    """Return only the fail-closed eligibility bit for a requested strength."""

    return assess_strength_eligibility(claims, strength, **kwargs).eligible


def claim_can_render_verified(
    claim: ClaimVersion,
    sources: Mapping[str, SourceReference] | Iterable[SourceReference] | None = None,
) -> bool:
    """Return whether a claim can be presented with the ``verified`` label.

    This is deliberately stricter than merely checking the enum.  A supplied
    source collection must contain every referenced ID, but semantic support is
    still the host model's responsibility and is not inferred here.
    """

    if not isinstance(claim, ClaimVersion):
        return False
    if (
        not claim.active
        or claim.evidence_state is not EvidenceState.VERIFIED
        or not claim.source_ids
    ):
        return False
    if claim.calculation is not None or claim.conflict is not None:
        return False
    if sources is None:
        return True
    if isinstance(sources, Mapping):
        available = {str(key): value for key, value in sources.items()}
    else:
        available = {str(item.source_id): item for item in sources}
    return all(
        str(source_id) in available and isinstance(available[str(source_id)], SourceReference)
        for source_id in claim.source_ids
    )


def can_render_verified(*args: Any, **kwargs: Any) -> bool:
    """Compatibility alias for :func:`claim_can_render_verified`."""

    return claim_can_render_verified(*args, **kwargs)


# Short aliases used by older callers and walkthroughs.
make_claim = make_claim_version
build_claim_version = make_claim_version
make_source = make_source_reference
build_source_reference = make_source_reference
make_conflict_record = make_conflict
build_conflict = make_conflict
current_versions = project_current_claim_versions
get_current_claim_versions = project_current_claim_versions
project_claim_versions = project_current_claim_versions
strength_eligibility = assess_strength_eligibility
eligible_strength = is_strength_eligible


__all__ = [
    "MAX_CLAIM_BASIS",
    "MAX_CLAIM_SOURCES",
    "StrengthEligibility",
    "assess_strength_eligibility",
    "build_claim_version",
    "build_conflict",
    "build_source_reference",
    "can_render_verified",
    "claim_can_render_verified",
    "conclusion_strength_eligibility",
    "construct_claim_version",
    "construct_conflict",
    "construct_source_reference",
    "current_claim_version",
    "current_versions",
    "get_current_claim_versions",
    "is_strength_eligible",
    "eligible_strength",
    "make_claim",
    "make_claim_version",
    "make_conflict",
    "make_conflict_record",
    "make_source",
    "make_source_reference",
    "project_current_claim_versions",
    "project_claim_versions",
    "revise_claim_version",
    "strength_eligibility",
    "validate_claim_history",
    "validate_claim_version_shape",
]
