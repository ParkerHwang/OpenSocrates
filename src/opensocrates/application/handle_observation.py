"""Application command for normalized evidence-bearing observations.

This use case only reads an active ``TaskProjection`` and returns a typed
content-free command.  It never parses a native event, appends a record, or
retains a raw tool result.  S14's host-control/turn-state owner applies the
returned command and owns any cross-process mutation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import InterventionClass
from ..domain.models import TaskProjection
from ..domain.observation import (
    ObservationDecision,
    ObservationDedupeState,
    ObservationMetadata,
    assess_observation,
)
from ..domain.record_event import ObservationCheckRequestedPayload
from .ports import TaskRepository


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationCommand:
    """The only durable command an eligible observation may produce."""

    payload: ObservationCheckRequestedPayload
    next_dedupe_state: ObservationDedupeState


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationHandlingResult:
    """Decision plus optional record command; empty paths have no payload."""

    decision: ObservationDecision
    command: ObservationCommand | None = None

    @property
    def eligible(self) -> bool:
        return self.command is not None

    @property
    def should_record(self) -> bool:
        return self.command is not None


def _command(decision: ObservationDecision) -> ObservationCommand | None:
    if not decision.eligible or decision.fingerprint is None or decision.tool_category is None:
        return None
    payload = ObservationCheckRequestedPayload(
        tool_category=decision.tool_category,
        dedupe_fingerprint=decision.fingerprint,
    )
    return ObservationCommand(
        payload=payload,
        next_dedupe_state=ObservationDedupeState(
            fingerprints=decision.next_fingerprints,
            batch_tags=decision.next_batch_tags,
        ),
    )


def handle_observation(
    metadata: ObservationMetadata,
    task: TaskProjection | None,
    *,
    dedupe_state: ObservationDedupeState | None = None,
    active_task_tag: str | None = None,
    intervention_class: InterventionClass = InterventionClass.WEAK_EVIDENCE,
) -> ObservationHandlingResult:
    """Evaluate one normalized observation and return a pure application command."""

    decision = assess_observation(
        metadata,
        task,
        dedupe_state=dedupe_state,
        active_task_tag=active_task_tag,
        intervention_class=intervention_class,
    )
    return ObservationHandlingResult(decision=decision, command=_command(decision))


def handle_observation_for_task(
    task_repository: TaskRepository,
    task_id: str,
    metadata: ObservationMetadata,
    *,
    dedupe_state: ObservationDedupeState | None = None,
    active_task_tag: str | None = None,
    intervention_class: InterventionClass = InterventionClass.WEAK_EVIDENCE,
) -> ObservationHandlingResult:
    """Read one task projection, then evaluate without mutating the repository."""

    task = task_repository.load_projection(task_id)
    return handle_observation(
        metadata,
        task,
        dedupe_state=dedupe_state,
        active_task_tag=active_task_tag,
        intervention_class=intervention_class,
    )


# Compatibility names for host-control integration.
ObservationResult = ObservationHandlingResult
evaluate_observation = handle_observation
apply_observation = handle_observation


__all__ = [
    "ObservationCommand",
    "ObservationHandlingResult",
    "ObservationResult",
    "apply_observation",
    "evaluate_observation",
    "handle_observation",
    "handle_observation_for_task",
]
