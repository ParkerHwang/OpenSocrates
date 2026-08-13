#!/usr/bin/env python3
"""Build the maintainer-authorized provisional v1.2 adjudication artifacts.

This is deliberately a synthesis tool, not another blind reviewer.  It keeps
both complete ChatGPT Pro reviews, the recoverable Claude subset, every
substantive disagreement, and the historical labels.  The resulting decision
set is development-only under ``ADJUDICATION_AI_AMENDMENT.md``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "evals/v1.2"
BUILD_ROOT = ROOT / "build/adjudication/v1.2"
PACKET_DIR = BUILD_ROOT / "blind-packets"

PRIMARY_PATH = BUILD_ROOT / "askpro-blind-adjudication.json"
SECONDARY_PATH = BUILD_ROOT / "askpro-second-blind-adjudication.json"
CLAUDE_PATH = BUILD_ROOT / "claude-opus5-blind-review.json"
COMPARISON_PATH = BUILD_ROOT / "reviewer-comparison.json"

GUIDE_PATH = EVAL_ROOT / "ADJUDICATION_GUIDE.md"
AMENDMENT_PATH = EVAL_ROOT / "ADJUDICATION_AI_AMENDMENT.md"
POLICY_PATH = EVAL_ROOT / "adjudication-policy-v1.0.0.json"
DECISIONS_PATH = EVAL_ROOT / "adjudication-decisions-v1.0.0.jsonl"
DISAGREEMENTS_PATH = EVAL_ROOT / "adjudication-disagreements-v1.0.0.jsonl"
MANIFEST_PATH = EVAL_ROOT / "adjudication-manifest-v1.0.0.json"

RAW_HASHES = {
    "screening-results.jsonl": "425828d03a831b61013247b317b6c425cca9c846b343915d2e61186e1e6a9636",
    "screening-max-unbounded-results.jsonl": "3aa5987b595a35be94c37e4a3776de59f250c1c9aa9678769740221bd52645ea",
}
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
COMPATIBLE_PAIRS = {
    "design-thinking-positive-03",
    "lateral-thinking-negative-02",
}
HOLD_NORMALIZATION_PAIRS = {
    "reflective-equilibrium-insufficiency-01",
    "triangulation-insufficiency-01",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")


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
) -> tuple[dict[str, Any], str, str]:
    """Return decision, selected source, and resolution explanation."""
    decision = normalize(secondary)
    selected = "secondary"
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
    elif pair_id in COMPATIBLE_PAIRS:
        explanation = (
            "Both complete reviews agree on intervention policy, leading-route "
            "semantics, and metric eligibility. The secondary review's narrower "
            "case-specific behavior and method sets are selected."
        )
    return decision, selected, explanation


def git_state() -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    return {
        "revision": revision,
        "dirty": bool(status),
        "note": "Dirty worktree preserved; manifest creation itself may add an untracked entry.",
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


def main() -> int:
    primary_artifact = read_json(PRIMARY_PATH)
    secondary_artifact = read_json(SECONDARY_PATH)
    packet_manifest = read_json(PACKET_DIR / "packet-manifest.json")
    claude_wrapper = read_json(CLAUDE_PATH)
    claude = extract_claude_records(claude_wrapper)

    primary = {record["pair_id"]: record for record in primary_artifact["decisions"]}
    secondary = {record["pair_id"]: record for record in secondary_artifact["decisions"]}
    expected = set(packet_manifest["pair_ids"])
    if set(primary) != expected or set(secondary) != expected:
        raise SystemExit("both complete reviews must cover exactly the frozen 51 pairs")
    if "decision-tree-analysis-mechanical-1" not in claude:
        raise SystemExit("mechanical boundary resolution requires the recovered Claude record")

    primary_lock = primary_artifact["decisions"][0]["review"]["primary_decision_locked_at"]
    secondary_lock = utc_mtime(SECONDARY_PATH)
    created_at = secondary_lock
    uncertainty_notes = {
        item["pair_id"]: item
        for item in secondary_artifact.get("uncertainties", [])
        if item.get("residual") is True
    }

    records: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    for pair_id in sorted(expected):
        packet = read_json(PACKET_DIR / f"{pair_id}.json")
        primary_record = primary[pair_id]
        second_record = secondary[pair_id]
        decision, selected_source, resolution_reason = final_decision(
            pair_id, second_record, claude
        )
        compatible = pair_id in COMPATIBLE_PAIRS
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

        notes: list[str] = []
        if pair_id in uncertainty_notes:
            note = uncertainty_notes[pair_id]
            notes.append(
                f"Non-decision-changing locale nuance: {note['issue']} {note['resolution']}"
            )

        record = {
            "schema": "opensocrates.eval-adjudication-decision/1.0.0",
            "protocol_version": "1.2.0",
            "pair_id": pair_id,
            "locales": ["en", "ko"],
            "legacy": packet["legacy"],
            "semantic_review": {
                "en_ko_equivalent": True,
                "translation_mismatch": False,
                "notes": notes,
            },
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
                "primary_decision_locked_at": primary_lock,
                "second_decision_locked_at": secondary_lock,
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
                        "status": "resolved_for_provisional_development_gold",
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
        "guide_version": "1.0.0",
        "status": "maintainer_authorized_ai_assisted_provisional_development_policy",
        "locked_at": created_at,
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
            "primary": primary_artifact["policy"],
            "secondary": secondary_artifact["policy"],
        },
        "resolution_note": (
            "The secondary policy is adopted as the case-specific base because it "
            "distinguishes explicit contraindications from method stop conditions. "
            "The primary policy is preserved as dissent. Two schema-level behavior "
            "normalizations and one Claude-supported mechanical-boundary resolution "
            "are recorded in the disagreement ledger."
        ),
        "publication_boundary": (
            "AI-assisted provisional development adjudication; not confirmation-grade "
            "human gold and not held-out evidence."
        ),
    }

    write_json(POLICY_PATH, policy)
    write_jsonl(DECISIONS_PATH, records)
    write_jsonl(DISAGREEMENTS_PATH, disagreements)

    status_counts = Counter(record["decision"]["status"] for record in records)
    agreement_counts = Counter(record["review"]["agreement"] for record in records)
    policy_counts = Counter(record["decision"]["intervention_policy"] for record in records)
    manifest = {
        "schema": "opensocrates.eval-adjudication-manifest/1.0.0",
        "protocol_version": "1.2.0",
        "status": "ai_assisted_provisional_development_gold",
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
        "annotation_guide_sha256": sha256(GUIDE_PATH),
        "ai_amendment_sha256": sha256(AMENDMENT_PATH),
        "packet_set_sha256": packet_manifest["packet_set_sha256"],
        "policy_sha256": sha256(POLICY_PATH),
        "decisions_sha256": sha256(DECISIONS_PATH),
        "disagreements_sha256": sha256(DISAGREEMENTS_PATH),
        "review_artifact_sha256": {
            "primary": sha256(PRIMARY_PATH),
            "secondary": sha256(SECONDARY_PATH),
            "claude_partial": sha256(CLAUDE_PATH),
            "comparison": sha256(COMPARISON_PATH),
        },
        "preserved_raw_result_sha256": RAW_HASHES,
        "decision_locked_at": created_at,
        "git": git_state(),
        "publication_boundary": (
            "Development diagnostics only. These records do not satisfy the frozen "
            "guide's independent-human confirmation requirement."
        ),
    }
    write_json(MANIFEST_PATH, manifest)
    print(
        f"wrote 51 decisions, {len(disagreements)} disagreement records, "
        f"Claude coverage {len(claude)}/51"
    )
    print(f"status={dict(status_counts)} agreement={dict(agreement_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
