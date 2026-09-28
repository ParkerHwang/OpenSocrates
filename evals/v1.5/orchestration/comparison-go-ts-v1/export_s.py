"""Post-call S24 export with the frozen S-specific qualification directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


EPISODE_FILES = (
    "started.json", "terminal.json", "startup-failure.json", "child-failure.json",
    "summary.json", "response.json", "observation.jsonl", "argv-map.jsonl",
)
RECEIPT_REQUIRED_STATUSES = {
    "deterministic_pass", "deterministic_failure", "mixed_failure_and_unassessable",
    "integration_pending_unassessable",
}
FORBIDDEN_COMPONENTS = {
    "auth.json", "private", "private-store", "raw-events.jsonl", "transcript.jsonl",
    "reasoning.json", "tool-output.log", "candidate-copy", ".eval-home", ".eval-server",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe_export_file:" + str(path))
    return path.read_bytes()


def require_directory(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("unsafe_or_missing_" + label)


def require_disjoint_output(output: Path, results: Path, checkout: Path) -> None:
    target = output.resolve(strict=False)
    for protected in (results.resolve(), checkout.resolve()):
        if target == protected or protected in target.parents:
            raise ValueError("S_export_output_inside_results_or_execution_checkout")


def owned_paths(task: dict) -> tuple[set[str], dict[str, set[str]]]:
    required = set(task["required_artifacts"])
    by_unit = {unit["unit_id"]: set(unit["owned_paths"]) for unit in task["units"]}
    if set(by_unit) != {"S-design", "S-implementation"} or set.union(*by_unit.values()) != required:
        raise ValueError("S_owned_path_manifest_mismatch")
    return required, by_unit


def allowed_candidate_path(path: Path, candidate: Path, required: set[str],
                           by_unit: dict[str, set[str]], arm: str) -> bool:
    parts = path.relative_to(candidate).parts
    if len(parts) >= 2 and parts[0] == "artifacts":
        return str(Path(*parts[1:])) in required
    if len(parts) >= 4 and parts[0] == "versions":
        unit, version = parts[1:3]
        if unit == "single":
            return arm in {"A", "B"} and version == "v1" and str(Path(*parts[3:])) in required
        return (unit in by_unit and re.fullmatch(r"v[1-9][0-9]*", version) is not None
                and arm in {"C", "D"} and str(Path(*parts[3:])) in by_unit[unit])
    return False


def approved_variant(label: str, scope: str) -> bool:
    if label in {"single-v1-design", "single-v1-full"}:
        return scope == ("design" if label.endswith("design") else "full")
    if re.fullmatch(r"S-design-v[1-9][0-9]*", label):
        return scope == "design"
    if re.fullmatch(r"S-design-v[1-9][0-9]*-S-implementation-v[1-9][0-9]*", label):
        return scope == "full"
    return False


def native_version_hashes(response: dict, required: set[str],
                          by_unit: dict[str, set[str]]) -> dict[str, str]:
    result = {}
    units = {unit["unit_id"]: unit for unit in response.get("units", [])}
    if set(units) != set(by_unit):
        raise ValueError("S_native_unit_set_mismatch")
    for unit_id, unit in units.items():
        for version in unit.get("versions", []):
            number = version["version"]
            if type(number) is not int or number < 1:
                raise ValueError("S_native_version_number_invalid")
            artifacts = {row["path"]: row["sha256"] for row in version["artifacts"]}
            if set(artifacts) != by_unit[unit_id]:
                raise ValueError("S_native_version_path_set_mismatch")
            for name, expected in artifacts.items():
                key = f"versions/{unit_id}/v{number}/{name}"
                if key in result:
                    raise ValueError("S_native_version_duplicate")
                result[key] = expected
    return result


def candidate_lineage(episode: Path, candidate: Path, required: set[str],
                      by_unit: dict[str, set[str]]) -> None:
    response_path = episode / "response.json"
    if not response_path.is_file():
        if any(candidate.rglob("*")):
            raise ValueError("S_candidate_without_response")
        return
    response = json.loads(read_regular(response_path))
    arm = episode.name.rsplit("-", 1)[-1]
    if arm in {"A", "B"}:
        expected = response.get("candidate_hashes") or {}
        actual = {}
        root = candidate / "artifacts"
        if root.exists():
            for path in root.rglob("*"):
                if path.is_file():
                    actual[str(path.relative_to(root))] = "sha256:" + sha(read_regular(path))
        if actual != expected:
            raise ValueError("S_single_candidate_hash_lineage_mismatch")
        if set(actual) not in (set(), required):
            raise ValueError("S_single_candidate_artifact_set_mismatch")
        version_root = candidate / "versions/single/v1"
        versioned = {}
        if version_root.exists():
            for path in version_root.rglob("*"):
                if path.is_file():
                    versioned[str(path.relative_to(version_root))] = "sha256:" + sha(read_regular(path))
        if versioned != expected or versioned != actual:
            raise ValueError("S_single_version_copy_hash_lineage_mismatch")
        return
    expected_versions = native_version_hashes(response, required, by_unit)
    actual_versions = {}
    version_root = candidate / "versions"
    if version_root.exists():
        for path in version_root.rglob("*"):
            if path.is_file():
                key = "versions/" + str(path.relative_to(version_root))
                actual_versions[key] = "sha256:" + sha(read_regular(path))
    if actual_versions != expected_versions:
        raise ValueError("S_orchestrated_version_hash_lineage_mismatch")
    units = {unit["unit_id"]: unit for unit in response["units"]}
    qualified = {}
    for unit_id in by_unit:
        versions = [v for v in units[unit_id]["versions"] if v["qualified"] is True]
        if len(versions) > 1:
            raise ValueError("S_multiple_native_qualified_versions")
        if versions:
            paths = {row["path"]: row["sha256"] for row in versions[0]["artifacts"]}
            if set(paths) != by_unit[unit_id] or set(qualified) & set(paths):
                raise ValueError("S_qualified_owned_path_mismatch")
            qualified.update(paths)
    published = candidate / "artifacts"
    actual_published = {}
    if published.exists():
        for path in published.rglob("*"):
            if path.is_file():
                name = str(path.relative_to(published))
                actual_published[name] = "sha256:" + sha(read_regular(path))
    if actual_published != qualified:
        raise ValueError("S_published_artifact_not_exact_qualified_union")


def expected_variants(episode: Path, arm: str) -> set[str]:
    response_path = episode / "response.json"
    if not response_path.is_file():
        return set()
    response = json.loads(read_regular(response_path))
    if arm in {"A", "B"}:
        if not response.get("candidate_hashes") or not (episode / "candidate/artifacts").is_dir():
            return set()
        return {"single-v1-design", "single-v1-full"}
    units = {unit["unit_id"]: unit for unit in response.get("units", [])}
    if set(units) != {"S-design", "S-implementation"}:
        return set()
    design = units["S-design"].get("versions", [])
    implementation = units["S-implementation"].get("versions", [])
    variants = {f"S-design-v{v['version']}" for v in design}
    qualified = [v for v in design if v["qualified"] is True]
    if implementation:
        if len(qualified) != 1:
            raise ValueError("S_implementation_without_single_qualified_design")
        variants.update(f"S-design-v{qualified[0]['version']}-S-implementation-v{v['version']}"
                        for v in implementation)
    return variants


def indexed_bundle_hash(episode: Path, label: str, required: set[str],
                        by_unit: dict[str, set[str]]) -> str:
    candidate = episode / "candidate"
    if label.startswith("single-v1-"):
        names = by_unit["S-design"] if label.endswith("design") else required
        files = {name: read_regular(candidate / "artifacts" / name) for name in names}
    else:
        match = re.fullmatch(r"S-design-v([1-9][0-9]*)(?:-S-implementation-v([1-9][0-9]*))?", label)
        if match is None:
            raise ValueError("S_indexed_bundle_variant_invalid")
        design_v, implementation_v = match.groups()
        files = {name: read_regular(candidate / "versions/S-design" / ("v" + design_v) / name)
                 for name in by_unit["S-design"]}
        if implementation_v is not None:
            files.update({name: read_regular(candidate / "versions/S-implementation" / ("v" + implementation_v) / name)
                          for name in by_unit["S-implementation"]})
            response = json.loads(read_regular(episode / "response.json"))
            design_unit = next(unit for unit in response["units"] if unit["unit_id"] == "S-design")
            native_design = next((v for v in design_unit["versions"] if v["version"] == int(design_v)), None)
            if native_design is None or native_design["qualified"] is not True:
                raise ValueError("S_indexed_full_dependency_not_native_qualified")
    manifest = {name: "sha256:" + sha(data) for name, data in files.items()}
    return "sha256:" + sha(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())


def frozen_context(freeze_path: Path, freeze_sha: str) -> tuple[dict, dict]:
    if sha(read_regular(freeze_path)) != freeze_sha:
        raise ValueError("S_freeze_sha256_mismatch")
    claimed = json.loads(freeze_path.read_text())
    checkout = Path(claimed["execution_checkout_root"])
    modules = checkout / "evals/v1.5/orchestration/comparison-go-ts-v1"
    sys.path.insert(0, str(modules))
    from run_main import verify_freeze
    from protocol import descriptor

    frozen = verify_freeze(freeze_path, freeze_sha)
    if set(frozen["task_descriptor_hashes"]) != {"S"} or len(frozen["cell_ids"]) != 24:
        raise ValueError("not_frozen_S24")
    task = descriptor(tasks={"S"})["tasks"]["S"]
    return frozen, task


def export(results: Path, freeze_path: Path, freeze_sha: str, output: Path) -> dict:
    frozen, task = frozen_context(freeze_path, freeze_sha)
    require_disjoint_output(output, results, Path(frozen["execution_checkout_root"]))
    if output.exists():
        raise FileExistsError(output)
    require_directory(results, "S_results_root")
    required, by_unit = owned_paths(task)
    selected: dict[str, bytes] = {"study/freeze.json": read_regular(freeze_path)}
    dispatch = results / "dispatch-index.json"
    selected["study/dispatch-index.json"] = read_regular(dispatch)
    if json.loads(selected["study/dispatch-index.json"]).get("scheduled_cells") != 24:
        raise ValueError("S_dispatch_cell_count_mismatch")
    for cell_id in frozen["cell_ids"]:
        episode = results / cell_id
        require_directory(episode, "S_episode")
        if (episode / "home/.codex/auth.json").exists():
            raise ValueError("auth_copy_present_export_refused:" + cell_id)
        for name in EPISODE_FILES:
            path = episode / name
            if path.exists():
                selected[f"episodes/{cell_id}/{name}"] = read_regular(path)
        if not (episode / "terminal.json").is_file() and not (episode / "startup-failure.json").is_file():
            raise ValueError("S_episode_not_terminal:" + cell_id)
        candidate = episode / "candidate"
        if candidate.exists():
            require_directory(candidate, "S_candidate")
            for path in sorted(candidate.rglob("*")):
                if path.is_symlink():
                    raise ValueError("S_candidate_symlink")
                if not path.is_file():
                    continue
                if not allowed_candidate_path(path, candidate, required, by_unit,
                                              cell_id.rsplit("-", 1)[-1]):
                    raise ValueError("S_candidate_path_not_allowlisted")
                selected[f"episodes/{cell_id}/candidate/{path.relative_to(candidate)}"] = read_regular(path)
            candidate_lineage(episode, candidate, required, by_unit)
        quarantine = episode / "quarantine"
        if quarantine.exists():
            require_directory(quarantine, "S_quarantine")
            for assignment in sorted(quarantine.iterdir()):
                require_directory(assignment, "S_quarantine_assignment")
                metadata_path = assignment / "metadata.json"
                metadata_bytes = read_regular(metadata_path)
                metadata = json.loads(metadata_bytes)
                if (metadata.get("schema") != "opensocrates.go-ts.candidate-diagnostic/2"
                        or metadata.get("assignment_id") != assignment.name):
                    raise ValueError("S_quarantine_metadata_mismatch")
                unit = metadata.get("unit_id")
                approved = set(metadata["quarantined_owned_paths"])
                allowed = required if unit == "single" else by_unit.get(unit)
                if allowed is None or not approved <= allowed or approved != set(metadata["owned_file_hashes"]):
                    raise ValueError("S_quarantine_owned_path_mismatch")
                actual = set()
                for path in assignment.rglob("*"):
                    if path.is_symlink():
                        raise ValueError("S_quarantine_symlink")
                    if path.is_file():
                        actual.add(str(path.relative_to(assignment)))
                if actual != approved | {"metadata.json"}:
                    raise ValueError("S_quarantine_file_set_mismatch")
                prefix = f"episodes/{cell_id}/quarantine/{assignment.name}/"
                selected[prefix + "metadata.json"] = metadata_bytes
                for name in sorted(approved):
                    data = read_regular(assignment / name)
                    if "sha256:" + sha(data) != metadata["owned_file_hashes"][name]:
                        raise ValueError("S_quarantine_file_hash_mismatch")
                    selected[prefix + name] = data

    qualification = results / "external-qualification-S"
    require_directory(qualification, "S_qualification")
    index_bytes = read_regular(qualification / "index.json")
    index = json.loads(index_bytes)
    if (index.get("schema") != "opensocrates.go-ts.S-serial-qualification/1"
            or index.get("generation_complete_before_start") is not True
            or index.get("scheduled_cells") != 24 or index.get("model_calls") != 0):
        raise ValueError("S_qualification_index_mismatch")
    selected["qualification/index.json"] = index_bytes
    receipt_paths = set()
    seen = set()
    sentinel_seen = set()
    for row in index["variants"]:
        cell_id = row["cell_id"]
        if cell_id not in frozen["cell_ids"]:
            raise ValueError("S_qualification_cell_outside_freeze")
        label, scope = row.get("variant"), row.get("scope")
        if label is None:
            if row["status"] not in {"candidate_unavailable", "blocked_dependency_or_no_versions"}:
                raise ValueError("S_unlabeled_qualification_status_invalid")
            if cell_id in sentinel_seen:
                raise ValueError("S_duplicate_qualification_sentinel")
            sentinel_seen.add(cell_id)
            continue
        if not isinstance(label, str) or not approved_variant(label, scope) or (cell_id, label) in seen:
            raise ValueError("S_qualification_variant_invalid_or_duplicate")
        arm = cell_id.rsplit("-", 1)[-1]
        if (label.startswith("single-v1-") and arm not in {"A", "B"}) or (
                label.startswith("S-design-v") and arm not in {"C", "D"}):
            raise ValueError("S_qualification_variant_arm_mismatch")
        seen.add((cell_id, label))
        if row["status"] in RECEIPT_REQUIRED_STATUSES and not row.get("candidate_sha256"):
            raise ValueError("S_required_candidate_bundle_hash_missing")
        if row.get("candidate_sha256") is not None and row["candidate_sha256"] != indexed_bundle_hash(
                results / cell_id, label, required, by_unit):
            raise ValueError("S_qualification_bundle_hash_mismatch")
        path = qualification / cell_id / label / "receipt.json"
        if path.exists():
            selected[f"qualification/{cell_id}/{label}/receipt.json"] = read_regular(path)
            receipt_paths.add(path.resolve())
        elif row["status"] in RECEIPT_REQUIRED_STATUSES:
            raise ValueError("S_required_qualification_receipt_missing")
    for path in qualification.rglob("*"):
        if path.is_symlink():
            raise ValueError("S_qualification_symlink")
        if path.is_file() and path.name in {"index.json", "receipt.json"}:
            if path == qualification / "index.json":
                continue
            if path.resolve() not in receipt_paths:
                raise ValueError("S_unindexed_qualification_receipt")
    if {row["cell_id"] for row in index["variants"]} != set(frozen["cell_ids"]):
        raise ValueError("S_qualification_cell_coverage_mismatch")
    if any(cell_id in sentinel_seen for cell_id, _ in seen):
        raise ValueError("S_qualification_sentinel_mixed_with_variants")
    indexed = {}
    for cell_id, label in seen:
        indexed.setdefault(cell_id, set()).add(label)
    for cell_id in frozen["cell_ids"]:
        expected = expected_variants(results / cell_id, cell_id.rsplit("-", 1)[-1])
        actual = indexed.get(cell_id, set())
        if expected != actual or (not expected and cell_id not in sentinel_seen):
            raise ValueError("S_qualification_variant_set_incomplete_or_extra")

    if any(any(part.lower() in FORBIDDEN_COMPONENTS for part in Path(name).parts)
           for name in selected):
        raise ValueError("S_sensitive_export_path")
    manifest = {
        "schema": "opensocrates.go-ts.S24-portable-export/1",
        "freeze_sha256": freeze_sha,
        "allowlist": frozen["export_allowlist"],
        "excluded": frozen["export_excluded"],
        "qualification_index_sha256": sha(index_bytes),
        "selected_cells": len(frozen["cell_ids"]),
        "selected_qualification_receipts": len(receipt_paths),
        "files": [{"path": name, "sha256": sha(data), "bytes": len(data)}
                  for name, data in sorted(selected.items())],
    }
    selected["study/export-manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(selected.items()):
            archive.writestr(name, data)
    with ZipFile(output) as archive:
        if set(archive.namelist()) != set(selected):
            raise ValueError("S_export_membership_mismatch")
        if any(archive.read(name) != data for name, data in selected.items()):
            raise ValueError("S_export_content_mismatch")
    return {"archive": str(output), "sha256": sha(output.read_bytes()),
            "file_count": len(selected), "selected_cells": len(frozen["cell_ids"]),
            "qualification_receipts": len(receipt_paths)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--freeze-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.results, args.freeze, args.freeze_sha256, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
