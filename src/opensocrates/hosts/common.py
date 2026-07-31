"""Small host-neutral action and injection protocols.

This module intentionally contains no native JSON.  Adapters project their
native input into :class:`NormalizedEvent`, call these explicit application
ports, and then turn the returned :class:`HostAction` back into a legal host
response.  Raw prompts, transcripts, tool input/output, and local paths have
no type or storage path here.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from ..domain.enums import HostActionKind
from ..domain.models import CapabilityProfile, HostControlResult, NormalizedEvent

_PROCESS_KEY = secrets.token_bytes(32)
_MAX_ACTION_TEXT = 8 * 1024


class HostActionError(ValueError):
    """Raised when an action is not legal at the host boundary."""


def _bounded_text(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise HostActionError(f"{name} must be non-empty text or null")
    if len(value.encode("utf-8")) > _MAX_ACTION_TEXT:
        raise HostActionError(f"{name} exceeds the host context limit")
    if "\x00" in value or unicodedata.normalize("NFC", value) != value:
        raise HostActionError(f"{name} is not canonical Unicode text")
    if any(ord(char) < 0x20 and char not in "\n\t" for char in value):
        raise HostActionError(f"{name} contains a control character")
    return value


@dataclass(frozen=True, slots=True)
class HostAction:
    """Closed adapter result before native response serialization.

    ``reason`` is a stable, content-free code.  User-facing text belongs in a
    localized context/status field supplied by the shared application/content
    service, never in a diagnostic assembled from native input.
    """

    kind: HostActionKind = HostActionKind.NO_OP
    additional_context: str | None = None
    reason: str | None = None
    system_message: str | None = None
    status_message: str | None = None
    suppress_output: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, HostActionKind):
            raise HostActionError("action kind is not closed")
        if not isinstance(self.suppress_output, bool):
            raise HostActionError("suppress_output must be boolean")
        for name in ("additional_context", "reason", "system_message", "status_message"):
            _bounded_text(getattr(self, name), name)
        if self.kind is HostActionKind.NO_OP and self.additional_context is not None:
            raise HostActionError("no_op cannot carry additional context")
        if self.kind in {HostActionKind.ADD_CONTEXT, HostActionKind.CONTINUE_TURN}:
            if self.additional_context is None:
                raise HostActionError(f"{self.kind.value} requires additional context")
        if self.kind is HostActionKind.BLOCK_PROMPT and self.reason is None:
            raise HostActionError("block_prompt requires a stable reason")

    @classmethod
    def no_op(cls) -> "HostAction":
        """Return the safe, nonblocking action."""

        return cls()

    @classmethod
    def add_context(cls, context: str, *, status_message: str | None = None) -> "HostAction":
        """Inject nonblocking context into a supported native event."""

        return cls(
            kind=HostActionKind.ADD_CONTEXT,
            additional_context=context,
            status_message=status_message,
        )

    @classmethod
    def continue_turn(cls, context: str, *, reason: str = "completion_repair") -> "HostAction":
        """Request one bounded continuation at a supported completion hook."""

        return cls(
            kind=HostActionKind.CONTINUE_TURN,
            additional_context=context,
            reason=reason,
        )

    @classmethod
    def block_prompt(cls, reason: str, *, message: str | None = None) -> "HostAction":
        """Block only a malformed explicit control invocation."""

        return cls(kind=HostActionKind.BLOCK_PROMPT, reason=reason, system_message=message)

    @classmethod
    def warn_user(cls, message: str, *, reason: str = "capability_degraded") -> "HostAction":
        """Surface a bounded, actionable user-safe warning."""

        return cls(kind=HostActionKind.WARN_USER, reason=reason, status_message=message)


@dataclass(frozen=True, slots=True)
class StopDecision:
    """Host-neutral result from the shared completion/Stop application service."""

    action: HostAction = field(default_factory=HostAction.no_op)
    repair_count_before: int = 0
    repair_count_after: int = 0
    capability_limitations: tuple[str, ...] = ()
    persisted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.action, HostAction):
            raise HostActionError("stop decision requires HostAction")
        if self.repair_count_before not in (0, 1) or self.repair_count_after not in (0, 1):
            raise HostActionError("Stop repair count must be 0 or 1")
        if self.repair_count_after < self.repair_count_before:
            raise HostActionError("Stop repair count cannot decrease")
        if len(self.capability_limitations) > 8 or any(
            not isinstance(item, str) or not item for item in self.capability_limitations
        ):
            raise HostActionError("Stop capability limitations are not bounded")
        if self.action.kind is HostActionKind.CONTINUE_TURN and self.repair_count_before != 0:
            raise HostActionError("a second Stop continuation is not legal")


class ControlApplicationPort(Protocol):
    """S14 control seam; native serialization remains in the adapter."""

    def apply(self, request: Any) -> HostControlResult: ...


class StopDecisionPort(Protocol):
    """S18 Stop seam; exactly one decision is delegated to this port."""

    def decide(
        self,
        event: NormalizedEvent,
        public_message: str | None,
        *,
        repair_count_before: int,
        stop_hook_active: bool,
        capability_profile: CapabilityProfile | None,
    ) -> StopDecision: ...


class EventApplicationPort(Protocol):
    """Optional application callbacks for lifecycle events."""

    def handle(self, event: NormalizedEvent) -> HostAction: ...


def _tag(key: bytes | None, domain: str, values: Sequence[str]) -> str:
    secret = _PROCESS_KEY if key is None else key
    if not isinstance(secret, bytes) or len(secret) != 32:
        raise HostActionError("installation key must be exactly 256 bits")
    pieces = [domain.encode("utf-8")]
    for value in values:
        if not isinstance(value, str):
            raise HostActionError("HMAC inputs must be text")
        encoded = value.encode("utf-8")
        pieces.extend((len(encoded).to_bytes(4, "big"), encoded))
    return (
        "sha256:"
        + hmac.new(
            secret, b"opensocrates-host-tag\0" + b"".join(pieces), hashlib.sha256
        ).hexdigest()
    )


def derive_session_tag(session_id: str | None, installation_key: bytes | None = None) -> str:
    """Hash a native session identifier without exposing it to the domain."""

    return _tag(installation_key, "session", (session_id or "unknown-session",))


def derive_turn_tag(turn_id: str | None, installation_key: bytes | None = None) -> str | None:
    """Hash a native turn identifier, returning null when it is unavailable."""

    if turn_id is None:
        return None
    return _tag(installation_key, "turn", (turn_id,))


def derive_tool_tag(
    tool_use_id: str | None,
    installation_key: bytes | None = None,
    *,
    session_tag: str | None = None,
) -> str:
    """Hash a native tool identifier for bounded dedupe."""

    return _tag(
        installation_key, "tool", (session_tag or "unknown-session", tool_use_id or "unknown-tool")
    )


__all__ = [
    "ControlApplicationPort",
    "EventApplicationPort",
    "HostAction",
    "HostActionError",
    "StopDecision",
    "StopDecisionPort",
    "derive_session_tag",
    "derive_tool_tag",
    "derive_turn_tag",
]
