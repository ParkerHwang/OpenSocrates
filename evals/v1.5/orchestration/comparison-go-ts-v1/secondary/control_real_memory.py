#!/usr/bin/env python3
"""Disposable, no-model integration control for the continuity adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from qualify_continuity import _result_from_version, after_role_state, sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    runner = args.runner_root.resolve()
    root = args.output_root.resolve()
    assert not root.exists() and not args.receipt.exists()
    sys.path[:0] = [str(runner / "src"), str(runner / "evals/v1.5/orchestration/comparison-go-ts-v1")]
    from continuity_memory import call, fixture, setup_one, uid
    from opensocrates.project_memory.registry import ProjectRegistry

    fixtures = runner / "evals/v1.5/orchestration/comparison-go-ts-v1/fixtures"
    _, description = fixture(fixtures)
    root.mkdir(mode=0o700, parents=True)
    results = []
    for condition in ("scoped_disposable_memory", "disabled_memory_with_equivalent_note"):
        cell = next(item for item in description["cells"] if item["model"] == "gpt-6-sol" and item["locale"] == "en" and item["condition"] == condition)
        episode = root / condition
        setup = setup_one(cell, fixtures, episode)
        (episode / "memory-setup.json").write_text(json.dumps(setup))
        state = after_role_state(cell, episode, setup)
        version_dir = episode / "candidate/versions/continuation/v1"
        version_dir.mkdir(parents=True)
        artifacts = []
        for name in cell["required_artifacts"]:
            source = fixtures / "continuity/private/controls/good/en" / name
            target = version_dir / name
            shutil.copyfile(source, target)
            artifacts.append({"path": name, "sha256": "sha256:" + sha(target.read_bytes())})
        result = _result_from_version(cell, episode, {"version": 1, "qualified": True, "artifacts": artifacts}, episode / "qualification", fixtures / "continuity/private/verify_continuity.py", state)
        expected_projection = "available" if condition == "scoped_disposable_memory" else "disabled"
        results.append({"control": condition, "setup_projection_status": setup["projection_status"],
                        "post_role_state_passed": state["passed"], "version_status": result["status"],
                        "passed": setup["projection_status"] == expected_projection and state["passed"] and result["status"] == "deterministic_pass" and result["subject_defect"] is False})
    cell = next(item for item in description["cells"] if item["model"] == "gpt-6-luna" and item["locale"] == "en" and item["condition"] == "scoped_disposable_memory")
    episode = root / "synthetic-post-setup-mutation"
    setup = setup_one(cell, fixtures, episode)
    identities = {"project_id": setup["project_id"], "workspace_id": setup["workspace_id"], "task_id": None}
    registry = ProjectRegistry(episode / "private-store")
    new_id = uid("secondary:unauthorized-control-record")
    call(registry, identities, "record", {
        "idempotency_key": uid("secondary:unauthorized-control-write"),
        "record_id": new_id, "expected_record_version": 0,
        "kind": "decision", "scope": {"level": "project"},
        "summary": "synthetic post-setup mutation detector",
        "origin": {"producer_kind": "agent", "source_reference": None, "attestation": "agent_reported"},
        "support": "agent_reported", "source_refs": [], "snapshot_id": None,
        "revalidation": {"dependency_paths": [], "negative_claim": False, "on_change": "not_applicable"},
    }, "secondary:unauthorized-control-write")
    changed = after_role_state(cell, episode, setup)
    failed = {item["id"] for item in changed["checks"] if not item["passed"]}
    mutation_passed = not changed["passed"] and {"continuity_memory_export_after_role", "continuity_persisted_ids_after_role"} <= failed
    results.append({"control": "synthetic-post-setup-mutation", "passed": mutation_passed,
                    "detected_checks": sorted(failed)})
    packet = {"schema": "opensocrates.go-ts.secondary-continuity-control/1",
              "passed": all(item["passed"] for item in results), "controls": results,
              "runner_fixture_descriptor_sha256": sha((fixtures / "continuity/descriptor.json").read_bytes()),
              "runner_memory_setup_sha256": sha((fixtures / "continuity/private/harness_setup.json").read_bytes()),
              "secondary_qualifier_sha256": hashlib.sha256((Path(__file__).with_name("qualify_continuity.py")).read_bytes()).hexdigest(),
              "role_model_calls": 0, "raw_memory_records_retained": False,
              "meaning": "Real disposable memory API and exact private checker controls; no subject outcome."}
    with args.receipt.open("x", encoding="utf-8") as out:
        json.dump(packet, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"passed": packet["passed"], "controls": len(results), "role_model_calls": 0}, sort_keys=True))
    return 0 if packet["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
