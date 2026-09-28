#!/usr/bin/env python3
"""S24-only accounting on original structured receipts; never executes subjects."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import summarize

FIELDS = (
    "command_started", "command_completed", "other_tool_started",
    "other_tool_completed", "public_message_count", "unclassified_error_items",
)
EXPECTED_FREEZE_SHA256 = "3973a93cf491030d3aac47cfe4748c2a70b67d43ebed39b879d9253e4a92f815"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_categories(root: Path, cells: list[dict]) -> dict:
    """Keep complete and truncated public streams apart, without call inference."""
    complete = Counter()
    partial = Counter()
    stream_states = Counter()
    for cell in cells:
        response = summarize.read(root / cell["id"] / "response.json")
        summary = summarize.read(root / cell["id"] / "summary.json")
        expected = Counter(call.get("assignment_id") for call in response["calls"])
        observed = Counter(row.get("assignment_id") for row in summary["role_event_summaries"])
        if expected != observed:
            raise ValueError("S24_event_assignment_mismatch:" + cell["id"])
        for row in summary["role_event_summaries"]:
            if row.get("event_stream_observed") is not True:
                raise ValueError("S24_event_stream_unobserved:" + cell["id"])
            is_complete = row.get("event_stream_complete") is True
            stream_states["complete" if is_complete else "partial"] += 1
            target = complete if is_complete else partial
            for field in FIELDS:
                value = row.get(field)
                if type(value) is not int or value < 0:
                    raise ValueError("S24_event_count_missing_or_invalid:" + cell["id"] + ":" + field)
                target[field] += value
    return {
        "complete_stream_role_calls": stream_states["complete"],
        "partial_stream_role_calls": stream_states["partial"],
        "complete_stream_counts": {field: complete[field] for field in FIELDS},
        "partial_stream_observed_counts": {field: partial[field] for field in FIELDS},
        "interpretation": (
            "Public command/message/error-item counters are observed stream items, not "
            "extra model calls or backend attempts. Partial-stream counts are lower-bound "
            "observations and are not added to complete-stream totals. Unclassified "
            "item errors and provider-error events are distinct counters and must not "
            "be summed as unique failures."
        ),
    }


def generation_inventory(result: dict) -> str:
    entries = [row for row in result["provenance"]["input_inventory"]
               if not row["path"].startswith("external-qualification-S/")]
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_generation(result: dict) -> None:
    if result["planned_episodes"] != 24 or result["completed_episodes"] != 24:
        raise ValueError("S24_not_all_terminal")
    if result["episodes_with_response"] != 24 or result["role_model_call_receipts"] != 68:
        raise ValueError("S24_call_receipt_count_mismatch")
    if result["native_check_processes"] != 21:
        raise ValueError("S24_native_check_count_mismatch")
    if not result["integrity"]["passed"]:
        raise ValueError("S24_original_receipt_integrity_failed")
    if result["role_call_status_counts"] != {"completed": 48, "failed": 1, "invalid_output": 19}:
        raise ValueError("S24_role_status_mismatch")
    for field in summarize.FIELDS:
        profile = result["usage"]["fields"][field]
        if profile["missing_calls"] != 1 or profile["complete_sum"] is not None:
            raise ValueError("S24_missing_usage_not_preserved:" + field)
    if any(result["usage_by_arm"][arm]["usage"]["fields"]["input_tokens"]["complete_sum"] is not None
           for arm in result["usage_by_arm"] if arm == "A"):
        raise ValueError("S24_A_failed_call_zero_filled")


def write_new(path: Path, value: dict | str) -> None:
    with path.open("x", encoding="utf-8") as stream:
        if isinstance(value, str):
            stream.write(value)
        else:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=("generation", "final"), required=True)
    args = parser.parse_args()
    root, freeze, out = args.root.resolve(), args.freeze.resolve(), args.out_dir.resolve()
    if digest(freeze) != EXPECTED_FREEZE_SHA256:
        raise ValueError("S24_freeze_hash_mismatch")
    if not out.is_dir():
        raise ValueError("S24_output_directory_missing")
    cells = summarize.read(freeze)["cells"]
    external = root / "external-qualification-S" / "index.json"
    if args.phase == "generation":
        result = summarize.aggregate_cohort(root, freeze, "S24", require_complete=False,
                                            snapshot_at="2026-09-28T00:00:00+00:00")
        validate_generation(result)
        categories = event_categories(root, cells)
        if categories["complete_stream_role_calls"] != 67 or categories["partial_stream_role_calls"] != 1:
            raise ValueError("S24_stream_completion_mismatch")
        receipt = {
            "schema": "opensocrates.go-ts.S24-generation-accounting/1",
            "evidence_state": "generation_complete_external_qualification_separate",
            "freeze_sha256": result["provenance"]["freeze_sha256"],
            "generation_input_inventory_sha256": generation_inventory(result),
            "generation_input_count": len([row for row in result["provenance"]["input_inventory"]
                                           if not row["path"].startswith("external-qualification-S/")]),
            "role_calls": result["role_model_call_receipts"],
            "native_checks": result["native_check_processes"],
            "usage": result["usage"],
            "event_categories": categories,
            "external_index_present_at_generation_receipt": external.is_file(),
            "integrity": result["integrity"],
            "model_calls_by_accounting": 0,
            "candidate_reruns": 0,
        }
        write_new(out / "S24_GENERATION_ACCOUNTING.json", receipt)
        print(json.dumps({"phase": "generation", "calls": 68, "integrity_passed": True,
                          "generation_inventory_sha256": receipt["generation_input_inventory_sha256"]}, sort_keys=True))
        return 0
    if not external.is_file():
        raise ValueError("S24_external_index_pending")
    result = summarize.aggregate_cohort(root, freeze, "S24", require_complete=True)
    validate_generation(result)
    categories = event_categories(root, cells)
    receipt_path = out / "S24_GENERATION_ACCOUNTING.json"
    receipt = summarize.read(receipt_path)
    if receipt["generation_input_inventory_sha256"] != generation_inventory(result):
        raise ValueError("S24_generation_receipts_changed_during_qualification")
    if receipt["event_categories"] != categories:
        raise ValueError("S24_event_categories_changed_during_qualification")
    result["s24_event_categories"] = categories
    result["s24_generation_receipt_sha256"] = "sha256:" + digest(receipt_path)
    result["s24_external_qualification_boundary"] = (
        "External qualification is a separate, serial, zero-model-call assessment; "
        "native qualified_candidate is only a unit terminal state, not external correctness. "
        "Browser transport unassessability requires the parent's separate boundary decision."
    )
    markdown = summarize.render_markdown(result)
    markdown += (
        "\nS24-specific evidence: one Astra A process failed after an observed partial "
        "event stream. All five token fields for that call are null. Cohort and affected "
        "arm/model complete token totals therefore remain unavailable; the known sums "
        "in JSON cover only the other 67 calls. The partial stream's observed public "
        "items are reported separately in `s24_event_categories` and are not complete "
        "event totals. Provider-error counts do not exhaust the public error-item "
        "inventory. Native `qualified_candidate` describes a unit terminal state; "
        "external correctness and browser-transport decisions are separate.\n"
    )
    write_new(out / "S24_USAGE.json", result)
    write_new(out / "S24_USAGE.md", markdown)
    final_receipt = {
        "schema": "opensocrates.go-ts.S24-accounting-final/1",
        "freeze_sha256": result["provenance"]["freeze_sha256"],
        "generation_receipt_sha256": result["s24_generation_receipt_sha256"],
        "full_input_inventory_sha256": result["provenance"]["input_inventory_sha256"],
        "full_input_count": len(result["provenance"]["input_inventory"]),
        "summarizer_sha256": result["provenance"]["summarizer_sha256"],
        "s24_account_sha256": "sha256:" + digest(Path(__file__)),
        "json_sha256": "sha256:" + digest(out / "S24_USAGE.json"),
        "markdown_sha256": "sha256:" + digest(out / "S24_USAGE.md"),
        "role_calls": result["role_model_call_receipts"],
        "native_checks": result["native_check_processes"],
        "external_qualification_reported_model_calls": result["external_qualification"]["reported_model_calls"],
        "integrity": result["integrity"],
        "model_calls_by_accounting": 0,
        "candidate_reruns": 0,
    }
    write_new(out / "S24_ACCOUNTING_FINAL.json", final_receipt)
    print(json.dumps({"phase": "final", "calls": 68, "integrity_passed": True,
                      "full_inventory_sha256": final_receipt["full_input_inventory_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
