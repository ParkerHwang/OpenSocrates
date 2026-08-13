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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY = ROOT / "build/adjudication/v1.2/askpro-blind-adjudication.json"
DEFAULT_SECONDARY = ROOT / "build/adjudication/v1.2/askpro-second-blind-adjudication.json"
DEFAULT_OUTPUT = ROOT / "build/adjudication/v1.2/reviewer-comparison.json"
PACKET_MANIFEST = ROOT / "build/adjudication/v1.2/blind-packets/packet-manifest.json"

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--packet-manifest", type=Path, default=PACKET_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="explicitly authorize replacement of an existing comparison artifact",
    )
    args = parser.parse_args()

    if not args.packet_manifest.is_file():
        raise SystemExit(f"{args.packet_manifest}: packet manifest does not exist")
    manifest = json.loads(args.packet_manifest.read_text(encoding="utf-8"))
    expected = set(manifest["pair_ids"])
    primary_review = load(args.primary)
    secondary_review = load(args.secondary)
    primary = index(primary_review, "primary")
    secondary = index(secondary_review, "secondary")
    for label, records in (("primary", primary), ("secondary", secondary)):
        missing = sorted(expected - set(records))
        extra = sorted(set(records) - expected)
        if missing or extra:
            raise SystemExit(f"{label}: missing={missing}, extra={extra}")

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for pair_id in sorted(expected):
        first = normalize_decision(primary[pair_id])
        second = normalize_decision(secondary[pair_id])
        classification = comparison_class(first, second)
        counts[classification] = counts.get(classification, 0) + 1
        differences = {
            field: {"primary": first[field], "secondary": second[field]}
            for field in SIGNATURE_FIELDS
            if first[field] != second[field]
        }
        rows.append(
            {
                "pair_id": pair_id,
                "legacy": primary[pair_id].get("legacy"),
                "classification": classification,
                "differences": differences,
                "primary": first,
                "secondary": second,
                "primary_rationale": primary[pair_id].get("rationale"),
                "secondary_rationale": secondary[pair_id].get("rationale"),
            }
        )

    result = {
        "schema": "opensocrates.eval-adjudication-review-comparison/1.0.0",
        "pair_count": len(rows),
        "classification_counts": counts,
        "primary_sha256": sha256(args.primary),
        "secondary_sha256": sha256(args.secondary),
        "packet_set_sha256": manifest["packet_set_sha256"],
        "normalization": {"behavior_aliases": BEHAVIOR_ALIASES, "list_order": "sorted"},
        "comparisons": rows,
    }
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
    print(f"wrote {args.output}: {len(rows)} pairs {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
