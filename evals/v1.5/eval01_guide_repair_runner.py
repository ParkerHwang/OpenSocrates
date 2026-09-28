#!/usr/bin/env python3
"""Run a new paired C/D cell against the revised installed recall guide."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from eval01_runner import (
    _join_existing_memory,
    _restore_source_artifact,
    _session,
    _source_digest,
)
from memory_pilot_runner import ROOT, _digest, _grade

FREEZE = Path(__file__).with_name("eval01-guide-repair-freeze.json")
PARENT = Path(__file__).with_name("memory-pilot-freeze.json")


def run(original: Path, output_root: Path | None) -> Path:
    freeze = json.loads(FREEZE.read_text())
    assert freeze["status"] == "frozen_before_repair_outcomes"
    assert (
        _digest(ROOT / "dist/opensocrates-1.4.0-codex-plugin.zip") == freeze["package_zip_sha256"]
    )
    assert (
        _digest(ROOT / "dist/codex/skills/opensocrates/references/assistance/guide.en.md")
        == freeze["guide_en_sha256"]
    )
    first = original / "D" / "first-artifact"
    original_d = original / "D" / "workspace"
    data = original / "D" / "data"
    assert first.is_dir() and original_d.is_dir() and data.is_dir()
    assert _source_digest(first) == freeze["first_artifact_source_sha256"]
    sys.path.insert(0, str(ROOT / "src"))
    from opensocrates.project_memory.registry import ProjectRegistry

    registry = ProjectRegistry(data).load()
    assert registry is not None and len(registry["projects"]) == 1
    project_id = next(iter(registry["projects"]))
    db = data / "projects" / project_id / "memory.sqlite3"
    assert _digest(db) == freeze["original_memory_store_sha256_before_join"]
    fixture = json.loads(PARENT.read_text())["lanes"]["EVAL-01"]
    base = output_root or Path(
        tempfile.mkdtemp(prefix="opensocrates-eval01-repair-", dir="/private/tmp")
    )
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    receipts = []
    for arm in ("C", "D"):
        pair = base / arm
        pair.mkdir(mode=0o700)
        workspace = pair / "workspace"
        subprocess.run(
            ["git", "-C", str(original_d), "worktree", "add", "-q", "--detach", str(workspace)],
            check=True,
        )
        _restore_source_artifact(first, workspace)
        assert _source_digest(workspace) == freeze["first_artifact_source_sha256"]
        arm_data = data if arm == "D" else pair / "data"
        if arm == "C":
            arm_data.mkdir(mode=0o700)
        workspace_id = _join_existing_memory(workspace, data, project_id) if arm == "D" else None
        (workspace / fixture["source_transition"]["added_untracked_file"]).write_text(
            fixture["source_transition"]["content"]
        )
        receipt = _session(
            base,
            f"repair-{arm}",
            arm,
            workspace,
            arm_data,
            fixture["followup_request"],
            project_id if arm == "D" else None,
            workspace_id,
            ROOT / "dist/opensocrates-1.4.0-codex-plugin.zip",
            ROOT / "dist/opensocrates-1.4.0-checksums.sha256",
        )
        receipt["grade"] = _grade("coding-untracked-caller", workspace)
        receipt["source_start_sha256"] = freeze["first_artifact_source_sha256"]
        receipt["source_after_sha256"] = _source_digest(workspace)
        receipts.append(receipt)
    result = {
        "schema": "opensocrates.v1.5.eval01-guide-repair/1.0.0",
        "status": "paired_repair_pilot",
        "freeze_sha256": _digest(FREEZE),
        "candidate_zip_sha256": freeze["package_zip_sha256"],
        "model": freeze["model"],
        "effort": freeze["effort"],
        "client": freeze["client"],
        "receipts": receipts,
        "exposure_gate": receipts[1]["successful_memory_calls"] >= 1,
        "quality_gate": all(all(item["grade"].values()) for item in receipts),
        "raw_local_evidence": str(base),
        "claim_boundary": freeze["claim_boundary"],
    }
    (base / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-pilot-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    print(run(args.original_pilot_root, args.output_root))


if __name__ == "__main__":
    main()
