#!/usr/bin/env python3
"""Summarize safe public swarm records; never execute actors or infer prices.

Input is S044's launch-v1 JSONL, one unique cell per line. Optional top-level
``cached_input_tokens`` and ``total_tokens`` are reported counters, not additions
to input/output. ``usage_semantics`` may declare ``input_cache`` as ``included``
or ``excluded``, ``total`` as ``input_plus_output`` or
``input_plus_cache_plus_output``, and ``scope`` as ``full_interaction`` or
``actor_response``. Missing declarations remain unknown. No total is derived.

An optional assignment ledger is a JSON array or an object with a ``cells``
array. Without it, absent records have unknown execution state; the launch-v1
54-cell plan is context, not evidence that 54 calls were made or assigned.
Only aggregates, safe categories and input digests are written, never answers,
prompts, paths from input records, raw errors or host transcripts.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
import statistics
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
LOCALES = ("en", "ko")
ARMS = ("plain", "general-check", "native-opensocrates")
STATUSES = ("NOT_RUN", "STARTED", "COMPLETED", "FAILED", "TIMEOUT", "BLOCKED")
ATTEMPTED = frozenset({"STARTED", "COMPLETED", "FAILED", "TIMEOUT"})
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")
SIZE_FIELDS = ("utf8_bytes", "unicode_scalars", "nonblank_lines")
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_CELLS = 54
SEMANTIC_VALUES = {
    "input_cache": ("included", "excluded"),
    "total": ("input_plus_output", "input_plus_cache_plus_output"),
    "scope": ("full_interaction", "actor_response"),
}


class MetricsError(ValueError):
    """Contains only a fixed safe category, never input content."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise MetricsError("duplicate_json_key")
        value[key] = item
    return value


def _decode(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except MetricsError:
        raise
    except (ValueError, RecursionError) as error:
        raise MetricsError("invalid_json") from error


def _read(path: Path) -> bytes:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as error:
        raise MetricsError("input_unavailable") from error
    if len(data) > MAX_INPUT_BYTES:
        raise MetricsError("input_too_large")
    return data


def _text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeError as error:
        raise MetricsError("invalid_utf8") from error


def _planned_cells() -> dict[str, dict[str, Any]]:
    cells: dict[str, dict[str, Any]] = {}
    for family, locale, arm, repeat in itertools.product(FAMILIES, LOCALES, ARMS, (1, 2, 3)):
        case_id = f"{family}-{locale}"
        cell_id = f"{case_id}-{arm}-r{repeat}"
        cells[cell_id] = {
            "cell_id": cell_id,
            "case_id": case_id,
            "family": family,
            "locale": locale,
            "arm": arm,
            "repeat": repeat,
        }
    return cells


PLAN = _planned_cells()


def _cell(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MetricsError("record_not_object")
    cell_id = value.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in PLAN:
        raise MetricsError("cell_id_outside_launch_v1")
    expected = PLAN[cell_id]
    for field in ("case_id", "family", "locale", "arm", "repeat"):
        if field in value and (
            value[field] != expected[field] or (field == "repeat" and type(value[field]) is not int)
        ):
            raise MetricsError("cell_identity_conflict")
    return expected.copy()


def _number(value: Any, *, integral: bool = False) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricsError("metric_not_number")
    if isinstance(value, float) and not math.isfinite(value):
        raise MetricsError("metric_not_finite")
    if value < 0 or (integral and not isinstance(value, int)):
        raise MetricsError("metric_outside_range")
    return value


def _sizes(answer: Any) -> dict[str, int | None]:
    if answer is None:
        return dict.fromkeys(SIZE_FIELDS)
    if not isinstance(answer, str):
        raise MetricsError("public_answer_not_text")
    try:
        byte_count = len(answer.encode("utf-8"))
    except UnicodeError as error:
        raise MetricsError("public_answer_not_unicode_scalars") from error
    return {
        "utf8_bytes": byte_count,
        "unicode_scalars": len(answer),
        "nonblank_lines": sum(bool(line.strip()) for line in answer.splitlines()),
    }


def _semantics(value: Any) -> dict[str, str]:
    if value is None:
        return dict.fromkeys(SEMANTIC_VALUES, "unknown")
    if not isinstance(value, dict):
        raise MetricsError("usage_semantics_not_object")
    result = {}
    for field, choices in SEMANTIC_VALUES.items():
        item = value.get(field)
        if item is not None and item != "unknown" and item not in choices:
            raise MetricsError("usage_semantics_invalid")
        result[field] = item if item in choices else "unknown"
    return result


def _record(value: Any) -> dict[str, Any]:
    row = _cell(value)
    status = value.get("status")
    if not isinstance(status, str) or status not in STATUSES:
        raise MetricsError("status_invalid")
    row["status"] = status
    for field in TOKEN_FIELDS:
        row[field] = _number(value.get(field), integral=True)
    row["elapsed_ms"] = _number(value.get("elapsed_ms"))
    row.update(_sizes(value.get("public_final_answer")))
    row["usage_semantics"] = _semantics(value.get("usage_semantics"))
    return row


def _records(data: bytes) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    # JSONL separates records with LF. Unicode line separators may legitimately
    # occur inside a JSON answer string and must not split that record.
    for line in _text(data).split("\n"):
        if not line.strip():
            continue
        row = _record(_decode(line))
        if row["cell_id"] in seen:
            raise MetricsError("duplicate_cell_no_retry_allowed")
        seen.add(row["cell_id"])
        rows.append(row)
        if len(rows) > MAX_CELLS:
            raise MetricsError("record_budget_exceeded")
    return rows


def _assignments(data: bytes) -> list[dict[str, Any]]:
    value = _decode(_text(data))
    cells = value.get("cells") if isinstance(value, dict) else value
    if not isinstance(cells, list) or len(cells) > MAX_CELLS:
        raise MetricsError("assignment_ledger_invalid")
    result = [_cell(cell) for cell in cells]
    if len({cell["cell_id"] for cell in result}) != len(result):
        raise MetricsError("duplicate_assignment")
    return result


def _stats(values: list[int | float]) -> dict[str, Any]:
    if not values:
        return dict.fromkeys(("observed_sum", "mean", "median", "p95", "min", "max"))
    ordered = sorted(values)
    try:
        total = sum(values)
        average = total / len(values)
        median = statistics.median(values)
    except OverflowError as error:
        raise MetricsError("aggregate_outside_range") from error
    try:
        finite = all(math.isfinite(item) for item in (average, median))
    except OverflowError as error:
        raise MetricsError("aggregate_outside_range") from error
    if not finite:
        raise MetricsError("aggregate_outside_range")
    return {
        "observed_sum": total,
        "mean": average,
        "median": median,
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "min": ordered[0],
        "max": ordered[-1],
    }


def _status_metric(rows: list[dict[str, Any]], field: str, status: str) -> dict[str, Any]:
    subset = [row for row in rows if row["status"] == status]
    known = [row[field] for row in subset if row[field] is not None]
    return {
        "records": len(subset),
        "measured": len(known),
        "missing": len(subset) - len(known),
        "observed_sum": _stats(known)["observed_sum"],
    }


def _metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [row[field] for row in rows if row[field] is not None]
    by_status = {status: _status_metric(rows, field, status) for status in STATUSES}
    attempted = [row for row in rows if row["status"] in ATTEMPTED]
    attempted_known = sum(row[field] is not None for row in attempted)
    return {
        "record_denominator": len(rows),
        "measured": len(values),
        "missing": len(rows) - len(values),
        "attempted_denominator": len(attempted),
        "attempted_measured": attempted_known,
        "attempted_missing": len(attempted) - attempted_known,
        **_stats(values),
        "by_status": by_status,
    }


def _semantic_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result = {}
    for field, choices in SEMANTIC_VALUES.items():
        counts = Counter(row["usage_semantics"][field] for row in rows)
        result[field] = {choice: counts[choice] for choice in (*choices, "unknown")}
    return result


def _token_strata(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Provider counter meaning and measurement scope must not disappear in a
    # global sum. An unknown profile is retained as a separate visible stratum.
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row["usage_semantics"][field] for field in SEMANTIC_VALUES)
        groups.setdefault(key, []).append(row)
    return [
        {
            "usage_semantics": dict(zip(SEMANTIC_VALUES, key, strict=True)),
            "records": len(subset),
            "tokens": {field: _metric(subset, field) for field in TOKEN_FIELDS},
        }
        for key, subset in sorted(groups.items())
    ]


def _summary(
    rows: list[dict[str, Any]],
    planned: list[dict[str, Any]],
    assigned: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    statuses = Counter(row["status"] for row in rows)
    measured_any = sum(
        any(row[field] is not None for field in (*TOKEN_FIELDS, "elapsed_ms", *SIZE_FIELDS))
        for row in rows
    )
    return {
        "counts": {
            "planned_launch_v1": len(planned),
            "assigned": None if assigned is None else len(assigned),
            "records": len(rows),
            "missing_records": None if assigned is None else len(assigned) - len(rows),
            "attempted": sum(statuses[status] for status in ATTEMPTED),
            "failed": statuses["FAILED"],
            "timeouts": statuses["TIMEOUT"],
            "failed_or_timeout": statuses["FAILED"] + statuses["TIMEOUT"],
            "unfinished_started": statuses["STARTED"],
            "status": {status: statuses[status] for status in STATUSES},
            "measured_any": measured_any,
            "missing_all_metrics": len(rows) - measured_any,
        },
        "elapsed_ms": _metric(rows, "elapsed_ms"),
        "public_output_size": {field: _metric(rows, field) for field in SIZE_FIELDS},
        "tokens_reported_counters": {field: _metric(rows, field) for field in TOKEN_FIELDS},
        "usage_semantics_counts": _semantic_counts(rows),
        "token_semantic_strata": _token_strata(rows),
    }


def _strata(
    rows: list[dict[str, Any]],
    assigned: list[dict[str, Any]] | None,
    dimensions: tuple[str, ...],
) -> list[dict[str, Any]]:
    plan = list(PLAN.values())
    keys = sorted({tuple(cell[field] for field in dimensions) for cell in plan})
    result = []
    for key in keys:

        def matches(row: dict[str, Any], group_key: tuple[Any, ...] = key) -> bool:
            return tuple(row[field] for field in dimensions) == group_key

        result.append(
            {
                **dict(zip(dimensions, key, strict=True)),
                **_summary(
                    [row for row in rows if matches(row)],
                    [row for row in plan if matches(row)],
                    None if assigned is None else [row for row in assigned if matches(row)],
                ),
            }
        )
    return result


def summarize(
    data: bytes, *, assignment_data: bytes | None = None, source_sha: str | None = None
) -> dict[str, Any]:
    """Pure arithmetic over supplied public records, without host/API access."""
    if source_sha is not None and re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise MetricsError("source_sha_invalid")
    rows = _records(data)
    assigned = None if assignment_data is None else _assignments(assignment_data)
    if assigned is not None:
        assigned_ids = {cell["cell_id"] for cell in assigned}
        if any(row["cell_id"] not in assigned_ids for row in rows):
            raise MetricsError("result_without_assignment")
    return {
        "schema_version": 1,
        "artifact": "usage-summary",
        "input_contract": "control/interfaces-v1.json result JSONL",
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "assignment_sha256": (
            None if assignment_data is None else hashlib.sha256(assignment_data).hexdigest()
        ),
        "source_sha": source_sha,
        "source_sha_unknown_reason": "not_supplied" if source_sha is None else None,
        "assignment_unknown_reason": "ledger_not_supplied" if assigned is None else None,
        "definitions": {
            "attempted": sorted(ATTEMPTED),
            "not_attempted_statuses": ["NOT_RUN", "BLOCKED"],
            "observed_sum": "Sum of measured values only; null when none; missing is never zero.",
            "means_and_percentiles": "Measured records only; p95 uses nearest rank; see denominators.",
            "status_inclusion": "All statuses contribute any known metrics, including failure/timeout.",
            "elapsed_ms": "Reported elapsed_ms only; timestamps are not subtracted or imputed.",
            "tokens": "Separate reported counters; no cache addition and no derived total.",
            "token_comparability": "Unknown semantics remain unknown; sums do not establish billing.",
            "scope": "Unknown unless explicitly declared; actor-only is not full interaction usage.",
            "utf8_bytes": "UTF-8 encoding of the complete supplied public_final_answer, unchanged.",
            "unicode_scalars": "Unicode scalar count, not graphemes, words or tokens.",
            "nonblank_lines": "str.splitlines lines containing any non-whitespace character.",
            "missing_answer": "Absent/null answer is missing; an explicit empty string measures zero.",
        },
        "limitations": [
            "No prices, monetary costs, speed improvements or savings are inferred.",
            "No whitespace word/eojeol count or cross-locale semantic length comparison is made.",
            "No model identity, service tier, native installation, delivery, reading or application is inferred.",
            "Native arm labels do not establish native installation or manual injection equivalence.",
            "Unknown backend identity and unavailable independent judging remain unresolved upstream.",
            "These records do not describe the 100 authoring chats as an experiment control group.",
            "No freeze, isolation, quality, completeness of public answer capture or provider billing is certified.",
            "Absent records are not assumed to be NOT_RUN, successful, or zero-cost.",
        ],
        "overall": _summary(rows, list(PLAN.values()), assigned),
        "by_arm": _strata(rows, assigned, ("arm",)),
        "by_locale": _strata(rows, assigned, ("locale",)),
        "by_family": _strata(rows, assigned, ("family",)),
        "by_arm_locale_family": _strata(rows, assigned, ("arm", "locale", "family")),
    }


def _write(path: Path, report: dict[str, Any]) -> None:
    temporary: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".usage-", delete=False
        ) as stream:
            temporary = stream.name
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
        temporary = None
    except (OSError, ValueError, OverflowError) as error:
        raise MetricsError("output_unavailable") from error
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="S044 safe-results.jsonl")
    parser.add_argument("--output", required=True, type=Path, help="Destination usage-summary.json")
    parser.add_argument("--assignments", type=Path, help="Optional launch-v1 cells JSON ledger")
    parser.add_argument("--source-sha", help="Exact frozen candidate SHA; never guessed")
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        inputs = [args.input] + ([] if args.assignments is None else [args.assignments])
        if any(output == path.resolve() for path in inputs):
            raise MetricsError("output_would_replace_input")
        data = _read(args.input)
        assignments = None if args.assignments is None else _read(args.assignments)
        report = summarize(data, assignment_data=assignments, source_sha=args.source_sha)
        _write(output, report)
    except MetricsError as error:
        print(f"swarm-usage-metrics: ERROR {error}")
        return 2
    print("swarm-usage-metrics: WROTE arithmetic summary; no experiment executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
