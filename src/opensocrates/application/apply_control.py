"""Application service for the closed host-model control protocol.

This service is deliberately boring at the boundary: parse one closed control,
resolve one opaque token, validate one legal transition, and either append
typed public events or advance only the content-free ephemeral state.  It never
accepts native host envelopes and never stores raw model input.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from threading import RLock
from typing import Any, Protocol

from ..clock import Clock, SystemClock, utc_date, utc_timestamp
from ..constants import MAX_CONTROL_ACCEPTED_CONTROLS, MAX_HOST_CONTROL_RESULT_BYTES
from ..domain.enums import (
    CapabilityStatus,
    EventType,
    HostControlErrorCode,
    HostControlMessageType,
    HostControlNextAction,
    HostControlReasonCode,
    HostControlStatus,
    JudgmentState,
    Participation,
    RecordEventType,
    Rigor,
    RoundingMode,
    SourceKind,
    TaskState,
)
from ..domain.host_control import (
    AlternativeDraft,
    BeginPayload,
    ClaimDraft,
    ConflictDraft,
    CrossExamDraft,
    FeedbackPayload,
    FramingDraft,
    HoldDraft,
    HostControlError,
    ReferenceDraft,
    RevisionDraft,
    legal_control_transition,
    next_control_state,
    validate_control_payload,
    validate_host_control,
)
from ..domain.models import (
    AcceptedControl,
    Alternative,
    AssignedIds,
    Assumption,
    Calculation,
    CalculationOperand,
    CapabilityProfile,
    ClaimVersion,
    Conflict,
    Criterion,
    EphemeralTurnState,
    FlipCondition,
    Framing,
    HostControl,
    HostControlResult,
    JudgmentVersion,
    NormalizedEvent,
    RouterDecision,
    SourceReference,
    TaskProjection,
    UserSettings,
)
from ..domain.record_event import (
    AlternativePublishedPayload,
    ClaimPublishedPayload,
    ConclusionPublishedPayload,
    ConflictPublishedPayload,
    CrossExamCompletedPayload,
    FramingPublishedPayload,
    JudgmentStartedPayload,
    MethodSelectedPayload,
    RecordEvent,
    SourcePublishedPayload,
    TaskCancelledPayload,
    TaskInsufficientPayload,
    TaskStartedPayload,
)
from ..domain.rigor import build_rigor_decision
from ..domain.routing import DEFAULT_ROUTING_CATALOG, RoutingCatalog, route_features
from ..domain.turn_state import (
    ReplayCapacityError,
    TurnStateError,
    TurnStateExpired,
    accepted_control_for,
    append_accepted_control,
    payload_tag_for,
    replace_lifecycle,
    require_active,
)
from ..domain.validation import model_from_dict, validate_model
from ..errors import OpenSocratesError
from ..ids import (
    new_event_id,
    new_local_id,
    new_task_id,
    validate_event_id,
    validate_local_id,
    validate_sha256,
)
from .ports import (
    ContentRepository,
    RecordRepository,
    SettingsRepository,
    TaskRepository,
    TurnStateRepository,
)


class ApplyControlError(ValueError):
    """A safe application-level control error."""


class _PromptCompiler(Protocol):
    def compile(self, request: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class ApplyControlRequest:
    """Already-normalized application context for one control invocation."""

    control: HostControl | Mapping[str, Any] | bytes | str
    current_event: NormalizedEvent | None = None
    capability_profile: CapabilityProfile | None = None
    public_artifact_confirmed: bool = False
    direct_user_authority: bool = False


@dataclass(frozen=True, slots=True)
class _Mutation:
    state: EphemeralTurnState
    assigned_ids: AssignedIds
    route: RouterDecision | None
    durable_mutation: bool
    reason_code: HostControlReasonCode | None
    next_action: HostControlNextAction
    capability_limitations: tuple[str, ...]
    events: tuple[RecordEvent, ...] = ()
    settings_mutated: bool = False


def _empty_ids() -> AssignedIds:
    return AssignedIds(
        task_id=None,
        judgment_id=None,
        claim_ids=(),
        source_ids=(),
        criterion_ids=(),
        alternative_ids=(),
    )


def _event_type_from_request(event: NormalizedEvent | None) -> EventType | None:
    return event.event_type if isinstance(event, NormalizedEvent) else None


def _safe_limitations(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                value[:128]
                for value in values
                if isinstance(value, str) and value and "\x00" not in value
            }
        )
    )[:8]


def _now(clock: Clock) -> str:
    return utc_timestamp(clock)


def _error_code_for(exc: Exception) -> HostControlErrorCode:
    text = str(exc).lower()
    if "json" in text or "utf-8" in text or "duplicate" in text:
        return HostControlErrorCode.INVALID_JSON
    if "32 kib" in text or "size" in text or "oversized" in text:
        return HostControlErrorCode.OVERSIZED
    if "schema" in text:
        return HostControlErrorCode.UNKNOWN_SCHEMA
    if "message type" in text or "unknown message" in text:
        return HostControlErrorCode.UNKNOWN_MESSAGE_TYPE
    if "token" in text:
        return HostControlErrorCode.INVALID_TOKEN
    return HostControlErrorCode.INVALID_PAYLOAD


def _message_id(value: object) -> str:
    if isinstance(value, Mapping) and isinstance(value.get("message_id"), str):
        candidate = value["message_id"]
        try:
            return validate_event_id(candidate)
        except Exception:
            pass
    return new_event_id()


def _control_payload_tag(control: HostControl, installation_key: bytes) -> str:
    """Tag the full closed command identity, not only its nested payload."""

    return payload_tag_for(
        {
            "message_type": control.message_type.value,
            "published": control.published,
            "payload": control.payload,
        },
        installation_key,
    )


def _result(
    message_id: str,
    *,
    status: HostControlStatus,
    reason_code: HostControlReasonCode | None = None,
    durable_mutation: bool = False,
    assigned_ids: AssignedIds | None = None,
    effective_rigor: Rigor | None = None,
    route: RouterDecision | None = None,
    capability_limitations: Sequence[str] = (),
    next_action: HostControlNextAction = HostControlNextAction.CONTINUE,
    error_code: HostControlErrorCode | None = None,
) -> HostControlResult:
    result = HostControlResult(
        message_id=message_id,
        status=status,
        reason_code=reason_code,
        durable_mutation=durable_mutation,
        assigned_ids=assigned_ids or _empty_ids(),
        effective_rigor=effective_rigor,
        route=route,
        capability_limitations=_safe_limitations(capability_limitations),
        next_action=next_action,
        error_code=error_code,
    )
    if len(result.to_json().encode("utf-8")) > MAX_HOST_CONTROL_RESULT_BYTES:
        # A result is a bounded protocol object.  Dropping optional route data
        # is safer than emitting an over-limit response, but it must remain an
        # honest accepted/rejected result.
        result = replace(result, route=None, capability_limitations=())
    return result


def _capability_limitations(profile: CapabilityProfile | None) -> tuple[str, ...]:
    if profile is None:
        return ()
    values: list[str] = []
    for key, entry in profile.capabilities.items():
        if entry.status is not CapabilityStatus.SUPPORTED and key in {
            "published_artifact_confirmation",
            "local_record_write",
            "local_control_execution",
            "method_skill_invocation",
        }:
            values.append(entry.limitation_key or key)
    return _safe_limitations(values)


def _events(task_repository: TaskRepository | None, task_id: str) -> tuple[RecordEvent, ...]:
    if task_repository is None:
        return ()
    snapshot = getattr(task_repository, "snapshot", None)
    if callable(snapshot):
        value = snapshot(task_id)
        if value is None:
            return ()
        return tuple(getattr(value, "events", ()))
    load_events = getattr(task_repository, "load_events", None)
    if callable(load_events):
        return tuple(load_events(task_id))
    return ()


def _projection(task_repository: TaskRepository | None, task_id: str) -> TaskProjection | None:
    if task_repository is None:
        return None
    loader = getattr(task_repository, "load_projection", None)
    if not callable(loader):
        return None
    return loader(task_id)  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.


def _next_number(events: Sequence[RecordEvent], prefix: str) -> int:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    maximum = 0
    for event in events:
        payload = event.payload
        values: list[object] = []
        for field in ("judgment_id", "claim_id", "source_id", "criterion_id", "alternative_id"):
            if hasattr(payload, field):
                values.append(getattr(payload, field))
        value = getattr(payload, "value", None)
        if value is not None:
            for field in ("judgment_id", "claim_id", "source_id", "criterion_id", "alternative_id"):
                if hasattr(value, field):
                    values.append(getattr(value, field))
            if hasattr(value, "completion_criteria"):
                values.extend(item.criterion_id for item in value.completion_criteria)
            if hasattr(value, "source_ids"):
                values.extend(value.source_ids)
            if hasattr(value, "alternative_ids"):
                values.extend(value.alternative_ids)
        for item in values:
            if (
                isinstance(item, str)
                and len(item) == 7
                and item.startswith(prefix)
                and item[1:].isdigit()
            ):
                maximum = max(maximum, int(item[1:]))
    return maximum + 1


def _allocate(events: Sequence[RecordEvent], prefix: str) -> str:
    return new_local_id(prefix, _next_number(events, prefix))


def _has_id(events: Sequence[RecordEvent], value: str, prefix: str) -> bool:
    for event in events:
        payload = event.payload
        candidate = getattr(payload, "value", None)
        values = [
            getattr(payload, field, None)
            for field in ("judgment_id", "claim_id", "source_id", "criterion_id", "alternative_id")
        ]
        if candidate is not None:
            values.extend(
                getattr(candidate, field, None)
                for field in (
                    "judgment_id",
                    "claim_id",
                    "source_id",
                    "criterion_id",
                    "alternative_id",
                )
            )
            if hasattr(candidate, "completion_criteria"):
                values.extend(item.criterion_id for item in candidate.completion_criteria)
            if hasattr(candidate, "source_ids"):
                values.extend(candidate.source_ids)
            if hasattr(candidate, "alternative_ids"):
                values.extend(candidate.alternative_ids)
        if value in values:
            return True
    return False


def _walk_text(value: object) -> Sequence[str]:
    """Collect scalar text from a typed public payload for reference checks."""

    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        result: list[str] = []
        for child in value.values():
            result.extend(_walk_text(child))
        return tuple(result)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        result = []
        for child in value:
            result.extend(_walk_text(child))
        return tuple(result)
    if is_dataclass(value) and not isinstance(value, type):
        result = []
        for field in fields(value):
            result.extend(_walk_text(getattr(value, field.name)))
        return tuple(result)
    return ()


def _known_ids(events: Sequence[RecordEvent], prefix: str) -> frozenset[str]:
    found: set[str] = set()
    for event in events:
        for value in _walk_text(event.payload):
            try:
                validate_local_id(value, prefix)
            except Exception:
                continue
            found.add(value)
    return frozenset(found)


def _require_known_ids(values: Sequence[str], known: frozenset[str], label: str) -> None:
    if any(value not in known for value in values):
        raise ApplyControlError(f"stale {label} reference")


def _current_claim(events: Sequence[RecordEvent], claim_id: str) -> ClaimVersion | None:
    current: ClaimVersion | None = None
    for event in events:
        if event.event_type is RecordEventType.CLAIM_PUBLISHED:
            value = getattr(event.payload, "value", None)
            if (
                isinstance(value, ClaimVersion)
                and value.claim_id == claim_id
                and (current is None or value.version > current.version)
            ):
                current = value
    return current


def _current_judgment_version(events: Sequence[RecordEvent], judgment_id: str) -> int:
    value = 0
    for event in events:
        if event.event_type is RecordEventType.CONCLUSION_PUBLISHED:
            candidate = getattr(event.payload, "value", None)
            if isinstance(candidate, JudgmentVersion) and candidate.judgment_id == judgment_id:
                value = max(value, candidate.version)
    return value


def _append_event(
    task_repository: TaskRepository,
    state: EphemeralTurnState,
    payload: Any,
    event_type: RecordEventType,
    *,
    occurred_at: str,
    host_version: str,
    adapter_version: str,
    locale: str,
) -> RecordEvent:
    if state.task_id is None:
        raise ApplyControlError("cannot append a task event without a task id")
    prior = _events(task_repository, state.task_id)
    sequence = (prior[-1].sequence + 1) if prior else 1
    event = RecordEvent.new(
        task_id=state.task_id,
        sequence=sequence,
        event_type=event_type,
        payload=payload,
        occurred_at=occurred_at,
        host=state.host,
        host_version=host_version,
        adapter_version=adapter_version,
        locale=locale,
    )
    task_repository.append(event)  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
    return event


def _host_context(
    state: EphemeralTurnState,
    event: NormalizedEvent | None,
    *,
    host_version: str,
    adapter_version: str,
    locale: str,
    clock: Clock,
) -> tuple[str, str, str, str]:
    return (
        event.occurred_at if event is not None else _now(clock),
        event.host_version if event is not None else host_version,
        event.adapter_version if event is not None else adapter_version,
        event.payload.get("locale", locale)
        if event is not None and isinstance(event.payload.get("locale", locale), str)
        else locale,
    )


def _public_confirmation(
    message_type: HostControlMessageType,
    request: ApplyControlRequest,
    capability_profile: CapabilityProfile | None,
) -> bool:
    if message_type in {
        HostControlMessageType.BEGIN_JUDGMENT,
        HostControlMessageType.INTERVENTION_FEEDBACK,
        HostControlMessageType.CANCEL_JUDGMENT,
    }:
        return True
    if not request.public_artifact_confirmed:
        return False
    if capability_profile is None:
        return True
    entry = capability_profile.capabilities.get("published_artifact_confirmation")
    return entry is not None and entry.status is CapabilityStatus.SUPPORTED


def _not_recorded_reason(
    state: EphemeralTurnState,
    request: ApplyControlRequest,
    capability_profile: CapabilityProfile | None,
    message_type: HostControlMessageType,
) -> HostControlReasonCode:
    if not state.recording_eligible:
        return (
            HostControlReasonCode.ONBOARDING_DISCLOSURE_TURN
            if state.onboarding_disclosure_turn
            else HostControlReasonCode.RECORDING_OFF
        )
    if not _public_confirmation(message_type, request, capability_profile):
        return HostControlReasonCode.PUBLIC_ARTIFACT_UNCONFIRMED
    return HostControlReasonCode.RECORDING_OFF


def _ephemeral_only_mutation(
    state: EphemeralTurnState,
    message_type: HostControlMessageType,
    request: ApplyControlRequest,
    capability_profile: CapabilityProfile | None,
) -> _Mutation:
    """Advance only the closed phase when a public artifact is untrusted."""

    return _Mutation(
        state=replace_lifecycle(
            state,
            task_state=next_control_state(message_type, state.task_state),
        ),
        assigned_ids=_empty_ids(),
        route=None,
        durable_mutation=False,
        reason_code=_not_recorded_reason(state, request, capability_profile, message_type),
        next_action=(
            HostControlNextAction.STOP_CONTROL_CALLS
            if message_type is HostControlMessageType.HOLD_JUDGMENT
            else HostControlNextAction.CONTINUE
        ),
        capability_limitations=_capability_limitations(capability_profile),
        events=(),
    )


def _bind_framing(
    draft: FramingDraft, state: EphemeralTurnState, events: Sequence[RecordEvent]
) -> tuple[Framing, tuple[str, ...]]:
    if state.judgment_id is None:
        raise ApplyControlError("framing requires an active judgment")
    criterion_ids: list[str] = []
    criteria: list[Criterion] = []
    next_criterion = _next_number(events, "K")
    for offset, item in enumerate(draft.completion_criteria):
        _require_known_ids(item.evidence_claim_ids, _known_ids(events, "C"), "claim")
        criterion_id = new_local_id("K", next_criterion + offset)
        criterion_ids.append(criterion_id)
        criteria.append(
            Criterion(
                criterion_id=criterion_id,
                text=item.text,
                required=item.required,
                kind=item.kind,
                evidence_claim_ids=tuple(item.evidence_claim_ids),
            )
        )
    framing = Framing(
        judgment_id=state.judgment_id,
        decision_question=draft.decision_question,
        assumptions=tuple(
            Assumption(text=item["text"], material=item["material"]) for item in draft.assumptions
        ),
        decisive_evidence=draft.decisive_evidence,
        completion_criteria=tuple(criteria),
    )
    return framing, tuple(criterion_ids)


def _bind_sources_and_claim(
    draft: ClaimDraft,
    state: EphemeralTurnState,
    events: Sequence[RecordEvent],
) -> tuple[ClaimVersion, tuple[SourceReference, ...], tuple[str, ...]]:
    if state.judgment_id is None:
        raise ApplyControlError("claim requires an active judgment")
    source_ids: list[str] = []
    source_models: list[SourceReference] = []
    new_source_by_index: dict[int, str] = {}
    next_source = _next_number(events, "E")
    for index, source in enumerate(draft.new_sources):
        source_id = new_local_id("E", next_source + index)
        new_source_by_index[index] = source_id
        source_models.append(
            SourceReference(
                source_id=source_id,
                kind=SourceKind(source.kind),
                display_name=source.display_name,
                uri=source.uri,
                safe_locator=source.safe_locator,
                published_at=source.published_at,
                checked_at=source.checked_at,
                content_hash=source.content_hash,
            )
        )
        source_ids.append(source_id)
    existing = {item for event in events for item in _source_ids_from_event(event)}
    for ref in draft.source_refs:
        source_id = (
            ref.existing_id  # type: ignore[assignment]  # Closed runtime boundary validates this value.
            if ref.existing_id is not None
            else new_source_by_index.get(ref.new_index)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        )
        if source_id is None or (ref.existing_id is not None and source_id not in existing):
            raise ApplyControlError("stale source reference")
        if source_id not in source_ids:
            source_ids.append(source_id)
    claim_id = draft.claim_ref or _allocate(events, "C")
    previous = _current_claim(events, claim_id) if draft.claim_ref is not None else None
    if draft.claim_ref is not None:
        if previous is None or previous.version != draft.expected_current_version:
            raise ApplyControlError("stale claim reference")
        version = previous.version + 1
    else:
        version = 1
    calculation = _bind_calculation(
        draft.calculation, new_source_by_index, existing | set(source_ids)
    )
    _require_known_ids(draft.basis_claim_ids, _known_ids(events, "C"), "claim")
    conflict = _bind_conflict(
        draft.conflict,
        known_claims=_known_ids(events, "C"),
        known_sources=_known_ids(events, "E"),
    )
    claim = ClaimVersion(
        claim_id=claim_id,
        version=version,
        text=draft.text,
        materiality=draft.materiality,
        evidence_state=draft.evidence_state,
        source_ids=tuple(source_ids),
        basis_claim_ids=draft.basis_claim_ids,
        calculation=calculation,
        conflict=conflict,
        active=True,
    )
    return claim, tuple(source_models), tuple(source_ids)


def _source_ids_from_event(event: RecordEvent) -> tuple[str, ...]:
    value = getattr(event.payload, "value", None)
    if event.event_type is RecordEventType.SOURCE_PUBLISHED and isinstance(value, SourceReference):
        return (value.source_id,)
    if isinstance(value, (ClaimVersion, Conflict)) and hasattr(value, "source_ids"):
        return tuple(value.source_ids)
    return ()


def _bind_calculation(
    value: Mapping[str, Any] | None, new_sources: Mapping[int, str], valid_sources: set[str]
) -> Calculation | None:
    if value is None:
        return None
    operands: list[CalculationOperand] = []
    for raw in value["operands"]:
        ref = raw["source_ref"]
        source_id = None
        if isinstance(ref, ReferenceDraft):
            source_id = (
                ref.existing_id if ref.existing_id is not None else new_sources.get(ref.new_index)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            )
        if source_id is not None and source_id not in valid_sources:
            raise ApplyControlError("stale calculation source reference")
        operands.append(
            CalculationOperand(
                name=raw["name"], value=raw["value"], unit=raw["unit"], source_id=source_id
            )
        )
    return Calculation(
        expression=value["expression"],
        operands=tuple(operands),
        result=value["result"],
        unit=value["unit"],
        rounding=RoundingMode(value["rounding"]),
    )


def _bind_conflict(
    value: Mapping[str, Any] | None,
    *,
    known_claims: frozenset[str] = frozenset(),
    known_sources: frozenset[str] = frozenset(),
) -> Conflict | None:
    if value is None:
        return None
    try:
        conflict = model_from_dict(Conflict, value)
    except Exception as exc:
        raise ApplyControlError("invalid claim conflict") from exc
    _require_known_ids(conflict.affected_claim_ids, known_claims, "claim")
    _require_known_ids(conflict.source_ids, known_sources, "source")
    return conflict  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.


def _bind_conflict_payload(draft: ConflictDraft, events: Sequence[RecordEvent]) -> Conflict:
    try:
        conflict = model_from_dict(Conflict, draft.conflict)
    except Exception as exc:
        raise ApplyControlError("invalid conflict payload") from exc
    known_claims = _known_ids(events, "C")
    known_sources = _known_ids(events, "E")
    _require_known_ids(draft.affected_claim_ids, known_claims, "claim")
    _require_known_ids(conflict.affected_claim_ids, known_claims, "claim")
    _require_known_ids(conflict.source_ids, known_sources, "source")
    return conflict  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.


def _bind_revision(
    draft: RevisionDraft, state: EphemeralTurnState, events: Sequence[RecordEvent]
) -> JudgmentVersion:
    if state.judgment_id is None:
        raise ApplyControlError("revision requires an active judgment")
    _require_known_ids(draft.ground_claim_ids, _known_ids(events, "C"), "claim")
    _require_known_ids(draft.uncertainty_claim_ids, _known_ids(events, "C"), "claim")
    _require_known_ids(draft.alternative_ids, _known_ids(events, "A"), "alternative")
    version = _current_judgment_version(events, state.judgment_id) + 1
    flips = tuple(model_from_dict(FlipCondition, item) for item in draft.flip_conditions)
    return JudgmentVersion(
        judgment_id=state.judgment_id,
        version=version,
        state=JudgmentState.REVISED,
        conclusion=draft.conclusion,
        strength=draft.strength,
        supersedes_version=version - 1 if version > 1 else None,
        change_reason=draft.change_reason if version > 1 else None,
        ground_claim_ids=draft.ground_claim_ids,
        uncertainty_claim_ids=draft.uncertainty_claim_ids,
        flip_conditions=flips,
        alternative_ids=draft.alternative_ids,
    )


def _validate_draft_references(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    message_type: HostControlMessageType,
    draft: Any,
    state: EphemeralTurnState,
    events: Sequence[RecordEvent],
) -> None:
    """Validate model-supplied references before any degraded path advances.

    The runtime may discard public prose when recording or exact artifact
    confirmation is unavailable, but it still rejects references that point
    outside the current task.  This keeps the closed control contract honest
    across both durable and ephemeral executions.
    """

    known_claims = _known_ids(events, "C")
    known_sources = _known_ids(events, "E")
    known_alternatives = _known_ids(events, "A")
    if message_type is HostControlMessageType.PUBLISH_FRAMING:
        for criterion in draft.completion_criteria:
            _require_known_ids(criterion.evidence_claim_ids, known_claims, "claim")
        return
    if message_type is HostControlMessageType.PUBLISH_CLAIM:
        _require_known_ids(draft.basis_claim_ids, known_claims, "claim")
        if draft.claim_ref is not None:
            current = _current_claim(events, draft.claim_ref)
            if current is None or current.version != draft.expected_current_version:
                raise ApplyControlError("stale claim reference")
        for reference in draft.source_refs:
            if reference.existing_id is not None and reference.existing_id not in known_sources:
                raise ApplyControlError("stale source reference")
        calculation = draft.calculation
        if calculation is not None:
            for operand in calculation["operands"]:
                reference = operand["source_ref"]
                if (
                    isinstance(reference, ReferenceDraft)
                    and reference.existing_id is not None
                    and reference.existing_id not in known_sources
                ):
                    raise ApplyControlError("stale calculation source reference")
        _bind_conflict(draft.conflict, known_claims=known_claims, known_sources=known_sources)
        return
    if message_type is HostControlMessageType.PUBLISH_CONFLICT:
        _bind_conflict_payload(draft, events)
        return
    if message_type is HostControlMessageType.PUBLISH_ALTERNATIVE:
        _require_known_ids(draft.material_claim_ids, known_claims, "claim")
        return
    if message_type is HostControlMessageType.REVISE_JUDGMENT:
        _require_known_ids(draft.ground_claim_ids, known_claims, "claim")
        _require_known_ids(draft.uncertainty_claim_ids, known_claims, "claim")
        _require_known_ids(draft.alternative_ids, known_alternatives, "alternative")
        return
    if message_type is HostControlMessageType.COMPLETE_CROSS_EXAM:
        known = frozenset().union(
            *(_known_ids(events, prefix) for prefix in ("J", "C", "E", "K", "A"))
        )
        _require_known_ids(draft.affected_ids, known, "local")


def _settings_feedback_transform(
    settings: UserSettings, payload: FeedbackPayload, day: str
) -> UserSettings:
    from ..domain.models import FeedbackEntry, InterventionPreference

    current = settings.intervention_preferences.get(
        payload.feedback_class.value, InterventionPreference()
    )
    sequence = current.next_sequence
    entries = (
        *current.recent_feedback,
        FeedbackEntry(sequence=sequence, day=day, outcome=payload.outcome),
    )[-20:]
    preference = replace(current, next_sequence=sequence + 1, recent_feedback=entries)
    values = dict(settings.intervention_preferences)
    values[payload.feedback_class.value] = preference
    return replace(settings, revision=settings.revision + 1, intervention_preferences=values)


class ControlApplication:
    """Closed control use case with injected repositories and policy seams."""

    def __init__(
        self,
        turn_repository: TurnStateRepository,
        *,
        task_repository: TaskRepository | None = None,
        record_repository: RecordRepository | None = None,
        settings_repository: SettingsRepository | None = None,
        content_repository: ContentRepository | None = None,
        prompt_compiler: _PromptCompiler | None = None,
        routing_catalog: RoutingCatalog = DEFAULT_ROUTING_CATALOG,
        capability_profile: CapabilityProfile | None = None,
        clock: Clock | None = None,
        installation_key: bytes | None = None,
        host_version: str = "unknown",
        adapter_version: str = "1.0.0",
        locale: str = "en",
    ) -> None:
        self.turn_repository = turn_repository
        self.task_repository = task_repository
        self.record_repository = record_repository
        self.settings_repository = settings_repository
        self.content_repository = content_repository
        self.prompt_compiler = prompt_compiler
        self.routing_catalog = routing_catalog
        self.capability_profile = capability_profile
        self.clock = clock or SystemClock()
        self.installation_key = installation_key or getattr(
            turn_repository, "installation_key", None
        )
        self.host_version = host_version
        self.adapter_version = adapter_version
        self.locale = locale
        self._apply_lock = RLock()

    def _require_key(self) -> bytes:
        if not isinstance(self.installation_key, bytes) or len(self.installation_key) != 32:
            raise ApplyControlError("turn repository installation key is unavailable")
        return self.installation_key

    def _sweep_expired(self) -> None:
        sweep = getattr(self.turn_repository, "sweep_expired", None)
        if callable(sweep):
            try:
                sweep(_now(self.clock))
            except Exception:
                pass

    def _load_state(
        self, control: HostControl, event: NormalizedEvent | None
    ) -> EphemeralTurnState:
        try:
            state = self.turn_repository.load_by_raw_token(control.turn_token)
        except Exception as exc:
            raise ApplyControlError("turn state store unavailable") from exc
        if state is None:
            raise ApplyControlError("invalid token")
        try:
            active = require_active(state, _now(self.clock))
        except TurnStateExpired as exc:
            try:
                self.turn_repository.delete(state)
            except Exception:
                pass
            raise exc
        if event is not None:
            if (
                event.host_session_key != active.host_session_key
                or event.host_turn_key != active.host_turn_key
            ):
                raise ApplyControlError("stale token reference")
        return active

    def _append(self, state: EphemeralTurnState, events: Sequence[RecordEvent]) -> None:
        if not events:
            return
        if self.task_repository is None:
            raise ApplyControlError("task store unavailable")
        for event in events:
            try:
                self.task_repository.append(event)  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
            except Exception as exc:
                raise ApplyControlError("task store unavailable") from exc

    def _content_context(self) -> tuple[Any | None, RoutingCatalog]:
        """Load immutable content once and derive a typed routing catalog."""

        if self.content_repository is None:
            if self.prompt_compiler is not None:
                raise ApplyControlError("content store unavailable")
            return None, self.routing_catalog
        try:
            bundle = self.content_repository.load()
        except Exception as exc:
            raise ApplyControlError("content store unavailable") from exc
        catalog = self.routing_catalog
        if catalog is DEFAULT_ROUTING_CATALOG:
            try:
                catalog = RoutingCatalog.from_bundle(bundle)
            except Exception as exc:
                raise ApplyControlError("content routing catalog unavailable") from exc
        return bundle, catalog

    def _prompt_hash(
        self,
        begin: BeginPayload,
        route: RouterDecision,
        effective: Any,
        event: NormalizedEvent | None,
        bundle: Any | None,
        capability_profile: CapabilityProfile | None,
    ) -> str | None:
        if bundle is None:
            return None
        semantic_hash = getattr(bundle, "normalized_semantic_hash", None)
        if not isinstance(semantic_hash, str):
            raise ApplyControlError("prompt bundle hash unavailable")
        try:
            validate_sha256(semantic_hash)
        except Exception as exc:
            raise ApplyControlError("prompt bundle hash unavailable") from exc
        if self.prompt_compiler is None:
            return semantic_hash
        try:
            from ..prompting.compiler import PromptCompileRequest, PromptEvent

            request = PromptCompileRequest(
                bundle=bundle,
                locale=event.payload.get("locale", self.locale)
                if event is not None
                else self.locale,
                event=PromptEvent.START,
                participation=begin.participation,
                rigor=effective,
                route=replace(route, prompt_bundle_hash=semantic_hash),
                phase=TaskState.FRAMING,
                capability_profile=capability_profile,
                expected_content_revision=bundle.content_revision,
            )
            compiled = self.prompt_compiler.compile(request)
            compiled_hash = getattr(compiled, "compiled_prompt_bundle_hash", None)
            if not isinstance(compiled_hash, str):
                raise ApplyControlError("prompt compiler returned no digest")
            validate_sha256(compiled_hash)
        except ApplyControlError:
            raise
        except Exception as exc:
            raise ApplyControlError("prompt bundle unavailable") from exc
        # The route identifies the immutable content bundle.  The compiler's
        # assembled-text digest remains transient and is never returned here.
        return semantic_hash

    def _begin(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        self, state: EphemeralTurnState, begin: BeginPayload, request: ApplyControlRequest
    ) -> _Mutation:
        if state.task_state is not TaskState.NEW:
            raise ApplyControlError("invalid state transition")
        if begin.participation.participation is Participation.MECHANICAL:
            raise ApplyControlError("mechanical begin is not legal")
        if (
            state.participation is not None
            and state.participation is not begin.participation.participation
        ):
            raise ApplyControlError("begin participation does not match current turn")
        if self.settings_repository is None:
            if state.recording_eligible:
                raise ApplyControlError("settings store unavailable")
            # An already-issued non-recording turn carries the only setting
            # needed to route safely.  No durable task path is possible here.
            settings = UserSettings(default_rigor=state.effective_rigor)
        else:
            try:
                settings = self.settings_repository.load()
            except Exception as exc:
                raise ApplyControlError("settings store unavailable") from exc
        if begin.rigor.stored_rigor is not settings.default_rigor:
            raise ApplyControlError("begin rigor does not match current settings")
        try:
            effective = build_rigor_decision(
                begin.rigor.stored_rigor,
                begin.rigor.task_override,
                begin.rigor.risk_floor,
                begin.rigor.risk_reason,
            )
        except Exception as exc:
            raise ApplyControlError("begin rigor is invalid") from exc
        if (
            begin.rigor.effective_rigor is not effective.effective_rigor
            or begin.rigor.show_raise_notice is not effective.show_raise_notice
        ):
            raise ApplyControlError("begin rigor is not the recomputed decision")
        bundle, catalog = self._content_context()
        base_route = route_features(begin.participation, begin.routing_features, catalog=catalog)
        prompt_hash = self._prompt_hash(
            begin,
            base_route,
            effective,
            request.current_event,
            bundle,
            request.capability_profile or self.capability_profile,
        )
        route = (
            replace(base_route, prompt_bundle_hash=prompt_hash)
            if prompt_hash is not None
            else base_route
        )
        events = _events(self.task_repository, state.task_id or "")
        can_create_task = state.recording_eligible
        task_id = state.task_id or (new_task_id(self.clock) if can_create_task else None)
        judgment_id = state.judgment_id or (_allocate(events, "J") if can_create_task else None)
        next_state = replace_lifecycle(
            state,
            task_id=task_id,
            judgment_id=judgment_id,
            task_state=TaskState.FRAMING,
            participation=begin.participation.participation,
            effective_rigor=effective.effective_rigor,
            primary_method=route.primary_method,
            secondary_method=route.secondary_method,
        )
        assigned = AssignedIds(
            task_id=task_id if can_create_task else None,
            judgment_id=judgment_id if can_create_task else None,
        )
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: list[RecordEvent] = []
        if next_state.recording_eligible:
            gaps = _capability_limitations(request.capability_profile or self.capability_profile)
            public_events.append(
                _append_event_placeholder(
                    task_id=task_id,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                    sequence=1,
                    payload=TaskStartedPayload(
                        requested_rigor=settings.default_rigor,
                        effective_rigor=effective.effective_rigor,
                        capability_gaps=gaps,
                        participation_reason=begin.participation.reason_code.value,
                        host_session_key=state.host_session_key,
                    ),
                    event_type=RecordEventType.TASK_STARTED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                )
            )
            if route.primary_method is not None:
                public_events.append(
                    _append_event_placeholder(
                        task_id=task_id,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                        sequence=2,
                        payload=MethodSelectedPayload(
                            route.primary_method,
                            route.secondary_method,
                            "explicit" if route.explicit_invocation else "automatic",
                        ),
                        event_type=RecordEventType.METHOD_SELECTED,
                        occurred_at=event_time,
                        host=state.host,
                        host_version=host_version,
                        adapter_version=adapter_version,
                        locale=locale,
                    )
                )
            public_events.append(
                _append_event_placeholder(
                    task_id=task_id,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                    sequence=len(public_events) + 1,
                    payload=JudgmentStartedPayload(judgment_id=judgment_id, version=1),  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                    event_type=RecordEventType.JUDGMENT_STARTED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                )
            )
        reason = (
            None
            if next_state.recording_eligible
            else (
                HostControlReasonCode.ONBOARDING_DISCLOSURE_TURN
                if next_state.onboarding_disclosure_turn
                else HostControlReasonCode.RECORDING_OFF
            )
        )
        return _Mutation(
            state=next_state,
            assigned_ids=assigned,
            route=route,
            durable_mutation=bool(next_state.recording_eligible),
            reason_code=reason,
            next_action=HostControlNextAction.ACTIVATE_PRIMARY_SKILL
            if route.primary_method
            else HostControlNextAction.CONTINUE,
            capability_limitations=_capability_limitations(
                request.capability_profile or self.capability_profile
            ),
            events=tuple(public_events),
        )

    def _publish_framing(
        self, state: EphemeralTurnState, draft: FramingDraft, request: ApplyControlRequest
    ) -> _Mutation:
        profile = request.capability_profile or self.capability_profile
        if not state.recording_eligible or not _public_confirmation(
            HostControlMessageType.PUBLISH_FRAMING, request, profile
        ):
            return _ephemeral_only_mutation(
                state, HostControlMessageType.PUBLISH_FRAMING, request, profile
            )
        events = _events(self.task_repository, state.task_id or "")
        framing, criteria = _bind_framing(draft, state, events)
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: list[RecordEvent] = []
        if state.recording_eligible and _public_confirmation(
            HostControlMessageType.PUBLISH_FRAMING, request, profile
        ):
            public_events.append(
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + 1,
                    payload=FramingPublishedPayload(framing),
                    event_type=RecordEventType.FRAMING_PUBLISHED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                )
            )
        return _Mutation(
            state=replace_lifecycle(
                state,
                task_state=next_control_state(
                    HostControlMessageType.PUBLISH_FRAMING, state.task_state
                ),
            ),
            assigned_ids=AssignedIds(
                task_id=state.task_id, judgment_id=state.judgment_id, criterion_ids=criteria
            ),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None
            if public_events
            else _not_recorded_reason(
                state, request, profile, HostControlMessageType.PUBLISH_FRAMING
            ),
            next_action=HostControlNextAction.CONTINUE,
            capability_limitations=_capability_limitations(profile),
            events=tuple(public_events),
        )

    def _publish_claim(
        self, state: EphemeralTurnState, draft: ClaimDraft, request: ApplyControlRequest
    ) -> _Mutation:
        profile = request.capability_profile or self.capability_profile
        if not state.recording_eligible or not _public_confirmation(
            HostControlMessageType.PUBLISH_CLAIM, request, profile
        ):
            return _ephemeral_only_mutation(
                state, HostControlMessageType.PUBLISH_CLAIM, request, profile
            )
        events = _events(self.task_repository, state.task_id or "")
        claim, sources, source_ids = _bind_sources_and_claim(draft, state, events)
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: list[RecordEvent] = []
        if state.recording_eligible and _public_confirmation(
            HostControlMessageType.PUBLISH_CLAIM, request, profile
        ):
            for source in sources:
                public_events.append(
                    _append_event_placeholder(
                        task_id=state.task_id or "",
                        sequence=len(events) + len(public_events) + 1,
                        payload=SourcePublishedPayload(source),
                        event_type=RecordEventType.SOURCE_PUBLISHED,
                        occurred_at=event_time,
                        host=state.host,
                        host_version=host_version,
                        adapter_version=adapter_version,
                        locale=locale,
                    )
                )
            public_events.append(
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + len(public_events) + 1,
                    payload=ClaimPublishedPayload(claim),
                    event_type=RecordEventType.CLAIM_PUBLISHED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                )
            )
        return _Mutation(
            state=state,
            assigned_ids=AssignedIds(
                task_id=state.task_id,
                judgment_id=state.judgment_id,
                claim_ids=(claim.claim_id,),
                source_ids=tuple(source_ids),
            ),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None
            if public_events
            else _not_recorded_reason(
                state, request, profile, HostControlMessageType.PUBLISH_CLAIM
            ),
            next_action=HostControlNextAction.CONTINUE,
            capability_limitations=_capability_limitations(profile),
            events=tuple(public_events),
        )

    def _publish_conflict(
        self, state: EphemeralTurnState, draft: ConflictDraft, request: ApplyControlRequest
    ) -> _Mutation:
        profile = request.capability_profile or self.capability_profile
        if not state.recording_eligible or not _public_confirmation(
            HostControlMessageType.PUBLISH_CONFLICT, request, profile
        ):
            return _ephemeral_only_mutation(
                state, HostControlMessageType.PUBLISH_CONFLICT, request, profile
            )
        events = _events(self.task_repository, state.task_id or "")
        conflict = _bind_conflict_payload(draft, events)
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: tuple[RecordEvent, ...] = ()
        if state.recording_eligible and _public_confirmation(
            HostControlMessageType.PUBLISH_CONFLICT, request, profile
        ):
            public_events = (
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + 1,
                    payload=ConflictPublishedPayload(conflict, draft.affected_claim_ids),
                    event_type=RecordEventType.CONFLICT_PUBLISHED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                ),
            )
        return _Mutation(
            state=replace_lifecycle(
                state,
                task_state=next_control_state(
                    HostControlMessageType.PUBLISH_CONFLICT, state.task_state
                ),
            ),
            assigned_ids=AssignedIds(task_id=state.task_id, judgment_id=state.judgment_id),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None
            if public_events
            else _not_recorded_reason(
                state, request, profile, HostControlMessageType.PUBLISH_CONFLICT
            ),
            next_action=HostControlNextAction.CONTINUE,
            capability_limitations=_capability_limitations(profile),
            events=public_events,
        )

    def _publish_alternative(
        self, state: EphemeralTurnState, draft: AlternativeDraft, request: ApplyControlRequest
    ) -> _Mutation:
        profile = request.capability_profile or self.capability_profile
        if not state.recording_eligible or not _public_confirmation(
            HostControlMessageType.PUBLISH_ALTERNATIVE, request, profile
        ):
            return _ephemeral_only_mutation(
                state, HostControlMessageType.PUBLISH_ALTERNATIVE, request, profile
            )
        events = _events(self.task_repository, state.task_id or "")
        _require_known_ids(draft.material_claim_ids, _known_ids(events, "C"), "claim")
        alternative_id = _allocate(events, "A")
        alternative = Alternative(
            alternative_id=alternative_id,
            name=draft.name,
            disposition=draft.disposition,
            reason=draft.reason,
            material_claim_ids=draft.material_claim_ids,
        )
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: tuple[RecordEvent, ...] = ()
        if state.recording_eligible and _public_confirmation(
            HostControlMessageType.PUBLISH_ALTERNATIVE, request, profile
        ):
            public_events = (
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + 1,
                    payload=AlternativePublishedPayload(alternative),
                    event_type=RecordEventType.ALTERNATIVE_PUBLISHED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                ),
            )
        return _Mutation(
            state=state,
            assigned_ids=AssignedIds(
                task_id=state.task_id,
                judgment_id=state.judgment_id,
                alternative_ids=(alternative_id,),
            ),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None
            if public_events
            else _not_recorded_reason(
                state, request, profile, HostControlMessageType.PUBLISH_ALTERNATIVE
            ),
            next_action=HostControlNextAction.CONTINUE,
            capability_limitations=_capability_limitations(profile),
            events=public_events,
        )

    def _revise(
        self, state: EphemeralTurnState, draft: RevisionDraft, request: ApplyControlRequest
    ) -> _Mutation:
        profile = request.capability_profile or self.capability_profile
        if not state.recording_eligible or not _public_confirmation(
            HostControlMessageType.REVISE_JUDGMENT, request, profile
        ):
            return _ephemeral_only_mutation(
                state, HostControlMessageType.REVISE_JUDGMENT, request, profile
            )
        events = _events(self.task_repository, state.task_id or "")
        judgment = _bind_revision(draft, state, events)
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: tuple[RecordEvent, ...] = ()
        if state.recording_eligible and _public_confirmation(
            HostControlMessageType.REVISE_JUDGMENT, request, profile
        ):
            public_events = (
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + 1,
                    payload=ConclusionPublishedPayload(judgment),
                    event_type=RecordEventType.CONCLUSION_PUBLISHED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                ),
            )
        return _Mutation(
            state=replace_lifecycle(
                state,
                task_state=next_control_state(
                    HostControlMessageType.REVISE_JUDGMENT, state.task_state
                ),
            ),
            assigned_ids=AssignedIds(task_id=state.task_id, judgment_id=state.judgment_id),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None
            if public_events
            else _not_recorded_reason(
                state, request, profile, HostControlMessageType.REVISE_JUDGMENT
            ),
            next_action=HostControlNextAction.CONTINUE,
            capability_limitations=_capability_limitations(profile),
            events=public_events,
        )

    def _cross_exam(
        self, state: EphemeralTurnState, draft: CrossExamDraft, request: ApplyControlRequest
    ) -> _Mutation:
        profile = request.capability_profile or self.capability_profile
        if not state.recording_eligible or not _public_confirmation(
            HostControlMessageType.COMPLETE_CROSS_EXAM, request, profile
        ):
            return _ephemeral_only_mutation(
                state, HostControlMessageType.COMPLETE_CROSS_EXAM, request, profile
            )
        events = _events(self.task_repository, state.task_id or "")
        known = frozenset().union(
            *(_known_ids(events, prefix) for prefix in ("J", "C", "E", "K", "A"))
        )
        _require_known_ids(draft.affected_ids, known, "local")
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: tuple[RecordEvent, ...] = ()
        if state.recording_eligible and _public_confirmation(
            HostControlMessageType.COMPLETE_CROSS_EXAM, request, profile
        ):
            public_events = (
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + 1,
                    payload=CrossExamCompletedPayload(draft.findings_summary, draft.affected_ids),
                    event_type=RecordEventType.CROSS_EXAM_COMPLETED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                ),
            )
        return _Mutation(
            state=replace_lifecycle(
                state,
                task_state=next_control_state(
                    HostControlMessageType.COMPLETE_CROSS_EXAM, state.task_state
                ),
            ),
            assigned_ids=AssignedIds(task_id=state.task_id, judgment_id=state.judgment_id),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None
            if public_events
            else _not_recorded_reason(
                state, request, profile, HostControlMessageType.COMPLETE_CROSS_EXAM
            ),
            next_action=HostControlNextAction.CONTINUE,
            capability_limitations=_capability_limitations(profile),
            events=public_events,
        )

    def _hold(
        self, state: EphemeralTurnState, draft: HoldDraft, request: ApplyControlRequest
    ) -> _Mutation:
        profile = request.capability_profile or self.capability_profile
        if not state.recording_eligible or not _public_confirmation(
            HostControlMessageType.HOLD_JUDGMENT, request, profile
        ):
            return _ephemeral_only_mutation(
                state, HostControlMessageType.HOLD_JUDGMENT, request, profile
            )
        events = _events(self.task_repository, state.task_id or "")
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: tuple[RecordEvent, ...] = ()
        if state.recording_eligible and _public_confirmation(
            HostControlMessageType.HOLD_JUDGMENT, request, profile
        ):
            public_events = (
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + 1,
                    payload=TaskInsufficientPayload(draft.reason_code, draft.missing_items),
                    event_type=RecordEventType.TASK_INSUFFICIENT,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                ),
            )
        return _Mutation(
            state=replace_lifecycle(state, task_state=TaskState.INSUFFICIENT),
            assigned_ids=AssignedIds(task_id=state.task_id, judgment_id=state.judgment_id),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None
            if public_events
            else _not_recorded_reason(
                state, request, profile, HostControlMessageType.HOLD_JUDGMENT
            ),
            next_action=HostControlNextAction.STOP_CONTROL_CALLS,
            capability_limitations=_capability_limitations(profile),
            events=public_events,
        )

    def _cancel(self, state: EphemeralTurnState, request: ApplyControlRequest) -> _Mutation:
        events = _events(self.task_repository, state.task_id or "")
        event_time, host_version, adapter_version, locale = _host_context(
            state,
            request.current_event,
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            clock=self.clock,
        )
        public_events: tuple[RecordEvent, ...] = ()
        if state.recording_eligible:
            public_events = (
                _append_event_placeholder(
                    task_id=state.task_id or "",
                    sequence=len(events) + 1,
                    payload=TaskCancelledPayload(),
                    event_type=RecordEventType.TASK_CANCELLED,
                    occurred_at=event_time,
                    host=state.host,
                    host_version=host_version,
                    adapter_version=adapter_version,
                    locale=locale,
                ),
            )
        return _Mutation(
            state=replace_lifecycle(state, task_state=TaskState.CANCELLED),
            assigned_ids=AssignedIds(task_id=state.task_id, judgment_id=state.judgment_id),
            route=None,
            durable_mutation=bool(public_events),
            reason_code=None if public_events else HostControlReasonCode.RECORDING_OFF,
            next_action=HostControlNextAction.STOP_CONTROL_CALLS,
            capability_limitations=_capability_limitations(
                request.capability_profile or self.capability_profile
            ),
            events=public_events,
        )

    def _feedback(
        self, state: EphemeralTurnState, payload: FeedbackPayload, request: ApplyControlRequest
    ) -> _Mutation:
        if (
            not request.direct_user_authority
            or _event_type_from_request(request.current_event)
            is not EventType.USER_PROMPT_SUBMITTED
        ):
            raise ApplyControlError("feedback requires current direct-user authority")
        if self.settings_repository is None:
            raise ApplyControlError("settings store unavailable")
        try:
            day = (
                request.current_event.occurred_at[:10]
                if request.current_event is not None
                else utc_date(self.clock)
            )
            mutate = getattr(self.settings_repository, "mutate", None)
            if callable(mutate):
                mutate(lambda settings: _settings_feedback_transform(settings, payload, day))
            elif hasattr(self.settings_repository, "apply_intervention_feedback"):
                self.settings_repository.apply_intervention_feedback(
                    payload.feedback_class, payload.outcome
                )
            else:
                settings = self.settings_repository.load()
                updated = _settings_feedback_transform(settings, payload, day)
                self.settings_repository.save(updated)
        except Exception as exc:
            raise ApplyControlError("settings store unavailable") from exc
        return _Mutation(
            state=state,
            assigned_ids=_empty_ids(),
            route=None,
            durable_mutation=True,
            reason_code=None,
            next_action=HostControlNextAction.CONTINUE,
            capability_limitations=(),
            settings_mutated=True,
        )

    def _mutate(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        self,
        state: EphemeralTurnState,
        control: HostControl,
        request: ApplyControlRequest,
        typed: Any,
    ) -> _Mutation:
        if control.message_type is HostControlMessageType.BEGIN_JUDGMENT:
            return self._begin(state, typed, request)
        if control.message_type is HostControlMessageType.INTERVENTION_FEEDBACK:
            return self._feedback(state, typed, request)
        if not legal_control_transition(control.message_type, state.task_state):
            raise ApplyControlError("invalid state transition")
        _validate_draft_references(
            control.message_type,
            typed,
            state,
            _events(self.task_repository, state.task_id or ""),
        )
        if control.message_type is HostControlMessageType.PUBLISH_FRAMING:
            return self._publish_framing(state, typed, request)
        if control.message_type is HostControlMessageType.PUBLISH_CLAIM:
            return self._publish_claim(state, typed, request)
        if control.message_type is HostControlMessageType.PUBLISH_CONFLICT:
            return self._publish_conflict(state, typed, request)
        if control.message_type is HostControlMessageType.PUBLISH_ALTERNATIVE:
            return self._publish_alternative(state, typed, request)
        if control.message_type is HostControlMessageType.REVISE_JUDGMENT:
            return self._revise(state, typed, request)
        if control.message_type is HostControlMessageType.COMPLETE_CROSS_EXAM:
            return self._cross_exam(state, typed, request)
        if control.message_type is HostControlMessageType.HOLD_JUDGMENT:
            return self._hold(state, typed, request)
        if control.message_type is HostControlMessageType.CANCEL_JUDGMENT:
            return self._cancel(state, request)
        raise ApplyControlError("unknown message type")

    def apply(
        self,
        request: ApplyControlRequest | HostControl | Mapping[str, Any] | bytes | str,
        **kwargs: Any,
    ) -> HostControlResult:
        """Apply one control under the process-local idempotency lock."""

        with self._apply_lock:
            return self._apply_unlocked(request, **kwargs)

    def _apply_unlocked(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        self,
        request: ApplyControlRequest | HostControl | Mapping[str, Any] | bytes | str,
        **kwargs: Any,
    ) -> HostControlResult:
        if isinstance(request, ApplyControlRequest):
            context = request
        else:
            context = ApplyControlRequest(control=request, **kwargs)
        raw_message_id = _message_id(
            context.control if isinstance(context.control, Mapping) else {}
        )
        try:
            if context.current_event is not None:
                validate_model(context.current_event)
            control = validate_host_control(context.control)
            raw_message_id = control.message_id
        except Exception as exc:
            return _result(
                raw_message_id, status=HostControlStatus.REJECTED, error_code=_error_code_for(exc)
            )
        try:
            state = self._load_state(control, context.current_event)
            self._sweep_expired()
            tag = _control_payload_tag(control, self._require_key())
            prior = accepted_control_for(state, control.message_id)
            if prior is not None:
                if prior.payload_tag == tag:
                    return replace(prior.result, status=HostControlStatus.REPLAYED)
                return _result(
                    control.message_id,
                    status=HostControlStatus.REJECTED,
                    error_code=HostControlErrorCode.REPLAYED_WITH_DIFFERENT_PAYLOAD,
                )
            if len(state.accepted_controls) >= MAX_CONTROL_ACCEPTED_CONTROLS:
                return _result(
                    control.message_id,
                    status=HostControlStatus.REJECTED,
                    reason_code=HostControlReasonCode.CAPACITY_EXHAUSTED,
                    error_code=HostControlErrorCode.CAPACITY_EXHAUSTED,
                    effective_rigor=state.effective_rigor,
                )
            typed = validate_control_payload(
                control.message_type, control.payload, published=control.published
            )
            mutation = self._mutate(state, control, context, typed)
            result_status = (
                HostControlStatus.ACCEPTED
                if mutation.durable_mutation
                else HostControlStatus.ACCEPTED_NOT_RECORDED
            )
            result = _result(
                control.message_id,
                status=result_status,
                reason_code=mutation.reason_code,
                durable_mutation=mutation.durable_mutation,
                assigned_ids=mutation.assigned_ids,
                effective_rigor=mutation.state.effective_rigor,
                route=mutation.route,
                capability_limitations=mutation.capability_limitations,
                next_action=mutation.next_action,
            )
            if mutation.events:
                self._append(mutation.state, mutation.events)
            if (
                mutation.next_action is HostControlNextAction.STOP_CONTROL_CALLS
                or mutation.state.task_state
                in {
                    TaskState.CANCELLED,
                    TaskState.INSUFFICIENT,
                    TaskState.CONCLUDED,
                    TaskState.BYPASSED,
                }
            ):
                try:
                    self.turn_repository.delete(state)
                except Exception as exc:
                    raise ApplyControlError("turn state store unavailable") from exc
            else:
                accepted = AcceptedControl(
                    message_id=control.message_id, payload_tag=tag, result=result
                )
                replacement = append_accepted_control(mutation.state, accepted)
                try:
                    self.turn_repository.compare_and_swap(state, replacement)
                except Exception as exc:
                    raise ApplyControlError("turn state store unavailable") from exc
            return result
        except TurnStateExpired:
            return _result(
                control.message_id,
                status=HostControlStatus.REJECTED,
                error_code=HostControlErrorCode.EXPIRED_TOKEN,
            )
        except ReplayCapacityError:
            return _result(
                control.message_id,
                status=HostControlStatus.REJECTED,
                reason_code=HostControlReasonCode.CAPACITY_EXHAUSTED,
                error_code=HostControlErrorCode.CAPACITY_EXHAUSTED,
            )
        except ApplyControlError as exc:
            text = str(exc).lower()
            if "expired" in text:
                code = HostControlErrorCode.EXPIRED_TOKEN
            elif "invalid token" in text:
                code = HostControlErrorCode.INVALID_TOKEN
            elif "store" in text or "content" in text or "prompt bundle" in text:
                code = HostControlErrorCode.STORE_UNAVAILABLE
            elif "stale" in text:
                code = HostControlErrorCode.STALE_REFERENCE
            elif "transition" in text:
                code = HostControlErrorCode.INVALID_STATE_TRANSITION
            elif "capacity" in text:
                code = HostControlErrorCode.CAPACITY_EXHAUSTED
            else:
                code = HostControlErrorCode.INVALID_PAYLOAD
            reason = (
                HostControlReasonCode.STORE_UNAVAILABLE
                if code is HostControlErrorCode.STORE_UNAVAILABLE
                else None
            )
            return _result(
                control.message_id,
                status=HostControlStatus.REJECTED,
                reason_code=reason,
                error_code=code,
            )
        except (
            HostControlError,
            TurnStateError,
            OpenSocratesError,
            TypeError,
            ValueError,
            OSError,
        ) as exc:
            code = (
                HostControlErrorCode.STORE_UNAVAILABLE
                if "store" in str(exc).lower()
                else _error_code_for(exc)
            )
            reason = (
                HostControlReasonCode.STORE_UNAVAILABLE
                if code is HostControlErrorCode.STORE_UNAVAILABLE
                else None
            )
            return _result(
                control.message_id,
                status=HostControlStatus.REJECTED,
                reason_code=reason,
                error_code=code,
            )


def _append_event_placeholder(
    *,
    task_id: str,
    sequence: int,
    payload: Any,
    event_type: RecordEventType,
    occurred_at: str,
    host: Any,
    host_version: str,
    adapter_version: str,
    locale: str,
) -> RecordEvent:
    return RecordEvent.new(
        task_id=task_id,
        sequence=sequence,
        event_type=event_type,
        payload=payload,
        occurred_at=occurred_at,
        host=host,
        host_version=host_version,
        adapter_version=adapter_version,
        locale=locale,
    )


def apply_control(
    request: ApplyControlRequest | HostControl | Mapping[str, Any] | bytes | str,
    *,
    application: ControlApplication | None = None,
    turn_repository: TurnStateRepository | None = None,
    task_repository: TaskRepository | None = None,
    settings_repository: SettingsRepository | None = None,
    content_repository: ContentRepository | None = None,
    prompt_compiler: _PromptCompiler | None = None,
    capability_profile: CapabilityProfile | None = None,
    routing_catalog: RoutingCatalog = DEFAULT_ROUTING_CATALOG,
    clock: Clock | None = None,
    **kwargs: Any,
) -> HostControlResult:
    """Convenience function for CLI/hooks and focused walkthroughs."""

    if application is not None:
        if not isinstance(application, ControlApplication):
            raise ApplyControlError("application must be ControlApplication")
        return (
            application.apply(request, **kwargs)
            if not isinstance(request, ApplyControlRequest)
            else application.apply(request)
        )
    if isinstance(request, ApplyControlRequest):
        if turn_repository is None:
            raise ApplyControlError("turn_repository is required")
        return ControlApplication(
            turn_repository,
            task_repository=task_repository,
            settings_repository=settings_repository,
            content_repository=content_repository,
            prompt_compiler=prompt_compiler,
            capability_profile=capability_profile,
            routing_catalog=routing_catalog,
            clock=clock,
        ).apply(request)
    if turn_repository is None:
        raise ApplyControlError("turn_repository is required")
    context_kwargs = dict(kwargs)
    context_kwargs.setdefault("capability_profile", capability_profile)
    context = ApplyControlRequest(control=request, **context_kwargs)
    return ControlApplication(
        turn_repository,
        task_repository=task_repository,
        settings_repository=settings_repository,
        content_repository=content_repository,
        prompt_compiler=prompt_compiler,
        capability_profile=capability_profile,
        routing_catalog=routing_catalog,
        clock=clock,
    ).apply(context)


__all__ = ["ApplyControlError", "ApplyControlRequest", "ControlApplication", "apply_control"]
