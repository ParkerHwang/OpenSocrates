#!/usr/bin/env python3
"""Validate the public v1.2 adjudication snapshot and optional private evidence.

The default ``committed`` mode is the public clean-clone gate. It reads only
tracked repository artifacts. ``maintainer-evidence`` is an explicit opt-in
that first runs the committed gate and then requires the unpublished packet,
raw-result, and reviewer files recorded by the historical manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from json_schema_2020 import ValidationIssue, check_schema, validate
from v12_adjudication_contract import (
    EVALUATION_ID,
    EVIDENCE_GRADE,
    find_forbidden_packet_keys,
)

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PAIR_COUNT = 51
EXPECTED_INSTANCE_COUNT = 102
EXPECTED_DISAGREEMENT_COUNT = 49
PROTOCOL_VERSION = "1.2.0"
DECISION_SCHEMA_ID = "opensocrates.eval-adjudication-decision/1.0.0"
DISAGREEMENT_SCHEMA_ID = "opensocrates.eval-adjudication-disagreement/1.0.0"
MAINTAINER_EVIDENCE_AVAILABILITY = "maintainer_held_not_repository_verifiable"
ROUTING_BEHAVIORS = {
    "route_clarifier",
    "route_owner_then_hold",
    "route_safe_alternative",
    "bounded_analysis",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_USE_PATTERN = re.compile(r"[\ue000-\uf8ff]")


@dataclass(frozen=True)
class ArtifactPaths:
    root: Path

    @property
    def eval_root(self) -> Path:
        return self.root / "evals" / "v1.2"

    @property
    def guide(self) -> Path:
        return self.eval_root / "ADJUDICATION_GUIDE.md"

    @property
    def amendment(self) -> Path:
        return self.eval_root / "ADJUDICATION_AI_AMENDMENT.md"

    @property
    def freeze(self) -> Path:
        return self.eval_root / "adjudication-freeze-v1.0.0.json"

    @property
    def policy(self) -> Path:
        return self.eval_root / "adjudication-policy-v1.0.0.json"

    @property
    def decisions(self) -> Path:
        return self.eval_root / "adjudication-decisions-v1.0.0.jsonl"

    @property
    def disagreements(self) -> Path:
        return self.eval_root / "adjudication-disagreements-v1.0.0.jsonl"

    @property
    def manifest(self) -> Path:
        return self.eval_root / "adjudication-manifest-v1.0.0.json"

    @property
    def decision_schema(self) -> Path:
        return self.eval_root / "schemas" / "adjudication-decision.schema.json"

    @property
    def disagreement_schema(self) -> Path:
        return self.eval_root / "schemas" / "adjudication-disagreement.schema.json"

    @property
    def report(self) -> Path:
        return self.root / "docs" / "v1.2-adjudication-report.md"

    @property
    def method_root(self) -> Path:
        return self.root / "content" / "methods"

    @property
    def queue(self) -> Path:
        return self.eval_root / "adjudication-queue.jsonl"

    @property
    def packet_dir(self) -> Path:
        return self.root / "build" / "adjudication" / "v1.2" / "blind-packets"

    @property
    def packet_manifest(self) -> Path:
        return self.packet_dir / "packet-manifest.json"

    @property
    def evidence_root(self) -> Path:
        return self.root / "build" / "evidence" / "v1.2"

    @property
    def review_root(self) -> Path:
        return self.root / "build" / "adjudication" / "v1.2"


class Report:
    def __init__(self) -> None:
        self.failures: list[tuple[str, str]] = []
        self.checks = 0

    def check(self, condition: bool, code: str, message: str) -> bool:
        self.checks += 1
        if not condition:
            self.failures.append((code, message))
        return condition

    def fail(self, code: str, message: str) -> None:
        self.check(False, code, message)

    def schema_issues(self, prefix: str, pair_id: str, issues: list[ValidationIssue]) -> None:
        self.check(not issues, f"{prefix}.schema", f"{pair_id}: schema validation failed")
        for issue in issues:
            self.failures.append((f"{prefix}.schema.detail", f"{pair_id}: {issue}"))

    def summary(self, label: str, *, scope: str) -> int:
        if self.failures:
            print(f"{label}: FAIL ({len(self.failures)} failures; {self.checks} checks; {scope})")
            for code, message in self.failures:
                print(f"  - [{code}] {message}")
            return 1
        print(f"{label}: PASS ({self.checks} checks; {scope})")
        return 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_object(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_text(report: Report, path: Path, label: str) -> str | None:
    if not report.check(path.is_file(), f"committed.{label}.missing", f"missing {path}"):
        return None
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        report.fail(f"committed.{label}.unreadable", f"cannot read {path}: {type(exc).__name__}")
        return None
    report.check(bool(value), f"committed.{label}.empty", f"{path} is empty")
    return value


def load_json_object(report: Report, path: Path, label: str) -> dict[str, Any] | None:
    text = load_text(report, path, label)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        report.fail(f"committed.{label}.json", f"{path}: invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        report.fail(f"committed.{label}.type", f"{path}: expected a JSON object")
        return None
    return value


def load_jsonl(report: Report, path: Path, label: str) -> list[dict[str, Any]]:
    text = load_text(report, path, label)
    if text is None:
        return []
    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            report.fail(f"committed.{label}.json", f"{path}:{lineno}: invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            report.fail(
                f"committed.{label}.record_type",
                f"{path}:{lineno}: expected a JSON object",
            )
            continue
        records.append(value)
    report.check(bool(records), f"committed.{label}.records_empty", f"{path} has no records")
    return records


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_rfc3339(value: Any) -> bool:
    return isinstance(value, str) and not validate(
        value,
        {"type": "string", "format": "date-time"},
    )


def _status_paths_ending_gold(node: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}"
            if key == "status" and isinstance(value, str) and value.endswith("_gold"):
                hits.append(child)
            hits.extend(_status_paths_ending_gold(value, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            hits.extend(_status_paths_ending_gold(value, f"{path}[{index}]"))
    return hits


def _record_pair_ids(report: Report, records: list[dict[str, Any]], label: str) -> set[str]:
    pair_ids: list[str] = []
    for index, record in enumerate(records):
        pair_id = record.get("pair_id")
        report.check(
            isinstance(pair_id, str) and bool(pair_id),
            f"committed.{label}.pair_id",
            f"record {index}: pair_id must be a non-empty string",
        )
        if isinstance(pair_id, str):
            pair_ids.append(pair_id)
    duplicates = sorted(pair_id for pair_id, count in Counter(pair_ids).items() if count > 1)
    report.check(
        not duplicates,
        f"committed.{label}.duplicate_pair",
        f"duplicate pair IDs: {duplicates}",
    )
    return set(pair_ids)


def _method_ids(record: dict[str, Any]) -> set[str]:
    decision = record.get("decision", {})
    values = set()
    leading = decision.get("leading_method")
    if isinstance(leading, str):
        values.add(leading)
    for field in (
        "acceptable_leading_methods",
        "acceptable_inclusion_methods",
        "prohibited_methods",
    ):
        raw = decision.get(field, [])
        if isinstance(raw, list):
            values.update(value for value in raw if isinstance(value, str))
    legacy_owner = record.get("legacy", {}).get("owner_method")
    if isinstance(legacy_owner, str):
        values.add(legacy_owner)
    return values


def _validate_decision_semantics(
    report: Report,
    record: dict[str, Any],
    known_methods: set[str],
) -> None:
    pair_id = str(record.get("pair_id", "<unknown>"))
    decision = record.get("decision", {})
    review = record.get("review", {})
    semantic = record.get("semantic_review", {})
    blinding = record.get("blinding", {})
    provenance = record.get("provenance", {})
    behaviors = decision.get("allowed_behaviors", [])

    report.check(
        record.get("evidence_grade") == EVIDENCE_GRADE,
        "committed.decisions.evidence_grade",
        f"{pair_id}: wrong or missing evidence_grade",
    )
    report.check(
        review.get("primary_adjudicator") != review.get("second_reviewer"),
        "committed.decisions.reviewer_separation",
        f"{pair_id}: primary and second reviewer must differ",
    )
    author = review.get("author_or_intent_witness")
    report.check(
        author is None or author != review.get("primary_adjudicator"),
        "committed.decisions.author_separation",
        f"{pair_id}: author cannot be primary adjudicator",
    )
    if review.get("agreement") == "resolved_disagreement":
        report.check(
            isinstance(review.get("resolution_reviewer"), str)
            and bool(review["resolution_reviewer"]),
            "committed.decisions.resolution_reviewer",
            f"{pair_id}: resolved disagreement needs a resolution reviewer",
        )
    for field in (
        "model_outputs_seen_by_primary",
        "aggregate_results_seen_by_primary",
        "model_outputs_seen_by_second",
        "aggregate_results_seen_by_second",
    ):
        report.check(
            blinding.get(field) is False,
            "committed.decisions.blinding",
            f"{pair_id}: {field} must be false",
        )

    if decision.get("intervention_policy") == "prohibited":
        report.check(
            decision.get("leading_method") is None,
            "committed.decisions.prohibited_leader",
            f"{pair_id}: prohibited intervention cannot have a leader",
        )
        report.check(
            not (set(behaviors) & ROUTING_BEHAVIORS),
            "committed.decisions.prohibited_behavior",
            f"{pair_id}: prohibited intervention contains routing behavior",
        )
    if behaviors == ["hold_no_intervention"]:
        report.check(
            decision.get("inclusion_metric_eligible") is False,
            "committed.decisions.hold_inclusion",
            f"{pair_id}: hold-only case cannot be inclusion-metric eligible",
        )
    if decision.get("leading_metric_eligible") is True:
        report.check(
            isinstance(decision.get("leading_method"), str) and bool(decision["leading_method"]),
            "committed.decisions.leading_metric",
            f"{pair_id}: leading-metric eligible case needs one leader",
        )
    if decision.get("inclusion_metric_eligible") is False:
        report.check(
            decision.get("acceptable_inclusion_methods") == [],
            "committed.decisions.inclusion_boundary",
            f"{pair_id}: ineligible inclusion metric must have an empty inclusion set",
        )
    if decision.get("policy_metric_eligible") is True:
        report.check(
            bool(behaviors),
            "committed.decisions.policy_behavior",
            f"{pair_id}: policy-metric eligible case needs an allowed behavior",
        )
    if semantic.get("translation_mismatch") is True:
        report.check(
            decision.get("policy_metric_eligible") is False,
            "committed.decisions.translation_metric",
            f"{pair_id}: translation mismatch cannot be policy-metric eligible",
        )

    acceptable = set(decision.get("acceptable_leading_methods", [])) | set(
        decision.get("acceptable_inclusion_methods", [])
    )
    prohibited = set(decision.get("prohibited_methods", []))
    report.check(
        not (acceptable & prohibited),
        "committed.decisions.method_conflict",
        f"{pair_id}: methods cannot be both acceptable and prohibited",
    )
    report.check(
        _method_ids(record) <= known_methods,
        "committed.decisions.unknown_method",
        f"{pair_id}: unknown method IDs {sorted(_method_ids(record) - known_methods)}",
    )
    report.check(
        _is_sha256(provenance.get("annotation_guide_sha256")),
        "committed.decisions.guide_hash_format",
        f"{pair_id}: annotation guide hash must be SHA-256",
    )


def _check_hash(
    report: Report,
    hashes: dict[str, Any],
    key: str,
    path: Path,
) -> None:
    expected = hashes.get(key)
    report.check(
        _is_sha256(expected),
        f"committed.hash.{key}.format",
        f"committed hash {key!r} is not SHA-256",
    )
    if path.is_file() and _is_sha256(expected):
        report.check(
            sha256_file(path) == expected,
            f"committed.hash.{key}.mismatch",
            f"{path}: SHA-256 does not match manifest",
        )


def _check_public_text_boundaries(report: Report, paths: ArtifactPaths) -> None:
    public_paths = (
        paths.guide,
        paths.amendment,
        paths.policy,
        paths.decisions,
        paths.disagreements,
        paths.manifest,
        paths.freeze,
        paths.report,
    )
    for path in public_paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        report.check(
            PRIVATE_USE_PATTERN.search(text) is None and "filecite" not in text.casefold(),
            "committed.privacy.private_citation",
            f"{path}: contains a private-use/filecite citation token",
        )
        report.check(
            re.search(r"(?<![A-Za-z0-9])#65\b", text) is None,
            "committed.identifier.stale_65",
            f"{path}: contains the colliding GitHub identifier #65",
        )


def validate_committed(paths: ArtifactPaths) -> Report:  # noqa: C901
    report = Report()
    guide_text = load_text(report, paths.guide, "guide")
    amendment_text = load_text(report, paths.amendment, "amendment")
    load_text(report, paths.report, "public_report")
    policy = load_json_object(report, paths.policy, "policy") or {}
    freeze = load_json_object(report, paths.freeze, "freeze") or {}
    manifest = load_json_object(report, paths.manifest, "manifest") or {}
    decision_schema = load_json_object(report, paths.decision_schema, "decision_schema") or {}
    disagreement_schema = (
        load_json_object(report, paths.disagreement_schema, "disagreement_schema") or {}
    )
    decisions = load_jsonl(report, paths.decisions, "decisions")
    disagreements = load_jsonl(report, paths.disagreements, "disagreements")

    decision_schema_issues = check_schema(decision_schema)
    disagreement_schema_issues = check_schema(disagreement_schema)
    report.schema_issues("committed.decision_schema", "schema", decision_schema_issues)
    report.schema_issues("committed.disagreement_schema", "schema", disagreement_schema_issues)

    report.check(
        len(decisions) == EXPECTED_PAIR_COUNT,
        "committed.decisions.count",
        f"expected exactly {EXPECTED_PAIR_COUNT} decisions, found {len(decisions)}",
    )
    report.check(
        len(disagreements) == EXPECTED_DISAGREEMENT_COUNT,
        "committed.disagreements.count",
        f"expected exactly {EXPECTED_DISAGREEMENT_COUNT} disagreements, found {len(disagreements)}",
    )
    decision_pairs = _record_pair_ids(report, decisions, "decisions")
    disagreement_pairs = _record_pair_ids(report, disagreements, "disagreements")
    report.check(
        len(decision_pairs) == EXPECTED_PAIR_COUNT,
        "committed.decisions.unique_count",
        f"expected {EXPECTED_PAIR_COUNT} unique decision pair IDs, found {len(decision_pairs)}",
    )

    known_methods = (
        {path.name for path in paths.method_root.iterdir() if path.is_dir()}
        if paths.method_root.is_dir()
        else set()
    )
    report.check(
        bool(known_methods),
        "committed.methods.missing",
        f"method definitions unavailable under {paths.method_root}",
    )
    if not decision_schema_issues:
        for record in decisions:
            pair_id = str(record.get("pair_id", "<unknown>"))
            report.schema_issues(
                "committed.decisions",
                pair_id,
                validate(record, decision_schema),
            )
            _validate_decision_semantics(report, record, known_methods)
    if not disagreement_schema_issues:
        for record in disagreements:
            pair_id = str(record.get("pair_id", "<unknown>"))
            report.schema_issues(
                "committed.disagreements",
                pair_id,
                validate(record, disagreement_schema),
            )

    indexed_decisions = {
        record["pair_id"]: record for record in decisions if isinstance(record.get("pair_id"), str)
    }
    indexed_disagreements = {
        record["pair_id"]: record
        for record in disagreements
        if isinstance(record.get("pair_id"), str)
    }
    expected_disagreements = {
        pair_id
        for pair_id, record in indexed_decisions.items()
        if record.get("review", {}).get("agreement") in {"resolved_disagreement", "unresolved"}
    }
    report.check(
        disagreement_pairs == expected_disagreements,
        "committed.disagreements.referential_integrity",
        "disagreement pair IDs do not exactly match resolved/unresolved decision records",
    )
    report.check(
        disagreement_pairs <= decision_pairs,
        "committed.disagreements.orphan",
        f"orphan disagreement pairs: {sorted(disagreement_pairs - decision_pairs)}",
    )
    for pair_id, disagreement in indexed_disagreements.items():
        decision = indexed_decisions.get(pair_id)
        if decision is None:
            continue
        report.check(
            disagreement.get("resolution", {}).get("final_decision") == decision.get("decision"),
            "committed.disagreements.final_decision",
            f"{pair_id}: disagreement final_decision differs from the decision record",
        )
        report.check(
            disagreement.get("evidence_grade") == EVIDENCE_GRADE,
            "committed.disagreements.evidence_grade",
            f"{pair_id}: wrong or missing evidence_grade",
        )

    expected_manifest_keys = {
        "schema",
        "protocol_version",
        "evaluation_id",
        "evidence_grade",
        "status",
        "pair_count",
        "locale_instance_count",
        "status_counts",
        "agreement_counts",
        "intervention_policy_counts",
        "metric_eligibility_counts",
        "unresolved_count",
        "substantive_disagreement_count",
        "reviewers",
        "committed_artifact_sha256",
        "maintainer_evidence",
        "decision_locked_at",
        "git",
        "publication_boundary",
    }
    report.check(
        set(manifest) == expected_manifest_keys,
        "committed.manifest.additional_properties",
        f"manifest fields differ: missing={sorted(expected_manifest_keys - set(manifest))} "
        f"extra={sorted(set(manifest) - expected_manifest_keys)}",
    )
    report.check(
        manifest.get("schema") == "opensocrates.eval-adjudication-manifest/1.0.0",
        "committed.manifest.schema",
        "manifest schema identifier is wrong",
    )
    report.check(
        manifest.get("evaluation_id") == EVALUATION_ID,
        "committed.manifest.evaluation_id",
        "manifest evaluation_id is wrong or missing",
    )
    report.check(
        manifest.get("protocol_version") == PROTOCOL_VERSION,
        "committed.manifest.protocol",
        "manifest protocol_version is wrong",
    )
    report.check(
        manifest.get("evidence_grade") == EVIDENCE_GRADE,
        "committed.manifest.evidence_grade",
        "manifest evidence_grade is wrong or missing",
    )
    report.check(
        manifest.get("status") == EVIDENCE_GRADE,
        "committed.manifest.status",
        "manifest status must use the non-gold evidence grade",
    )
    report.check(
        _is_rfc3339(manifest.get("decision_locked_at")),
        "committed.manifest.decision_locked_at",
        "manifest decision_locked_at must be an RFC 3339 date-time",
    )
    report.check(
        manifest.get("pair_count") == len(decisions) == EXPECTED_PAIR_COUNT,
        "committed.manifest.pair_count",
        "manifest pair_count does not match the required decision count",
    )
    locale_count = sum(
        len(record.get("locales", []))
        for record in decisions
        if isinstance(record.get("locales"), list)
    )
    report.check(
        manifest.get("locale_instance_count") == locale_count == EXPECTED_INSTANCE_COUNT,
        "committed.manifest.locale_count",
        "manifest locale_instance_count does not match decisions",
    )
    aggregates = {
        "status_counts": dict(
            sorted(Counter(r.get("decision", {}).get("status") for r in decisions).items())
        ),
        "agreement_counts": dict(
            sorted(Counter(r.get("review", {}).get("agreement") for r in decisions).items())
        ),
        "intervention_policy_counts": dict(
            sorted(
                Counter(r.get("decision", {}).get("intervention_policy") for r in decisions).items()
            )
        ),
        "metric_eligibility_counts": {
            "leading": sum(
                r.get("decision", {}).get("leading_metric_eligible") is True for r in decisions
            ),
            "inclusion": sum(
                r.get("decision", {}).get("inclusion_metric_eligible") is True for r in decisions
            ),
            "policy": sum(
                r.get("decision", {}).get("policy_metric_eligible") is True for r in decisions
            ),
        },
    }
    for field, expected in aggregates.items():
        report.check(
            manifest.get(field) == expected,
            f"committed.manifest.{field}",
            f"manifest {field} does not match committed decisions",
        )
    unresolved_count = sum(
        record.get("review", {}).get("agreement") == "unresolved" for record in decisions
    )
    report.check(
        manifest.get("unresolved_count") == unresolved_count,
        "committed.manifest.unresolved_count",
        "manifest unresolved_count does not match decisions",
    )
    report.check(
        manifest.get("substantive_disagreement_count") == len(disagreements),
        "committed.manifest.disagreement_count",
        "manifest substantive_disagreement_count does not match ledger",
    )

    hashes = manifest.get("committed_artifact_sha256", {})
    report.check(
        isinstance(hashes, dict),
        "committed.manifest.hashes_type",
        "committed_artifact_sha256 must be an object",
    )
    if isinstance(hashes, dict):
        expected_hash_keys = {
            "annotation_guide",
            "ai_amendment",
            "policy",
            "decisions",
            "disagreements",
            "decision_schema",
            "disagreement_schema",
        }
        report.check(
            set(hashes) == expected_hash_keys,
            "committed.manifest.hashes_fields",
            "committed_artifact_sha256 fields are incomplete or contain extras",
        )
        for key, path in (
            ("annotation_guide", paths.guide),
            ("ai_amendment", paths.amendment),
            ("policy", paths.policy),
            ("decisions", paths.decisions),
            ("disagreements", paths.disagreements),
            ("decision_schema", paths.decision_schema),
            ("disagreement_schema", paths.disagreement_schema),
        ):
            _check_hash(report, hashes, key, path)

    maintainer = manifest.get("maintainer_evidence", {})
    report.check(
        isinstance(maintainer, dict)
        and maintainer.get("availability") == MAINTAINER_EVIDENCE_AVAILABILITY,
        "committed.manifest.evidence_boundary",
        "maintainer evidence must be marked not repository-verifiable",
    )
    if isinstance(maintainer, dict):
        expected_maintainer_keys = {
            "availability",
            "annotation_guide_sha256",
            "decision_schema_sha256",
            "packet_set_sha256",
            "queue_sha256",
            "review_artifact_sha256",
            "preserved_raw_result_sha256",
        }
        report.check(
            set(maintainer) == expected_maintainer_keys,
            "committed.manifest.maintainer_evidence_fields",
            "maintainer_evidence fields are incomplete or contain extras",
        )
        for key in (
            "annotation_guide_sha256",
            "decision_schema_sha256",
            "packet_set_sha256",
            "queue_sha256",
        ):
            report.check(
                _is_sha256(maintainer.get(key)),
                f"committed.manifest.maintainer_hash.{key}",
                f"maintainer evidence {key} must be SHA-256",
            )
        for group in ("review_artifact_sha256", "preserved_raw_result_sha256"):
            values = maintainer.get(group)
            report.check(
                isinstance(values, dict) and bool(values),
                f"committed.manifest.maintainer_hash.{group}",
                f"maintainer evidence {group} must be a non-empty object",
            )
            if isinstance(values, dict):
                for key, value in values.items():
                    report.check(
                        _is_sha256(value),
                        f"committed.manifest.maintainer_hash.{group}.{key}",
                        f"maintainer evidence {group}.{key} must be SHA-256",
                    )

    report.check(
        freeze.get("evaluation_id") == EVALUATION_ID,
        "committed.freeze.evaluation_id",
        "freeze evaluation_id is wrong or missing",
    )
    report.check(
        freeze.get("evidence_grade") == EVIDENCE_GRADE,
        "committed.freeze.evidence_grade",
        "freeze evidence_grade is wrong or missing",
    )
    report.check(
        _is_rfc3339(freeze.get("frozen_at")),
        "committed.freeze.frozen_at",
        "freeze frozen_at must be an RFC 3339 date-time",
    )
    report.check(
        freeze.get("evidence_availability") == MAINTAINER_EVIDENCE_AVAILABILITY,
        "committed.freeze.evidence_boundary",
        "freeze must mark historical evidence as not repository-verifiable",
    )
    if isinstance(maintainer, dict):
        for freeze_key, manifest_key in (
            ("annotation_guide_sha256", "annotation_guide_sha256"),
            ("decision_schema_sha256", "decision_schema_sha256"),
            ("packet_set_sha256", "packet_set_sha256"),
            ("queue_sha256", "queue_sha256"),
        ):
            report.check(
                freeze.get(freeze_key) == maintainer.get(manifest_key),
                f"committed.freeze.{freeze_key}",
                f"freeze {freeze_key} differs from maintainer evidence record",
            )
        report.check(
            freeze.get("preserved_raw_result_sha256")
            == maintainer.get("preserved_raw_result_sha256"),
            "committed.freeze.raw_hashes",
            "freeze raw-result hashes differ from maintainer evidence record",
        )

    historical_guide_hash = (
        maintainer.get("annotation_guide_sha256") if isinstance(maintainer, dict) else None
    )
    for record in decisions:
        pair_id = str(record.get("pair_id", "<unknown>"))
        report.check(
            record.get("provenance", {}).get("annotation_guide_sha256") == historical_guide_hash,
            "committed.decisions.historical_guide_hash",
            f"{pair_id}: provenance guide hash differs from the recorded historical packet guide",
        )

    report.check(
        policy.get("evidence_grade") == EVIDENCE_GRADE,
        "committed.policy.evidence_grade",
        "policy evidence_grade is wrong or missing",
    )
    report.check(
        policy.get("schema") == "opensocrates.eval-adjudication-policy/1.0.0",
        "committed.policy.schema",
        "policy schema identifier is wrong",
    )
    report.check(
        policy.get("protocol_version") == PROTOCOL_VERSION,
        "committed.policy.protocol",
        "policy protocol_version is wrong",
    )
    report.check(
        _is_rfc3339(policy.get("locked_at")),
        "committed.policy.locked_at",
        "policy locked_at must be an RFC 3339 date-time",
    )
    report.check(
        policy.get("evaluation_id") == EVALUATION_ID,
        "committed.policy.evaluation_id",
        "policy evaluation_id is wrong or missing",
    )
    boundary_values = (
        str(policy.get("publication_boundary", "")),
        str(manifest.get("publication_boundary", "")),
        amendment_text or "",
        guide_text or "",
    )
    boundary = " ".join(boundary_values).casefold()
    for phrase in ("not confirmation-grade", "not held-out", "not answer-quality evidence"):
        report.check(
            phrase in boundary,
            f"committed.claim_boundary.{phrase.replace(' ', '_')}",
            f"public artifacts must state {phrase!r}",
        )

    gold_statuses: list[str] = []
    for value in (manifest, policy, decisions, disagreements):
        gold_statuses.extend(_status_paths_ending_gold(value))
    report.check(
        not gold_statuses,
        "committed.status.gold_suffix",
        f"machine status fields must not end in _gold: {gold_statuses}",
    )
    _check_public_text_boundaries(report, paths)
    return report


def _load_evidence_json(report: Report, path: Path, code: str) -> dict[str, Any] | None:
    if not report.check(
        path.is_file(), f"evidence.{code}.missing", f"required evidence absent: {path}"
    ):
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report.fail(f"evidence.{code}.invalid", f"{path}: invalid evidence JSON: {exc}")
        return None
    if not isinstance(value, dict):
        report.fail(f"evidence.{code}.type", f"{path}: expected a JSON object")
        return None
    return value


def _empty_decision_form(form: Any, path: str = "$") -> list[str]:
    failures: list[str] = []
    allowed_prefilled = {
        "$.schema",
        "$.protocol_version",
        "$.pair_id",
        "$.locales",
        "$.legacy",
        "$.blinding",
    }
    if not isinstance(form, dict):
        return [f"{path}: decision_form must be an object"]
    for key, value in form.items():
        child = f"{path}.{key}"
        if child in allowed_prefilled:
            continue
        if isinstance(value, dict):
            failures.extend(_empty_decision_form(value, child))
        elif isinstance(value, list):
            if value:
                failures.append(f"{child}: list is pre-filled")
        elif value not in (None, ""):
            failures.append(f"{child}: value is pre-filled")
    return failures


def validate_maintainer_evidence(paths: ArtifactPaths, manifest: dict[str, Any]) -> Report:  # noqa: C901
    report = Report()
    maintainer = manifest.get("maintainer_evidence", {})
    if not isinstance(maintainer, dict):
        report.fail("evidence.manifest.boundary", "manifest has no maintainer_evidence object")
        maintainer = {}

    packet_manifest = _load_evidence_json(report, paths.packet_manifest, "packet_manifest")
    review_hashes = maintainer.get("review_artifact_sha256", {})
    review_paths = {
        "primary": paths.review_root / "askpro-blind-adjudication.json",
        "secondary": paths.review_root / "askpro-second-blind-adjudication.json",
        "claude_partial": paths.review_root / "claude-opus5-blind-review.json",
        "comparison": paths.review_root / "reviewer-comparison.json",
    }
    for label, path in review_paths.items():
        exists = report.check(
            path.is_file(),
            f"evidence.review.{label}.missing",
            f"required reviewer evidence absent: {path}",
        )
        expected = review_hashes.get(label) if isinstance(review_hashes, dict) else None
        report.check(
            _is_sha256(expected),
            f"evidence.review.{label}.hash_format",
            f"manifest reviewer hash is invalid for {label}",
        )
        if exists and _is_sha256(expected):
            report.check(
                sha256_file(path) == expected,
                f"evidence.review.{label}.hash",
                f"{path}: reviewer artifact SHA-256 mismatch",
            )

    raw_hashes = maintainer.get("preserved_raw_result_sha256", {})
    if not isinstance(raw_hashes, dict):
        raw_hashes = {}
    for name, expected in raw_hashes.items():
        path = paths.evidence_root / name
        exists = report.check(
            path.is_file(),
            f"evidence.raw.{name}.missing",
            f"required raw-result evidence absent: {path}",
        )
        if exists:
            report.check(
                sha256_file(path) == expected,
                f"evidence.raw.{name}.hash",
                f"{path}: raw-result SHA-256 mismatch",
            )

    queue_exists = report.check(
        paths.queue.is_file(),
        "evidence.queue.missing",
        f"required historical queue absent: {paths.queue}",
    )
    if queue_exists:
        report.check(
            sha256_file(paths.queue) == maintainer.get("queue_sha256"),
            "evidence.queue.hash",
            "historical queue SHA-256 mismatch",
        )

    decisions_report = Report()
    decisions = load_jsonl(decisions_report, paths.decisions, "decisions")
    # The committed gate has already validated this file. Do not duplicate its
    # diagnostics, but use the records to link packets to decision provenance.
    indexed_decisions = {
        record["pair_id"]: record for record in decisions if isinstance(record.get("pair_id"), str)
    }
    packet_files = sorted(
        path for path in paths.packet_dir.glob("*.json") if path != paths.packet_manifest
    )
    report.check(
        len(packet_files) == EXPECTED_PAIR_COUNT,
        "evidence.packets.count",
        f"expected {EXPECTED_PAIR_COUNT} packet files, found {len(packet_files)}",
    )
    packet_hashes: dict[str, str] = {}
    for path in packet_files:
        packet = _load_evidence_json(report, path, f"packet.{path.stem}")
        if packet is None:
            continue
        pair_id = packet.get("pair_id")
        report.check(
            pair_id == path.stem,
            "evidence.packet.pair_id",
            f"{path.name}: pair_id/filename mismatch",
        )
        body = {key: value for key, value in packet.items() if key != "decision_form"}
        forbidden = find_forbidden_packet_keys(body)
        report.check(
            not forbidden,
            "evidence.packet.forbidden_key",
            f"{path.name}: forbidden packet keys {forbidden}",
        )
        prefilled = _empty_decision_form(packet.get("decision_form"))
        report.check(
            not prefilled,
            "evidence.packet.prefilled_form",
            f"{path.name}: {prefilled}",
        )
        if isinstance(pair_id, str):
            digest = hashlib.sha256(canonical_json(packet).encode("utf-8")).hexdigest()
            packet_hashes[pair_id] = digest
            decision = indexed_decisions.get(pair_id)
            if decision is not None:
                report.check(
                    decision.get("provenance", {}).get("blind_packet_sha256") == digest,
                    "evidence.packet.decision_hash",
                    f"{pair_id}: decision blind_packet_sha256 mismatch",
                )

    if packet_manifest is not None:
        expected_pairs = set(packet_manifest.get("pair_ids", []))
        report.check(
            expected_pairs == set(indexed_decisions) and len(expected_pairs) == EXPECTED_PAIR_COUNT,
            "evidence.packet_manifest.pairs",
            "packet manifest pair IDs do not match committed decisions",
        )
        report.check(
            packet_manifest.get("packet_sha256") == packet_hashes,
            "evidence.packet_manifest.packet_hashes",
            "packet file hashes do not match packet manifest",
        )
        report.check(
            sha256_object(packet_manifest.get("packet_sha256", {}))
            == packet_manifest.get("packet_set_sha256")
            == maintainer.get("packet_set_sha256"),
            "evidence.packet_manifest.packet_set",
            "packet-set hash does not match manifest records",
        )
        report.check(
            packet_manifest.get("annotation_guide_sha256")
            == maintainer.get("annotation_guide_sha256"),
            "evidence.packet_manifest.guide_hash",
            "historical packet guide hash mismatch",
        )
        report.check(
            packet_manifest.get("decision_schema_sha256")
            == maintainer.get("decision_schema_sha256"),
            "evidence.packet_manifest.schema_hash",
            "historical packet decision-schema hash mismatch",
        )
        report.check(
            packet_manifest.get("queue_sha256") == maintainer.get("queue_sha256"),
            "evidence.packet_manifest.queue_hash",
            "historical packet queue hash mismatch",
        )
        report.check(
            packet_manifest.get("preserved_raw_result_sha256") == raw_hashes,
            "evidence.packet_manifest.raw_hashes",
            "historical packet raw-result hashes differ from manifest",
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("committed", "maintainer-evidence"),
        default="committed",
        help="validation boundary (default: %(default)s)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="repository root (primarily for mutation tests)",
    )
    args = parser.parse_args(argv)
    paths = ArtifactPaths(args.root.resolve())

    committed = validate_committed(paths)
    status = committed.summary("committed", scope="tracked repository artifacts only")
    if args.mode == "maintainer-evidence":
        manifest = (
            json.loads(paths.manifest.read_text(encoding="utf-8"))
            if paths.manifest.is_file()
            else {}
        )
        evidence = validate_maintainer_evidence(paths, manifest)
        status |= evidence.summary(
            "maintainer-evidence",
            scope="unpublished packet, raw-result, queue, and reviewer files required",
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
