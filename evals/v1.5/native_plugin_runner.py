"""Execute the frozen native-plugin pilot in isolated, disposable Codex homes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pilot_runner import checks_for, digest, read_events, side_question_observation, summarize_events


HERE = Path(__file__).resolve().parent
NATIVE_FREEZE = HERE / "native-plugin-execution-freeze.v1.json"
TASK_FREEZE = HERE / "pilot-execution-freeze.json"
GLOBAL_AUTH = Path.home() / ".codex" / "auth.json"
FREEZE_COMMIT = "b843b9d581d9fa94a563fa5ec49c1d4c4efd2645"


def profile_environment(base: Path) -> tuple[Path, dict[str, str]]:
    os_home = base / "os-home"
    os_home.mkdir(mode=0o700)
    codex_home = os_home / ".codex"
    codex_home.mkdir(mode=0o700)
    shutil.copyfile(GLOBAL_AUTH, codex_home / "auth.json")
    os.chmod(codex_home / "auth.json", 0o600)
    tmp = base / "tmp"
    tmp.mkdir(mode=0o700)
    env = os.environ.copy()
    env.update({"HOME": str(os_home), "CODEX_HOME": str(codex_home), "TMPDIR": str(tmp)})
    return codex_home, env


def install_or_check(freeze: dict[str, Any], env: dict[str, str], marketplace: Path, plugin: bool) -> dict[str, Any]:
    cli = freeze["client"]["path"]
    started = time.monotonic()
    operations = []
    if plugin:
        for args in (
            ["plugin", "marketplace", "add", str(marketplace), "--json"],
            ["plugin", "add", "opensocrates@os-eval", "--json"],
        ):
            process = subprocess.run([cli, *args], env=env, text=True, capture_output=True, timeout=90, check=False)
            try:
                value = json.loads(process.stdout)
            except json.JSONDecodeError:
                value = {}
            operations.append({
                "operation": "marketplace_add" if args[1] == "marketplace" else "plugin_add",
                "exit_code": process.returncode,
                "stdout_sha256": digest(process.stdout) if process.stdout else None,
                "stderr_sha256": digest(process.stderr) if process.stderr else None,
                "installed_version": value.get("version"),
            })
            if process.returncode != 0:
                return {"ok": False, "operations": operations, "wall_seconds": round(time.monotonic() - started, 3), "inventory": None}
    process = subprocess.run([cli, "plugin", "list", "--json"], env=env, text=True, capture_output=True, timeout=90, check=False)
    try:
        inventory = json.loads(process.stdout)
    except json.JSONDecodeError:
        inventory = {}
    matches = [item for item in inventory.get("installed", []) if item.get("name") == "opensocrates"]
    identity = [
        {"id": item.get("pluginId"), "version": item.get("version"), "installed": item.get("installed"), "enabled": item.get("enabled")}
        for item in matches
    ]
    expected = plugin and len(identity) == 1 and identity[0] == {"id": "opensocrates@os-eval", "version": "1.4.0", "installed": True, "enabled": True}
    clean = (not plugin) and len(identity) == 0
    return {
        "ok": process.returncode == 0 and (expected or clean),
        "operations": operations,
        "inventory": identity,
        "inventory_exit_code": process.returncode,
        "wall_seconds": round(time.monotonic() - started, 3),
    }


def invoke(
    freeze: dict[str, Any], fixture: Path, env: dict[str, str], arm: dict[str, Any], prompt: str,
    *, resume: bool = False,
) -> dict[str, Any]:
    cli = freeze["client"]["path"]
    command = [cli, "exec"]
    if resume:
        command += ["resume", "--last", "--skip-git-repo-check", "-c", "sandbox_mode=workspace-write"]
    else:
        command += ["--sandbox", "workspace-write", "--skip-git-repo-check", "-C", str(fixture)]
    command += ["--json", "--disable", "multi_agent", "-m", arm["model"], "-c", "model_reasoning_effort=medium"]
    if arm["hooks"]:
        command += ["--dangerously-bypass-hook-trust"]
    else:
        command += ["--disable", "hooks"]
    command.append("-")
    started = time.monotonic()
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    timed_out = False
    try:
        result = subprocess.run(
            command, input=prompt, text=True, capture_output=True, env=env, cwd=fixture,
            timeout=freeze["client"]["per_turn_wall_seconds"], check=False,
        )
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    events, malformed = read_events(stdout)
    summary = summarize_events(events)
    final_message = summary.pop("final_message")
    hook_events = sum("hook" in str(event.get("type", "")).lower() for event in events)
    return {
        "stage": "followup" if resume else "initial",
        "client": freeze["client"]["version"],
        "requested_model": arm["model"],
        "requested_effort": "medium",
        "command_mode": "installed_hooks" if arm["hooks"] else "hooks_disabled",
        "prompt_sha256": digest(prompt),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "wall_seconds": round(time.monotonic() - started, 3),
        "event_count": len(events),
        "malformed_event_lines": malformed,
        "stderr_sha256": digest(stderr) if stderr else None,
        "hook_event_count": hook_events,
        "grounding_line_claim_present": "OpenSocrates grounding:" in final_message,
        "failure": timed_out or exit_code != 0 or bool(summary["error_types"]),
        **summary,
        "side_question_observation": side_question_observation(final_message),
        "billed_cost": None,
        "server_echoed_model": None,
        "native_hook_application": None,
    }


def cell(
    freeze: dict[str, Any], tasks: dict[str, Any], marketplace: Path, lane: str,
    task_id: str, arm: dict[str, Any], language: str,
) -> dict[str, Any]:
    task = tasks["tasks"][task_id]
    with tempfile.TemporaryDirectory(prefix="os-v15-native-cell-") as td:
        base = Path(td)
        fixture = base / "fixture"
        fixture.mkdir(mode=0o700)
        for name, content in task["files"].items():
            (fixture / name).write_text(content, encoding="utf-8")
        source_hashes = {name: digest(content) for name, content in task["files"].items()}
        codex_home, env = profile_environment(base)
        installation = install_or_check(freeze, env, marketplace, arm["plugin"])
        result: dict[str, Any] = {
            "lane": lane,
            "task": task_id,
            "language": language,
            "arm": arm["id"],
            "requested_model": arm["model"],
            "requested_effort": "medium",
            "candidate_zip_sha256": freeze["candidate_zip"]["sha256"] if arm["plugin"] else None,
            "plugin_installed": arm["plugin"],
            "hooks_requested": arm["hooks"],
            "source_hashes_before": source_hashes,
            "installation": installation,
            "calls": [],
            "repairs": [],
            "escalations": [],
            "manual_bilingual_dialogue_score": None,
            "manual_score_missing_reason": "No independent bilingual human reviewer assigned.",
        }
        if not installation["ok"]:
            result.update({"deterministic_success": False, "missing_cell_reason": "Disposable profile installation or baseline absence check failed; model was not called."})
            return result
        prompt = freeze["common_prompt"]
        if arm["plugin"]:
            prompt += "\n\n" + freeze["native_prompt_addition"]
        prompt += "\n\n" + (task.get(f"request_{language}") or task["request_en"])
        result["calls"].append(invoke(freeze, fixture, env, arm, prompt))
        try:
            result["initial_checks"] = checks_for(task_id, fixture, "initial")
        except Exception as exc:
            result["initial_checks"] = None
            result["initial_check_failure"] = type(exc).__name__
        if lane == "EVAL-05":
            if "followup_source" in task:
                (fixture / "event.json").write_text(task["followup_source"], encoding="utf-8")
            result["calls"].append(invoke(freeze, fixture, env, arm, task[f"followup_{language}"], resume=True))
        try:
            result["final_checks"] = checks_for(task_id, fixture, "followup" if lane == "EVAL-05" else "initial")
        except Exception as exc:
            result["final_checks"] = None
            result["final_check_failure"] = type(exc).__name__
        result["artifact_hashes_after"] = {
            path.name: digest(path.read_bytes()) for path in fixture.iterdir()
            if path.is_file() and path.suffix in {".py", ".md", ".json"}
        }
        result["deterministic_success"] = (
            bool(result["final_checks"]) and all(result["final_checks"].values())
            and all(not call["failure"] for call in result["calls"])
        )
        result["codex_home_owner_only"] = (codex_home.stat().st_mode & 0o777) == 0o700
        result["auth_copy_owner_only"] = ((codex_home / "auth.json").stat().st_mode & 0o777) == 0o600
        result["auth_is_symlink"] = (codex_home / "auth.json").is_symlink()
        return result


def build_marketplace(freeze: dict[str, Any], base: Path) -> Path:
    archive = Path(freeze["candidate_zip"]["path"])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != freeze["candidate_zip"]["sha256"]:
        raise SystemExit("Candidate ZIP hash drift")
    marketplace = base / "marketplace"
    package = marketplace / "plugin"
    package.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise SystemExit("Candidate ZIP corrupt")
        zipped.extractall(package)
    manifest = json.loads((package / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if manifest.get("name") != "opensocrates" or manifest.get("version") != "1.4.0":
        raise SystemExit("Candidate plugin identity mismatch")
    config = {
        "name": "os-eval",
        "plugins": [{
            "name": "opensocrates",
            "source": {"source": "local", "path": "./plugin"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }],
    }
    meta = marketplace / ".agents" / "plugins"
    meta.mkdir(parents=True)
    (meta / "marketplace.json").write_text(json.dumps(config), encoding="utf-8")
    return marketplace


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=["EVAL-02", "EVAL-03", "EVAL-05"], required=True)
    args = parser.parse_args()
    raw_freeze = NATIVE_FREEZE.read_bytes()
    freeze = json.loads(raw_freeze)
    raw_tasks = TASK_FREEZE.read_bytes()
    if digest(raw_tasks) != freeze["task_manifest_sha256"]:
        raise SystemExit("Frozen task manifest hash drift")
    tasks = json.loads(raw_tasks)
    if not GLOBAL_AUTH.is_file():
        raise SystemExit("Existing ChatGPT auth file unavailable")
    version = subprocess.run([freeze["client"]["path"], "--version"], text=True, capture_output=True, check=True).stdout.strip()
    if version != freeze["client"]["version"]:
        raise SystemExit("Client version drift")
    with tempfile.TemporaryDirectory(prefix="os-v15-native-market-") as td:
        marketplace = build_marketplace(freeze, Path(td))
        work = []
        for task_id in tasks["lanes"][args.lane]["tasks"]:
            for language in tasks["lanes"][args.lane].get("languages", ["en"]):
                for arm in freeze["arms"][args.lane]:
                    work.append((task_id, arm, language))
        cells = []
        with ThreadPoolExecutor(max_workers=freeze["client"]["max_parallel_cells"]) as pool:
            futures = {pool.submit(cell, freeze, tasks, marketplace, args.lane, *entry): entry for entry in work}
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "lane": args.lane, "task": entry[0], "arm": entry[1]["id"],
                        "language": entry[2], "runner_failure": type(exc).__name__,
                        "deterministic_success": False, "calls": None,
                        "missing_receipt_reason": "Runner exception; exact attempted-call count unavailable.",
                    }
                cells.append(result)
                print(f"{args.lane} {result['task']} {result['language']} {result['arm']}: {result['deterministic_success']}", flush=True)
        cells.sort(key=lambda row: (row["task"], row["language"], row["arm"]))
        output = {
            "schema": "opensocrates.v1.5.native-plugin-pilot-results/1.0.0",
            "lane": args.lane,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "freeze_commit": FREEZE_COMMIT,
            "freeze_sha256": digest(raw_freeze),
            "candidate_zip_sha256": freeze["candidate_zip"]["sha256"],
            "client": version,
            "held_out": False,
            "validated_profile": False,
            "cells": cells,
        }
        result_path = HERE / "results" / f"native-{args.lane.lower()}-pilot.json"
        result_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(result_path)


if __name__ == "__main__":
    main()
