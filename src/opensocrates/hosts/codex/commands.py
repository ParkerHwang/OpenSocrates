"""Fixed Codex hook commands and the data-driven hook configuration."""

from __future__ import annotations

from typing import Any

NATIVE_TO_NORMALIZED = {
    "SessionStart": "session_started",
    "UserPromptSubmit": "user_prompt_submitted",
    "PreToolUse": None,
    "PostToolUse": "tool_succeeded",
    "PreCompact": "pre_compaction",
    "PostCompact": "post_compaction",
    "Stop": "completion_candidate",
    "SessionEnd": "session_ended",
}

# PermissionRequest is a documented input shape, but v1 does not configure a
# permission handler.  Batch, unified_exec, WebSearch, and other unconfirmed
# surfaces are intentionally absent.
CODEX_NATIVE_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "Stop",
    "SessionEnd",
)

_MATCHERS = {
    "SessionStart": "startup|resume|clear|compact",
    "UserPromptSubmit": "",
    # PreToolUse remains metadata-only; the matcher is narrow so tool coverage
    # cannot be mistaken for exhaustive interception.
    "PreToolUse": "Bash|apply_patch|mcp__.*",
    "PostToolUse": "Bash|apply_patch|mcp__.*",
    "PreCompact": "manual|auto",
    "Stop": "",
    "SessionEnd": "other",
}


def normalized_hook_event(native_event: str) -> str:
    try:
        normalized = NATIVE_TO_NORMALIZED[native_event]
    except KeyError as exc:
        raise ValueError(f"unknown Codex hook event: {native_event}") from exc
    if normalized is None:
        # The fixed launcher consumes the normalized union.  PreToolUse is
        # still dispatched through the safe tool lane and produces no domain
        # event when the application has no metadata action.
        return "tool_succeeded"
    return normalized


def fixed_launcher_command(native_event: str, *, windows: bool = False) -> str:
    """Return a literal S09 launcher invocation with no shell wrapper."""

    normalized = normalized_hook_event(native_event)
    launcher = "${PLUGIN_ROOT}/bin/launch.ps1" if windows else "${PLUGIN_ROOT}/bin/launch.sh"
    if windows:
        return f'powershell -NoProfile -ExecutionPolicy Bypass -File "{launcher}" hook codex {normalized}'
    return f"{launcher} hook codex {normalized}"


def fixed_control_command(*, windows: bool = False) -> str:
    if windows:
        return 'powershell -NoProfile -ExecutionPolicy Bypass -File "${PLUGIN_ROOT}/bin/launch.ps1" control codex'
    return "${PLUGIN_ROOT}/bin/launch.sh control codex"


def hook_command(native_event: str, *, windows: bool = False) -> dict[str, Any]:
    if native_event not in CODEX_NATIVE_EVENTS:
        raise ValueError(f"unknown Codex hook event: {native_event}")
    command: dict[str, Any] = {
        "type": "command",
        "command": fixed_launcher_command(native_event, windows=windows),
    }
    # The prototype's one synchronous selector call is bounded internally at
    # thirty seconds.  Deliberately omit the host timeout so Codex applies its
    # documented 600-second maximum; every other fixed legacy handler keeps
    # its existing timeout.
    if native_event != "UserPromptSubmit":
        command["timeout"] = 3 if native_event in {"Stop", "SessionEnd"} else 2
    return command


def build_hooks() -> dict[str, Any]:
    """Build the exact v1 Codex command-handler map."""

    hooks: dict[str, list[dict[str, Any]]] = {}
    for native_event in CODEX_NATIVE_EVENTS:
        entry: dict[str, Any] = {"hooks": [hook_command(native_event)]}
        matcher = _MATCHERS[native_event]
        if matcher:
            entry["matcher"] = matcher
        hooks[native_event] = [entry]
    return {"hooks": hooks}


build_hooks_config = build_hooks
to_native_hook_config = build_hooks


__all__ = [
    "CODEX_NATIVE_EVENTS",
    "NATIVE_TO_NORMALIZED",
    "build_hooks",
    "build_hooks_config",
    "fixed_control_command",
    "fixed_launcher_command",
    "hook_command",
    "normalized_hook_event",
    "to_native_hook_config",
]
