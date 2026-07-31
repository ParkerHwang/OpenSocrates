"""Legal, deterministic Codex command-hook responses."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from typing import Any

from ...content.injection import MAX_INJECTION_ESTIMATED_TOKENS, estimate_injection_tokens
from ...domain.enums import HostActionKind
from ..common import HostAction


class NativeResponseError(ValueError):
    """Raised when an action is not legal for a Codex callback."""


KNOWN_EVENTS = frozenset(
    {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "PermissionRequest",
        "PreCompact",
        "PostCompact",
        "Stop",
        "SessionEnd",
    }
)

# PermissionRequest is parsed defensively but is not configured by the v1
# command hook package.  Keeping it outside this set prevents accidental
# claims that a permission decision is supported.
CONTEXT_EVENTS = frozenset(
    {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
    }
)

SELECTOR_CONTEXT_EVENTS = frozenset({"SessionStart", "UserPromptSubmit"})


def _event_name(value: str) -> str:
    if not isinstance(value, str) or value not in KNOWN_EVENTS:
        raise NativeResponseError("unknown Codex native event")
    return value


def response_object(action: HostAction, event_name: str) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Return a host-legal object for one Codex hook event.

    Codex Stop is intentionally special: the only continuation response is
    the documented JSON ``decision: block`` form. ``hookSpecificOutput`` is
    never emitted for Stop.
    """

    native_name = _event_name(event_name)
    if not isinstance(action, HostAction):
        raise NativeResponseError("response requires a HostAction")
    if action.kind is HostActionKind.NO_OP:
        return {}
    if native_name == "Stop":
        if action.kind is HostActionKind.CONTINUE_TURN:
            reason = action.additional_context or action.reason
            if not reason:
                raise NativeResponseError("Stop continuation requires a reason")
            return {"decision": "block", "reason": reason}
        if action.kind in {
            HostActionKind.ADD_CONTEXT,
            HostActionKind.BLOCK_PROMPT,
            HostActionKind.WARN_USER,
        }:
            raise NativeResponseError(f"{action.kind.value} is not legal for Codex Stop")
    if action.kind in {HostActionKind.ADD_CONTEXT, HostActionKind.CONTINUE_TURN}:
        if native_name not in CONTEXT_EVENTS:
            raise NativeResponseError(f"additionalContext is not legal for {native_name}")
        if action.additional_context is None:
            raise NativeResponseError("additionalContext requires text")
        specific: dict[str, Any] = {
            "hookEventName": native_name,
            "additionalContext": action.additional_context,
        }
        result: dict[str, Any] = {"hookSpecificOutput": specific}
        # Codex currently parses suppressOutput only on selected events and
        # the adapter has no need to request it.  Do not invent it here.
        return result
    if action.kind is HostActionKind.WARN_USER:
        if native_name not in CONTEXT_EVENTS:
            raise NativeResponseError(f"systemMessage is not legal for {native_name}")
        message = action.status_message or action.system_message
        if message is None:
            raise NativeResponseError("warn_user requires a message")
        return {"systemMessage": message}
    # Codex has no v1 reasoning-denial response in this adapter.  A product
    # control rejection is handled by the shared application port instead.
    if action.kind is HostActionKind.BLOCK_PROMPT:
        raise NativeResponseError("Codex command hooks do not block reasoning prompts")
    raise NativeResponseError("unsupported HostAction kind")


def selector_context_response(instructions: str, event_name: str) -> dict[str, Any]:
    """Return the approved OpenSocrates selector context response.

    The selector content is a validated, compact reference to an owner-only
    temporary instruction file. This boundary repeats output-shape, Unicode,
    and hook-message size checks.
    """

    native_name = _event_name(event_name)
    if native_name not in SELECTOR_CONTEXT_EVENTS:
        raise NativeResponseError("selector additionalContext is not legal for this event")
    if not isinstance(instructions, str) or not instructions.strip() or "\x00" in instructions:
        raise NativeResponseError("selector additionalContext must be non-empty text")
    if unicodedata.normalize("NFC", instructions) != instructions:
        raise NativeResponseError("selector additionalContext is not canonical Unicode")
    if any(ord(character) < 0x20 and character not in "\n\t" for character in instructions):
        raise NativeResponseError("selector additionalContext contains a control character")
    if estimate_injection_tokens(instructions) >= MAX_INJECTION_ESTIMATED_TOKENS:
        raise NativeResponseError("selector additionalContext exceeds the Codex limit")
    return {
        "hookSpecificOutput": {
            "hookEventName": native_name,
            "additionalContext": instructions,
        }
    }


def serialize_response_object(response: Mapping[str, Any]) -> str:
    """Serialize one adapter-owned native response object canonically."""

    if not isinstance(response, Mapping):
        raise NativeResponseError("native response must be an object")
    return json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def serialize_codex_response(action: HostAction, event_name: str) -> str:
    """Serialize a legal Codex response as canonical JSON plus one LF."""

    return serialize_response_object(response_object(action, event_name))


def response_bytes(action: HostAction, event_name: str) -> bytes:
    return serialize_codex_response(action, event_name).encode("utf-8")


def pass_through_response(event_name: str) -> str:
    return serialize_codex_response(HostAction.no_op(), event_name)


to_native_response = serialize_codex_response


__all__ = [
    "CONTEXT_EVENTS",
    "KNOWN_EVENTS",
    "NativeResponseError",
    "pass_through_response",
    "response_bytes",
    "response_object",
    "selector_context_response",
    "serialize_codex_response",
    "serialize_response_object",
    "to_native_response",
]
