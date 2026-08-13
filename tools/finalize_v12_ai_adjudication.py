#!/usr/bin/env python3
"""Build the maintainer-authorized provisional v1.2 adjudication artifacts.

This is deliberately a synthesis tool, not another blind reviewer.  It keeps
both complete ChatGPT Pro reviews, the recoverable Claude subset, every
substantive disagreement, and the historical labels.  The resulting decision
set is development-only under ``ADJUDICATION_AI_AMENDMENT.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from compare_v12_adjudication_reviews import (
    ComparisonValidationError,
    validate_comparison_artifact,
)
from json_schema_2020 import check_schema, validate
from v12_adjudication_contract import EVALUATION_ID, EVIDENCE_GRADE

ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "evals/v1.2"
BUILD_ROOT = ROOT / "build/adjudication/v1.2"
PACKET_DIR = BUILD_ROOT / "blind-packets"

PRIMARY_PATH = BUILD_ROOT / "askpro-blind-adjudication.json"
SECONDARY_PATH = BUILD_ROOT / "askpro-second-blind-adjudication.json"
CLAUDE_PATH = BUILD_ROOT / "claude-opus5-blind-review.json"
COMPARISON_PATH = BUILD_ROOT / "reviewer-comparison.json"
COMPARISON_SCHEMA_PATH = EVAL_ROOT / "schemas/adjudication-review-comparison.schema.json"

GUIDE_PATH = EVAL_ROOT / "ADJUDICATION_GUIDE.md"
AMENDMENT_PATH = EVAL_ROOT / "ADJUDICATION_AI_AMENDMENT.md"
FREEZE_PATH = EVAL_ROOT / "adjudication-freeze-v1.0.0.json"
REPORT_PATH = ROOT / "docs/v1.2-adjudication-report.md"
RELEASE_NOTES_PATH = ROOT / ".github/release-notes/v1.2.1.md"
PRIMARY_ID = "chatgpt-pro-blind-review-1"
SECONDARY_ID = "chatgpt-pro-blind-review-2"
RESOLUTION_ID = "maintainer-authorized-codex-synthesis"
CLAUDE_ID = "claude-opus-5-high-partial-review"

BEHAVIOR_ALIASES = {
    "hold": "hold_no_intervention",
    "clarifier": "route_clarifier",
    "owner-then-hold": "route_owner_then_hold",
    "safe alternative": "route_safe_alternative",
    "bounded analysis": "bounded_analysis",
}
DECISION_FIELDS = (
    "status",
    "intervention_policy",
    "allowed_behaviors",
    "leading_method",
    "acceptable_leading_methods",
    "acceptable_inclusion_methods",
    "prohibited_methods",
    "leading_metric_eligible",
    "inclusion_metric_eligible",
    "policy_metric_eligible",
)
LIST_FIELDS = {
    "allowed_behaviors",
    "acceptable_leading_methods",
    "acceptable_inclusion_methods",
    "prohibited_methods",
}
HOLD_NORMALIZATION_PAIRS = {
    "reflective-equilibrium-insufficiency-01",
    "triangulation-insufficiency-01",
}
UNCERTAINTY_FIELDS = frozenset({"issue", "pair_id", "residual", "resolution"})
SYNTHESIS_OVERRIDE_TYPES = frozenset(
    {"claude_partial_selection", "schema_consistency_normalization"}
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("decision", record)
    result: dict[str, Any] = {}
    for field in DECISION_FIELDS:
        value = deepcopy(source[field])
        if field == "allowed_behaviors":
            value = [BEHAVIOR_ALIASES.get(item, item) for item in value]
        if field in LIST_FIELDS:
            value = sorted(set(value))
        result[field] = value
    return result


def extract_claude_records(wrapper: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Recover only syntactically complete top-level decision objects."""
    text = wrapper.get("result", "")
    decoder = json.JSONDecoder()
    recovered: dict[str, dict[str, Any]] = {}
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(value, dict)
            and value.get("schema") == "opensocrates.eval-adjudication-decision/1.0.0"
            and isinstance(value.get("pair_id"), str)
        ):
            recovered[value["pair_id"]] = value
    return recovered


def final_decision(
    pair_id: str,
    secondary: dict[str, Any],
    claude: dict[str, dict[str, Any]],
    classification: str,
) -> tuple[dict[str, Any], str, str, dict[str, str] | None]:
    """Return decision, selected source, explanation, and any typed override."""
    decision = normalize(secondary)
    selected = "secondary"
    override: dict[str, str] | None = None
    explanation = (
        "The secondary review applied the frozen method-specific Use, Do-not-use, "
        "and Stop conditions case by case. The primary review instead applied one "
        "blanket optional-intervention template with all five behaviors to almost "
        "every insufficiency pair, so its case-specific route fields were retained "
        "as dissent rather than selected for the provisional development policy."
    )

    if pair_id == "decision-tree-analysis-mechanical-1":
        decision = normalize(claude[pair_id])
        selected = "claude_partial"
        explanation = (
            "The two complete reviews disagreed between rewrite and an optional "
            "mechanical/deduction route. Claude independently selected the same "
            "multi-valid boundary as the secondary review but represented the two "
            "behaviors canonically as no-intervention hold or bounded deterministic "
            "rule application; that representation is selected."
        )
        override = {"type": "claude_partial_selection", "rationale": explanation}
    elif pair_id in HOLD_NORMALIZATION_PAIRS:
        decision["allowed_behaviors"] = ["hold_no_intervention"]
        selected = "secondary_with_schema_consistency_normalization"
        explanation = (
            "The secondary review prohibited method intervention but encoded the "
            "direct limitation as bounded_analysis. Under protocol 1.2, bounded "
            "analysis is a routing behavior and is inconsistent with prohibited "
            "intervention. The supported direct limitation remains in the rationale, "
            "while selector behavior is normalized to hold_no_intervention."
        )
        override = {
            "type": "schema_consistency_normalization",
            "rationale": explanation,
        }
    elif pair_id == "design-thinking-positive-03":
        decision["acceptable_inclusion_methods"] = []
        selected = "secondary_with_schema_consistency_normalization"
        explanation = (
            "Both complete reviews accept design thinking and jobs-to-be-done as "
            "alternative leaders. No stable non-leading inclusion set is established, "
            "so the inclusion list is empty and the inclusion metric remains ineligible."
        )
        override = {
            "type": "schema_consistency_normalization",
            "rationale": explanation,
        }
    elif classification in {"exact_agreement", "compatible_agreement"}:
        explanation = (
            "Both complete reviews agree on intervention policy, leading-route "
            "semantics, and metric eligibility. The secondary review's narrower "
            "case-specific behavior and method sets are selected."
        )
    return decision, selected, explanation, override


def git_state(root: Path, *, allow_dirty: bool) -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    if status and not allow_dirty:
        raise SystemExit(
            "refusing to finalize from a dirty source tree; commit/stash unrelated work "
            "or pass --allow-dirty-source explicitly"
        )
    return {
        "revision": revision,
        "dirty": bool(status),
        "note": (
            "Dirty source explicitly authorized; reproducibility is limited."
            if status
            else "Source tree was clean before atomic output publication."
        ),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
        ),
        encoding="utf-8",
    )


def _is_rfc3339(value: Any) -> bool:
    return isinstance(value, str) and not validate(
        value,
        {"type": "string", "format": "date-time"},
    )


def _artifact_timestamp(
    artifact: dict[str, Any],
    records: dict[str, dict[str, Any]],
    field: str,
    override: str | None,
    label: str,
) -> str:
    candidates: list[Any] = [override]
    for key in ("locked_at", "completed_at", "created_at"):
        candidates.append(artifact.get(key))
    record_values = {
        record.get("review", {}).get(field)
        for record in records.values()
        if record.get("review", {}).get(field) is not None
    }
    if len(record_values) == 1:
        candidates.extend(record_values)
    for candidate in candidates:
        if _is_rfc3339(candidate):
            return str(candidate)
    raise SystemExit(
        f"{label} lock timestamp is absent or ambiguous in source metadata; "
        f"pass --{label}-locked-at with an RFC 3339 value"
    )


def _record_timestamp(record: dict[str, Any], field: str, fallback: str) -> str:
    value = record.get("review", {}).get(field)
    return str(value) if _is_rfc3339(value) else fallback


def _semantic_review_schema(decision_schema: dict[str, Any]) -> dict[str, Any]:
    issues = check_schema(decision_schema)
    if issues:
        rendered = "; ".join(str(issue) for issue in issues)
        raise SystemExit(f"invalid decision schema: {rendered}")
    semantic_schema = decision_schema.get("properties", {}).get("semantic_review")
    if not isinstance(semantic_schema, dict):
        raise SystemExit("decision schema must declare an object semantic_review property")
    return semantic_schema


def _validated_uncertainty(
    value: Any,
    *,
    label: str,
    expected_pair_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit(f"{label}: secondary uncertainty must be an object")
    fields = set(value)
    if fields != UNCERTAINTY_FIELDS:
        missing = sorted(UNCERTAINTY_FIELDS - fields)
        extra = sorted(fields - UNCERTAINTY_FIELDS)
        raise SystemExit(
            f"{label}: malformed secondary uncertainty fields; missing={missing}, extra={extra}"
        )
    pair_id = value["pair_id"]
    if not isinstance(pair_id, str) or not pair_id:
        raise SystemExit(f"{label}: secondary uncertainty pair_id must be a non-empty string")
    if expected_pair_id is not None and pair_id != expected_pair_id:
        raise SystemExit(
            f"{label}: secondary uncertainty pair_id {pair_id!r} does not match "
            f"{expected_pair_id!r}"
        )
    if not isinstance(value["residual"], bool):
        raise SystemExit(f"{label}: secondary uncertainty residual must be boolean")
    for field in ("issue", "resolution"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise SystemExit(f"{label}: secondary uncertainty {field} must be a non-empty string")
    return value


def _uncertainty_index(values: Any, expected_pairs: set[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list):
        raise SystemExit("secondary uncertainties must be an array")
    indexed: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(values):
        item = _validated_uncertainty(raw, label=f"secondary uncertainties[{index}]")
        pair_id = item["pair_id"]
        if pair_id not in expected_pairs:
            raise SystemExit(f"secondary uncertainty names unknown pair_id {pair_id!r}")
        if pair_id in indexed:
            raise SystemExit(f"duplicate secondary uncertainty for {pair_id!r}")
        indexed[pair_id] = item
    return indexed


def _final_semantic_review(
    pair_id: str,
    primary_record: dict[str, Any],
    final_decision: dict[str, Any],
    semantic_schema: dict[str, Any],
    uncertainty: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate and preserve the primary semantic judgment without inventing truth."""

    semantic_review = primary_record.get("semantic_review")
    issues = validate(semantic_review, semantic_schema)
    if issues:
        rendered = "; ".join(str(issue) for issue in issues)
        raise SystemExit(f"{pair_id}: invalid primary semantic_review: {rendered}")
    if not isinstance(semantic_review, dict):  # narrowed by validate; protects type checkers
        raise AssertionError("validated semantic_review must be an object")

    equivalent = semantic_review["en_ko_equivalent"]
    mismatch = semantic_review["translation_mismatch"]
    if equivalent == mismatch:
        raise SystemExit(
            f"{pair_id}: primary semantic_review must record exactly one of "
            "en_ko_equivalent or translation_mismatch"
        )
    if mismatch and final_decision.get("policy_metric_eligible") is not False:
        raise SystemExit(
            f"{pair_id}: translation_mismatch=true conflicts with final "
            "policy_metric_eligible; finalization refused"
        )

    result = deepcopy(semantic_review)
    if uncertainty is None:
        return result
    validated_uncertainty = _validated_uncertainty(
        uncertainty,
        label=pair_id,
        expected_pair_id=pair_id,
    )
    if validated_uncertainty["residual"] is False:
        return result
    issue = validated_uncertainty["issue"]
    resolution = validated_uncertainty["resolution"]
    note = f"Secondary-review residual uncertainty: {issue.strip()} {resolution.strip()}"
    if note not in result["notes"]:
        result["notes"].append(note)
    return result


def _remove_private_citations(value: Any) -> Any:
    """Drop session-private citation fields while preserving reviewer policy text."""

    if isinstance(value, dict):
        return {
            key: _remove_private_citations(child)
            for key, child in value.items()
            if key != "source_citations"
        }
    if isinstance(value, list):
        return [_remove_private_citations(child) for child in value]
    return value


def _assert_public_text(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    if "filecite" in serialized.casefold() or any(
        "\ue000" <= char <= "\uf8ff" for char in serialized
    ):
        raise SystemExit("refusing to publish private-use/filecite citation tokens")


def _unresolved_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _checked_output_path(path: Path, *, label: str) -> Path:
    """Reject symlinks in an unresolved output path before following any component."""

    absolute = _unresolved_absolute(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise SystemExit(f"cannot inspect {label} component {current}: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise SystemExit(f"refusing symlink {label} component: {current}")
    return absolute


def _publish_directory(staged: Path, output: Path, *, allow_overwrite: bool) -> None:
    output = _checked_output_path(output, label="finalization output")
    resolved_output = output.resolve(strict=False)
    if resolved_output in {Path("/"), ROOT.resolve(), ROOT.parent.resolve()}:
        raise SystemExit(f"unsafe finalization output directory: {output}")
    if output.exists() and not output.is_dir():
        raise SystemExit(f"finalization output exists and is not a directory: {output}")
    if output.exists() and not allow_overwrite:
        raise SystemExit(
            f"versioned finalization output already exists: {output}\n"
            "choose a new --output-dir or pass --allow-overwrite-versioned-lock explicitly"
        )
    if not output.exists():
        os.replace(staged, output)
        return
    backup = output.with_name(f".{output.name}.previous-{os.getpid()}")
    if backup.exists():
        raise SystemExit(f"refusing overwrite because swap path exists: {backup}")
    os.replace(output, backup)
    try:
        os.replace(staged, output)
    except OSError:
        os.replace(backup, output)
        raise
    shutil.rmtree(backup)


def main(argv: list[str] | None = None) -> int:  # noqa: C901
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, default=PRIMARY_PATH)
    parser.add_argument("--secondary", type=Path, default=SECONDARY_PATH)
    parser.add_argument("--claude-partial", type=Path, default=CLAUDE_PATH)
    parser.add_argument("--comparison", type=Path, default=COMPARISON_PATH)
    parser.add_argument("--comparison-schema", type=Path, default=COMPARISON_SCHEMA_PATH)
    parser.add_argument("--packet-dir", type=Path, default=PACKET_DIR)
    parser.add_argument("--guide", type=Path, default=GUIDE_PATH)
    parser.add_argument("--amendment", type=Path, default=AMENDMENT_PATH)
    parser.add_argument("--freeze", type=Path, default=FREEZE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--release-notes", type=Path, default=RELEASE_NOTES_PATH)
    parser.add_argument(
        "--decision-schema",
        type=Path,
        default=EVAL_ROOT / "schemas/adjudication-decision.schema.json",
    )
    parser.add_argument(
        "--disagreement-schema",
        type=Path,
        default=EVAL_ROOT / "schemas/adjudication-disagreement.schema.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new directory published atomically with all versioned outputs",
    )
    parser.add_argument("--primary-locked-at", help="RFC 3339 fallback from source metadata")
    parser.add_argument("--secondary-locked-at", help="RFC 3339 fallback from source metadata")
    parser.add_argument("--decision-created-at", help="RFC 3339 source lock timestamp")
    parser.add_argument(
        "--allow-dirty-source",
        action="store_true",
        help="explicitly authorize a dirty source snapshot",
    )
    parser.add_argument(
        "--allow-overwrite-versioned-lock",
        action="store_true",
        help="explicitly authorize atomic replacement of an existing output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build and hash the staged set without publishing it",
    )
    args = parser.parse_args(argv)

    input_paths = {
        "primary review": args.primary,
        "secondary review": args.secondary,
        "Claude partial review": args.claude_partial,
        "review comparison": args.comparison,
        "review comparison schema": args.comparison_schema,
        "packet manifest": args.packet_dir / "packet-manifest.json",
        "annotation guide": args.guide,
        "AI amendment": args.amendment,
        "freeze record": args.freeze,
        "public report": args.report,
        "release notes": args.release_notes,
        "decision schema": args.decision_schema,
        "disagreement schema": args.disagreement_schema,
    }
    missing = [f"{label}: {path}" for label, path in input_paths.items() if not path.is_file()]
    if missing:
        raise SystemExit(
            "required maintainer input is absent:\n  - "
            + "\n  - ".join(missing)
            + "\nNo review, packet, or raw artifact will be invented."
        )

    source_git = git_state(ROOT, allow_dirty=args.allow_dirty_source)
    primary_artifact = read_json(args.primary)
    secondary_artifact = read_json(args.secondary)
    comparison_artifact = read_json(args.comparison)
    packet_manifest = read_json(args.packet_dir / "packet-manifest.json")
    claude_wrapper = read_json(args.claude_partial)
    semantic_schema = _semantic_review_schema(read_json(args.decision_schema))
    comparison_schema = read_json(args.comparison_schema)
    claude = extract_claude_records(claude_wrapper)

    primary = {record["pair_id"]: record for record in primary_artifact["decisions"]}
    secondary = {record["pair_id"]: record for record in secondary_artifact["decisions"]}
    expected = set(packet_manifest["pair_ids"])
    if set(primary) != expected or set(secondary) != expected:
        raise SystemExit("both complete reviews must cover exactly the frozen 51 pairs")
    try:
        comparison_rows = validate_comparison_artifact(
            comparison_artifact,
            comparison_schema,
            primary_artifact,
            secondary_artifact,
            packet_manifest,
            primary_sha256=sha256(args.primary),
            secondary_sha256=sha256(args.secondary),
        )
    except ComparisonValidationError as exc:
        raise SystemExit(f"invalid review comparison: {exc}") from exc
    if "decision-tree-analysis-mechanical-1" not in claude:
        raise SystemExit("mechanical boundary resolution requires the recovered Claude record")

    primary_lock = _artifact_timestamp(
        primary_artifact,
        primary,
        "primary_decision_locked_at",
        args.primary_locked_at,
        "primary",
    )
    secondary_lock = _artifact_timestamp(
        secondary_artifact,
        secondary,
        "second_decision_locked_at",
        args.secondary_locked_at,
        "secondary",
    )
    created_at_fallback = args.decision_created_at or secondary_lock
    if not _is_rfc3339(created_at_fallback):
        raise SystemExit("--decision-created-at must be an RFC 3339 date-time")
    uncertainty_notes = _uncertainty_index(
        secondary_artifact.get("uncertainties", []),
        expected,
    )

    records: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    synthesis_overrides: list[dict[str, str]] = []
    for pair_id in sorted(expected):
        packet = read_json(args.packet_dir / f"{pair_id}.json")
        primary_record = primary[pair_id]
        second_record = secondary[pair_id]
        comparison_row = comparison_rows[pair_id]
        classification = comparison_row["classification"]
        decision, selected_source, resolution_reason, synthesis_override = final_decision(
            pair_id, second_record, claude, classification
        )
        if synthesis_override is not None:
            if set(synthesis_override) != {"type", "rationale"} or (
                synthesis_override["type"] not in SYNTHESIS_OVERRIDE_TYPES
            ):
                raise SystemExit(f"{pair_id}: invalid typed synthesis override")
            synthesis_overrides.append({"pair_id": pair_id, **synthesis_override})
        pair_primary_lock = _record_timestamp(
            primary_record, "primary_decision_locked_at", primary_lock
        )
        pair_secondary_lock = _record_timestamp(
            second_record, "second_decision_locked_at", secondary_lock
        )
        created_at = (
            pair_secondary_lock if args.decision_created_at is None else created_at_fallback
        )
        compatible = classification in {"exact_agreement", "compatible_agreement"}
        agreement = "minor_revision" if compatible else "resolved_disagreement"
        dissent = (
            None
            if compatible
            else (
                "Primary review retained optional intervention and a broader behavior set; "
                "see adjudication-disagreements-v1.0.0.jsonl for both locked decisions."
            )
        )
        rationale = second_record["rationale"]
        if pair_id == "decision-tree-analysis-mechanical-1":
            rationale = claude[pair_id]["rationale"]
        elif pair_id in HOLD_NORMALIZATION_PAIRS:
            rationale += " Selector intervention remains prohibited; the direct limitation does not require a method route."
        elif pair_id == "design-thinking-positive-03":
            rationale += (
                " No stable non-leading inclusion method was established, so the "
                "inclusion set is empty and the inclusion metric remains ineligible."
            )

        semantic_review = _final_semantic_review(
            pair_id,
            primary_record,
            decision,
            semantic_schema,
            uncertainty_notes.get(pair_id),
        )

        record = {
            "schema": "opensocrates.eval-adjudication-decision/1.0.0",
            "protocol_version": "1.2.0",
            "evidence_grade": EVIDENCE_GRADE,
            "pair_id": pair_id,
            "locales": ["en", "ko"],
            "legacy": packet["legacy"],
            "semantic_review": semantic_review,
            "decision": {
                "status": decision["status"],
                "case_kind": packet["legacy"]["kind"],
                "intervention_policy": decision["intervention_policy"],
                "allowed_behaviors": decision["allowed_behaviors"],
                "leading_method": decision["leading_method"],
                "acceptable_leading_methods": decision["acceptable_leading_methods"],
                "acceptable_inclusion_methods": decision["acceptable_inclusion_methods"],
                "prohibited_methods": decision["prohibited_methods"],
                "leading_metric_eligible": decision["leading_metric_eligible"],
                "inclusion_metric_eligible": decision["inclusion_metric_eligible"],
                "policy_metric_eligible": decision["policy_metric_eligible"],
            },
            "decisive_features": packet["authored_decisive_features"],
            "rationale": rationale,
            "review": {
                "author_or_intent_witness": None,
                "primary_adjudicator": PRIMARY_ID,
                "second_reviewer": SECONDARY_ID,
                "primary_decision_locked_at": pair_primary_lock,
                "second_decision_locked_at": pair_secondary_lock,
                "agreement": agreement,
                "resolution_reviewer": None if compatible else RESOLUTION_ID,
                "dissent": dissent,
            },
            "blinding": {
                "model_outputs_seen_by_primary": False,
                "aggregate_results_seen_by_primary": False,
                "model_outputs_seen_by_second": False,
                "aggregate_results_seen_by_second": False,
                "attestation": (
                    "Both complete reviewer conversations used only the frozen blind "
                    "packet bundle. The later synthesis was not blind and is separately "
                    "identified as maintainer-authorized resolution."
                ),
            },
            "provenance": {
                "source_case_sha256": packet["source_case_sha256"],
                "annotation_guide_sha256": packet["annotation_guide_sha256"],
                "blind_packet_sha256": packet_manifest["packet_sha256"][pair_id],
                "decision_created_at": created_at,
            },
        }
        records.append(record)

        if not compatible:
            disagreements.append(
                {
                    "schema": "opensocrates.eval-adjudication-disagreement/1.0.0",
                    "protocol_version": "1.2.0",
                    "evidence_grade": EVIDENCE_GRADE,
                    "pair_id": pair_id,
                    "classification": "substantive_disagreement",
                    "primary_decision": normalize(primary_record),
                    "primary_rationale": primary_record["rationale"],
                    "secondary_decision": normalize(second_record),
                    "secondary_rationale": second_record["rationale"],
                    "claude_partial_decision": (
                        normalize(claude[pair_id]) if pair_id in claude else None
                    ),
                    "resolution": {
                        "status": "resolved_for_provisional_development",
                        "selected_source": selected_source,
                        "final_decision": record["decision"],
                        "rationale": resolution_reason,
                        "resolution_reviewer": RESOLUTION_ID,
                        "resolved_at": created_at,
                    },
                }
            )

    policy = {
        "schema": "opensocrates.eval-adjudication-policy/1.0.0",
        "protocol_version": "1.2.0",
        "evaluation_id": EVALUATION_ID,
        "evidence_grade": EVIDENCE_GRADE,
        "guide_version": "1.0.0",
        "status": "maintainer_authorized_ai_assisted_provisional_development_policy",
        "locked_at": created_at_fallback,
        "answers": {
            "1_non_intervention_default": "case_by_case_rule",
            "2_clarification_is_intervention": "yes",
            "3_clarifier_policy_success": "allowed_but_not_required_unless_owner_is_contraindicated_or_target_missing",
            "4_owner_route_then_hold": "allowed_route_identification_and_required_when_owner_is_unique_and_not_contraindicated",
            "5_clarifier_and_owner_order": "owner_leads_unless_clarification_itself_is_the_main_repair_route",
            "6_nonleading_clarifier": "inclusion_only_success",
            "7_ambiguity_vs_missing_evidence": "two_rules_defined_below",
            "8_contraindication_rule": (
                "A matching Do-not-use condition prohibits the method. A matching Stop "
                "condition with an identifiable task owner permits owner-route-then-hold."
            ),
            "9_multi_behavior_leading_metric": "excluded_from_leading_metric_unless_one_unique_owner_is_fixed",
            "10_policy_metric_exclusions": (
                "Exclude undetermined, unresolved, rewrite, invalid, material translation "
                "mismatch, or cases whose allowed behavior set cannot be represented."
            ),
        },
        "reviewer_policies": {
            "primary": _remove_private_citations(primary_artifact["policy"]),
            "secondary": _remove_private_citations(secondary_artifact["policy"]),
        },
        "resolution_note": (
            "The secondary policy is adopted as the case-specific base because it "
            "distinguishes explicit contraindications from method stop conditions. "
            "The primary policy is preserved as dissent. Two behavior normalizations "
            "and one Claude-supported mechanical-boundary resolution are recorded in "
            "the disagreement ledger; the compatible design-thinking boundary also "
            "clears an unscored inclusion list."
        ),
        "publication_boundary": (
            "AI-assisted provisional development adjudication; not confirmation-grade "
            "human gold, not held-out, and not answer-quality evidence."
        ),
    }

    _assert_public_text(policy)
    _assert_public_text(records)
    _assert_public_text(disagreements)

    checked_output = _checked_output_path(args.output_dir, label="finalization output")
    output_parent = checked_output.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    checked_output = _checked_output_path(checked_output, label="finalization output")
    staged = Path(tempfile.mkdtemp(prefix=f".{checked_output.name}.staged-", dir=output_parent))
    try:
        policy_path = staged / "adjudication-policy-v1.0.0.json"
        decisions_path = staged / "adjudication-decisions-v1.0.0.jsonl"
        disagreements_path = staged / "adjudication-disagreements-v1.0.0.jsonl"
        manifest_path = staged / "adjudication-manifest-v1.0.0.json"
        write_json(policy_path, policy)
        write_jsonl(decisions_path, records)
        write_jsonl(disagreements_path, disagreements)

        status_counts = Counter(record["decision"]["status"] for record in records)
        agreement_counts = Counter(record["review"]["agreement"] for record in records)
        policy_counts = Counter(record["decision"]["intervention_policy"] for record in records)
        manifest = {
            "schema": "opensocrates.eval-adjudication-manifest/1.0.0",
            "protocol_version": "1.2.0",
            "evaluation_id": EVALUATION_ID,
            "evidence_grade": EVIDENCE_GRADE,
            "status": EVIDENCE_GRADE,
            "pair_count": len(records),
            "locale_instance_count": len(records) * 2,
            "status_counts": dict(sorted(status_counts.items())),
            "agreement_counts": dict(sorted(agreement_counts.items())),
            "intervention_policy_counts": dict(sorted(policy_counts.items())),
            "metric_eligibility_counts": {
                "leading": sum(r["decision"]["leading_metric_eligible"] for r in records),
                "inclusion": sum(r["decision"]["inclusion_metric_eligible"] for r in records),
                "policy": sum(r["decision"]["policy_metric_eligible"] for r in records),
            },
            "unresolved_count": 0,
            "substantive_disagreement_count": len(disagreements),
            "reviewers": {
                "primary": {"id": PRIMARY_ID, "coverage": "51/51", "blind": True},
                "secondary": {"id": SECONDARY_ID, "coverage": "51/51", "blind": True},
                "additional": {
                    "id": CLAUDE_ID,
                    "coverage": f"{len(claude)}/51",
                    "blind": True,
                    "limitation": "CLI response truncated; retry blocked by service session limit",
                },
                "resolution": {"id": RESOLUTION_ID, "blind": False},
            },
            "comparison_provenance": {
                "schema_sha256": sha256(args.comparison_schema),
                "artifact_sha256": sha256(args.comparison),
                "primary_sha256": sha256(args.primary),
                "secondary_sha256": sha256(args.secondary),
                "packet_set_sha256": packet_manifest["packet_set_sha256"],
                "pair_count": comparison_artifact["pair_count"],
                "classification_counts": {
                    "exact_agreement": comparison_artifact["classification_counts"].get(
                        "exact_agreement", 0
                    ),
                    "compatible_agreement": comparison_artifact["classification_counts"][
                        "compatible_agreement"
                    ],
                    "substantive_disagreement": comparison_artifact["classification_counts"][
                        "substantive_disagreement"
                    ],
                },
                "classification_by_pair": {
                    pair_id: comparison_rows[pair_id]["classification"]
                    for pair_id in sorted(comparison_rows)
                },
            },
            "synthesis_overrides": synthesis_overrides,
            "committed_artifact_sha256": {
                "annotation_guide": sha256(args.guide),
                "ai_amendment": sha256(args.amendment),
                "policy": sha256(policy_path),
                "decisions": sha256(decisions_path),
                "disagreements": sha256(disagreements_path),
                "decision_schema": sha256(args.decision_schema),
                "disagreement_schema": sha256(args.disagreement_schema),
                "comparison_schema": sha256(args.comparison_schema),
                "freeze": sha256(args.freeze),
                "report": sha256(args.report),
                "release_notes": sha256(args.release_notes),
            },
            "maintainer_evidence": {
                "availability": "maintainer_held_not_repository_verifiable",
                "annotation_guide_sha256": packet_manifest["annotation_guide_sha256"],
                "decision_schema_sha256": packet_manifest["decision_schema_sha256"],
                "packet_set_sha256": packet_manifest["packet_set_sha256"],
                "queue_sha256": packet_manifest["queue_sha256"],
                "review_artifact_sha256": {
                    "primary": sha256(args.primary),
                    "secondary": sha256(args.secondary),
                    "claude_partial": sha256(args.claude_partial),
                    "comparison": sha256(args.comparison),
                },
                "preserved_raw_result_sha256": packet_manifest["preserved_raw_result_sha256"],
            },
            "decision_locked_at": created_at_fallback,
            "git": source_git,
            "publication_boundary": (
                "Development diagnostics only: not confirmation-grade human gold, "
                "not held-out, and not answer-quality evidence."
            ),
        }
        _assert_public_text(manifest)
        write_json(manifest_path, manifest)
        if args.dry_run:
            print(
                "dry-run: staged 51 decisions and "
                f"{len(disagreements)} disagreements; manifest_sha256={sha256(manifest_path)}"
            )
        else:
            _publish_directory(
                staged,
                checked_output,
                allow_overwrite=args.allow_overwrite_versioned_lock,
            )
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    print(
        f"wrote 51 decisions, {len(disagreements)} disagreement records, "
        f"Claude coverage {len(claude)}/51"
    )
    print(f"status={dict(status_counts)} agreement={dict(agreement_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
