"""Run the frozen synthetic v1.5 pilot in disposable Codex homes.

Only privacy-safe receipts are persisted. Raw JSONL, prompts, tool text, and
session data live in TemporaryDirectory and are removed after each cell.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FREEZE = Path(__file__).with_name("pilot-execution-freeze.json")
AUTH = Path.home() / ".codex" / "auth.json"


def digest(value: str | bytes) -> str:
    payload = value.encode() if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def read_events(stdout: str) -> tuple[list[dict[str, Any]], int]:
    events = []
    malformed = 0
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(value, dict):
            events.append(value)
    return events, malformed


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    tool_events: list[dict[str, Any]] = []
    usage: dict[str, int | None] = {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "reasoning_output_tokens": None,
    }
    thread_id = None
    final_message = ""
    error_types = []
    for event in events:
        event_type = event.get("type")
        if event_type == "thread.started":
            thread_id = event.get("thread_id")
        if event_type == "turn.completed":
            reported = event.get("usage") or {}
            for key in usage:
                if isinstance(reported.get(key), int):
                    usage[key] = reported[key]
        if event_type in {"turn.failed", "error"}:
            error_types.append(event_type)
        item = event.get("item") or {}
        if event_type == "item.completed" and item.get("type") == "agent_message":
            final_message = item.get("text") or final_message
        if event_type == "item.completed" and item.get("type") in {
            "command_execution",
            "file_change",
            "mcp_tool_call",
            "web_search",
        }:
            raw_command = item.get("command") or item.get("name") or ""
            tool_events.append(
                {
                    "type": item.get("type"),
                    "command_sha256": digest(raw_command) if raw_command else None,
                    "exit_code": item.get("exit_code"),
                    "status": item.get("status"),
                    "retrieval": bool(re.search(r"\b(rg|grep|find|cat|sed|ls)\b", raw_command)),
                    "policy_call": "opensocrates" in raw_command
                    or "assistance codex" in raw_command,
                }
            )
    return {
        "thread_id": thread_id,
        "usage": usage,
        "tool_events": tool_events,
        "tool_calls": len(tool_events),
        "retrieval_calls": sum(bool(event["retrieval"]) for event in tool_events),
        "policy_calls": sum(bool(event["policy_call"]) for event in tool_events),
        "error_types": error_types,
        "final_message_sha256": digest(final_message) if final_message else None,
        "final_message": final_message,
    }


def call_codex(
    freeze: dict[str, Any],
    fixture: Path,
    codex_home: Path,
    model: str,
    prompt: str,
    *,
    resume: bool = False,
) -> dict[str, Any]:
    client = freeze["client_path"]
    prefix = [client, "exec"]
    if resume:
        prefix.append("resume")
        prefix.append("--last")
        prefix.append("--skip-git-repo-check")
        prefix.extend(["-c", "sandbox_mode=workspace-write"])
    else:
        prefix += ["--sandbox", "workspace-write", "--skip-git-repo-check", "-C", str(fixture)]
    command = prefix + [
        "--json",
        "--ignore-user-config",
        "--disable",
        "hooks",
        "-m",
        model,
        "-c",
        "model_reasoning_effort=medium",
        "-",
    ]
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    started = time.monotonic()
    timed_out = False
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=fixture,
            env=env,
            timeout=freeze["limits"]["per_call_wall_seconds"],
            check=False,
        )
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (
            (exc.stdout or b"").decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            (exc.stderr or b"").decode(errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
    elapsed = round(time.monotonic() - started, 3)
    events, malformed = read_events(stdout)
    summary = summarize_events(events)
    final_message = summary.pop("final_message")
    return {
        "client": freeze["client_version"],
        "model": model,
        "effort": "medium",
        "stage": "followup" if resume else "initial",
        "prompt_sha256": digest(prompt),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "wall_seconds": elapsed,
        "event_count": len(events),
        "malformed_event_lines": malformed,
        "stderr_sha256": digest(stderr) if stderr else None,
        "failure": timed_out or exit_code != 0 or bool(summary["error_types"]),
        **summary,
        "side_question_observation": side_question_observation(final_message),
    }


def side_question_observation(message: str) -> dict[str, Any]:
    """Text-only heuristic, explicitly not a human dialogue score."""
    lowered = message.lower()
    rejects_proof = bool(
        re.search(
            r"not prove|doesn.t prove|cannot prove|does not guarantee|아니|증명하지|보장하지",
            lowered,
        )
    )
    rejects_inaccessible = bool(
        re.search(r"not acceptable|cannot|not sufficient|아니|안 됩니다|충족하지", lowered)
    )
    return {
        "rejects_proof_heuristic": rejects_proof,
        "rejects_inaccessible_heuristic": rejects_inaccessible,
    }


def make_prompt(
    freeze: dict[str, Any], task: dict[str, Any], intervention: str, language: str
) -> str:
    segments = [freeze["intervention"]["common"]]
    if intervention in {"guides", "adaptive"}:
        for name in freeze["intervention"]["guidance_files"]:
            content = (ROOT / name).read_text(encoding="utf-8")
            segments.append(f"Reference guide {Path(name).name}:\n{content}")
    if intervention == "adaptive":
        segments.append(freeze["intervention"]["adaptive_wrapper"])
    segments.append(task.get(f"request_{language}") or task["request_en"])
    return "\n\n".join(segments)


def python_result(fixture: Path, expression: str) -> bool:
    code = f"import sys;sys.path.insert(0,{str(fixture)!r});{expression}"
    try:
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            cwd=fixture,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def checks_for(task_id: str, fixture: Path, stage: str) -> dict[str, bool]:  # noqa: C901  # Frozen rubric branches stay explicit.
    if task_id == "coding":
        source = (fixture / "names.py").read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
            safe = next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "safe_display_name"
            )
            reuse = "clean_name" in {
                node.id for node in ast.walk(safe) if isinstance(node, ast.Name)
            }
        except (SyntaxError, StopIteration):
            reuse = False
        return {
            "safe_none": python_result(
                fixture,
                "from names import safe_display_name;assert safe_display_name(None)=='Guest'",
            ),
            "safe_blank": python_result(
                fixture,
                "from names import safe_display_name;assert safe_display_name('  ')== 'Guest'",
            ),
            "safe_normal": python_result(
                fixture,
                "from names import safe_display_name;assert safe_display_name('  ada   lovelace ')== 'Ada Lovelace'",
            ),
            "existing_caller": python_result(
                fixture,
                "from names import display_name;assert display_name('  ada   lovelace ')== 'Ada Lovelace'",
            ),
            "reuse_helper": reuse,
        }
    if task_id == "planning":
        try:
            plan = json.loads((fixture / "plan.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            plan = {}
        if not isinstance(plan, dict):
            plan = {}
        action = str(plan.get("next_booking_action", "")).lower()
        return {
            "venue_A": plan.get("venue_id") == "A",
            "capacity_24": plan.get("capacity") == 24,
            "attendance_20": plan.get("expected_guests") == 20,
            "access": plan.get("step_free") is True,
            "quiet_room": plan.get("quiet_room") is True,
            "booking_action": bool(re.search("availab|가능|예약", action))
            and bool(re.search("step.free|access|접근|무장애", action)),
        }
    if task_id == "mechanical":
        return {
            "exact_file": (fixture / "README.md").read_text(encoding="utf-8")
            == "# Welcome Guide\n\nRead this note before starting.\n"
        }
    if task_id == "developer":
        expected = 99 if stage == "initial" else 100
        return {
            f"{stage}_behavior": python_result(
                fixture,
                f"from quote import discounted_quote;assert discounted_quote(100,10)=={expected}",
            ),
            "existing_caller": python_result(
                fixture, "from quote import quote;assert quote(100,10)==110"
            ),
        }
    if task_id == "nondeveloper":
        try:
            plan = json.loads((fixture / "plan.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            plan = {}
        if not isinstance(plan, dict):
            plan = {}
        if stage == "initial":
            return {
                "initial_holds": plan.get("venue_id") is None
                or str(plan.get("venue_id", "")).lower() in {"none", "unresolved", "hold"}
            }
        action = str(plan.get("next_booking_action", "")).lower()
        accessibility = plan.get("accessibility")
        if isinstance(accessibility, dict):
            access_met = accessibility.get("step_free") is True
        elif isinstance(accessibility, (str, bool)):
            access_met = accessibility in {True, "step-free", "step_free", "accessible"}
        else:
            access_met = False
        return {
            "corrected_venue_A": plan.get("venue_id") == "A",
            "corrected_attendance_20": plan.get("expected_guests") == 20,
            "accessibility": access_met,
            "booking_action": bool(re.search("availab|가능|예약", action))
            and bool(re.search("step.free|access|접근|무장애", action)),
        }
    raise ValueError(task_id)


def run_cell(
    freeze: dict[str, Any], lane: str, task_id: str, arm: dict[str, str], language: str
) -> dict[str, Any]:
    task = freeze["tasks"][task_id]
    with tempfile.TemporaryDirectory(prefix="os-v15-pilot-") as temp:
        base = Path(temp)
        fixture = base / "fixture"
        fixture.mkdir()
        home = base / "codex-home"
        home.mkdir()
        (home / "auth.json").symlink_to(AUTH)
        for filename, content in task["files"].items():
            (fixture / filename).write_text(content, encoding="utf-8")
        before_hashes = {name: digest(content) for name, content in task["files"].items()}
        prompt = make_prompt(freeze, task, arm["intervention"], language)
        calls = [call_codex(freeze, fixture, home, arm["model"], prompt)]
        initial_checks = checks_for(task_id, fixture, "initial")
        final_checks = initial_checks
        if lane == "EVAL-05":
            if "followup_source" in task:
                (fixture / "event.json").write_text(task["followup_source"], encoding="utf-8")
            followup = task[f"followup_{language}"]
            calls.append(call_codex(freeze, fixture, home, arm["model"], followup, resume=True))
            final_checks = checks_for(task_id, fixture, "followup")
        after_hashes = {
            path.name: digest(path.read_bytes())
            for path in fixture.iterdir()
            if path.is_file() and path.suffix in {".py", ".md", ".json"}
        }
        return {
            "lane": lane,
            "task": task_id,
            "language": language,
            "arm": arm["id"],
            "intervention": arm["intervention"],
            "source_hashes_before": before_hashes,
            "artifact_hashes_after": after_hashes,
            "calls": calls,
            "initial_checks": initial_checks,
            "final_checks": final_checks,
            "deterministic_success": all(final_checks.values())
            and all(not call["failure"] for call in calls),
            "manual_bilingual_dialogue_score": None,
            "manual_score_missing_reason": "No independent bilingual human reviewer assigned to this engineering pilot.",
            "repairs": [],
            "escalations": [],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", required=True, choices=["EVAL-02", "EVAL-03", "EVAL-05"])
    args = parser.parse_args()
    freeze_bytes = FREEZE.read_bytes()
    freeze = json.loads(freeze_bytes)
    if not AUTH.is_file():
        raise SystemExit("Existing ChatGPT auth file is unavailable")
    client = subprocess.run(
        [freeze["client_path"], "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if client != freeze["client_version"]:
        raise SystemExit(f"Client version drift: {client}")
    work = []
    spec = freeze["lanes"][args.lane]
    for task_id in spec["tasks"]:
        for language in spec.get("languages", ["en"]):
            for arm in spec["arms"]:
                work.append((task_id, arm, language))
    results = []
    with ThreadPoolExecutor(max_workers=freeze["limits"]["max_parallel_calls"]) as pool:
        futures = {pool.submit(run_cell, freeze, args.lane, *item): item for item in work}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "lane": args.lane,
                    "task": item[0],
                    "arm": item[1]["id"],
                    "language": item[2],
                    "runner_failure": type(exc).__name__,
                    "deterministic_success": False,
                }
            results.append(result)
            print(
                f"{args.lane} {result['task']} {result['language']} {result['arm']}: {result['deterministic_success']}",
                flush=True,
            )
    results.sort(key=lambda row: (row["task"], row["language"], row["arm"]))
    output = {
        "schema": "opensocrates.v1.5.pilot-results/1.0.0",
        "lane": args.lane,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_commit": "72e054b3fdfd7e162dacd777ef2b68fdbb3ae177",
        "freeze_sha256": digest(freeze_bytes),
        "client": client,
        "held_out": False,
        "validated_profile": False,
        "installed_plugin_activation": False,
        "cells": results,
    }
    path = FREEZE.parent / "results" / f"{args.lane.lower()}-pilot.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
