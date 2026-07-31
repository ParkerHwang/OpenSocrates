"""Content-free Codex event projections.

The native parser is the only place that sees a Codex callback envelope.  This
module turns its short-lived facts into the closed ``NormalizedEvent`` union.
Identifiers are replaced with process-keyed tags and native prompt/tool
content is deliberately not represented in the result.
"""

from __future__ import annotations

from typing import Any

from ...clock import Clock, utc_timestamp
from ...domain.enums import EventType, ToolCategory
from ...domain.models import NormalizedEvent
from ...ids import new_event_id
from ...version import PRODUCT_VERSION
from ..common import derive_session_tag, derive_tool_tag, derive_turn_tag
from .native import CodexNativeEvent

# Codex's documented tool names are intentionally mapped explicitly.  In
# particular, do not turn an arbitrary future tool label into an observation
# claim by using fuzzy name matching.
_TOOL_CATEGORIES: dict[str, ToolCategory] = {
    "Bash": ToolCategory.EXECUTION,
    "apply_patch": ToolCategory.WRITE,
}


def tool_category(tool_name: str | None) -> ToolCategory:
    """Map only the captured Codex tool labels to a closed category."""

    if not isinstance(tool_name, str):
        return ToolCategory.OTHER
    if tool_name in _TOOL_CATEGORIES:
        return _TOOL_CATEGORIES[tool_name]
    # MCP tool names are an allowlisted shape, but their operation semantics
    # are not available at this boundary.  Keep them observable as ``other``.
    if tool_name.startswith("mcp__") and len(tool_name) <= 256:
        return ToolCategory.OTHER
    return ToolCategory.OTHER


def result_size_bucket(size: int | None) -> str:
    """Return a bounded result-size category without retaining output."""

    if size is None:
        return "unknown"
    if size <= 0:
        return "0"
    if size < 1024:
        return "1_1023"
    if size < 4 * 1024:
        return "1_4k"
    if size < 64 * 1024:
        return "4k_64k"
    if size < 256 * 1024:
        return "64k_256k"
    return "256k_plus"


def _tool_payload(native: CodexNativeEvent, *, session_tag: str) -> dict[str, Any]:
    failed = native.failure_class is not None
    payload: dict[str, Any] = {
        "tool_category": tool_category(native.tool_name).value,
        "tool_use_key": derive_tool_tag(
            native.tool_use_id,
            session_tag=session_tag,
        ),
        "result_present": native.result_present,
        "result_size_bucket": result_size_bucket(native.result_size),
        "status": "failed" if failed else "succeeded",
    }
    if failed:
        payload["failure_class"] = native.failure_class or "unknown"
    return payload


def _event_projection(
    native: CodexNativeEvent, *, session_tag: str
) -> tuple[EventType | None, dict[str, Any]]:
    """Return the domain event type and safe payload for one native event."""

    if native.native_event == "SessionStart":
        return EventType.SESSION_STARTED, {
            "native_source": native.source or "unknown",
            "version": native.native_version or "unknown",
        }
    if native.native_event == "UserPromptSubmit":
        # Prompt contents are intentionally not used to infer direct skill
        # invocation.  A separate exact activation receipt is required.
        return EventType.USER_PROMPT_SUBMITTED, {"is_direct_skill_invocation": False}
    if native.native_event == "PostToolUse":
        return (
            EventType.TOOL_FAILED if native.failure_class is not None else EventType.TOOL_SUCCEEDED,
            _tool_payload(native, session_tag=session_tag),
        )
    if native.native_event == "Stop":
        return EventType.COMPLETION_CANDIDATE, {
            "stop_already_continued": native.stop_hook_active,
            "native_stop_reason": "missing-final-message" if native.final_message is None else None,
            "final_message_present": native.final_message is not None,
        }
    if native.native_event == "PreCompact":
        return EventType.PRE_COMPACTION, {
            "trigger": native.trigger or "unknown",
            "active_task": False,
        }
    if native.native_event == "PostCompact":
        return EventType.POST_COMPACTION, {
            "trigger": native.trigger or "unknown",
            "active_task": False,
        }
    if native.native_event == "SessionEnd":
        return EventType.SESSION_ENDED, {"reason": native.reason or "other"}
    # PreToolUse and PermissionRequest are parsed only to prove the callback
    # shape.  They cannot carry a reasoning intervention or product state.
    return None, {}


def project_codex_payload(native: CodexNativeEvent) -> dict[str, Any]:
    """Return the safe fixture-facing projection, without native identifiers."""

    if native.native_event == "PreToolUse":
        return {"reasoning_intervention": False}
    if native.native_event == "PermissionRequest":
        return {"tool_category": tool_category(native.tool_name).value}
    session_tag = derive_session_tag(native.session_id)
    _event_type, payload = _event_projection(native, session_tag=session_tag)
    return dict(payload)


def normalize_codex_event(
    native: CodexNativeEvent,
    *,
    installation_key: bytes | None = None,
    clock: Clock | None = None,
    adapter_version: str = PRODUCT_VERSION,
) -> NormalizedEvent | None:
    """Project one parsed Codex callback into the closed event model.

    ``None`` is the deliberate no-op projection for PreToolUse and
    PermissionRequest.  Unsupported native events never reach this function.
    """

    if not isinstance(native, CodexNativeEvent):
        raise TypeError("normalize_codex_event requires CodexNativeEvent")
    session_tag = derive_session_tag(native.session_id, installation_key)
    event_type, payload = _event_projection(native, session_tag=session_tag)
    if event_type is None:
        return None
    return NormalizedEvent(
        event_id=new_event_id(clock),
        event_type=event_type,
        occurred_at=utc_timestamp(clock),
        host=native.host,
        host_version=native.native_version or "unknown",
        adapter_version=adapter_version,
        host_session_key=session_tag,
        host_turn_key=derive_turn_tag(native.turn_id, installation_key),
        cwd_hint=None,
        payload=payload,
    )


normalize_event = normalize_codex_event
project_event = normalize_codex_event


__all__ = [
    "normalize_codex_event",
    "normalize_event",
    "project_codex_payload",
    "project_event",
    "result_size_bucket",
    "tool_category",
]
