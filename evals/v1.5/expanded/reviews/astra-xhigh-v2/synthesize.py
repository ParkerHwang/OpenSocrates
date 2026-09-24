"""Join treatment identity only after the complete rating lock is verified."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from validate_review import AXES
from verify_review import sha, verify

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def critical_status(gates: list[dict]) -> str:
    if any(gate["status"] == "fail" for gate in gates):
        return "fail"
    if not gates or any(gate["status"] == "unassessable" for gate in gates):
        return "unassessable"
    return "pass"


def aggregate(rows: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in key_fields)].append(row)
    output = []
    for key, entries in sorted(groups.items(), key=lambda pair: str(pair[0])):
        group = {**dict(zip(key_fields, key, strict=True)), "packets": len(entries), "phases": {}}
        for phase, score_field, gate_field in (
            ("first_pass", "first_pass_scores", "critical_gates"),
            ("after_evidence", "post_evidence_scores", "post_evidence_critical_gates"),
        ):
            scores = {}
            for axis in AXES:
                values = [
                    entry[score_field][axis]["score"]
                    for entry in entries
                    if entry[score_field][axis]["score"] is not None
                ]
                counts = Counter(entry[score_field][axis]["status"] for entry in entries)
                scores[axis] = {
                    "rated": len(values),
                    "histogram": {str(score): values.count(score) for score in range(5)},
                    "median_available": statistics.median(values) if values else None,
                    "mean_available": round(statistics.mean(values), 3) if values else None,
                    "min": min(values) if values else None,
                    "max": max(values) if values else None,
                    "unassessable": counts["unassessable"],
                    "not_applicable": counts["not_applicable"],
                }
            group["phases"][phase] = {
                "scores": scores,
                "packet_critical_status": dict(
                    Counter(critical_status(entry[gate_field]) for entry in entries)
                ),
            }
        output.append(group)
    return output


def bilingual_pairs(rows: list[dict]) -> list[dict]:
    """Describe matched language cells without pooling cohorts or imputing nulls."""
    keys = ("cohort", "lane", "family", "arm", "solver_model", "repetition")
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    output = []
    for key, entries in sorted(groups.items(), key=lambda pair: str(pair[0])):
        by_locale = defaultdict(list)
        for entry in entries:
            by_locale[entry["locale"]].append(entry)
        if "ko" not in by_locale:
            continue
        pair = {
            **dict(zip(keys, key, strict=True)),
            "packet_ids": {
                locale: [entry["packet_id"] for entry in values]
                for locale, values in sorted(by_locale.items())
            },
            "direction": "Korean minus English; descriptive ordinal differences only",
            "phases": {},
        }
        if len(by_locale["en"]) != 1 or len(by_locale["ko"]) != 1:
            pair["status"] = "unassessable_pair"
            output.append(pair)
            continue
        pair["status"] = "matched"
        english, korean = by_locale["en"][0], by_locale["ko"][0]
        for phase in ("first_pass_scores", "post_evidence_scores"):
            pair["phases"][phase] = {
                axis: {
                    "en": english[phase][axis]["score"],
                    "ko": korean[phase][axis]["score"],
                    "difference": (
                        korean[phase][axis]["score"] - english[phase][axis]["score"]
                        if english[phase][axis]["score"] is not None
                        and korean[phase][axis]["score"] is not None
                        else None
                    ),
                }
                for axis in AXES
            }
        output.append(pair)
    return output


def main() -> None:  # noqa: C901
    verification = verify(complete=True)  # The treatment maps are not opened before this gate.
    manifest = read(HERE / "manifest.json")
    for name, expected in manifest["unblinding_hashes"].items():
        assert sha(BASE / name) == expected
    source_map = {row["packet_id"]: row["cell_id"] for row in read(BASE / "unblinding-v2.json")}
    diagnostic_map = {
        row["packet_id"]: row["cell_id"] for row in read(BASE / "diagnostic-unblinding.json")
    }
    rows = []
    first = {}
    for assignment in manifest["assignment_order"]:
        first_response = read(
            HERE / "assessments" / f"{assignment['assignment_id']}-first_pass.json"
        )
        first.update({packet["packet_id"]: packet for packet in first_response["packets"]})
        response = read(HERE / "assessments" / f"{assignment['assignment_id']}-evidence.json")
        for assessment in response["packets"]:
            identifier = assessment["packet_id"]
            if identifier in source_map:
                cell_id = source_map[identifier]
                original = read(BASE / "results-v2" / cell_id / "result.json")
                cell = original["cell"]
                identity = {
                    "cohort": "expanded-guide2",
                    "lane": original["lane"],
                    "arm": cell["arm"],
                    "solver_model": cell["model"],
                    "solver_effort": cell["effort"],
                    "locale": original["locale"],
                    "repetition": cell["repetition"],
                    "task": original["task"],
                    "original_deterministic_success": original["deterministic_success"],
                }
            else:
                cell_id = diagnostic_map[identifier]
                version = cell_id.split("-")[0]
                original = read(BASE / f"diagnostic-results-{version}" / cell_id / "result.json")
                cell = original["cell"]
                identity = {
                    "cohort": f"diagnostic-{version}",
                    "lane": "DIAG-" + cell["kind"],
                    "arm": version,
                    "solver_model": cell["model"],
                    "solver_effort": cell["effort"],
                    "locale": cell["locale"],
                    "repetition": 1,
                    "task": cell["task"],
                    "original_deterministic_success": original["diagnostic_pass"],
                }
            source = next(
                packet for packet in manifest["packets"] if packet["packet_id"] == identifier
            )
            rows.append(
                {
                    **identity,
                    "packet_id": identifier,
                    "cell_id": cell_id,
                    "family": source["family"],
                    "assignment_id": assignment["assignment_id"],
                    "original_packet_sha256": source["original_sha256"],
                    "first_pass_view_sha256": source["first_pass_sha256"],
                    **{
                        key: value
                        for key, value in assessment.items()
                        if key not in {"packet_id", "packet_sha256", "locale"}
                    },
                    "assessor": "opensocrates_bilingual_reviewer",
                    "assessor_model": "gpt-6-astra",
                    "assessor_effort": "xhigh",
                    "human_scores": None,
                    "human_status": "unavailable",
                    "provisional": True,
                }
            )
    assert len(rows) == 60
    calls = []
    for path in sorted((HERE / "attempts").glob("*/*/*/receipt.json")):
        receipt = read(path)
        calls.append(
            {
                "path": str(path.relative_to(HERE)),
                "phase": path.parts[-3],
                "exit_code": receipt["exit_code"],
                "process_success": receipt["process_success"],
                "wall_seconds": receipt["wall_seconds"],
                "usage": receipt["usage"],
                "tool_actions": receipt["tool_actions_started_or_completed"],
                "failed_tool_actions": receipt["failed_tool_actions"],
                "validation": read(path.parent / "validation.json"),
            }
        )
    previous = HERE.with_name("astra-xhigh-v1")
    old_call = read(previous / "attempts/A01/first_pass/attempt-01/receipt.json")
    probe = read(previous / "preflight/transport-diagnostic.json")
    all_usage = [call["usage"] for call in calls] + [old_call["usage"], probe["usage"]]
    usage = {}
    for key in (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    ):
        values = [(item or {}).get(key) for item in all_usage]
        usage[key] = {
            "sum_available": sum(value for value in values if value is not None),
            "missing_calls": sum(value is None for value in values),
            "complete_total": sum(values) if all(value is not None for value in values) else None,
        }
    disagreements = [
        {
            "packet_id": row["packet_id"],
            "cohort": row["cohort"],
            "lane": row["lane"],
            "locale": row["locale"],
            **entry,
        }
        for row in rows
        for entry in row["disagreements"]
        if entry["category"] != "no_disagreement"
    ]
    cooccurrences = [
        {
            "packet_id": row["packet_id"],
            "cohort": row["cohort"],
            "lane": row["lane"],
            "locale": row["locale"],
            "original_deterministic_success": row["original_deterministic_success"],
            "ai_critical_status": critical_status(row["post_evidence_critical_gates"]),
        }
        for row in rows
        if (
            row["original_deterministic_success"]
            and critical_status(row["post_evidence_critical_gates"]) != "pass"
        )
        or (
            not row["original_deterministic_success"]
            and critical_status(row["post_evidence_critical_gates"]) == "pass"
        )
    ]
    output = {
        "schema": "opensocrates.provisional-ai-review-synthesis/1.0.0",
        "verification": verification,
        "manifest_sha256": sha(HERE / "manifest.json"),
        "all_ratings_lock_sha256": sha(HERE / "locks/all-ratings.lock.json"),
        "packets": 60,
        "reviewer_configurations": 1,
        "human_reviews": 0,
        "human_scores": None,
        "accepted_assignments_per_phase": 17,
        "v2_review_attempts": len(calls),
        "prior_rejected_review_calls": 1,
        "zero_packet_transport_diagnostics": 1,
        "total_cli_attempts": len(calls) + 2,
        "usage": usage,
        "billed_cost": None,
        "backend_model_echo": None,
        "blinding": dict(Counter(row["blinding_status"] for row in rows)),
        "per_lane_language_condition": aggregate(
            rows, ("cohort", "lane", "locale", "arm", "solver_model")
        ),
        "per_lane_language": aggregate(rows, ("cohort", "lane", "locale")),
        "per_task_language_condition": aggregate(
            rows, ("cohort", "lane", "task", "locale", "arm", "solver_model")
        ),
        "bilingual_pairs": bilingual_pairs(rows),
        "disagreements": disagreements,
        "machine_pass_ai_flag_cooccurrences": cooccurrences,
        "limits": [
            "One provisional Astra/xhigh assessor configuration; fresh contexts are not independent humans.",
            "The evidence phase uses a fresh context with its own locked first pass; score changes are descriptive and may include rerating variation, not a causal estimate of evidence disclosure.",
            "Original deterministic scores and outcome artifacts remain unchanged.",
            "Means exclude explicit nulls and are descriptive within cohorts, not held-out performance estimates.",
            "The 0-4 anchors are ordinal; histograms/medians are primary descriptions and numeric means do not establish equal-interval quality or a practical noninferiority margin.",
            "Critical failures and unassessable gates remain separate from scalar scores.",
            "Local context controls do not prove account-side isolation or complete blinding.",
            "No profile promotion, numerical margin, sample-size invention, or release approval follows.",
        ],
    }
    save(HERE / "unblinded-assessments.json", rows)
    save(HERE / "review-usage-ledger.json", calls)
    save(HERE / "synthesis.json", output)
    save(
        HERE / "review-integrity.json",
        {
            str(path.relative_to(HERE)): sha(path)
            for directory in ("assessments", "attempts", "locks")
            for path in sorted((HERE / directory).rglob("*"))
            if path.is_file()
        },
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in output.items()
                if key
                not in {
                    "per_lane_language_condition",
                    "per_lane_language",
                    "per_task_language_condition",
                    "bilingual_pairs",
                    "disagreements",
                    "machine_pass_ai_flag_cooccurrences",
                }
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
