"""Post-outcome accounting and numeric audit; never repairs candidate artifacts."""

from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def optional(path):
    return read(path) if path.is_file() else None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def usage_totals(rows, key):
    values = [r["usage"][key] for r in rows if r["usage"][key] is not None]
    return {
        "reported_sum": sum(values) if values else None,
        "reported_calls": len(values),
        "missing_attempts": sum(r["call_attempted"] and r["usage"][key] is None for r in rows),
    }


def summary():
    manifest = read(HERE / "manifest.json")
    rows = []
    for cell in manifest["cells"]:
        directory = HERE / "results" / cell["id"]
        call = optional(directory / "call.json")
        acceptance = optional(directory / "acceptance.json")
        office = optional(directory / "office-checks.json")
        own = optional(directory / "own-tests.json")
        build = optional(directory / "build.json")
        protected = optional(directory / "protected-inputs.json")
        performance = optional(directory / "performance.json")
        native_operations = optional(directory / "native-operations.json")
        row = {
            **cell,
            "call_attempted": (directory / "call.started.json").exists(),
            "process_success": call.get("process_success") if call else None,
            "wall_seconds": call.get("wall_seconds") if call else None,
            "usage": {k: (call.get("usage") or {}).get(k) if call else None for k in KEYS},
            "tool_actions": len(call.get("tool_actions", [])) if call else None,
            "nonzero_commands": sum(
                x.get("exit_code") not in (None, 0) for x in call.get("commands", [])
            )
            if call and not call.get("retention_failure")
            else None,
            "native_adapter_attempts": len(native_operations)
            if native_operations is not None
            else None,
            "direct_native_operations_lexical": call.get("direct_operations_lexical")
            if call
            else None,
            "native_response_projections": len(call.get("native_output_projections", []))
            if call
            else None,
            "protected_inputs_unchanged": protected.get("unchanged") if protected else None,
            "snapshot_available": (directory / "snapshot").is_dir(),
            "skipped": optional(directory / "skipped.json"),
            "harness_failure": optional(directory / "harness-failure.json"),
        }
        row.update(
            timed_out=call.get("timed_out") if call else None,
            failed_tool_actions=call.get("failed_tool_actions") if call else None,
            incomplete_tool_actions=call.get("incomplete_tool_actions") if call else None,
        )
        inp, cached = row["usage"]["input_tokens"], row["usage"]["cached_input_tokens"]
        row["uncached_input_tokens"] = (
            inp - cached if inp is not None and cached is not None else None
        )
        if cell["task"] == "coding":
            row.update(
                build_pass=build.get("exit_code") == 0 and not build.get("timeout")
                if build
                else None,
                own_tests_pass=own.get("exit_code") == 0 and not own.get("timeout")
                if own
                else None,
                passed_checks=acceptance.get("passed_count") if acceptance else None,
                total_checks=28,
                failed_checks=[x["name"] for x in acceptance["groups"] if not x["passed"]]
                if acceptance
                else None,
            )
            row["artifact_gate"] = bool(
                acceptance
                and acceptance["passed"]
                and row["own_tests_pass"]
                and row["protected_inputs_unchanged"]
            )
            row["performance_qualified"] = bool(
                performance and performance["interpretation"] == "eligible" and row["artifact_gate"]
            )
            row["performance"] = {}
            if performance:
                for workload in ("read", "write"):
                    for concurrency in (1, 16):
                        cells = [
                            x
                            for x in performance["cells"]
                            if x["workload"] == workload
                            and x["concurrency"] == concurrency
                            and x.get("stats")
                        ]
                        fields = {}
                        for name, getter in [
                            ("rps", lambda x: x["stats"]["throughput_success_rps"]),
                            (
                                "p99_ms",
                                lambda x: (
                                    x["stats"]["latency_s"]["p99"] * 1000
                                    if x["stats"]["latency_s"]["p99"] is not None
                                    else None
                                ),
                            ),
                            (
                                "cpu_seconds",
                                lambda x: (x.get("resources") or {}).get(
                                    "cpu_s_warmup_measurement_drain"
                                ),
                            ),
                            (
                                "rss_mib",
                                lambda x: (
                                    ((x.get("resources") or {}).get("rss_kib_sampled_peak") / 1024)
                                    if (x.get("resources") or {}).get("rss_kib_sampled_peak")
                                    is not None
                                    else None
                                ),
                            ),
                        ]:
                            values = [getter(x) for x in cells]
                            values = [v for v in values if v is not None]
                            fields[name] = (
                                {
                                    "median": statistics.median(values),
                                    "min": min(values),
                                    "max": max(values),
                                    "n": len(values),
                                }
                                if values
                                else None
                            )
                        row["performance"][f"{workload}-c{concurrency}"] = fields
        else:
            row.update(
                office_status=office.get("status") if office else None,
                passed_checks=sum(x["passed"] for x in office.get("checks", []))
                if office and office.get("objective_score") is not None
                else None,
                total_checks=27,
                failed_checks=[x["id"] for x in office.get("checks", []) if not x["passed"]]
                if office
                else None,
            )
            row["artifact_gate"] = bool(
                office
                and office.get("status") == "assessed"
                and row["passed_checks"] == 27
                and row["protected_inputs_unchanged"]
            )
        row["episode_gate"] = row["process_success"] is True and row["artifact_gate"]
        row["terminal_message_available"] = call.get("turn_completed") if call else None
        rows.append(row)
    return {
        "schema": "opensocrates.hard-task-summary/1",
        "planned_calls": 18,
        "attempted_calls": sum(r["call_attempted"] for r in rows),
        "completed_cli_turns": sum(r["process_success"] is True for r in rows),
        "skipped_cells": sum(r["skipped"] is not None for r in rows),
        "rows": rows,
        "usage_accounting": {k: usage_totals(rows, k) for k in KEYS},
        "human_scores": None,
        "billed_cost": None,
        "backend_model_echo": None,
        "limits": [
            "One generated artifact per tuple/condition/domain",
            "Load repetitions are not model replications",
            "Prose review is separate and provisional",
            "Account-side memory isolation unproven",
        ],
    }


def audit(storage=None):
    cells = 0
    samples = 0
    values = (
        (read(path) for path in storage.glob("coding-*/performance.json"))
        if storage
        else (
            {"cells": json.loads(gzip.decompress(path.read_bytes()))}
            for path in (HERE / "results").glob("coding-*/timing-samples.json.gz")
        )
    )
    for value in values:
        for cell in value["cells"]:
            if not cell.get("stats"):
                continue
            rows = cell["raw_attempts"]
            stats = cell["stats"]
            begin = stats["measured_start_monotonic"]
            end = stats["measured_end_monotonic"]
            cohort = [r for r in rows if begin <= r["started"] < end]
            complete = [r for r in cohort if begin <= r["ended"] < end]
            success = [r for r in complete if r["success"]]
            assert stats["attempts_started"] == len(cohort)
            assert stats["attempts_completed_in_window"] == len(complete)
            assert stats["successful_completions_in_window"] == len(success)
            assert stats["attempts_failed"] == sum(not r["success"] for r in cohort)
            assert stats["carry_in_completions"] == sum(
                r["started"] < begin and begin <= r["ended"] < end for r in rows
            )
            assert stats["attempts_drained_after_window"] == sum(r["ended"] >= end for r in cohort)
            assert math.isclose(
                stats["throughput_success_rps"], len(success) / (end - begin), rel_tol=1e-12
            )
            latencies = sorted(r["ended"] - r["started"] for r in cohort)
            for label, q in [("p50", 0.5), ("p95", 0.95), ("p99", 0.99)]:
                expected = (
                    latencies[max(0, math.ceil(q * len(latencies)) - 1)] if latencies else None
                )
                assert stats["latency_s"][label] == expected
            assert stats["all_attempts_started"] == len(rows)
            assert stats["all_attempts_completed"] == len(rows)
            assert stats["all_failed"] == sum(not r["success"] for r in rows)
            assert stats["all_successful"] == sum(r["success"] for r in rows)
            assert all(r["latency_s"] == r["ended"] - r["started"] for r in rows)
            cells += 1
            samples += len(rows)
    return {
        "status": "pass",
        "cells": cells,
        "raw_samples_including_warmup": samples,
        "method": "independent recomputation from monotonic starts/ends and success flags; start-cohort nearest-rank quantiles",
    }


def lock():
    files = {
        str(p.relative_to(HERE)): sha(p)
        for p in sorted((HERE / "results").rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }
    return {"schema": "opensocrates.hard-outcome-lock/1", "files": files}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--storage", type=Path)
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    result = summary()
    if args.write:
        for name, value in [("summary.json", result), ("outcomes.lock.json", lock())] + (
            [("numeric-audit.json", audit(args.storage))] if args.storage else []
        ):
            with (HERE / name).open("x", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
                f.write("\n")
    print(
        json.dumps(
            {
                "attempted": result["attempted_calls"],
                "completed": result["completed_cli_turns"],
                "rows": [
                    {"id": r["id"], "checks": r["passed_checks"], "gate": r["artifact_gate"]}
                    for r in result["rows"]
                ],
            },
            indent=2,
        )
    )
