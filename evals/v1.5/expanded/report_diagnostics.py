"""Offline integrity checks and blinded packets for every diagnostic attempt."""

from __future__ import annotations

import argparse
import json
import subprocess

from harness_v4 import HERE, ROOT, USAGE_KEYS, digest, save_new
from report_v2 import blinded, read


def build(write: bool = False) -> dict:
    rows, joins = [], []
    for version in (3, 4, 5):
        freeze_path = HERE / f"diagnostic-freeze.v{version}.json"
        relative = str(freeze_path.relative_to(ROOT))
        assert (
            subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
            == freeze_path.read_bytes()
        )
        freeze = read(freeze_path)
        for name, expected in freeze["file_hashes"].items():
            assert digest((ROOT / name).read_bytes()) == expected, name
        for scheduled in freeze["cells"]:
            directory = HERE / f"diagnostic-results-v{version}" / scheduled["id"]
            result = read(directory / "result.json")
            assert result["cell"] == scheduled
            calls = [read(directory / name) for name in result["calls"]]
            assert len(calls) == len(list(directory.glob("turn-*.started.json")))
            for call in calls:
                assert (
                    call["requested_model"] == "gpt-6-sol" and call["requested_effort"] == "medium"
                )
                assert call["billed_cost"] is None and call["server_echoed_model"] is None
            row = {
                "id": scheduled["id"],
                "version": version,
                "kind": scheduled["kind"],
                "locale": scheduled["locale"],
                "calls": len(calls),
                "cli_exit_zero": sum(call["exit_code"] == 0 for call in calls),
                "instrumentation_errors": [
                    call["invocation_error"] for call in calls if call.get("invocation_error")
                ],
                "artifact_pass": result.get("artifact_pass"),
                "memory_forgetting_verified": result.get("memory_forgetting_verified"),
                "strict_diagnostic_pass": result["diagnostic_pass"],
                "original_strict_check": result.get("original_strict_check"),
                "question_any_public_message_heuristic": result.get(
                    "question_in_any_public_message_heuristic"
                ),
                "wall_seconds": round(sum(call["wall_seconds"] for call in calls), 3),
                "usage": {
                    key: sum(call["usage"][key] for call in calls)
                    if all(call["usage"].get(key) is not None for call in calls)
                    else None
                    for key in USAGE_KEYS
                },
                "missing_usage_calls": sum(call["usage"]["input_tokens"] is None for call in calls),
                "tool_actions": None
                if any(call.get("invocation_error") for call in calls)
                else sum(call["tool_actions_started_or_completed"] for call in calls),
                "native_tables": result["native_tables"],
                "human_scores": None,
            }
            rows.append(row)
            opaque = digest(str(freeze["judging"]["blinding_seed"]) + scheduled["id"])[:16]
            task = freeze["tasks"][scheduled["task"]]
            packet = {
                "packet_id": opaque,
                "task_kind": scheduled["kind"],
                "locale": scheduled["locale"],
                "task_requests": task["prompts"],
                "source_before": {**task["files"], **task.get("replay_files", {})},
                "source_transition": task.get("source_transition"),
                "stages": [
                    {
                        "artifacts": read(directory / name)["artifacts"],
                        "public_final": blinded(read(directory / name)["public_final"]),
                    }
                    for name in result["stages"]
                ],
                "public_messages_by_turn": [
                    [blinded(text) for text in call.get("public_messages", [])]
                    if not call.get("invocation_error")
                    else None
                    for call in calls
                ],
                "message_missing_reason": "Parser failure; never interpret missing messages as no question or no tool work"
                if row["instrumentation_errors"]
                else None,
                "persisted_memory_observation": result.get("memory_postcheck"),
                "human_status": "unavailable",
                "human_scores": None,
                "non_blindable_cues": "Memory operations, retained intent and characteristic phrasing can reveal treatment; version/model labels removed",
            }
            joins.append(
                {
                    "packet_id": opaque,
                    "cell_id": scheduled["id"],
                    "packet_sha256": digest(json.dumps(packet, sort_keys=True, ensure_ascii=False)),
                }
            )
            if write:
                save_new(HERE / "blinded-diagnostics" / f"{opaque}.json", packet)
    output = {
        "schema": "opensocrates.v1.5.diagnostic-summary/1.0.0",
        "held_out": False,
        "cells": rows,
        "calls": sum(row["calls"] for row in rows),
        "missing_usage_calls": sum(row["missing_usage_calls"] for row in rows),
        "limits": [
            "V3/V4/V5 are separate conditions; failures are not replaced.",
            "V3 parser-failed zero event/action counts are missing observations, not actual zeros.",
            "V5 confirms two bounded persisted corrections; it does not establish reliable general quality or efficiency.",
            "No human or model-judge quality scores. Account-side isolation and billing remain unavailable.",
        ],
    }
    if write:
        save_new(HERE / "diagnostic-summary.json", output)
        save_new(HERE / "diagnostic-unblinding.json", joins)
        inventory = {
            str(path.relative_to(HERE)): digest(path.read_bytes())
            for version in (3, 4, 5)
            for path in sorted((HERE / f"diagnostic-results-v{version}").rglob("*.json"))
        }
        save_new(HERE / "diagnostic-result-inventory.json", inventory)
    elif (HERE / "diagnostic-result-inventory.json").exists():
        for name, expected in read(HERE / "diagnostic-result-inventory.json").items():
            assert digest((HERE / name).read_bytes()) == expected, name
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    result = build(parser.parse_args().write)
    print(json.dumps({key: value for key, value in result.items() if key != "cells"}, indent=2))
