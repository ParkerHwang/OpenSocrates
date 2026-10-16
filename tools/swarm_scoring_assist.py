#!/usr/bin/env python3
"""Generate deterministic scoring hints and an unfinished human decision form.

Python 3.12 standard library only; no model, network, host or credential access.
Run after integration and protocol freeze, never as an actor or an evaluator:

    python tools/swarm_scoring_assist.py --input bundle.json --output rubric-assist.json

The JSON bundle contains launch-v1 ``cases``, ``cells``, ``results`` and ``freeze``.
Alternatively ``results_file`` names S044's safe-results.jsonl relative to the
bundle (explicit absolute paths are also accepted). Do not supply both forms.
Optional ``intake_reviews`` or ``review_file`` carries S044's separate control
records. Delivery-mode assertions are used only when their result hash matches.
``retention_contract`` must be ``public-synthetic-only-v1``. This declaration is
not a detector for private text: only S044-approved public synthetic material may
be supplied. No prompt, transcript, screenshot or hidden reasoning is needed.

Optional, predeclared case.scoring_assist contract, to freeze before any actor:

    {"numeric_facts": [{"id": "profit", "expected_value": "60",
        "calculation": {"operation": "subtract", "operands": ["100", "40"]}}],
     "required_artifacts": [{"id": "draft", "literal_markers": ["Draft:"]}]}

Launch-v1 expected_numeric_facts also accepts that numeric list or an object
mapping fact IDs to decimal values. Other shapes remain explicitly unsupported.
Calculations check the authored key with Decimal, never infer the answer's
calculation. A number or literal occurrence can be negated, conditional, quoted,
obsolete, a rejected alternative, or attached to another unit. Absence can mean
paraphrase. Neither occurrence nor absence proves a semantic pass or failure.

All human_decision fields stay null. Completed blank answers get a *draft* fail
for observable incompleteness; other answers await human judgment. Infrastructure
failures get an execution-unscorable classification, separately from semantic
quality uncertainty, and stay in attempted denominators. This output
is NOT a blind judge packet: S047 must remove execution and delivery metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime
from decimal import Decimal, DecimalException, Inexact, localcontext
from pathlib import Path
from typing import Any

SCHEMA = "opensocrates.swarm-rubric-assist/1"
BASE_SHA = "227a528996d93c423851db1d663f9572be534e59"
ACTOR_BUDGET = 54
MAX_BYTES = 16 * 1024 * 1024
MAX_ANSWER_CHARS = 200_000
MAX_CHECKS = 128
MAX_HITS = 100
STATUSES = ("NOT_RUN", "STARTED", "COMPLETED", "FAILED", "TIMEOUT", "BLOCKED")
ATTEMPT_STATUSES = {"STARTED", "COMPLETED", "FAILED", "TIMEOUT"}
FAMILIES = {"email-agreement", "changed-recommendation", "price-profit"}
ARMS = {"plain", "general-check", "native-opensocrates"}
FORBIDDEN_FIELDS = {
    "prompt",
    "raw_prompt",
    "user_prompt",
    "transcript",
    "raw_transcript",
    "messages",
    "raw_logs",
    "host_logs",
    "credentials",
    "access_token",
    "refresh_token",
    "api_key",
    "screenshot",
    "screenshots",
    "hidden_reasoning",
    "chain_of_thought",
    "reasoning",
    "auth",
    "authentication",
    "workspace_content",
    "authorization",
    "password",
    "secret",
    "cookie",
    "cookies",
    "oauth",
    "raw_output",
    "event_stream",
    "conversation",
    "private_prompt",
    "system_prompt",
}
FORBIDDEN_NORMALIZED = {re.sub(r"[^a-z0-9]", "", key) for key in FORBIDDEN_FIELDS}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}\Z")
DECIMAL_LITERAL = re.compile(r"[+-]?[0-9]{1,40}(?:\.[0-9]{1,20})?\Z")
# ASCII decimal-dot convention only. Commas are thousands separators only in
# complete groups. Unsupported local notations are a human-review limitation.
NUMBER = re.compile(
    r"(?<![0-9.,])[-+]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
    r"(?:\.[0-9]+)?(?![0-9]|[.,][0-9])"
)
WARNINGS = [
    "Numeric/literal occurrence is a location hint, never semantic correctness.",
    "Negation, conditional mentions, quotations, units and rejected alternatives need review.",
    "Missing markers may be paraphrases; no keyword rule produces a quality pass.",
    "Arithmetic checks verify only declared reference operands and values.",
    "Native installation, entry, full read, application and answer quality are separate.",
    "Manual canonical injection is not native installed delivery.",
    "No native application receipt or independent evaluator is inferred.",
    "All attempts remain counted; no favorable reruns or post-result threshold changes.",
    "54 authored actor cells are the budget; the 100 authoring chats are not controls.",
    "This artifact is a draft assistance form, not an adjudicated score or blind packet.",
]


class InputError(ValueError):
    """A safe category only; never include rejected input content in errors."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise InputError(category)


def identifier(value: Any) -> str:
    require(
        isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None, "invalid_identifier"
    )
    return str(value)


def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_: str) -> None:
    raise InputError("nonfinite_json_number")


def parse_json(payload: str) -> Any:
    return json.loads(payload, object_pairs_hook=object_pairs, parse_constant=reject_constant)


def safe_fields(node: Any, depth: int = 0) -> None:
    require(depth <= 32, "input_too_deep")
    if isinstance(node, dict):
        require(
            not FORBIDDEN_NORMALIZED.intersection(
                re.sub(r"[^a-z0-9]", "", key.lower()) for key in node
            ),
            "forbidden_private_field",
        )
        for value in node.values():
            safe_fields(value, depth + 1)
    elif isinstance(node, list):
        for value in node:
            safe_fields(value, depth + 1)


def read_bytes(path: Path) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(MAX_BYTES + 1)
    require(len(payload) <= MAX_BYTES, "input_too_large")
    return payload


def read_jsonl_reference(path: Path, name: Any) -> tuple[list[Any], str]:
    require(isinstance(name, str) and bool(name), "invalid_jsonl_reference")
    reference = Path(name)
    if not reference.is_absolute():
        reference = path.parent / reference
    payload = read_bytes(reference)
    rows = [parse_json(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    require(len(rows) <= ACTOR_BUDGET, "actor_budget_exceeded")
    return rows, hashlib.sha256(payload).hexdigest()


def read_bundle(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    payload = read_bytes(path)
    bundle = parse_json(payload.decode("utf-8"))
    require(isinstance(bundle, dict), "bundle_must_be_object")
    require(
        bundle.get("retention_contract") == "public-synthetic-only-v1",
        "public_synthetic_declaration_required",
    )
    digests = {"bundle_sha256": hashlib.sha256(payload).hexdigest()}
    for inline, reference in (("results", "results_file"), ("intake_reviews", "review_file")):
        require(not (inline in bundle and reference in bundle), "ambiguous_record_sources")
        if reference in bundle:
            bundle[inline], digests[f"{inline}_file_sha256"] = read_jsonl_reference(
                path, bundle[reference]
            )
    safe_fields(bundle)
    return bundle, digests


def index_records(value: Any, key: str, limit: int) -> dict[str, dict[str, Any]]:
    require(isinstance(value, list) and len(value) <= limit, "invalid_record_list")
    indexed: dict[str, dict[str, Any]] = {}
    for record in value:
        require(isinstance(record, dict), "record_must_be_object")
        record_id = identifier(record.get(key))
        require(record_id not in indexed, "duplicate_record_no_retry_allowed")
        indexed[record_id] = record
    return indexed


def decimal_value(value: Any) -> Decimal:
    require(not isinstance(value, bool), "invalid_decimal")
    text = str(value)
    require(DECIMAL_LITERAL.fullmatch(text) is not None, "unsupported_decimal_notation")
    return Decimal(text)


def calculate(spec: dict[str, Any]) -> Decimal:
    operands = spec.get("operands")
    require(isinstance(operands, list) and 2 <= len(operands) <= 16, "invalid_calculation_operands")
    values = [decimal_value(value) for value in operands]
    operation = spec.get("operation")
    require(operation in {"add", "subtract", "multiply", "divide"}, "unsupported_calculation")
    with localcontext() as context:
        context.prec = 80
        context.traps[Inexact] = True
        result = values[0]
        for value in values[1:]:
            if operation == "add":
                result += value
            elif operation == "subtract":
                result -= value
            elif operation == "multiply":
                result *= value
            else:
                result /= value
    return result


def location(answer: str, start: int, end: int) -> dict[str, int]:
    """Half-open Unicode-codepoint offsets; lines and columns are one-based."""
    return {
        "start": start,
        "end": end,
        "line": answer.count("\n", 0, start) + 1,
        "column": start - answer.rfind("\n", 0, start),
    }


def numeric_hits(answer: str, expected: Decimal) -> dict[str, Any]:
    hits: list[dict[str, int]] = []
    total = 0
    for match in NUMBER.finditer(answer):
        text = match.group().replace(",", "")
        if len(text) > 80:
            continue
        if Decimal(text) == expected:
            total += 1
            if len(hits) < MAX_HITS:
                hits.append(location(answer, match.start(), match.end()))
    return {
        "numeric_value_seen": total > 0,
        "occurrences": hits,
        "occurrence_count": total,
        "locations_truncated": total > MAX_HITS,
        "semantic_correctness": None,
    }


def fact_specs(case: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    assist = case.get("scoring_assist", {})
    require(isinstance(assist, dict), "invalid_scoring_assist")
    facts = assist.get("numeric_facts", case.get("expected_numeric_facts", []))
    if isinstance(facts, dict):
        facts = [{"id": key, "expected_value": value} for key, value in facts.items()]
    if not isinstance(facts, list) or not all(isinstance(item, dict) for item in facts):
        return [], False
    require(len(facts) <= MAX_CHECKS, "too_many_numeric_facts")
    return facts, True


def numeric_check(fact: dict[str, Any], answer: str) -> dict[str, Any]:
    fact_id = identifier(fact.get("id"))
    check: dict[str, Any] = {
        "fact_id": fact_id,
        "kind": "numeric_location_hint",
        "human_decision": None,
    }
    if fact.get("expected_value") is None:
        check.update(
            expected_value=None,
            reference_calculation={
                "state": "unscorable",
                "reason": "authored_value_unknown_not_zero",
            },
            numeric_value_seen=None,
            semantic_correctness=None,
        )
        return check
    try:
        expected = decimal_value(fact.get("expected_value"))
        check["expected_value"] = str(expected)
        check.update(numeric_hits(answer, expected))
        calculation = fact.get("calculation")
        if calculation is None:
            check["reference_calculation"] = {"state": "unavailable"}
        else:
            require(isinstance(calculation, dict), "invalid_calculation")
            calculated = calculate(calculation)
            check["reference_calculation"] = {
                "state": "pass" if calculated == expected else "fail",
                "calculated_value": str(calculated),
                "precision_digits": 80,
                "scope": "authored reference key only; not answer correctness",
            }
    except (InputError, DecimalException) as exc:
        check["reference_calculation"] = {
            "state": "unscorable",
            "reason": str(exc) if isinstance(exc, InputError) else "decimal_arithmetic_unavailable",
        }
    return check


def literal_hits(answer: str, literal: str) -> dict[str, Any]:
    hits: list[dict[str, int]] = []
    count = 0
    offset = 0
    while (found := answer.find(literal, offset)) != -1:
        count += 1
        if len(hits) < MAX_HITS:
            hits.append(location(answer, found, found + len(literal)))
        offset = found + len(literal)
    return {
        "literal": literal,
        "occurrence_count": count,
        "occurrences": hits,
        "locations_truncated": count > MAX_HITS,
    }


def artifact_checks(case: dict[str, Any], answer: str) -> list[dict[str, Any]]:
    specs = case.get("scoring_assist", {}).get("required_artifacts", [])
    require(isinstance(specs, list) and len(specs) <= MAX_CHECKS, "invalid_artifact_specs")
    checks: list[dict[str, Any]] = []
    for spec in specs:
        require(isinstance(spec, dict), "invalid_artifact_spec")
        artifact_id = identifier(spec.get("id"))
        markers = spec.get("literal_markers", [])
        require(isinstance(markers, list) and len(markers) <= 16, "invalid_artifact_markers")
        require(
            all(isinstance(m, str) and 0 < len(m) <= 200 for m in markers),
            "invalid_artifact_literal",
        )
        checks.append(
            {
                "artifact_id": artifact_id,
                "kind": "literal_location_hint",
                "marker_observations": [literal_hits(answer, m) for m in markers],
                "deliverable_complete": None,
                "human_decision": None,
            }
        )
    return checks


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def freeze_assessment(bundle: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    freeze = bundle.get("freeze", {})
    require(isinstance(freeze, dict), "invalid_freeze")
    frozen_at = timestamp(freeze.get("frozen_at"))
    starts = [timestamp(row.get("started_at")) for row in results.values()]
    reasons: list[str] = []
    if freeze.get("state") != "FROZEN":
        reasons.append("protocol_not_declared_frozen")
    if not isinstance(freeze.get("source_sha"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", freeze["source_sha"]
    ):
        reasons.append("exact_source_sha_unavailable")
    if freeze.get("quota") != ACTOR_BUDGET:
        reasons.append("actor_quota_not_54")
    if not isinstance(freeze.get("input_files"), list) or not freeze.get("input_files"):
        reasons.append("frozen_input_inventory_unavailable")
    if frozen_at is None:
        reasons.append("freeze_timestamp_unavailable")
    elif any(start is not None and start <= frozen_at for start in starts):
        reasons.append("result_started_before_or_at_freeze")
    if any(
        start is None and row.get("status") in ATTEMPT_STATUSES
        for start, row in zip(starts, results.values(), strict=True)
    ):
        reasons.append("attempt_start_timestamp_unavailable")
    return {
        "state": "declared_pre_result_freeze" if not reasons else "unverified",
        "reasons": reasons,
        "source_sha": freeze.get("source_sha")
        if isinstance(freeze.get("source_sha"), str)
        and re.fullmatch(r"[0-9a-f]{40}", freeze["source_sha"])
        else None,
        "source_matches_assignment_base": freeze.get("source_sha") == BASE_SHA,
        "input_hashes_verified": False,
        "limitation": "Declaration/timing checks only; S041/S049 own exact hash audit.",
    }


def critical_form(case: dict[str, Any], rubric: dict[str, Any]) -> list[dict[str, Any]]:
    labels = case.get("critical_errors", [])
    require(isinstance(labels, list) and len(labels) <= MAX_CHECKS, "invalid_critical_labels")
    require(
        all(isinstance(label, str) and 0 < len(label) <= 300 for label in labels),
        "invalid_critical_label",
    )
    common = rubric.get("common_critical_errors", [])
    require(
        isinstance(common, list) and len(common) <= MAX_CHECKS, "invalid_common_critical_errors"
    )
    for item in common:
        require(isinstance(item, dict), "invalid_common_critical_error")
    combined = [*labels, *(identifier(item.get("id")) for item in common)]
    return [
        {"label": label, "present": None, "answer_evidence_locations": [], "public_rationale": None}
        for label in dict.fromkeys(combined)
    ]


def criterion_form(case: dict[str, Any], pointer: str) -> list[dict[str, Any]]:
    outcome = case.get("required_outcome")
    rows = outcome if isinstance(outcome, list) else [outcome]
    require(0 < len(rows) <= MAX_CHECKS, "invalid_required_outcomes")
    checks = [
        {
            "criterion_id": f"outcome-{index + 1}",
            "finding_outcome": None,
            "frozen_task_key_ref": pointer
            + "/required_outcome"
            + (f"/{index}" if isinstance(outcome, list) else ""),
            "answer_evidence_locations": [],
            "absence": None,
            "public_ground": None,
        }
        for index, _ in enumerate(rows)
    ]
    facts = case.get("required_facts", [])
    require(isinstance(facts, list) and len(facts) <= MAX_CHECKS, "invalid_required_fact_list")
    for index, fact in enumerate(facts):
        require(isinstance(fact, dict), "invalid_required_fact")
        checks.append(
            {
                "criterion_id": identifier(fact.get("fact_id")),
                "finding_outcome": None,
                "frozen_task_key_ref": f"{pointer}/required_facts/{index}",
                "answer_evidence_locations": [],
                "absence": None,
                "public_ground": None,
            }
        )
    return checks


def manual_form(case: dict[str, Any], pointer: str, rubric: dict[str, Any]) -> dict[str, Any]:
    return {
        "human_decision": None,
        "allowed_decisions": ["pass", "fail", "unscorable"],
        "judge_provenance": {
            "kind": None,
            "reviewer_reference": None,
            "independent_evaluator": None,
            "independence_reason": "unavailable_until_actual_review",
        },
        "required_outcome_reference": pointer + "/required_outcome",
        "required_deliverables_complete": None,
        "material_facts_supported": None,
        "binding_constraints_met": None,
        "correction_burden": None,
        "critical_error_assessment": "not_reviewed",
        "critical_errors": critical_form(case, rubric),
        "criterion_reviews": criterion_form(case, pointer),
        "public_rationale": None,
        "dimension_findings": {
            "task_completion": None,
            "factuality": None,
            "constraint_compliance": None,
            "critical_errors": None,
            "correction_burden": None,
        },
        "answer_evidence_locations": [],
        "task_key_references": [],
        "reviewed_at": None,
        "pass_rule": "complete deliverables AND supported facts AND constraints met "
        "AND every predeclared critical error assessed absent",
        "instructions": "Use frozen criterion IDs/key references and public answer spans. "
        "Keep uncertainty, first ratings and dissent; never write hidden reasoning. "
        "Only COMPLETED eligible public answers receive semantic findings. "
        "Execution-unscorable classifications are separately counted.",
    }


def quality_draft(status: str, answer: Any, freeze: dict[str, Any]) -> dict[str, Any]:
    if status != "COMPLETED":
        return {
            "assessment_state": "not_assessed_execution_incomplete",
            "draft_verdict": "unscorable",
            "score_basis": "execution_unavailable",
            "reason": "execution_not_final"
            if status == "STARTED"
            else "execution_output_unavailable",
        }
    if not isinstance(answer, str):
        return {
            "assessment_state": "answer_unavailable",
            "draft_verdict": "unscorable",
            "score_basis": "pending",
            "reason": "public_answer_not_captured",
        }
    if freeze["state"] != "declared_pre_result_freeze":
        return {
            "assessment_state": "freeze_unverified",
            "draft_verdict": "unscorable",
            "score_basis": "pending",
            "reason": "protocol_provenance_needs_review",
        }
    if not answer.strip():
        return {
            "assessment_state": "observable_empty_answer",
            "draft_verdict": "fail",
            "score_basis": "public_final_answer",
            "reason": "completed_empty_answer_cannot_complete_required_deliverable",
        }
    return {
        "assessment_state": "awaiting_human_semantic_review",
        "draft_verdict": "unscorable",
        "score_basis": "pending",
        "reason": "numeric_or_literal_hints_are_insufficient",
    }


def delivery_observations(result: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in ("entry_emitted", "canonical_full_read", "tool_query_observed"):
        value = result.get(key)
        fields[key] = value if type(value) is bool else None
    fields["application_evidence"] = "unverified"
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True)
    matched = (
        bool(result)
        and review.get("result_sha256") == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    )
    mode = review.get("delivery_mode") if matched else None
    modes = {
        "none",
        "general-check",
        "native-installed",
        "manual-canonical",
        "manual_canonical_injection",
        "unknown",
        "unavailable",
    }
    fields["delivery_mode_declared"] = mode if isinstance(mode, str) and mode in modes else None
    fields["intake_review_hash_matched"] = matched
    fields["delivery_observation_provenance"] = "curator assertion; no native receipt"
    fields["manual_canonical_injection_is_native"] = False
    fields["installation_profile"] = None
    fields["backend_model_observed"] = None
    fields["backend_model_reason"] = "not_inferred_from_requested_model_or_settings"
    fields["quality_inferred_from_delivery"] = False
    return fields


def attempt_state(status: str, cell: dict[str, Any], result: dict[str, Any]) -> bool | None:
    if (
        status in ATTEMPT_STATUSES
        or cell.get("status") in ATTEMPT_STATUSES
        or timestamp(result.get("started_at")) is not None
    ):
        return True
    return None if status == "BLOCKED" else False


def assess_cell(
    cell: dict[str, Any],
    case: dict[str, Any],
    result: dict[str, Any],
    freeze: dict[str, Any],
    pointer: str,
    rubric: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    status = result.get("status", cell.get("status", "NOT_RUN"))
    require(status in STATUSES, "invalid_execution_status")
    answer = result.get("public_final_answer")
    require(answer is None or isinstance(answer, str), "invalid_public_answer")
    require(answer is None or len(answer) <= MAX_ANSWER_CHARS, "public_answer_too_large")
    usable = answer if isinstance(answer, str) and status == "COMPLETED" else ""
    facts, facts_supported = fact_specs(case)
    return {
        "cell_id": cell["cell_id"],
        "case_id": case["case_id"],
        "family": case["family"],
        "locale": case["locale"],
        "arm": cell["arm"],
        "repeat": cell["repeat"],
        "human_decision": None,
        "execution": {
            "status": status,
            "result_record_present": bool(result),
            "attempted": attempt_state(status, cell, result),
            "attempt_unknown_reason": "BLOCKED_without_prior_start_evidence"
            if attempt_state(status, cell, result) is None
            else None,
            "quality_verdict": None,
        },
        "answer_reference": {
            "field": "public_final_answer",
            "sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest()
            if isinstance(answer, str)
            else None,
            "unicode_codepoints": len(answer) if isinstance(answer, str) else None,
            "offset_convention": "half-open Unicode codepoints; line/column 1-based",
        },
        "quality": quality_draft(status, answer, freeze),
        "delivery_observations": delivery_observations(result, review),
        "automatic_hints": {
            "available": isinstance(answer, str) and status == "COMPLETED",
            "numeric_contract_supported": facts_supported,
            "numeric_checks": [numeric_check(fact, usable) for fact in facts],
            "artifact_checks": artifact_checks(case, usable),
            "semantic_pass": None,
        },
        "human_form": manual_form(case, pointer, rubric),
    }


def validate_design(cases: dict[str, Any], cells: dict[str, Any]) -> None:
    for case in cases.values():
        require(
            case.get("family") in FAMILIES and case.get("locale") in {"en", "ko"},
            "invalid_case_stratum",
        )
        require(case["case_id"] == f"{case['family']}-{case['locale']}", "invalid_case_id")
        require("required_outcome" in case, "required_outcome_missing")
    combinations: set[tuple[str, str, int]] = set()
    for cell in cells.values():
        require(cell.get("case_id") in cases and cell.get("arm") in ARMS, "invalid_cell_assignment")
        require(type(cell.get("repeat")) is int and cell["repeat"] in {1, 2, 3}, "invalid_repeat")
        require(
            cell["cell_id"] == f"{cell['case_id']}-{cell['arm']}-r{cell['repeat']}",
            "cell_id_assignment_mismatch",
        )
        combination = (cell["case_id"], cell["arm"], cell["repeat"])
        require(combination not in combinations, "duplicate_design_cell_no_retry_allowed")
        combinations.add(combination)


def build(bundle: dict[str, Any], digests: dict[str, str]) -> dict[str, Any]:
    cases = index_records(bundle.get("cases"), "case_id", 6)
    cells = index_records(bundle.get("cells"), "cell_id", ACTOR_BUDGET)
    results = index_records(bundle.get("results", []), "cell_id", ACTOR_BUDGET)
    reviews = index_records(bundle.get("intake_reviews", []), "cell_id", ACTOR_BUDGET)
    require(set(results) <= set(cells), "unassigned_result_no_retry_allowed")
    require(set(reviews) <= set(results), "intake_review_without_result")
    require(
        all(
            isinstance(row.get("status"), str) and row["status"] in STATUSES
            for row in results.values()
        ),
        "result_status_required",
    )
    validate_design(cases, cells)
    rubric = bundle.get("rubric", {})
    require(isinstance(rubric, dict), "invalid_rubric")
    pointers = {key: f"/cases/{index}" for index, key in enumerate(cases)}
    freeze = freeze_assessment(bundle, results)
    assessments = [
        assess_cell(
            cell,
            cases[cell["case_id"]],
            results.get(key, {}),
            freeze,
            pointers[cell["case_id"]],
            rubric,
            reviews.get(key, {}),
        )
        for key, cell in cells.items()
    ]
    statuses = Counter(row["execution"]["status"] for row in assessments)
    drafts = Counter(
        row["quality"]["draft_verdict"]
        for row in assessments
        if row["execution"]["status"] == "COMPLETED"
    )
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "tool_role": "deterministic_assistance_only",
        "artifact_name": "rubric-assist.json",
        "blind_judge_packet": False,
        "retention_contract": "public-synthetic-only-v1",
        "input_digests": digests,
        "assignment_base_sha": BASE_SHA,
        "freeze_assessment": freeze,
        "protocol_rubric": {
            "reference": "frozen common rubric plus case answer keys",
            "threshold_changes_after_results_allowed": False,
            "exact_hash_audit": "S041/S049; not performed by this tool",
        },
        "summary": {
            "planned_actor_budget": ACTOR_BUDGET,
            "assigned_cells": len(cells),
            "assignment_complete": len(cells) == ACTOR_BUDGET,
            "unassigned_budget_cells": ACTOR_BUDGET - len(cells),
            "result_records": len(results),
            "attempted_cells": sum(row["execution"]["attempted"] is True for row in assessments),
            "attempted_cells_unknown": sum(
                row["execution"]["attempted"] is None for row in assessments
            ),
            "execution_status_counts": {key: statuses[key] for key in STATUSES},
            "completed_answer_quality_draft_counts": {
                key: drafts[key] for key in ("pass", "fail", "unscorable")
            },
            "execution_unscorable_drafts": sum(
                row["quality"]["score_basis"] == "execution_unavailable" for row in assessments
            ),
            "semantic_ratings_pending": sum(
                row["quality"]["score_basis"] == "pending" for row in assessments
            ),
            "human_decisions_pending": len(assessments),
            "human_observed_successes": None,
            "success_rate": None,
            "denominator_policy": "all assigned attempted cells, including FAILED/TIMEOUT; "
            "NOT_RUN/BLOCKED and absent assignments reported separately",
        },
        "warnings": WARNINGS,
        "assessments": assessments,
    }


def atomic_write(path: Path, output: dict[str, Any]) -> None:
    require(not path.exists(), "output_exists_refusing_to_replace_first_ratings")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".rubric-assist-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Same-filesystem hard link atomically publishes without clobbering a
        # concurrent first result. Unsupported filesystems fail explicitly.
        os.link(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Explicit public synthetic bundle JSON"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="New rubric-assist JSON file; never overwritten"
    )
    args = parser.parse_args()
    try:
        require(args.input.resolve() != args.output.resolve(), "input_output_paths_must_differ")
        bundle, digests = read_bundle(args.input)
        atomic_write(args.output, build(bundle, digests))
    except InputError as exc:
        print(f"swarm_scoring_assist: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        print("swarm_scoring_assist: input_or_output_unavailable", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
