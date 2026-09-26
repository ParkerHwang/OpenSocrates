"""Join treatment identity only after the complete rating lock is verified."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from validate_review import AXES
from verify_review import ROOT, attempt_ledger, sha, verify

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
    result_integrity = read(HERE / "analysis-input-integrity.json")
    for name, expected in result_integrity["result_files"].items():
        assert sha(ROOT / name) == expected, name
    for name, expected in manifest["unblinding_hashes"].items():
        assert sha(BASE / name) == expected
    source_map = {row["packet_id"]: row["cell_id"] for row in read(BASE / "unblinding-v2.json")}
    diagnostic_map = {
        row["packet_id"]: row["cell_id"] for row in read(BASE / "diagnostic-unblinding.json")
    }
    rows = []
    locked = read(HERE / "locks/all-ratings.lock.json")
    for assignment_id, reference in locked["assessments"].items():
        response = read(ROOT / reference["path"])
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
                    "domain": (
                        "coding"
                        if source["family"]
                        in {
                            "v2-eval01-coding-transition",
                            "v2-eval02-coding-invoice",
                            "developer_collaboration",
                        }
                        else "general"
                    ),
                    "assignment_id": assignment_id,
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
    calls = attempt_ledger(complete=True)
    configuration_preflights = [
        {
            "path": str(path.relative_to(ROOT)),
            "receipt": read(path),
            "model_calls": 0,
            "usage_status": "not_applicable_non_model",
        }
        for path in sorted(
            (HERE.with_name("astra-xhigh-v1") / "preflight").glob("configuration-*.json")
        )
    ]
    all_usage = [call["usage"] for call in calls]
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
    resources = {}
    for key in ("wall_seconds", "tool_actions", "failed_tool_actions", "incomplete_tool_actions"):
        values = [call[key] for call in calls]
        resources[key] = {
            "sum_available": round(sum(value for value in values if value is not None), 3),
            "missing_calls": sum(value is None for value in values),
            "complete_total": (
                round(sum(values), 3) if all(value is not None for value in values) else None
            ),
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
        "schema": "opensocrates.provisional-ai-review-synthesis/4.0.0",
        "verification": verification,
        "manifest_sha256": sha(HERE / "manifest.json"),
        "original_result_integrity_sha256": sha(HERE / "analysis-input-integrity.json"),
        "all_ratings_lock_sha256": sha(HERE / "locks/all-ratings.lock.json"),
        "packets": 60,
        "reviewer_configurations": 1,
        "human_reviews": 0,
        "human_scores": None,
        "accepted_first_pass_assignments": 17,
        "accepted_evidence_assignments": len(locked["assessments"]),
        "v2_review_attempts": sum(call["version"] == "astra-xhigh-v2" for call in calls),
        "v3_review_attempts": sum(call["version"] == "astra-xhigh-v3" for call in calls),
        "v4_review_attempts": sum(call["version"] == "astra-xhigh-v4" for call in calls),
        "validation_rejected_assessments": sum(
            call["process_success"] and not call["validation"]["valid"] for call in calls
        ),
        "prior_rejected_review_calls": 1,
        "zero_packet_transport_diagnostics": 1,
        "evidence_timeouts": sum(call["timed_out"] for call in calls),
        "coordinator_interruptions": sum(
            call["invocation_error"] == "coordinator_interrupted_after_repeated_timeouts"
            for call in calls
        ),
        "model_review_transport_attempts": len(calls),
        "local_configuration_inspections": configuration_preflights,
        "usage": usage,
        "review_execution_resources": resources,
        "billed_cost": None,
        "backend_model_echo": None,
        "blinding": dict(Counter(row["blinding_status"] for row in rows)),
        "per_lane_domain_language_condition": aggregate(
            rows, ("cohort", "lane", "domain", "locale", "arm", "solver_model")
        ),
        "per_lane_domain_language": aggregate(rows, ("cohort", "lane", "domain", "locale")),
        "per_task_language_condition": aggregate(
            rows, ("cohort", "lane", "task", "locale", "arm", "solver_model")
        ),
        "bilingual_pairs": bilingual_pairs(rows),
        "disagreements": disagreements,
        "machine_pass_ai_flag_cooccurrences": cooccurrences,
        "limits": [
            "One provisional Astra/xhigh assessor configuration; fresh contexts are not independent humans.",
            "The evidence phase uses a fresh context with its own locked first pass; score changes are descriptive and may include rerating variation, not a causal estimate of evidence disclosure.",
            "V3 splits failed/pending evidence assignments into at most two packets, with three concurrent calls; the prior A01 evidence assessment is retained. Batching and continuation selection are disclosed, not treated as a quality experiment.",
            "V4 retains 56 completed evidence packets and reviews four singly after two citation rejections and another timeout; only syntax/batch guidance changes, not role, rubric, validator, or scores.",
            "Original deterministic scores and outcome artifacts remain unchanged.",
            "Means exclude explicit nulls and are descriptive within cohorts, not held-out performance estimates.",
            "The 0-4 anchors are ordinal; histograms/medians are primary descriptions and numeric means do not establish equal-interval quality or a practical noninferiority margin.",
            "Critical failures and unassessable gates remain separate from scalar scores.",
            "Local context controls do not prove account-side isolation or complete blinding.",
            "Input includes cached input; reported reasoning output is a subset of output. Do not add these categories. Summed per-call wall time is work accounting, not elapsed end-to-end time, because calls overlap. Review resource use is separate from candidate resource outcomes.",
            "No profile promotion, numerical margin, sample-size invention, or release approval follows.",
        ],
    }
    save(HERE / "unblinded-assessments.json", rows)
    save(HERE / "review-usage-ledger.json", calls)
    save(HERE / "synthesis.json", output)
    save(
        HERE / "review-integrity.json",
        {
            str(path.relative_to(ROOT)): sha(path)
            for version in ("astra-xhigh-v1", "astra-xhigh-v2", "astra-xhigh-v3", "astra-xhigh-v4")
            for directory in ("assessments", "attempts", "locks")
            for path in sorted((HERE.with_name(version) / directory).rglob("*"))
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
                    "per_lane_domain_language_condition",
                    "per_lane_domain_language",
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
