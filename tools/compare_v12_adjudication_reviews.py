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


def normalize_decision(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("decision", record)
    normalized: dict[str, Any] = {}
    missing: list[str] = []
    for field in SIGNATURE_FIELDS:
        if field not in source:
            missing.append(field)
            continue
        value = source[field]
        if field in SET_FIELDS:
            values = value if isinstance(value, list) else []
            if field == "allowed_behaviors":
                values = [BEHAVIOR_ALIASES.get(item, item) for item in values]
                unknown = sorted(set(values) - BEHAVIORS)
                if unknown:
                    raise SystemExit(f"{record.get('pair_id')}: unknown behavior values {unknown}")
            value = sorted(set(values))
        normalized[field] = value
    if missing:
        raise SystemExit(f"{record.get('pair_id')}: missing decision fields {missing}")
    return normalized


def index(review: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in review["decisions"]:
        pair_id = record.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise SystemExit(f"{label}: decision missing pair_id")
        if pair_id in result:
            raise SystemExit(f"{label}: duplicate pair_id {pair_id}")
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

    raw_counts = comparison.get("classification_counts", {})
    normalized_counts = (
        {classification: raw_counts.get(classification, 0) for classification in CLASSIFICATIONS}
        if isinstance(raw_counts, dict)
        else {}
    )
    if normalized_counts != expected["classification_counts"]:
        errors.append("classification_counts do not match derived comparison rows")
    if normalized_counts != EXPECTED_CLASSIFICATION_COUNTS:
        errors.append(
            "classification_counts must be exactly "
            f"{EXPECTED_CLASSIFICATION_COUNTS}, got {normalized_counts}"
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
    result = build_comparison_artifact(
        primary_review,
        secondary_review,
        manifest,
        primary_sha256=sha256(args.primary),
        secondary_sha256=sha256(args.secondary),
    )
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validate_comparison_artifact(
        result,
        schema,
        primary_review,
        secondary_review,
        manifest,
        primary_sha256=sha256(args.primary),
        secondary_sha256=sha256(args.secondary),
    )
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
