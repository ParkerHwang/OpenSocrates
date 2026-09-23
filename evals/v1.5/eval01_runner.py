#!/usr/bin/env python3
"""Execute one frozen EVAL-01 naturalistic/replay pilot in disposable roots."""

from __future__ import annotations

import argparse
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

from memory_pilot_runner import AUTH, CODEX, ROOT, _digest, _enroll_memory, _events, _grade

FREEZE = Path(__file__).with_name("eval01-execution-freeze.json")
PARENT = Path(__file__).with_name("memory-pilot-freeze.json")


def _source_digest(workspace: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or ".git" in path.relative_to(workspace).parts:
            continue
        digest.update(str(path.relative_to(workspace)).encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _install(profile: Path, asset: Path, checksum: Path) -> None:
    environment = dict(os.environ)
    environment.update({"CODEX_HOME": str(profile), "CODEX_BIN": str(CODEX)})
    completed = subprocess.run(
        [
            "node",
            str(ROOT / "installer/opensocrates.mjs"),
            "install",
            "--host",
            "codex",
            "--asset",
            str(asset),
            "--checksum",
            str(checksum),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"disposable plugin install failed: {completed.returncode}")


def _session(
    base: Path,
    name: str,
    arm: str,
    workspace: Path,
    data: Path,
    prompt: str,
    project_id: str | None,
    workspace_id: str | None,
    released_asset: Path,
    released_checksum: Path,
) -> dict[str, Any]:
    profile = base / f"profile-{name}"
    profile.mkdir(mode=0o700)
    shutil.copyfile(AUTH, profile / "auth.json")
    (profile / "auth.json").chmod(0o600)
    try:
        if arm == "B":
            _install(profile, released_asset, released_checksum)
        elif arm in {"C", "D"}:
            _install(
                profile,
                ROOT / "dist/opensocrates-1.4.0-codex-plugin.zip",
                ROOT / "dist/opensocrates-1.4.0-checksums.sha256",
            )
        environment = dict(os.environ)
        environment["CODEX_HOME"] = str(profile)
        if arm == "D":
            environment.update(
                {
                    "OPENSOCRATES_MEMORY_FIXTURE": "1",
                    "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                    "OPENSOCRATES_DATA_DIR": str(data),
                }
            )
        full_prompt = prompt + (
            " Work only in this disposable repository. Inspect current files and run a focused "
            "behavior check. Do not use previous conversations or account memory."
        )
        if arm in {"B", "C", "D"}:
            full_prompt += " Use the installed $opensocrates skill."
        if arm == "D":
            full_prompt += (
                f" Explicitly recall enrolled project_id={project_id} workspace_id={workspace_id} "
                "with task_id null and budget_bytes 8192 before deciding. Current source "
                "governs observed behavior; memory is scoped accepted intent."
            )
        command = [str(CODEX), "--disable", "hooks"]
        if arm == "A":
            command += ["--disable", "plugins"]
        command += [
            "exec",
            "--json",
            "--ephemeral",
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
        if arm == "A":
            command += ["--ignore-user-config"]
        if arm == "D":
            command += ["--add-dir", str(data)]
        command += [full_prompt]
        start = time.perf_counter()
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=environment,
                capture_output=True,
                timeout=1800,
                check=False,
            )
            raw, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            raw, stderr, exit_code = error.stdout or b"", error.stderr or b"", None
        wall = round(time.perf_counter() - start, 3)
        events_path, stderr_path = base / f"{name}.jsonl", base / f"{name}.stderr"
        events_path.write_bytes(raw)
        stderr_path.write_bytes(stderr)
        events = _events(raw)
        return {
            "name": name,
            "arm": arm,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "wall_seconds": wall,
            "usage": events["usage"],
            "tool_commands": events["tool_commands"],
            "failed_tool_commands": events["failed_tool_commands"],
            "memory_calls": events["memory_calls"],
            "successful_memory_calls": events["successful_memory_calls"],
            "turn_completed": events["turn_completed"],
            "event_stream_sha256": _digest(events_path),
            "final_answer_sha256": "sha256:"
            + hashlib.sha256((events["final_answer"] or "").encode()).hexdigest(),
            "raw_event_path": str(events_path),
            "stderr_path": str(stderr_path),
        }
    finally:
        (profile / "auth.json").unlink(missing_ok=True)


def _first_grade(workspace: Path) -> dict[str, bool]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(workspace)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from api import public_key; assert public_key(' Quick Start ') == 'quick-start'",
        ],
        cwd=workspace,
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )
    count = sum(path.read_text().count("def normalize_label") for path in workspace.glob("*.py"))
    return {"api_behavior": completed.returncode == 0, "one_normalizer": count == 1}


def _join_existing_memory(workspace: Path, data: Path, project_id: str) -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from opensocrates.project_memory.registry import ProjectRegistry

    registry = ProjectRegistry(data)
    policy = {"mode": "read_write", "capture_policy": "milestones", "excluded_paths": []}
    preview = registry.preview(str(workspace), policy, 1, project_id)
    joined = registry.enroll(
        str(workspace),
        policy,
        preview["disclosure_digest"],
        "fixture:eval01-paired-join",
        "operator_declared",
        expected_policy_version=1,
        target_project_id=project_id,
        idempotency_key=str(uuid4()),
    )
    return str(joined["workspace_id"])


def _restore_source_artifact(source: Path, destination: Path) -> None:
    wanted = {
        path.relative_to(source)
        for path in source.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(source).parts
    }
    for path in destination.rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(destination).parts:
            if path.relative_to(destination) not in wanted:
                path.unlink()
    for relative in wanted:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)


def run(released_asset: Path, released_checksum: Path, output_root: Path | None) -> Path:  # noqa: C901  # Arm and replay state remain explicit.
    freeze = json.loads(FREEZE.read_text())
    parent = json.loads(PARENT.read_text())
    assert freeze["status"] == "frozen_before_outcomes"
    assert _digest(PARENT) == freeze["parent_freeze_sha256"]
    assert _digest(released_asset) == freeze["released_v14_asset_sha256"]
    assert (
        _digest(ROOT / "dist/opensocrates-1.4.0-codex-plugin.zip")
        == freeze["candidate_asset_sha256"]
    )
    assert _digest(CODEX) == parent["client"]["sha256"]
    fixture = parent["lanes"]["EVAL-01"]
    base = output_root or Path(tempfile.mkdtemp(prefix="opensocrates-eval01-", dir="/private/tmp"))
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    receipts: list[dict[str, Any]] = []
    first_artifacts: dict[str, Path] = {}
    d_project_id: str | None = None
    for arm in ("A", "B", "C", "D"):
        arm_root = base / arm
        workspace, data = arm_root / "workspace", arm_root / "data"
        workspace.mkdir(parents=True, mode=0o700)
        data.mkdir(mode=0o700)
        for name, content in fixture["initial_files"].items():
            (workspace / name).write_text(content)
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
        project_id = workspace_id = None
        if arm == "D":
            project_id, workspace_id = _enroll_memory(workspace, data, fixture["accepted_intent"])
            d_project_id = project_id
        first = _session(
            base,
            f"{arm}-first",
            arm,
            workspace,
            data,
            fixture["first_session_request"],
            project_id,
            workspace_id,
            released_asset,
            released_checksum,
        )
        first["grade"] = _first_grade(workspace)
        first["source_after_sha256"] = _source_digest(workspace)
        receipts.append(first)
        artifact = arm_root / "first-artifact"
        shutil.copytree(workspace, artifact)
        first_artifacts[arm] = artifact
        (workspace / fixture["source_transition"]["added_untracked_file"]).write_text(
            fixture["source_transition"]["content"]
        )
        second = _session(
            base,
            f"{arm}-followup",
            arm,
            workspace,
            data,
            fixture["followup_request"],
            project_id,
            workspace_id,
            released_asset,
            released_checksum,
        )
        second["grade"] = _grade("coding-untracked-caller", workspace)
        second["source_after_sha256"] = _source_digest(workspace)
        receipts.append(second)
    # Separate retrieval replay: linked worktrees share the exact D project store.
    replay_source_digest = _source_digest(first_artifacts["D"])
    assert d_project_id is not None
    original_d = base / "D" / "workspace"
    d_data = base / "D" / "data"
    for arm in ("C", "D"):
        pair_root = base / f"paired-{arm}"
        pair_root.mkdir(mode=0o700)
        workspace = pair_root / "workspace"
        subprocess.run(
            ["git", "-C", str(original_d), "worktree", "add", "-q", "--detach", str(workspace)],
            check=True,
        )
        _restore_source_artifact(first_artifacts["D"], workspace)
        data = d_data if arm == "D" else pair_root / "data"
        if arm == "C":
            data.mkdir(mode=0o700)
        project_id = workspace_id = None
        if arm == "D":
            project_id = d_project_id
            workspace_id = _join_existing_memory(workspace, data, project_id)
        assert _source_digest(workspace) == replay_source_digest
        (workspace / fixture["source_transition"]["added_untracked_file"]).write_text(
            fixture["source_transition"]["content"]
        )
        replay = _session(
            base,
            f"paired-{arm}-followup",
            arm,
            workspace,
            data,
            fixture["followup_request"],
            project_id,
            workspace_id,
            released_asset,
            released_checksum,
        )
        replay["grade"] = _grade("coding-untracked-caller", workspace)
        replay["replay_start_sha256"] = replay_source_digest
        replay["source_after_sha256"] = _source_digest(workspace)
        receipts.append(replay)
    result = {
        "schema": "opensocrates.v1.5.eval01-pilot/1.0.0",
        "status": "partial_engineering_pilot",
        "freeze_sha256": _digest(FREEZE),
        "parent_freeze_sha256": _digest(PARENT),
        "client_version": parent["client"]["version"],
        "model": "gpt-6-sol",
        "effort": "medium",
        "released_asset_sha256": _digest(released_asset),
        "candidate_asset_sha256": _digest(ROOT / "dist/opensocrates-1.4.0-codex-plugin.zip"),
        "naturalistic_sessions": 8,
        "paired_replay_sessions": 2,
        "paired_replay_start_sha256": replay_source_digest,
        "receipts": receipts,
        "raw_artifact_dir": str(base),
        "limitations": [
            "one fixture and one GPT-6 model only",
            "pre-enrolled accepted intent",
            "native server-side memory isolation unverified",
            "no blinded human quality judge",
            "subscription billing unavailable",
        ],
    }
    (base / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--released-asset", type=Path, required=True)
    parser.add_argument("--released-checksum", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    print(run(args.released_asset, args.released_checksum, args.output_root))


if __name__ == "__main__":
    main()
