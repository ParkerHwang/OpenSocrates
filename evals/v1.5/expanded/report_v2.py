"""Verify fixed pilot records and build blinded synthetic artifact packets."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

from harness_v3 import HERE, ROOT, USAGE_KEYS, digest, save_new


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def evidence_freeze() -> tuple[dict, str]:
    """Offline evidence verification does not require the old client/account."""
    path = HERE / "execution-freeze.v2.json"
    relative = str(path.relative_to(ROOT))
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    assert committed == path.read_bytes()
    freeze = json.loads(committed)
    for name, expected in freeze["file_hashes"].items():
        assert digest((ROOT / name).read_bytes()) == expected, name
    inventory = HERE / "result-inventory.v2.json"
    if inventory.exists():
        for name, expected in read(inventory).items():
            assert digest((HERE / name).read_bytes()) == expected, name
    commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", relative], cwd=ROOT, text=True
    ).strip()
    return freeze, commit


def blinded(text: str) -> str:
    text = re.sub(
        r"(?m)^.*OpenSocrates grounding:.*$", "[Treatment audit line removed for review.]", text
    )
    text = re.sub(r"(?i)gpt-6-(?:luna|sol|astra)|opensocrates", "[treatment label removed]", text)
    return text


def build(*, write: bool = False) -> dict:  # noqa: C901
    freeze, freeze_commit = evidence_freeze()
    tasks = {task["id"]: task for task in read(HERE / "fixtures.v2.json")["tasks"]}
    host = read(HERE / "host-fixture.v2.json")
    tasks[host["id"]] = host
    groups = defaultdict(list)
    source_groups = defaultdict(set)
    cells, packets, missing = [], [], []
    for scheduled in freeze["cells"]:
        directory = HERE / "results-v2" / scheduled["id"]
        path = directory / "result.json"
        if not path.exists():
            missing.append(scheduled["id"])
            continue
        result = read(path)
        assert result["cell"] == scheduled
        calls = [read(directory / name) for name in result["calls"]]
        starts = list(directory.glob("turn-*.started.json"))
        assert len(starts) == len(calls), f"Unfinished call: {scheduled['id']}"
        for call in calls:
            assert call["requested_model"] == scheduled["model"]
            assert call["requested_effort"] == "medium"
            assert call["billed_cost"] is None and call["server_echoed_model"] is None
            assert call["tool_actions_started_or_completed"] == len(call["tool_actions"])
            for value in call["usage"].values():
                assert value is None or (type(value) is int and value >= 0)
        for started in directory.glob("*.started.json"):
            if started.name != "cell.started.json":
                assert started.with_name(started.name.replace(".started.json", ".json")).exists(), (
                    started
                )
        task = tasks[result["task"]]
        source_groups[task["id"]].add(
            json.dumps(result.get("source_hashes_before_call"), sort_keys=True)
        )
        total_usage = {}
        missing_usage = {}
        for key in USAGE_KEYS:
            values = [call["usage"].get(key) for call in calls]
            missing_usage[key] = sum(value is None for value in values)
            total_usage[key] = (
                sum(values) if values and all(value is not None for value in values) else None
            )
        entry = {
            "id": scheduled["id"],
            "lane": task["lane"],
            "task": task["id"],
            "locale": task["locale"],
            "arm": scheduled["arm"],
            "model": scheduled["model"],
            "repetition": scheduled["repetition"],
            "attempted_calls": len(starts),
            "completed_processes": sum(call["process_success"] for call in calls),
            "deterministic_success": result["deterministic_success"],
            "grade": result.get("grade"),
            "wall_turn_seconds": round(sum(call["wall_seconds"] for call in calls), 3),
            "wall_with_setup_seconds": result["wall_including_setup_seconds"],
            "usage": total_usage,
            "missing_usage_fields": missing_usage,
            "tool_actions": sum(call["tool_actions_started_or_completed"] for call in calls),
            "failed_tool_actions": sum(call["failed_tool_actions"] for call in calls),
            "protocol_rejections": sum(call.get("protocol_rejections", 0) for call in calls),
            "direct_memory_command_lower_bound": sum(
                call["direct_operations_lexical"].get("memory", 0) for call in calls
            ),
            "actual_memory_api_invocations": None,
            "actual_policy_invocations": None,
            "count_limit": "Direct command classifier cannot resolve arbitrary indirect Python/shell calls; actual totals remain null.",
            "human_quality_scores": None,
            "model_judge_scores": None,
            "native_tables": result["native_tables"],
            "runner_error": result.get("runner_error"),
        }
        cells.append(entry)
        groups[(task["lane"], task["id"], scheduled["arm"])].append(entry)
        opaque = digest(str(freeze["judging"]["blinding_seed"]) + scheduled["id"])[:16]
        seed_files = {**task["files"], **(task.get("replay_files") or {})}
        before = (
            {**seed_files, **(task["source_transition"] or {})}
            if task["lane"] in {"EVAL-01", "EVAL-04"}
            else seed_files
        )
        stages = [read(directory / name) for name in result["stages"]]
        for stage in stages:
            stage["public_final"] = blinded(stage["public_final"])
        patches = {}
        if stages:
            for name, final in stages[-1]["artifacts"].items():
                if final is not None:
                    patches[name] = "".join(
                        difflib.unified_diff(
                            before.get(name, "").splitlines(True),
                            final.splitlines(True),
                            fromfile="before/" + name,
                            tofile="after/" + name,
                        )
                    )
        packet = {
            "packet_id": opaque,
            "task_id": task["id"],
            "locale": task["locale"],
            "initial_request": task["prompt"],
            "followup_request": task["followup_prompt"],
            "source_before_task": before,
            "declared_source_transition": task["source_transition"],
            "scoped_public_intent": task["accepted_decision"]
            if scheduled.get("memory") or scheduled.get("note")
            else None,
            "stages": stages,
            "designated_artifact_diffs": patches,
            "human_status": "unavailable",
            "human_scores": None,
            "non_blindable_cues": [
                "Memory/note references and characteristic wording may reveal condition; complete blinding is not guaranteed."
            ],
            "coverage_limit": "Packets contain declared task sources and designated output artifacts, not a complete post-run filesystem snapshot or raw tool transcript.",
        }
        packets.append(
            {
                "packet_id": opaque,
                "cell_id": scheduled["id"],
                "packet_sha256": digest(json.dumps(packet, sort_keys=True, ensure_ascii=False)),
            }
        )
        if write:
            save_new(HERE / "blinded-v2" / f"{opaque}.json", packet)
            save_new(
                HERE / "judge-evidence-v2" / f"{opaque}.json",
                {
                    "packet_id": opaque,
                    "deterministic_checks": result.get("grade"),
                    "tool_actions": entry["tool_actions"],
                    "failed_tool_actions": entry["failed_tool_actions"],
                    "wall_seconds": entry["wall_turn_seconds"],
                    "review_order": "Show only after independent code/artifact first read; human scores missing",
                },
            )
    assert all(len(values) == 1 for values in source_groups.values()), (
        "Paired starting-source drift"
    )
    summaries = []
    for (lane, task, arm), entries in sorted(groups.items()):
        wall = [row["wall_turn_seconds"] for row in entries]
        summaries.append(
            {
                "lane": lane,
                "task": task,
                "arm": arm,
                "n": len(entries),
                "deterministic_pass": sum(row["deterministic_success"] for row in entries),
                "wall_mean": round(statistics.mean(wall), 3),
                "wall_sample_sd": round(statistics.stdev(wall), 3) if len(wall) > 1 else None,
                "wall_min": min(wall),
                "wall_max": max(wall),
            }
        )
    output = {
        "schema": "opensocrates.v1.5.expanded-results/2.0.0",
        "freeze_commit": freeze_commit,
        "freeze_sha256": digest((HERE / "execution-freeze.v2.json").read_bytes()),
        "held_out": False,
        "scheduled_cells": len(freeze["cells"]),
        "completed_cells": len(cells),
        "missing_cells": missing,
        "attempted_model_calls": sum(row["attempted_calls"] for row in cells),
        "successful_cli_processes": sum(row["completed_processes"] for row in cells),
        "quality_pilot_cells": sum(row["lane"] != "H02" for row in cells),
        "quality_pilot_deterministic_pass": sum(
            row["deterministic_success"] for row in cells if row["lane"] != "H02"
        ),
        "H02_artifact_pass": sum(
            row["deterministic_success"] for row in cells if row["lane"] == "H02"
        ),
        "human_review_count": 0,
        "model_judge_count": 0,
        "cells": cells,
        "descriptive_repetition_variance": summaries,
        "limits": [
            "Two repetitions per authored task; no independent human quality distribution.",
            "Memory effects confounded by unverified account-side isolation.",
            "Billed cost, backend model echo, universal native application receipt unavailable.",
            "Direct command counts are lower bounds, not complete policy/retrieval counts.",
            "No validated profile, held-out outcome, quality/noninferiority or savings claim.",
        ],
    }
    if write:
        assert not missing, "Do not finalize a partial matrix"
        save_new(HERE / "unblinding-v2.json", packets)
        save_new(HERE / "summary.v2.json", output)
        inventory = {
            str(path.relative_to(HERE)): digest(path.read_bytes())
            for path in sorted((HERE / "results-v2").rglob("*.json"))
        }
        save_new(HERE / "result-inventory.v2.json", inventory)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    result = build(write=arguments.write)
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"cells", "descriptive_repetition_variance"}
            },
            indent=2,
        )
    )
