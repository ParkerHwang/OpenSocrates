"""Deterministic, pure replay into the canonical S01 ``TaskProjection``."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from opensocrates.errors import OpenSocratesError

from .enums import RecordEventType, Rigor, TaskState, TaskTerminalReason
from .models import TaskProjection
from .record_event import RecordEvent
from .task_state import TaskTransitionError, transition_state
from .validation import validate_model


class ReducerError(ValueError):
    """Raised when a record cannot be replayed into a valid projection."""

    def __init__(self, message: str, *, sequence: int | None = None) -> None:
        super().__init__(message)
        self.sequence = sequence


def _payload_fields(event: RecordEvent) -> Mapping[str, object]:
    try:
        return event.payload.public_fields()
    except (AttributeError, TypeError, ValueError) as error:
        raise ReducerError("event payload cannot be projected", sequence=event.sequence) from error


def _terminal_reason(value: object) -> TaskTerminalReason:
    try:
        return TaskTerminalReason(value)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise ReducerError("event contains an unknown terminal reason") from error


def _initial_projection(event: RecordEvent) -> TaskProjection:
    if event.event_type is not RecordEventType.TASK_STARTED or event.sequence != 1:
        raise ReducerError("first record event must be task_started", sequence=event.sequence)
    fields = _payload_fields(event)
    try:
        requested_rigor = Rigor(fields["requested_rigor"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        effective_rigor = Rigor(fields["effective_rigor"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        host_session_key = fields["host_session_key"]
    except (KeyError, TypeError, ValueError) as error:
        raise ReducerError("task_started fields are invalid", sequence=event.sequence) from error
    if not isinstance(host_session_key, str):
        raise ReducerError("task_started host_session_key is invalid", sequence=event.sequence)
    reason = fields.get("participation_reason")
    state = (
        TaskState.BYPASSED
        if reason
        in {
            "direct_transformation",
            "direct_artifact_action",
            "direct_retrieval",
            "explicit_method_without_judgment",
        }
        else TaskState.FRAMING
    )
    projection = TaskProjection(
        task_id=event.task_id,
        state=state,
        terminal_reason=TaskTerminalReason.MECHANICAL if state is TaskState.BYPASSED else None,
        locale=event.locale,
        requested_rigor=requested_rigor,
        effective_rigor=effective_rigor,
        host=event.host,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        host_session_key=host_session_key,
        current_judgment_id=None,
        repair_count=0,
        capability_gaps=tuple(fields.get("capability_gaps", ())),  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        latest_sequence=event.sequence,
        created_at=event.occurred_at,
        updated_at=event.occurred_at,
    )
    try:
        validate_model(projection)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise ReducerError(
            "task_started did not produce a valid TaskProjection", sequence=event.sequence
        ) from error
    return projection


def apply_event(projection: TaskProjection, event: RecordEvent) -> TaskProjection:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Apply exactly one known event, returning a new canonical projection."""

    if not isinstance(projection, TaskProjection):
        raise ReducerError("reducer accepts the canonical TaskProjection only")
    if not isinstance(event, RecordEvent):
        raise ReducerError("reducer accepts RecordEvent instances only")
    if not isinstance(event.event_type, RecordEventType):
        raise ReducerError("unknown record event type", sequence=getattr(event, "sequence", None))
    if event.task_id != projection.task_id:
        raise ReducerError("event task_id does not match projection", sequence=event.sequence)
    if event.host != projection.host:
        raise ReducerError("event host changed within a task", sequence=event.sequence)
    if event.sequence != projection.latest_sequence + 1:
        raise ReducerError("record event sequence is not contiguous", sequence=event.sequence)

    fields = _payload_fields(event)
    try:
        next_state = transition_state(projection.state, event.event_type, fields)
    except TaskTransitionError as error:
        raise ReducerError(str(error), sequence=event.sequence) from error

    current = replace(
        projection,
        state=next_state,
        locale=event.locale,
        latest_sequence=event.sequence,
        updated_at=event.occurred_at,
    )

    if event.event_type is RecordEventType.JUDGMENT_STARTED:
        judgment_id = fields.get("judgment_id")
        if not isinstance(judgment_id, str):
            raise ReducerError("judgment_started id is invalid", sequence=event.sequence)
        current = replace(current, current_judgment_id=judgment_id)
    elif event.event_type is RecordEventType.CONCLUSION_PUBLISHED:
        value = fields.get("judgment_version")
        judgment_id: object = None  # type: ignore[no-redef]  # Closed runtime boundary validates this value.
        if isinstance(value, Mapping):
            judgment_id = value.get("judgment_id")
        else:
            judgment_id = getattr(value, "judgment_id", None)
        if judgment_id is not None:
            if not isinstance(judgment_id, str):
                raise ReducerError("conclusion judgment id is invalid", sequence=event.sequence)
            current = replace(current, current_judgment_id=judgment_id)
    elif event.event_type is RecordEventType.REPAIR_REQUESTED:
        repair_count = fields.get("repair_count")
        if repair_count != 1 or current.repair_count >= 1:
            raise ReducerError("record contains more than one repair", sequence=event.sequence)
        current = replace(current, repair_count=1)
    elif event.event_type is RecordEventType.CAPABILITY_DEGRADED:
        capability_key = fields.get("capability_key")
        if not isinstance(capability_key, str):
            raise ReducerError("capability_degraded key is invalid", sequence=event.sequence)
        current = replace(
            current, capability_gaps=tuple(sorted(set((*current.capability_gaps, capability_key))))
        )
    elif event.event_type is RecordEventType.TASK_CONCLUDED:
        current = replace(current, terminal_reason=_terminal_reason(fields.get("terminal_reason")))
    elif event.event_type is RecordEventType.TASK_INSUFFICIENT:
        current = replace(current, terminal_reason=_terminal_reason(fields.get("terminal_reason")))
    elif event.event_type is RecordEventType.TASK_CANCELLED:
        current = replace(current, terminal_reason=TaskTerminalReason.USER_CANCELLED)
    elif event.event_type is RecordEventType.VERIFICATION_FAILED:
        current = replace(current, terminal_reason=TaskTerminalReason.VERIFIER_FAILED)

    try:
        validate_model(current)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise ReducerError(
            "event produced an invalid TaskProjection", sequence=event.sequence
        ) from error
    return current


def reduce_events(events: Sequence[RecordEvent] | Iterable[RecordEvent]) -> TaskProjection | None:
    """Replay a complete ordered event history into a canonical projection."""

    iterator = iter(events)
    try:
        first = next(iterator)
    except StopIteration:
        return None
    if not isinstance(first, RecordEvent):
        raise ReducerError("reducer accepts RecordEvent instances only")
    seen_ids = {first.event_id}
    projection = _initial_projection(first)
    for event in iterator:
        if not isinstance(event, RecordEvent):
            raise ReducerError("reducer accepts RecordEvent instances only")
        if event.event_id in seen_ids:
            raise ReducerError("duplicate record event id", sequence=event.sequence)
        seen_ids.add(event.event_id)
        projection = apply_event(projection, event)
    return projection


def project_events(events: Sequence[RecordEvent] | Iterable[RecordEvent]) -> TaskProjection | None:
    """Alias emphasizing that the reducer is the projection authority."""

    return reduce_events(events)


__all__ = ["ReducerError", "TaskProjection", "apply_event", "reduce_events", "project_events"]
