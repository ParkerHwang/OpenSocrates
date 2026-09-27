"""Read-only view over immutable receipts and explicitly provisional live samples."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
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


def process_health(receipt):
    """Observe a PID without signalling it; detect exit, zombies and PID reuse."""
    result = {"pid": receipt.get("pid"), "status": "unconfirmed"}
    if not isinstance(result["pid"], int) or result["pid"] <= 0:
        return result
    try:
        probe = subprocess.run(
            ["ps", "-p", str(result["pid"]), "-o", "pid=,state=,lstart=,comm="],
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C", "TZ": "UTC"},
        )
        if probe.returncode == 1 and not probe.stdout.strip() and not probe.stderr.strip():
            return {**result, "status": "exited"}
        if probe.returncode != 0:
            return result
        fields = probe.stdout.strip().split(maxsplit=7)
        if len(fields) != 8 or int(fields[0]) != result["pid"]:
            return result
        observed_start = datetime.strptime(" ".join(fields[2:7]), "%a %b %d %H:%M:%S %Y")
        expected_start = datetime.fromisoformat(receipt["started_utc"])
        difference = abs(
            (observed_start.replace(tzinfo=timezone.utc) - expected_start).total_seconds()
        )
        # ps rounds to seconds; the receipt is written just after Popen returns.
        if difference > 5 or Path(fields[7]).name != "codex":
            return {**result, "status": "identity_mismatch"}
        return {**result, "status": "zombie" if "Z" in fields[1] else "alive"}
    except (OSError, ValueError, KeyError, TypeError):
        return result


def live_observation(output, events, resources, checked_at, probe):
    receipt_path = output / "process.json"
    health = probe(read(receipt_path)) if receipt_path.exists() else {"status": "unconfirmed"}
    terminal = next(
        (
            r["event"]["type"]
            for r in reversed(events)
            if r["event"].get("type") in {"turn.completed", "turn.failed"}
        ),
        None,
    )
    observation = {"process": health, "public_terminal_event": terminal}
    for label, records in (("resource_sample", resources), ("public_event", events)):
        stamp = records[-1].get("utc") if records else None
        observation[f"last_{label}_utc"] = stamp
        observation[f"{label}_age_seconds"] = (
            max(0, (checked_at - datetime.fromisoformat(stamp)).total_seconds()) if stamp else None
        )
    if health["status"] == "alive":
        state = "finalizing" if terminal else "running"
    elif health["status"] in {"exited", "zombie", "identity_mismatch"}:
        state = "awaiting_terminal_receipt"
    else:
        state = "unconfirmed"
    return state, observation


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


def summarize(cohort=None, probe=process_health, checked_at=None):
    cohort = cohort if cohort is not None else HERE / "v2"
    checked_at = checked_at or datetime.now(timezone.utc)
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
            "live_observation": None,
            "process_outcome": None,
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
                process_outcome="complete" if terminal["process_success"] else "failed",
                started_utc=terminal["started_utc"],
                ended_utc=terminal["ended_utc"],
                wall_seconds=terminal["wall_seconds"],
                usage=terminal["usage"],
                call_receipt_sha256=sha(output / "call.json"),
                native_memory=terminal["native_memory"],
                protected_inputs_unchanged=terminal["protected_inputs_unchanged"],
                package_members_unchanged=terminal["package_members_unchanged"],
            )
        transfer = None
        skipped_path = output / "skipped.json"
        if skipped_path.exists():
            marker = read(skipped_path)
            if marker.get("reason") == "transferred_to_parallel_v1":
                transfer = marker
        row["scheduler_transfer"] = transfer
        if terminal:
            row["scheduler_regime"] = terminal.get("scheduler_regime", "original-three-worker")
        elif (output / "call.started.json").exists():
            row["scheduler_regime"] = read(output / "call.started.json").get(
                "scheduler_regime", "original-three-worker"
            )
        else:
            row["scheduler_regime"] = "parallel-v1" if transfer else None
        # A post-call snapshot/cleanup failure can coexist with a successful call.
        # Keep both facts and all reported usage instead of masking the failure.
        if (output / "harness-failure.json").exists():
            row.update(state="harness_failed", failure=read(output / "harness-failure.json"))
        elif not terminal and skipped_path.exists() and transfer is None:
            row.update(state="skipped", failure=read(output / "skipped.json"))
        elif not terminal and (output / "call.started.json").exists():
            state, observation = live_observation(output, events, resources, checked_at, probe)
            row.update(
                state=state,
                started_utc=read(output / "call.started.json")["started_utc"],
                live_observation=observation,
            )
            if resources:
                row["latest_observed_elapsed_seconds"] = resources[-1]["elapsed_seconds"]
        if row["started_utc"] is None and (output / "call.started.json").exists():
            row["started_utc"] = read(output / "call.started.json")["started_utc"]
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
        "view_generated_utc": checked_at.isoformat(),
        "active_manifest_sha256": sha(cohort / "manifest.json"),
        "intended_cells": len(manifest["cells"]),
        "state_counts": dict(Counter(r["state"] for r in rows)),
        "attention_cells": [
            {"id": r["id"], "state": r["state"]}
            for r in rows
            if r["state"]
            in {"awaiting_terminal_receipt", "unconfirmed", "harness_failed", "failed", "skipped"}
        ],
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
            "A complete process is not independent artifact qualification.",
            "PID checks are local observations, not backend progress evidence.",
            "Quiet public events do not establish a stall or authorize interruption.",
            "Awaiting receipts may be transient finalization; never auto-rerun a cell.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = summarize()
    if args.output:
        args.output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {k: value[k] for k in ("state_counts", "attention_cells", "usage_totals")}, indent=2
        )
    )
