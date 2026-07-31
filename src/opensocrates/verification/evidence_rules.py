"""Deterministic evidence-state, source-link, and strength rules.

The host model may propose public claim objects, but this module is the final
closed check before a claim/card can be recorded or presented as supported.
Rules return bounded typed violations.  A verifier exception is represented as
an error violation and never as an implicit pass.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..domain.enums import (
    ClaimMateriality,
    ConflictResolution,
    EvidenceState,
    JudgmentStrength,
    ViolationSeverity,
)
from ..domain.evidence import (
    MAX_CLAIM_BASIS,
    MAX_CLAIM_SOURCES,
    assess_strength_eligibility,
    claim_can_render_verified,
    project_current_claim_versions,
    validate_claim_version_shape,
)
from ..domain.models import (
    ClaimVersion,
    CompletionResult,
    SourceReference,
    Violation,
)
from ..domain.validation import validate_safe_text
from ..errors import ValidationError
from .calculation_rules import calculation_violations, verify_calculation
from .source_rules import collect_source_violations

MAX_EVIDENCE_VIOLATIONS = 32


def _violation(rule_id: str, field: str | None, message_key: str) -> Violation:
    return Violation(
        rule_id=rule_id,
        severity=ViolationSeverity.ERROR,
        message_key=message_key,
        field=field,
        repair_hint_key=None,
    )


def _bounded_append(violations: list[Violation], violation: Violation) -> None:
    if len(violations) < MAX_EVIDENCE_VIOLATIONS:
        violations.append(violation)


def _source_lookup(
    sources: Mapping[str, SourceReference] | Iterable[SourceReference] | None,
) -> dict[str, SourceReference] | None:
    if sources is None:
        return None
    if isinstance(sources, Mapping):
        return {str(key): value for key, value in sources.items()}
    return {str(source.source_id): source for source in sources}


def _claim_lookup(
    claims: Mapping[str, ClaimVersion] | Iterable[ClaimVersion] | None,
) -> dict[str, ClaimVersion] | None:
    if claims is None:
        return None
    if isinstance(claims, Mapping):
        return {str(key): value for key, value in claims.items()}
    result: dict[str, ClaimVersion] = {}
    for claim in claims:
        if not isinstance(claim, ClaimVersion):
            continue
        # Keep the highest version for basis-existence checks.  Current-version
        # projection is separately checked when requested.
        existing = result.get(str(claim.claim_id))
        if existing is None or claim.version > existing.version:
            result[str(claim.claim_id)] = claim
    return result


def _normal_claims(value: ClaimVersion | Iterable[ClaimVersion]) -> tuple[ClaimVersion, ...]:
    if isinstance(value, ClaimVersion):
        return (value,)
    try:
        return tuple(value)
    except TypeError as exc:
        raise ValidationError("claims must be a ClaimVersion or iterable") from exc


def _text_violation(violations: list[Violation], claim: ClaimVersion) -> None:
    try:
        validate_safe_text(
            claim.text,
            field_name="claim.text",
            max_length=600,
            allow_newline=False,
            allow_tab=False,
        )
        if not claim.text.strip():
            raise ValidationError("claim text is blank")
    except (ValidationError, TypeError, ValueError):
        _bounded_append(
            violations, _violation("OSV-EVIDENCE-001", "text", "evidence.claim_text_invalid")
        )


def _check_basis(
    violations: list[Violation],
    claim: ClaimVersion,
    known_claims: Mapping[str, ClaimVersion] | None,
) -> None:
    if len(claim.basis_claim_ids) > MAX_CLAIM_BASIS:
        _bounded_append(
            violations, _violation("OSV-EVIDENCE-002", "basis_claim_ids", "evidence.basis_limit")
        )
    if len(set(claim.basis_claim_ids)) != len(claim.basis_claim_ids):
        _bounded_append(
            violations, _violation("OSV-EVIDENCE-003", "basis_claim_ids", "evidence.basis_unique")
        )
    for index, basis_id in enumerate(claim.basis_claim_ids):
        if str(basis_id) == str(claim.claim_id):
            _bounded_append(
                violations,
                _violation("OSV-EVIDENCE-004", f"basis_claim_ids[{index}]", "evidence.basis_self"),
            )
        if known_claims is not None and str(basis_id) not in known_claims:
            _bounded_append(
                violations,
                _violation(
                    "OSV-EVIDENCE-005", f"basis_claim_ids[{index}]", "evidence.basis_unknown"
                ),
            )


def _check_sources(
    violations: list[Violation],
    claim: ClaimVersion,
    source_lookup: Mapping[str, SourceReference] | None,
) -> None:
    if len(claim.source_ids) > MAX_CLAIM_SOURCES:
        _bounded_append(
            violations, _violation("OSV-SOURCE-012", "source_ids", "source.reference_limit")
        )
    if len(set(claim.source_ids)) != len(claim.source_ids):
        _bounded_append(
            violations, _violation("OSV-SOURCE-013", "source_ids", "source.reference_unique")
        )
    if source_lookup is None:
        return
    for index, source_id in enumerate(claim.source_ids):
        source = source_lookup.get(str(source_id))
        if not isinstance(source, SourceReference):
            _bounded_append(
                violations,
                _violation("OSV-SOURCE-014", f"source_ids[{index}]", "source.reference_unknown"),
            )
            continue
        for source_violation in collect_source_violations(source):
            _bounded_append(violations, source_violation)


def collect_claim_violations(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    claim: ClaimVersion,
    *,
    sources: Mapping[str, SourceReference] | Iterable[SourceReference] | None = None,
    known_claims: Mapping[str, ClaimVersion] | Iterable[ClaimVersion] | None = None,
) -> tuple[Violation, ...]:
    """Validate one claim's immutable version and exact evidence-state shape."""

    if not isinstance(claim, ClaimVersion):
        return (_violation("OSV-EVIDENCE-000", None, "evidence.claim_invalid"),)
    violations: list[Violation] = []
    source_lookup = _source_lookup(sources)
    claim_lookup = _claim_lookup(known_claims)
    _text_violation(violations, claim)
    if not isinstance(claim.version, int) or isinstance(claim.version, bool) or claim.version < 1:
        _bounded_append(
            violations, _violation("OSV-EVIDENCE-006", "version", "evidence.version_positive")
        )
    if not isinstance(claim.active, bool):
        _bounded_append(
            violations, _violation("OSV-EVIDENCE-007", "active", "evidence.active_boolean")
        )
    _check_sources(violations, claim, source_lookup)
    _check_basis(violations, claim, claim_lookup)

    try:
        validate_claim_version_shape(claim)
    except (ValidationError, TypeError, ValueError):
        # State-specific branches below provide stable, field-level reasons;
        # this generic code covers a malformed model created outside the helper.
        _bounded_append(
            violations, _violation("OSV-EVIDENCE-008", None, "evidence.state_invariant")
        )

    state = claim.evidence_state
    if not isinstance(state, EvidenceState):
        _bounded_append(
            violations, _violation("OSV-EVIDENCE-009", "evidence_state", "evidence.state_unknown")
        )
        return tuple(violations[:MAX_EVIDENCE_VIOLATIONS])
    if claim.materiality not in {ClaimMateriality.MATERIAL, ClaimMateriality.NON_MATERIAL}:
        _bounded_append(
            violations,
            _violation("OSV-EVIDENCE-010", "materiality", "evidence.materiality_unknown"),
        )

    if state is EvidenceState.VERIFIED:
        if not claim.source_ids:
            _bounded_append(
                violations,
                _violation("OSV-EVIDENCE-011", "source_ids", "evidence.verified_source_required"),
            )
        if claim.calculation is not None or claim.conflict is not None:
            _bounded_append(
                violations,
                _violation("OSV-EVIDENCE-012", None, "evidence.verified_no_derived_support"),
            )
        if (
            claim.active
            and source_lookup is not None
            and not claim_can_render_verified(claim, source_lookup)
        ):
            _bounded_append(
                violations,
                _violation("OSV-EVIDENCE-013", "source_ids", "evidence.verified_source_invalid"),
            )
    elif state is EvidenceState.COMPUTED:
        if claim.calculation is None:
            _bounded_append(
                violations,
                _violation(
                    "OSV-EVIDENCE-014", "calculation", "evidence.computed_calculation_required"
                ),
            )
        else:
            result = verify_calculation(claim.calculation, sources=source_lookup)
            if not result.ok:
                for item in calculation_violations(claim.calculation, sources=source_lookup):
                    _bounded_append(violations, item)
        if claim.conflict is not None:
            _bounded_append(
                violations,
                _violation("OSV-EVIDENCE-015", "conflict", "evidence.computed_no_conflict"),
            )
    elif state is EvidenceState.INFERRED:
        if not claim.basis_claim_ids:
            _bounded_append(
                violations,
                _violation(
                    "OSV-EVIDENCE-016", "basis_claim_ids", "evidence.inferred_basis_required"
                ),
            )
        if claim.calculation is not None or claim.conflict is not None:
            _bounded_append(
                violations,
                _violation("OSV-EVIDENCE-017", None, "evidence.inferred_no_derived_support"),
            )
    elif state is EvidenceState.ASSUMED:
        if (
            claim.source_ids
            or claim.basis_claim_ids
            or claim.calculation is not None
            or claim.conflict is not None
        ):
            _bounded_append(
                violations, _violation("OSV-EVIDENCE-018", None, "evidence.assumed_empty_support")
            )
    elif state is EvidenceState.UNVERIFIED:
        if claim.calculation is not None or claim.conflict is not None:
            _bounded_append(
                violations, _violation("OSV-EVIDENCE-019", None, "evidence.unverified_bounded")
            )
    elif state is EvidenceState.CONFLICTED:
        if claim.conflict is None:
            _bounded_append(
                violations, _violation("OSV-CONFLICT-001", "conflict", "conflict.required")
            )
        has_two_sources = len(claim.source_ids) >= 2
        has_source_and_basis = bool(claim.source_ids) and bool(
            claim.basis_claim_ids or claim.calculation is not None
        )
        if not (has_two_sources or has_source_and_basis):
            _bounded_append(
                violations,
                _violation("OSV-CONFLICT-002", None, "conflict.source_or_basis_required"),
            )
        if (
            claim.conflict is not None
            and claim.conflict.resolution is ConflictResolution.UNRESOLVED
        ):
            if not claim.conflict.material and claim.materiality is ClaimMateriality.MATERIAL:
                _bounded_append(
                    violations,
                    _violation(
                        "OSV-CONFLICT-003", "conflict.material", "conflict.materiality_mismatch"
                    ),
                )
        if claim.conflict is not None and claim.conflict.source_ids:
            if not set(claim.conflict.source_ids).issubset(set(claim.source_ids)):
                _bounded_append(
                    violations,
                    _violation(
                        "OSV-CONFLICT-004", "conflict.source_ids", "conflict.sources_not_claimed"
                    ),
                )
    return tuple(violations[:MAX_EVIDENCE_VIOLATIONS])


def _criterion_items(criteria: Iterable[Any]) -> tuple[Any, ...]:
    flattened: list[Any] = []
    for item in criteria:
        if isinstance(item, CompletionResult):
            flattened.extend(item.criteria)
        else:
            flattened.append(item)
    return tuple(flattened)


def collect_strength_violations(
    claims: Iterable[ClaimVersion],
    strength: JudgmentStrength | str,
    *,
    required_criteria: Iterable[Any] = (),
    required_criterion_unverified: bool = False,
    missing_decisive_evidence: bool = False,
    blocking_conflict: bool = False,
    conflicts: Iterable[Any] = (),
) -> tuple[Violation, ...]:
    """Validate requested conclusion strength against current public claims."""

    current = tuple(claims)
    try:
        assessment = assess_strength_eligibility(
            current,
            strength,
            required_criteria=_criterion_items(required_criteria),
            required_criterion_unverified=required_criterion_unverified,
            missing_decisive_evidence=missing_decisive_evidence,
            blocking_conflict=blocking_conflict,
            conflicts=conflicts,
        )
    except (ValidationError, TypeError, ValueError):
        return (_violation("OSV-STRENGTH-000", "strength", "evidence.strength_invalid"),)
    if assessment.eligible:
        return ()
    reason_to_rule = {
        "missing_material_basis": ("OSV-STRENGTH-001", "evidence.material_basis_required"),
        "unresolved_material_conflict": ("OSV-STRENGTH-002", "conflict.must_hold_or_lower"),
        "required_criterion_unverified": (
            "OSV-STRENGTH-003",
            "completion.required_criterion_unverified",
        ),
        "missing_decisive_evidence": ("OSV-STRENGTH-004", "evidence.decisive_missing"),
        "material_basis_is_assumed_or_unverified": (
            "OSV-STRENGTH-005",
            "evidence.strong_support_required",
        ),
        "material_claim_is_conflicted": ("OSV-STRENGTH-006", "conflict.must_resolve_or_hold"),
        "strength_requirements_not_met": ("OSV-STRENGTH-007", "evidence.strength_requirements"),
    }
    violations: list[Violation] = []
    for reason in assessment.reason_codes:
        rule_id, message_key = reason_to_rule.get(
            reason,
            ("OSV-STRENGTH-007", "evidence.strength_requirements"),
        )
        _bounded_append(violations, _violation(rule_id, "strength", message_key))
    return tuple(violations[:MAX_EVIDENCE_VIOLATIONS])


def collect_claim_history_violations(claims: Iterable[ClaimVersion]) -> tuple[Violation, ...]:
    """Validate one-active-current-version projection invariants."""

    history = tuple(claims)
    try:
        project_current_claim_versions(history)
    except (ValidationError, TypeError, ValueError):
        return (
            _violation("OSV-EVIDENCE-020", "claim_history", "evidence.current_version_projection"),
        )
    return ()


def collect_evidence_violations(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    claims: ClaimVersion | Iterable[ClaimVersion],
    *,
    sources: Mapping[str, SourceReference] | Iterable[SourceReference] | None = None,
    known_claims: Mapping[str, ClaimVersion] | Iterable[ClaimVersion] | None = None,
    strength: JudgmentStrength | str | None = None,
    required_criteria: Iterable[Any] = (),
    required_criterion_unverified: bool = False,
    missing_decisive_evidence: bool = False,
    blocking_conflict: bool = False,
    conflicts: Iterable[Any] = (),
    require_current_projection: bool = False,
) -> tuple[Violation, ...]:
    """Validate claims, source references, state invariants, and strength."""

    try:
        current = _normal_claims(claims)
    except (ValidationError, TypeError, ValueError):
        return (_violation("OSV-EVIDENCE-000", None, "evidence.claim_invalid"),)
    if not current:
        return (_violation("OSV-EVIDENCE-021", "claims", "evidence.claim_required"),)
    source_lookup = _source_lookup(sources)
    claim_lookup = _claim_lookup(known_claims) or _claim_lookup(current)
    violations: list[Violation] = []
    for claim in current:
        for item in collect_claim_violations(
            claim, sources=source_lookup, known_claims=claim_lookup
        ):
            _bounded_append(violations, item)
    if require_current_projection or len(current) > 1:
        for item in collect_claim_history_violations(current):
            _bounded_append(violations, item)
    strength_claims = current
    if strength is not None:
        try:
            strength_claims = tuple(project_current_claim_versions(current).values())
        except (ValidationError, TypeError, ValueError):
            # The history violation above is authoritative for an invalid
            # projection; preserve the supplied claims so strength still
            # fails closed and reports any independent blockers.
            strength_claims = current
        for item in collect_strength_violations(
            strength_claims,
            strength,
            required_criteria=required_criteria,
            required_criterion_unverified=required_criterion_unverified,
            missing_decisive_evidence=missing_decisive_evidence,
            blocking_conflict=blocking_conflict,
            conflicts=conflicts,
        ):
            _bounded_append(violations, item)
    # Stable de-duplication avoids repeated source errors from multiple claims.
    unique: list[Violation] = []
    seen: set[tuple[str, str | None]] = set()
    for item in violations:
        key = (str(item.rule_id), item.field)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return tuple(unique[:MAX_EVIDENCE_VIOLATIONS])


def enforce_evidence_rules(
    claims: ClaimVersion | Iterable[ClaimVersion],
    **kwargs: Any,
) -> tuple[ClaimVersion, ...]:
    """Raise unless all evidence and optional strength rules pass."""

    normalized = _normal_claims(claims)
    violations = collect_evidence_violations(normalized, **kwargs)
    if violations:
        details = ", ".join(item.rule_id for item in violations)
        raise ValidationError(f"evidence verification failed: {details}")
    return normalized


def is_valid_evidence(
    claims: ClaimVersion | Iterable[ClaimVersion],
    **kwargs: Any,
) -> bool:
    """Return the fail-closed evidence validity bit."""

    return not collect_evidence_violations(claims, **kwargs)


# Names shared with card/verifier callers.
validate_evidence_rules = collect_evidence_violations
verify_evidence = collect_evidence_violations
check_evidence = collect_evidence_violations
verify_claim = collect_claim_violations
verify_claims = collect_evidence_violations
validate_claim = collect_claim_violations
check_claim = collect_claim_violations


__all__ = [
    "MAX_EVIDENCE_VIOLATIONS",
    "check_evidence",
    "check_claim",
    "collect_claim_history_violations",
    "collect_claim_violations",
    "collect_evidence_violations",
    "collect_strength_violations",
    "enforce_evidence_rules",
    "is_valid_evidence",
    "validate_evidence_rules",
    "validate_claim",
    "verify_claim",
    "verify_claims",
    "verify_evidence",
]
