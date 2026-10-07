"""Exact legal Claude entry envelopes, distinct from Codex responses."""

from __future__ import annotations

import json
from typing import Any

from .events import ENTRY_EVENTS

MAX_CONTEXT_BYTES = 16384


def entry_response(context: str, event_name: str) -> dict[str, Any] | None:
    if event_name not in ENTRY_EVENTS or not context.strip():
        return None
    if len(context.encode("utf-8")) > MAX_CONTEXT_BYTES:
        return None
    if any(ord(character) < 32 and character not in "\n\t" for character in context):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        }
    }


def serialize_response(response: dict[str, Any]) -> str:
    return json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
