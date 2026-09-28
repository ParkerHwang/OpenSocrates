"""One-shot eight-cell continuation lane using real disposable memory APIs."""

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

from opensocrates.orchestration.runtime import orchestrate
from opensocrates.orchestration.paths import identity
from opensocrates.project_memory.registry import ProjectRegistry

from boundary_gate import evaluate as evaluate_boundary_gate
from continuity_memory import HERE, SHIM, fixture, request_for, setup_one
from observer import ObservedAdapter, reconcile
from protocol import CLIENT, ROOT, sha
from run_main import dispatch_summary, profile, resource_snapshot, write_new
from usage import aggregate


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_freeze(path: Path, expected_sha: str) -> dict[str, Any]:
    if sha(path.read_bytes()) != expected_sha:
        raise ValueError("continuity_freeze_hash_mismatch")
    frozen = json.loads(path.read_text())
    if frozen.get("schema") != "opensocrates.go-ts.continuity-freeze/1" or frozen.get("ready_for_outcomes") is not True:
        raise ValueError("continuity_freeze_not_ready")
    if str(ROOT.resolve()) != frozen["execution_checkout_root"]:
        raise ValueError("execution_checkout_path_changed")
    head = subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    if head != frozen["execution_checkout_commit"]:
        raise ValueError("execution_checkout_commit_changed")
    if evaluate_boundary_gate() != frozen["boundary_component_decision"]:
        raise ValueError("role_boundary_decision_changed")
    for relative, expected in frozen["code_hashes"].items():
        if sha((HERE / relative).read_bytes()) != expected:
            raise ValueError("continuity_code_changed:" + relative)
    for relative, expected in frozen["product_hashes"].items():
        if sha((ROOT / relative).read_bytes()) != expected:
            raise ValueError("continuity_product_changed:" + relative)
    for absolute, expected in frozen["tool_hashes"].items():
        if sha(Path(absolute).read_bytes()) != expected:
            raise ValueError("continuity_tool_changed:" + absolute)
    if sha((HERE / "fixtures/continuity/descriptor.json").read_bytes()) != frozen["descriptor_sha256"]:
        raise ValueError("continuity_descriptor_changed")
    if sha((HERE / "fixtures/continuity/private/harness_setup.json").read_bytes()) != frozen["memory_setup_sha256"]:
        raise ValueError("continuity_setup_changed")
    for relative, expected in frozen["fixture_file_hashes"].items():
        if sha((HERE / "fixtures/continuity" / relative).read_bytes()) != expected:
            raise ValueError("continuity_fixture_changed:" + relative)
    return frozen


def child(cell: dict[str, Any], episode: Path, receipt: dict[str, Any]) -> None:
    source = episode / "source"
    binding = {
        "project_id": receipt["project_id"], "workspace_id": receipt["workspace_id"],
        "record_ids": [*receipt["retained_record_ids"], receipt["stale_record_id"],
                       receipt["proposed_record_id"]],
    }
    planned = request_for(cell, source, episode / "candidate", binding)
    planned["operation"] = "run"
    registry = ProjectRegistry(episode / "private-store")
    adapter = ObservedAdapter(str(SHIM), episode / "observation.jsonl")
    started = utc()
    response = orchestrate(planned, registry=registry, adapter=adapter)
    write_new(episode / "response.json", response)
    summary = {
        "schema": "opensocrates.go-ts.continuity-episode/1",
        "cell_id": cell["id"], "condition": cell["condition"],
        "model": response.get("model"), "started_utc": started, "ended_utc": utc(),
        "status": response["status"], "plan_sha256": identity(planned),
        "memory_setup_sha256": "sha256:" + sha((episode / "memory-setup.json").read_bytes()),
        "memory_status": response.get("memory_status"),
        "memory_snapshot_sha256": response.get("memory_snapshot_sha256"),
        "usage": aggregate(response["calls"]),
        "observer_revision": 2,
        "candidate_diagnostics": adapter.candidate_diagnostics,
        "role_event_summaries": adapter.role_event_summaries,
        "observation_failures": adapter.observation_failures,
        "observation_reconciliation": reconcile(episode / "observation.jsonl"),
        "native_client_sha256_is_shim": response.get("client_sha256") == adapter.sha256,
        "actual_client_sha256": "sha256:" + sha(Path(CLIENT).read_bytes()),
        "external_qualification_status": "pending_serial_post_generation",
        "raw_prompt_transcript_reasoning_tool_output_retained": False,
    }
    write_new(episode / "summary.json", summary)


def one(cell: dict[str, Any], results: Path, freeze_path: Path,
        freeze_sha: str) -> dict[str, Any]:
    verify_freeze(freeze_path, freeze_sha)
    episode = results / cell["id"]
    episode.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_new(episode / "started.json", {
        "schema": "opensocrates.go-ts.continuity-start/1",
        "cell_id": cell["id"], "utc": utc(), "freeze_sha256": freeze_sha,
        "resource": resource_snapshot(),
        "terminal_missing_means_unknown_not_retry": True,
    })
    auth = episode / "home/.codex/auth.json"
    try:
        # Keep the enrolled workspace at its original path. Moving it would
        # invalidate the product's stored workspace binding.
        setup = setup_one(cell, HERE / "fixtures", episode)
        write_new(episode / "memory-setup.json", setup)
        profile(episode)
        auth_source = Path.home() / ".codex/auth.json"
        if not auth_source.is_file():
            raise ValueError("existing_auth_unavailable")
        shutil.copyfile(auth_source, auth)
        auth.chmod(0o600)
        env = dict(os.environ)
        env.update({
            "HOME": str(episode / "home"), "CODEX_HOME": str(episode / "home/.codex"),
            "TMPDIR": str(episode / "tmp"), "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(HERE))),
        })
        proc = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "_child", "--cell-id", cell["id"],
             "--results", str(results)], cwd=episode, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False,
        )
        result = {"schema": "opensocrates.go-ts.continuity-terminal/1",
                  "cell_id": cell["id"], "utc": utc(), "child_exit_code": proc.returncode,
                  "resource": resource_snapshot(),
                  "status": "terminal" if (episode / "summary.json").is_file() else "unknown_after_start"}
        write_new(episode / "terminal.json", result)
        return result
    except Exception as error:
        failure = {"schema": "opensocrates.go-ts.continuity-startup-failure/1",
                   "cell_id": cell["id"], "utc": utc(),
                   "error_type": type(error).__name__, "status": "startup_or_harness_failure"}
        write_new(episode / "startup-failure.json", failure)
        return failure
    finally:
        auth.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["list", "cell", "dispatch", "_child"])
    parser.add_argument("--cell-id")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--freeze-sha256")
    parser.add_argument("--outcomes-enabled", action="store_true")
    parser.add_argument("--max-workers", type=int)
    args = parser.parse_args()
    _, description = fixture(HERE / "fixtures")
    cells = description["cells"]
    if args.command == "list":
        print(json.dumps({"count": len(cells), "ids": [item["id"] for item in cells]}))
        return
    if args.command == "_child":
        item = next(item for item in cells if item["id"] == args.cell_id)
        episode = args.results / item["id"]
        try:
            child(item, episode, json.loads((episode / "memory-setup.json").read_text()))
        except BaseException as error:
            write_new(episode / "child-failure.json", {
                "schema": "opensocrates.go-ts.continuity-child-failure/1",
                "utc": utc(), "error_type": type(error).__name__,
                "status": "unknown_after_start",
            })
            raise SystemExit(1)
        return
    if not args.outcomes_enabled or args.results is None or args.freeze is None or not args.freeze_sha256:
        parser.error("outcomes require enabled flag, result root and exact ready freeze")
    frozen = verify_freeze(args.freeze, args.freeze_sha256)
    selected = [cell for cell in cells if cell["id"] in frozen["cell_ids"]]
    if len(selected) != 8 or len(set(frozen["cell_ids"])) != 8:
        raise ValueError("continuity_cell_set_changed")
    if args.command == "cell":
        item = next(item for item in selected if item["id"] == args.cell_id)
        print(json.dumps(one(item, args.results, args.freeze, args.freeze_sha256)))
    else:
        if args.max_workers != frozen["dispatch"]["max_workers"]:
            parser.error("explicit max workers must match freeze")
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = [pool.submit(one, item, args.results, args.freeze, args.freeze_sha256)
                       for item in selected]
            returned = []
            for future in as_completed(futures):
                value = future.result()
                returned.append(value)
                print(json.dumps(value, sort_keys=True), flush=True)
        write_new(args.results / "dispatch-index.json",
                  dispatch_summary(args.results, selected, returned, args.max_workers))


if __name__ == "__main__":
    main()
