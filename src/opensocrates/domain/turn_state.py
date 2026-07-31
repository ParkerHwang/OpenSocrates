"""Pure invariants for the ephemeral cross-process turn protocol.

The persistence implementation owns files, locks, and permissions.  This
module owns only the closed state object, domain-separated HMAC tags, replay
capacity, and the six-hour lifetime rule.  In particular, no helper here ever
accepts a prompt, card, tool result, or other prose field.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Final

from ..constants import MAX_CONTROL_ACCEPTED_CONTROLS, MAX_OBSERVATION_TAGS
from ..errors import ValidationError
from ..ids import validate_sha256, validate_timestamp, validate_turn_token
from .enums import TaskState
from .models import AcceptedControl, EphemeralTurnState, HostControlResult
from .validation import canonical_json, validate_model

UTC = timezone.utc
MAX_TURN_AGE: Final[timedelta] = timedelta(hours=6)
MAX_TURN_AGE_SECONDS: Final[int] = int(MAX_TURN_AGE.total_seconds())
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
_HEX_TAG_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class TurnStateError(ValidationError):
    """Base error for an invalid pure turn-state operation."""


class TurnStateExpired(TurnStateError):
    """The state is at or beyond its bounded expiry timestamp."""


class ReplayCapacityError(TurnStateError):
    """A bounded replay/deduplication collection has no remaining capacity."""


def _require_key(installation_key: bytes) -> bytes:
    if not isinstance(installation_key, bytes) or len(installation_key) != 32:
        raise TurnStateError("installation key must be exactly 256 bits")
    return installation_key


def _require_tag(tag: str, name: str) -> str:
    if not isinstance(tag, str) or _HEX_TAG_RE.fullmatch(tag) is None:
        raise TurnStateError(f"{name} must be a sha256 tag")
    # Keep the scalar validator as the final closed-shape check.  It also
    # protects callers that pass a str subclass with surprising behaviour.
    try:
        validate_sha256(tag)
    except Exception as exc:  # pragma: no cover - validator supplies detail
        raise TurnStateError(f"{name} must be a sha256 tag") from exc
    return tag


def _timestamp(value: str, name: str) -> datetime:
    try:
        validate_timestamp(value)
        return datetime.strptime(value, _TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except (TypeError, ValueError) as exc:
        raise TurnStateError(f"{name} must be a canonical UTC timestamp") from exc


def _format_timestamp(value: datetime) -> str:
    value = value.astimezone(UTC)
    # The contract is millisecond precision, never a variable-width value.
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"


def token_tag_for(raw_token: str, installation_key: bytes) -> str:
    """Derive the opaque token basename used by ``TurnStateStore``.

    The length prefix is part of the domain separation and mirrors the secure
    persistence implementation.  The raw token is never part of an
    ``EphemeralTurnState`` value.
    """

    try:
        validate_turn_token(raw_token)
    except Exception as exc:  # pragma: no cover - validator supplies detail
        raise TurnStateError("turn token is invalid") from exc
    key = _require_key(installation_key)
    message = b"turn-token\0" + len(raw_token).to_bytes(4, "big") + raw_token.encode("ascii")
    return "sha256:" + hmac.new(key, message, hashlib.sha256).hexdigest()


def payload_tag_for(payload: Mapping[str, object], installation_key: bytes) -> str:
    """Return a domain-separated tag for one canonical control payload."""

    if not isinstance(payload, Mapping):
        raise TurnStateError("control payload must be an object")
    key = _require_key(installation_key)
    try:
        encoded = canonical_json(payload).encode("utf-8")
    except Exception as exc:  # pragma: no cover - canonical adapter detail
        raise TurnStateError("control payload is not canonical JSON") from exc
    digest = hmac.new(key, b"control-payload\0" + encoded, hashlib.sha256).hexdigest()
    return "sha256:" + digest


def observation_tag_for(
    stable_observation_key: str,
    installation_key: bytes,
    *,
    category: str = "observation",
) -> str:
    """Tag a stable, already-normalized observation identity.

    Callers must pass a category and stable host-provided identifier; this
    helper intentionally has no parameter for raw tool input or output.
    """

    if not isinstance(stable_observation_key, str) or not stable_observation_key:
        raise TurnStateError("observation key must be non-empty text")
    if not isinstance(category, str) or not category:
        raise TurnStateError("observation category must be non-empty text")
    key = _require_key(installation_key)
    material = category.encode("utf-8") + b"\0" + stable_observation_key.encode("utf-8")
    digest = hmac.new(key, b"observation\0" + material, hashlib.sha256).hexdigest()
    return "sha256:" + digest


def expiry_for(issued_at: str, *, max_age: timedelta = MAX_TURN_AGE) -> str:
    """Compute a bounded expiry timestamp, rejecting lifetimes over six hours."""

    if not isinstance(max_age, timedelta) or max_age <= timedelta(0) or max_age > MAX_TURN_AGE:
        raise TurnStateError("turn lifetime must be positive and at most six hours")
    issued = _timestamp(issued_at, "issued_at")
    return _format_timestamp(issued + max_age)


def validate_lifetime(state: EphemeralTurnState) -> EphemeralTurnState:
    """Validate the timestamp ordering and six-hour upper bound."""

    if not isinstance(state, EphemeralTurnState):
        raise TurnStateError("expected EphemeralTurnState")
    issued = _timestamp(state.issued_at, "issued_at")
    expires = _timestamp(state.expires_at, "expires_at")
    if expires <= issued:
        raise TurnStateError("turn state must expire after issuance")
    if expires - issued > MAX_TURN_AGE:
        raise TurnStateError("turn state lifetime exceeds six hours")
    return state


def validate_turn_state(state: EphemeralTurnState) -> EphemeralTurnState:
    """Validate a complete state object without touching persistence."""

    if not isinstance(state, EphemeralTurnState):
        raise TurnStateError("expected EphemeralTurnState")
    validate_lifetime(state)
    _require_tag(state.token_tag, "token_tag")
    _require_tag(state.host_session_key, "host_session_key")
    if state.host_turn_key is not None:
        _require_tag(state.host_turn_key, "host_turn_key")
    if len(state.accepted_controls) > MAX_CONTROL_ACCEPTED_CONTROLS:
        raise ReplayCapacityError("accepted-control capacity is exhausted")
    if len(state.observation_tags) > MAX_OBSERVATION_TAGS:
        raise ReplayCapacityError("observation-tag capacity is exhausted")
    if len(set(state.observation_tags)) != len(state.observation_tags):
        raise TurnStateError("observation tags must be unique")
    for accepted in state.accepted_controls:
        if not isinstance(accepted, AcceptedControl):
            raise TurnStateError("accepted_controls must contain AcceptedControl values")
        _require_tag(accepted.payload_tag, "payload_tag")
        if not isinstance(accepted.result, HostControlResult):
            raise TurnStateError("accepted control result must be HostControlResult")
    try:
        validate_model(state)
    except Exception as exc:
        raise TurnStateError("ephemeral turn state violates its closed model") from exc
    return state


def is_expired(state: EphemeralTurnState, now: str) -> bool:
    """Return whether ``now`` is at or after ``expires_at``."""

    validate_lifetime(state)
    return _timestamp(now, "now") >= _timestamp(state.expires_at, "expires_at")


def require_active(state: EphemeralTurnState, now: str) -> EphemeralTurnState:
    """Validate and return a live state, raising ``TurnStateExpired`` otherwise."""

    validate_turn_state(state)
    if is_expired(state, now):
        raise TurnStateExpired("turn state has expired")
    return state


def accepted_control_for(
    state: EphemeralTurnState,
    message_id: str,
) -> AcceptedControl | None:
    """Find a prior control by its opaque idempotency key."""

    validate_turn_state(state)
    return next((item for item in state.accepted_controls if item.message_id == message_id), None)


def append_accepted_control(
    state: EphemeralTurnState,
    accepted: AcceptedControl,
) -> EphemeralTurnState:
    """Return a state with one new replay entry, enforcing the hard cap."""

    validate_turn_state(state)
    if not isinstance(accepted, AcceptedControl):
        raise TurnStateError("accepted value must be AcceptedControl")
    if accepted_control_for(state, accepted.message_id) is not None:
        raise TurnStateError("message_id is already present in accepted controls")
    if len(state.accepted_controls) >= MAX_CONTROL_ACCEPTED_CONTROLS:
        raise ReplayCapacityError("accepted-control capacity is exhausted")
    replacement = replace(state, accepted_controls=(*state.accepted_controls, accepted))
    return validate_turn_state(replacement)


def append_observation_tag(state: EphemeralTurnState, tag: str) -> EphemeralTurnState:
    """Return a state with one bounded observation tag.

    Repeating an existing tag is idempotent and returns the same state.  A
    fresh tag beyond capacity raises ``ReplayCapacityError`` so callers can
    degrade/suppress the intervention without mutating the state.
    """

    validate_turn_state(state)
    _require_tag(tag, "observation tag")
    if tag in state.observation_tags:
        return state
    if len(state.observation_tags) >= MAX_OBSERVATION_TAGS:
        raise ReplayCapacityError("observation-tag capacity is exhausted")
    replacement = replace(state, observation_tags=(*state.observation_tags, tag))
    return validate_turn_state(replacement)


def replace_lifecycle(state: EphemeralTurnState, **changes: object) -> EphemeralTurnState:
    """Apply a closed in-memory state update and revalidate all invariants."""

    validate_turn_state(state)
    replacement = replace(state, **changes)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    return validate_turn_state(replacement)


def is_terminal_task_state(state: TaskState) -> bool:
    """Return whether a task-state value is terminal for control purposes."""

    if not isinstance(state, TaskState):
        raise TurnStateError("task state must be closed")
    return state in {
        TaskState.BYPASSED,
        TaskState.CONCLUDED,
        TaskState.CANCELLED,
        TaskState.INSUFFICIENT,
    }


__all__ = [
    "MAX_TURN_AGE",
    "MAX_TURN_AGE_SECONDS",
    "ReplayCapacityError",
    "TurnStateError",
    "TurnStateExpired",
    "accepted_control_for",
    "append_accepted_control",
    "append_observation_tag",
    "expiry_for",
    "is_expired",
    "is_terminal_task_state",
    "observation_tag_for",
    "payload_tag_for",
    "replace_lifecycle",
    "require_active",
    "token_tag_for",
    "validate_lifetime",
    "validate_turn_state",
]
