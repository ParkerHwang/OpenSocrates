"""Verify frozen inputs, complete attempt accounting and retained outcome bytes.

This postprocessing check neither invokes a model nor changes a candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import analyze

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST_SHA256 = "8fafe6f815d30724ac4f5568cf494bcfd0a4d38dfe56de0054aebf8e3732c00e"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(storage=None, complete=False):
    assert sha(HERE / "manifest.json") == MANIFEST_SHA256
    manifest = read(HERE / "manifest.json")
    for path, digest in manifest["files"].items():
        assert sha(ROOT / path) == digest, path
    assert len({cell["id"] for cell in manifest["cells"]}) == 18
    assert len({cell["task_id"] for cell in manifest["cells"]}) == 18
    terminal = attempted = completed = timeouts = retained = 0
    issues = []
    for cell in manifest["cells"]:
        directory = HERE / "results" / cell["id"]
        if not directory.is_dir():
            assert not complete, f"missing cell: {cell['id']}"
            continue
        started = analyze.optional(directory / "call.started.json")
        call = analyze.optional(directory / "call.json")
        failure = analyze.optional(directory / "harness-failure.json")
        skipped = analyze.optional(directory / "skipped.json")
        attempted += started is not None
        if call is None and failure is None and skipped is None:
            assert not complete, f"unfinished cell: {cell['id']}"
            continue
        terminal += 1
        if skipped:
            assert started is None and skipped["call_attempted"] is False
            continue
        cleanup = read(directory / "cleanup.json")
        assert cleanup["auth_copy_removed"] is True
        if storage:
            assert not (storage / cell["id"] / "profile/home/.codex/auth.json").exists()
        if failure:
            assert failure["call_attempted"] == (started is not None)
            issues.append({"id": cell["id"], "kind": "harness_failure", "evidence": failure})
        if call is None:
            continue
        assert started is not None
        assert call["attempt"] == started["attempt"] == 1
        for key, value in cell.items():
            assert call[key] == started[key] == value, (cell["id"], key)
        assert call["client_sha256"] == manifest["runtime"]["client"]["sha256"]
        assert call["package_sha256"] == manifest["arms"][cell["arm"]].get("archive_sha256")
        assert call["process_success"] == (
            call["exit_code"] == 0 and call["turn_completed"] and not call["timed_out"]
        )
        completed += call["process_success"]
        timeouts += call["timed_out"]
        for key in analyze.KEYS:
            value = call["usage"].get(key)
            assert value is None or type(value) is int and value >= 0, (cell["id"], key)
            if not call.get("usage_reports"):
                assert value is None, (cell["id"], "invented missing usage", key)
        assert call["billed_cost"] is None and call["backend_model_echo"] is None
        assert len(call["tool_actions"]) == call["tool_actions_started_or_completed"]
        assert len(call["commands"]) <= len(call["tool_actions"])
        if complete:
            if cell["task"] == "coding":
                assert (directory / "own-tests.json").is_file()
                build = read(directory / "build.json")
                if build["exit_code"] == 0 and not build["timeout"]:
                    command = read(directory / "acceptance-command.json")
                    acceptance = analyze.optional(directory / "acceptance.json")
                    if acceptance is None:
                        assert command["timeout"] or command["exit_code"] != 0
                        issues.append(
                            {"id": cell["id"], "kind": "acceptance_harness_did_not_finish"}
                        )
                    else:
                        assert acceptance["group_count"] == len(acceptance["groups"]) == 28
                        assert acceptance["passed_count"] == sum(
                            group["passed"] for group in acceptance["groups"]
                        )
            else:
                command = read(directory / "office-check-command.json")
                checks = analyze.optional(directory / "office-checks.json")
                if checks is None:
                    assert command["timeout"] or command["exit_code"] != 0
                    issues.append({"id": cell["id"], "kind": "office_checker_did_not_finish"})
        protected = read(directory / "protected-inputs.json")
        if not protected["unchanged"]:
            issues.append({"id": cell["id"], "kind": "protected_input_changed"})
        if storage:
            actual = all(
                (storage / cell["id"] / "workspace" / p).is_file()
                and sha(storage / cell["id"] / "workspace" / p) == d
                for p, d in protected["sha256"].items()
            )
            assert actual == protected["unchanged"], (
                cell["id"],
                "protected state changed after capture",
            )
        inventory = read(directory / "artifact-inventory.json")
        exported = {item["path"]: item for item in inventory if item["retained"]}
        for path, item in exported.items():
            assert sha(directory / "snapshot" / path) == item["export_sha256"], (cell["id"], path)
            retained += 1
        if complete and cell["task"] == "coding":
            acceptance = analyze.optional(directory / "acceptance.json")
            if acceptance:
                qualified_sources = dict(acceptance["source_identity"]["source_files"])
                for path, item in exported.items():
                    if path.endswith(".go") or path in ("go.mod", "go.sum"):
                        assert qualified_sources.get(path) == item["sha256"], (
                            cell["id"],
                            "qualified source differs from generation artifact",
                            path,
                        )
        if cell["arm"] == "v15":
            adapter = exported.get("native_tool.py")
            expected = manifest["files"]["evals/v1.5/hard-tasks/v1/native_tool.py"]
            if not adapter or adapter["sha256"] != expected:
                issues.append({"id": cell["id"], "kind": "native_adapter_changed_or_missing"})
        for receipt in (directory / "call.json", directory / "prompt.json"):
            text = receipt.read_text(encoding="utf-8")
            assert not re.search(
                r"(?<![A-Za-z0-9_])sk-(?:proj-)?[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{30,}\.", text
            )
    if complete:
        assert terminal == 18
        assert read(HERE / "summary.json") == analyze.summary()
        lock = read(HERE / "outcomes.lock.json")
        assert lock == analyze.lock(), "outcome file set or digest changed after lock"
        assert read(HERE / "numeric-audit.json") == analyze.audit(), "portable timing audit"
        if storage:
            assert read(HERE / "numeric-audit.json") == analyze.audit(storage)
        reviewed = []
        for path in (HERE / "review").glob("office-batch*.assessments.json"):
            assessment = read(path)
            assert assessment["human_scores"] is None and assessment["blinding"] == "unblinded"
            review_lock = read(HERE / assessment["input_lock"])
            for name, digest in review_lock["files"].items():
                assert sha(HERE / name) == digest, ("changed review input", name)
            for review in assessment["reviews"]:
                reviewed.append(review["cell"])
                if review["scores"] is not None:
                    assert len(review["scores"]) == 5
                    assert all(
                        type(value) is int and 0 <= value <= 4
                        for value in review["scores"].values()
                    )
                    assert review["total"] == sum(review["scores"].values())
                else:
                    assert review["total"] is None
        assert sorted(reviewed) == sorted(
            cell["id"] for cell in manifest["cells"] if cell["task"] == "office"
        )
    return {
        "status": "pass",
        "manifest_sha256": MANIFEST_SHA256,
        "frozen_files": len(manifest["files"]),
        "terminal_cells": terminal,
        "attempted_calls": attempted,
        "completed_cli_turns": completed,
        "timeouts": timeouts,
        "retained_artifacts": retained,
        "recorded_issues": issues,
        "complete_verification": complete,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", type=Path)
    parser.add_argument("--complete", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.storage, arguments.complete), indent=2))
