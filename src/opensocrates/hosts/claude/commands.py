"""Fixed Claude Code/Cowork hook commands."""

from __future__ import annotations

from typing import Any

NATIVE_TO_NORMALIZED = {
    "SessionStart": "session_started",
    "UserPromptSubmit": "user_prompt_submitted",
    "Stop": "completion_candidate",
    "SessionEnd": "session_ended",
}

CLAUDE_NATIVE_EVENTS = tuple(NATIVE_TO_NORMALIZED)

_MATCHERS = {
    "SessionStart": "startup|resume|clear|compact|fork",
    "UserPromptSubmit": "",
    "Stop": "",
    "SessionEnd": "clear|resume|logout|prompt_input_exit|bypass_permissions_disabled|other",
}


def normalized_hook_event(native_event: str) -> str:
    try:
        return NATIVE_TO_NORMALIZED[native_event]
    except KeyError as exc:
        raise ValueError(f"unknown Claude hook event: {native_event}") from exc


def hook_command(native_event: str) -> dict[str, Any]:
    if native_event not in CLAUDE_NATIVE_EVENTS:
        raise ValueError(f"unknown Claude hook event: {native_event}")
    command: dict[str, Any] = {
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/bin/launch.sh",
        "args": ["hook", "claude", normalized_hook_event(native_event)],
    }
    if native_event == "UserPromptSubmit":
        command["timeout"] = 35
    elif native_event == "Stop":
        # Claude Code's Stop default is 600s and Stop has no shared budget.
        # One second cannot cover launcher dispatch plus frozen-runtime cold
        # start, so turn-artifact deletion would silently miss its deadline and
        # fall through to the 24-hour TTL sweep.  Three seconds matches Codex.
        command["timeout"] = 3
    elif native_event == "SessionEnd":
        # SessionEnd hooks share a 1.5-second budget; stay inside it.
        command["timeout"] = 1
    else:
        command["timeout"] = 2
    return command


def build_hooks() -> dict[str, Any]:
    hooks: dict[str, list[dict[str, Any]]] = {}
    for native_event in CLAUDE_NATIVE_EVENTS:
        entry: dict[str, Any] = {"hooks": [hook_command(native_event)]}
        matcher = _MATCHERS[native_event]
        if matcher:
            entry["matcher"] = matcher
        hooks[native_event] = [entry]
    return {
        "description": "Fail-open OpenSocrates prompt selection and artifact cleanup.",
        "hooks": hooks,
    }


build_hooks_config = build_hooks
to_native_hook_config = build_hooks


__all__ = [
    "CLAUDE_NATIVE_EVENTS",
    "NATIVE_TO_NORMALIZED",
    "build_hooks",
    "build_hooks_config",
    "hook_command",
    "normalized_hook_event",
    "to_native_hook_config",
]
