#!/usr/bin/env python3
"""Run one frozen, disposable EVAL-04 pilot cell with exact CLI receipts."""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
FREEZE = Path(__file__).with_name("memory-pilot-freeze.json")
CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
AUTH = Path.home() / ".codex" / "auth.json"


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _request(
    operation: str,
    payload: dict[str, Any],
    project_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": "opensocrates.project-memory.request/1.0.0",
        "operation": operation,
        "request_id": str(uuid4()),
        "project_id": project_id,
        "workspace_id": workspace_id,
        "task_id": None,
        "payload": payload,
    }


def _enroll_memory(workspace: Path, data: Path, intent: str) -> tuple[str, str]:
    sys.path.insert(0, str(ROOT / "src"))
    from opensocrates.project_memory.registry import ProjectRegistry
    from opensocrates.project_memory.service import handle_memory

    registry = ProjectRegistry(data)

    def call(
        operation: str,
        payload: dict[str, Any],
        project: str | None = None,
        worktree: str | None = None,
    ) -> dict[str, Any]:
        answer = handle_memory(_request(operation, payload, project, worktree), registry=registry)
        if answer["status"] != "ok":
            raise RuntimeError(
                f"memory setup {operation}: {answer['status']} {answer['limitations']}"
            )
        return answer["result"]

    policy = {
        "root": str(workspace),
        "apply": False,
        "mode": "read_write",
        "capture_policy": "milestones",
        "excluded_paths": [],
    }
    preview = call("init", policy)
    policy.update(
        {
            "apply": True,
            "disclosure_digest": preview["disclosure_digest"],
            "authorization_basis": "fixture:eval04-enrollment",
            "authorization_attribution": "operator_declared",
            "idempotency_key": str(uuid4()),
        }
    )
    enrollment = call("init", policy)
    project, worktree = enrollment["project_id"], enrollment["workspace_id"]
    created = call(
        "record",
        {
            "idempotency_key": str(uuid4()),
            "expected_record_version": 0,
            "kind": "decision",
            "scope": {"level": "project"},
            "summary": intent,
            "origin": {
                "producer_kind": "agent",
                "source_reference": None,
                "attestation": "agent_reported",
            },
            "support": "agent_reported",
            "source_refs": [],
            "revalidation": {
                "dependency_paths": [],
                "negative_claim": False,
                "on_change": "not_applicable",
            },
        },
        project,
        worktree,
    )
    call(
        "accept",
        {
            "record_id": created["record"]["record_id"],
            "expected_record_version": 1,
            "idempotency_key": str(uuid4()),
            "acceptance_basis": "fixture:eval04-accepted-intent",
            "acceptance_attribution": "operator_declared",
        },
        project,
        worktree,
    )
    return project, worktree


def _events(raw: bytes) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    invalid = 0
    for line in raw.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            invalid += 1
            continue
        if isinstance(value, dict):
            events.append(value)
    usage = next(
        (event.get("usage") for event in reversed(events) if event.get("type") == "turn.completed"),
        None,
    )
    messages = [
        event.get("item", {}).get("text", "")
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    ]
    commands = [
        event.get("item", {})
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "command_execution"
    ]
    memory_calls = [item for item in commands if "launch.sh memory" in item.get("command", "")]
    return {
        "event_count": len(events),
        "invalid_event_lines": invalid,
        "turn_completed": any(item.get("type") == "turn.completed" for item in events),
        "usage": usage,
        "final_answer": messages[-1] if messages else None,
        "tool_commands": len(commands),
        "failed_tool_commands": sum(item.get("exit_code") not in {0, None} for item in commands),
        "memory_calls": len(memory_calls),
        "successful_memory_calls": sum(item.get("exit_code") == 0 for item in memory_calls),
    }


def _grade(fixture_id: str, workspace: Path) -> dict[str, Any]:
    if fixture_id == "general-event-correction":
        value = (workspace / "plan.md").read_text().casefold()
        return {
            "capacity_24": "24" in value,
            "attendance_20": "20" in value,
            "step_free": "step-free" in value or "wheelchair" in value,
            "booking_action": any(word in value for word in ("book", "hold", "contact", "reserve")),
        }
    if fixture_id == "research-evidence-revision":
        value = (workspace / "finding.md").read_text().casefold()
        return {
            "new_birch_source": "birch" in value and "2026-03" in value,
            "prior_cedar_uncertainty": "cedar" in value
            and any(word in value for word in ("small", "bias", "uncertain", "provisional")),
            "finding_updated": "source c" in value or "2026-03" in value,
        }
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workspace)
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            "from api import public_key; from cli import command_tag; "
            "assert public_key(' Quick Start ') == 'quick-start'; "
            "assert command_tag(' Quick\\t  Start ') == 'quick-start'",
        ],
        cwd=workspace,
        env=env,
        capture_output=True,
        timeout=10,
        check=False,
    )
    source = (workspace / "helper.py").read_text()
    return {
        "hidden_behavior": check.returncode == 0,
        "one_normalizer": sum(
            path.read_text().count("def normalize_label") for path in workspace.glob("*.py")
        )
        == 1,
        "helper_changed": 'split(" "' not in source,
    }


def run(fixture_id: str, arm: str, output_root: Path | None) -> Path:  # noqa: C901  # The frozen cell setup stays explicit for audit.
    freeze = json.loads(FREEZE.read_text())
    assert freeze["status"] == "frozen_before_outcomes_partial_pilot"
    assert _digest(CODEX) == freeze["client"]["sha256"]
    fixture = next(
        item for item in freeze["lanes"]["EVAL-04"]["fixtures"] if item["id"] == fixture_id
    )
    base = output_root or Path(tempfile.mkdtemp(prefix="opensocrates-eval04-", dir="/private/tmp"))
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile, workspace, data = (base / name for name in ("codex-home", "workspace", "data"))
    for path in (profile, workspace, data):
        path.mkdir(mode=0o700)
    shutil.copyfile(AUTH, profile / "auth.json")
    (profile / "auth.json").chmod(0o600)
    atexit.register(lambda: (profile / "auth.json").unlink(missing_ok=True))
    for name, content in fixture["initial_files"].items():
        (workspace / name).write_text(content)
    if fixture["workspace_kind"] == "git_worktree":
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "initial",
            ],
            check=True,
        )
    if arm == "maintained visible project note":
        (workspace / "PROJECT_NOTES.md").write_text(fixture["visible_note"] + "\n")
    project_id = workspace_id = None
    environment = dict(os.environ)
    environment["CODEX_HOME"] = str(profile)
    if arm == "v1.5 memory enabled":
        environment["CODEX_BIN"] = str(CODEX)
        install = subprocess.run(
            [
                "node",
                str(ROOT / "installer/opensocrates.mjs"),
                "install",
                "--host",
                "codex",
                "--asset",
                str(ROOT / "dist/opensocrates-1.4.0-codex-plugin.zip"),
                "--checksum",
                str(ROOT / "dist/opensocrates-1.4.0-checksums.sha256"),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if install.returncode:
            raise RuntimeError(f"disposable plugin install failed: {install.returncode}")
        project_id, workspace_id = _enroll_memory(workspace, data, fixture["accepted_intent"])
        environment.update(
            {
                "OPENSOCRATES_MEMORY_FIXTURE": "1",
                "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                "OPENSOCRATES_DATA_DIR": str(data),
            }
        )
    # Apply the predeclared source change only after note/memory state is frozen.
    for name, content in fixture["transition"].items():
        (workspace / name).write_text(content)
    prompt = (
        fixture["followup_request"] + " Work only in this disposable project. "
        "Read current files, update the relevant artifact, and run a focused check. "
        "Do not use prior conversations or account memory."
    )
    if arm == "maintained visible project note":
        prompt += " Consult the maintained PROJECT_NOTES.md before acting."
    if arm == "v1.5 memory enabled":
        prompt += (
            " Use the installed $opensocrates skill and explicitly recall the enrolled "
            f"project_id={project_id} workspace_id={workspace_id} with task_id null, "
            "a need about the current task, and budget_bytes 8192. Current files govern "
            "observed facts; accepted memory is scoped intent."
        )
    command = [str(CODEX), "--disable", "hooks"]
    if arm != "v1.5 memory enabled":
        command += ["--disable", "plugins"]
    command += [
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "-C",
        str(workspace),
        "-s",
        "workspace-write",
        "-m",
        "gpt-6-sol",
        "-c",
        'model_reasoning_effort="medium"',
        "-c",
        "features.external_agent_memory_import=false",
    ]
    if arm != "v1.5 memory enabled":
        command += ["--ignore-user-config"]
    else:
        command += ["--add-dir", str(data)]
    command += [prompt]
    start = time.perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            command, cwd=workspace, env=environment, capture_output=True, timeout=1800, check=False
        )
        raw, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        raw, stderr, exit_code = error.stdout or b"", error.stderr or b"", None
    wall = time.perf_counter() - start
    (base / "events.jsonl").write_bytes(raw)
    (base / "stderr.txt").write_bytes(stderr)
    events = _events(raw)
    grade = _grade(fixture_id, workspace)
    result = {
        "schema": "opensocrates.v1.5.memory-pilot-cell/1.0.0",
        "lane": "EVAL-04",
        "fixture": fixture_id,
        "arm": arm,
        "freeze_sha256": _digest(FREEZE),
        "source_commit": freeze["source_commit"],
        "client_version": freeze["client"]["version"],
        "client_sha256": _digest(CODEX),
        "model": "gpt-6-sol",
        "effort": "medium",
        "exit_code": exit_code,
        "timed_out": timed_out,
        "wall_seconds": round(wall, 3),
        "project_id_fixture_only": project_id is not None,
        "native_profile_initial_state": "new CODEX_HOME with auth only; --ephemeral; import flag disabled",
        "server_side_memory_isolation": "unverified",
        "events": {key: value for key, value in events.items() if key != "final_answer"},
        "answer_sha256": hashlib.sha256((events["final_answer"] or "").encode()).hexdigest(),
        "grade": grade,
        "all_gates_pass": bool(grade) and all(grade.values()),
        "raw_event_path": str(base / "events.jsonl"),
        "stderr_path": str(base / "stderr.txt"),
        "claim_boundary": "partial engineering pilot, no model-quality or memory-effect claim",
    }
    (base / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        choices=[
            "general-event-correction",
            "research-evidence-revision",
            "coding-untracked-caller",
        ],
        required=True,
    )
    parser.add_argument(
        "--arm",
        choices=["memory disabled", "v1.5 memory enabled", "maintained visible project note"],
        required=True,
    )
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    print(run(args.fixture, args.arm, args.output_root))


if __name__ == "__main__":
    main()
