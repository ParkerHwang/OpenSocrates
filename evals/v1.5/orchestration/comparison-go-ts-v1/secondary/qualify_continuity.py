#!/usr/bin/env python3
"""Post-generation continuity version checks; no subject model invocation.

`run_continuity.py` alone owns disposable enrollment, correction, forgetting and
native three-role execution. This module reads those receipts afterward,
checks actual memory/source state with read-only APIs, and qualifies exact
candidate versions using the frozen private fixture checker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def after_role_state(cell: dict[str, Any], episode: Path, setup: dict[str, Any]) -> dict[str, Any]:
    """Use only read-only memory APIs; retain digests/IDs, never raw records."""
    parent = Path(__file__).resolve().parents[1]
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    from continuity_memory import call
    from opensocrates.project_memory.registry import ProjectRegistry

    checks = []
    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"id": name, "passed": bool(passed), "detail": detail[:160]})

    source = episode / "source"
    expected_paths = {item["materialized_path"] for item in cell["sources"]}
    source_has_symlink = any(path.is_symlink() for path in source.rglob("*"))
    actual_paths = {str(path.relative_to(source)) for path in source.rglob("*") if path.is_file()}
    source_ok = not source_has_symlink and actual_paths == expected_paths and all(
        "sha256:" + sha((source / item["materialized_path"]).read_bytes()) == item["sha256"]
        for item in cell["sources"]
    )
    add("continuity_source_bytes_after_role", source_ok, "exact allowlisted source bytes unchanged")
    current = source / "current-source.md"
    add("continuity_corrected_source_after_role", current.is_file() and "sha256:" + sha(current.read_bytes()) == setup["source_after_sha256"], "tracked final Markdown correction retained")
    note = source / "maintained_note.md"
    if cell["condition"] == "scoped_disposable_memory":
        add("continuity_note_boundary", not note.exists(), "memory condition has no maintained note")
    else:
        add("continuity_note_boundary", note.is_file() and "sha256:" + sha(note.read_bytes()) == setup["maintained_note_sha256"], "disabled-memory condition uses exact maintained note")

    registry = ProjectRegistry(episode / "private-store")
    identities = {"project_id": setup["project_id"], "workspace_id": setup["workspace_id"], "task_id": None}
    exported = call(registry, identities, "export", {"format": "json"}, cell["id"] + ":export")
    current_export_sha = "sha256:" + sha(json.dumps(exported, sort_keys=True).encode())
    add("continuity_memory_export_after_role", current_export_sha == setup["export_sha256"], "persisted export digest unchanged since pre-role readback")
    inspected = call(registry, identities, "inspect", {}, cell["id"] + ":post-inspect")
    records = inspected["result"]
    by_id = {item["record_id"]: item for item in records}
    expected_ids = set(setup["persisted_record_ids"])
    retained = set(setup["retained_record_ids"])
    deleted = setup["deleted_record_id"]
    add("continuity_persisted_ids_after_role", set(by_id) == expected_ids and deleted not in by_id, "one scoped deletion preserved; no added or removed records")
    lifecycle_ok = all(by_id[key]["lifecycle"] == "accepted" for key in [*retained, setup["stale_record_id"]] if key in by_id)
    lifecycle_ok &= setup["proposed_record_id"] in by_id and by_id[setup["proposed_record_id"]]["lifecycle"] != "accepted"
    add("continuity_record_lifecycle_after_role", lifecycle_ok, "accepted records retained; proposal not promoted")
    status = call(registry, identities, "status", {}, cell["id"] + ":post-status")
    mode = status["result"]["policy"]["mode"]
    expected_mode = "disabled" if cell["condition"] == "disabled_memory_with_equivalent_note" else "read_write"
    add("continuity_policy_mode_after_role", mode == expected_mode, "post-role memory policy unchanged")
    return {"passed": all(item["passed"] for item in checks), "checks": checks,
            "export_sha256": current_export_sha, "record_count": len(records),
            "policy_mode": mode, "read_only_api_operations": ["export", "inspect", "status"],
            "raw_records_retained": False}


def _result_from_version(cell: dict[str, Any], episode: Path, version: dict[str, Any],
                         root: Path, checker: Path, state: dict[str, Any]) -> dict[str, Any]:
    parent = Path(__file__).resolve().parents[1]
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    from qualify_main import classification, files_for_version
    from run_main import write_new

    files = files_for_version(episode, cell["unit"], version)
    label = f"continuation-v{version['version']}"
    run = root / cell["id"] / label
    run.mkdir(mode=0o700, parents=True, exist_ok=False)
    candidate = run / "candidate-copy"
    candidate.mkdir(mode=0o700)
    (candidate / ".eval-copy").write_text("disposable qualification copy\n")
    for name, data in files.items():
        path = candidate / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    setup_path = episode / "memory-setup.json"
    command = [
        "/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-B", str(checker),
        "--candidate", str(candidate), "--locale", cell["locale"],
        "--condition", cell["condition"], "--state-receipt", str(setup_path),
        "--source-root", str(episode / "source"),
    ]
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}
    process = subprocess.run(command, cwd=run, env=env, stdin=subprocess.DEVNULL,
                             capture_output=True, check=False, timeout=45)
    try:
        structured = json.loads(process.stdout)
        if not isinstance(structured, dict):
            structured = None
    except (ValueError, UnicodeError):
        structured = None
    receipt = {"schema": "opensocrates.go-ts.continuity-external/1", "scope": "continuation",
               "exit_code": process.returncode,
               "argv_sha256": "sha256:" + sha(json.dumps(command, separators=(",", ":")).encode()),
               "checker_sha256": "sha256:" + sha(checker.read_bytes()),
               "stdout_sha256": "sha256:" + sha(process.stdout),
               "stderr_sha256": "sha256:" + sha(process.stderr),
               "structured": structured, "raw_output_retained": False}
    write_new(run / "receipt.json", receipt)
    artifact_result = classification(structured, process.returncode)
    if not state["passed"]:
        status = {"status": "memory_or_source_boundary_unassessable", "subject_defect": None,
                  "artifact_assessment": artifact_result}
    else:
        status = artifact_result
    return {"cell_id": cell["id"], "variant": label,
            "native_qualified": version["qualified"],
            "candidate_hashes": {name: "sha256:" + sha(data) for name, data in files.items()},
            **status}


def qualify_all(results: Path, freeze: dict[str, Any]) -> dict[str, Any]:
    parent = Path(__file__).resolve().parents[1]
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    from continuity_memory import HERE, fixture
    from qualify_main import all_generated
    from run_main import write_new

    _, description = fixture(HERE / "fixtures")
    selected = [cell for cell in description["cells"] if cell["id"] in freeze["cell_ids"]]
    if len(selected) != 8 or len(set(freeze["cell_ids"])) != 8:
        raise ValueError("continuity_frozen_cell_set_invalid")
    all_generated(results, selected)
    checker = HERE / "fixtures/continuity/private/verify_continuity.py"
    if not checker.is_file():
        raise ValueError("continuity_checker_missing")
    root = results / "external-qualification-continuity"
    root.mkdir(mode=0o700, exist_ok=False)
    summaries = []
    states = []
    for cell in selected:  # Post-generation and serial; setup remains in run_continuity.
        episode = results / cell["id"]
        try:
            setup = json.loads((episode / "memory-setup.json").read_text())
            state = after_role_state(cell, episode, setup)
            state_run = root / cell["id"]
            state_run.mkdir(mode=0o700, parents=True, exist_ok=False)
            write_new(state_run / "post-role-state.json", state)
            states.append({"cell_id": cell["id"], "passed": state["passed"],
                           "post_export_sha256": state["export_sha256"]})
            response = json.loads((episode / "response.json").read_text())
            units = response["units"]
            if len(units) != 1 or units[0]["unit_id"] != cell["unit"]["unit_id"]:
                raise ValueError("continuity_native_unit_set_mismatch")
            versions = units[0]["versions"]
            if not versions:
                summaries.append({"cell_id": cell["id"], "status": "no_candidate_versions",
                                  "subject_defect": None, "post_role_state_passed": state["passed"]})
            for version in versions:
                try:
                    result = _result_from_version(cell, episode, version, root, checker, state)
                    result["post_role_state_passed"] = state["passed"]
                    summaries.append(result)
                except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
                    summaries.append({"cell_id": cell["id"], "variant": f"continuation-v{version.get('version')}",
                                      "status": "harness_unavailable", "subject_defect": None,
                                      "reason": type(error).__name__})
        except (OSError, ValueError, KeyError, TypeError) as error:
            summaries.append({"cell_id": cell["id"], "status": "setup_or_response_unavailable",
                              "subject_defect": None, "reason": type(error).__name__})
    index = {"schema": "opensocrates.go-ts.continuity-serial-qualification/1",
             "scheduled_cells": len(selected), "variants": summaries,
             "post_role_states": states, "model_calls": 0,
             "clarification_timing": "unassessable_without_complete_public_message_stream",
             "raw_memory_or_model_output_retained": False}
    write_new(root / "index.json", index)
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--freeze-sha256", required=True)
    args = parser.parse_args()
    parent = Path(__file__).resolve().parents[1]
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    from run_continuity import verify_freeze
    frozen = verify_freeze(args.freeze, args.freeze_sha256)
    result = qualify_all(args.results, frozen)
    print(json.dumps({"scheduled_cells": result["scheduled_cells"],
                      "variant_count": len(result["variants"]),
                      "post_role_states": len(result["post_role_states"])}, sort_keys=True))


if __name__ == "__main__":
    main()
