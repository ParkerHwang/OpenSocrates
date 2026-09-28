"""Export only the frozen continuity lane's public, synthetic evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


EPISODE_FILES = (
    "started.json", "terminal.json", "startup-failure.json", "child-failure.json",
    "memory-setup.json", "summary.json", "response.json", "observation.jsonl",
    "argv-map.jsonl",
)
QUALIFICATION_FILES = {"index.json", "receipt.json", "post-role-state.json"}
OWNED_FILES = {"continuation.json", "handoff.md"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe_export_file:" + str(path))
    return path.read_bytes()


def export(results: Path, freeze_path: Path, freeze_sha: str, output: Path) -> dict:
    if sha(freeze_path.read_bytes()) != freeze_sha:
        raise ValueError("continuity_freeze_hash_mismatch")
    claimed = json.loads(freeze_path.read_text())
    execution_modules = (Path(claimed["execution_checkout_root"])
                         / "evals/v1.5/orchestration/comparison-go-ts-v1")
    sys.path.insert(0, str(execution_modules))
    from run_continuity import verify_freeze

    frozen = verify_freeze(freeze_path, freeze_sha)
    if frozen.get("lane") != "continuity-EN-KO-memory-note" or len(frozen["cell_ids"]) != 8:
        raise ValueError("not_frozen_continuity8")
    if output.exists():
        raise FileExistsError(output)

    selected: dict[str, bytes] = {"study/freeze.json": checked_file(freeze_path)}
    dispatch = results / "dispatch-index.json"
    if dispatch.exists():
        selected["study/dispatch-index.json"] = checked_file(dispatch)

    for cell_id in frozen["cell_ids"]:
        episode = results / cell_id
        if episode.is_symlink() or not episode.is_dir():
            raise ValueError("episode_missing_or_symlink:" + cell_id)
        if (episode / "home/.codex/auth.json").exists():
            raise ValueError("auth_copy_present_export_refused:" + cell_id)
        for name in EPISODE_FILES:
            path = episode / name
            if path.exists():
                selected[f"episodes/{cell_id}/{name}"] = checked_file(path)
        candidate = episode / "candidate"
        if candidate.exists():
            if candidate.is_symlink() or not candidate.is_dir():
                raise ValueError("unsafe_candidate_directory")
            for path in sorted(candidate.rglob("*")):
                if path.is_symlink():
                    raise ValueError("candidate_symlink_export_refused")
                if not path.is_file():
                    continue
                parts = path.relative_to(candidate).parts
                valid_artifact = len(parts) == 2 and parts[0] == "artifacts" and parts[1] in OWNED_FILES
                valid_version = (len(parts) == 4 and parts[:2] == ("versions", "continuation")
                                 and parts[2].startswith("v") and parts[2][1:].isdigit()
                                 and parts[3] in OWNED_FILES)
                if not (valid_artifact or valid_version):
                    raise ValueError("unallowlisted_candidate_file:" + str(path.relative_to(candidate)))
                relative = "candidate/" + str(path.relative_to(candidate))
                selected[f"episodes/{cell_id}/{relative}"] = checked_file(path)
        quarantine = episode / "quarantine"
        if quarantine.exists():
            if quarantine.is_symlink() or not quarantine.is_dir():
                raise ValueError("unsafe_quarantine_directory")
            for assignment in sorted(quarantine.iterdir()):
                if assignment.is_symlink() or not assignment.is_dir():
                    raise ValueError("unsafe_quarantine_assignment")
                metadata_path = assignment / "metadata.json"
                metadata = json.loads(checked_file(metadata_path))
                if metadata.get("schema") != "opensocrates.go-ts.candidate-diagnostic/2":
                    raise ValueError("quarantine_metadata_schema_mismatch")
                approved = set(metadata["quarantined_owned_paths"])
                if approved != set(metadata["owned_file_hashes"]):
                    raise ValueError("quarantine_file_manifest_mismatch")
                actual = set()
                for path in assignment.rglob("*"):
                    if path.is_symlink():
                        raise ValueError("quarantine_symlink_export_refused")
                    if path.is_file():
                        actual.add(str(path.relative_to(assignment)))
                if actual != approved | {"metadata.json"}:
                    raise ValueError("unallowlisted_quarantine_file")
                prefix = f"episodes/{cell_id}/quarantine/{assignment.name}/"
                selected[prefix + "metadata.json"] = checked_file(metadata_path)
                for name in sorted(approved):
                    if name not in OWNED_FILES:
                        raise ValueError("unexpected_continuity_owned_file:" + name)
                    data = checked_file(assignment / name)
                    if "sha256:" + sha(data) != metadata["owned_file_hashes"][name]:
                        raise ValueError("quarantine_file_changed")
                    selected[prefix + name] = data

    qualification = results / "external-qualification-continuity"
    if qualification.exists():
        if qualification.is_symlink() or not qualification.is_dir():
            raise ValueError("unsafe_qualification_directory")
        if not (qualification / "index.json").is_file():
            raise ValueError("continuity_qualification_index_missing")
        for path in sorted(qualification.rglob("*")):
            if path.is_symlink():
                raise ValueError("qualification_symlink_export_refused")
            if path.is_file() and path.name in QUALIFICATION_FILES:
                parts = path.relative_to(qualification).parts
                root_index = parts == ("index.json",)
                cell_state = (len(parts) == 2 and parts[0] in frozen["cell_ids"]
                              and parts[1] == "post-role-state.json")
                version_receipt = (len(parts) == 3 and parts[0] in frozen["cell_ids"]
                                   and parts[1].startswith("continuation-v")
                                   and parts[1][len("continuation-v"):].isdigit()
                                   and parts[2] == "receipt.json")
                if not (root_index or cell_state or version_receipt):
                    raise ValueError("unallowlisted_qualification_receipt:" + str(path.relative_to(qualification)))
                selected["qualification/" + str(path.relative_to(qualification))] = checked_file(path)

    forbidden = {"auth.json", "private", "raw-events.jsonl", "transcript.jsonl",
                 "reasoning.json", "tool-output.log", "candidate-copy"}
    if any(any(part.lower() in forbidden for part in Path(name).parts)
           for name in selected):
        raise ValueError("sensitive_export_path")
    manifest = {
        "schema": "opensocrates.go-ts.continuity-portable-export/1",
        "freeze_sha256": freeze_sha,
        "allowlist": frozen["export_allowlist"],
        "excluded": frozen["export_excluded"],
        "files": [{"path": name, "sha256": sha(data), "bytes": len(data)}
                  for name, data in sorted(selected.items())],
    }
    selected["study/export-manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(selected.items()):
            archive.writestr(name, data)
    with ZipFile(output) as archive:
        if set(archive.namelist()) != set(selected):
            raise ValueError("export_membership_mismatch")
        if any(archive.read(name) != data for name, data in selected.items()):
            raise ValueError("export_bytes_mismatch")
    return {"archive": str(output), "sha256": sha(output.read_bytes()),
            "file_count": len(selected), "selected_cells": len(frozen["cell_ids"])}


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
