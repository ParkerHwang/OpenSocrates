"""Deterministic prompt token and context-size limits.

The production runtime deliberately avoids a tokenizer dependency.  Its
documented approximation counts non-whitespace runs (``len(text.split())``
with empty runs removed) as tokens.  This is stable for both supported locales
and is used consistently for fragment, group, and total checks.

The authored total ceiling is 2,440 estimated tokens.  Build/runtime prompt
validation uses 95 percent of that ceiling (2,318 tokens, rounded down) so a
host renderer can add its own envelope without silently truncating canonical
content.  Context-size limits are measured on the complete UTF-8 prompt,
including the terminal LF.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

MAX_START_CONTEXT_BYTES: Final[int] = 8 * 1024
MAX_TOOL_OBSERVATION_CONTEXT_BYTES: Final[int] = 2 * 1024
MAX_STOP_REPAIR_CONTEXT_BYTES: Final[int] = 2 * 1024

MAX_PARTICIPATION_RIGOR_TOKENS: Final[int] = 450
MAX_PRIMARY_PROCEDURE_TOKENS: Final[int] = 900
MAX_SECONDARY_COMPLEMENT_TOKENS: Final[int] = 220
MAX_EVIDENCE_CARD_COMPLETION_TOKENS: Final[int] = 750
MAX_CAPABILITY_NOTICE_TOKENS: Final[int] = 120
MAX_TOTAL_TOKENS: Final[int] = 2_440
TOTAL_VALIDATION_RATIO: Final[float] = 0.95
MAX_VALIDATED_TOTAL_TOKENS: Final[int] = math.floor(MAX_TOTAL_TOKENS * TOTAL_VALIDATION_RATIO)

# Public aliases use the wording from the architecture and acceptance
# checklist.  Keeping the aliases here avoids callers inventing their own
# slightly different limits.
START_CONTEXT_MAX_BYTES: Final[int] = MAX_START_CONTEXT_BYTES
TOOL_OBSERVATION_CONTEXT_MAX_BYTES: Final[int] = MAX_TOOL_OBSERVATION_CONTEXT_BYTES
STOP_REPAIR_CONTEXT_MAX_BYTES: Final[int] = MAX_STOP_REPAIR_CONTEXT_BYTES
TOTAL_TOKEN_CEILING: Final[int] = MAX_TOTAL_TOKENS
TOTAL_VALIDATION_TOKEN_CEILING: Final[int] = MAX_VALIDATED_TOTAL_TOKENS

EVENT_CONTEXT_LIMITS: Final[dict[str, int]] = {
    "start": MAX_START_CONTEXT_BYTES,
    "tool_observation": MAX_TOOL_OBSERVATION_CONTEXT_BYTES,
    "stop_repair": MAX_STOP_REPAIR_CONTEXT_BYTES,
}

BUCKET_LIMITS: Final[dict[str, int]] = {
    "participation_rigor": MAX_PARTICIPATION_RIGOR_TOKENS,
    "primary_procedure": MAX_PRIMARY_PROCEDURE_TOKENS,
    "secondary_complement": MAX_SECONDARY_COMPLEMENT_TOKENS,
    "evidence_card_completion": MAX_EVIDENCE_CARD_COMPLETION_TOKENS,
    "capability_notice": MAX_CAPABILITY_NOTICE_TOKENS,
}

FRAGMENT_BUCKETS: Final[dict[str, str]] = {
    "controller": "participation_rigor",
    "participation_rigor": "participation_rigor",
    "routing_classifier": "participation_rigor",
    "framing": "evidence_card_completion",
    "evidence_card_completion": "evidence_card_completion",
    "cross_exam": "evidence_card_completion",
    "strict_second_pass": "evidence_card_completion",
    "capability_notice": "capability_notice",
}

_TOKEN_RE = re.compile(r"\S+")


class PromptBudgetError(ValueError):
    """Base error for a deterministic prompt budget violation."""


class FragmentBudgetError(PromptBudgetError):
    """A fragment or fragment group exceeds its authored token limit."""


class TotalPromptBudgetError(PromptBudgetError):
    """The assembled prompt exceeds the validated total token ceiling."""


class ContextSizeError(PromptBudgetError):
    """The complete UTF-8 prompt exceeds the event-specific byte ceiling."""


@dataclass(frozen=True, slots=True)
class BudgetFragment:
    """A canonical text fragment plus its explicit budget group."""

    id: str
    text: str
    bucket: str

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise ValueError("budget fragment id must be non-empty text")
        if not isinstance(self.text, str):
            raise TypeError("budget fragment text must be text")
        if self.bucket not in BUCKET_LIMITS:
            raise ValueError(f"unknown prompt budget bucket: {self.bucket}")


@dataclass(frozen=True, slots=True)
class PromptBudgetReport:
    """Measured budget facts returned after successful enforcement."""

    event: str
    fragment_tokens: dict[str, int]
    bucket_tokens: dict[str, int]
    total_tokens: int
    context_bytes: int
    context_limit_bytes: int
    total_limit_tokens: int = MAX_VALIDATED_TOTAL_TOKENS

    @property
    def estimated_tokens(self) -> int:
        """Compatibility alias for callers that use one total estimate."""

        return self.total_tokens


ContextBudget = PromptBudgetReport
BudgetReport = PromptBudgetReport
FragmentBudget = BudgetFragment


def estimated_tokens(text: str) -> int:
    """Return the stable whitespace-run token approximation for ``text``."""

    if not isinstance(text, str):
        raise TypeError("prompt text must be text")
    return len(_TOKEN_RE.findall(text))


estimate_tokens = estimated_tokens
approximate_tokens = estimated_tokens


def utf8_bytes(text: str) -> int:
    """Return the exact encoded byte length used by context-size checks."""

    if not isinstance(text, str):
        raise TypeError("prompt text must be text")
    return len(text.encode("utf-8"))


def context_limit(event: str) -> int:
    """Return the byte limit for ``start``, ``tool_observation``, or ``stop_repair``."""

    value = getattr(event, "value", event)
    if not isinstance(value, str) or value not in EVENT_CONTEXT_LIMITS:
        raise ValueError(f"unknown prompt event: {event!r}")
    return EVENT_CONTEXT_LIMITS[value]


def _bucket_for(fragment: BudgetFragment) -> str:
    if fragment.bucket:
        return fragment.bucket
    return FRAGMENT_BUCKETS.get(fragment.id, "")


def _coerce_fragments(
    fragments: Iterable[BudgetFragment] | Mapping[str, str],
) -> tuple[BudgetFragment, ...]:
    if isinstance(fragments, Mapping):
        result: list[BudgetFragment] = []
        for fragment_id, text in fragments.items():
            if fragment_id in FRAGMENT_BUCKETS:
                bucket = FRAGMENT_BUCKETS[fragment_id]
            elif fragment_id == "primary_procedure" or fragment_id.startswith("procedure:"):
                bucket = "primary_procedure"
            elif fragment_id == "secondary_complement" or fragment_id.startswith("complement:"):
                bucket = "secondary_complement"
            else:
                raise FragmentBudgetError(
                    f"unknown prompt budget bucket for {fragment_id}: no bucket"
                )
            result.append(BudgetFragment(id=fragment_id, text=text, bucket=bucket))
        return tuple(result)
    return tuple(fragments)


def enforce_fragment_budgets(
    fragments: Iterable[BudgetFragment] | Mapping[str, str],
) -> tuple[dict[str, int], dict[str, int]]:
    """Enforce each canonical fragment group and return measured counts.

    A group is checked once after all selected fragments are projected.  This
    matters for the common policy, which is intentionally composed from the
    controller, participation/rigor, and optional classifier fragments.
    """

    fragment_tokens: dict[str, int] = {}
    bucket_tokens = {bucket: 0 for bucket in BUCKET_LIMITS}
    for fragment in _coerce_fragments(fragments):
        if fragment.id in fragment_tokens:
            raise FragmentBudgetError(f"duplicate prompt fragment ID: {fragment.id}")
        tokens = estimated_tokens(fragment.text)
        fragment_tokens[fragment.id] = tokens
        bucket = _bucket_for(fragment)
        if bucket not in BUCKET_LIMITS:
            raise FragmentBudgetError(f"unknown prompt budget bucket for {fragment.id}: {bucket!r}")
        bucket_tokens[bucket] += tokens

    for bucket, used in bucket_tokens.items():
        limit = BUCKET_LIMITS[bucket]
        if used > limit:
            raise FragmentBudgetError(
                f"{bucket} fragments use {used} estimated tokens; maximum is {limit}"
            )
    return fragment_tokens, bucket_tokens


def enforce_context_budget(
    event: str,
    fragments: Iterable[BudgetFragment] | Mapping[str, str],
    assembled_text: str,
    *,
    total_limit_tokens: int = MAX_VALIDATED_TOTAL_TOKENS,
) -> PromptBudgetReport:
    """Enforce group, total, and event-specific UTF-8 byte budgets.

    ``assembled_text`` must be the exact text that will be returned to the
    host.  No truncation or rewriting is performed by this function.
    """

    event_value = getattr(event, "value", event)
    limit_bytes = context_limit(event_value)
    if (
        not isinstance(total_limit_tokens, int)
        or isinstance(total_limit_tokens, bool)
        or total_limit_tokens <= 0
    ):
        raise ValueError("total_limit_tokens must be a positive integer")
    fragment_list = _coerce_fragments(fragments)
    fragment_counts, bucket_counts = enforce_fragment_budgets(fragment_list)
    total = estimated_tokens(assembled_text)
    if total > total_limit_tokens:
        raise TotalPromptBudgetError(
            f"prompt uses {total} estimated tokens; validation maximum is {total_limit_tokens}"
        )
    size = utf8_bytes(assembled_text)
    if size > limit_bytes:
        raise ContextSizeError(
            f"{event_value} context is {size} UTF-8 bytes; maximum is {limit_bytes}"
        )
    return PromptBudgetReport(
        event=event_value,
        fragment_tokens=fragment_counts,
        bucket_tokens=bucket_counts,
        total_tokens=total,
        context_bytes=size,
        context_limit_bytes=limit_bytes,
        total_limit_tokens=total_limit_tokens,
    )


enforce_budgets = enforce_context_budget


__all__ = [
    "BUCKET_LIMITS",
    "BudgetReport",
    "BudgetFragment",
    "ContextBudget",
    "ContextSizeError",
    "EVENT_CONTEXT_LIMITS",
    "FRAGMENT_BUCKETS",
    "FragmentBudgetError",
    "FragmentBudget",
    "MAX_CAPABILITY_NOTICE_TOKENS",
    "MAX_EVIDENCE_CARD_COMPLETION_TOKENS",
    "MAX_PARTICIPATION_RIGOR_TOKENS",
    "MAX_PRIMARY_PROCEDURE_TOKENS",
    "MAX_SECONDARY_COMPLEMENT_TOKENS",
    "MAX_START_CONTEXT_BYTES",
    "MAX_STOP_REPAIR_CONTEXT_BYTES",
    "MAX_TOOL_OBSERVATION_CONTEXT_BYTES",
    "MAX_TOTAL_TOKENS",
    "MAX_VALIDATED_TOTAL_TOKENS",
    "PromptBudgetError",
    "PromptBudgetReport",
    "START_CONTEXT_MAX_BYTES",
    "STOP_REPAIR_CONTEXT_MAX_BYTES",
    "TOTAL_TOKEN_CEILING",
    "TOTAL_VALIDATION_RATIO",
    "TOTAL_VALIDATION_TOKEN_CEILING",
    "TOOL_OBSERVATION_CONTEXT_MAX_BYTES",
    "TotalPromptBudgetError",
    "approximate_tokens",
    "context_limit",
    "enforce_budgets",
    "enforce_context_budget",
    "enforce_fragment_budgets",
    "estimate_tokens",
    "estimated_tokens",
    "utf8_bytes",
]
