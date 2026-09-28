"""One-shot, atomically claimed main comparison episodes.

Every C/D episode is a separate Python process, so the evaluation-only C guide
binding cannot leak into D. No model call occurs in `list` or `dry-run`.
`dispatch` and `cell` require a frozen ready manifest and explicit enabled flag.
No timeout, coaching, fallback model, outer repair, or automatic restart exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opensocrates.orchestration.adapter import null_usage
from opensocrates.orchestration.contracts import MAX_OUTPUT, candidate_files, checked
from opensocrates.orchestration.runtime import orchestrate
from opensocrates.orchestration.paths import encoded, identity

import opensocrates.orchestration.runtime as runtime
from boundary_gate import evaluate as evaluate_boundary_gate
from generic_guides import guides as generic_guides
from native_profile_client import MARKER
from observer import ObservedAdapter, reconcile
from protocol import DESCRIPTOR, HERE, ROOT, cell_id, descriptor, main_cells, request, sha, single_assignment
from usage import aggregate


SHIM = HERE / "native_profile_client.py"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_new(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as out:
        json.dump(value, out, sort_keys=True, indent=2, ensure_ascii=False)
        out.write("\n")


def verify_freeze(path: Path, expected_sha: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if sha(raw) != expected_sha:
        raise ValueError("freeze_hash_mismatch")
    value = json.loads(raw)
    if value.get("schema") != "opensocrates.go-ts.execution-freeze/1":
        raise ValueError("freeze_schema_mismatch")
    if value.get("ready_for_outcomes") is not True:
        raise ValueError("freeze_not_ready")
    if str(ROOT.resolve()) != value["execution_checkout_root"]:
        raise ValueError("execution_checkout_path_changed")
    current_commit = subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    if current_commit != value["execution_checkout_commit"]:
        raise ValueError("execution_checkout_commit_changed")
    current = descriptor(tasks=set(value["task_descriptor_hashes"]))
    for task_id, expected in value["task_descriptor_hashes"].items():
        data = json.dumps(current["tasks"][task_id], sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False).encode()
        if sha(data) != expected:
            raise ValueError("task_descriptor_changed:" + task_id)
    for name, relative in (("runner_sha256", "run_main.py"),
                           ("shim_sha256", "native_profile_client.py"),
                           ("observer_sha256", "observer.py"),
                           ("generic_guides_sha256", "generic_guides.py"),
                           ("protocol_sha256", "protocol.py")):
        if sha((HERE / relative).read_bytes()) != value[name]:
            raise ValueError("runner_component_changed:" + name)
    for name, expected in value["other_code_hashes"].items():
        if sha((HERE / name).read_bytes()) != expected:
            raise ValueError("evaluation_code_changed:" + name)
    for name, expected in value["product_file_hashes"].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError("product_source_changed:" + name)
    for path, expected in value["tool_and_archive_hashes"].items():
        if sha(Path(path).read_bytes()) != expected:
            raise ValueError("tool_or_archive_changed:" + path)
    task = current["tasks"][next(iter(value["task_descriptor_hashes"]))]
    verifier = HERE / "fixtures" / task["external_qualification"]["entrypoint"]
    if sha(verifier.read_bytes()) != value["fixture_controls"]["external_verifier_sha256"]:
        raise ValueError("external_verifier_changed")
    dependency_root = Path(value["subject_dependency_root"])
    if sorted(item.name for item in dependency_root.iterdir()) != value["subject_dependency_top_level"]:
        raise ValueError("subject_dependency_root_changed")
    boundary = evaluate_boundary_gate()
    if (boundary.get("accepted_component_evidence") is not True
        or boundary != value["boundary_component_decision"]):
        raise ValueError("boundary_component_decision_changed")
    return value


def stage_sources(task: dict[str, Any], source: Path) -> None:
    public = HERE / "fixtures" / task["public_root"]
    source.mkdir(mode=0o700)
    for item in task["sources"]:
        data = (public / item["path"]).read_bytes()
        if "sha256:" + sha(data) != item["sha256"]:
            raise ValueError("source_changed:" + item["id"])
        target = source / item["path"]
        if not target.resolve().is_relative_to(source.resolve()):
            raise ValueError("source_path_escape")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def profile(episode: Path) -> None:
    (episode / MARKER).write_text("isolated comparison episode\n", encoding="utf-8")
    (episode / "home/.codex").mkdir(parents=True)
    (episode / "tmp").mkdir()


def materialize_single(task: dict[str, Any], episode: Path, value: dict[str, Any]) -> dict[str, Any]:
    checked(value, "candidate", MAX_OUTPUT)
    if value["blocked_reason"] is not None:
        raise ValueError("single_author_blocked_reason")
    unit = {"owned_paths": task["required_artifacts"]}
    files = candidate_files(value["files"], unit)
    target = episode / "candidate"
    for prefix in ("artifacts", "versions/single/v1"):
        for name, data in files.items():
            path = target / prefix / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return {name: "sha256:" + sha(data) for name, data in files.items()}


def execute_child(cell: dict[str, str], episode: Path) -> None:
    task = descriptor(tasks={cell["task"]})["tasks"][cell["task"]]
    source = episode / "source"
    journal = episode / "observation.jsonl"
    adapter = ObservedAdapter(str(SHIM), journal)
    started = utc()
    if cell["arm"] in {"C", "D"}:
        if cell["arm"] == "C":
            runtime.guides = generic_guides
        planned = request(task, cell, source, episode / "candidate", SHIM, "run")
        response = orchestrate(planned, adapter=adapter)
        write_new(episode / "response.json", response)
        calls = response["calls"]
        status = response["status"]
        product_client_sha = response.get("client_sha256")
        candidate_hashes = None
        input_sha = identity(planned)
    else:
        role = episode / "role"
        role.mkdir()
        assigned, files = single_assignment(task, cell, source)
        for name, data in files.items():
            path = role / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        input_sha = identity(assigned)
        try:
            adapter.probe()
        except Exception:
            response = {"status": "unavailable", "reason": "client_or_sandbox_unavailable",
                        "calls": []}
            candidate_hashes = None
        else:
            call = adapter.invoke(assigned, role)
            response = {"status": "candidate_returned" if call.value is not None else "unavailable",
                        "reason": call.receipt["reason"], "calls": [call.receipt]}
            candidate_hashes = None
            if call.value is not None:
                try:
                    candidate_hashes = materialize_single(task, episode, call.value)
                except (ValueError, OSError):
                    response.update({"status": "invalid_output", "reason": "candidate_contract_rejected"})
            response["candidate_hashes"] = candidate_hashes
        write_new(episode / "response.json", response)
        calls = response["calls"]
        status = response["status"]
        product_client_sha = adapter.sha256
    summary = {
        "schema": "opensocrates.go-ts.main-episode/1",
        "cell": cell, "started_utc": started, "ended_utc": utc(),
        "status": status, "input_sha256": input_sha,
        "adapter_client_sha256": product_client_sha,
        "actual_client_sha256": "sha256:" + sha(Path(
            "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
        ).read_bytes()),
        "wrapper_sha256": "sha256:" + sha(SHIM.read_bytes()),
        "usage": aggregate(calls),
        "role_event_summaries": adapter.role_event_summaries,
        "observation_failures": adapter.observation_failures,
        "observation_reconciliation": reconcile(journal),
        "candidate_hashes": candidate_hashes,
        "raw_prompt_transcript_reasoning_tool_output_retained": False,
        "external_qualification_status": "pending_serial_post_generation",
    }
    write_new(episode / "summary.json", summary)


def cell_once(cell: dict[str, str], results: Path, freeze_path: Path,
              freeze_sha: str) -> dict[str, Any]:
    verify_freeze(freeze_path, freeze_sha)
    task = descriptor(tasks={cell["task"]})["tasks"][cell["task"]]
    episode = results / cell["id"]
    episode.mkdir(mode=0o700, parents=True, exist_ok=False)  # atomic ownership claim
    write_new(episode / "started.json", {
        "schema": "opensocrates.go-ts.episode-start/1", "cell": cell,
        "utc": utc(), "freeze_sha256": freeze_sha,
        "terminal_missing_means_unknown_not_retry": True,
    })
    auth = episode / "home/.codex/auth.json"
    try:
        profile(episode)
        stage_sources(task, episode / "source")
        auth_source = Path.home() / ".codex/auth.json"
        if not auth_source.is_file():
            raise ValueError("existing_auth_unavailable")
        shutil.copyfile(auth_source, auth)
        auth.chmod(0o600)
        child_env = dict(os.environ)
        child_env.update({
            "HOME": str(episode / "home"), "CODEX_HOME": str(episode / "home/.codex"),
            "TMPDIR": str(episode / "tmp"), "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(HERE))),
        })
        child = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "_child", "--cell-id", cell["id"],
             "--results", str(results)],
            cwd=episode, env=child_env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        status = "terminal" if (episode / "summary.json").is_file() else "unknown_after_start"
        terminal = {"schema": "opensocrates.go-ts.episode-terminal/1",
                    "utc": utc(), "child_exit_code": child.returncode, "status": status}
        write_new(episode / "terminal.json", terminal)
        return {"cell_id": cell["id"], **terminal}
    except Exception as error:
        failure = {"schema": "opensocrates.go-ts.episode-startup-failure/1",
                   "utc": utc(), "status": "startup_or_harness_failure",
                   "error_type": type(error).__name__, "usage": null_usage()}
        if not (episode / "startup-failure.json").exists():
            write_new(episode / "startup-failure.json", failure)
        return {"cell_id": cell["id"], **failure}
    finally:
        auth.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["list", "dry-run", "cell", "dispatch", "_child"])
    parser.add_argument("--cell-id")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--freeze-sha256")
    parser.add_argument("--outcomes-enabled", action="store_true")
    parser.add_argument("--max-workers", type=int)
    parser.add_argument("--descriptor", type=Path,
                        help="pre-integration dry-run only; outcome execution uses committed fixtures")
    parser.add_argument("--task", choices=["S", "O"],
                        help="limit a no-model dry-run to one independently frozen task")
    args = parser.parse_args()
    cells = main_cells()
    if args.command == "list":
        print(json.dumps({"cell_count": len(cells), "ids": [c["id"] for c in cells]}))
        return
    if args.command == "dry-run":
        from protocol import single_assignment
        count = 0
        source_descriptor = args.descriptor or DESCRIPTOR
        data = descriptor(source_descriptor, tasks={args.task} if args.task else None)
        for cell in (item for item in cells if args.task is None or item["task"] == args.task):
            task = data["tasks"][cell["task"]]
            public = source_descriptor.parent / task["public_root"]
            if cell["arm"] in {"A", "B"}:
                single_assignment(task, cell, public)
            else:
                old = runtime.guides
                if cell["arm"] == "C":
                    runtime.guides = generic_guides
                try:
                    response = orchestrate(request(task, cell, public,
                        public.parent / "candidate-absent", SHIM, "prepare"))
                    if response["status"] != "prepared" or response["calls"]:
                        raise ValueError("prepare_failed")
                finally:
                    runtime.guides = old
            count += 1
        print(json.dumps({"prepared_cells": count, "model_calls": 0}))
        return
    if args.command == "_child":
        cell = next(c for c in cells if c["id"] == args.cell_id)
        try:
            execute_child(cell, args.results / cell["id"])
        except BaseException as error:
            write_new(args.results / cell["id"] / "child-failure.json", {
                "schema": "opensocrates.go-ts.child-failure/1", "utc": utc(),
                "error_type": type(error).__name__, "status": "unknown_after_start",
            })
            raise SystemExit(1)
        return
    if not args.outcomes_enabled or args.results is None or args.freeze is None or not args.freeze_sha256:
        parser.error("outcomes require --outcomes-enabled, --results, --freeze, and --freeze-sha256")
    if args.descriptor is not None:
        parser.error("--descriptor is only available for dry-run")
    if args.task is not None:
        parser.error("--task is only available for dry-run")
    verify_freeze(args.freeze, args.freeze_sha256)
    frozen_ids = json.loads(args.freeze.read_text())["cell_ids"]
    selected = [cell for cell in cells if cell["id"] in set(frozen_ids)]
    if len(selected) != len(frozen_ids) or len(set(frozen_ids)) != len(frozen_ids):
        raise ValueError("frozen_cell_set_invalid")
    if args.command == "cell":
        cell = next(c for c in selected if c["id"] == args.cell_id)
        print(json.dumps(cell_once(cell, args.results, args.freeze, args.freeze_sha256)))
    else:
        if args.max_workers is None or args.max_workers < 1:
            parser.error("dispatch requires an explicit frozen --max-workers")
        if args.max_workers != json.loads(args.freeze.read_text())["dispatch"]["max_workers"]:
            raise ValueError("dispatch_parallelism_differs_from_freeze")
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = [pool.submit(cell_once, cell, args.results, args.freeze,
                                   args.freeze_sha256) for cell in selected]
            for future in as_completed(futures):
                print(json.dumps(future.result(), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
