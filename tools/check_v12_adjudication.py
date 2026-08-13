#!/usr/bin/env python3
"""Validate the OpenSocrates v1.2 #65 adjudication artifacts.

Two stages run independently so the packet stage can gate the blind review
before any decision exists:

    packets    structure, blinding, provenance of the blind packets
    decisions  structure, role separation, blinding attestation, semantic
               consistency, and provenance of the locked decision files

Exit status is non-zero when any check fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

EVAL_ROOT = ROOT / "evals" / "v1.2"
GUIDE_PATH = EVAL_ROOT / "ADJUDICATION_GUIDE.md"
QUEUE_PATH = EVAL_ROOT / "adjudication-queue.jsonl"
FREEZE_PATH = EVAL_ROOT / "adjudication-freeze-v1.0.0.json"
DECISION_SCHEMA_PATH = EVAL_ROOT / "schemas" / "adjudication-decision.schema.json"
DECISIONS_PATH = EVAL_ROOT / "adjudication-decisions-v1.0.0.jsonl"
DISAGREEMENTS_PATH = EVAL_ROOT / "adjudication-disagreements-v1.0.0.jsonl"
MANIFEST_PATH = EVAL_ROOT / "adjudication-manifest-v1.0.0.json"

PACKET_DIR = ROOT / "build" / "adjudication" / "v1.2" / "blind-packets"
PACKET_MANIFEST_PATH = PACKET_DIR / "packet-manifest.json"

EVIDENCE_ROOT = ROOT / "build" / "evidence" / "v1.2"
RAW_RESULT_PATHS = (
    EVIDENCE_ROOT / "screening-results.jsonl",
    EVIDENCE_ROOT / "screening-max-unbounded-results.jsonl",
)

EXPECTED_PAIR_COUNT = 51
EXPECTED_INSTANCE_COUNT = 102

DECISION_SCHEMA = "opensocrates.eval-adjudication-decision/1.0.0"
PROTOCOL_VERSION = "1.2.0"

FORBIDDEN_PACKET_KEYS = frozenset(
    {
        "selected",
        "selected_reasoning_systems",
        "intervene",
        "instructions",
        "score",
        "pass",
        "passed",
        "failure",
        "failed",
        "effort",
        "reasoning_effort",
        "aggregate",
        "recall",
        "model_output",
        "run_id",
        "usage",
        "latency_ms",
    }
)

STATUSES = {
    "retain",
    "relabel",
    "multi_valid",
    "rewrite",
    "exclude_from_policy_metric",
    "invalid",
}
INTERVENTION_POLICIES = {"prohibited", "optional", "required", "undetermined"}
BEHAVIORS = {
    "hold_no_intervention",
    "route_clarifier",
    "route_owner_then_hold",
    "route_safe_alternative",
    "bounded_analysis",
}
AGREEMENTS = {"agreement", "minor_revision", "resolved_disagreement", "unresolved"}
ROUTING_BEHAVIORS = BEHAVIORS - {"hold_no_intervention"}


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, condition: bool, message: str) -> bool:
        self.checks += 1
        if not condition:
            self.failures.append(message)
        return condition

    def summary(self, stage: str) -> int:
        if self.failures:
            print(f"{stage}: FAIL ({len(self.failures)} of {self.checks} checks)")
            for failure in self.failures:
                print(f"  - {failure}")
            return 1
        print(f"{stage}: PASS ({self.checks} checks)")
        return 0


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return records


def find_forbidden_keys(node: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_PACKET_KEYS:
                hits.append(f"{path}.{key}")
            hits.extend(find_forbidden_keys(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            hits.extend(find_forbidden_keys(value, f"{path}[{index}]"))
    return hits


def check_packets() -> int:
    report = Report()

    if not report.check(PACKET_MANIFEST_PATH.exists(), f"missing {PACKET_MANIFEST_PATH}"):
        return report.summary("packets")

    manifest = json.loads(PACKET_MANIFEST_PATH.read_text(encoding="utf-8"))
    packet_files = sorted(p for p in PACKET_DIR.glob("*.json") if p != PACKET_MANIFEST_PATH)

    # --- structure -------------------------------------------------------
    report.check(
        len(packet_files) == EXPECTED_PAIR_COUNT,
        f"expected {EXPECTED_PAIR_COUNT} packets, found {len(packet_files)}",
    )
    report.check(
        manifest.get("unique_pair_count") == EXPECTED_PAIR_COUNT,
        f"manifest unique_pair_count is {manifest.get('unique_pair_count')}",
    )
    report.check(
        manifest.get("locale_instance_count") == EXPECTED_INSTANCE_COUNT,
        f"manifest locale_instance_count is {manifest.get('locale_instance_count')}",
    )
    report.check(
        len(set(manifest.get("pair_ids", []))) == EXPECTED_PAIR_COUNT,
        "manifest pair_ids contains duplicates",
    )

    packet_hashes: dict[str, str] = {}
    for path in packet_files:
        packet = json.loads(path.read_text(encoding="utf-8"))
        pair_id = packet.get("pair_id")
        report.check(pair_id == path.stem, f"{path.name}: pair_id/filename mismatch")
        report.check(
            sorted(packet.get("locales", [])) == ["en", "ko"],
            f"{pair_id}: locales must be exactly en+ko",
        )
        for locale in ("en", "ko"):
            text = packet.get("case_text", {}).get(locale)
            report.check(bool(text), f"{pair_id}: missing {locale} case text")

        # --- blinding ----------------------------------------------------
        body = {k: v for k, v in packet.items() if k != "decision_form"}
        hits = find_forbidden_keys(body)
        report.check(not hits, f"{pair_id}: forbidden packet keys {hits}")

        form = packet.get("decision_form", {})
        report.check(
            form.get("decision", {}).get("status") is None,
            f"{pair_id}: decision form is pre-filled",
        )
        report.check(
            not form.get("decision", {}).get("allowed_behaviors"),
            f"{pair_id}: decision form has pre-filled allowed_behaviors",
        )
        report.check(
            form.get("blinding", {}).get("model_outputs_seen_by_primary") is False,
            f"{pair_id}: decision form blinding default must be false",
        )

        # --- provenance ---------------------------------------------------
        report.check(
            packet.get("annotation_guide_sha256") == manifest.get("annotation_guide_sha256"),
            f"{pair_id}: guide hash does not match manifest",
        )
        report.check(
            bool(packet.get("legacy", {}).get("owner_method")),
            f"{pair_id}: missing legacy owner method",
        )
        report.check(
            bool(packet.get("method_definitions")),
            f"{pair_id}: missing method definitions",
        )

        packet_hashes[pair_id] = hashlib.sha256(canonical_json(packet).encode("utf-8")).hexdigest()

    report.check(
        packet_hashes == manifest.get("packet_sha256"),
        "packet hashes do not match the manifest (packets edited after generation)",
    )
    report.check(
        sha256_obj(manifest.get("packet_sha256", {})) == manifest.get("packet_set_sha256"),
        "packet_set_sha256 does not match packet_sha256",
    )
    report.check(
        sha256_file(GUIDE_PATH) == manifest.get("annotation_guide_sha256"),
        "annotation guide changed after packet generation",
    )
    report.check(
        sha256_file(QUEUE_PATH) == manifest.get("queue_sha256"),
        "adjudication queue changed after packet generation",
    )

    check_raw_results_unchanged(report, manifest.get("preserved_raw_result_sha256", {}))

    if FREEZE_PATH.exists():
        freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        report.check(
            freeze.get("annotation_guide_sha256") == manifest.get("annotation_guide_sha256"),
            "freeze record guide hash differs from packet manifest",
        )
        report.check(
            freeze.get("packet_set_sha256") == manifest.get("packet_set_sha256"),
            "freeze record packet set hash differs from packet manifest",
        )

    return report.summary("packets")


def check_raw_results_unchanged(report: Report, recorded: dict[str, Any]) -> None:
    """Historical #65 evidence must be byte-identical to the recorded baseline."""
    for path in RAW_RESULT_PATHS:
        expected = recorded.get(path.name)
        if expected is None:
            report.check(
                not path.exists(),
                f"{path.name} exists but has no recorded baseline hash",
            )
            continue
        if not report.check(path.exists(), f"{path.name} is missing but was hashed"):
            continue
        report.check(
            sha256_file(path) == expected,
            f"{path.name} was modified: raw #65 results must never be rewritten",
        )


def check_decisions() -> int:  # noqa: C901  # Branch-explicit adjudication contract.
    report = Report()

    if not DECISIONS_PATH.exists():
        print(f"decisions: SKIP (no {DECISIONS_PATH.name} yet)")
        print("  Phases 4-7 are pending: no locked adjudication decision set exists.")
        return 0

    decisions = read_jsonl(DECISIONS_PATH)
    disagreements = read_jsonl(DISAGREEMENTS_PATH) if DISAGREEMENTS_PATH.exists() else []
    manifest = (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    )
    packet_manifest = (
        json.loads(PACKET_MANIFEST_PATH.read_text(encoding="utf-8"))
        if PACKET_MANIFEST_PATH.exists()
        else {}
    )
    expected_pairs = set(packet_manifest.get("pair_ids", []))

    seen: set[str] = set()
    for index, record in enumerate(decisions):
        pair_id = record.get("pair_id", f"<record {index}>")

        # --- structure ----------------------------------------------------
        report.check(record.get("schema") == DECISION_SCHEMA, f"{pair_id}: wrong schema")
        report.check(
            record.get("protocol_version") == PROTOCOL_VERSION,
            f"{pair_id}: wrong protocol_version",
        )
        report.check(pair_id not in seen, f"{pair_id}: duplicate decision record")
        seen.add(pair_id)
        report.check(
            sorted(record.get("locales", [])) == ["en", "ko"],
            f"{pair_id}: locales must be exactly en+ko",
        )

        decision = record.get("decision", {})
        review = record.get("review", {})
        blinding = record.get("blinding", {})
        semantic = record.get("semantic_review", {})
        provenance = record.get("provenance", {})

        report.check(decision.get("status") in STATUSES, f"{pair_id}: bad status")
        report.check(
            decision.get("intervention_policy") in INTERVENTION_POLICIES,
            f"{pair_id}: bad intervention_policy",
        )
        behaviors = decision.get("allowed_behaviors", [])
        report.check(set(behaviors) <= BEHAVIORS, f"{pair_id}: unknown allowed_behaviors")
        report.check(review.get("agreement") in AGREEMENTS, f"{pair_id}: bad agreement value")
        report.check(bool(record.get("rationale")), f"{pair_id}: rationale is required")
        report.check(
            bool(record.get("decisive_features")),
            f"{pair_id}: decisive_features is required",
        )

        # --- role separation ----------------------------------------------
        primary = review.get("primary_adjudicator")
        second = review.get("second_reviewer")
        author = review.get("author_or_intent_witness")
        report.check(bool(primary), f"{pair_id}: missing primary adjudicator")
        report.check(bool(second), f"{pair_id}: missing second reviewer")
        report.check(primary != second, f"{pair_id}: primary and second reviewer are the same")
        report.check(
            author is None or author != primary,
            f"{pair_id}: label author cannot be the primary adjudicator",
        )
        if review.get("agreement") == "resolved_disagreement":
            report.check(
                bool(review.get("resolution_reviewer")),
                f"{pair_id}: resolved disagreement needs a resolution reviewer",
            )
        report.check(
            bool(review.get("primary_decision_locked_at")),
            f"{pair_id}: missing primary lock timestamp",
        )
        report.check(
            bool(review.get("second_decision_locked_at")),
            f"{pair_id}: missing second lock timestamp",
        )

        # --- blinding -------------------------------------------------------
        for field in (
            "model_outputs_seen_by_primary",
            "aggregate_results_seen_by_primary",
            "model_outputs_seen_by_second",
            "aggregate_results_seen_by_second",
        ):
            report.check(
                blinding.get(field) is False,
                f"{pair_id}: blinding attestation {field} must be false",
            )
        report.check(bool(blinding.get("attestation")), f"{pair_id}: missing blinding attestation")

        # --- semantic consistency --------------------------------------------
        if decision.get("intervention_policy") == "prohibited":
            report.check(
                decision.get("leading_method") is None,
                f"{pair_id}: prohibited intervention cannot set a leading method",
            )
            report.check(
                not (set(behaviors) & ROUTING_BEHAVIORS),
                f"{pair_id}: prohibited intervention cannot allow routing behaviors",
            )
        if behaviors == ["hold_no_intervention"]:
            report.check(
                decision.get("inclusion_metric_eligible") is False,
                f"{pair_id}: hold-only case cannot be inclusion-metric eligible",
            )
        if decision.get("leading_metric_eligible") is True:
            report.check(
                isinstance(decision.get("leading_method"), str) and decision.get("leading_method"),
                f"{pair_id}: leading-metric eligible case needs one leading method",
            )
        if decision.get("policy_metric_eligible") is True:
            report.check(
                bool(behaviors),
                f"{pair_id}: policy-metric eligible case needs allowed behaviors",
            )
        if semantic.get("translation_mismatch") is True:
            report.check(
                decision.get("policy_metric_eligible") is False,
                f"{pair_id}: translation mismatch cannot be policy-metric eligible",
            )
        if decision.get("status") in {"rewrite", "invalid"}:
            report.check(
                pair_id in expected_pairs,
                f"{pair_id}: rewrite/invalid must keep the original pair id on record",
            )

        # --- provenance -------------------------------------------------------
        report.check(
            bool(provenance.get("annotation_guide_sha256")),
            f"{pair_id}: missing annotation guide hash",
        )
        report.check(
            bool(provenance.get("blind_packet_sha256")),
            f"{pair_id}: missing blind packet hash",
        )
        report.check(
            bool(provenance.get("decision_created_at")),
            f"{pair_id}: missing decision timestamp",
        )
        source = provenance.get("source_case_sha256", {})
        report.check(
            bool(source.get("en")) and bool(source.get("ko")),
            f"{pair_id}: missing source case hashes",
        )
        if expected_pairs:
            expected_packet = packet_manifest.get("packet_sha256", {}).get(pair_id)
            report.check(
                provenance.get("blind_packet_sha256") == expected_packet,
                f"{pair_id}: blind packet hash does not match the generated packet",
            )

    if expected_pairs:
        missing = sorted(expected_pairs - seen)
        report.check(not missing, f"decisions missing for pairs: {missing}")
        extra = sorted(seen - expected_pairs)
        report.check(not extra, f"decisions for unknown pairs: {extra}")

    unresolved = [
        r["pair_id"] for r in decisions if r.get("review", {}).get("agreement") == "unresolved"
    ]
    for pair_id in unresolved:
        record = next(r for r in decisions if r["pair_id"] == pair_id)
        report.check(
            record.get("decision", {}).get("status")
            in {"rewrite", "exclude_from_policy_metric", "invalid"}
            or record.get("decision", {}).get("policy_metric_eligible") is False,
            f"{pair_id}: unresolved pair must not stay policy-metric eligible",
        )

    disagreement_pairs = {d.get("pair_id") for d in disagreements}
    for record in decisions:
        if record.get("review", {}).get("agreement") in {
            "resolved_disagreement",
            "unresolved",
        }:
            report.check(
                record["pair_id"] in disagreement_pairs,
                f"{record['pair_id']}: disagreement is not recorded in the disagreement file",
            )

    if manifest:
        report.check(
            manifest.get("decisions_sha256") == sha256_file(DECISIONS_PATH),
            "manifest decisions_sha256 does not match the decision file",
        )
        report.check(
            manifest.get("annotation_guide_sha256") == sha256_file(GUIDE_PATH),
            "manifest guide hash does not match the annotation guide",
        )
        check_raw_results_unchanged(report, manifest.get("preserved_raw_result_sha256", {}))

    return report.summary("decisions")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("packets", "decisions", "all"),
        default="all",
        help="which artifacts to validate (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    status = 0
    if args.stage in {"packets", "all"}:
        status |= check_packets()
    if args.stage in {"decisions", "all"}:
        status |= check_decisions()
    return status


if __name__ == "__main__":
    sys.exit(main())
