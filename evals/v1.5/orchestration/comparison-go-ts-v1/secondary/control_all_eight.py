#!/usr/bin/env python3
"""Eight-cell synthetic terminal replay using real disposable memory setup.

This is a no-model adapter control. Synthetic terminal markers and good fixture
bytes stay in the supplied disposable output root, never in study results.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from qualify_continuity import qualify_all, sha


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
    from continuity_memory import fixture, setup_one

    fixtures = runner / "evals/v1.5/orchestration/comparison-go-ts-v1/fixtures"
    _, description = fixture(fixtures)
    cells = description["cells"]
    assert len(cells) == 8
    output.mkdir(mode=0o700, parents=True)
    for cell in cells:
        episode = output / cell["id"]
        setup = setup_one(cell, fixtures, episode)
        (episode / "memory-setup.json").write_text(json.dumps(setup, sort_keys=True))
        artifacts = []
        for name in cell["required_artifacts"]:
            source = fixtures / "continuity/private/controls/good" / cell["locale"] / name
            target = episode / "candidate/versions/continuation/v1" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            artifacts.append({"path": name, "sha256": "sha256:" + sha(target.read_bytes())})
        (episode / "response.json").write_text(json.dumps({"synthetic_control": True,
            "units": [{"unit_id": "continuation", "versions": [{"version": 1, "qualified": True, "artifacts": artifacts}]}]}))
        (episode / "started.json").write_text(json.dumps({"synthetic_control": True, "role_model_calls": 0}))
        (episode / "terminal.json").write_text(json.dumps({"synthetic_control": True, "role_model_calls": 0}))
    index = qualify_all(output, {"cell_ids": [cell["id"] for cell in cells]})
    passed = (index["scheduled_cells"] == 8 and len(index["post_role_states"]) == 8
              and all(item["passed"] for item in index["post_role_states"])
              and len(index["variants"]) == 8
              and all(item.get("status") == "deterministic_pass" and item.get("subject_defect") is False
                      for item in index["variants"]))
    result = {"schema": "opensocrates.go-ts.secondary-eight-control/1",
              "passed": passed, "scheduled_cells": 8,
              "post_role_state_passes": sum(item["passed"] for item in index["post_role_states"]),
              "qualified_versions": sum(item.get("status") == "deterministic_pass" for item in index["variants"]),
              "memory_conditions": {condition: sum(cell["condition"] == condition for cell in cells)
                                    for condition in ("scoped_disposable_memory", "disabled_memory_with_equivalent_note")},
              "role_model_calls": 0, "synthetic_terminal_markers": True,
              "raw_memory_records_retained": False,
              "descriptor_sha256": sha((fixtures / "continuity/descriptor.json").read_bytes()),
              "qualifier_sha256": sha(Path(__file__).with_name("qualify_continuity.py").read_bytes())}
    with args.receipt.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"passed": passed, "cells": 8, "role_model_calls": 0}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
