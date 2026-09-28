"""Portable allowlisted synthetic evidence export; never packs profiles or raw logs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from run_main import verify_freeze


EPISODE_FILES = (
    "started.json", "terminal.json", "startup-failure.json", "child-failure.json",
    "summary.json", "response.json", "observation.jsonl", "argv-map.jsonl",
)
ARTIFACT_PREFIXES = ("candidate/artifacts/", "candidate/versions/")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def export(results: Path, freeze_path: Path, freeze_sha: str, output: Path) -> dict:
    frozen = verify_freeze(freeze_path, freeze_sha)
    if output.exists():
        raise FileExistsError(output)
    selected: dict[str, bytes] = {"study/freeze.json": freeze_path.read_bytes()}
    dispatch_index = results / "dispatch-index.json"
    if dispatch_index.is_file():
        selected["study/dispatch-index.json"] = dispatch_index.read_bytes()
    for cell_id in frozen["cell_ids"]:
        episode = results / cell_id
        if (episode / "home/.codex/auth.json").exists():
            raise ValueError("auth_copy_present_export_refused:" + cell_id)
        for name in EPISODE_FILES:
            path = episode / name
            if path.is_file():
                selected[f"episodes/{cell_id}/{name}"] = path.read_bytes()
        candidate = episode / "candidate"
        if candidate.is_dir():
            for path in sorted(candidate.rglob("*")):
                if path.is_symlink():
                    raise ValueError("candidate_symlink_export_refused")
                if not path.is_file():
                    continue
                relative = "candidate/" + str(path.relative_to(candidate))
                if not relative.startswith(ARTIFACT_PREFIXES):
                    raise ValueError("unallowlisted_candidate_file:" + relative)
                selected[f"episodes/{cell_id}/{relative}"] = path.read_bytes()
        quarantine = episode / "quarantine"
        if quarantine.is_dir():
            for assignment in sorted(quarantine.iterdir()):
                if not assignment.is_dir() or assignment.is_symlink():
                    raise ValueError("unsafe_quarantine_assignment")
                metadata_path = assignment / "metadata.json"
                metadata = json.loads(metadata_path.read_text())
                if metadata.get("schema") != "opensocrates.go-ts.candidate-diagnostic/2":
                    raise ValueError("quarantine_metadata_schema_mismatch")
                approved = set(metadata["quarantined_owned_paths"])
                if set(metadata["owned_file_hashes"]) != approved:
                    raise ValueError("quarantine_file_manifest_mismatch")
                if any(path.is_symlink() for path in assignment.rglob("*")):
                    raise ValueError("quarantine_symlink_export_refused")
                actual = {str(path.relative_to(assignment)) for path in assignment.rglob("*")
                          if path.is_file()}
                if actual != approved | {"metadata.json"}:
                    raise ValueError("unallowlisted_quarantine_file")
                selected[f"episodes/{cell_id}/quarantine/{assignment.name}/metadata.json"] = metadata_path.read_bytes()
                for name in sorted(approved):
                    path = assignment / name
                    if path.is_symlink() or not path.is_file() or "sha256:" + sha(path.read_bytes()) != metadata["owned_file_hashes"][name]:
                        raise ValueError("quarantine_file_changed")
                    selected[f"episodes/{cell_id}/quarantine/{assignment.name}/{name}"] = path.read_bytes()
    qualification = results / "external-qualification"
    if qualification.is_dir():
        for path in sorted(qualification.rglob("*")):
            if path.is_symlink():
                raise ValueError("qualification_symlink_export_refused")
            if path.is_file() and path.name in {"receipt.json", "index.json"}:
                selected["qualification/" + str(path.relative_to(qualification))] = path.read_bytes()
    forbidden_components = {"auth.json", "private", "raw-events.jsonl", "transcript.jsonl",
                            "reasoning.json", "tool-output.log"}
    if any(any(part.lower() in forbidden_components for part in Path(name).parts)
           for name in selected):
        raise ValueError("sensitive_export_path")
    manifest = {
        "schema": "opensocrates.go-ts.portable-export/1",
        "freeze_sha256": freeze_sha,
        "allowlist": ["study/dispatch-index.json", *EPISODE_FILES, *ARTIFACT_PREFIXES,
                      "quarantine/<assignment>/metadata.json", "quarantine/<assignment>/<declared-owned-path>",
                      "qualification/**/receipt.json",
                      "qualification/index.json"],
        "files": [{"path": name, "sha256": sha(data), "bytes": len(data)}
                  for name, data in sorted(selected.items())],
        "excluded": ["auth", "raw_prompts", "transcripts", "reasoning", "raw_events",
                     "tool_output_bodies", "private_oracles", "candidate_copies", "server_logs"],
        "partial_evidence_allowed": True,
    }
    selected["study/export-manifest.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(selected.items()):
            archive.writestr(name, data)
    with ZipFile(output) as archive:
        if set(archive.namelist()) != set(selected):
            raise ValueError("export_membership_mismatch")
        for name, data in selected.items():
            if archive.read(name) != data:
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
