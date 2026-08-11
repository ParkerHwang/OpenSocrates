#!/usr/bin/env python3
"""Measure packaged Claude PostToolUse receipt and Stop cleanup latency on macOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opensocrates.constants import INSTRUCTION_ARTIFACT_END_MARKER
from opensocrates.content.injection import AssembledInstruction
from opensocrates.persistence import DataRootConfig, TurnStateStore, ensure_data_root
from opensocrates.selector import InstructionFileStore

ROOT = Path(__file__).resolve().parents[1]
TARGET = "darwin-arm64"
HOOK_BUDGET_MS = 3_000
SUFFICIENT_MARGIN_MS = HOOK_BUDGET_MS // 2


class TimingError(Exception):
    """A content-free timing contract failure."""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.5)))
    return round(ordered[index], 3)


def _distribution(values: list[float]) -> dict[str, float]:
    return {
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def _payload(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def _run_hook(
    launcher: Path,
    lane: str,
    payload: bytes,
    *,
    environment: dict[str, str],
    cwd: Path,
) -> tuple[float, bytes]:
    started = time.perf_counter()
    process = subprocess.Popen(
        [str(launcher), "hook", "claude", lane],
        cwd=cwd,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, _stderr = process.communicate(payload, timeout=HOOK_BUDGET_MS / 1_000)
    except subprocess.TimeoutExpired as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise TimingError("hook_deadline_exceeded") from error
    elapsed = (time.perf_counter() - started) * 1_000
    if process.returncode != 0:
        raise TimingError("packaged_launcher_nonzero_exit")
    return elapsed, stdout


def _prepare_package(source: Path, destination: Path) -> Path:
    plugin = destination / "plugin"
    shutil.copytree(source, plugin, copy_function=shutil.copy2)
    launcher = plugin / "bin" / "launch.sh"
    runtime = plugin / "runtime" / TARGET / "opensocrates-runtime" / "opensocrates-runtime"
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise TimingError("packaged_launcher_missing")
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise TimingError("packaged_runtime_missing")
    return launcher


def _sample(
    launcher: Path,
    sample_root: Path,
    sample_number: int,
) -> tuple[float, float]:
    home = sample_root / "home"
    temporary = sample_root / "tmp"
    workspace = sample_root / "workspace"
    for directory in (home, temporary, workspace):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    data_directory = home / "Library" / "Application Support" / "OpenSocrates"
    data_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    data_root = ensure_data_root(DataRootConfig(host_data_dir=data_directory))
    turn_store = TurnStateStore(data_root)

    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = str(temporary)
    try:
        artifact_store = InstructionFileStore(installation_key=turn_store.installation_key)
    finally:
        tempfile.tempdir = previous_tempdir

    session_id = f"timing-session-{sample_number}"
    turn_id = f"timing-turn-{sample_number}"
    assembled = AssembledInstruction(
        content_revision=1,
        locale="en",
        selected_reasoning_systems=("critical-thinking",),
        selected_display_names=("Critical Thinking",),
        inline_guardrails=(),
        instructions="Synthetic timing instruction with no user content.",
        estimated_tokens=12,
    )
    artifact = artifact_store.create(session_id, turn_id, assembled)
    artifact_content = artifact.path.read_text(encoding="utf-8")
    if INSTRUCTION_ARTIFACT_END_MARKER not in artifact_content:
        raise TimingError("synthetic_artifact_invalid")
    lines = artifact_content.splitlines()

    environment = dict(os.environ)
    environment.update(
        {
            "HOME": str(home),
            "TMPDIR": str(temporary),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        }
    )
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "OPENSOCRATES_DATA_DIR",
        "OPENSOCRATES_DEVELOPMENT_MANIFEST",
    ):
        environment.pop(key, None)

    post_tool = _payload(
        {
            "hook_event_name": "PostToolUse",
            "session_id": session_id,
            "prompt_id": turn_id,
            "cwd": str(workspace),
            "transcript_path": str(sample_root / "synthetic-transcript.jsonl"),
            "permission_mode": "acceptEdits",
            "tool_name": "Read",
            "tool_use_id": f"toolu-timing-{sample_number}",
            "tool_input": {"file_path": str(artifact.path)},
            "tool_response": {
                "type": "text",
                "file": {
                    "filePath": str(artifact.path),
                    "content": artifact_content,
                    "numLines": len(lines),
                    "startLine": 1,
                    "totalLines": len(lines),
                },
            },
        }
    )
    post_tool_ms, post_tool_stdout = _run_hook(
        launcher,
        "tool_succeeded",
        post_tool,
        environment=environment,
        cwd=workspace,
    )
    if post_tool_stdout != b"":
        raise TimingError("post_tool_use_stdout_not_empty")
    if not artifact_store.has_complete_read_receipt(artifact):
        raise TimingError("post_tool_use_receipt_missing")

    stop = _payload(
        {
            "hook_event_name": "Stop",
            "session_id": session_id,
            "prompt_id": turn_id,
            "cwd": str(workspace),
            "transcript_path": str(sample_root / "synthetic-transcript.jsonl"),
            "permission_mode": "acceptEdits",
            "stop_hook_active": False,
            "last_assistant_message": f"Synthetic completion.\n\n{artifact.grounding_footer()}",
            "background_tasks": [],
            "session_crons": [],
        }
    )
    stop_ms, stop_stdout = _run_hook(
        launcher,
        "completion_candidate",
        stop,
        environment=environment,
        cwd=workspace,
    )
    if stop_stdout != b"":
        raise TimingError("stop_stdout_not_empty")
    if artifact.path.exists() or artifact.path.parent.exists():
        raise TimingError("stop_cleanup_incomplete")
    return post_tool_ms, stop_ms


def _scenario(package: Path, root: Path, *, runs: int, fresh_path: bool) -> dict[str, Any]:
    post_tool_values: list[float] = []
    stop_values: list[float] = []
    if fresh_path:
        for index in range(runs):
            sample_root = root / f"cold-{index}"
            launcher = _prepare_package(package, sample_root)
            post_tool, stop = _sample(launcher, sample_root, index)
            post_tool_values.append(post_tool)
            stop_values.append(stop)
    else:
        sample_root = root / "warm"
        launcher = _prepare_package(package, sample_root)
        # Prime executable and filesystem metadata caches with a complete pair;
        # the priming result is deliberately excluded from the distribution.
        _sample(launcher, sample_root, -1)
        for index in range(runs):
            post_tool, stop = _sample(launcher, sample_root, index)
            post_tool_values.append(post_tool)
            stop_values.append(stop)
    post_tool = _distribution(post_tool_values)
    stop = _distribution(stop_values)
    worst_p95 = max(post_tool["p95"], stop["p95"])
    return {
        "runs": runs,
        "condition": "fresh_package_path_first_invocation" if fresh_path else "reused_package_path",
        "os_cache_purge_claimed": False,
        "post_tool_use_receipt_ms": post_tool,
        "stop_cleanup_ms": stop,
        "verified_receipts": runs,
        "verified_cleanups": runs,
        "p95_margin_ms": round(HOOK_BUDGET_MS - worst_p95, 3),
        "sufficient_margin": worst_p95 <= SUFFICIENT_MARGIN_MS,
    }


def measure(package: Path, runs: int) -> dict[str, Any]:
    manifest_path = package / "release-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("product_version") != "1.1.2" or manifest.get("host") != "claude":
        raise TimingError("package_identity_mismatch")
    if TARGET not in manifest.get("runtime_targets", []):
        raise TimingError("darwin_arm64_runtime_missing")
    hooks = json.loads((package / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    hook_deadlines = {
        "PostToolUse": hooks["PostToolUse"][0]["hooks"][0]["timeout"],
        "Stop": hooks["Stop"][0]["hooks"][0]["timeout"],
    }
    if hook_deadlines != {"PostToolUse": 3, "Stop": 3}:
        raise TimingError("packaged_hook_deadline_mismatch")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise TimingError("native_darwin_arm64_required")

    with tempfile.TemporaryDirectory(prefix="opensocrates-hook-timing-") as name:
        root = Path(name)
        cold = _scenario(package, root, runs=runs, fresh_path=True)
        warm = _scenario(package, root, runs=runs, fresh_path=False)
    sufficient = cold["sufficient_margin"] and warm["sufficient_margin"]
    return {
        "schema": "opensocrates.claude-hook-timing/1.0.0",
        "generated_at": _now(),
        "status": "pass" if sufficient else "fail",
        "product_version": "1.1.2",
        "target": TARGET,
        "environment": {
            "system": platform.system(),
            "macos_version": platform.mac_ver()[0],
            "machine": platform.machine(),
        },
        "package_manifest_sha256": "sha256:" + hashlib.sha256(manifest_bytes).hexdigest(),
        "hook_budget_ms": HOOK_BUDGET_MS,
        "hook_deadlines_seconds": hook_deadlines,
        "required_p95_margin_ms": SUFFICIENT_MARGIN_MS,
        "timeout_change_recommended": not sufficient,
        "cold": cold,
        "warm": warm,
        "privacy": {
            "synthetic_content_only": True,
            "paths_recorded": False,
            "payloads_recorded": False,
            "artifact_content_recorded": False,
            "session_ids_recorded": False,
            "stdout_recorded": False,
            "stderr_recorded": False,
        },
        "limitations": [
            "fresh-path cold samples do not purge macOS kernel or filesystem caches",
            "measurement covers this local Apple-silicon Mac only",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="dist/claude")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--report", default="build/evidence/claude-hook-timing.json")
    args = parser.parse_args()
    if not 10 <= args.runs <= 100:
        parser.error("--runs must be between 10 and 100")
    package = (ROOT / args.package).resolve()
    report_path = (ROOT / args.report).resolve()
    try:
        report = measure(package, args.runs)
    except (OSError, ValueError, json.JSONDecodeError, TimingError) as error:
        report = {
            "schema": "opensocrates.claude-hook-timing/1.0.0",
            "generated_at": _now(),
            "status": "blocked",
            "diagnostic": str(error),
            "privacy": {"raw_output_recorded": False},
        }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"claude-hook-timing: {report['status'].upper()} "
        f"target={report.get('target', 'unavailable')}"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
