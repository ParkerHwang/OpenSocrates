"""Deterministic completion/card/evidence projection rules.

The parser, card rules, and evidence/calculation rules are supplied at the
boundary.  This module only compares their typed public projections and
returns stable :class:`Violation` values.  It never fetches sources, infers
semantic truth, reads a transcript, or turns an exception into a pass.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from ..domain.completion import (
    MAX_COMPLETION_CRITERIA,
    required_criterion_gaps,
)
from ..domain.enums import (
    AlternativeDisposition,
    CriterionKind,
    CriterionStatus,
    EvidenceState,
    TaskState,
    ViolationSeverity,
)
from ..domain.models import CompletionCriterion, ConclusionCard, Violation

MAX_RULE_VIOLATIONS = 64


@dataclass(frozen=True, slots=True)
class CompletionRuleContext:
    """Typed boundary bundle for callers that prefer one request object."""

    card: ConclusionCard
    task_projection: object | None = None
    framing: object | None = None
    current_judgment: object | None = None
    claim_versions: object = ()
    criterion_statuses: object | None = None
    alternatives: object = ()
    conflicts: object = ()
    card_violations: tuple[Violation, ...] = ()
    evidence_violations: tuple[Violation, ...] = ()
    capability_profile: object | None = None
    public_claim_changed: bool = False


def _get(value: object | None, name: str, default: object = None) -> object:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_text(value: object) -> str:
    return str(getattr(value, "value", value))


def _as_status(value: object) -> CriterionStatus | None:
    if isinstance(value, CriterionStatus):
        return value
    try:
        return CriterionStatus(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_state(value: object) -> EvidenceState | None:
    if isinstance(value, EvidenceState):
        return value
    try:
        return EvidenceState(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _violation(
    rule_id: str,
    message_key: str,
    *,
    field: str | None = None,
    repair_hint_key: str | None = "repair.group",
    severity: ViolationSeverity = ViolationSeverity.ERROR,
) -> Violation:
    return Violation(
        rule_id=rule_id,
        severity=severity,
        message_key=message_key,
        field=field,
        repair_hint_key=repair_hint_key,
    )


def _append(result: list[Violation], item: Violation) -> None:
    if not isinstance(item, Violation):
        return
    if not isinstance(item.repair_hint_key, str) or not item.repair_hint_key.startswith("repair."):
        item = replace(item, repair_hint_key="repair.group")
    key = (str(item.rule_id), str(item.field or ""), str(item.message_key), str(item.severity))
    if any(
        (
            str(existing.rule_id),
            str(existing.field or ""),
            str(existing.message_key),
            str(existing.severity),
        )
        == key
        for existing in result
    ):
        return
    if len(result) < MAX_RULE_VIOLATIONS:
        result.append(item)


def _extend(result: list[Violation], values: Iterable[object]) -> None:
    for value in values:
        if isinstance(value, Violation):
            _append(result, value)


def _claim_items(claim_versions: object) -> tuple[object, ...]:
    if claim_versions is None:
        return ()
    if isinstance(claim_versions, Mapping):
        values: list[object] = []
        for value in claim_versions.values():
            if isinstance(value, (tuple, list, set, frozenset)):
                values.extend(value)
            else:
                values.append(value)
        return tuple(values)
    if isinstance(claim_versions, (str, bytes)):
        return ()
    try:
        return tuple(claim_versions)  # type: ignore[arg-type]
    except TypeError:
        return ()


def _current_claims(claim_versions: object) -> tuple[dict[str, object], tuple[str, ...]]:
    """Select active current claims and report malformed duplicate projections."""

    grouped: dict[str, list[object]] = {}
    for claim in _claim_items(claim_versions):
        claim_id = _get(claim, "claim_id")
        if claim_id is None:
            continue
        grouped.setdefault(str(claim_id), []).append(claim)
    current: dict[str, object] = {}
    invalid: list[str] = []
    for claim_id, values in grouped.items():
        active = [value for value in values if bool(_get(value, "active", True))]
        if len(active) != 1:
            invalid.append(claim_id)
            continue
        selected = active[0]
        # If a history is supplied, only the highest active version can be
        # current.  A direct mapping with one value remains valid.
        versions = [
            _get(value, "version")
            for value in values
            if isinstance(_get(value, "version"), int)
            and not isinstance(_get(value, "version"), bool)
        ]
        if versions and _get(selected, "version") != max(versions):  # type: ignore[type-var]  # Closed runtime boundary validates this value.
            invalid.append(claim_id)
            continue
        current[claim_id] = selected
    return current, tuple(sorted(invalid))


def _criteria_from_framing(framing: object | None) -> tuple[object, ...]:
    values = _get(framing, "completion_criteria", ())
    if values is None or isinstance(values, (str, bytes)):
        return ()
    try:
        return tuple(values)  # type: ignore[arg-type]
    except TypeError:
        return ()


def _explicit_statuses(value: object | None) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if isinstance(value, (str, bytes)):
        return {}
    result: dict[str, object] = {}
    try:
        values = tuple(value)  # type: ignore[arg-type, var-annotated]  # Closed runtime boundary validates this value.
    except TypeError:
        return result
    for item in values:
        criterion_id = _get(item, "criterion_id")
        if criterion_id is not None:
            result[str(criterion_id)] = item
    return result


def _criterion_kind(value: object) -> CriterionKind | None:
    raw = _get(value, "kind")
    if isinstance(raw, CriterionKind):
        return raw
    try:
        return CriterionKind(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _criterion_reason(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value[:400]
    return "criterion"


def _criterion_status(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    criterion: object,
    *,
    card_valid: bool,
    claims: Mapping[str, object],
    explicit: Mapping[str, object],
    privacy_violation: bool,
) -> tuple[CriterionStatus, str]:
    criterion_id = str(_get(criterion, "criterion_id", ""))
    override = explicit.get(criterion_id)
    if override is not None:
        raw_status = _get(override, "status", override)
        status = _as_status(raw_status)
        if status is not None:
            return status, _criterion_reason(
                _get(override, "reason"),
                _get(override, "text"),
                _get(criterion, "reason"),
                _get(criterion, "text"),
                criterion_id,
            )
        return CriterionStatus.NOT_RECORDED, _criterion_reason(
            _get(override, "reason"),
            _get(override, "text"),
            _get(criterion, "reason"),
            _get(criterion, "text"),
            criterion_id,
        )

    explicit_status = _as_status(_get(criterion, "status"))
    if explicit_status is not None:
        return explicit_status, _criterion_reason(
            _get(criterion, "reason"),
            _get(criterion, "text"),
            criterion_id,
        )

    kind = _criterion_kind(criterion)
    if kind is CriterionKind.CARD_CONTRACT:
        return _criterion_status_value(
            CriterionStatus.MET if card_valid else CriterionStatus.UNMET,
            criterion,
            criterion_id,
        )
    if kind is CriterionKind.EVIDENTIARY:
        ids = _get(criterion, "evidence_claim_ids", ())
        try:
            claim_ids = tuple(str(item) for item in ids)  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        except TypeError:
            claim_ids = ()
        if not claim_ids:
            return _criterion_status_value(CriterionStatus.NOT_RECORDED, criterion, criterion_id)
        states = [
            _as_state(_get(claims[item], "evidence_state")) for item in claim_ids if item in claims
        ]
        if len(states) != len(claim_ids):
            return _criterion_status_value(CriterionStatus.NOT_RECORDED, criterion, criterion_id)
        if any(state is EvidenceState.CONFLICTED for state in states):
            return _criterion_status_value(CriterionStatus.UNMET, criterion, criterion_id)
        if any(state in {EvidenceState.UNVERIFIED, EvidenceState.ASSUMED} for state in states):
            return _criterion_status_value(CriterionStatus.UNVERIFIED, criterion, criterion_id)
        if any(state is None for state in states):
            return _criterion_status_value(CriterionStatus.NOT_RECORDED, criterion, criterion_id)
        return _criterion_status_value(CriterionStatus.MET, criterion, criterion_id)
    if privacy_violation:
        return _criterion_status_value(CriterionStatus.UNMET, criterion, criterion_id)
    # Structural, user-constraint, and safety semantics are not inferred from
    # free-form criterion prose.  Callers can provide explicit statuses when a
    # host has published the corresponding public result.
    return _criterion_status_value(CriterionStatus.NOT_RECORDED, criterion, criterion_id)


def _criterion_status_value(
    status: CriterionStatus,
    criterion: object,
    criterion_id: str,
) -> tuple[CriterionStatus, str]:
    return status, _criterion_reason(
        _get(criterion, "reason"),
        _get(criterion, "text"),
        criterion_id,
    )


def evaluate_completion_criteria(
    framing: object | None,
    *,
    card_valid: bool,
    claim_versions: object = (),
    criterion_statuses: object | None = None,
    privacy_violation: bool = False,
) -> tuple[CompletionCriterion, ...]:
    """Evaluate only statuses that are mechanically observable at completion."""

    raw = _criteria_from_framing(framing)
    if len(raw) > MAX_COMPLETION_CRITERIA:
        raw = raw[:MAX_COMPLETION_CRITERIA]
    current, _ = _current_claims(claim_versions)
    explicit = _explicit_statuses(criterion_statuses)
    result: list[CompletionCriterion] = []
    for item in raw:
        criterion_id = _get(item, "criterion_id")
        if not isinstance(criterion_id, str) or not criterion_id:
            continue
        status, reason = _criterion_status(
            item,
            card_valid=card_valid,
            claims=current,
            explicit=explicit,
            privacy_violation=privacy_violation,
        )
        required = bool(_get(item, "required", True))
        result.append(
            CompletionCriterion(
                criterion_id=criterion_id,
                status=status,
                reason=reason[:400],
                required=required,
            )
        )
    return tuple(result)


def _choice_requires_alternative(
    framing: object | None,
    task_projection: object | None,
    current_judgment: object | None,
) -> bool:
    for item in (framing, task_projection, current_judgment):
        value = _get(item, "requires_alternative", None)
        if isinstance(value, bool):
            if value:
                return True
        shape = _as_text(_get(item, "answer_shape", ""))
        if "decision" in shape or "choice" in shape:
            return True
    alternative_ids = _get(current_judgment, "alternative_ids", ())
    try:
        return bool(tuple(alternative_ids))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    except TypeError:
        return False


def _alternative_items(alternatives: object) -> tuple[object, ...]:
    if alternatives is None or isinstance(alternatives, (str, bytes)):
        return ()
    if isinstance(alternatives, Mapping):
        return tuple(alternatives.values())
    try:
        return tuple(alternatives)  # type: ignore[arg-type]
    except TypeError:
        return ()


def collect_completion_violations(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    card: ConclusionCard | CompletionRuleContext,
    task_projection: object | None = None,
    framing: object | None = None,
    current_judgment: object | None = None,
    claim_versions: object = (),
    *,
    criterion_statuses: object | None = None,
    alternatives: object = (),
    conflicts: object = (),
    card_violations: Iterable[Violation] = (),
    evidence_violations: Iterable[Violation] = (),
    capability_profile: object | None = None,
    public_claim_changed: bool = False,
) -> tuple[Violation, ...]:
    """Return stable blocking/warning violations for one current card projection."""

    if isinstance(card, CompletionRuleContext):
        context = card
        card = context.card
        if task_projection is None:
            task_projection = context.task_projection
        if framing is None:
            framing = context.framing
        if current_judgment is None:
            current_judgment = context.current_judgment
        if claim_versions == ():
            claim_versions = context.claim_versions
        if criterion_statuses is None:
            criterion_statuses = context.criterion_statuses
        if alternatives == ():
            alternatives = context.alternatives
        if conflicts == ():
            conflicts = context.conflicts
        if card_violations == ():
            card_violations = context.card_violations
        if evidence_violations == ():
            evidence_violations = context.evidence_violations
        if capability_profile is None:
            capability_profile = context.capability_profile
        public_claim_changed = public_claim_changed or context.public_claim_changed

    result: list[Violation] = []
    if not isinstance(card, ConclusionCard):
        return (_violation("OSV-CARD-011", "card.invalid", field="/card"),)

    incoming_card = tuple(item for item in card_violations if isinstance(item, Violation))
    _extend(result, incoming_card)
    _extend(result, evidence_violations)

    if task_projection is None:
        _append(
            result,
            _violation(
                "OSV-CAPABILITY-001",
                "capability.current_projection_missing",
                field="/task_projection",
            ),
        )
    else:
        task_id = _get(task_projection, "task_id")
        if task_id is not None and str(card.task_id) != str(task_id):
            _append(result, _violation("OSV-CARD-011", "card.task_mismatch", field="/task_id"))
        locale = _get(task_projection, "locale")
        if locale is not None and str(card.locale) != _as_text(locale):
            _append(
                result, _violation("OSV-LOCALE-002", "locale.card_task_mismatch", field="/locale")
            )
        state = _get(task_projection, "state")
        if state is not None and _as_text(state) in {
            TaskState.BYPASSED.value,
            TaskState.CANCELLED.value,
        }:
            _append(
                result,
                _violation(
                    "OSV-CAPABILITY-004",
                    "capability.task_not_judgment",
                    field="/task_projection.state",
                ),
            )

    if current_judgment is None:
        _append(
            result,
            _violation(
                "OSV-CAPABILITY-002",
                "capability.current_judgment_missing",
                field="/current_judgment",
            ),
        )
    else:
        task_judgment_id = _get(task_projection, "current_judgment_id")
        judgment_id = _get(current_judgment, "judgment_id")
        if (
            task_judgment_id is not None
            and judgment_id is not None
            and str(task_judgment_id) != str(judgment_id)
        ):
            _append(
                result, _violation("OSV-CARD-012", "card.judgment_mismatch", field="/judgment_id")
            )
        if judgment_id is not None and str(card.judgment_id) != str(judgment_id):
            _append(
                result, _violation("OSV-CARD-012", "card.judgment_mismatch", field="/judgment_id")
            )
        version = _get(current_judgment, "version")
        if (
            isinstance(version, int)
            and not isinstance(version, bool)
            and card.judgment_version != version
        ):
            _append(
                result, _violation("OSV-CARD-013", "card.version_stale", field="/judgment_version")
            )
        conclusion = _get(current_judgment, "conclusion")
        if isinstance(conclusion, str) and conclusion and card.conclusion != conclusion:
            _append(
                result, _violation("OSV-CARD-014", "card.conclusion_stale", field="/conclusion")
            )
        strength = _get(current_judgment, "strength")
        if strength is not None and _as_text(card.strength) != _as_text(strength):
            _append(result, _violation("OSV-CARD-015", "card.strength_mismatch", field="/strength"))
        expected_ground_ids = _get(current_judgment, "ground_claim_ids", ())
        try:
            ground_ids = tuple(str(item) for item in expected_ground_ids)  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        except TypeError:
            ground_ids = ()
        actual_ground_ids = tuple(str(item.claim_id) for item in card.grounds)
        if ground_ids and actual_ground_ids != ground_ids:
            _append(
                result, _violation("OSV-CARD-016", "card.ground_ids_mismatch", field="/grounds")
            )
        elif not ground_ids and actual_ground_ids:
            _append(result, _violation("OSV-CARD-016", "card.ground_ids_missing", field="/grounds"))

    current_claims, invalid_claims = _current_claims(claim_versions)
    for claim_id in invalid_claims:
        _append(
            result,
            _violation(
                "OSV-EVIDENCE-012", "evidence.current_claim_invalid", field=f"/claims/{claim_id}"
            ),
        )
    for index, ground in enumerate(card.grounds):
        claim_id = str(ground.claim_id)
        claim = current_claims.get(claim_id)
        if claim is None:
            _append(
                result,
                _violation(
                    "OSV-EVIDENCE-010",
                    "evidence.current_claim_missing",
                    field=f"/grounds/{index}/claim_id",
                ),
            )
            continue
        current_state = _as_state(_get(claim, "evidence_state"))
        if current_state is None or current_state is not ground.state:
            _append(
                result,
                _violation(
                    "OSV-EVIDENCE-011", "evidence.state_mismatch", field=f"/grounds/{index}/state"
                ),
            )
        claim_text = _get(claim, "text")
        if isinstance(claim_text, str) and claim_text and claim_text != ground.text:
            _append(
                result,
                _violation(
                    "OSV-EVIDENCE-014", "evidence.claim_text_stale", field=f"/grounds/{index}/text"
                ),
            )

    for conflict in _alternative_items(conflicts):
        material = bool(_get(conflict, "material", False))
        resolution = _as_text(_get(conflict, "resolution", "unresolved"))
        if material and resolution == "unresolved":
            _append(
                result,
                _violation("OSV-CONFLICT-003", "conflict.material_unresolved", field="/conflicts"),
            )
    for claim in current_claims.values():
        conflict = _get(claim, "conflict")
        if _as_state(_get(claim, "evidence_state")) is EvidenceState.CONFLICTED and bool(
            _get(conflict, "material", False)
        ):
            if _as_text(_get(conflict, "resolution", "unresolved")) == "unresolved":
                _append(
                    result,
                    _violation("OSV-CONFLICT-003", "conflict.material_unresolved", field="/claims"),
                )

    if public_claim_changed:
        _append(
            result,
            _violation(
                "OSV-COMPLETION-006", "completion.new_candidate_required", field="/candidate"
            ),
        )

    choice_required = _choice_requires_alternative(framing, task_projection, current_judgment)
    if choice_required:
        alternatives_items = _alternative_items(alternatives)
        non_selected = [
            item
            for item in alternatives_items
            if _as_text(_get(item, "disposition", "")) != AlternativeDisposition.SELECTED.value
        ]
        if not non_selected:
            _append(
                result,
                _violation(
                    "OSV-COMPLETION-007", "completion.alternative_required", field="/alternatives"
                ),
            )

    privacy_violation = any(str(item.rule_id).startswith("OSV-PRIVACY-") for item in incoming_card)
    raw_criteria = _criteria_from_framing(framing)
    if len(raw_criteria) > MAX_COMPLETION_CRITERIA:
        _append(
            result,
            _violation(
                "OSV-COMPLETION-008",
                "completion.criteria_limit",
                field="/completion_criteria",
            ),
        )
    criterion_ids: set[str] = set()
    for index, raw_criterion in enumerate(raw_criteria[:MAX_COMPLETION_CRITERIA]):
        criterion_id = _get(raw_criterion, "criterion_id")
        if not isinstance(criterion_id, str) or not criterion_id:
            _append(
                result,
                _violation(
                    "OSV-COMPLETION-008",
                    "completion.criterion_id_invalid",
                    field=f"/completion_criteria/{index}/criterion_id",
                ),
            )
        elif criterion_id in criterion_ids:
            _append(
                result,
                _violation(
                    "OSV-COMPLETION-008",
                    "completion.criterion_id_duplicate",
                    field=f"/completion_criteria/{index}/criterion_id",
                ),
            )
        else:
            criterion_ids.add(criterion_id)

    criteria = evaluate_completion_criteria(
        framing,
        card_valid=not any(item.severity is ViolationSeverity.ERROR for item in incoming_card),
        claim_versions=claim_versions,
        criterion_statuses=criterion_statuses,
        privacy_violation=privacy_violation,
    )
    if not criteria:
        _append(
            result,
            _violation(
                "OSV-COMPLETION-005", "completion.criteria_missing", field="/completion_criteria"
            ),
        )
    else:
        required = tuple(item for item in criteria if item.required)
        if not required:
            _append(
                result,
                _violation(
                    "OSV-COMPLETION-005",
                    "completion.required_criterion_missing",
                    field="/completion_criteria",
                ),
            )
        for gap in required_criterion_gaps(criteria):
            rule_id = {
                CriterionStatus.UNMET: "OSV-COMPLETION-001",
                CriterionStatus.UNVERIFIED: "OSV-COMPLETION-002",
                CriterionStatus.NOT_RECORDED: "OSV-COMPLETION-003",
                CriterionStatus.NOT_APPLICABLE: "OSV-COMPLETION-004",
                None: "OSV-COMPLETION-003",
            }[gap.status]
            message_key = {
                CriterionStatus.UNMET: "completion.required_unmet",
                CriterionStatus.UNVERIFIED: "completion.required_unverified",
                CriterionStatus.NOT_RECORDED: "completion.required_not_recorded",
                CriterionStatus.NOT_APPLICABLE: "completion.required_not_applicable",
                None: "completion.required_not_recorded",
            }[gap.status]
            _append(
                result,
                _violation(rule_id, message_key, field=f"/completion_criteria/{gap.criterion_id}"),
            )

    # Capability entries are warnings when a verifier can still validate the
    # supplied final message; they never erase a blocking error.  Stop owns the
    # hard continuation capability check.
    if capability_profile is not None:
        capabilities = _get(capability_profile, "capabilities", {})
        if isinstance(capabilities, Mapping):
            entry = capabilities.get("completion_candidate_observation")
            status = _as_text(_get(entry, "status", entry)) if entry is not None else "unknown"
            if status not in {"supported", "degraded"}:
                _append(
                    result,
                    _violation(
                        "OSV-CAPABILITY-003",
                        "capability.completion_observation_unavailable",
                        field="/capability_profile",
                        severity=ViolationSeverity.WARNING,
                    ),
                )
    return tuple(result[:MAX_RULE_VIOLATIONS])


def completion_criteria_for(
    framing: object | None,
    *,
    card_valid: bool,
    claim_versions: object = (),
    criterion_statuses: object | None = None,
    privacy_violation: bool = False,
) -> tuple[CompletionCriterion, ...]:
    """Compatibility façade for callers that need evaluated criteria only."""

    return evaluate_completion_criteria(
        framing,
        card_valid=card_valid,
        claim_versions=claim_versions,
        criterion_statuses=criterion_statuses,
        privacy_violation=privacy_violation,
    )


validate_completion_rules = collect_completion_violations
check_completion = collect_completion_violations
collect_violations = collect_completion_violations


__all__ = [
    "CompletionRuleContext",
    "MAX_RULE_VIOLATIONS",
    "check_completion",
    "collect_completion_violations",
    "collect_violations",
    "completion_criteria_for",
    "evaluate_completion_criteria",
    "validate_completion_rules",
]
