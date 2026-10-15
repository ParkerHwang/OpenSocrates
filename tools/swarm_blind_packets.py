#!/usr/bin/env python3
"""Prepare blind review packets from launch-v1 public synthetic results.

This tool makes no model calls and does not score answers. Supply S044's sanitized
result JSONL and separate intake-review JSONL, all six public cases, the S036 rubric,
the 54-cell assignment ledger, a pre-result
FROZEN manifest, and a custodian-held seed file. JSON case/assignment files may be
lists or objects with a ``cases``/``cells`` list. All inputs are explicit; no host,
account, transcript, authentication, or workspace discovery occurs.

The freeze's input_files SHA-256 inventory must bind the exact case file, rubric, ledger,
seed bytes and this generator. Keep the seed and freeze away from reviewers. A
fixed secret seed determines both opaque IDs and reviewer order; rerunning with
the same inputs is deterministic. Neither arm labels nor run-order metadata are
copied into the reviewer JSON. Public final answer strings, including whitespace
and method mentions, are copied whole. Private-looking content rejects the whole
generation instead of producing selectively redacted answers.

--output and --map-output are new files in existing separate, non-nested reviewer
and custodian directories. Existing files and linked path components are refused.
Give only --output to reviewers; lock independent scores before revealing the map.
This is metadata blinding, not proof that answer text conceals its condition or
that a reviewer/provider/backend is independent. No historical study is replayed.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import stat
import sys
import tempfile
from collections import Counter
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any

FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
LOCALES = ("en", "ko")
ARMS = ("plain", "general-check", "native-opensocrates")
REPEATS = (1, 2, 3)
STATUSES = {"NOT_RUN", "STARTED", "COMPLETED", "FAILED", "TIMEOUT", "BLOCKED"}
ACTOR_BUDGET = 54
MAX_INPUT_BYTES = 16 * 1024 * 1024
RESULT_KEYS = {
    "cell_id",
    "status",
    "public_final_answer",
    "started_at",
    "ended_at",
    "elapsed_ms",
    "input_tokens",
    "output_tokens",
    "critical_error_labels",
    "task_complete",
    "entry_emitted",
    "canonical_full_read",
    "application_evidence",
    "failure_reason",
    "identity",
}
NULLABLE_RESULT_KEYS = {
    "public_final_answer",
    "started_at",
    "ended_at",
    "elapsed_ms",
    "input_tokens",
    "output_tokens",
    "task_complete",
    "entry_emitted",
    "canonical_full_read",
    "failure_reason",
}
IDENTITY_KEYS = {
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
}
INTAKE_KEYS = {
    "schema_version",
    "source_id",
    "run_id",
    "attempt_id",
    "case_id",
    "locale",
    "manual_review",
    "delivery_mode",
    "independent_evaluation",
    "unknown_reasons",
}
FAILURE_REASONS = {
    "EXECUTION_FAILED",
    "TIMEOUT",
    "INTERRUPTED",
    "RESOURCE_BLOCKED",
    "ISOLATION_UNVERIFIED",
    "BUDGET_EXHAUSTED",
    "HOST_UNAVAILABLE",
    "OUTPUT_UNAVAILABLE",
    "PRIVACY_REVIEW_PENDING",
    "CANCELLED",
    "UNKNOWN",
    "call_failed",
    "deadline_exceeded",
    "interrupted_after_start",
    "call_outcome_unknown",
    "freeze_unavailable",
    "isolation_unverified",
    "resource_unavailable",
    "host_unavailable",
    "owner_stopped",
    "preflight_unavailable",
    "host_error",
    "timeout",
    "interrupted",
    "dispatch_uncertain",
    "answer_unavailable",
    "budget_exhausted",
    "other_safe_category",
}
CASE_KEYS = (
    "case_id",
    "family",
    "locale",
    "public_synthetic_input",
    "required_outcome",
    "critical_errors",
    "expected_numeric_facts",
)
AXES = (
    "task_completion",
    "factuality",
    "constraint_compliance",
    "critical_errors",
    "correction_burden",
)
RUBRIC_KEYS = ("verdicts", "dimensions", "common_critical_errors", "evidence_contract")
TASK_KEY_FIELDS = (
    "precedence",
    "criterion_evaluation",
    "critical_label_rule",
    "pointer_rule",
    "conflict",
)
KEY_REFERENCE_FIELDS = (
    "family",
    "path",
    "case_ids",
    "locale_case_pointers",
    "actor_input_relative_pointers",
    "required_outcome_relative_pointers",
    "critical_error_relative_pointers",
    "fact_check_relative_pointers",
    "shared_key_absolute_pointers",
    "locale_key_absolute_pointers",
    "criterion_ids",
    "critical_error_labels",
    "common_check_focus",
    "exact_key_rule",
)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_SHA = re.compile(r"[0-9a-f]{40}\Z")
EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@([A-Z0-9.-]{1,253}\.[A-Z]{2,63})", re.I)
PRIVATE_TEXT = re.compile(
    r"(?:/(?:Users|home|root|tmp|private|var|etc|opt|Volumes|Library|Applications|System|mnt|workspace|workspaces|srv)/"
    # A drive/token must not start inside a public URL scheme or schema identifier.
    r"|(?<!\w)[A-Z]:[\\/]|(?<!\w)~/"
    r"|\\\\[^\s\\]+\\|file://|(?<!\w)(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~-]{12,}"
    r"|<(?:think|analysis)>|\b(?:account_id|oauth_token|access_token|refresh_token)\s*[:=]"
    r"|https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(?=[:/\s]|$))",
    re.I,
)
FORBIDDEN_CASE_KEYS = {
    "arm",
    "cell_id",
    "repeat",
    "order_index",
    "assignment_seed",
    "identity",
    "model",
    "model_requested",
    "model_observed",
    "host",
    "installation",
    "entry_emitted",
    "canonical_full_read",
    "application_evidence",
    "score",
    "verdict",
    "failure_reason",
    "reasoning",
    "transcript",
    "credentials",
    "account_id",
}


class PacketError(Exception):
    """A safe error category; never include an input value or raw exception."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, "packet_generation_refused:cli_arguments\n")


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PacketError("duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_value: str) -> None:
    raise PacketError("nonfinite_json_number")


def decode(payload: bytes) -> Any:
    try:
        return json.loads(
            payload.decode("utf-8"), object_pairs_hook=object_pairs, parse_constant=reject_constant
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PacketError("invalid_json_or_utf8") from exc


def read_bytes(path: Path) -> bytes:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
            raise PacketError("regular_bounded_input_required")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            payload = stream.read(MAX_INPUT_BYTES + 1)
        if len(payload) > MAX_INPUT_BYTES:
            raise PacketError("input_too_large")
        return payload
    except OSError as exc:
        raise PacketError("input_unavailable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def records(value: Any, key: str) -> list[dict[str, Any]]:
    items = value.get(key) if isinstance(value, dict) else value
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise PacketError("expected_record_list")
    return items


def public_text(value: Any) -> None:
    """Reject known private categories without rewriting any public string.

    This bounded check cannot certify that arbitrary prose is public. S038/S044
    provenance review and a custodian privacy check remain necessary.
    """
    if isinstance(value, str):
        scan_text(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            public_text(key)
            public_text(item)
    elif isinstance(value, list):
        for item in value:
            public_text(item)


def scan_text(value: str) -> None:
    if PRIVATE_TEXT.search(value):
        raise PacketError("private_content_category")
    for match in EMAIL.finditer(value):
        domain = match.group(1).lower()
        reserved = ("example.com", "example.net", "example.org", "test", "invalid", "localhost")
        if not any(domain == suffix or domain.endswith("." + suffix) for suffix in reserved):
            raise PacketError("non_synthetic_account_category")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise PacketError("invalid_unicode_scalar") from exc


def task_fields(value: Any) -> None:
    if isinstance(value, dict):
        if FORBIDDEN_CASE_KEYS.intersection(value):
            raise PacketError("condition_metadata_in_public_criteria")
        for item in value.values():
            task_fields(item)
    elif isinstance(value, list):
        for item in value:
            task_fields(item)


def prepare_cases(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for item in items:
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or case_id in cases:
            raise PacketError("invalid_or_duplicate_case_id")
        if (item.get("family"), item.get("locale")) not in set(product(FAMILIES, LOCALES)):
            raise PacketError("invalid_case_stratum")
        if case_id != f"{item['family']}-{item['locale']}":
            raise PacketError("case_id_not_launch_v1")
        if not isinstance(item.get("public_synthetic_input"), (str, dict, list)):
            raise PacketError("missing_public_synthetic_input")
        if not item.get("required_outcome") or not isinstance(item.get("critical_errors"), list):
            raise PacketError("missing_public_criteria")
        case = {key: item[key] for key in CASE_KEYS if key in item}
        task_fields(case.get("required_outcome"))
        task_fields(case.get("critical_errors"))
        task_fields(case.get("expected_numeric_facts"))
        public_text(case)
        cases[case_id] = case
    if set(cases) != {f"{family}-{locale}" for family, locale in product(FAMILIES, LOCALES)}:
        raise PacketError("six_cases_required")
    return cases


def prepare_rubric(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or any(key not in value for key in RUBRIC_KEYS):
        raise PacketError("public_scoring_rubric_required")
    rubric = {key: value[key] for key in RUBRIC_KEYS}
    if not isinstance(rubric["dimensions"], dict) or not set(AXES).issubset(rubric["dimensions"]):
        raise PacketError("scoring_dimensions_mismatch")
    contract = value.get("task_key_contract")
    if isinstance(contract, dict):
        rubric["task_key_contract"] = {
            key: contract[key] for key in TASK_KEY_FIELDS if key in contract
        }
        references = records(contract.get("references", []), "references")
        rubric["task_key_contract"]["references"] = [
            {key: item[key] for key in KEY_REFERENCE_FIELDS if key in item} for item in references
        ]
    task_fields(rubric)
    public_text(rubric)
    return rubric


def prepare_cells(items: list[dict[str, Any]], cases: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cells: dict[str, dict[str, Any]] = {}
    combinations: set[tuple[str, str, int]] = set()
    order: set[int] = set()
    for item in items:
        case_id, arm, repeat = item.get("case_id"), item.get("arm"), item.get("repeat")
        if (
            case_id not in cases
            or arm not in ARMS
            or type(repeat) is not int
            or repeat not in REPEATS
        ):
            raise PacketError("invalid_cell_stratum")
        cell_id = item.get("cell_id")
        if cell_id != f"{case_id}-{arm}-r{repeat}" or cell_id in cells:
            raise PacketError("invalid_or_duplicate_cell_id")
        index = item.get("order_index")
        if type(index) is not int or index not in range(1, ACTOR_BUDGET + 1) or index in order:
            raise PacketError("invalid_or_duplicate_order_index")
        if item.get("status") not in STATUSES:
            raise PacketError("invalid_assignment_status")
        combinations.add((case_id, arm, repeat))
        order.add(index)
        cells[cell_id] = item
    if len(cells) != ACTOR_BUDGET or combinations != set(product(cases, ARMS, REPEATS)):
        raise PacketError("complete_54_cell_assignment_required")
    return cells


def parse_reviews(payload: bytes, cells: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reviews: dict[str, dict[str, Any]] = {}
    for line in payload.splitlines():
        if not line.strip():
            continue
        review = decode(line)
        if not isinstance(review, dict) or set(review) != INTAKE_KEYS | {
            "cell_id",
            "result_sha256",
        }:
            raise PacketError("unexpected_intake_control_fields")
        cell_id = review.get("cell_id")
        if not isinstance(cell_id, str) or cell_id not in cells or cell_id in reviews:
            raise PacketError("unknown_or_duplicate_intake_cell")
        if not isinstance(review["result_sha256"], str) or not SHA256.fullmatch(
            review["result_sha256"]
        ):
            raise PacketError("intake_result_hash_required")
        public_text(review)
        reviews[cell_id] = review
    return reviews


def prepare_result(line: bytes, cells: dict[str, Any], seen: dict[str, Any]) -> dict[str, Any]:
    result = decode(line)
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise PacketError("unexpected_result_fields")
    cell_id = result.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in cells or cell_id in seen:
        raise PacketError("unknown_or_duplicate_result_cell")
    if result.get("status") not in STATUSES:
        raise PacketError("invalid_result_status")
    answer = result.get("public_final_answer")
    if answer is not None and not isinstance(answer, str):
        raise PacketError("invalid_public_answer_type")
    validate_result_metadata(result)
    public_text(result)
    return result


def parse_results(
    payload: bytes,
    cells: dict[str, Any],
    reviews: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    run_ids: set[str] = set()
    for line in payload.splitlines():
        if not line.strip():
            continue
        result = prepare_result(line, cells, results)
        cell_id = result["cell_id"]
        review = reviews.get(cell_id)
        if review is None:
            raise PacketError("matching_intake_control_required")
        joined = {**result, **review}
        validate_intake(joined, result["public_final_answer"], cells[cell_id])
        canonical_result = json.dumps(
            result, ensure_ascii=False, allow_nan=False, sort_keys=True
        ).encode("utf-8")
        if review["result_sha256"] != digest(canonical_result):
            raise PacketError("intake_result_hash_mismatch")
        run_ids.add(joined["run_id"])
        results[cell_id] = joined
    if len(run_ids) > 1:
        raise PacketError("mixed_result_runs")
    if set(results) != set(reviews):
        raise PacketError("intake_without_matching_result")
    return results


def validate_identity(identity: Any) -> None:
    if not isinstance(identity, dict) or set(identity) != IDENTITY_KEYS:
        raise PacketError("unexpected_identity_fields")
    for value in identity.values():
        if value is not None and (not isinstance(value, str) or len(value) > 128):
            raise PacketError("invalid_public_identity_label")
    repository = identity.get("repository")
    if repository not in (
        None,
        "ParkerHwang/OpenSocrates",
        "https://github.com/ParkerHwang/OpenSocrates",
    ):
        raise PacketError("public_repository_identity_required")
    source_sha = identity.get("source_sha")
    if source_sha is not None and SOURCE_SHA.fullmatch(source_sha) is None:
        raise PacketError("invalid_result_source_sha")


def validate_result_metadata(result: dict[str, Any]) -> None:
    validate_identity(result.get("identity"))
    validate_measurements(result)
    for key in ("task_complete", "entry_emitted", "canonical_full_read"):
        if result.get(key) is not None and type(result[key]) is not bool:
            raise PacketError("invalid_observation_boolean")
    labels = result.get("critical_error_labels", [])
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        raise PacketError("invalid_critical_error_labels")
    if result.get("application_evidence", "unverified") not in (
        "unverified",
        "unknown",
        "unavailable",
    ):
        raise PacketError("unsupported_application_assertion")
    if result.get("failure_reason") is not None and result["failure_reason"] not in FAILURE_REASONS:
        raise PacketError("unsafe_failure_category")


def validate_measurements(result: dict[str, Any]) -> None:
    for key in ("started_at", "ended_at"):
        if result.get(key) is not None:
            timestamp(result[key])
    if result.get("started_at") is not None and result.get("ended_at") is not None:
        if timestamp(result["ended_at"]) < timestamp(result["started_at"]):
            raise PacketError("result_timestamp_order")
    for key in ("elapsed_ms", "input_tokens", "output_tokens"):
        value = result.get(key)
        if value is not None and (
            type(value) not in (int, float) or value < 0 or not math.isfinite(value)
        ):
            raise PacketError("invalid_observed_measurement")


def validate_intake(result: dict[str, Any], answer: Any, cell: dict[str, Any]) -> None:
    """Consume S044's separate bounded control without exposing it to reviewers."""
    if "schema_version" in result and (
        type(result["schema_version"]) is not int or result["schema_version"] != 1
    ):
        raise PacketError("intake_schema_mismatch")
    if "source_id" in result and result["source_id"] != "manual-public-synthetic":
        raise PacketError("public_synthetic_source_required")
    for key in ("case_id", "locale"):
        expected = cell["case_id"] if key == "case_id" else cell["case_id"].rsplit("-", 1)[1]
        if key in result and result[key] != expected:
            raise PacketError("intake_assignment_mismatch")
    if (
        "attempt_id" in result
        and result["attempt_id"] != f"{result['run_id']}:{cell['cell_id']}:a1"
    ):
        raise PacketError("single_first_attempt_required")
    if "run_id" in result and (
        not isinstance(result["run_id"], str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", result["run_id"]) is None
    ):
        raise PacketError("invalid_public_run_label")
    if "delivery_mode" in result:
        expected = {
            "plain": "none",
            "general-check": "general-check",
            "native-opensocrates": "native-installed",
        }
        if result["delivery_mode"] not in (expected[cell["arm"]], "unknown", "unavailable"):
            raise PacketError("delivery_deviation_not_native_evidence")
    validate_review(result, answer)
    validate_unknown_reasons(result)


def validate_review(result: dict[str, Any], answer: Any) -> None:
    review = result.get("manual_review")
    if answer is None and review is None:
        return
    checks = ("synthetic_only", "sensitive_content_checked", "final_answer_only")
    if not isinstance(review, dict) or set(review) != {"status", *checks}:
        raise PacketError("public_answer_approval_required")
    expected_status, expected_value = (
        ("NO_PUBLIC_OUTPUT", None) if answer is None else ("APPROVED", True)
    )
    if review["status"] != expected_status or any(
        review[key] is not expected_value for key in checks
    ):
        raise PacketError("public_answer_approval_required")


def validate_unknown_reasons(result: dict[str, Any]) -> None:
    if result.get("independent_evaluation", "unknown") not in (
        "unknown",
        "unavailable",
        "not_assessed",
    ):
        raise PacketError("unsupported_evaluator_assertion")
    if "unknown_reasons" not in result:
        return
    reasons = result["unknown_reasons"]
    allowed_keys = NULLABLE_RESULT_KEYS | {f"identity.{key}" for key in IDENTITY_KEYS}
    allowed_reasons = {
        "UNKNOWN",
        "UNAVAILABLE",
        "NOT_OBSERVED",
        "NOT_APPLICABLE",
        "NOT_RUN",
        "WITHHELD_PENDING_REVIEW",
    }
    if not isinstance(reasons, dict) or set(reasons) - allowed_keys:
        raise PacketError("unexpected_unknown_reason_fields")
    if not all(isinstance(value, str) and value in allowed_reasons for value in reasons.values()):
        raise PacketError("unsafe_unknown_reason_category")
    expected_keys = {key for key in NULLABLE_RESULT_KEYS if result[key] is None}
    expected_keys |= {f"identity.{key}" for key in IDENTITY_KEYS if result["identity"][key] is None}
    if set(reasons) != expected_keys:
        raise PacketError("null_reason_mismatch")


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PacketError("missing_timezone_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PacketError("invalid_timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PacketError("missing_timestamp_timezone")
    return parsed


def prepare_freeze(freeze: Any, required_hashes: list[str]) -> datetime:
    if not isinstance(freeze, dict) or freeze.get("state") != "FROZEN":
        raise PacketError("pre_result_freeze_required")
    if freeze.get("approved_by") != "S001" or freeze.get("quota") != ACTOR_BUDGET:
        raise PacketError("freeze_authority_or_quota_mismatch")
    if not isinstance(freeze.get("source_sha"), str) or not SOURCE_SHA.fullmatch(
        freeze["source_sha"]
    ):
        raise PacketError("freeze_exact_source_sha_required")
    inventory = freeze.get("input_files")
    if not isinstance(inventory, list) or not all(isinstance(item, dict) for item in inventory):
        raise PacketError("freeze_input_inventory_required")
    hashes = [item.get("sha256") for item in inventory]
    if not all(isinstance(value, str) and SHA256.fullmatch(value) for value in hashes):
        raise PacketError("invalid_freeze_input_hash")
    if not set(required_hashes).issubset(hashes):
        raise PacketError("generator_cases_assignments_or_seed_not_frozen")
    return timestamp(freeze.get("frozen_at"))


def unknown(reason: str) -> dict[str, Any]:
    return {"value": None, "reason": reason}


def decision_form(blind_id: str) -> dict[str, Any]:
    return {
        "blind_id": blind_id,
        "reviewer_alias": None,
        "verdict": None,
        "allowed_verdicts": ["pass", "fail", "unscorable"],
        "axes": {axis: {"assessment": None, "public_evidence": []} for axis in AXES},
        "task_complete": None,
        "critical_error_assessment": None,
        "critical_error_labels": [],
        "criterion_findings": [],
        "public_rationale": None,
        "condition_inference_from_answer_text": unknown("Reviewer has not assessed textual cues."),
        "locked_at": None,
    }


def reviewer_provenance() -> dict[str, Any]:
    return {
        "reviewer_alias": None,
        "reviewer_kind": unknown("No evaluator has been assigned or called by this tool."),
        "reviewer_provider": unknown("No evaluator provider evidence supplied."),
        "reviewer_model_observed": unknown("No backend evaluator identity observation supplied."),
        "independent_human": unknown("An independent human review has not been confirmed."),
        "provider_independence": unknown(
            "Actor and evaluator provider independence is unconfirmed."
        ),
        "author_or_actor_conflict": unknown("Evaluator role and prior exposure need confirmation."),
        "map_unseen_before_lock": unknown("Custodian must obtain an actual reviewer attestation."),
    }


def masked_token(seed: bytes, domain: bytes, cell_id: str) -> str:
    return hmac.new(seed, domain + b"\0" + cell_id.encode("utf-8"), hashlib.sha256).hexdigest()


def build_packets(
    cases: dict[str, Any],
    rubric: dict[str, Any],
    cells: dict[str, Any],
    results: dict[str, Any],
    seed: bytes,
    frozen_at: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    packets: list[dict[str, Any]] = []
    mapping: list[dict[str, Any]] = []
    ordered = sorted(cells, key=lambda cell_id: masked_token(seed, b"review-order-v1", cell_id))
    for cell_id in ordered:
        cell, result = cells[cell_id], results.get(cell_id)
        blind_id = "B-" + masked_token(seed, b"blind-id-v1", cell_id)[:24]
        answer = result.get("public_final_answer") if result is not None else None
        started_at = result.get("started_at") if result is not None else None
        ended_at = result.get("ended_at") if result is not None else None
        if any(
            value is not None and timestamp(value) < frozen_at for value in (started_at, ended_at)
        ):
            raise PacketError("result_observed_before_freeze")
        packets.append(
            {
                "blind_id": blind_id,
                "case": cases[cell["case_id"]],
                "public_final_answer": answer,
                "decision_form": decision_form(blind_id),
            }
        )
        mapping.append(
            {
                "blind_id": blind_id,
                "cell_id": cell_id,
                "case_id": cell["case_id"],
                "arm": cell["arm"],
                "repeat": cell["repeat"],
                "order_index": cell["order_index"],
                "execution_status": result["status"] if result is not None else cell["status"],
                "result_record_present": result is not None,
                "public_answer_present": answer is not None,
                "public_answer_sha256": digest(answer.encode("utf-8"))
                if answer is not None
                else None,
                "safe_result_sha256": result.get("result_sha256") if result is not None else None,
                "actor_identity": result.get("identity") if result is not None else None,
                "actor_identity_unknowns": {
                    key: unknown(
                        result.get("unknown_reasons", {}).get(f"identity.{key}", "NOT_OBSERVED")
                        if result is not None
                        else "NOT_OBSERVED"
                    )
                    for key in IDENTITY_KEYS
                    if result is None or (result.get("identity") or {}).get(key) is None
                },
                "independent_evaluation": result.get("independent_evaluation", "unknown")
                if result is not None
                else "unknown",
                "delivery_mode": result.get("delivery_mode") if result is not None else None,
                "delivery_mode_reason": (
                    "Input provenance assertion only; no installation/read/application receipt is created."
                    if result is not None and result.get("delivery_mode") is not None
                    else "Delivery mode was not supplied or observed."
                ),
                "freeze_precedes_start": (
                    True
                    if started_at is not None
                    else unknown("Observed start timestamp unavailable.")
                ),
            }
        )
    if len({item["blind_id"] for item in mapping}) != ACTOR_BUDGET:
        raise PacketError("blind_id_collision")
    reviewer = {
        "schema": "opensocrates.swarm-blind-packets/1",
        "schema_version": 1,
        "evidence_level": "public_synthetic_materials_prepared_no_judging_performed",
        "planned_cell_count": ACTOR_BUDGET,
        "reviewer_provenance": reviewer_provenance(),
        "rubric": rubric,
        "review_instructions": [
            "Review each complete public answer against its public task and frozen criteria.",
            "Pass only when required deliverables, supported facts and constraints are satisfied, "
            "with no predeclared critical error; otherwise record fail or unscorable with evidence.",
            "Keep completion, factuality, constraints, critical errors and correction burden separate.",
            "Empty critical labels do not establish that every critical check passed.",
            "For each finding record a criterion ID, public answer span, frozen task-key reference "
            "and concise public rationale; do not disclose private reasoning.",
            "A null answer is unavailable, not a semantic failure: record unscorable. An empty "
            "answer string is a preserved answer and can fail completion.",
            "Do not infer execution success from an answer. All assigned cells remain accounted for.",
            "Execution status is withheld here. After text ratings lock, the custodian applies the "
            "frozen execution-eligibility rule: no non-COMPLETED cell becomes a study pass from a text rating.",
            "Do not contact recipients, run actor calls, retrieve provider metadata or reveal mappings.",
            "Lock first ratings independently before discussion or map disclosure; preserve dissent.",
        ],
        "blinding_limits": [
            "Answer text is complete and unchanged, including method mentions and self-identification; "
            "it can reveal a condition despite removed external metadata.",
            "Formatting and repeated task facts may also permit condition or repetition inference.",
            "Preparing a packet establishes neither evaluator independence nor a model backend identity.",
            "A privacy pattern check is bounded; custodian review is required before disclosure.",
        ],
        "packets": packets,
    }
    return reviewer, mapping


def checked_path(path: Path) -> Path:
    path = Path(os.path.abspath(os.fspath(path)))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PacketError("linked_output_component")
    return path


def output_paths(output: Path, mapping: Path, inputs: list[Path]) -> tuple[Path, Path]:
    output, mapping = checked_path(output), checked_path(mapping)
    parents = output.parent, mapping.parent
    if parents[0] == parents[1] or any(
        left in right.parents for left, right in (parents, parents[::-1])
    ):
        raise PacketError("reviewer_and_custodian_directories_must_be_separate")
    for target in (output, mapping):
        if not target.parent.is_dir() or target.exists():
            raise PacketError("new_file_in_existing_directory_required")
        if any(target == path.resolve() for path in inputs):
            raise PacketError("output_input_collision")
    return output, mapping


def stage(path: Path, payload: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".blind-packet-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def publish(output: Path, reviewer: bytes, mapping: Path, custody: bytes) -> None:
    """Exclusive publication; remove only our map link if reviewer publish fails."""
    staged: list[Path] = []
    map_published = False
    try:
        staged.append(stage(mapping, custody))
        staged.append(stage(output, reviewer))
        checked_path(mapping)
        checked_path(output)
        os.link(staged[0], mapping)
        map_published = True
        os.link(staged[1], output)
    except BaseException:
        if (
            map_published
            and mapping.exists()
            and os.path.samestat(mapping.lstat(), staged[0].lstat())
        ):
            mapping.unlink()
        raise
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)


def generate(args: argparse.Namespace) -> int:
    input_paths = [
        args.input,
        args.review_input,
        args.cases,
        args.rubric,
        args.assignments,
        args.freeze,
        args.seed_file,
        Path(__file__),
    ]
    output, mapping = output_paths(args.output, args.map_output, input_paths)
    (
        result_bytes,
        review_bytes,
        case_bytes,
        rubric_bytes,
        cell_bytes,
        freeze_bytes,
        seed,
        source_bytes,
    ) = map(read_bytes, input_paths)
    if len(seed) < 32 or len(seed) > 4096:
        raise PacketError("private_seed_requires_32_to_4096_bytes")
    freeze = decode(freeze_bytes)
    case_data, rubric_data, cell_data = map(decode, (case_bytes, rubric_bytes, cell_bytes))
    for value in (freeze, case_data, rubric_data, cell_data):
        public_text(value)
    frozen_at = prepare_freeze(
        freeze,
        [digest(value) for value in (case_bytes, rubric_bytes, cell_bytes, seed, source_bytes)],
    )
    cases = prepare_cases(records(case_data, "cases"))
    rubric = prepare_rubric(rubric_data)
    cells = prepare_cells(records(cell_data, "cells"), cases)
    reviews = parse_reviews(review_bytes, cells)
    results = parse_results(result_bytes, cells, reviews)
    reviewer, links = build_packets(cases, rubric, cells, results, seed, frozen_at)
    reviewer_bytes = encoded(reviewer)
    custody = {
        "schema": "opensocrates.swarm-blind-map/1",
        "schema_version": 1,
        "custody": "RESTRICTED_UNTIL_INDEPENDENT_RATINGS_LOCKED",
        "source_sha": freeze["source_sha"],
        "reviewer_packet_sha256": digest(reviewer_bytes),
        "input_sha256": {
            "safe_results": digest(result_bytes),
            "intake_review": digest(review_bytes),
            "cases": digest(case_bytes),
            "rubric": digest(rubric_bytes),
            "assignments": digest(cell_bytes),
            "freeze": digest(freeze_bytes),
            "private_seed_commitment": digest(seed),
            "generator": digest(source_bytes),
        },
        "planned_cells": ACTOR_BUDGET,
        "result_records": len(results),
        "execution_status_counts": dict(
            sorted(Counter(item["execution_status"] for item in links).items())
        ),
        "reviewer_provenance": reviewer_provenance(),
        "claim_boundaries": [
            "The seed is fixed by the supplied freeze inventory, which is not a trusted timestamp signature.",
            "Native installation, entry, full canonical reading, application and usefulness are distinct; "
            "an arm label or packet is evidence of none of them.",
            "Manual canonical injection must not be relabeled as a native-installed arm.",
            "Backend model identity is unavailable here; requested configuration does not establish it.",
            "Count all attempted cells including FAILED/TIMEOUT; separately report NOT_RUN/BLOCKED, "
            "missing results and unscorable ratings. Never exclude them to improve a rate.",
            "No quality retries, favorable rerolls, model calls, judge calls or human validation occur here.",
            "The 100 authoring chats are not experimental controls; the full actor budget is 54 single turns.",
        ],
        "mapping": links,
    }
    publish(output, reviewer_bytes, mapping, encoded(custody))
    print(
        json.dumps({"packet_count": ACTOR_BUDGET, "result_records": len(results), "model_calls": 0})
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag, help_text in (
        ("--input", "S044 sanitized launch-v1 result JSONL; never raw host output"),
        (
            "--review-input",
            "S044 separate intake-review JSONL, bound to exact public result hashes",
        ),
        ("--cases", "six public synthetic launch-v1 cases JSON"),
        ("--rubric", "S036 frozen public scoring rubric JSON; condition metadata is not projected"),
        (
            "--assignments",
            "complete immutable frozen launch-v1 54-cell plan JSON, not a later mutated ledger",
        ),
        ("--freeze", "custodian-held pre-result FROZEN launch-v1 manifest"),
        ("--seed-file", "private fixed seed bytes, committed by hash in the pre-result freeze"),
        ("--output", "new reviewer blind-packets.json file"),
        ("--map-output", "new restricted blind-map.json in a separate non-nested directory"),
    ):
        parser.add_argument(flag, type=Path, required=True, help=help_text)
    args = parser.parse_args(argv)
    try:
        return generate(args)
    except PacketError as exc:
        print(f"packet_generation_refused:{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("packet_generation_refused:interrupted", file=sys.stderr)
        return 130
    except (OSError, UnicodeError, RecursionError, TypeError, ValueError, OverflowError) as exc:
        # Never echo raw errors: they can contain local paths or input values.
        print(f"packet_generation_refused:{type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
