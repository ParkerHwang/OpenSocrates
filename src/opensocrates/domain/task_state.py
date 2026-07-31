"""Pure task-state transition rules for the judgment record event log."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from .enums import RecordEventType, TaskState, TaskTerminalReason


class TaskTransitionError(ValueError):
    """Raised when an event cannot legally follow the current task state."""


class TransitionKind(StrEnum):
    KEEP = "keep"
    MOVE = "move"


_MECHANICAL_REASONS = {
    "direct_transformation",
    "direct_artifact_action",
    "direct_retrieval",
    "explicit_method_without_judgment",
}


def _allowed(event_type: RecordEventType, state: TaskState) -> bool:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if event_type is RecordEventType.RECOVERED_FROM_TORN_TAIL:
        return True
    if state in {
        TaskState.BYPASSED,
        TaskState.CONCLUDED,
        TaskState.CANCELLED,
        TaskState.INSUFFICIENT,
    }:
        return False
    if event_type is RecordEventType.TASK_STARTED:
        return state is TaskState.NEW
    if event_type is RecordEventType.FRAMING_PUBLISHED:
        return state is TaskState.FRAMING
    if event_type in {
        RecordEventType.METHOD_SELECTED,
        RecordEventType.METHOD_ACTIVATED,
        RecordEventType.JUDGMENT_STARTED,
    }:
        return state in {TaskState.FRAMING, TaskState.WORKING, TaskState.REJUDGING}
    if event_type in {
        RecordEventType.OBSERVATION_CHECK_REQUESTED,
        RecordEventType.INTERVENTION_PUBLISHED,
        RecordEventType.CLAIM_PUBLISHED,
        RecordEventType.SOURCE_PUBLISHED,
        RecordEventType.ALTERNATIVE_PUBLISHED,
    }:
        return state in {TaskState.FRAMING, TaskState.WORKING, TaskState.REJUDGING}
    if event_type is RecordEventType.CONFLICT_PUBLISHED:
        return state in {TaskState.WORKING, TaskState.REJUDGING}
    if event_type is RecordEventType.CONFLICT_RESOLVED:
        return state is TaskState.REJUDGING
    if event_type is RecordEventType.CONCLUSION_PUBLISHED:
        return state in {TaskState.WORKING, TaskState.REJUDGING}
    if event_type is RecordEventType.CROSS_EXAM_COMPLETED:
        return state is TaskState.CROSS_EXAMINING
    if event_type is RecordEventType.COMPLETION_CHECKED:
        return state is TaskState.VERIFYING
    if event_type is RecordEventType.REPAIR_REQUESTED:
        return state is TaskState.VERIFYING
    if event_type is RecordEventType.VERIFICATION_FAILED:
        return state is TaskState.VERIFYING
    if event_type is RecordEventType.CAPABILITY_DEGRADED:
        return state not in {TaskState.NEW, TaskState.BYPASSED}
    if event_type is RecordEventType.TASK_CONCLUDED:
        return state in {
            TaskState.FRAMING,
            TaskState.WORKING,
            TaskState.REJUDGING,
            TaskState.CROSS_EXAMINING,
            TaskState.VERIFYING,
            TaskState.DEGRADED,
        }
    if event_type is RecordEventType.TASK_INSUFFICIENT:
        return state in {
            TaskState.FRAMING,
            TaskState.WORKING,
            TaskState.REJUDGING,
            TaskState.CROSS_EXAMINING,
            TaskState.VERIFYING,
            TaskState.DEGRADED,
        }
    if event_type is RecordEventType.TASK_CANCELLED:
        return state not in {TaskState.NEW}
    return False


def transition_state(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    state: TaskState,
    event_type: RecordEventType,
    payload: Mapping[str, object],
) -> TaskState:
    """Return the next state or reject the event without mutation."""

    if not _allowed(event_type, state):
        raise TaskTransitionError(f"illegal {event_type.value} from {state.value}")
    if event_type is RecordEventType.TASK_STARTED:
        reason = payload.get("participation_reason")
        return TaskState.BYPASSED if reason in _MECHANICAL_REASONS else TaskState.FRAMING
    if event_type is RecordEventType.FRAMING_PUBLISHED:
        return TaskState.WORKING
    if event_type is RecordEventType.CONFLICT_PUBLISHED:
        return TaskState.REJUDGING
    if event_type is RecordEventType.CONFLICT_RESOLVED:
        return TaskState.WORKING
    if event_type is RecordEventType.CONCLUSION_PUBLISHED:
        return TaskState.CROSS_EXAMINING
    if event_type is RecordEventType.CROSS_EXAM_COMPLETED:
        return TaskState.VERIFYING
    if event_type is RecordEventType.REPAIR_REQUESTED:
        return TaskState.WORKING
    if event_type is RecordEventType.VERIFICATION_FAILED:
        return TaskState.INSUFFICIENT
    if event_type is RecordEventType.CAPABILITY_DEGRADED:
        return TaskState.DEGRADED if state is TaskState.VERIFYING else state
    if event_type is RecordEventType.TASK_INSUFFICIENT:
        return TaskState.INSUFFICIENT
    if event_type is RecordEventType.TASK_CANCELLED:
        return TaskState.CANCELLED
    if event_type is RecordEventType.TASK_CONCLUDED:
        raw_reason = payload.get("terminal_reason")
        if not isinstance(raw_reason, str):
            raise TaskTransitionError("task_concluded has an invalid terminal reason")
        try:
            reason = TaskTerminalReason(raw_reason)
        except ValueError as error:
            raise TaskTransitionError("task_concluded has an invalid terminal reason") from error
        if reason is TaskTerminalReason.MECHANICAL:
            return TaskState.BYPASSED
        if reason is TaskTerminalReason.USER_CANCELLED:
            return TaskState.CANCELLED
        if reason is TaskTerminalReason.CRITERIA_SATISFIED:
            return TaskState.CONCLUDED
        if reason in {
            TaskTerminalReason.CAPABILITY_MISSING,
            TaskTerminalReason.VERIFIER_UNAVAILABLE,
        }:
            return TaskState.DEGRADED
        return TaskState.INSUFFICIENT
    return state


def legal_event(event_type: RecordEventType, state: TaskState) -> bool:
    """Expose the closed transition table for callers and focused checks."""

    return _allowed(event_type, state)


__all__ = ["TaskTransitionError", "TransitionKind", "transition_state", "legal_event"]
