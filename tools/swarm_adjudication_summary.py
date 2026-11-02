#!/usr/bin/env python3
"""Describe fixed swarm ratings without majority votes or efficacy conclusions.

Python 3.12 standard library only. --input names a JSON wrapper containing
schema_version=1, reviews_fixed=true, expected_judges, and artifacts. References
are {path, sha256, artifact_id?, frozen_path?}; paths resolve beside the wrapper.
Required artifact roles: freeze, assignments, rubric, analysis_plan, results,
reviews (an array of references). Optional role: blind_mapping.

Assignments/rubric/analysis_plan must be hash-bound by a FROZEN launch-v1
manifest. Results and first reviews are separately hash-pinned after execution.
This verifies byte linkage, not freeze timing, isolation, evidence semantics,
judge independence, or the truth of a caller's reviews_fixed declaration.

Results accept JSONL, a JSON array, or {results: [...]}; reviews similarly accept
{reviews: [...]} or {decisions: [...]}. Review fields: judge_id (or nested
judge_provenance.judge_id), cell_id or blind_id, answer_sha256, quality_verdict
(alias verdict), task_complete, critical_error_assessment, critical_error_labels,
rubric_sha256. S036 critical states are present/none_found/unknown; the draft
complete/partial/unavailable vocabulary is accepted as an explicit adapter.
Blind mapping accepts {mapping: [{blind_id, cell_id, answer_sha256}]} or S047's
public_answer_sha256 alias. When using an S047 custody map, also supply the
judge_packet reference; its hash and the map's source/input links are checked.
A review can bind its answer through that exact packet hash instead of carrying
an answer_sha256 field, matching S036's score-record contract.

Every assigned cell remains represented. Repeated scores cannot add actor
attempts. Conflicting result records and same-judge decisions are quarantined;
missing ratings and unresolved quality/critical disagreements are unscorable.
Public answer text, judge rationales and arbitrary metadata are never copied.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "opensocrates.swarm.adjudication-summary/1.0.0"
FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
LOCALES = ("en", "ko")
ARMS = ("plain", "general-check", "native-opensocrates")
STATUSES = ("NOT_RUN", "STARTED", "COMPLETED", "FAILED", "TIMEOUT", "BLOCKED", "INTERRUPTED")
ATTEMPT_STATUSES = frozenset({"STARTED", "COMPLETED", "FAILED", "TIMEOUT", "INTERRUPTED"})
QUALITY_FIELDS = (
    "quality_verdict",
    "task_complete",
    "critical_error_assessment",
    "critical_error_labels",
)
DECISIVE_FIELDS = ("quality_verdict", "critical_error_assessment", "critical_error_labels")
IDENTITY_FIELDS = (
    "repository",
    "source_sha",
    "product_version",
    "content_revision",
    "host",
    "platform",
    "model_requested",
    "model_observed",
    "effort",
    "service_tier_requested",
    "service_tier_observed",
)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}\Z")
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 10000


class SummaryInputError(ValueError):
    """Only a safe error category, never arbitrary source content."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise SummaryInputError(category)


def identifier(value: Any) -> bool:
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_value: str) -> None:
    raise SummaryInputError("non_finite_json_number")


def decode(raw: bytes, *, jsonl: bool = False) -> Any:
    try:
        text = raw.decode("utf-8")
        if jsonl:
            return [
                json.loads(line, object_pairs_hook=unique_keys, parse_constant=reject_constant)
                for line in text.splitlines()
                if line.strip()
            ]
        return json.loads(text, object_pairs_hook=unique_keys, parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise SummaryInputError("invalid_utf8_or_json") from None


def read_bytes(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(), "input_not_regular_file")
    require(path.stat().st_size <= MAX_BYTES, "input_too_large")
    raw = path.read_bytes()
    require(len(raw) <= MAX_BYTES, "input_too_large")
    return raw


def rows(value: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        found = [key for key in keys if key in value]
        require(len(found) == 1, "ambiguous_or_missing_record_array")
        value = value[found[0]]
    require(isinstance(value, list), "record_array_required")
    require(len(value) <= MAX_ROWS, "too_many_records")
    require(all(isinstance(row, dict) for row in value), "record_object_required")
    return value


class ArtifactSet:
    def __init__(self, wrapper: Path) -> None:
        raw = read_bytes(wrapper)
        self.config = decode(raw)
        require(isinstance(self.config, dict), "wrapper_object_required")
        require(type(self.config.get("schema_version")) is int, "schema_version_required")
        require(self.config["schema_version"] == 1, "unsupported_schema_version")
        require(self.config.get("reviews_fixed") is True, "reviews_must_be_fixed_before_reveal")
        require(isinstance(self.config.get("artifacts"), dict), "artifact_references_required")
        self.root = wrapper.parent
        self.paths = {wrapper.resolve()}
        self.links: dict[str, dict[str, Any]] = {
            "wrapper": {"artifact_id": "wrapper", "sha256": digest(raw)}
        }

    def load(self, role: str, reference: Any = None, *, opaque: bool = False) -> Any:
        ref = self.config["artifacts"].get(role) if reference is None else reference
        require(isinstance(ref, dict), "artifact_reference_required")
        require(isinstance(ref.get("path"), str), "artifact_path_required")
        expected = ref.get("sha256")
        require(
            isinstance(expected, str) and HEX64.fullmatch(expected) is not None,
            "artifact_sha256_required",
        )
        artifact_id = ref.get("artifact_id", role)
        require(identifier(artifact_id), "invalid_artifact_id")
        path = self.root / ref["path"]
        raw = read_bytes(path)
        require(digest(raw) == expected, "artifact_hash_mismatch")
        self.paths.add(path.resolve())
        self.links[role] = {"artifact_id": artifact_id, "sha256": expected}
        return None if opaque else decode(raw, jsonl=path.suffix.lower() == ".jsonl")


def freeze_inputs(artifacts: ArtifactSet) -> dict[str, Any]:
    freeze = artifacts.load("freeze")
    require(isinstance(freeze, dict) and freeze.get("state") == "FROZEN", "freeze_not_frozen")
    source_sha = freeze.get("source_sha")
    require(
        isinstance(source_sha, str) and HEX40.fullmatch(source_sha) is not None,
        "freeze_source_sha_required",
    )
    inputs = rows(freeze.get("input_files"), ())
    indexed: dict[str, str] = {}
    for item in inputs:
        require(isinstance(item.get("path"), str), "freeze_input_path_required")
        sha = item.get("sha256")
        require(
            isinstance(sha, str) and HEX64.fullmatch(sha) is not None,
            "freeze_input_sha256_required",
        )
        require(item["path"] not in indexed, "duplicate_freeze_input_path")
        indexed[item["path"]] = sha
    for role in ("assignments", "rubric", "analysis_plan"):
        # These files may be Markdown; only the ledger is parsed by this tool.
        artifacts.load(role, opaque=role != "assignments")
        ref = artifacts.config["artifacts"][role]
        sha = artifacts.links[role]["sha256"]
        path = ref.get("frozen_path")
        bound = sha in indexed.values() if path is None else indexed.get(path) == sha
        require(bound, "required_input_not_bound_to_freeze")
    return freeze


def assignments(value: Any) -> tuple[dict[str, dict[str, Any]], int]:
    indexed: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in rows(value, ("cells",)):
        case_id, arm, repeat = row.get("case_id"), row.get("arm"), row.get("repeat")
        require(type(repeat) is int and repeat in (1, 2, 3), "invalid_assignment_repeat")
        require(arm in ARMS and isinstance(case_id, str), "invalid_assignment_stratum")
        matching = [(f, loc) for f in FAMILIES for loc in LOCALES if case_id == f"{f}-{loc}"]
        require(len(matching) == 1, "invalid_assignment_case")
        family, locale = matching[0]
        require(
            row.get("family", family) == family and row.get("locale", locale) == locale,
            "contradictory_assignment_stratum",
        )
        cell_id = f"{case_id}-{arm}-r{repeat}"
        require(row.get("cell_id") == cell_id, "noncanonical_assignment_cell_id")
        status = row.get("status", "NOT_RUN")
        require(status in STATUSES, "invalid_assignment_status")
        projected = {
            "cell_id": cell_id,
            "case_id": case_id,
            "family": family,
            "locale": locale,
            "arm": arm,
            "repeat": repeat,
            "status": status,
        }
        if cell_id in indexed:
            require(indexed[cell_id] == projected, "conflicting_assignment_duplicate")
            duplicates += 1
        indexed[cell_id] = projected
    expected = {
        f"{family}-{locale}-{arm}-r{repeat}"
        for family, locale, arm, repeat in itertools.product(FAMILIES, LOCALES, ARMS, (1, 2, 3))
    }
    require(set(indexed) == expected, "assignment_grid_must_contain_54_unique_cells")
    return indexed, duplicates


def safe_identity(value: Any) -> dict[str, Any]:
    supplied = value if isinstance(value, dict) else {}
    result: dict[str, Any] = {}
    for field in IDENTITY_FIELDS:
        item = supplied.get(field)
        valid = (
            isinstance(item, str)
            and 0 < len(item) <= 200
            and not any(ord(character) < 32 for character in item)
        )
        result[field] = item if valid else None
    result["unknown_reasons"] = {
        field: "not_supplied_or_unavailable" for field in IDENTITY_FIELDS if result[field] is None
    }
    return result


def record_ref(artifact: dict[str, Any], index: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": artifact["artifact_id"],
        "row_index": index,
        "record_sha256": digest(canonical(row).encode("utf-8")),
    }


def result_record(row: dict[str, Any], source_sha: str) -> dict[str, Any]:
    status = row.get("status")
    errors: list[str] = []
    if status not in STATUSES:
        status = "INVALID"
        errors.append("invalid_execution_status")
    answer = row.get("public_final_answer")
    if answer is not None and not isinstance(answer, str):
        errors.append("invalid_public_answer_type")
    answer_sha = digest(answer.encode("utf-8")) if isinstance(answer, str) else None
    if answer_sha is not None and status != "COMPLETED":
        errors.append("public_answer_on_noncompleted_result")
    declared = row.get("answer_sha256", row.get("public_final_answer_sha256"))
    if declared is not None and declared != answer_sha:
        errors.append("declared_answer_hash_mismatch")
    identity = safe_identity(row.get("identity"))
    if identity["source_sha"] not in (None, source_sha):
        errors.append("observed_source_sha_mismatch")
    delivery = row.get("delivery_mode", "unknown")
    if isinstance(delivery, str):
        delivery = {
            "none": "no_opensocrates",
            "general-check": "general_check_instruction",
            "native-installed": "native_installation",
            "manual-canonical": "manual_canonical_injection",
        }.get(delivery, delivery)
    if delivery not in (
        "native_installation",
        "manual_canonical_injection",
        "no_opensocrates",
        "general_check_instruction",
    ):
        delivery = "unknown"
    return {
        "status": status,
        "answer_sha256": answer_sha,
        "started_observed": isinstance(row.get("started_at"), str) and bool(row["started_at"]),
        "identity": identity,
        "delivery_mode": delivery,
        "errors": errors,
    }


def index_results(
    value: Any, ledger: dict[str, dict[str, Any]], artifact: dict[str, Any], source_sha: str
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rejected = []
    for number, row in enumerate(rows(value, ("results",))):
        ref = record_ref(artifact, number, row)
        cell_id = row.get("cell_id")
        if not isinstance(cell_id, str) or cell_id not in ledger:
            rejected.append({"category": "unassigned_result", "provenance": ref})
            continue
        record = result_record(row, source_sha)
        record["provenance"] = ref
        indexed[cell_id].append(record)
    return indexed, rejected


def blind_map(value: Any, ledger: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {}
    seen_cells: set[str] = set()
    for row in rows(value, ("mapping",)):
        blind_id, cell_id = row.get("blind_id"), row.get("cell_id")
        sha = row.get("answer_sha256", row.get("public_answer_sha256"))
        if "answer_sha256" in row and "public_answer_sha256" in row:
            require(
                row["answer_sha256"] == row["public_answer_sha256"],
                "contradictory_mapping_hash_alias",
            )
        require(identifier(blind_id), "invalid_blind_id")
        require(isinstance(cell_id, str) and cell_id in ledger, "unassigned_blind_mapping")
        require(
            sha is None or isinstance(sha, str) and HEX64.fullmatch(sha) is not None,
            "invalid_mapping_answer_sha256",
        )
        require(blind_id not in indexed and cell_id not in seen_cells, "duplicate_blind_mapping")
        indexed[blind_id] = {"cell_id": cell_id, "answer_sha256": sha}
        seen_cells.add(cell_id)
    return indexed


def judge_roster(value: Any) -> list[dict[str, Any]]:
    require(isinstance(value, list), "expected_judges_array_required")
    output = []
    seen: set[str] = set()
    for row in value:
        require(isinstance(row, dict) and identifier(row.get("judge_id")), "invalid_judge_id")
        require(row["judge_id"] not in seen, "duplicate_expected_judge")
        seen.add(row["judge_id"])
        kind = row.get("judge_kind", row.get("kind", "unknown"))
        require(
            kind in ("ai", "human", "unknown", "unavailable", "deterministic_assist"),
            "invalid_judge_kind",
        )
        # Independence is never inferred, including from a different requested model.
        independent = row.get("independent")
        require(independent is None or type(independent) is bool, "invalid_judge_independence")
        output.append(
            {
                "judge_id": row["judge_id"],
                "judge_kind": kind,
                "independent_declared": independent,
                "independence_verified": None,
                "independence_reason": "not_verified_by_aggregation",
                "identity": safe_identity(row),
            }
        )
    return output


def review_decision(  # noqa: C901 - normalize each independent scored field explicitly
    row: dict[str, Any],
    rubric_sha: str,
) -> dict[str, Any]:
    quality = row.get("quality_verdict", row.get("verdict"))
    require(quality in ("pass", "fail", "unscorable", None), "invalid_quality_verdict")
    if "quality_verdict" in row and "verdict" in row:
        require(row["quality_verdict"] == row["verdict"], "contradictory_verdict_alias")
    complete = row.get("task_complete")
    require(complete is None or type(complete) is bool, "invalid_task_complete")
    labels = row.get("critical_error_labels")
    require(
        isinstance(labels, list) and all(identifier(label) for label in labels),
        "invalid_critical_labels",
    )
    require(len(labels) == len(set(labels)), "duplicate_critical_label")
    assessment = row.get("critical_error_assessment")
    if assessment == "complete":
        assessment = "present" if labels else "none_found"
    elif assessment in ("partial", "unavailable"):
        assessment = "unknown"
    require(assessment in ("present", "none_found", "unknown"), "invalid_critical_assessment")
    require(assessment != "none_found" or not labels, "contradictory_critical_assessment")
    require(assessment != "present" or bool(labels), "critical_label_missing")
    present = row.get("critical_error_present")
    require(present is None or type(present) is bool, "invalid_critical_present")
    require(not (present is False and labels), "contradictory_critical_present")
    require(not (present is True and assessment == "none_found"), "contradictory_critical_present")
    require(
        quality != "pass" or complete is True and assessment == "none_found" and not labels,
        "pass_rule_not_satisfied",
    )
    require(not labels or quality in ("fail", "unscorable"), "critical_error_cannot_pass")
    provenance = row.get("judge_provenance", {})
    require(isinstance(provenance, dict), "invalid_judge_provenance")
    require(
        row.get("rubric_sha256", provenance.get("rubric_sha256")) == rubric_sha,
        "review_rubric_hash_mismatch",
    )
    burden = row.get("correction_burden", "unknown")
    if isinstance(burden, dict):
        burden = burden.get("state", "unknown")
    if burden not in ("none", "minor", "substantial", "replacement", "unknown"):
        burden = "unknown"
    return {
        "quality_verdict": quality,
        "task_complete": complete,
        "critical_error_assessment": assessment,
        "critical_error_labels": sorted(labels),
        "correction_burden": burden,
    }


def locate_review(
    row: dict[str, Any],
    mapping: dict[str, dict[str, Any]],
    packet_sha: str | None,
) -> tuple[str, str | None]:
    cell_id = row.get("cell_id")
    answer_sha = row.get("answer_sha256")
    if "blind_id" in row:
        require(
            isinstance(row["blind_id"], str) and row["blind_id"] in mapping, "unmapped_blind_review"
        )
        mapped = mapping[row["blind_id"]]
        require(cell_id is None or cell_id == mapped["cell_id"], "contradictory_review_target")
        cell_id = mapped["cell_id"]
        provenance = row.get("judge_provenance", {})
        if answer_sha is None and packet_sha is not None and isinstance(provenance, dict):
            require(provenance.get("packet_sha256") == packet_sha, "review_packet_hash_mismatch")
            answer_sha = mapped["answer_sha256"]
        require(answer_sha == mapped["answer_sha256"], "review_mapping_answer_hash_mismatch")
    require(isinstance(cell_id, str), "review_cell_id_required")
    no_output_rating = row.get("quality_verdict", row.get("verdict")) is None
    require(
        answer_sha is None
        and no_output_rating
        or isinstance(answer_sha, str)
        and HEX64.fullmatch(answer_sha) is not None,
        "review_answer_sha256_required",
    )
    return cell_id, answer_sha


def index_reviews(  # noqa: C901 - malformed records remain visible with safe categories
    artifacts: ArtifactSet,
    ledger: dict[str, dict[str, Any]],
    roster: list[dict[str, Any]],
    mapping: dict[str, dict[str, Any]],
    packet_sha: str | None,
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], list[dict[str, Any]]]:
    references = artifacts.config["artifacts"].get("reviews")
    require(isinstance(references, list), "review_references_array_required")
    require(len(references) <= 100, "too_many_review_artifacts")
    expected = {judge["judge_id"] for judge in roster}
    indexed: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    rejected = []
    for artifact_index, reference in enumerate(references):
        role = f"reviews-{artifact_index + 1}"
        value = artifacts.load(role, reference)
        for number, row in enumerate(rows(value, ("reviews", "decisions"))):
            ref = record_ref(artifacts.links[role], number, row)
            provenance = row.get("judge_provenance", {})
            judge_id = row.get("judge_id")
            if judge_id is None and isinstance(provenance, dict):
                judge_id = provenance.get("judge_id")
            # Preserve a known target even when a later digest/decision check fails.
            cell_id = row.get("cell_id")
            if not isinstance(cell_id, str):
                cell_id = None
            blind_id = row.get("blind_id")
            if isinstance(blind_id, str) and blind_id in mapping:
                cell_id = mapping[blind_id]["cell_id"]
            try:
                cell_id, answer_sha = locate_review(row, mapping, packet_sha)
                require(cell_id in ledger, "unassigned_review")
                require(isinstance(judge_id, str) and judge_id in expected, "unexpected_judge")
                if isinstance(provenance, dict) and provenance.get("judge_id") is not None:
                    require(provenance["judge_id"] == judge_id, "contradictory_judge_identity")
                if packet_sha is not None:
                    require(
                        isinstance(provenance, dict)
                        and provenance.get("packet_sha256") == packet_sha,
                        "review_packet_hash_mismatch",
                    )
                decision = review_decision(row, artifacts.links["rubric"]["sha256"])
                decision.update(answer_sha256=answer_sha, errors=[], provenance=ref)
            except SummaryInputError as exc:
                rejected.append({"category": str(exc), "provenance": ref})
                # A malformed duplicate must not leave an otherwise favorable slot usable.
                if (
                    cell_id not in ledger
                    or not isinstance(judge_id, str)
                    or judge_id not in expected
                ):
                    continue
                decision = {"errors": [str(exc)], "provenance": ref}
            indexed[cell_id][judge_id].append(decision)
    return indexed, rejected


def variants(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for record in records:
        decision = {key: value for key, value in record.items() if key != "provenance"}
        key = canonical(decision)
        if key not in groups:
            groups[key] = {**decision, "record_count": 0, "provenance": []}
        groups[key]["record_count"] += 1
        groups[key]["provenance"].append(record["provenance"])
    return [groups[key] for key in sorted(groups)]


def judge_slots(
    records: dict[str, list[dict[str, Any]]],
    roster: list[dict[str, Any]],
    answer_sha: str | None,
) -> list[dict[str, Any]]:
    output = []
    for judge in roster:
        submitted = records.get(judge["judge_id"], [])
        unique = variants(submitted)
        state = "valid"
        if not submitted:
            state = "missing"
        elif any(item["errors"] for item in unique):
            state = "invalid"
        elif any(item.get("answer_sha256") != answer_sha for item in unique):
            state = "stale_answer"
        elif (
            len({canonical({field: item[field] for field in QUALITY_FIELDS}) for item in unique})
            > 1
        ):
            state = "conflicting_duplicate"
        elif judge["judge_kind"] in ("unavailable", "deterministic_assist"):
            state = "not_an_available_quality_judge"
        output.append(
            {
                "judge_id": judge["judge_id"],
                "state": state,
                "record_count": len(submitted),
                "duplicate_records": len(submitted) - len(unique),
                "variants": unique,
            }
        )
    return output


def cell_summary(  # noqa: C901 - denominator and missingness decisions stay together
    assignment: dict[str, Any],
    records: list[dict[str, Any]],
    reviews: dict[str, list[dict[str, Any]]],
    roster: list[dict[str, Any]],
) -> dict[str, Any]:
    result_variants = variants(records)
    statuses = sorted({record["status"] for record in result_variants})
    status = statuses[0] if len(result_variants) == 1 else "CONFLICTING_RESULTS"
    if not result_variants:
        status = assignment["status"]
    attempted = assignment["status"] in ATTEMPT_STATUSES or any(
        record["status"] in ATTEMPT_STATUSES
        or record["started_observed"]
        or record["status"] == "INVALID"
        or record["answer_sha256"] is not None
        for record in records
    )
    unique = result_variants[0] if len(result_variants) == 1 else None
    answer_sha = unique["answer_sha256"] if unique else None
    eligible = bool(unique and not unique["errors"] and status == "COMPLETED" and answer_sha)
    slots = judge_slots(reviews, roster, answer_sha)
    decisions = [slot["variants"][0] for slot in slots if slot["state"] == "valid"]
    missing = [slot["judge_id"] for slot in slots if slot["state"] == "missing"]
    blocked = [slot["judge_id"] for slot in slots if slot["state"] not in ("valid", "missing")]
    disagreement = (
        len({canonical({field: row[field] for field in DECISIVE_FIELDS}) for row in decisions}) > 1
    )
    completion_disagreement = len({row["task_complete"] for row in decisions}) > 1
    quality: str | None = None
    score_state = "execution_unavailable"
    complete = None
    critical = "unknown"
    if eligible:
        quality = "unscorable"
        if not roster:
            score_state = "no_available_judges"
        elif missing or blocked:
            score_state = "missing_or_invalid_required_review"
        elif disagreement:
            score_state = "unresolved_disagreement"
        elif decisions and decisions[0]["quality_verdict"] is not None:
            quality = decisions[0]["quality_verdict"]
            complete = None if completion_disagreement else decisions[0]["task_complete"]
            critical = decisions[0]["critical_error_assessment"]
            score_state = "single_provisional_rating" if len(decisions) == 1 else "unanimous_rating"
        else:
            score_state = "missing_quality_verdict"
    elif status == "COMPLETED" or status == "CONFLICTING_RESULTS":
        quality, score_state = "unscorable", "result_unavailable_or_conflicting"
    labels = sorted(
        {
            label
            for slot in slots
            for item in slot["variants"]
            if eligible and not item["errors"] and item.get("answer_sha256") == answer_sha
            for label in item.get("critical_error_labels", [])
        }
    )
    burdens = sorted(
        {item.get("correction_burden", "unknown") for slot in slots for item in slot["variants"]}
    )
    return {
        **{
            field: assignment[field]
            for field in ("cell_id", "case_id", "family", "locale", "arm", "repeat")
        },
        "attempted": attempted,
        "execution_status": status,
        "execution_status_evidence": statuses,
        "missing_result": not bool(records),
        "result_variants": result_variants,
        "duplicate_result_records": len(records) - len(result_variants),
        "result_conflict": len(result_variants) > 1,
        "answer_sha256": answer_sha,
        "quality_verdict": quality,
        "score_state": score_state,
        "evaluable": eligible and quality in ("pass", "fail"),
        "task_complete": complete,
        "critical_error_consensus": critical,
        "critical_error_labels_observed": labels,
        "critical_error_presence_disputed_or_unknown": bool(labels) and critical != "present",
        "correction_burden_ratings": burdens,
        "judges": slots,
        "missing_judges": missing,
        "invalid_or_conflicting_judges": blocked,
        "judge_disagreement": disagreement,
        "completion_disagreement": completion_disagreement,
        "same_judge_conflict": any(slot["state"] == "conflicting_duplicate" for slot in slots),
        "adjudication_rule": "no_automatic_resolution",
        "application_evidence": "unverified",
    }


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
        "unavailable_reason": None if denominator else "zero_denominator",
    }


def aggregate(cells: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = [row for row in cells if row["attempted"]]
    evaluable = [row for row in cells if row["evaluable"]]
    passed = sum(row["quality_verdict"] == "pass" for row in cells)
    quality_counts = Counter(row["quality_verdict"] or "null_due_to_execution" for row in cells)
    critical_counts = Counter(row["critical_error_consensus"] for row in attempted)
    return {
        "assigned_cells": len(cells),
        "all_attempted_denominator": len(attempted),
        "evaluable_denominator": len(evaluable),
        "execution_status_counts": {
            status: sum(row["execution_status"] == status for row in cells)
            for status in (*STATUSES, "INVALID", "CONFLICTING_RESULTS")
        },
        "quality_counts": {
            key: quality_counts[key]
            for key in ("pass", "fail", "unscorable", "null_due_to_execution")
        },
        "critical_error_counts_among_attempted": {
            key: critical_counts[key] for key in ("present", "none_found", "unknown")
        },
        "critical_error_observed_cells": sum(
            bool(row["critical_error_labels_observed"]) for row in cells
        ),
        "critical_error_label_counts": dict(
            sorted(
                Counter(
                    label for row in cells for label in row["critical_error_labels_observed"]
                ).items()
            )
        ),
        "completion_counts_among_attempted": {
            "true": sum(row["task_complete"] is True for row in attempted),
            "false": sum(row["task_complete"] is False for row in attempted),
            "unknown": sum(row["task_complete"] is None for row in attempted),
        },
        "disagreement_cells": sum(row["judge_disagreement"] for row in cells),
        "same_judge_conflict_cells": sum(row["same_judge_conflict"] for row in cells),
        "completion_disagreement_cells": sum(row["completion_disagreement"] for row in cells),
        "missing_result_cells": sum(row["missing_result"] for row in cells),
        "result_conflict_cells": sum(row["result_conflict"] for row in cells),
        "missing_review_cells": sum(bool(row["missing_judges"]) for row in cells),
        "missing_judge_slots": sum(len(row["missing_judges"]) for row in cells),
        "invalid_or_conflicting_review_cells": sum(
            bool(row["invalid_or_conflicting_judges"]) for row in cells
        ),
        "duplicate_result_records": sum(row["duplicate_result_records"] for row in cells),
        "duplicate_review_records": sum(
            slot["duplicate_records"] for row in cells for slot in row["judges"]
        ),
        "observed_success_per_attempt": fraction(passed, len(attempted)),
        "observed_success_per_assigned": fraction(passed, len(cells)),
        "attempt_coverage": fraction(len(attempted), len(cells)),
        "conditional_pass_per_evaluable": fraction(passed, len(evaluable)),
    }


def build_summary(wrapper: Path) -> tuple[dict[str, Any], set[Path]]:
    artifacts = ArtifactSet(wrapper)
    freeze = freeze_inputs(artifacts)
    ledger, duplicate_assignments = assignments(artifacts.load("assignments"))
    roster = judge_roster(artifacts.config.get("expected_judges"))
    result_index, rejected_results = index_results(
        artifacts.load("results"), ledger, artifacts.links["results"], freeze["source_sha"]
    )
    mapping = {}
    packet_sha = None
    if "blind_mapping" in artifacts.config["artifacts"]:
        mapping_value = artifacts.load("blind_mapping")
        mapping = blind_map(mapping_value, ledger)
        if isinstance(mapping_value, dict) and "reviewer_packet_sha256" in mapping_value:
            artifacts.load("judge_packet", opaque=True)
            packet_sha = artifacts.links["judge_packet"]["sha256"]
            require(
                mapping_value["reviewer_packet_sha256"] == packet_sha,
                "mapping_packet_hash_mismatch",
            )
            require(
                mapping_value.get("source_sha") == freeze["source_sha"],
                "mapping_source_sha_mismatch",
            )
            input_hashes = mapping_value.get("input_sha256")
            require(isinstance(input_hashes, dict), "mapping_input_hashes_required")
            for map_role, role in (
                ("safe_results", "results"),
                ("assignments", "assignments"),
                ("freeze", "freeze"),
            ):
                require(
                    input_hashes.get(map_role) == artifacts.links[role]["sha256"],
                    "mapping_input_hash_mismatch",
                )
    review_index, rejected_reviews = index_reviews(artifacts, ledger, roster, mapping, packet_sha)
    cells = [
        cell_summary(ledger[key], result_index.get(key, []), review_index.get(key, {}), roster)
        for key in sorted(ledger)
    ]
    strata = {}
    for dimensions in (("arm",), ("family",), ("locale",), ("arm", "family", "locale")):
        groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in cells:
            groups[tuple(row[dimension] for dimension in dimensions)].append(row)
        strata["_".join(dimensions)] = [
            {**dict(zip(dimensions, values, strict=True)), **aggregate(group)}
            for values, group in sorted(groups.items())
        ]
    summary = {
        "schema": SCHEMA,
        "source_sha": freeze["source_sha"],
        "provenance": artifacts.links,
        "freeze": {
            "state": "FROZEN",
            "byte_links_checked": True,
            "timing_verified": None,
            "timing_reason": "no_trusted_clock_or_execution_attestation",
            "isolation_state_declared": freeze.get("isolation_state")
            if freeze.get("isolation_state") in ("UNVERIFIED", "VERIFIED", "BLOCKED")
            else None,
        },
        "reviews_fixed_declared": True,
        "review_lock_verified": None,
        "judge_roster": roster,
        "judge_roster_predeclared_verified": None,
        "overall": aggregate(cells),
        "strata": strata,
        "cells": cells,
        "data_quality": {
            "duplicate_assignment_records": duplicate_assignments,
            "rejected_results": rejected_results,
            "rejected_reviews": rejected_reviews,
        },
        "boundaries": [
            "Descriptive counts only; no significance, superiority, effect generalization or retention inference.",
            "Attempts are unique assigned cells with start/terminal evidence; failures/timeouts/interruptions remain.",
            "NOT_RUN and pre-start BLOCKED remain in assigned counts and are shown separately from attempts.",
            "Missing, invalid, stale or conflicting reviews never create passes or extra actor attempts.",
            "First ratings and all dissent remain; no majority, optimistic tie-break or adjudicator override.",
            "Observed critical labels are not a resolved critical-error finding when ratings conflict.",
            "Single available ratings are provisional; declared independence and backend identity are not verified.",
            "Review evidence semantics, predeclared label membership and criterion completeness are not regraded.",
            "Native installation, manual injection, entry, read, application and usefulness remain distinct.",
            "Unknown observed models/tier/delivery remain unknown; no native application receipt is created.",
            "No answer text, rationale, raw log, credentials, hidden reasoning or screenshots are emitted.",
        ],
    }
    return summary, artifacts.paths


def write_output(path: Path, summary: dict[str, Any], *, overwrite: bool) -> None:
    require(not path.is_symlink() and not path.is_dir(), "unsafe_output_target")
    require(overwrite or not path.exists(), "output_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            # Exclusive publication also refuses a concurrently created target.
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True, help="Hash-pinned aggregation wrapper JSON"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Descriptive adjudication summary JSON"
    )
    parser.add_argument(
        "--allow-overwrite", action="store_true", help="Replace an existing summary explicitly"
    )
    args = parser.parse_args(argv)
    try:
        summary, inputs = build_summary(args.input)
        require(args.output.resolve() not in inputs, "output_cannot_replace_input")
        if args.output.exists():
            require(
                not any(os.path.samefile(args.output, item) for item in inputs),
                "output_cannot_replace_input",
            )
        write_output(args.output, summary, overwrite=args.allow_overwrite)
    except SummaryInputError as exc:
        parser.exit(2, f"adjudication summary refused: {exc}\n")
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        parser.exit(2, "adjudication summary refused: unreadable_or_malformed_artifact\n")
    print("wrote descriptive adjudication summary; no statistical conclusion generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
