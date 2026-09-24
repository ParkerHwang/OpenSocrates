"""Freeze smaller evidence assignments; preserve the original 60 first passes."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.with_name("astra-xhigh-v2")
ROOT = HERE.parents[4]


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def main() -> None:
    original = read(PREVIOUS / "manifest.json")
    first_lock = read(PREVIOUS / "locks/first-pass.lock.json")
    assignments = []
    for old in original["assignment_order"]:
        if old["assignment_id"] == "A01":
            continue  # Its two evidence assessments already passed; do not rerun them.
        original_path = PREVIOUS / "assessments" / f"{old['assignment_id']}-first_pass.json"
        assert sha(original_path) == first_lock["assessments"][old["assignment_id"]]
        first = read(original_path)
        for offset in range(0, len(old["packet_ids"]), 2):
            identifiers = old["packet_ids"][offset : offset + 2]
            identifier = f"{old['assignment_id']}P{offset // 2 + 1}"
            projection = copy.deepcopy(first)
            projection["assignment_id"] = identifier
            projection["packets"] = [
                packet for packet in first["packets"] if packet["packet_id"] in identifiers
            ]
            assert len(projection["packets"]) == len(identifiers)
            target = HERE / "inputs/locked-first" / f"{identifier}.json"
            save(target, projection)
            assignments.append(
                {
                    "assignment_id": identifier,
                    "locale": old["locale"],
                    "packet_ids": identifiers,
                    "original_assignment_id": old["assignment_id"],
                    "original_first_pass_path": str(original_path.relative_to(ROOT)),
                    "original_first_pass_sha256": sha(original_path),
                    "first_pass_projection_path": str(target.relative_to(ROOT)),
                    "first_pass_projection_sha256": sha(target),
                    "projection_rule": "Only assignment_id and packet list change; every retained packet judgment is byte-equivalent as canonical JSON to its original locked object. No new first-pass rating.",
                }
            )
    retained_path = PREVIOUS / "assessments/A01-evidence.json"
    assert sha(retained_path) == read(PREVIOUS / "locks/A01-evidence.json")["response_sha256"]
    manifest = {
        **original,
        "schema": "opensocrates.provisional-ai-review-manifest/3.0.0",
        "status": "frozen_before_evidence_continuation",
        "source_commit_before_freeze": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "assignment_order": assignments,
        "original_first_pass_lock": {
            "path": str((PREVIOUS / "locks/first-pass.lock.json").relative_to(ROOT)),
            "sha256": sha(PREVIOUS / "locks/first-pass.lock.json"),
            "packets": 60,
            "original_assignments": 17,
        },
        "retained_evidence_assessments": {
            "A01": {
                "path": str(retained_path.relative_to(ROOT)),
                "sha256": sha(retained_path),
            }
        },
        "limits": {
            **original["limits"],
            "max_packets_per_assignment": 2,
            "max_parallel_calls": 3,
            "output_guidance": "Preserve every original judgment field exactly. Give concise separate evidence-phase grounds with complete gates and citations. Avoid repeated dumps of already-read schema, role or packet text; no quality inference from length.",
        },
        "phase_order": "All original 60 first passes remain locked in v2 before any disclosure. Retain A01 evidence (2 packets); review the remaining 58 in 30 same-language assignments of one or two packets. Each gets only its own exact projected first-pass objects and matching evidence. All 60 final assessments must lock before analytical unblinding.",
        "failure_handling": original["failure_handling"]
        + " Stop further dispatch at the first terminal failed assignment; let only already-running bounded calls finish. Never submit the entire pending queue at once.",
        "previous_freeze": {
            "path": str((PREVIOUS / "manifest.json").relative_to(ROOT)),
            "sha256": sha(PREVIOUS / "manifest.json"),
            "accepted_first_pass_assignments": 17,
            "accepted_first_pass_packets": 60,
            "accepted_evidence_packets": 2,
            "evidence_timeouts": 2,
            "evidence_coordinator_interruptions": 2,
            "failed_usage": None,
            "reason": "Two four-packet evidence calls reached 900 seconds without completion. Stopped the coordinator and its next two active calls to prevent repeated unchanged dispatch. No artifacts, rubric, first-pass scores, role, model or effort change.",
        },
    }
    files = dict(original["file_hashes"])
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            files[str(path.relative_to(ROOT))] = sha(path)
    files[manifest["original_first_pass_lock"]["path"]] = manifest["original_first_pass_lock"][
        "sha256"
    ]
    files[str(retained_path.relative_to(ROOT))] = sha(retained_path)
    for assignment in assignments:
        files[assignment["original_first_pass_path"]] = assignment["original_first_pass_sha256"]
    manifest["file_hashes"] = files
    assert len(assignments) == 30
    assert sum(len(row["packet_ids"]) for row in assignments) == 58
    save(HERE / "manifest.json", manifest)
    print("Frozen continuation: 58 packets / 30 assignments, 2 prior evidence packets retained.")


if __name__ == "__main__":
    main()
