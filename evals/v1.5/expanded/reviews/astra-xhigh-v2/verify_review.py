"""Offline verification of review locks, scope, provenance and missingness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_review import validate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(complete: bool = True) -> dict:  # noqa: C901
    manifest = read(HERE / "manifest.json")
    for name, expected in manifest["file_hashes"].items():
        assert sha(ROOT / name) == expected, name
    for info in manifest["packets"]:
        assert sha(ROOT / info["original_path"]) == info["original_sha256"], info["packet_id"]
    assignments = manifest["assignment_order"]
    assert len(assignments) == 17
    identifiers = [
        identifier for assignment in assignments for identifier in assignment["packet_ids"]
    ]
    assert len(identifiers) == len(set(identifiers)) == 60
    packets = {
        info["packet_id"]: {
            "content": read(ROOT / info["first_pass_path"]),
            "sha256": info["first_pass_sha256"],
        }
        for info in manifest["packets"]
    }
    deterministic = {
        info["packet_id"]: {
            "content": read(ROOT / info["evidence_path"]),
            "sha256": info["evidence_sha256"],
        }
        for info in manifest["packets"]
    }
    rubric, schema = manifest["rubric"], read(HERE / "response.schema.json")
    first_lock = (
        read(HERE / "locks/first-pass.lock.json")
        if (HERE / "locks/first-pass.lock.json").exists()
        else None
    )
    final_lock = (
        read(HERE / "locks/all-ratings.lock.json")
        if (HERE / "locks/all-ratings.lock.json").exists()
        else None
    )
    reviewed = {"first_pass": 0, "evidence": 0}
    for assignment in assignments:
        assert 1 <= len(assignment["packet_ids"]) <= 4
        assert all(
            packets[identifier]["content"]["locale"] == assignment["locale"]
            for identifier in assignment["packet_ids"]
        )
        first = None
        for phase in ("first_pass", "evidence"):
            path = HERE / "assessments" / f"{assignment['assignment_id']}-{phase}.json"
            if not path.exists():
                assert not complete, str(path)
                continue
            value = read(path)
            validate(
                value,
                schema=schema,
                assignment=assignment,
                packets=packets,
                rubric=rubric,
                phase=phase,
                deterministic=deterministic if phase == "evidence" else None,
                locked=first,
            )
            per_lock = read(HERE / "locks" / f"{assignment['assignment_id']}-{phase}.json")
            assert sha(path) == per_lock["response_sha256"]
            reviewed[phase] += len(value["packets"])
            if phase == "first_pass":
                first = value
                if first_lock:
                    assert first_lock["assessments"][assignment["assignment_id"]] == sha(path)
                    assert per_lock["locked_at_unix"] <= first_lock["locked_at_unix"]
            else:
                assert first_lock is not None
                if final_lock:
                    assert final_lock["assessments"][assignment["assignment_id"]] == sha(path)
                    assert per_lock["locked_at_unix"] <= final_lock["locked_at_unix"]
    attempts = []
    intervals = []
    for path in sorted((HERE / "attempts").glob("*/*/*/started.json")):
        started = read(path)
        phase = path.parts[-3]
        if phase == "evidence":
            assert first_lock is not None and started["started_unix"] > first_lock["locked_at_unix"]
        receipt = path.parent / "receipt.json"
        if not receipt.exists():
            assert not complete
            continue
        row = read(receipt)
        assert (row["model_requested"], row["effort_requested"], row["sandbox_requested"]) == (
            "gpt-6-astra",
            "xhigh",
            "read-only",
        )
        assert row["agent_definition_sha256"] == manifest["agent"]["definition_sha256"]
        assert row["runtime_profile_sha256"] == manifest["agent"]["runtime_profile_sha256"]
        assert row["client_sha256"] == manifest["client"]["sha256"]
        assert row["started_unix"] == started["started_unix"]
        intervals.extend(
            [(started["started_unix"], 1), (started["started_unix"] + row["wall_seconds"], -1)]
        )
        assert row["billed_cost"] is None and row["backend_model_echo"] is None
        for number in row["usage"].values():
            assert number is None or (type(number) is int and number >= 0)
        assert read(path.parent / "cleanup.json")["auth_copy_removed"]
        isolation = read(path.parent / "isolation.json")
        assert isolation["input_hashes_unchanged"]
        if read(path.parent / "validation.json")["valid"]:
            assert not row["access_audit"]["flags"]
        attempts.append(row)
    active = maximum_parallel = 0
    for _, delta in sorted(intervals):
        active += delta
        maximum_parallel = max(maximum_parallel, active)
    assert maximum_parallel <= manifest["limits"]["max_parallel_calls"]
    if complete:
        assert first_lock is not None and final_lock is not None
        assert reviewed == {"first_pass": 60, "evidence": 60}
        assert (
            first_lock["manifest_sha256"]
            == final_lock["manifest_sha256"]
            == sha(HERE / "manifest.json")
        )
    return {
        "status": "pass" if complete else "partial_verified",
        "packet_count": 60,
        "assessments_verified": reviewed,
        "v2_completed_attempts": len(attempts),
        "v2_missing_usage_attempts": sum(row["usage"]["input_tokens"] is None for row in attempts),
        "v2_failed_processes": sum(not row["process_success"] for row in attempts),
        "maximum_completed_call_overlap": maximum_parallel,
        "human_scores": None,
        "provisional_model_assessor": "gpt-6-astra/xhigh",
        "historical_transport_failures": "v1 rejected review call plus a zero-packet transport diagnostic; retained separately",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial", action="store_true")
    result = verify(not parser.parse_args().partial)
    print(json.dumps(result, indent=2))
