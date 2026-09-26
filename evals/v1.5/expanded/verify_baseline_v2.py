"""Audit every retained old pilot attempt without changing any old result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent


def audit() -> dict:  # noqa: C901  # Historical receipt shapes remain separate and explicit.
    inventory = json.loads((HERE / "baseline-inventory.v2.json").read_text())
    for name, expected in inventory["sha256"].items():
        assert hashlib.sha256((OLD / name).read_bytes()).hexdigest() == expected, name
    files = []
    all_calls = []
    for path in sorted((OLD / "results").glob("*.json")):
        value = json.loads(path.read_text())
        calls = [call for cell in value["cells"] for call in cell.get("calls", [])]
        assert all(
            cell.get("attempted_calls_known", len(cell["calls"])) == len(cell["calls"])
            for cell in value["cells"]
        )
        for call in calls:
            for key, count in call["usage"].items():
                assert count is None or (type(count) is int and count >= 0), (path, key)
            if "tool_events" in call:
                assert len(call["tool_events"]) == call["tool_calls"]
                assert (
                    sum(event["policy_call"] for event in call["tool_events"])
                    == call["policy_calls"]
                )
            if (
                call["usage"]["input_tokens"] is not None
                and call["usage"]["cached_input_tokens"] is not None
            ):
                assert call["usage"]["cached_input_tokens"] <= call["usage"]["input_tokens"]
        files.append(
            {
                "file": str(path.relative_to(OLD)),
                "scheduled_cells": len(value["cells"]),
                "declared_attempts": len(calls),
                "missing_exit_receipts": sum(c.get("exit_code") is None for c in calls),
                "failed_cli_processes": sum(c.get("exit_code") not in (0, None) for c in calls),
                "strict_cell_successes": sum(
                    c.get("deterministic_success") is True for c in value["cells"]
                ),
                "keyword_policy_flags_are_not_exact_calls": True,
            }
        )
        all_calls.extend(calls)
    memory = []
    for name in (
        "eval01-pilot-2026-09-24.json",
        "eval01-guide-repair-2026-09-24.json",
        "eval04-pilot-2026-09-24.json",
    ):
        value = json.loads((OLD / "memory-results" / name).read_text())
        receipts = value.get("receipts", value.get("cells", []))
        for receipt in receipts:
            grade = receipt.get("grade")
            declared = receipt.get("all_frozen_gates_pass", receipt.get("all_gates_pass"))
            if grade is not None and declared is not None:
                assert bool(grade) and all(grade.values()) == declared
            all_calls.append(receipt)
        memory.append(
            {
                "file": name,
                "declared_attempts": len(receipts),
                "missing_wall_values": sum(
                    receipt.get("wall_seconds") is None for receipt in receipts
                ),
            }
        )
    usage = {}
    categories = sorted({key for call in all_calls for key in (call.get("usage") or {})})
    for key in categories:
        values = [(call.get("usage") or {}).get(key) for call in all_calls]
        usage[key] = {
            "sum_of_available_values": sum(value for value in values if value is not None),
            "missing_call_count": sum(value is None for value in values),
            "total_is_complete": all(value is not None for value in values),
        }
    assert len(all_calls) == 109
    assert sum(row["missing_exit_receipts"] for row in files) == 8
    assert sum(row["failed_cli_processes"] for row in files) == 4
    return {
        "schema": "opensocrates.v1.5.baseline-audit/2.0.0",
        "frozen_files_checked": len(inventory["sha256"]),
        "model_collaboration_batches": files,
        "memory_batches": memory,
        "all_declared_evaluation_calls": len(all_calls),
        "usage": usage,
        "source_client_package_quality_are_separate": True,
        "limits": [
            "Eight attempted calls have placeholder receipts; missing usage is not zero.",
            "Nine original coding sessions have missing wall time; cannot reconstruct efficiency.",
            "Old native executable runtime/hook delivery is unverified; inventory is not activation.",
            "Old EVAL05 semantic artifacts were discarded; strict field failures cannot be regraded.",
            "This verifies retained data consistency, not its original semantic correctness or causal effects.",
        ],
    }


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
