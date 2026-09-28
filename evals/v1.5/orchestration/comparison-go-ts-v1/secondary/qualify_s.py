#!/usr/bin/env python3
"""S-specific post-generation lineage and qualification; no model invocation.

The shared runner still owns dispatch, native roles, candidate staging, the
strict child sandbox, and receipt classification. This module only selects
actual S versions and feeds them to those existing components.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def version_files(episode: Path, unit: dict[str, Any], version: dict[str, Any]) -> dict[str, bytes]:
    """Read exact native version bytes, rejecting substitutions and partials."""
    expected = {item["path"]: item["sha256"] for item in version["artifacts"]}
    if set(expected) != set(unit["owned_paths"]):
        raise ValueError("S_version_artifact_set_mismatch")
    folder = episode / "candidate/versions" / unit["unit_id"] / f"v{version['version']}"
    result = {}
    for name in unit["owned_paths"]:
        path = folder / name
        if not path.resolve().is_relative_to(folder.resolve()) or path.is_symlink():
            raise ValueError("S_version_symlink")
        data = path.read_bytes()
        if "sha256:" + sha(data) != expected[name]:
            raise ValueError("S_version_bytes_differ_from_native_receipt")
        result[name] = data
    return result


def versions_for_cell(cell: dict[str, str], task: dict[str, Any], episode: Path) -> list[tuple[str, str, dict[str, bytes], dict[str, Any]]]:
    """Return design versions separately, then only real qualified-design joins."""
    response = json.loads((episode / "response.json").read_text())
    units = {unit["unit_id"]: unit for unit in task["units"]}
    if set(units) != {"S-design", "S-implementation"}:
        raise ValueError("S_unit_graph_changed")
    design_owned = set(units["S-design"]["owned_paths"])
    if cell["arm"] in {"A", "B"}:
        files = {}
        for name in task["required_artifacts"]:
            path = episode / "candidate/artifacts" / name
            if not path.resolve().is_relative_to((episode / "candidate/artifacts").resolve()) or path.is_symlink():
                raise ValueError("S_single_symlink")
            files[name] = path.read_bytes()
        if {name: "sha256:" + sha(data) for name, data in files.items()} != response.get("candidate_hashes"):
            raise ValueError("S_single_candidate_changed")
        design = {name: files[name] for name in units["S-design"]["owned_paths"]}
        return [
            ("single-v1-design", "design", design, {"kind": "single_author_actual_design"}),
            ("single-v1-full", "full", files, {"kind": "single_author_actual_candidate"}),
        ]
    results = {unit["unit_id"]: unit for unit in response["units"]}
    if set(results) != set(units):
        raise ValueError("S_native_unit_set_mismatch")
    design_versions = results["S-design"]["versions"]
    implementation_versions = results["S-implementation"]["versions"]
    variants = []
    for version in design_versions:
        files = version_files(episode, units["S-design"], version)
        variants.append((f"S-design-v{version['version']}", "design", files, {
            "kind": "actual_design_version", "design_version": version["version"],
            "design_native_qualified": version["qualified"], "implementation_version": None,
        }))
    qualified = [version for version in design_versions if version["qualified"]]
    if implementation_versions and len(qualified) != 1:
        raise ValueError("S_implementation_without_one_qualified_design_dependency")
    if qualified:
        dependency = qualified[0]
        design_files = version_files(episode, units["S-design"], dependency)
        if set(design_files) != design_owned:
            raise ValueError("S_design_owned_set_changed")
        for version in implementation_versions:
            implementation_files = version_files(episode, units["S-implementation"], version)
            files = {**design_files, **implementation_files}
            if set(files) != set(task["required_artifacts"]):
                raise ValueError("S_full_owned_set_mismatch")
            variants.append((
                f"S-design-v{dependency['version']}-S-implementation-v{version['version']}",
                "full", files, {
                    "kind": "actual_implementation_on_qualified_design",
                    "design_version": dependency["version"],
                    "implementation_version": version["version"],
                    "implementation_native_qualified": version["qualified"],
                },
            ))
    return variants


def assess_design(files: dict[str, bytes]) -> dict[str, Any]:
    """Bounded outer structure evidence; no claim of design judgment quality."""
    checks = []
    try:
        design = json.loads(files["design.json"].decode("utf-8"))
        markdown = files["design.md"].decode("utf-8")
        checks.append({"id": "s_design_utf8_json", "passed": isinstance(design, dict), "detail": "UTF-8 JSON object"})
        required = {"api", "state_transitions", "ownership", "persistence", "migration", "compatibility", "examples"}
        checks.append({"id": "s_design_contract_sections", "passed": required <= design.keys() and all(design[key] for key in required if key in design), "detail": "public contract sections present"})
        examples = design.get("examples")
        examples_ok = isinstance(examples, list) and len(examples) >= 4 and all(isinstance(item, dict) and item.get("request") and item.get("expected") for item in examples)
        checks.append({"id": "s_design_examples", "passed": bool(examples_ok), "detail": "four or more request/expected examples"})
        checks.append({"id": "s_design_markdown", "passed": len(markdown.strip()) > 300, "detail": "nonempty explanatory Markdown"})
    except (KeyError, UnicodeError, json.JSONDecodeError, TypeError):
        checks.append({"id": "s_design_utf8_json", "passed": False, "detail": "design files missing or invalid"})
    return {"scope": "design", "passed": all(item["passed"] for item in checks),
            "checks": checks,
            "limitations": ["Design correctness and usefulness require separate independent judgment; these are structural checks."]}


def decision(freeze: dict[str, Any]) -> dict[str, str]:
    value = freeze.get("s_browser_transport_decision")
    if not isinstance(value, dict) or value.get("status") != "allow_unassessable_as_pending" or value.get("attribution") != "parent_explicit" or not value.get("reference"):
        raise ValueError("S_separate_browser_transport_decision_missing")
    return value


def bundle_hash(files: dict[str, bytes]) -> str:
    value = {name: "sha256:" + sha(data) for name, data in files.items()}
    return "sha256:" + sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def qualify_all(results: Path, freeze: dict[str, Any]) -> dict[str, Any]:
    decision(freeze)
    parent = Path(__file__).resolve().parents[1]
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    from external import qualify
    from protocol import HERE, descriptor, main_cells
    from qualify_main import all_generated, classification
    from run_main import write_new

    selected = [cell for cell in main_cells() if cell["task"] == "S" and cell["id"] in freeze["cell_ids"]]
    if len(selected) != 24 or set(freeze["task_descriptor_hashes"]) != {"S"}:
        raise ValueError("S_frozen_cell_or_task_set_invalid")
    all_generated(results, selected)
    task = descriptor(tasks={"S"})["tasks"]["S"]
    fixtures = HERE / "fixtures"
    deps = Path(freeze["subject_dependency_root"])
    root = results / "external-qualification-S"
    root.mkdir(mode=0o700, exist_ok=False)
    summaries = []
    for cell in selected:  # Serial after all generation; no extra model calls.
        episode = results / cell["id"]
        try:
            variants = versions_for_cell(cell, task, episode)
        except (OSError, ValueError, KeyError, TypeError) as error:
            summaries.append({"cell_id": cell["id"], "status": "candidate_unavailable", "subject_defect": None,
                              "reason": type(error).__name__})
            continue
        if not variants:
            summaries.append({"cell_id": cell["id"], "status": "blocked_dependency_or_no_versions", "subject_defect": None})
            continue
        for label, scope, files, lineage in variants:
            run = root / cell["id"] / label
            run.parent.mkdir(parents=True, exist_ok=True)
            try:
                if scope == "design":
                    run.mkdir(mode=0o700, exist_ok=False)
                    structured = assess_design(files)
                    receipt = {"schema": "opensocrates.go-ts.S-design-qualification/1",
                               "scope": "design", "exit_code": 0, "structured": structured,
                               "raw_output_retained": False}
                else:
                    receipt = qualify(task, fixtures, deps, files, run, scope="full")
                    structured = receipt["structured"]
                result = classification(structured, receipt["exit_code"])
                write_new(run / "receipt.json", receipt)
                summaries.append({"cell_id": cell["id"], "variant": label,
                                  "scope": scope, "lineage": lineage,
                                  "candidate_sha256": bundle_hash(files), **result})
            except (OSError, ValueError, KeyError, TypeError) as error:
                summaries.append({"cell_id": cell["id"], "variant": label,
                                  "scope": scope, "lineage": lineage,
                                  "status": "harness_unavailable", "subject_defect": None,
                                  "reason": type(error).__name__})
    index = {"schema": "opensocrates.go-ts.S-serial-qualification/1", "task": "S",
             "generation_complete_before_start": True, "scheduled_cells": len(selected),
             "variants": summaries, "model_calls": 0,
             "browser_transport_decision": freeze["s_browser_transport_decision"],
             "unassessable_count": sum(item["status"] == "integration_pending_unassessable" for item in summaries),
             "raw_oracle_tool_output_retained": False}
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
    from run_main import verify_freeze
    frozen = verify_freeze(args.freeze, args.freeze_sha256)
    result = qualify_all(args.results, frozen)
    print(json.dumps({"scheduled_cells": result["scheduled_cells"],
                      "variant_count": len(result["variants"]),
                      "unassessable_count": result["unassessable_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
