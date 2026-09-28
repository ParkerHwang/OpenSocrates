"""Offline, identity-preserving verification of the continued review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_review import validate

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.with_name("astra-xhigh-v2")
ROOT = HERE.parents[4]


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt_ledger(complete: bool = True) -> list[dict]:
    rows = []
    for version in ("astra-xhigh-v1", "astra-xhigh-v2", "astra-xhigh-v3"):
        directory = HERE.with_name(version)
        configuration = read(directory / "manifest.json")
        for path in sorted((directory / "attempts").glob("*/*/*/started.json")):
            receipt_path = path.with_name("receipt.json")
            if not receipt_path.exists():
                assert not complete, str(receipt_path)
                continue
            receipt = read(receipt_path)
            validation = read(path.with_name("validation.json"))
            rows.append(
                {
                    "version": version,
                    "path": str(receipt_path.relative_to(ROOT)),
                    "assignment_id": path.parts[-4],
                    "phase": path.parts[-3],
                    "attempt": path.parts[-2],
                    "started_unix": receipt["started_unix"],
                    "wall_seconds": receipt["wall_seconds"],
                    "exit_code": receipt["exit_code"],
                    "process_success": receipt["process_success"],
                    "timed_out": receipt.get("timed_out", False),
                    "invocation_error": receipt.get("invocation_error"),
                    "usage": receipt["usage"],
                    "tool_actions": receipt["tool_actions_started_or_completed"],
                    "failed_tool_actions": receipt["failed_tool_actions"],
                    "incomplete_tool_actions": receipt.get("incomplete_tool_actions"),
                    "validation": validation,
                }
            )
            assert read(path.with_name("cleanup.json"))["auth_copy_removed"]
            assert read(path.with_name("isolation.json"))["input_hashes_unchanged"]
            assert receipt["model_requested"] == "gpt-6-astra"
            assert receipt["effort_requested"] == "xhigh"
            assert receipt["sandbox_requested"] == "read-only"
            assert receipt["agent_definition_sha256"] == configuration["agent"]["definition_sha256"]
            assert (
                receipt["runtime_profile_sha256"]
                == configuration["agent"]["runtime_profile_sha256"]
            )
            assert receipt["client_sha256"] == configuration["client"]["sha256"]
            assert receipt["billed_cost"] is None and receipt["backend_model_echo"] is None
            assert len(receipt.get("usage_reports", [])) <= 1
            for value in receipt["usage"].values():
                assert value is None or (type(value) is int and value >= 0)
            if validation["valid"]:
                assert not receipt["access_audit"]["flags"]
    probe_path = HERE.with_name("astra-xhigh-v1") / "preflight/transport-diagnostic.json"
    probe = read(probe_path)
    rows.append(
        {
            "version": "astra-xhigh-v1",
            "path": str(probe_path.relative_to(ROOT)),
            "phase": "zero_packet_transport_diagnostic",
            "assignment_id": None,
            "attempt": None,
            "started_unix": None,
            "wall_seconds": probe["wall_seconds"],
            "exit_code": probe["exit_code"],
            "process_success": False,
            "timed_out": False,
            "invocation_error": "invalid_json_schema",
            "usage": probe["usage"],
            "tool_actions": None,
            "failed_tool_actions": None,
            "incomplete_tool_actions": None,
            "validation": {"valid": False, "errors": ["No packets; schema transport rejected"]},
        }
    )
    return rows


def verify(complete: bool = True) -> dict:  # noqa: C901
    manifest = read(HERE / "manifest.json")
    old = read(PREVIOUS / "manifest.json")
    for name, expected in manifest["file_hashes"].items():
        assert sha(ROOT / name) == expected, name
    for packet in manifest["packets"]:
        assert sha(ROOT / packet["original_path"]) == packet["original_sha256"]
    schema = read(HERE / "response.schema.json")
    packets = {
        packet["packet_id"]: {
            "content": read(ROOT / packet["first_pass_path"]),
            "sha256": packet["first_pass_sha256"],
        }
        for packet in manifest["packets"]
    }
    deterministic = {
        packet["packet_id"]: {
            "content": read(ROOT / packet["evidence_path"]),
            "sha256": packet["evidence_sha256"],
        }
        for packet in manifest["packets"]
    }
    original_lock = read(ROOT / manifest["original_first_pass_lock"]["path"])
    assert (
        sha(ROOT / manifest["original_first_pass_lock"]["path"])
        == manifest["original_first_pass_lock"]["sha256"]
    )
    original_first = {}
    for assignment in old["assignment_order"]:
        identifier = assignment["assignment_id"]
        path = PREVIOUS / "assessments" / f"{identifier}-first_pass.json"
        assert sha(path) == original_lock["assessments"][identifier]
        value = read(path)
        validate(
            value,
            schema=schema,
            assignment=assignment,
            packets=packets,
            rubric=manifest["rubric"],
            phase="first_pass",
        )
        original_first[identifier] = value
    original_ids = [p["packet_id"] for value in original_first.values() for p in value["packets"]]
    assert len(original_ids) == len(set(original_ids)) == 60
    references = dict(manifest["retained_evidence_assessments"])
    reviewed = []
    for identifier, reference in references.items():
        path = ROOT / reference["path"]
        assert sha(path) == reference["sha256"]
        value = read(path)
        assignment = next(a for a in old["assignment_order"] if a["assignment_id"] == identifier)
        validate(
            value,
            schema=schema,
            assignment=assignment,
            packets=packets,
            rubric=manifest["rubric"],
            phase="evidence",
            deterministic=deterministic,
            locked=original_first[identifier],
        )
        reviewed.extend(p["packet_id"] for p in value["packets"])
    for assignment in manifest["assignment_order"]:
        assert 1 <= len(assignment["packet_ids"]) <= 2
        projection = read(ROOT / assignment["first_pass_projection_path"])
        original = original_first[assignment["original_assignment_id"]]
        assert projection["assignment_id"] == assignment["assignment_id"]
        assert projection["packets"] == [
            p for p in original["packets"] if p["packet_id"] in assignment["packet_ids"]
        ]
        assert {p["locale"] for p in projection["packets"]} == {assignment["locale"]}
        path = HERE / "assessments" / f"{assignment['assignment_id']}-evidence.json"
        if not path.exists():
            assert not complete, str(path)
            continue
        value = read(path)
        validate(
            value,
            schema=schema,
            assignment=assignment,
            packets=packets,
            rubric=manifest["rubric"],
            phase="evidence",
            deterministic=deterministic,
            locked=projection,
        )
        lock = read(HERE / "locks" / f"{assignment['assignment_id']}-evidence.json")
        assert sha(path) == lock["response_sha256"]
        references[assignment["assignment_id"]] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha(path),
        }
        reviewed.extend(p["packet_id"] for p in value["packets"])
    assert len(reviewed) == len(set(reviewed))
    ledger = attempt_ledger(complete)
    intervals = []
    for row in ledger:
        if row["version"] == "astra-xhigh-v3":
            assert row["started_unix"] > original_lock["locked_at_unix"]
            intervals.extend(
                [
                    (row["started_unix"], 1),
                    (row["started_unix"] + row["wall_seconds"], -1),
                ]
            )
    active = maximum = 0
    for _, delta in sorted(intervals):
        active += delta
        maximum = max(maximum, active)
    assert maximum <= manifest["limits"]["max_parallel_calls"]
    if complete:
        assert sorted(reviewed) == sorted(original_ids)
        lock = read(HERE / "locks/all-ratings.lock.json")
        assert lock["manifest_sha256"] == sha(HERE / "manifest.json")
        assert lock["assessments"] == references
        for path in (HERE / "locks").glob("*-evidence.json"):
            assert read(path)["locked_at_unix"] <= lock["locked_at_unix"]
    return {
        "status": "pass" if complete else "partial_verified",
        "first_pass_packets": 60,
        "evidence_packets": len(reviewed),
        "completed_or_interrupted_cli_receipts": len(ledger),
        "failed_process_or_transport_receipts": sum(not row["process_success"] for row in ledger),
        "validation_rejected_successful_processes": sum(
            row["process_success"] and not row["validation"]["valid"] for row in ledger
        ),
        "missing_input_usage_calls": sum(
            (row["usage"] or {}).get("input_tokens") is None for row in ledger
        ),
        "maximum_completed_v3_overlap": maximum,
        "human_scores": None,
        "human_status": "unavailable",
        "assessor": "gpt-6-astra/xhigh/read-only",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial", action="store_true")
    print(json.dumps(verify(not parser.parse_args().partial), indent=2))
