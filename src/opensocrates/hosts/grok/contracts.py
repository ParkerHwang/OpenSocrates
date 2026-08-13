"""Privacy-safe validator for Grok hook-contract probe envelopes.

This parser is diagnostic-only. The shipped Grok package has no hooks or
runtime adapter; values are discarded so probe fixtures cannot become a
prompt or transcript storage surface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

MAX_GROK_HOOK_PAYLOAD_BYTES = 128 * 1024
_EVENTS = frozenset(
    {
        "session_start",
        "user_prompt_submit",
        "pre_tool_use",
        "post_tool_use",
        "post_tool_use_failure",
        "stop",
        "stop_failure",
        "subagent_start",
        "subagent_stop",
        "pre_compact",
        "post_compact",
        "session_end",
    }
)
_BASE_FIELDS = frozenset({"hookEventName", "sessionId", "cwd", "workspaceRoot", "timestamp"})


class GrokHookContractError(ValueError):
    """Raised when a probe payload is malformed, unsafe, or unsupported."""


@dataclass(frozen=True)
class SanitizedGrokHookEnvelope:
    event: str
    keys: tuple[str, ...]
    prompt_present: bool
    prompt_nonempty: bool


def parse_sanitized_hook_envelope(  # noqa: C901 -- explicit fail-closed field contract
    payload: bytes,
) -> SanitizedGrokHookEnvelope:
    """Validate an envelope and retain structural facts only."""

    if len(payload) > MAX_GROK_HOOK_PAYLOAD_BYTES:
        raise GrokHookContractError("Grok hook payload exceeds the 128 KiB host limit")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GrokHookContractError("Grok hook payload is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise GrokHookContractError("Grok hook payload must be a JSON object")
    event = value.get("hookEventName")
    if not isinstance(event, str) or event not in _EVENTS:
        raise GrokHookContractError("Grok hook event is unknown")
    if not _BASE_FIELDS.issubset(value):
        raise GrokHookContractError("Grok hook payload is missing a base field")
    for key in _BASE_FIELDS:
        if not isinstance(value[key], str) or not value[key]:
            raise GrokHookContractError(f"Grok hook field {key} must be a non-empty string")
    prompt = value.get("prompt")
    if prompt is not None and not isinstance(prompt, str):
        raise GrokHookContractError("Grok hook prompt must be a string when present")
    if event == "user_prompt_submit" and not isinstance(prompt, str):
        raise GrokHookContractError("UserPromptSubmit must contain the current prompt")
    if event in {"pre_tool_use", "post_tool_use", "post_tool_use_failure"}:
        if not isinstance(value.get("toolName"), str) or not isinstance(
            value.get("toolInput"), dict
        ):
            raise GrokHookContractError("Grok tool hook fields are malformed")
    return SanitizedGrokHookEnvelope(
        event=event,
        keys=tuple(sorted(value)),
        prompt_present=isinstance(prompt, str),
        prompt_nonempty=bool(prompt),
    )


__all__ = [
    "GrokHookContractError",
    "MAX_GROK_HOOK_PAYLOAD_BYTES",
    "SanitizedGrokHookEnvelope",
    "parse_sanitized_hook_envelope",
]
