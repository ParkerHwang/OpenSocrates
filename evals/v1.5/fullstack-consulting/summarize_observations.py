"""Read-only view over immutable receipts and explicitly provisional live samples."""

from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
TOOLS = {"command_execution", "file_change", "mcp_tool_call", "web_search"}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    if not path.exists():
        return []
    result = []
    for line in path.read_text().splitlines():
        try:
            result.append(json.loads(line))
        except ValueError:
            pass  # a live last line can be mid-write; raw file is unchanged
    return result


def tool_summary(events):
    starts = {}
    items = {}
    messages = 0
    plans = 0
    for row in events:
        event = row["event"]
        kind = event.get("type")
        item = event.get("item", {})
        identity = item.get("id")
        if item.get("type") in TOOLS:
            if kind == "item.started":
                starts[identity] = row["elapsed_seconds"]
            if kind == "item.completed":
                start = starts.get(identity)
                end = row["elapsed_seconds"]
                items[identity] = dict(
                    type=item["type"],
                    start_seconds=start,
                    end_seconds=end,
                    duration_seconds=end - start if start is not None else None,
                    exit_code=item.get("exit_code"),
                    status=item.get("status"),
                    command_sha256=hashlib.sha256(item["command"].encode()).hexdigest()
                    if item.get("command")
                    else None,
                )
        if kind == "item.completed" and item.get("type") == "agent_message":
            messages += 1
        if kind == "item.completed" and item.get("type") == "todo_list":
            plans += 1
    for identity, start in starts.items():
        if identity not in items:
            items[identity] = dict(
                type="uncompleted_public_tool",
                start_seconds=start,
                end_seconds=None,
                duration_seconds=None,
                exit_code=None,
                status="incomplete",
                command_sha256=None,
            )
    intervals = sorted(
        (r["start_seconds"], r["end_seconds"])
        for r in items.values()
        if r["duration_seconds"] is not None
    )
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    hashes = Counter(r["command_sha256"] for r in items.values() if r["command_sha256"])
    return dict(
        tool_items=list(items.values()),
        type_counts=dict(Counter(r["type"] for r in items.values())),
        count=len(items),
        nonzero_or_failed=sum(
            r["exit_code"] not in (0, None) or r["status"] == "failed" for r in items.values()
        ),
        missing_duration_count=sum(r["duration_seconds"] is None for r in items.values()),
        observed_tool_interval_union_seconds=sum(b - a for a, b in merged),
        repeated_command_hash_count=sum(v - 1 for v in hashes.values()),
        public_message_count=messages,
        plan_update_count=plans,
    )


def summarize():
    cohort = HERE / "v2"
    manifest = read(cohort / "manifest.json")
    rows = []
    for cell in manifest["cells"]:
        output = cohort / "results" / cell["id"]
        terminal = read(output / "call.json") if (output / "call.json").exists() else None
        events = lines(output / "observation.jsonl")
        tools = tool_summary(events)
        resources = lines(output / "resources.jsonl")
        row = {
            **cell,
            "state": "pending",
            "started_utc": None,
            "ended_utc": None,
            "wall_seconds": None,
            "usage": dict.fromkeys(KEYS),
            "tools": tools,
            "source_room_get_requests": len(lines(output / "source-requests.jsonl")),
            "resource_sample_count": len(resources),
            "peak_sampled_process_tree_rss_kib": max(
                (r["rss_kib"] for r in resources), default=None
            ),
            "peak_sampled_browser_tree_rss_kib": max(
                (r["browser_tool"]["rss_kib"] for r in resources if r.get("browser_tool")),
                default=None,
            ),
        }
        if terminal:
            row.update(
                state="complete" if terminal["process_success"] else "failed",
                started_utc=terminal["started_utc"],
                ended_utc=terminal["ended_utc"],
                wall_seconds=terminal["wall_seconds"],
                usage=terminal["usage"],
                call_receipt_sha256=sha(output / "call.json"),
                native_memory=terminal["native_memory"],
                protected_inputs_unchanged=terminal["protected_inputs_unchanged"],
                package_members_unchanged=terminal["package_members_unchanged"],
            )
        elif (output / "harness-failure.json").exists():
            row.update(state="harness_failed", failure=read(output / "harness-failure.json"))
        elif (output / "skipped.json").exists():
            row.update(state="skipped", failure=read(output / "skipped.json"))
        elif (output / "call.started.json").exists():
            row.update(
                state="running", started_utc=read(output / "call.started.json")["started_utc"]
            )
            if resources:
                row["latest_observed_elapsed_seconds"] = resources[-1]["elapsed_seconds"]
        usage = row["usage"]
        row["input_minus_reported_cached"] = (
            usage["input_tokens"] - usage["cached_input_tokens"]
            if usage.get("input_tokens") is not None
            and usage.get("cached_input_tokens") is not None
            else None
        )
        row["output_minus_reported_reasoning"] = (
            usage["output_tokens"] - usage["reasoning_output_tokens"]
            if usage.get("output_tokens") is not None
            and usage.get("reasoning_output_tokens") is not None
            else None
        )
        rows.append(row)
    totals = {}
    attempted = [r for r in rows if r["started_utc"]]
    for key in KEYS:
        values = [r["usage"].get(key) for r in attempted if r["usage"].get(key) is not None]
        totals[key] = {
            "reported_sum": sum(values) if values else None,
            "reported_cells": len(values),
            "missing_attempted_cells": len(attempted) - len(values),
        }
    return {
        "view_generated_utc": datetime.now(timezone.utc).isoformat(),
        "active_manifest_sha256": sha(cohort / "manifest.json"),
        "intended_cells": 36,
        "state_counts": dict(Counter(r["state"] for r in rows)),
        "usage_totals": totals,
        "cells": rows,
        "prior_setup_failures": 36,
        "prior_model_calls": 0,
        "limits": [
            "Mutable derived view; original receipts are authoritative.",
            "Tool intervals are public event spans, not internal reasoning time.",
            "Nonzero tool exits include expected negative checks, not just defects.",
            "Do not double-count cached input/reasoning output.",
            "Summed RSS is not unique physical memory.",
            "Billing and independent backend echo unavailable.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = summarize()
    if args.output:
        args.output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: value[k] for k in ("state_counts", "usage_totals")}, indent=2))
