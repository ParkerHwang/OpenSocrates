#!/usr/bin/env python3
"""Compare two blind v1.2 adjudication reviews without changing either one.

The reviewer artifacts are intentionally kept under ``build/``.  This tool
normalizes only vocabulary and list ordering, verifies complete 51-pair
coverage, and writes a reproducible comparison artifact for the later
maintainer-authorized synthesis.  It never promotes a reviewer decision to
gold by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from json_schema_2020 import check_schema, validate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY = ROOT / "build/adjudication/v1.2/askpro-blind-adjudication.json"
DEFAULT_SECONDARY = ROOT / "build/adjudication/v1.2/askpro-second-blind-adjudication.json"
DEFAULT_OUTPUT = ROOT / "build/adjudication/v1.2/reviewer-comparison.json"
PACKET_MANIFEST = ROOT / "build/adjudication/v1.2/blind-packets/packet-manifest.json"
COMPARISON_SCHEMA = ROOT / "evals/v1.2/schemas/adjudication-review-comparison.schema.json"
EXPECTED_PAIR_COUNT = 51

BEHAVIOR_ALIASES = {
    "hold": "hold_no_intervention",
    "clarifier": "route_clarifier",
    "owner-then-hold": "route_owner_then_hold",
    "safe alternative": "route_safe_alternative",
    "bounded analysis": "bounded_analysis",
}
BEHAVIORS = {
    "hold_no_intervention",
    "route_clarifier",
    "route_owner_then_hold",
    "route_safe_alternative",
    "bounded_analysis",
}
STATUSES = {
    "retain",
    "relabel",
    "multi_valid",
    "rewrite",
    "exclude_from_policy_metric",
    "invalid",
}
INTERVENTION_POLICIES = {"prohibited", "optional", "required", "undetermined"}
LEGACY_KINDS = {"positive", "negative", "mechanical", "insufficiency", "explicit"}
LEGACY_ASSERTIONS = {"exact_route", "exclusion_only", "no_intervention"}
SIGNATURE_FIELDS = (
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
SET_FIELDS = {
    "allowed_behaviors",
    "acceptable_leading_methods",
    "acceptable_inclusion_methods",
    "prohibited_methods",
}
BOOLEAN_FIELDS = {
    "leading_metric_eligible",
    "inclusion_metric_eligible",
    "policy_metric_eligible",
}
COMPACT_RECORD_KEYS = frozenset({"pair_id", "legacy", "rationale", *SIGNATURE_FIELDS})
FULL_RECORD_KEYS = frozenset(
    {
        "schema",
        "protocol_version",
        "pair_id",
        "locales",
        "legacy",
        "semantic_review",
        "decision",
        "decisive_features",
        "rationale",
        "review",
        "blinding",
        "provenance",
    }
)
FULL_DECISION_KEYS = frozenset({*SIGNATURE_FIELDS, "case_kind"})
CLASSIFICATIONS = (
    "exact_agreement",
    "compatible_agreement",
    "substantive_disagreement",
)
EXPECTED_CLASSIFICATION_COUNTS = {
    "exact_agreement": 0,
    "compatible_agreement": 2,
    "substantive_disagreement": 49,
}


class ComparisonValidationError(ValueError):
    """The comparison is not the exact frozen two-review provenance artifact."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"{path}: review artifact does not exist")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("decisions"), list):
        raise SystemExit(f"{path}: expected an object with a decisions array")
    return value


def _require_exact_keys(value: dict[str, Any], expected: frozenset[str], label: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        raise ComparisonValidationError(f"{label}: missing={missing}, extra={extra}")


def _validate_legacy(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComparisonValidationError(f"{label}: legacy must be an object")
    _require_exact_keys(
        value,
        frozenset({"kind", "owner_method", "expected_route", "assertion"}),
        f"{label}.legacy",
    )
    kind = value["kind"]
    if not isinstance(kind, str):
        raise ComparisonValidationError(f"{label}.legacy.kind: must be a string")
    if kind not in LEGACY_KINDS:
        raise ComparisonValidationError(f"{label}.legacy.kind: invalid enum value")
    if not isinstance(value["owner_method"], str) or not value["owner_method"]:
        raise ComparisonValidationError(f"{label}.legacy.owner_method: non-empty string required")
    expected_route = value["expected_route"]
    if expected_route is not None and (not isinstance(expected_route, str) or not expected_route):
        raise ComparisonValidationError(
            f"{label}.legacy.expected_route: non-empty string or null required"
        )
    assertion = value["assertion"]
    if not isinstance(assertion, str):
        raise ComparisonValidationError(f"{label}.legacy.assertion: must be a string")
    if assertion not in LEGACY_ASSERTIONS:
        raise ComparisonValidationError(f"{label}.legacy.assertion: invalid enum value")
    return value


def _validate_string_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ComparisonValidationError(f"{label}: must be an array of strings")
    if any(not isinstance(item, str) or not item for item in value):
        raise ComparisonValidationError(f"{label}: every item must be a non-empty string")
    if len(value) != len(set(value)):
        raise ComparisonValidationError(f"{label}: duplicate items are forbidden")
    return value


def _validate_decision_source(  # noqa: C901 - every normalized scalar is checked explicitly
    source: dict[str, Any], legacy: dict[str, Any], label: str, *, nested: bool
) -> None:
    expected_keys = FULL_DECISION_KEYS if nested else frozenset(SIGNATURE_FIELDS)
    _require_exact_keys(source, expected_keys, label)

    status = source["status"]
    if not isinstance(status, str):
        raise ComparisonValidationError(f"{label}.status: must be a string")
    if status not in STATUSES:
        raise ComparisonValidationError(f"{label}.status: invalid enum value")
    intervention_policy = source["intervention_policy"]
    if not isinstance(intervention_policy, str):
        raise ComparisonValidationError(f"{label}.intervention_policy: must be a string")
    if intervention_policy not in INTERVENTION_POLICIES:
        raise ComparisonValidationError(f"{label}.intervention_policy: invalid enum value")
    if nested and source["case_kind"] != legacy["kind"]:
        raise ComparisonValidationError(f"{label}.case_kind: must equal legacy.kind")

    for field in SET_FIELDS:
        values = _validate_string_array(source[field], f"{label}.{field}")
        if field == "allowed_behaviors":
            normalized = [BEHAVIOR_ALIASES.get(item, item) for item in values]
            unknown = sorted(set(normalized) - BEHAVIORS)
            if unknown:
                raise ComparisonValidationError(
                    f"{label}.allowed_behaviors: unknown values {unknown}"
                )
            if len(normalized) != len(set(normalized)):
                raise ComparisonValidationError(
                    f"{label}.allowed_behaviors: aliases create duplicate normalized values"
                )

    leading_method = source["leading_method"]
    if leading_method is not None and (not isinstance(leading_method, str) or not leading_method):
        raise ComparisonValidationError(f"{label}.leading_method: string or null required")
    for field in BOOLEAN_FIELDS:
        if not isinstance(source[field], bool):
            raise ComparisonValidationError(f"{label}.{field}: boolean required")


def _validate_review_record(record: Any, review_label: str, index_value: int) -> None:
    label = f"{review_label}.decisions[{index_value}]"
    if not isinstance(record, dict):
        raise ComparisonValidationError(f"{label}: must be an object")
    nested = "decision" in record
    _require_exact_keys(
        record,
        FULL_RECORD_KEYS if nested else COMPACT_RECORD_KEYS,
        label,
    )
    pair_id = record["pair_id"]
    if not isinstance(pair_id, str) or not pair_id:
        raise ComparisonValidationError(f"{label}.pair_id: non-empty string required")
    legacy = _validate_legacy(record["legacy"], label)
    if not isinstance(record["rationale"], str) or not record["rationale"]:
        raise ComparisonValidationError(f"{label}.rationale: non-empty string required")
    if nested:
        if record["schema"] != "opensocrates.eval-adjudication-decision/1.0.0":
            raise ComparisonValidationError(f"{label}.schema: invalid enum value")
        if record["protocol_version"] != "1.2.0":
            raise ComparisonValidationError(f"{label}.protocol_version: invalid enum value")
        if record["locales"] != ["en", "ko"]:
            raise ComparisonValidationError(f"{label}.locales: must equal ['en', 'ko']")
        source = record["decision"]
        if not isinstance(source, dict):
            raise ComparisonValidationError(f"{label}.decision: must be an object")
    else:
        source = {field: record[field] for field in SIGNATURE_FIELDS}
    _validate_decision_source(source, legacy, f"{label}.decision", nested=nested)


def _validate_review_artifact(review: Any, label: str) -> dict[str, Any]:
    if not isinstance(review, dict):
        raise ComparisonValidationError(f"{label}: review artifact must be an object")
    decisions = review.get("decisions")
    if not isinstance(decisions, list):
        raise ComparisonValidationError(f"{label}: decisions must be an array")
    for index_value, record in enumerate(decisions):
        _validate_review_record(record, label, index_value)
    return review


def normalize_decision(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("decision", record)
    normalized: dict[str, Any] = {}
    for field in SIGNATURE_FIELDS:
        value = source[field]
        if field in SET_FIELDS:
            values = value
            if field == "allowed_behaviors":
                values = [BEHAVIOR_ALIASES.get(item, item) for item in values]
                unknown = sorted(set(values) - BEHAVIORS)
                if unknown:
                    raise ComparisonValidationError(
                        f"{record.get('pair_id')}: unknown behavior values {unknown}"
                    )
            value = sorted(values)
        normalized[field] = value
    return normalized


def index(review: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in review["decisions"]:
        pair_id = record["pair_id"]
        if pair_id in result:
            raise ComparisonValidationError(f"{label}: duplicate pair_id {pair_id}")
        result[pair_id] = record
    return result


def _differences(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        field: {"primary": primary[field], "secondary": secondary[field]}
        for field in SIGNATURE_FIELDS
        if primary[field] != secondary[field]
    }


def comparison_class(primary: dict[str, Any], secondary: dict[str, Any]) -> str:
    if primary == secondary:
        return "exact_agreement"
    same_policy = primary["intervention_policy"] == secondary["intervention_policy"]
    behaviors_overlap = bool(
        set(primary["allowed_behaviors"]) & set(secondary["allowed_behaviors"])
    )
    leader_sets = ({primary["leading_method"]} if primary["leading_method"] else set()) | set(
        primary["acceptable_leading_methods"]
    )
    other_leaders = ({secondary["leading_method"]} if secondary["leading_method"] else set()) | set(
        secondary["acceptable_leading_methods"]
    )
    leaders_compatible = (not leader_sets and not other_leaders) or bool(
        leader_sets & other_leaders
    )
    if same_policy and behaviors_overlap and leaders_compatible:
        return "compatible_agreement"
    return "substantive_disagreement"


def build_comparison_artifact(
    primary_review: dict[str, Any],
    secondary_review: dict[str, Any],
    packet_manifest: dict[str, Any],
    *,
    primary_sha256: str,
    secondary_sha256: str,
) -> dict[str, Any]:
    """Build the canonical comparison from two complete frozen review artifacts."""

    primary_review = _validate_review_artifact(primary_review, "primary")
    secondary_review = _validate_review_artifact(secondary_review, "secondary")

    pair_ids = packet_manifest.get("pair_ids")
    if not isinstance(pair_ids, list) or any(
        not isinstance(pair_id, str) or not pair_id for pair_id in pair_ids
    ):
        raise ComparisonValidationError("packet manifest pair_ids must be non-empty strings")
    if len(pair_ids) != EXPECTED_PAIR_COUNT or len(set(pair_ids)) != EXPECTED_PAIR_COUNT:
        raise ComparisonValidationError(
            f"packet manifest must name exactly {EXPECTED_PAIR_COUNT} unique pairs"
        )
    expected = set(pair_ids)
    primary = index(primary_review, "primary")
    secondary = index(secondary_review, "secondary")
    for label, records in (("primary", primary), ("secondary", secondary)):
        missing = sorted(expected - set(records))
        extra = sorted(set(records) - expected)
        if missing or extra:
            raise ComparisonValidationError(f"{label}: missing={missing}, extra={extra}")

    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for pair_id in sorted(expected):
        first_record = primary[pair_id]
        second_record = secondary[pair_id]
        if first_record.get("legacy") != second_record.get("legacy"):
            raise ComparisonValidationError(f"{pair_id}: primary/secondary legacy values differ")
        first = normalize_decision(first_record)
        second = normalize_decision(second_record)
        classification = comparison_class(first, second)
        counts[classification] += 1
        rows.append(
            {
                "pair_id": pair_id,
                "legacy": first_record.get("legacy"),
                "classification": classification,
                "differences": _differences(first, second),
                "primary": first,
                "secondary": second,
                "primary_rationale": first_record.get("rationale"),
                "secondary_rationale": second_record.get("rationale"),
            }
        )

    return {
        "schema": "opensocrates.eval-adjudication-review-comparison/1.0.0",
        "pair_count": len(rows),
        "classification_counts": {
            classification: counts[classification] for classification in CLASSIFICATIONS
        },
        "primary_sha256": primary_sha256,
        "secondary_sha256": secondary_sha256,
        "packet_set_sha256": packet_manifest.get("packet_set_sha256"),
        "normalization": {"behavior_aliases": BEHAVIOR_ALIASES, "list_order": "sorted"},
        "comparisons": rows,
    }


def validate_comparison_artifact(  # noqa: C901 - strict provenance checks stay linear
    comparison: dict[str, Any],
    comparison_schema: dict[str, Any],
    primary_review: dict[str, Any],
    secondary_review: dict[str, Any],
    packet_manifest: dict[str, Any],
    *,
    primary_sha256: str,
    secondary_sha256: str,
) -> dict[str, dict[str, Any]]:
    """Strictly validate schema, hashes, counts, coverage, and every derived row."""

    schema_issues = check_schema(comparison_schema)
    if schema_issues:
        raise ComparisonValidationError(
            "invalid comparison schema: " + "; ".join(str(issue) for issue in schema_issues)
        )
    issues = validate(comparison, comparison_schema)
    if issues:
        raise ComparisonValidationError(
            "comparison schema validation failed: " + "; ".join(str(issue) for issue in issues)
        )

    try:
        expected = build_comparison_artifact(
            primary_review,
            secondary_review,
            packet_manifest,
            primary_sha256=primary_sha256,
            secondary_sha256=secondary_sha256,
        )
    except ComparisonValidationError:
        raise
    except (KeyError, TypeError, ValueError, SystemExit) as exc:
        raise ComparisonValidationError(f"review provenance is malformed: {exc}") from exc
    errors: list[str] = []
    for field in (
        "schema",
        "pair_count",
        "primary_sha256",
        "secondary_sha256",
        "packet_set_sha256",
        "normalization",
    ):
        if comparison.get(field) != expected[field]:
            errors.append(f"{field} does not match frozen provenance")

    raw_counts = comparison.get("classification_counts")
    if not isinstance(raw_counts, dict) or set(raw_counts) != set(CLASSIFICATIONS):
        errors.append(
            "classification_counts must contain exactly exact_agreement, "
            "compatible_agreement, and substantive_disagreement"
        )
    if raw_counts != expected["classification_counts"]:
        errors.append("classification_counts do not match derived comparison rows")
    if raw_counts != EXPECTED_CLASSIFICATION_COUNTS:
        errors.append(
            "classification_counts must be exactly "
            f"{EXPECTED_CLASSIFICATION_COUNTS}, got {raw_counts}"
        )

    raw_rows = comparison.get("comparisons", [])
    expected_rows = expected["comparisons"]
    if raw_rows != expected_rows:
        if isinstance(raw_rows, list) and len(raw_rows) == len(expected_rows):
            for index_value, (actual, derived) in enumerate(
                zip(raw_rows, expected_rows, strict=True)
            ):
                if actual != derived:
                    pair_id = derived["pair_id"]
                    errors.append(f"comparisons[{index_value}] ({pair_id}) was tampered or stale")
                    break
        else:
            errors.append(f"comparisons must contain exactly {EXPECTED_PAIR_COUNT} derived rows")

    if errors:
        raise ComparisonValidationError("; ".join(errors))
    return {row["pair_id"]: row for row in raw_rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--packet-manifest", type=Path, default=PACKET_MANIFEST)
    parser.add_argument("--schema", type=Path, default=COMPARISON_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="explicitly authorize replacement of an existing comparison artifact",
    )
    args = parser.parse_args(argv)

    if not args.packet_manifest.is_file():
        raise SystemExit(f"{args.packet_manifest}: packet manifest does not exist")
    if not args.schema.is_file():
        raise SystemExit(f"{args.schema}: comparison schema does not exist")
    manifest = json.loads(args.packet_manifest.read_text(encoding="utf-8"))
    primary_review = load(args.primary)
    secondary_review = load(args.secondary)
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    try:
        result = build_comparison_artifact(
            primary_review,
            secondary_review,
            manifest,
            primary_sha256=sha256(args.primary),
            secondary_sha256=sha256(args.secondary),
        )
        validate_comparison_artifact(
            result,
            schema,
            primary_review,
            secondary_review,
            manifest,
            primary_sha256=sha256(args.primary),
            secondary_sha256=sha256(args.secondary),
        )
    except ComparisonValidationError as exc:
        raise SystemExit(f"invalid review provenance: {exc}") from None
    if args.output.is_symlink():
        raise SystemExit(f"refusing symlink output: {args.output}")
    if args.output.is_dir():
        raise SystemExit(f"comparison output is a directory: {args.output}")
    if args.output.exists() and not args.allow_overwrite:
        raise SystemExit(
            f"comparison output already exists: {args.output}; choose a new --output "
            "or pass --allow-overwrite explicitly"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{args.output.name}.", dir=args.output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"wrote {args.output}: {result['pair_count']} pairs {result['classification_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
