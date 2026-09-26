"""Read-only post-processing of retained QueueForge observations."""

import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review"
ARMS = ["vanilla", "v1.4.0", "v1.5.0-rc"]


def read(path):
    return json.loads(path.read_text())


def null_sum(values):
    return sum(values) if values and all(x is not None for x in values) else None


def summarize():
    calls, stages, cells = [], [], []
    for arm in ARMS:
        for stage in (1, 2, 3):
            folder = ROOT / "evidence" / arm / f"stage{stage}"
            if (folder / "call.json").exists():
                record = read(folder / "call.json")
                calls.append(
                    {
                        "arm": arm,
                        "stage": stage,
                        **{
                            key: record.get(key)
                            for key in [
                                "process_success",
                                "exit_code",
                                "timed_out",
                                "wall_seconds",
                                "tool_actions_started_or_completed",
                                "failed_tool_actions",
                                "incomplete_tool_actions",
                                "usage",
                                "model",
                                "effort",
                                "attempt",
                            ]
                        },
                    }
                )
            if (folder / "stage.json").exists():
                state = read(folder / "stage.json")
                checks = read(folder / "acceptance.json")
                statuses = [s["status"] for s in checks.get("scenarios", [])]
                own = read(folder / "own-tests.json") if (folder / "own-tests.json").exists() else {}
                named = []
                for line in own.get("stdout", "").splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("Test") and event.get("Action") in ("pass", "fail", "skip"):
                        named.append({"package": event.get("Package"), "test": event["Test"], "status": event["Action"]})
                stages.append(
                    {
                        "arm": arm,
                        "stage": stage,
                        "commit": state.get("source_commit"),
                        "api_checks_pass": state["api_checks_pass"],
                        "own_tests_pass": state["own_tests_pass"],
                        "named_own_tests": named,
                        "domain_tests_seen": sum(x["test"] != "TestPinnedDriverAvailable" for x in named),
                        "dependency_locks_unchanged": state[
                            "dependency_locks_unchanged"
                        ],
                        "expected_scenarios": 8 if stage == 1 else 19,
                        "unavailable_reason": checks.get("unavailable_reason"),
                        "scenario_counts": {
                            s: statuses.count(s)
                            for s in ["pass", "fail", "error", "unassessable"]
                        },
                    }
                )
    for stage in (2, 3):
        path = ROOT / "evidence" / f"performance-stage{stage}" / "summary.json"
        if not path.exists():
            continue
        for row in read(path):
            config = row["config"]
            measured = (row.get("phases") or {}).get("measure") or {}
            conservation = row.get("conservation") or {}
            attempts = measured.get("attempts")
            errors = measured.get("errors")
            resource = row.get("server_resources") or {}
            generator = row.get("generator_resources") or {}
            cells.append(
                {
                    "arm": config["arm"],
                    "stage": stage,
                    "workload": config["workload"],
                    "concurrency": config["concurrency"],
                    "rate": config["rate"],
                    "repetition": config["repetition"],
                    "cell_index": config["index"],
                    "measurement_version": 2,
                    "attempted": row.get("attempted"),
                    "artifact_gate_pass": row.get("artifact_gate_pass"),
                    "conservation_pass": conservation.get("valid"),
                    "unavailable_reason": row.get("unavailable_reason"),
                    "http_success_rps": measured.get("successful_rps"),
                    "attempted_rps": measured.get("attempted_rps"),
                    "completed_rps": measured.get("completed_rps"),
                    "completed_jobs_per_second": measured.get(
                        "completed_jobs_per_second"
                    ),
                    "send_p50_ms": (measured.get("send_latency_ms") or {}).get("p50"),
                    "send_p95_ms": (measured.get("send_latency_ms") or {}).get("p95"),
                    "send_p99_ms": (measured.get("send_latency_ms") or {}).get("p99"),
                    "scheduled_p99_ms": (
                        measured.get("scheduled_latency_ms") or {}
                    ).get("p99"),
                    "samples": measured.get("sample_count"),
                    "attempts": attempts,
                    "errors": errors,
                    "error_pct": 100 * errors / attempts
                    if attempts and errors is not None
                    else None,
                    "timeouts": measured.get("timeouts"),
                    "drain_completed_requests": measured.get("drain_completed_requests"),
                    "drain_budget_exceeded": row.get("drain_budget_exceeded"),
                    "stopped_transport_failures": row.get("stopped_transport_failures"),
                    "generator_capacity_flag": row.get("generator_capacity_flag"),
                    "scheduled_count": measured.get("scheduled_count"),
                    "scheduler_misses": measured.get("scheduler_misses"),
                    "scheduler_lag_p99_ms": (measured.get("scheduler_lag_ms") or {}).get("p99"),
                    "drops": measured.get("drops"),
                    "idle_claims": measured.get("idle_claims"),
                    "duplicates": measured.get("duplicates"),
                    "lost_acknowledgements": row.get("lost_acknowledgements"),
                    "server_cpu_seconds": resource.get("cpu_seconds"),
                    "server_peak_rss_mib": resource["peak_rss_bytes"] / 1024**2
                    if resource.get("peak_rss_bytes") is not None
                    else None,
                    "generator_cpu_seconds": generator.get("cpu_seconds"),
                    "generator_peak_rss_mib": generator["peak_rss_bytes"] / 1024**2
                    if generator.get("peak_rss_bytes") is not None
                    else None,
                    "db_bytes": row.get("db_bytes"),
                    "wal_bytes": row.get("wal_bytes"),
                    "db_bytes_at_measure_end": row.get("db_bytes_at_measure_end"),
                    "wal_bytes_at_measure_end": row.get("wal_bytes_at_measure_end"),
                    "load_average_1m": (row.get("host_before") or {}).get("load_average", [None])[0],
                }
            )
            cells[-1]["measurement_valid"] = (
                not row.get("unavailable_reason")
                and row.get("attempted") is True
                and row.get("drain_budget_exceeded") is False
                and row.get("stopped_transport_failures") is False
            )
            cells[-1]["observable_load_checks_pass"] = (
                cells[-1]["measurement_valid"]
                and conservation.get("valid") is True
                and all(measured.get(k) == 0 for k in ("errors", "timeouts", "duplicates"))
                and row.get("lost_acknowledgements") == 0
            )
            cells[-1]["frozen_artifact_and_load_gates_pass"] = (
                cells[-1]["observable_load_checks_pass"]
                and row.get("artifact_gate_pass") is True
            )
    groups = []
    keys = sorted(
        {
            (x["arm"], x["stage"], x["workload"], x["concurrency"], x["rate"])
            for x in cells
        }
    )
    metrics = [
        "http_success_rps",
        "completed_jobs_per_second",
        "send_p95_ms",
        "send_p99_ms",
        "scheduled_p99_ms",
        "error_pct",
        "server_cpu_seconds",
        "server_peak_rss_mib",
        "generator_cpu_seconds",
        "generator_peak_rss_mib",
        "scheduler_lag_p99_ms",
    ]
    for arm, stage, workload, concurrency, rate in keys:
        rows = [
            x
            for x in cells
            if (x["arm"], x["stage"], x["workload"], x["concurrency"], x["rate"])
            == (arm, stage, workload, concurrency, rate)
        ]
        group = {
            "arm": arm,
            "stage": stage,
            "workload": workload,
            "concurrency": concurrency,
            "rate": rate,
            "planned_or_recorded_cells": len(rows),
            "available_cells": sum(x["measurement_valid"] for x in rows),
            "all_artifact_gates_pass": all(
                x["artifact_gate_pass"] is True for x in rows
            ),
            "all_conservation_pass": all(x["conservation_pass"] is True for x in rows),
            "all_observable_load_checks_pass": all(x["observable_load_checks_pass"] for x in rows),
            "all_frozen_gates_pass": all(x["frozen_artifact_and_load_gates_pass"] for x in rows),
            "scope": "Source durability review and generator-capacity inspection are separate; no blanket qualification inferred from pre-load gates.",
        }
        for metric in metrics:
            values = [x[metric] for x in rows if x["measurement_valid"] and x[metric] is not None]
            group[metric] = (
                {
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                    "n": len(values),
                }
                if values
                else None
            )
        groups.append(group)
    totals = {}
    for arm in ARMS:
        relevant = [x for x in calls if x["arm"] == arm]
        totals[arm] = {
            "attempted_model_calls": len(relevant),
            "completed_successfully": sum(
                x["process_success"] is True for x in relevant
            ),
            "model_seconds": null_sum([x["wall_seconds"] for x in relevant]),
            "tool_actions": null_sum(
                [x["tool_actions_started_or_completed"] for x in relevant]
            ),
            "failed_tool_actions": null_sum(
                [x["failed_tool_actions"] for x in relevant]
            ),
            "usage": {
                key: null_sum([(x.get("usage") or {}).get(key) for x in relevant])
                for key in [
                    "input_tokens",
                    "cached_input_tokens",
                    "cache_write_input_tokens",
                    "output_tokens",
                    "reasoning_output_tokens",
                ]
            },
            "billed_cost": None,
        }
        u = totals[arm]["usage"]
        totals[arm]["uncached_input_tokens"] = (
            u["input_tokens"] - u["cached_input_tokens"]
            if u["input_tokens"] is not None and u["cached_input_tokens"] is not None else None
        )
    return {
        "calls": calls,
        "stages": stages,
        "cells": cells,
        "groups": groups,
        "development_totals": totals,
        "human_scores": None,
        "backend_model_echo": None,
        "study": "Luna-only matched replication; new outcome boundary",
        "cross_model_limit": "Prior Sol study received invalid preliminary performance feedback; this Luna study uses the corrected meter prospectively. Cross-model differences are descriptive and confounded, not a controlled gap estimate.",
        "preparation_model_calls": 0,
        "interpretation": "One generated artifact per condition; repeated load observations are not independent model replications. Window throughput and start-cohort latency remain distinct; resource figures cover process lifetime.",
    }


def main():
    result = summarize()
    (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    if result["cells"]:
        with (OUT / "performance-cells.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result["cells"][0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(result["cells"])
    print(
        json.dumps(
            {
                "model_receipts": len(result["calls"]),
                "stage_receipts": len(result["stages"]),
                "performance_cells": len(result["cells"]),
            }
        )
    )


if __name__ == "__main__":
    main()
