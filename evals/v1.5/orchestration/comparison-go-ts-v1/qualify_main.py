"""Serial external qualification of locked synthetic candidate versions.

This program never edits model artifacts. It runs only after every selected
episode has a terminal or startup marker. Unknown/sandbox-limited obligations
stay pending and are not counted as subject correctness defects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from external import qualify
from protocol import DESCRIPTOR, HERE, descriptor, main_cells, sha
from run_main import verify_freeze, write_new


def files_for_version(episode: Path, unit: dict[str, Any], version: dict[str, Any]) -> dict[str, bytes]:
    folder = episode / "candidate/versions" / unit["unit_id"] / f"v{version['version']}"
    expected = {item["path"]: item["sha256"] for item in version["artifacts"]}
    if set(expected) != set(unit["owned_paths"]):
        raise ValueError("version_artifact_set_mismatch")
    files = {}
    for name in unit["owned_paths"]:
        path = folder / name
        data = path.read_bytes()
        if "sha256:" + sha(data) != expected[name]:
            raise ValueError("version_bytes_differ_from_response")
        files[name] = data
    return files


def versions_for_cell(cell: dict[str, str], task: dict[str, Any],
                      episode: Path) -> list[tuple[str, str, dict[str, bytes], dict[str, Any]]]:
    response = json.loads((episode / "response.json").read_text())
    if cell["arm"] in {"A", "B"}:
        root = episode / "candidate/artifacts"
        files = {name: (root / name).read_bytes() for name in task["required_artifacts"]}
        expected = response.get("candidate_hashes") or {}
        if {name: "sha256:" + sha(data) for name, data in files.items()} != expected:
            raise ValueError("single_candidate_changed")
        return [("single-v1", "full", files, {"kind": "single_author_actual_candidate"})]
    by_id = {unit["unit_id"]: unit for unit in task["units"]}
    results = {item["unit_id"]: item for item in response["units"]}
    if set(results) != set(by_id):
        raise ValueError("native_unit_set_mismatch")
    analysis_unit = by_id["O-analysis"]
    document_unit = by_id["O-document"]
    analysis_versions = results["O-analysis"]["versions"]
    document_versions = results["O-document"]["versions"]
    variants: list[tuple[str, str, dict[str, bytes], dict[str, Any]]] = []
    for version in analysis_versions:
        files = files_for_version(episode, analysis_unit, version)
        variants.append((f"O-analysis-v{version['version']}", "analysis", files, {
            "kind": "actual_analysis_version", "analysis_version": version["version"],
            "native_qualified": version["qualified"], "document_version": None,
        }))
    qualified = [version for version in analysis_versions if version["qualified"]]
    if document_versions and len(qualified) != 1:
        raise ValueError("document_without_one_qualified_analysis_dependency")
    if qualified:
        dependency = qualified[0]
        analysis_files = files_for_version(episode, analysis_unit, dependency)
        for version in document_versions:
            files = {**analysis_files, **files_for_version(episode, document_unit, version)}
            variants.append((
                f"O-analysis-v{dependency['version']}-O-document-v{version['version']}",
                "full", files, {
                    "kind": "actual_document_on_qualified_analysis",
                    "analysis_version": dependency["version"],
                    "document_version": version["version"],
                    "document_native_qualified": version["qualified"],
                },
            ))
    return variants


def classification(structured: dict[str, Any] | None, process_exit: int) -> dict[str, Any]:
    if structured is None:
        return {"status": "harness_unavailable", "subject_defect": None,
                "reason": "structured_verifier_receipt_missing"}
    if structured.get("error") is not None:
        return {"status": "harness_unavailable", "subject_defect": None,
                "reason": "verifier_error"}
    checks = structured.get("checks") or []
    pending = [item["id"] for item in checks if item.get("status") == "unassessable"]
    failed = [item["id"] for item in checks if item.get("passed") is False
              and item.get("status") != "unassessable"]
    if pending and failed:
        return {"status": "mixed_failure_and_unassessable", "subject_defect": True,
                "failed_obligations": failed, "pending_obligations": pending}
    if pending:
        return {"status": "integration_pending_unassessable", "subject_defect": None,
                "pending_obligations": pending}
    if failed:
        return {"status": "deterministic_failure", "subject_defect": True,
                "failed_obligations": failed}
    if process_exit != 0 or not checks or not structured.get("passed"):
        return {"status": "harness_unavailable", "subject_defect": None,
                "reason": "incomplete_or_inconsistent_verifier_receipt"}
    return {"status": "deterministic_pass", "subject_defect": False,
            "passed_obligations": [item["id"] for item in checks]}


def all_generated(results: Path, selected: list[dict[str, str]]) -> None:
    for cell in selected:
        episode = results / cell["id"]
        if not (episode / "started.json").is_file():
            raise ValueError("cell_not_started:" + cell["id"])
        if not (episode / "terminal.json").is_file() and not (episode / "startup-failure.json").is_file():
            raise ValueError("generation_still_active_or_unknown:" + cell["id"])


def qualify_all(results: Path, freeze: dict[str, Any]) -> dict[str, Any]:
    selected = [cell for cell in main_cells() if cell["id"] in freeze["cell_ids"]]
    all_generated(results, selected)
    data = descriptor(tasks=set(freeze["task_descriptor_hashes"]))
    task = data["tasks"]["O"]
    fixtures = HERE / "fixtures"
    deps = Path(freeze["subject_dependency_root"])
    root = results / "external-qualification"
    root.mkdir(mode=0o700, exist_ok=False)
    summaries = []
    for cell in selected:  # Deliberately serial, after all generation.
        episode = results / cell["id"]
        try:
            variants = versions_for_cell(cell, task, episode)
        except (OSError, ValueError) as error:
            summaries.append({"cell_id": cell["id"], "status": "candidate_unavailable",
                              "reason": type(error).__name__})
            continue
        if not variants:
            summaries.append({"cell_id": cell["id"], "status": "blocked_dependency_or_no_versions"})
            continue
        for label, scope, files, lineage in variants:
            run = root / cell["id"] / label
            run.parent.mkdir(parents=True, exist_ok=True)
            try:
                receipt = qualify(task, fixtures, deps, files, run, scope=scope)
                result = classification(receipt["structured"], receipt["exit_code"])
                write_new(run / "receipt.json", receipt)
                summaries.append({"cell_id": cell["id"], "variant": label,
                                  "scope": scope, "lineage": lineage,
                                  "candidate_sha256": "sha256:" + sha(json.dumps(
                                      {name: "sha256:" + sha(data) for name, data in files.items()},
                                      sort_keys=True, separators=(",", ":")).encode()),
                                  **result})
            except (OSError, ValueError) as error:
                summaries.append({"cell_id": cell["id"], "variant": label,
                                  "scope": scope, "lineage": lineage,
                                  "status": "harness_unavailable", "subject_defect": None,
                                  "reason": type(error).__name__})
    result = {"schema": "opensocrates.go-ts.serial-qualification/1",
              "task": "O", "generation_complete_before_start": True,
              "scheduled_cells": len(selected), "variants": summaries,
              "model_calls": 0,
              "unassessable_count": sum(x["status"] == "integration_pending_unassessable" for x in summaries),
              "raw_oracle_tool_output_retained": False}
    write_new(root / "index.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--freeze-sha256", required=True)
    args = parser.parse_args()
    frozen = verify_freeze(args.freeze, args.freeze_sha256)
    result = qualify_all(args.results, frozen)
    print(json.dumps({"scheduled_cells": result["scheduled_cells"],
                      "variant_count": len(result["variants"]),
                      "unassessable_count": result["unassessable_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
