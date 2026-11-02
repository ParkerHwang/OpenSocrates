"""Local coordination with transient bodies and explicit host evidence boundaries.

Adapters and authorizers are trusted application ports, not user-supplied flags.
An adapter must establish its own actual host/conversation binding; an identifier
inside this module does not establish a user's identity or grant file access.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from threading import RLock
from typing import Protocol
from uuid import uuid4


class RuntimeState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    CLOSED = "closed"


class TaskState(StrEnum):
    REQUESTED = "requested"
    WAITING_AUTHORITY = "waiting_authority"
    UNAVAILABLE = "unavailable"
    SESSION_CREATED = "session_created"
    DELIVERY_REPORTED = "delivery_reported"
    DELIVERY_UNCONFIRMED = "delivery_unconfirmed"
    EFFECT_UNKNOWN = "effect_unknown"


class DeliveryState(StrEnum):
    ATTEMPTED = "attempted"
    SENT_UNCONFIRMED = "sent_unconfirmed"
    DELIVERED = "delivered"
    REFUSED = "refused"
    EFFECT_UNKNOWN = "effect_unknown"


class Permission(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    UNKNOWN = "unknown"


class Action(StrEnum):
    CREATE_SESSION = "create_session"
    DELIVER = "deliver"


class ServiceError(ValueError):
    """Fixed, content-free application errors."""

    def __init__(self, code: str) -> None:
        known = {
            "invalid_reference", "invalid_revision", "invalid_transient_payload",
            "invalid_task_state", "invalid_error_code", "invalid_delivery_state",
            "unverified_read_or_application", "invalid_creation_outcome",
            "missing_created_session", "invalid_capacity", "state_capacity_reached",
            "session_reference_conflict", "revision_conflict", "host_registration_conflict",
            "service_closed", "service_not_running", "request_identity_already_attempted",
            "unknown_task_or_session", "recipient_or_authority_unconfirmed",
            "host_unavailable", "operation_state_unknown",
        }
        super().__init__(code if type(code) is str and code in known else "operation_state_unknown")


def _reference(value: str) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ServiceError("invalid_reference")
    if any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in value):
        raise ServiceError("invalid_reference")


def _revision(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ServiceError("invalid_revision")


@dataclass(frozen=True, slots=True)
class TransientPayload:
    """A current call's body. Never included in service state or error text."""

    text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text or len(self.text) > 65_536:
            raise ServiceError("invalid_transient_payload")


@dataclass(frozen=True, slots=True)
class ServiceTask:
    task_id: str
    project_ref: str
    intake_ref: str
    host_ref: str
    authority_ref: str
    state: TaskState = TaskState.REQUESTED
    revision: int = 0
    execution_ref: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        for reference in (
            self.task_id, self.project_ref, self.intake_ref, self.host_ref, self.authority_ref
        ):
            _reference(reference)
        if self.execution_ref is not None:
            _reference(self.execution_ref)
        _revision(self.revision)
        if not isinstance(self.state, TaskState):
            raise ServiceError("invalid_task_state")
        if self.error_code not in {
            None,
            "authority_unconfirmed",
            "host_unavailable",
            "session_creation_unconfirmed",
            "created_session_state_unknown",
            "recipient_unconfirmed",
        }:
            raise ServiceError("invalid_error_code")


@dataclass(frozen=True, slots=True)
class ServiceSession:
    session_ref: str
    task_id: str
    host_ref: str
    project_ref: str

    def __post_init__(self) -> None:
        for reference in (self.session_ref, self.task_id, self.host_ref, self.project_ref):
            _reference(reference)


@dataclass(frozen=True, slots=True)
class ServiceDelivery:
    request_id: str
    task_id: str
    sender_ref: str
    destination_ref: str
    state: DeliveryState
    revision: int = 0
    read: str = "unknown"
    applied: str = "unknown"

    def __post_init__(self) -> None:
        for reference in (
            self.request_id, self.task_id, self.sender_ref, self.destination_ref
        ):
            _reference(reference)
        _revision(self.revision)
        if not isinstance(self.state, DeliveryState):
            raise ServiceError("invalid_delivery_state")
        if self.read != "unknown" or self.applied != "unknown":
            raise ServiceError("unverified_read_or_application")


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    action: Action
    task: ServiceTask
    sender_ref: str
    destination: ServiceSession | None
    authority_ref: str


@dataclass(frozen=True, slots=True)
class SessionCreation:
    session_ref: str | None = None
    outcome: str = "unavailable"

    def __post_init__(self) -> None:
        if self.session_ref is not None:
            _reference(self.session_ref)
        if self.outcome not in {"created", "unavailable", "unknown"}:
            raise ServiceError("invalid_creation_outcome")
        if self.outcome == "created" and self.session_ref is None:
            raise ServiceError("missing_created_session")


class StateStore(Protocol):
    """A metadata-only state repository. Saves use expected-revision semantics."""

    def task(self, task_id: str) -> ServiceTask | None: ...

    def save_task(self, value: ServiceTask, expected_revision: int | None) -> None: ...

    def session(self, session_ref: str) -> ServiceSession | None: ...

    def save_session(self, value: ServiceSession) -> None: ...

    def delivery(self, request_id: str) -> ServiceDelivery | None: ...

    def save_delivery(self, value: ServiceDelivery, expected_revision: int | None) -> None: ...

    def counts(self) -> tuple[int, int, int]: ...


class ServiceHost(Protocol):
    """An actual host binding or an explicitly identified synthetic test adapter."""

    def create_session(self, task_id: str) -> SessionCreation: ...

    def deliver(
        self, session: ServiceSession, request_id: str, payload: TransientPayload
    ) -> DeliveryState: ...


class Authorizer(Protocol):
    def __call__(self, request: AuthorizationRequest) -> Permission: ...


def _unknown_authority(request: AuthorizationRequest) -> Permission:
    return Permission.UNKNOWN


class MemoryStateStore:
    """Bounded-process metadata state. Closing the process loses this state."""

    def __init__(self, capacity: int = 10_000) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ServiceError("invalid_capacity")
        self._capacity = capacity
        self._tasks: dict[str, ServiceTask] = {}
        self._sessions: dict[str, ServiceSession] = {}
        self._deliveries: dict[str, ServiceDelivery] = {}
        self._lock = RLock()

    def _room(self, exists: bool) -> None:
        if not exists and sum(self.counts()) >= self._capacity:
            raise ServiceError("state_capacity_reached")

    def task(self, task_id: str) -> ServiceTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def save_task(self, value: ServiceTask, expected_revision: int | None) -> None:
        with self._lock:
            old = self._tasks.get(value.task_id)
            self._check_revision(old.revision if old else None, expected_revision, value.revision)
            self._room(old is not None)
            self._tasks[value.task_id] = value

    def session(self, session_ref: str) -> ServiceSession | None:
        with self._lock:
            return self._sessions.get(session_ref)

    def save_session(self, value: ServiceSession) -> None:
        with self._lock:
            if value.session_ref in self._sessions:
                raise ServiceError("session_reference_conflict")
            self._room(False)
            self._sessions[value.session_ref] = value

    def delivery(self, request_id: str) -> ServiceDelivery | None:
        with self._lock:
            return self._deliveries.get(request_id)

    def save_delivery(self, value: ServiceDelivery, expected_revision: int | None) -> None:
        with self._lock:
            old = self._deliveries.get(value.request_id)
            self._check_revision(old.revision if old else None, expected_revision, value.revision)
            self._room(old is not None)
            self._deliveries[value.request_id] = value

    @staticmethod
    def _check_revision(old: int | None, expected: int | None, new: int) -> None:
        if old != expected or new != (0 if old is None else old + 1):
            raise ServiceError("revision_conflict")

    def counts(self) -> tuple[int, int, int]:
        with self._lock:
            return len(self._tasks), len(self._sessions), len(self._deliveries)


class RuntimeService:
    """Coordinates real adapter calls without executing a model itself.

    No host is enabled by default. The authorizer must check task authority and
    the adapter's actual recipient binding. Host-reported delivery is separate
    from reading, application, completion, and independently observed evidence.
    """

    def __init__(
        self,
        store: StateStore | None = None,
        authorizer: Authorizer | None = None,
    ) -> None:
        self.store = store if store is not None else MemoryStateStore()
        self._authorize = authorizer if authorizer is not None else _unknown_authority
        self._hosts: dict[str, ServiceHost] = {}
        self._state = RuntimeState.STOPPED
        self._lock = RLock()

    def register_host(self, reference: str, adapter: ServiceHost) -> None:
        _reference(reference)
        with self._lock:
            if self._state is RuntimeState.CLOSED or reference in self._hosts:
                raise ServiceError("host_registration_conflict")
            self._hosts[reference] = adapter

    def start(self) -> None:
        with self._lock:
            if self._state is RuntimeState.CLOSED:
                raise ServiceError("service_closed")
            self._state = RuntimeState.RUNNING

    def stop(self) -> None:
        with self._lock:
            if self._state is not RuntimeState.CLOSED:
                self._state = RuntimeState.STOPPED

    def close(self) -> None:
        with self._lock:
            self._state = RuntimeState.CLOSED
            self._hosts.clear()

    def status(self) -> dict[str, object]:
        with self._lock:
            tasks, sessions, deliveries = self.store.counts()
            return {
                "state": self._state.value,
                "tasks": tasks,
                "sessions": sessions,
                "deliveries": deliveries,
                "registered_hosts": len(self._hosts),
                "actual_host_support": "unverified",
                "read": "unknown",
                "applied": "unknown",
            }

    def _running(self) -> None:
        if self._state is not RuntimeState.RUNNING:
            raise ServiceError("service_not_running")

    def _permission(self, request: AuthorizationRequest) -> Permission:
        try:
            result = self._authorize(request)
        except Exception:
            return Permission.UNKNOWN
        return result if isinstance(result, Permission) else Permission.UNKNOWN

    def _task_state(
        self, task: ServiceTask, state: TaskState, error: str | None = None
    ) -> ServiceTask:
        updated = replace(task, state=state, revision=task.revision + 1, error_code=error)
        self.store.save_task(updated, task.revision)
        return updated

    def submit(
        self,
        *,
        task_id: str,
        project_ref: str,
        intake_ref: str,
        host_ref: str,
        authority_ref: str,
        payload: TransientPayload,
    ) -> ServiceTask:
        for reference in (task_id, project_ref, intake_ref, host_ref, authority_ref):
            _reference(reference)
        if not isinstance(payload, TransientPayload):
            raise ServiceError("invalid_transient_payload")
        with self._lock:
            self._running()
            try:
                return self._submit(task_id, project_ref, intake_ref, host_ref, authority_ref, payload)
            except ServiceError:
                raise
            except Exception:
                raise ServiceError("operation_state_unknown") from None

    def _submit(
        self,
        task_id: str,
        project_ref: str,
        intake_ref: str,
        host_ref: str,
        authority_ref: str,
        payload: TransientPayload,
    ) -> ServiceTask:
        task = ServiceTask(task_id, project_ref, intake_ref, host_ref, authority_ref)
        self.store.save_task(task, None)
        request = AuthorizationRequest(Action.CREATE_SESSION, task, intake_ref, None, authority_ref)
        if self._permission(request) is not Permission.ALLOW:
            return self._task_state(task, TaskState.WAITING_AUTHORITY, "authority_unconfirmed")
        host = self._hosts.get(host_ref)
        if host is None:
            return self._task_state(task, TaskState.UNAVAILABLE, "host_unavailable")
        creation = self._create(host, task_id)
        if creation.outcome != "created" or creation.session_ref is None:
            state = TaskState.EFFECT_UNKNOWN if creation.outcome == "unknown" else TaskState.UNAVAILABLE
            return self._task_state(task, state, "session_creation_unconfirmed")
        return self._created_task(task, host, creation.session_ref, payload)

    @staticmethod
    def _create(host: ServiceHost, task_id: str) -> SessionCreation:
        try:
            result = host.create_session(task_id)
            if not isinstance(result, SessionCreation):
                return SessionCreation(outcome="unknown")
            if result.session_ref is not None:
                _reference(result.session_ref)
            return result
        except Exception:
            return SessionCreation(outcome="unknown")

    def _created_task(
        self, task: ServiceTask, host: ServiceHost, session_ref: str, payload: TransientPayload
    ) -> ServiceTask:
        session = ServiceSession(session_ref, task.task_id, task.host_ref, task.project_ref)
        try:
            self.store.save_session(session)
            updated = replace(
                task,
                execution_ref=session_ref,
                state=TaskState.SESSION_CREATED,
                revision=task.revision + 1,
            )
            self.store.save_task(updated, task.revision)
        except ServiceError:
            return self._task_state(task, TaskState.EFFECT_UNKNOWN, "created_session_state_unknown")
        request = AuthorizationRequest(Action.DELIVER, updated, task.intake_ref, session, task.authority_ref)
        if self._permission(request) is not Permission.ALLOW:
            return self._task_state(updated, TaskState.WAITING_AUTHORITY, "recipient_unconfirmed")
        delivery = self._deliver(host, updated, task.intake_ref, session, uuid4().hex, payload)
        state = self._state_after_delivery(delivery.state)
        return self._task_state(updated, state)

    @staticmethod
    def _state_after_delivery(state: DeliveryState) -> TaskState:
        if state is DeliveryState.DELIVERED:
            return TaskState.DELIVERY_REPORTED
        if state is DeliveryState.SENT_UNCONFIRMED:
            return TaskState.DELIVERY_UNCONFIRMED
        if state is DeliveryState.REFUSED:
            return TaskState.UNAVAILABLE
        return TaskState.EFFECT_UNKNOWN

    def _deliver(
        self,
        host: ServiceHost,
        task: ServiceTask,
        sender_ref: str,
        destination: ServiceSession,
        request_id: str,
        payload: TransientPayload,
    ) -> ServiceDelivery:
        initial = ServiceDelivery(
            request_id, task.task_id, sender_ref, destination.session_ref, DeliveryState.ATTEMPTED
        )
        self.store.save_delivery(initial, None)
        try:
            outcome = host.deliver(destination, request_id, payload)
            if not isinstance(outcome, DeliveryState) or outcome is DeliveryState.ATTEMPTED:
                outcome = DeliveryState.EFFECT_UNKNOWN
        except Exception:
            outcome = DeliveryState.EFFECT_UNKNOWN
        final = replace(initial, state=outcome, revision=1)
        self.store.save_delivery(final, initial.revision)
        return final

    def relay(
        self,
        *,
        task_id: str,
        sender_ref: str,
        destination_ref: str,
        authority_ref: str,
        request_id: str,
        payload: TransientPayload,
    ) -> ServiceDelivery:
        """Relay once per request identity; existing identities are never resent.

        A conflict is surfaced even when the route matches, because retaining no
        body means this service cannot establish that a retry's content is equal.
        Inspect the existing delivery, particularly an unknown external effect.
        """
        for reference in (task_id, sender_ref, destination_ref, authority_ref, request_id):
            _reference(reference)
        if not isinstance(payload, TransientPayload):
            raise ServiceError("invalid_transient_payload")
        with self._lock:
            self._running()
            try:
                return self._relay(
                    task_id, sender_ref, destination_ref, authority_ref, request_id, payload
                )
            except ServiceError:
                raise
            except Exception:
                raise ServiceError("operation_state_unknown") from None

    def _relay(
        self,
        task_id: str,
        sender_ref: str,
        destination_ref: str,
        authority_ref: str,
        request_id: str,
        payload: TransientPayload,
    ) -> ServiceDelivery:
        if self.store.delivery(request_id) is not None:
            raise ServiceError("request_identity_already_attempted")
        task = self.store.task(task_id)
        sender = self.store.session(sender_ref)
        destination = self.store.session(destination_ref)
        if task is None or sender is None or destination is None:
            raise ServiceError("unknown_task_or_session")
        request = AuthorizationRequest(Action.DELIVER, task, sender_ref, destination, authority_ref)
        if self._permission(request) is not Permission.ALLOW:
            raise ServiceError("recipient_or_authority_unconfirmed")
        host = self._hosts.get(destination.host_ref)
        if host is None:
            raise ServiceError("host_unavailable")
        return self._deliver(host, task, sender_ref, destination, request_id, payload)
