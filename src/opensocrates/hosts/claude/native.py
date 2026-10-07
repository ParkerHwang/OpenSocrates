"""Bounded Claude JSON normalization without retaining private host fields."""

from __future__ import annotations

import json
from typing import Any

from .events import NATIVE_TO_NORMALIZED, ClaudeEvent

MAX_PAYLOAD_CHARS = 65536
MAX_PAYLOAD_BYTES = 262144
_START_SOURCES = frozenset({"startup", "resume", "clear", "compact", "fork"})


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate native field")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("non-JSON numeric constant")


def _optional_text(payload: dict[str, Any], key: str, limit: int) -> bool:
    if key not in payload:
        return True
    value = payload[key]
    return isinstance(value, str) and 0 < len(value) <= limit and "\x00" not in value


def parse_claude_event(raw: str) -> ClaudeEvent | None:
    """Accept new host fields as transient data, returning no private values."""

    try:
        if not isinstance(raw, str) or len(raw) > MAX_PAYLOAD_CHARS:
            return None
        if len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            return None
        payload = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
        if not isinstance(payload, dict):
            return None
        name = payload.get("hook_event_name")
        if not isinstance(name, str) or name not in NATIVE_TO_NORMALIZED:
            return None
        if not _optional_text(payload, "session_id", 1024):
            return None
        if not _optional_text(payload, "prompt_id", 1024):
            return None
        return _event(payload, name)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return None


def _event(payload: dict[str, Any], name: str) -> ClaudeEvent | None:
    source: str | None = None
    if name == "SessionStart":
        value = payload.get("source")
        if not isinstance(value, str) or value not in _START_SOURCES:
            return None
        source = value
    if name == "UserPromptSubmit" and not isinstance(payload.get("prompt"), str):
        return None
    if name == "Stop" and "stop_hook_active" in payload:
        if not isinstance(payload["stop_hook_active"], bool):
            return None
    return ClaudeEvent(name, NATIVE_TO_NORMALIZED[name], source)
