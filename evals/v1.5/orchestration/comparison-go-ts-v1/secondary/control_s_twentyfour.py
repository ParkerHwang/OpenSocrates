#!/usr/bin/env python3
"""All 24 S cell routing control with synthetic versions and no model calls."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from qualify_s import assess_design, qualify_all, sha, versions_for_cell


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    runner = args.runner_root.resolve()
    output = args.output_root.resolve()
    assert not output.exists() and not args.receipt.exists()
    sys.path[:0] = [str(runner / "src"), str(runner / "evals/v1.5/orchestration/comparison-go-ts-v1")]
    import external
    import protocol
    from protocol import main_cells

    s_root = Path(__file__).resolve().parents[1] / "fixtures/s_incidentops"
    task = json.loads((s_root / "descriptor.json").read_text())["task"]
    cells = [cell for cell in main_cells() if cell["task"] == "S"]
    assert len(cells) == 24
    output.mkdir(mode=0o700, parents=True)
    summaries = []
    for cell in cells:
        episode = output / cell["id"]
        episode.mkdir()
        if cell["arm"] in {"A", "B"}:
            candidate_hashes = {}
            for name in task["required_artifacts"]:
                source = s_root / "private/controls/good" / name
                target = episode / "candidate/artifacts" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                candidate_hashes[name] = "sha256:" + sha(target.read_bytes())
            (episode / "response.json").write_text(json.dumps({"synthetic_control": True,
                "candidate_hashes": candidate_hashes}))
        else:
            units = []
            for unit in task["units"]:
                versions = []
                numbers = (1, 2) if unit["unit_id"] == "S-design" else (1,)
                for number in numbers:
                    artifacts = []
                    for name in unit["owned_paths"]:
                        data = (s_root / "private/controls/good" / name).read_bytes()
                        if unit["unit_id"] == "S-design" and number == 1 and name == "design.json":
                            value = json.loads(data)
                            value["examples"] = []
                            data = json.dumps(value).encode()
                        target = episode / "candidate/versions" / unit["unit_id"] / f"v{number}" / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        artifacts.append({"path": name, "sha256": "sha256:" + sha(data)})
                    versions.append({"version": number,
                                     "qualified": unit["unit_id"] != "S-design" or number == 2,
                                     "artifacts": artifacts})
                units.append({"unit_id": unit["unit_id"], "versions": versions})
            (episode / "response.json").write_text(json.dumps({"synthetic_control": True, "units": units}))
        variants = versions_for_cell(cell, task, episode)
        (episode / "started.json").write_text(json.dumps({"synthetic_control": True, "role_model_calls": 0}))
        (episode / "terminal.json").write_text(json.dumps({"synthetic_control": True, "role_model_calls": 0}))
        design_results = [assess_design(files) for _, scope, files, _ in variants if scope == "design"]
        full = [entry for entry in variants if entry[1] == "full"]
        correct_lineage = (len(full) == 1 and
                           (cell["arm"] in {"A", "B"} or full[0][3]["design_version"] == 2))
        expected_design_status = [True] if cell["arm"] in {"A", "B"} else [False, True]
        passed = correct_lineage and [item["passed"] for item in design_results] == expected_design_status
        summaries.append({"cell_id": cell["id"], "arm": cell["arm"],
                          "variant_count": len(variants), "design_assessments": expected_design_status,
                          "qualified_design_for_full": full[0][3].get("design_version") if full else None,
                          "passed": passed})
    original_descriptor, original_qualify = protocol.descriptor, external.qualify
    def synthetic_descriptor(*, tasks=None):
        assert tasks == {"S"}
        return {"tasks": {"S": task}}
    def synthetic_qualify(task_value, fixtures, deps, files, run, *, scope="full"):
        assert task_value is task and scope == "full" and set(files) == set(task["required_artifacts"])
        run.mkdir(mode=0o700, parents=True, exist_ok=False)
        if run.parent.name == cells[0]["id"]:
            structured = {"passed": False, "checks": [
                {"id": "s_api_contract", "passed": True},
                {"id": "s_browser_network_ui", "passed": False, "status": "unassessable"},
            ]}
            return {"scope": scope, "exit_code": 1, "structured": structured,
                    "synthetic_control": True, "raw_output_retained": False}
        return {"scope": scope, "exit_code": 0,
                "structured": {"passed": True, "checks": [{"id": "s_external_stub", "passed": True}]},
                "synthetic_control": True, "raw_output_retained": False}
    protocol.descriptor, external.qualify = synthetic_descriptor, synthetic_qualify
    try:
        index = qualify_all(output, {"s_browser_transport_decision": {
            "status": "allow_unassessable_as_pending", "attribution": "parent_explicit",
            "reference": "synthetic:secondary-control"},
            "cell_ids": [cell["id"] for cell in cells], "task_descriptor_hashes": {"S": "synthetic"},
            "subject_dependency_root": "/private/tmp/opensocrates-go-ts-deps-20260928"})
    finally:
        protocol.descriptor, external.qualify = original_descriptor, original_qualify
    postgen_ok = (len(index["variants"]) == 60 and index["scheduled_cells"] == 24
                  and index["unassessable_count"] == 1
                  and sum(item.get("status") == "integration_pending_unassessable" and item.get("subject_defect") is None for item in index["variants"]) == 1)
    result = {"schema": "opensocrates.go-ts.secondary-S24-control/1",
              "passed": all(item["passed"] for item in summaries) and postgen_ok,
              "scheduled_cells": len(cells), "variants": sum(item["variant_count"] for item in summaries),
              "postgen_variants": len(index["variants"]),
              "postgen_unassessable_count": index["unassessable_count"],
              "arms": {arm: sum(item["arm"] == arm for item in summaries) for arm in ("A", "B", "C", "D")},
              "cells": summaries, "role_model_calls": 0, "synthetic_control_only": True,
              "full_external_qualification_stubbed": True,
              "S_descriptor_sha256": sha((s_root / "descriptor.json").read_bytes())}
    with args.receipt.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"passed": result["passed"], "cells": len(cells),
                      "variants": result["variants"], "role_model_calls": 0}, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
