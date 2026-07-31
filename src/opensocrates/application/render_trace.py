"""Build a public trace projection from validated typed record events.

The renderer deliberately lives in :mod:`opensocrates.rendering.trace`.  This
module only replays the closed event union and exposes a ``TraceView``; raw
JSON objects, host payloads, transcript data, and model calls are rejected at
this boundary.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from ..domain.enums import RecordEventType
from ..domain.models import (
    Alternative,
    ClaimVersion,
    CompletionResult,
    ConclusionCard,
    Conflict,
    Framing,
    TaskProjection,
    TraceView,
)
from ..domain.record_event import (
    AlternativePublishedPayload,
    ClaimPublishedPayload,
    CompletionCheckedPayload,
    ConclusionPublishedPayload,
    ConflictPublishedPayload,
    FramingPublishedPayload,
    RecordEvent,
    RecordEventError,
)
from ..domain.reducer import ReducerError, reduce_events
from ..domain.validation import validate_model
from ..errors import OpenSocratesError


class TraceProjectionError(ValueError):
    """Raised when typed events cannot produce a trustworthy ``TraceView``."""


class TraceDataState(StrEnum):
    """Honest storage states that a caller may surface to the user."""

    RECORDED = "recorded"
    NOT_RECORDED = "not_recorded"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    CORRUPT = "corrupt"


@dataclass(frozen=True, slots=True)
class TraceProjectionResult:
    """A view plus the storage state used to qualify it."""

    view: TraceView
    data_state: TraceDataState

    def __post_init__(self) -> None:
        if not isinstance(self.view, TraceView):
            raise TraceProjectionError("trace result requires TraceView")
        if not isinstance(self.data_state, TraceDataState):
            raise TraceProjectionError("trace result data state is not closed")


_METHOD_GAP_HINTS: Final[frozenset[str]] = frozenset(
    {
        "method_invocation_observation",
        "method_skill_invocation",
        "model_initiated_method_skill_activation",
    }
)
_PUBLIC_SHORT_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9A-HJKMNP-TV-Z]{8}$")
_TRACE_NOTE_BY_STATE: Final[dict[TraceDataState, str]] = {
    TraceDataState.NOT_RECORDED: "trace.not_recorded",
    TraceDataState.UNAVAILABLE: "trace.unavailable",
    TraceDataState.PARTIAL: "trace.record.partial",
    TraceDataState.CORRUPT: "trace.record.corrupt",
}


def _checked_projection(projection: TaskProjection) -> TaskProjection:
    if not isinstance(projection, TaskProjection):
        raise TraceProjectionError("trace projection requires TaskProjection")
    try:
        validate_model(projection)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TraceProjectionError("task projection is invalid") from error
    return projection


def _checked_card(projection: TaskProjection, card: ConclusionCard | None) -> ConclusionCard | None:
    if card is None:
        return None
    if not isinstance(card, ConclusionCard):
        raise TraceProjectionError("current card must be a typed ConclusionCard")
    try:
        validate_model(card)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TraceProjectionError("current card is invalid") from error
    if card.task_id != projection.task_id or str(card.locale) != str(projection.locale):
        raise TraceProjectionError("current card does not belong to this task and locale")
    return card


def _checked_events(
    events: Sequence[RecordEvent] | Iterable[RecordEvent],
) -> tuple[RecordEvent, ...]:
    if isinstance(events, (str, bytes, bytearray, Mapping)):
        raise TraceProjectionError("trace projection accepts typed RecordEvent values only")
    try:
        materialized = tuple(events)
    except TypeError as error:
        raise TraceProjectionError("trace events must be iterable") from error
    if not materialized:
        raise TraceProjectionError("trace requires at least one validated event")
    if any(not isinstance(event, RecordEvent) for event in materialized):
        raise TraceProjectionError("trace projection accepts typed RecordEvent values only")
    return materialized


def _fields(event: RecordEvent) -> Mapping[str, object]:
    try:
        fields = event.payload.public_fields()
    except (AttributeError, TypeError, ValueError) as error:
        raise TraceProjectionError("record payload is not projectable") from error
    if not isinstance(fields, Mapping):
        raise TraceProjectionError("record payload did not expose a mapping")
    return fields


def _model_payload(event: RecordEvent, expected: type[Any]) -> Any:
    payload = event.payload
    value = getattr(payload, "value", None)
    if not isinstance(payload, expected) or not isinstance(value, expected.model_type):
        raise TraceProjectionError("record payload is not the expected closed model")
    return value


def _summary_entry(
    event: RecordEvent,
    *,
    kind: str,
    summary: str,
    effect: str = "",
) -> dict[str, object]:
    """Create the only dictionary shape admitted to ``TraceView.chronology``."""

    if not all(isinstance(item, str) for item in (kind, summary, effect)):
        raise TraceProjectionError("trace chronology contains an unsafe summary")
    return {
        "sequence": event.sequence,
        "occurred_at": event.occurred_at,
        "kind": kind,
        "summary": summary,
        "effect": effect,
    }


def _method_projection(
    projection: TaskProjection,
    selected: Mapping[str, object] | None,
    activations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    gaps = set(projection.capability_gaps)
    unavailable = bool(gaps & _METHOD_GAP_HINTS)
    if selected is None:
        status = "unavailable" if unavailable else "none"
        return {
            "status": status,
            "activation_status": status,
            "primary_method": None,
            "complement_method": None,
            "selection_source": None,
            "confirmed_activations": (),
            "complement_cue": None,
        }

    primary = selected.get("primary_method")
    secondary = selected.get("secondary_method")
    confirmed = tuple(item["method_id"] for item in activations if item.get("method_id") == primary)
    if confirmed:
        activation_status = "confirmed"
        status = "confirmed"
    else:
        activation_status = "unavailable" if unavailable else "not_recorded"
        status = "selected"
    return {
        "status": status,
        "activation_status": activation_status,
        "primary_method": primary,
        "complement_method": secondary,
        "selection_source": selected.get("selection_source"),
        "confirmed_activations": confirmed,
        # A complement is a cue only.  It is never added to confirmed
        # activations, even if an untrusted event tries to name it.
        "complement_cue": secondary,
    }


def _public_short_id(task_id: str, supplied: str | None) -> str:
    # The public selector is the last eight Crockford characters of the local
    # ULID.  It is a display/selection handle, never a globally meaningful ID.
    value = task_id[-8:] if supplied is None else supplied
    if not isinstance(value, str) or _PUBLIC_SHORT_ID_RE.fullmatch(value) is None:
        raise TraceProjectionError("public short ID must be exactly eight alphanumeric characters")
    return value


def _validated_notes(values: Iterable[str]) -> set[str]:
    if isinstance(values, (str, bytes, bytearray, Mapping)):
        raise TraceProjectionError("trace capability notes must be a sequence of safe keys")
    try:
        materialized = tuple(values)
    except TypeError as error:
        raise TraceProjectionError("trace capability notes must be iterable") from error
    notes: set[str] = set()
    for note in materialized:
        if (
            not isinstance(note, str)
            or not note
            or len(note) > 128
            or "\n" in note
            or "\r" in note
            or "\x00" in note
            or "/" in note
            or "\\" in note
        ):
            raise TraceProjectionError("trace capability notes must be safe keys")
        notes.add(note)
    return notes


def project_trace(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    projection: TaskProjection,
    events: Sequence[RecordEvent] | Iterable[RecordEvent],
    *,
    public_short_id: str | None = None,
    current_card: ConclusionCard | None = None,
    capability_notes: Iterable[str] = (),
) -> TraceView:
    """Replay validated events into a deterministic public ``TraceView``."""

    projection = _checked_projection(projection)
    materialized = _checked_events(events)
    if any(event.task_id != projection.task_id for event in materialized):
        raise TraceProjectionError("trace event task ID does not match projection")
    try:
        replayed = reduce_events(materialized)
    except (ReducerError, RecordEventError, TypeError, ValueError) as error:
        raise TraceProjectionError("record events are not replayable") from error
    if replayed != projection:
        raise TraceProjectionError("task projection does not match the event replay")
    current_card = _checked_card(projection, current_card)

    framing: Framing | None = None
    claims: list[ClaimVersion] = []
    conflicts: list[Conflict] = []
    alternatives: list[Alternative] = []
    completion: CompletionResult | None = None
    selected: Mapping[str, object] | None = None
    activations: list[Mapping[str, object]] = []
    chronology: list[dict[str, object]] = []

    for event in materialized:
        fields = _fields(event)
        event_type = event.event_type
        if event_type is RecordEventType.TASK_STARTED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="",
                    effect="",
                )
            )
        elif event_type is RecordEventType.FRAMING_PUBLISHED:
            framing = _model_payload(event, FramingPublishedPayload)
        elif event_type is RecordEventType.METHOD_SELECTED:
            selected = {
                "primary_method": fields.get("primary_method"),
                "secondary_method": fields.get("secondary_method"),
                "selection_source": fields.get("selection_source"),
            }
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=str(fields.get("primary_method", "")),
                    effect="",
                )
            )
        elif event_type is RecordEventType.METHOD_ACTIVATED:
            method_id = fields.get("method_id")
            activation_source = fields.get("activation_source")
            activation = {"method_id": method_id, "activation_source": activation_source}
            activations.append(activation)
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=str(method_id),
                    effect="",
                )
            )
        elif event_type is RecordEventType.JUDGMENT_STARTED:
            judgment_id = fields.get("judgment_id", "")
            version = fields.get("version", "")
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=f"{judgment_id} v{version}",
                    effect="",
                )
            )
        elif event_type is RecordEventType.OBSERVATION_CHECK_REQUESTED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="",
                    effect="",
                )
            )
        elif event_type is RecordEventType.INTERVENTION_PUBLISHED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=str(fields.get("summary", "")),
                    effect=str(fields.get("action", "")),
                )
            )
        elif event_type is RecordEventType.CLAIM_PUBLISHED:
            value = _model_payload(event, ClaimPublishedPayload)
            claims.append(value)
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=value.text,
                    effect="",
                )
            )
        elif event_type is RecordEventType.SOURCE_PUBLISHED:
            source = getattr(event.payload, "value", None)
            display_name = getattr(source, "display_name", None)
            if not isinstance(display_name, str):
                raise TraceProjectionError("source event did not contain a safe display name")
            chronology.append(
                _summary_entry(event, kind=event_type.value, summary=display_name, effect="")
            )
        elif event_type is RecordEventType.CONFLICT_PUBLISHED:
            value = _model_payload(event, ConflictPublishedPayload)
            conflicts.append(value)
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=value.summary,
                    effect="",
                )
            )
        elif event_type is RecordEventType.CONFLICT_RESOLVED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=str(fields.get("public_reason", "")),
                    effect="",
                )
            )
        elif event_type is RecordEventType.ALTERNATIVE_PUBLISHED:
            value = _model_payload(event, AlternativePublishedPayload)
            alternatives.append(value)
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=value.name,
                    effect=value.reason,
                )
            )
        elif event_type is RecordEventType.CONCLUSION_PUBLISHED:
            value = _model_payload(event, ConclusionPublishedPayload)
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=value.conclusion or "",
                    effect=value.change_reason or "",
                )
            )
        elif event_type is RecordEventType.CROSS_EXAM_COMPLETED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=str(fields.get("findings_summary", "")),
                    effect="",
                )
            )
        elif event_type is RecordEventType.COMPLETION_CHECKED:
            completion = _model_payload(event, CompletionCheckedPayload)
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="",
                    effect="",
                )
            )
        elif event_type is RecordEventType.REPAIR_REQUESTED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="",
                    effect="",
                )
            )
        elif event_type is RecordEventType.VERIFICATION_FAILED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary=str(fields.get("reason", "")),
                    effect="",
                )
            )
        elif event_type is RecordEventType.CAPABILITY_DEGRADED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="",
                    effect="",
                )
            )
        elif event_type is RecordEventType.TASK_CONCLUDED:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="",
                    effect="",
                )
            )
        elif event_type is RecordEventType.TASK_INSUFFICIENT:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="; ".join(str(item) for item in fields.get("missing_items", ())),  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
                    effect="",
                )
            )
        elif event_type is RecordEventType.TASK_CANCELLED:
            chronology.append(_summary_entry(event, kind=event_type.value, summary="", effect=""))
        elif event_type is RecordEventType.RECOVERED_FROM_TORN_TAIL:
            chronology.append(
                _summary_entry(
                    event,
                    kind=event_type.value,
                    summary="",
                    effect="",
                )
            )

    note_values = _validated_notes(projection.capability_gaps)
    note_values.update(_validated_notes(capability_notes))
    view = TraceView(
        task_id=projection.task_id,
        public_short_id=_public_short_id(projection.task_id, public_short_id),
        status=projection.state,
        terminal_reason=projection.terminal_reason,
        locale=projection.locale,
        framing=framing,
        chronology=tuple(chronology),
        methods=_method_projection(projection, selected, activations),
        claim_history=tuple(claims),
        conflicts=tuple(conflicts),
        alternatives=tuple(alternatives),
        completion=completion,
        current_card=current_card,
        capability_notes=tuple(sorted(note_values)),
    )
    try:
        validate_model(view)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TraceProjectionError("trace view is invalid") from error
    return view


def unavailable_trace(
    projection: TaskProjection,
    *,
    data_state: TraceDataState,
    public_short_id: str | None = None,
    current_card: ConclusionCard | None = None,
    capability_notes: Iterable[str] = (),
) -> TraceView:
    """Create an honest empty view when records are missing or unreadable."""

    projection = _checked_projection(projection)
    current_card = _checked_card(projection, current_card)
    if not isinstance(data_state, TraceDataState):
        raise TraceProjectionError("trace data state is not closed")
    if data_state is TraceDataState.RECORDED:
        raise TraceProjectionError("recorded state requires validated events")
    notes = _validated_notes(projection.capability_gaps)
    notes.update(_validated_notes(capability_notes))
    notes.add(_TRACE_NOTE_BY_STATE[data_state])
    methods = {
        "status": "unavailable"
        if data_state is not TraceDataState.NOT_RECORDED
        else "not_recorded",
        "activation_status": "unavailable"
        if data_state is not TraceDataState.NOT_RECORDED
        else "not_recorded",
        "primary_method": None,
        "complement_method": None,
        "selection_source": None,
        "confirmed_activations": (),
        "complement_cue": None,
    }
    view = TraceView(
        task_id=projection.task_id,
        public_short_id=_public_short_id(projection.task_id, public_short_id),
        status=projection.state,
        terminal_reason=projection.terminal_reason,
        locale=projection.locale,
        framing=None,
        chronology=(),
        methods=methods,
        claim_history=(),
        conflicts=(),
        alternatives=(),
        completion=None,
        current_card=current_card,
        capability_notes=tuple(sorted(str(note) for note in notes)),
    )
    try:
        validate_model(view)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TraceProjectionError("unavailable trace view is invalid") from error
    return view


def project_trace_result(
    projection: TaskProjection,
    events: Sequence[RecordEvent] | Iterable[RecordEvent] | None,
    *,
    data_state: TraceDataState = TraceDataState.RECORDED,
    **kwargs: object,
) -> TraceProjectionResult:
    """Return a qualified view without reconstructing unreadable records."""

    if data_state is not TraceDataState.RECORDED or events is None:
        selected_state = (
            data_state if data_state is not TraceDataState.RECORDED else TraceDataState.NOT_RECORDED
        )
        return TraceProjectionResult(
            view=unavailable_trace(projection, data_state=selected_state, **kwargs),  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            data_state=selected_state,
        )
    return TraceProjectionResult(
        view=project_trace(projection, events, **kwargs),  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        data_state=TraceDataState.RECORDED,
    )


build_trace_view = project_trace


__all__ = [
    "TraceDataState",
    "TraceProjectionError",
    "TraceProjectionResult",
    "build_trace_view",
    "project_trace",
    "project_trace_result",
    "unavailable_trace",
]
