"""Typed task repositories backed by the authoritative JSONL event store."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from opensocrates.domain.models import JudgmentEvent, TaskProjection
from opensocrates.domain.record_event import RecordEvent, RecordEventError
from opensocrates.domain.reducer import ReducerError, reduce_events

from .jsonl_store import AppendReceipt, JsonlRecordStore, RecordSequenceError


class TaskStoreError(OSError):
    """Raised when a task projection cannot be loaded or updated safely."""


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    task_id: str
    events: tuple[RecordEvent, ...]
    projection: TaskProjection


class TaskRepository(Protocol):
    """Minimal typed task-store surface used by application services."""

    def load_projection(self, task_id: str, *, month: str | None = None) -> TaskProjection | None:
        """Replay one task's validated event history."""

    def append(
        self, event: RecordEvent | JudgmentEvent, *, month: str | None = None
    ) -> AppendReceipt:
        """Append one closed event and return the persisted event receipt."""


class TaskStore:
    """Disk repository that preflights reducer legality before appending."""

    def __init__(self, records: JsonlRecordStore) -> None:
        self.records = records

    def load_events(self, task_id: str, *, month: str | None = None) -> tuple[RecordEvent, ...]:
        return self.records.read_events(task_id, month=month)

    def load_projection(self, task_id: str, *, month: str | None = None) -> TaskProjection | None:
        events = self.load_events(task_id, month=month)
        try:
            return reduce_events(events)
        except ReducerError as error:
            raise TaskStoreError("task projection is not replayable") from error

    def snapshot(self, task_id: str, *, month: str | None = None) -> TaskSnapshot | None:
        events = self.load_events(task_id, month=month)
        if not events:
            return None
        projection = reduce_events(events)
        if projection is None:
            return None
        return TaskSnapshot(task_id=task_id, events=events, projection=projection)

    def append(
        self, event: RecordEvent | JudgmentEvent, *, month: str | None = None
    ) -> AppendReceipt:
        if isinstance(event, JudgmentEvent):
            try:
                event = RecordEvent.from_judgment_event(event)
            except RecordEventError as error:
                raise TaskStoreError("event payload is not a closed public event") from error
        if not isinstance(event, RecordEvent):
            raise TypeError("task store accepts RecordEvent or JudgmentEvent only")
        existing = self.load_events(event.task_id, month=month or event.occurred_at[:7])
        candidate = (*existing, event)
        try:
            reduce_events(candidate)
        except ReducerError as error:
            raise TaskStoreError("event would create an illegal task transition") from error
        try:
            return self.records.append(event, month=month)
        except RecordSequenceError as error:
            raise TaskStoreError(
                "task changed concurrently; retry with a fresh sequence"
            ) from error


class InMemoryTaskStore:
    """Equivalent reducer-backed repository for focused demos and unit seams."""

    def __init__(self) -> None:
        self._events: dict[str, tuple[RecordEvent, ...]] = {}
        self._lock = RLock()

    def load_events(self, task_id: str) -> tuple[RecordEvent, ...]:
        with self._lock:
            return self._events.get(task_id, ())

    def load_projection(self, task_id: str) -> TaskProjection | None:
        with self._lock:
            events = self._events.get(task_id, ())
            return reduce_events(events)

    def append(self, event: RecordEvent | JudgmentEvent) -> RecordEvent:
        if isinstance(event, JudgmentEvent):
            try:
                event = RecordEvent.from_judgment_event(event)
            except RecordEventError as error:
                raise TaskStoreError("event payload is not a closed public event") from error
        if not isinstance(event, RecordEvent):
            raise TypeError("in-memory task store accepts RecordEvent or JudgmentEvent only")
        with self._lock:
            existing = self._events.get(event.task_id, ())
            try:
                reduce_events((*existing, event))
            except ReducerError as error:
                raise TaskStoreError("event would create an illegal task transition") from error
            self._events[event.task_id] = (*existing, event)
            return event

    def snapshot(self, task_id: str) -> TaskSnapshot | None:
        with self._lock:
            events = self._events.get(task_id, ())
            if not events:
                return None
            projection = reduce_events(events)
            if projection is None:
                return None
            return TaskSnapshot(task_id=task_id, events=events, projection=projection)

    def task_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._events))


__all__ = [
    "TaskRepository",
    "TaskSnapshot",
    "TaskStoreError",
    "TaskStore",
    "InMemoryTaskStore",
]
