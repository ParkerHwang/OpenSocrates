"""Whole-episode exposed usage with explicit missingness and subset semantics."""

from __future__ import annotations

from typing import Any

FIELDS = (
    "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
    "output_tokens", "reasoning_output_tokens",
)


def aggregate(calls: list[dict[str, Any]]) -> dict[str, Any]:
    sums: dict[str, int | None] = {}
    missing: dict[str, int] = {}
    for field in FIELDS:
        values = [(call.get("usage") or {}).get(field) for call in calls]
        missing[field] = sum(type(value) is not int or value < 0 for value in values)
        sums[field] = sum(values) if calls and missing[field] == 0 else None
    uncached = (
        sums["input_tokens"] - sums["cached_input_tokens"]
        if sums["input_tokens"] is not None and sums["cached_input_tokens"] is not None
        else None
    )
    return {
        "call_count": len(calls), "reported_usage": sums, "missing_call_count": missing,
        "derived_uncached_input_tokens": uncached if uncached is None or uncached >= 0 else None,
        "combined_input_plus_output_tokens": (
            sums["input_tokens"] + sums["output_tokens"]
            if sums["input_tokens"] is not None and sums["output_tokens"] is not None else None
        ),
        "subset_rule": "cached input is within input; reasoning output is within output; neither is added twice",
        "billing_verified": False,
        "backend_attempts": None,
    }
