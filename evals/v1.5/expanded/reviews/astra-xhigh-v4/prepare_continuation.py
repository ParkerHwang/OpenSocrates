"""Freeze four single-packet continuations as a separate protocol version."""

import copy
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.with_name("astra-xhigh-v3")
ROOT = HERE.parents[4]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def main():
    old = read(PREVIOUS / "manifest.json")
    retained = dict(old["retained_evidence_assessments"])
    assignments = []
    for assignment in old["assignment_order"]:
        identifier = assignment["assignment_id"]
        if identifier not in {"A16P1", "A17P1"}:
            path = PREVIOUS / "assessments" / f"{identifier}-evidence.json"
            lock = read(PREVIOUS / "locks" / f"{identifier}-evidence.json")
            assert sha(path) == lock["response_sha256"]
            retained[identifier] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
            continue
        first = read(ROOT / assignment["first_pass_projection_path"])
        for index, packet in enumerate(first["packets"], 1):
            new_id = f"{identifier}S{index}"
            projection = copy.deepcopy(first)
            projection["assignment_id"] = new_id
            projection["packets"] = [packet]
            path = HERE / "inputs/locked-first" / f"{new_id}.json"
            save(path, projection)
            assignments.append(
                {
                    **assignment,
                    "assignment_id": new_id,
                    "packet_ids": [packet["packet_id"]],
                    "first_pass_projection_path": str(path.relative_to(ROOT)),
                    "first_pass_projection_sha256": sha(path),
                }
            )
    assert sum(len(read(ROOT / row["path"])["packets"]) for row in retained.values()) == 56
    assert len(assignments) == 4
    files = dict(old["file_hashes"])
    for path in HERE.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            files[str(path.relative_to(ROOT))] = sha(path)
    for row in retained.values():
        files[row["path"]] = row["sha256"]
    for failed_assignment in ("A16P1", "A17P1"):
        for path in (PREVIOUS / "attempts" / failed_assignment / "evidence").rglob("*"):
            if path.is_file():
                files[str(path.relative_to(ROOT))] = sha(path)
    save(
        HERE / "manifest.json",
        {
            **old,
            "schema": "opensocrates.provisional-ai-review-manifest/4.0.0",
            "status": "frozen_before_single_packet_citation_continuation",
            "source_commit_before_freeze": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, cwd=ROOT
            ).strip(),
            "assignment_order": assignments,
            "retained_evidence_assessments": retained,
            "file_hashes": files,
            "limits": {**old["limits"], "max_packets_per_assignment": 1, "max_parallel_calls": 2},
            "phase_order": "Retain the original 60 first passes and 56 completed evidence assessments. Judge only the four remaining packets, independently, with unchanged role/rubric/model/effort/schema. Lock the combined 60 before analytic unblinding.",
            "previous_freeze": {
                "path": str((PREVIOUS / "manifest.json").relative_to(ROOT)),
                "sha256": sha(PREVIOUS / "manifest.json"),
                "accepted_evidence_packets_across_versions": 56,
                "citation_rejections": 2,
                "evidence_timeouts": 1,
                "rejected_attempts": "A16P1 evidence attempts 1 and 2 (citation validation); A17P1 evidence attempt 1 (900-second timeout); all receipts retained",
                "reason": "One attempt cited deterministic:/ and its permitted fresh retry cited deterministic:. Both violate the existing named-field pointer syntax. The final A17P1 two-packet call timed out at 900 seconds. New single-packet assignments clarify only citation grammar; no rejected scores or semantic feedback are supplied. The frozen validator, rubric and all candidate artifacts remain unchanged.",
            },
        },
    )
    print("Frozen: 56 retained evidence packets plus 4 single-packet assignments.")


if __name__ == "__main__":
    main()
