#!/usr/bin/env python3
"""Shared machine-readable contracts for the v1.2 adjudication tools."""

from __future__ import annotations

from typing import Any

EVALUATION_ID = "v1.2-adjudication-51"
EVIDENCE_GRADE = "ai_assisted_provisional_development"

# Fields that disclose model behavior or evaluation outcomes. Packet builders
# and validators import this single set so their blinding boundaries cannot
# drift. ``output`` and ``status`` are intentionally included.
FORBIDDEN_PACKET_KEYS = frozenset(
    {
        "selected",
        "selected_reasoning_systems",
        "intervene",
        "instructions",
        "score",
        "pass",
        "passed",
        "failure",
        "failed",
        "effort",
        "reasoning_effort",
        "aggregate",
        "recall",
        "output",
        "model_output",
        "run_id",
        "status",
        "usage",
        "latency_ms",
    }
)


def find_forbidden_packet_keys(node: Any, path: str = "$") -> list[str]:
    """Return every forbidden key path found in a packet-visible value."""

    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_PACKET_KEYS:
                hits.append(f"{path}.{key}")
            hits.extend(find_forbidden_packet_keys(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            hits.extend(find_forbidden_packet_keys(value, f"{path}[{index}]"))
    return hits
