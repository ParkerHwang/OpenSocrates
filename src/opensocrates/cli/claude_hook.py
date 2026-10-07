"""Fail-open Claude hook CLI; bounded transient input and no disk writes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from ..hosts.claude.adapter import build_entry_response
from ..hosts.claude.native import MAX_PAYLOAD_CHARS, parse_claude_event
from ..hosts.claude.responses import serialize_response


def _installed_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve(strict=True)
    if executable.name != "opensocrates-runtime":
        return None
    if tuple(path.name for path in executable.parents[:3]) != (
        "opensocrates-runtime",
        "darwin-arm64",
        "runtime",
    ):
        return None
    return executable.parents[3]


def run_claude_hook(stdin: TextIO, stdout: TextIO, *, plugin_root: Path | None = None) -> int:
    """Return zero with literal empty stdout on every unavailable/error path."""

    try:
        raw = stdin.read(MAX_PAYLOAD_CHARS + 1)
        event = parse_claude_event(raw)
        if event is None:
            return 0
        root = plugin_root if plugin_root is not None else _installed_root()
        response = build_entry_response(event, plugin_root=root)
        if response is not None:
            stdout.write(serialize_response(response))
            stdout.flush()
    except Exception:
        return 0
    return 0
