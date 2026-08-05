"""Fixed, bounded native hook entrypoint.

The launcher passes one normalized lane and the host name.  This module reads
one bounded JSON object, validates the lane against the native event in that
object, invokes exactly one registered adapter, and writes exactly one native
response object.  It has no logging path for callback input.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any, BinaryIO, TextIO

from ..hosts.claude.commands import NATIVE_TO_NORMALIZED as CLAUDE_EVENTS
from ..hosts.codex.commands import NATIVE_TO_NORMALIZED as CODEX_EVENTS

MAX_HOOK_INPUT_BYTES = 4 * 1024 * 1024
_HOSTS = frozenset({"claude", "codex"})
_NORMALIZED_EVENTS = frozenset(
    {
        "session_started",
        "user_prompt_submitted",
        "skill_invoked",
        "tool_succeeded",
        "tool_failed",
        "tool_batch_completed",
        "completion_candidate",
        "pre_compaction",
        "post_compaction",
        "session_ended",
    }
)


def _native_for_lane(host: str, lane: str, native: object) -> str | None:
    if not isinstance(native, str):
        return None
    events = CLAUDE_EVENTS if host == "claude" else CODEX_EVENTS
    if events.get(native) != lane:
        # Codex PreToolUse is intentionally mapped to the tool_succeeded
        # launcher lane even though its mapping value is None.
        if not (host == "codex" and native == "PreToolUse" and lane == "tool_succeeded"):
            return None
    return native


def parse_hook_arguments(argv: Sequence[str]) -> tuple[str, str] | None:
    """Accept only the two fixed launcher forms."""

    values = list(argv)
    if values and values[0] == "hook":
        values = values[1:]
    if len(values) == 2 and values[0] in _HOSTS and values[1] in _NORMALIZED_EVENTS:
        return values[0], values[1]
    if (
        len(values) == 3
        and values[0] in _NORMALIZED_EVENTS
        and values[1] == "--host"
        and values[2] in _HOSTS
    ):
        return values[2], values[0]
    return None


def _read_bounded(stream: BinaryIO | TextIO) -> bytes | None:
    source = getattr(stream, "buffer", stream)
    try:
        value = source.read(MAX_HOOK_INPUT_BYTES + 1)
    except Exception:
        return None
    if isinstance(value, str):
        try:
            value = value.encode("utf-8")
        except UnicodeEncodeError:
            return None
    if not isinstance(value, (bytes, bytearray)):
        return None
    result = bytes(value)
    if len(result) > MAX_HOOK_INPUT_BYTES:
        return None
    return result


def _input_native_name(raw: bytes) -> str | None:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(decoded, Mapping):
        return None
    candidate = decoded.get("hook_event_name")
    return candidate if isinstance(candidate, str) else None


def _safe_response(value: object) -> str:
    if isinstance(value, str):
        if value == "":
            return ""
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            decoded = None
    else:
        decoded = value
    if isinstance(decoded, Mapping):
        # The native adapter already performed host-specific legality checks;
        # canonicalization here guarantees one object and one trailing LF.
        return json.dumps(decoded, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return "{}\n"


def run_hook(  # noqa: C901  # Explicit host-safe early-return boundary.
    argv: Sequence[str] | None = None,
    *,
    stdin: BinaryIO | TextIO | None = None,
    stdout: TextIO | None = None,
    services: Any | None = None,
) -> int:
    """Run one fixed hook callback without exposing callback input."""

    output = stdout or sys.stdout
    arguments = argv if argv is not None else sys.argv[1:]
    selected = parse_hook_arguments(arguments)
    if selected is None:
        output.write("")
        return 0
    host, lane = selected
    # The isolated selector worker marks its environment before it can cause a
    # nested hook callback.  Return before reading callback input or composing
    # services.
    if os.environ.get("OPENSOCRATES_SELECTOR_ACTIVE"):
        return 0
    raw = _read_bounded(stdin or sys.stdin)
    if raw is None:
        output.write("")
        return 0
    native_name = _input_native_name(raw)
    native_name = _native_for_lane(host, lane, native_name)
    if native_name is None:
        output.write("")
        return 0
    runtime: Any | None = None
    owns_runtime = services is None
    try:
        runtime = services
        if runtime is None:
            from ..cli.runtime import build_runtime_services

            runtime = build_runtime_services(host=host)
        adapter = getattr(runtime, "adapter_for", lambda _host: None)(host)
        if adapter is None:
            output.write("")
            return 0
        result = adapter.handle(raw, event_name=native_name)
        output.write(_safe_response(getattr(result, "stdout", None)))
    except Exception:
        # Native callbacks are host-owned.  A central composition failure must
        # remain a nonblocking pass-through and must not print a traceback.
        output.write("")
    finally:
        if owns_runtime and runtime is not None:
            closer = getattr(runtime, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: BinaryIO | TextIO | None = None,
    stdout: TextIO | None = None,
    services: Any | None = None,
) -> int:
    return run_hook(
        argv if argv is not None else sys.argv[1:], stdin=stdin, stdout=stdout, services=services
    )


entrypoint = run_hook


__all__ = ["MAX_HOOK_INPUT_BYTES", "entrypoint", "main", "parse_hook_arguments", "run_hook"]
