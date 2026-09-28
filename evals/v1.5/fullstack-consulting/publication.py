"""Describe portable publication without modifying original or exported artifacts.

Only unchanged files identified by installed-distribution RECORD hashes can be
omitted as a dependency cache. Candidate edits and unrecognized files stay public.
"""

from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
from email.parser import Parser
import hashlib
import json
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependency_files(original, locked):
    omitted = set()
    distributions = []
    dependency_root = original / ".deps"
    for record in sorted(dependency_root.glob("*.dist-info/RECORD")):
        metadata = record.parent / "METADATA"
        if not metadata.is_file():
            continue
        meta = Parser().parsestr(metadata.read_text())
        if not meta.get("Name") or not meta.get("Version"):
            continue
        matched = []
        with record.open(newline="") as stream:
            for relative, digest, _size in csv.reader(stream):
                path = PurePosixPath(relative)
                if path.is_absolute() or ".." in path.parts:
                    continue
                name = str(PurePosixPath(".deps") / path)
                if name not in locked:
                    continue
                if digest.startswith("sha256="):
                    value = digest.split("=", 1)[1]
                    expected = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).hex()
                    if locked[name]["sha256"] == expected:
                        matched.append(name)
                elif not digest and original / name == record:
                    # RECORD inventories itself with an empty digest by convention.
                    matched.append(name)
        omitted.update(matched)
        wheel = record.parent / "WHEEL"
        distributions.append(
            {
                "name": meta["Name"],
                "version": meta["Version"],
                "metadata_sha256": sha(metadata),
                "record_sha256": sha(record),
                "wheel_tags": [
                    line.removeprefix("Tag: ")
                    for line in wheel.read_text().splitlines()
                    if line.startswith("Tag: ")
                ]
                if wheel.exists()
                else [],
                "matched_files": len(matched),
            }
        )
    return omitted, distributions


def describe(cell, original):
    lock = json.loads((cell / "snapshot.json").read_text())
    exported = json.loads((cell / "export-map.json").read_text())
    for name, info in lock["files"].items():
        assert sha(original / name) == info["sha256"], name
    omitted, distributions = dependency_files(original, lock["files"])
    published = sorted(set(exported["files"]) - omitted)
    for name in published:
        assert sha(cell / "artifact-export" / name) == exported["files"][name]["export_sha256"], (
            name
        )
    return {
        "schema": "opensocrates.artifact-publication/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "publication_helper_sha256": sha(Path(__file__)),
        "snapshot_sha256": sha(cell / "snapshot.json"),
        "export_map_sha256": sha(cell / "export-map.json"),
        "published_files": published,
        "retained_dependency_files": sorted(omitted),
        "retained_dependency_bytes": sum(lock["files"][name]["bytes"] for name in omitted),
        "distributions": distributions,
        "original_and_full_local_export_unchanged": True,
        "reconstruction": "Use the exact distribution names/versions and recorded wheel tags in a disposable compatible Python environment. Install into .deps, then apply any published overlay files. Validate against the original snapshot inventory before claiming byte-equivalent reconstruction. No reconstruction or independent artifact qualification is claimed by this receipt.",
        "qualification_source": "Original locked artifacts, including the complete original dependency cache; no candidate repairs.",
    }


def verify_published(cell):
    manifest = json.loads((cell / "publication-manifest.v1.json").read_text())
    exported = json.loads((cell / "export-map.json").read_text())
    assert sha(cell / "snapshot.json") == manifest["snapshot_sha256"]
    assert sha(cell / "export-map.json") == manifest["export_map_sha256"]
    public, cache = set(manifest["published_files"]), set(manifest["retained_dependency_files"])
    assert not public & cache and public | cache == set(exported["files"])
    for name in public:
        assert sha(cell / "artifact-export" / name) == exported["files"][name]["export_sha256"], (
            name
        )
    return {"published_files": len(public), "retained_dependency_files": len(cache)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify"])
    parser.add_argument("--storage", type=Path)
    args = parser.parse_args()
    results = []
    for cell in sorted((HERE / "v2/results").iterdir()):
        if not (cell / "export-map.json").exists():
            continue
        target = cell / "publication-manifest.v1.json"
        if args.action == "prepare" and not target.exists():
            assert args.storage is not None
            value = describe(cell, args.storage / cell.name / "locked-artifacts")
            with target.open("x") as stream:
                json.dump(value, stream, indent=2)
                stream.write("\n")
        if target.exists():
            results.append({"cell": cell.name, **verify_published(cell)})
    print(json.dumps(results, indent=2))
