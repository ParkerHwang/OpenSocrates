"""Closed Claude lifecycle names; no prompt, transcript, or identity storage."""

from __future__ import annotations

from dataclasses import dataclass

NATIVE_TO_NORMALIZED = {
    "SessionStart": "session_started",
    "UserPromptSubmit": "user_prompt_submitted",
    "PostCompact": "post_compaction",
    "Stop": "completion_candidate",
    "SessionEnd": "session_ended",
}
ENTRY_EVENTS = frozenset({"SessionStart", "UserPromptSubmit"})


@dataclass(frozen=True, slots=True)
class ClaudeEvent:
    """Only adapter-owned lifecycle metadata survives input normalization."""

    native_event: str
    normalized_event: str
    source: str | None = None
