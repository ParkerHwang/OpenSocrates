#!/usr/bin/env python3
"""Build blind adjudication packets for the OpenSocrates v1.2 #65 label review.

The packets carry only what an independent adjudicator is allowed to see:
case text, legacy authored labels, authoring intent, method definitions, the
selector ordering contract, the adjudication questions, and an empty decision
form. No selector output, score, effort, or aggregate ever enters a packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

EVAL_ROOT = ROOT / "evals" / "v1.2"
QUEUE_PATH = EVAL_ROOT / "adjudication-queue.jsonl"
GUIDE_PATH = EVAL_ROOT / "ADJUDICATION_GUIDE.md"
DECISION_SCHEMA_PATH = EVAL_ROOT / "schemas" / "adjudication-decision.schema.json"
FREEZE_PATH = EVAL_ROOT / "adjudication-freeze-v1.0.0.json"

EVIDENCE_ROOT = ROOT / "build" / "evidence" / "v1.2"
DATASET_PATH = EVIDENCE_ROOT / "authored-dev-768.jsonl"
DATASET_MANIFEST_PATH = EVIDENCE_ROOT / "authored-dev-768.manifest.json"

# Historical raw results. Hashed for immutability proof only; never read for content.
RAW_RESULT_PATHS = (
    EVIDENCE_ROOT / "screening-results.jsonl",
    EVIDENCE_ROOT / "screening-max-unbounded-results.jsonl",
)

DEFAULT_PACKET_DIR = ROOT / "build" / "adjudication" / "v1.2" / "blind-packets"

METHOD_ROOT = ROOT / "content" / "methods"
DEFINITION_SECTIONS = ("Purpose", "Use when", "Do not use when", "Stop conditions")

PACKET_SCHEMA = "opensocrates.eval-adjudication-packet/1.0.0"
PACKET_MANIFEST_SCHEMA = "opensocrates.eval-adjudication-packet-manifest/1.0.0"
GUIDE_VERSION = "1.0.0"
PROTOCOL_VERSION = "1.2.0"

EXPECTED_PAIR_COUNT = 51
EXPECTED_INSTANCE_COUNT = 102

# Fields that would leak model behavior. Enforced structurally on every packet.
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
        "output",
        "model_output",
        "run_id",
        "status",
        "usage",
        "latency_ms",
    }
)

BOUNDARY_PAIR_IDS = (
    "decision-tree-analysis-mechanical-1",
    "lateral-thinking-negative-02",
    "design-thinking-positive-03",
    "socratic-questioning-insufficiency-01",
)

COMMON_QUESTIONS = (
    "Do the EN and KO texts convey the same situation, decision pressure, and"
    " missing information?",
    "Can this text, as written, support a single defensible gold policy?",
    "Is selector intervention prohibited, optional, required, or undetermined?",
    "Which behaviors are allowed (hold, clarifier, owner-then-hold, safe"
    " alternative, bounded analysis)?",
    "Is there exactly one leading method, several acceptable leaders, or none?",
    "Which methods, if any, are prohibited for this case and why?",
    "Is the pair eligible for the leading, inclusion, and policy metrics?",
    "Close as retain, relabel, multi_valid, rewrite, exclude_from_policy_metric,"
    " or invalid.",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:  # pragma: no cover - input guard
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return records


def parse_definition(method_id: str, locale: str) -> dict[str, str]:
    """Extract the public definition sections of a method procedure."""
    path = METHOD_ROOT / method_id / f"procedure.{locale}.md"
    if not path.exists():
        raise SystemExit(f"missing method procedure: {path}")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    out: dict[str, str] = {}
    for name in DEFINITION_SECTIONS:
        body = "\n".join(sections.get(name, [])).strip()
        if body:
            out[name] = body
    return out


def collect_pairs(dataset: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for case in dataset:
        pair_id = case["pair_id"]
        locale = case["locale"]
        bucket = pairs.setdefault(pair_id, {})
        if locale in bucket:
            raise SystemExit(f"duplicate locale {locale} for pair {pair_id}")
        bucket[locale] = case
    return pairs


def queue_scope(queue: list[dict[str, Any]]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Return the batch kinds and the per-pair queue items."""
    batch_kinds: list[str] = []
    pair_items: dict[str, dict[str, Any]] = {}
    for item in queue:
        scope = item.get("scope", {})
        if "kind" in scope:
            batch_kinds.append(scope["kind"])
        pair_id = item.get("pair_id") or scope.get("pair_id")
        if pair_id:
            pair_items[pair_id] = item
    return batch_kinds, pair_items


def build_inventory(
    dataset: list[dict[str, Any]],
    queue: list[dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    pairs = collect_pairs(dataset)
    batch_kinds, pair_items = queue_scope(queue)

    selected: list[str] = []
    for kind in batch_kinds:
        selected.extend(
            pair_id
            for pair_id, locales in pairs.items()
            if next(iter(locales.values()))["kind"] == kind
        )
    selected.extend(pair_items)

    # Deduplicate by pair_id; the socratic insufficiency pair is in both scopes.
    unique = sorted(dict.fromkeys(selected))

    missing = [pair_id for pair_id in unique if pair_id not in pairs]
    if missing:
        raise SystemExit(f"queue references unknown pairs: {missing}")

    return unique, pairs, pair_items


def candidate_methods(item: dict[str, Any] | None, owner: str) -> list[str]:
    """Method ids worth showing definitions for, beyond the owner method."""
    known = {path.name for path in METHOD_ROOT.iterdir() if path.is_dir()}
    found: list[str] = []
    for resolution in (item or {}).get("candidate_resolutions", []):
        for method_id in sorted(known, key=len, reverse=True):
            if method_id in resolution and method_id not in found and method_id != owner:
                found.append(method_id)
    # Clarification candidates are decision-relevant for every insufficiency pair.
    for clarifier in ("socratic-questioning", "conceptual-analysis"):
        if clarifier != owner and clarifier not in found:
            found.append(clarifier)
    return found


def empty_decision_form(pair_id: str, legacy: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "opensocrates.eval-adjudication-decision/1.0.0",
        "protocol_version": PROTOCOL_VERSION,
        "pair_id": pair_id,
        "locales": ["en", "ko"],
        "legacy": legacy,
        "semantic_review": {
            "en_ko_equivalent": None,
            "translation_mismatch": None,
            "notes": [],
        },
        "decision": {
            "status": None,
            "case_kind": None,
            "intervention_policy": None,
            "allowed_behaviors": [],
            "leading_method": None,
            "acceptable_leading_methods": [],
            "acceptable_inclusion_methods": [],
            "prohibited_methods": [],
            "leading_metric_eligible": None,
            "inclusion_metric_eligible": None,
            "policy_metric_eligible": None,
        },
        "decisive_features": [],
        "rationale": "",
        "review": {
            "author_or_intent_witness": None,
            "primary_adjudicator": None,
            "second_reviewer": None,
            "primary_decision_locked_at": None,
            "second_decision_locked_at": None,
            "agreement": None,
            "resolution_reviewer": None,
            "dissent": None,
        },
        "blinding": {
            "model_outputs_seen_by_primary": False,
            "aggregate_results_seen_by_primary": False,
            "model_outputs_seen_by_second": False,
            "aggregate_results_seen_by_second": False,
            "attestation": "",
        },
        "provenance": {
            "source_case_sha256": {"en": None, "ko": None},
            "annotation_guide_sha256": None,
            "blind_packet_sha256": None,
            "decision_created_at": None,
        },
    }


def assert_no_forbidden_keys(node: Any, path: str = "$") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_PACKET_KEYS:
                raise SystemExit(f"blinding violation: forbidden key {path}.{key}")
            assert_no_forbidden_keys(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            assert_no_forbidden_keys(value, f"{path}[{index}]")


def assert_empty_decision_form(form: dict[str, Any], path: str = "$") -> None:
    """A packet's decision form must carry no pre-filled adjudicator answer."""
    prefilled_ok = {
        "$.schema",
        "$.protocol_version",
        "$.pair_id",
        "$.locales",
        "$.legacy",
        "$.blinding",
    }
    for key, value in form.items():
        node = f"{path}.{key}"
        if node in prefilled_ok:
            continue
        if isinstance(value, dict):
            assert_empty_decision_form(value, node)
        elif isinstance(value, list):
            if value:
                raise SystemExit(f"decision form must start empty: {node}")
        elif value not in (None, ""):
            raise SystemExit(f"decision form must start empty: {node} = {value!r}")


def build_packet(
    pair_id: str,
    locales: dict[str, dict[str, Any]],
    queue_item: dict[str, Any] | None,
    guide_sha: str,
) -> dict[str, Any]:
    en = locales["en"]
    ko = locales["ko"]
    owner = en["owner_method_id"]
    expected = en["expected"]

    legacy = {
        "kind": en["kind"],
        "owner_method": owner,
        "expected_route": expected.get("expected_route"),
        "assertion": expected.get("type"),
    }

    method_ids = [owner, *candidate_methods(queue_item, owner)]
    definitions = {
        method_id: {
            "en": parse_definition(method_id, "en"),
            "ko": parse_definition(method_id, "ko"),
        }
        for method_id in method_ids
    }

    questions = list(COMMON_QUESTIONS)
    if queue_item is not None:
        questions.insert(0, queue_item["issue"])

    packet_body = {
        "schema": PACKET_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "guide_version": GUIDE_VERSION,
        "annotation_guide_sha256": guide_sha,
        "pair_id": pair_id,
        "locales": ["en", "ko"],
        "case_text": {"en": en["prompt"], "ko": ko["prompt"]},
        "authoring_intent": {"en": en["rationale"], "ko": ko["rationale"]},
        "authored_decisive_features": sorted(
            set(en["decisive_features"]) | set(ko["decisive_features"])
        ),
        "legacy": legacy,
        "legacy_action": "preserve_do_not_relabel",
        "method_definitions": definitions,
        "selector_ordering_contract": (
            "selected_reasoning_systems[0] is the leading method for the user's"
            " main judgment; complementary methods follow in application order."
        ),
        "adjudication_questions": questions,
        "candidate_resolutions": (queue_item or {}).get("candidate_resolutions", []),
        "source_case_sha256": {
            "en": sha256_obj(en),
            "ko": sha256_obj(ko),
        },
    }
    # The forbidden-key scan covers everything an adjudicator reads. The decision
    # form is excluded because its own field names (status, ...) are adjudicator
    # outputs, not model results; it is verified separately to be all-empty.
    assert_no_forbidden_keys(packet_body)
    form = empty_decision_form(pair_id, legacy)
    assert_empty_decision_form(form)
    return {**packet_body, "decision_form": form}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet-dir",
        type=Path,
        default=DEFAULT_PACKET_DIR,
        help="output directory for blind packets (default: %(default)s)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="normalized development dataset (default: %(default)s)",
    )
    parser.add_argument(
        "--write-freeze",
        action="store_true",
        help="write the guide/packet freeze record into evals/v1.2/",
    )
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        raise SystemExit(
            f"dataset not found: {args.dataset}\n"
            "run: PYTHONPATH=src python3 tools/v12_eval.py build-dataset"
        )

    guide_sha = sha256_file(GUIDE_PATH)
    dataset = read_jsonl(args.dataset)
    queue = read_jsonl(QUEUE_PATH)

    pair_ids, pairs, pair_items = build_inventory(dataset, queue)

    if len(pair_ids) != EXPECTED_PAIR_COUNT:
        raise SystemExit(
            f"expected {EXPECTED_PAIR_COUNT} unique pairs, found {len(pair_ids)}"
        )

    locale_instances = 0
    for pair_id in pair_ids:
        locales = pairs[pair_id]
        if set(locales) != {"en", "ko"}:
            raise SystemExit(f"pair {pair_id} has locales {sorted(locales)}, expected en+ko")
        locale_instances += len(locales)
    if locale_instances != EXPECTED_INSTANCE_COUNT:
        raise SystemExit(
            f"expected {EXPECTED_INSTANCE_COUNT} locale instances, found {locale_instances}"
        )

    args.packet_dir.mkdir(parents=True, exist_ok=True)
    for stale in args.packet_dir.glob("*.json"):
        stale.unlink()

    packet_hashes: dict[str, str] = {}
    kind_counts: Counter[str] = Counter()
    for pair_id in pair_ids:
        packet = build_packet(pair_id, pairs[pair_id], pair_items.get(pair_id), guide_sha)
        payload = canonical_json(packet).encode("utf-8")
        packet_hashes[pair_id] = sha256_bytes(payload)
        kind_counts[packet["legacy"]["kind"]] += 1
        (args.packet_dir / f"{pair_id}.json").write_bytes(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            + b"\n"
        )

    dataset_manifest_sha = (
        sha256_file(DATASET_MANIFEST_PATH) if DATASET_MANIFEST_PATH.exists() else None
    )
    raw_result_hashes = {
        path.name: (sha256_file(path) if path.exists() else None) for path in RAW_RESULT_PATHS
    }

    manifest = {
        "schema": PACKET_MANIFEST_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "guide_version": GUIDE_VERSION,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generation_command": "python3 tools/build_v12_adjudication_packets.py",
        "queue_item_count": len(queue),
        "unique_pair_count": len(pair_ids),
        "locale_instance_count": locale_instances,
        "pair_ids": pair_ids,
        "boundary_pair_ids": list(BOUNDARY_PAIR_IDS),
        "counts_by_legacy_kind": dict(sorted(kind_counts.items())),
        "annotation_guide_sha256": guide_sha,
        "decision_schema_sha256": sha256_file(DECISION_SCHEMA_PATH),
        "queue_sha256": sha256_file(QUEUE_PATH),
        "dataset_sha256": sha256_file(args.dataset),
        "dataset_manifest_sha256": dataset_manifest_sha,
        "packet_sha256": packet_hashes,
        "packet_set_sha256": sha256_obj(packet_hashes),
        "preserved_raw_result_sha256": raw_result_hashes,
        "blinding_note": (
            "Packets contain no selector output, selected method, pass/fail, effort,"
            " or aggregate field. Raw result hashes are recorded for immutability"
            " proof only; their contents are not read into packets."
        ),
    }

    manifest_path = args.packet_dir / "packet-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.write_freeze:
        freeze = {
            "schema": "opensocrates.eval-adjudication-freeze/1.0.0",
            "protocol_version": PROTOCOL_VERSION,
            "guide_version": GUIDE_VERSION,
            "frozen_at": manifest["generated_at"],
            "annotation_guide_sha256": guide_sha,
            "decision_schema_sha256": manifest["decision_schema_sha256"],
            "queue_sha256": manifest["queue_sha256"],
            "packet_set_sha256": manifest["packet_set_sha256"],
            "unique_pair_count": len(pair_ids),
            "locale_instance_count": locale_instances,
            "preserved_raw_result_sha256": raw_result_hashes,
            "note": (
                "The annotation guide and blind packets are frozen before any"
                " pair-level decision is locked. Model outputs stay closed until"
                " every decision and the manifest are written."
            ),
        }
        FREEZE_PATH.write_text(
            json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(f"pairs: {len(pair_ids)}  instances: {locale_instances}")
    print(f"legacy kinds: {dict(sorted(kind_counts.items()))}")
    print(f"guide sha256: {guide_sha}")
    print(f"packet set sha256: {manifest['packet_set_sha256']}")
    print(f"packets: {args.packet_dir}")
    if args.write_freeze:
        print(f"freeze: {FREEZE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
