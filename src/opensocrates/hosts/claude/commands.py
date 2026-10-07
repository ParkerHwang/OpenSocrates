"""Fixed macOS Claude command hooks; no prompt or shell interpolation."""

from __future__ import annotations

from typing import Any

from .events import NATIVE_TO_NORMALIZED

CLAUDE_NATIVE_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")


def hook_command(native_event: str) -> dict[str, Any]:
    if native_event not in CLAUDE_NATIVE_EVENTS:
        raise ValueError("unsupported Claude hook event")
    return {
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/bin/launch.sh",
        "args": ["hook", "claude", NATIVE_TO_NORMALIZED[native_event]],
        "timeout": 1 if native_event in {"Stop", "SessionEnd"} else 3,
    }


def build_hooks() -> dict[str, Any]:
    """Zero-argument builder used by the generic package generator."""

    hooks: dict[str, list[dict[str, Any]]] = {}
    for native_event in CLAUDE_NATIVE_EVENTS:
        entry: dict[str, Any] = {"hooks": [hook_command(native_event)]}
        if native_event == "SessionStart":
            entry["matcher"] = "startup|resume|clear|compact|fork"
        hooks[native_event] = [entry]
    return {"hooks": hooks}
