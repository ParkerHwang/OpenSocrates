#!/usr/bin/env python3
"""Focused mutation and regression tests for the v1.2 adjudication gate."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

from build_v12_adjudication_packets import _publish_directory as publish_packet_directory
from compare_v12_adjudication_reviews import (
    ComparisonValidationError,
    build_comparison_artifact,
    comparison_class,
    validate_comparison_artifact,
)
from compare_v12_adjudication_reviews import (
    main as compare_main,
)
from finalize_v12_ai_adjudication import (
    _final_semantic_review,
    _semantic_review_schema,
    _uncertainty_index,
)
from finalize_v12_ai_adjudication import (
    _publish_directory as publish_final_directory,
)
from json_schema_2020 import DRAFT_2020_12, check_schema, validate
from v12_adjudication_contract import FORBIDDEN_PACKET_KEYS, find_forbidden_packet_keys

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check_v12_adjudication.py"
COMPARISON_TOOL = ROOT / "tools" / "compare_v12_adjudication_reviews.py"
EVAL_RELATIVE = Path("evals/v1.2")
REPORT_RELATIVE = Path("docs/v1.2-adjudication-report.md")
RELEASE_NOTES_RELATIVE = Path(".github/release-notes/v1.2.1.md")
COMPARISON_SCHEMA_RELATIVE = EVAL_RELATIVE / "schemas/adjudication-review-comparison.schema.json"
PUBLICATION_LOCK_RELATIVE = EVAL_RELATIVE / "adjudication-publication-lock-v1.0.0.json"
HASH_PATHS = {
    "annotation_guide": EVAL_RELATIVE / "ADJUDICATION_GUIDE.md",
    "ai_amendment": EVAL_RELATIVE / "ADJUDICATION_AI_AMENDMENT.md",
    "policy": EVAL_RELATIVE / "adjudication-policy-v1.0.0.json",
    "decisions": EVAL_RELATIVE / "adjudication-decisions-v1.0.0.jsonl",
    "disagreements": EVAL_RELATIVE / "adjudication-disagreements-v1.0.0.jsonl",
    "decision_schema": EVAL_RELATIVE / "schemas/adjudication-decision.schema.json",
    "disagreement_schema": EVAL_RELATIVE / "schemas/adjudication-disagreement.schema.json",
    "comparison_schema": COMPARISON_SCHEMA_RELATIVE,
    "freeze": EVAL_RELATIVE / "adjudication-freeze-v1.0.0.json",
    "report": REPORT_RELATIVE,
    "release_notes": RELEASE_NOTES_RELATIVE,
}


def _fixture(parent: Path, name: str) -> Path:
    target = parent / name
    shutil.copytree(ROOT / EVAL_RELATIVE, target / EVAL_RELATIVE)
    report = target / REPORT_RELATIVE
    report.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / REPORT_RELATIVE, report)
    release_notes = target / RELEASE_NOTES_RELATIVE
    release_notes.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / RELEASE_NOTES_RELATIVE, release_notes)
    method_root = target / "content/methods"
    method_root.mkdir(parents=True)
    for source in (ROOT / "content/methods").iterdir():
        if source.is_dir():
            (method_root / source.name).mkdir()
    return target


def _run(root: Path, *, mode: str = "committed") -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), "--mode", mode],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=30,
    )
    return result.returncode, result.stdout


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _with_rehashed_manifest(
    mutate: Callable[[Path], None], *hash_fields: str
) -> Callable[[Path], None]:
    """Apply a coherent artifact mutation and refresh every named manifest hash."""

    def wrapped(root: Path) -> None:
        mutate(root)
        manifest_path = root / EVAL_RELATIVE / "adjudication-manifest-v1.0.0.json"
        manifest = _json(manifest_path)
        for field in hash_fields:
            manifest["committed_artifact_sha256"][field] = _sha256(root / HASH_PATHS[field])
        _write_json(manifest_path, manifest)

    return wrapped


def _with_rehashed_manifest_and_publication_lock(
    mutate: Callable[[Path], None], *hash_fields: str
) -> Callable[[Path], None]:
    """Rehash the manifest and lock while leaving the checker trust root unchanged."""

    rehash_manifest = _with_rehashed_manifest(mutate, *hash_fields)

    def wrapped(root: Path) -> None:
        rehash_manifest(root)
        lock_path = root / PUBLICATION_LOCK_RELATIVE
        lock = _json(lock_path)
        for field in hash_fields:
            lock["artifacts"][field]["sha256"] = _sha256(root / HASH_PATHS[field])
        manifest_path = root / EVAL_RELATIVE / "adjudication-manifest-v1.0.0.json"
        lock["artifacts"]["manifest"]["sha256"] = _sha256(manifest_path)
        _write_json(lock_path, lock)

    return wrapped


def _mutate_json(
    relative: Path, callback: Callable[[dict[str, Any]], None]
) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        path = root / relative
        value = _json(path)
        callback(value)
        _write_json(path, value)

    return mutate


def _mutate_jsonl(
    relative: Path,
    callback: Callable[[list[dict[str, Any]]], None],
) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        path = root / relative
        rows = _jsonl(path)
        callback(rows)
        _write_jsonl(path, rows)

    return mutate


def _append_text(relative: Path, text: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        path = root / relative
        path.write_text(
            path.read_text(encoding="utf-8") + "\n" + text + "\n",
            encoding="utf-8",
        )

    return mutate


def _replace_text(relative: Path, old: str, new: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        path = root / relative
        original = path.read_text(encoding="utf-8")
        if original.count(old) != 1:
            raise AssertionError(f"{relative}: expected one exact source context")
        path.write_text(original.replace(old, new, 1), encoding="utf-8")

    return mutate


def _signature(*, leader: str | None, alternatives: list[str], status: str) -> dict[str, Any]:
    return {
        "status": status,
        "intervention_policy": "required",
        "allowed_behaviors": ["bounded_analysis"],
        "leading_method": leader,
        "acceptable_leading_methods": alternatives,
        "acceptable_inclusion_methods": [],
        "prohibited_methods": [],
        "leading_metric_eligible": leader is not None,
        "inclusion_metric_eligible": False,
        "policy_metric_eligible": True,
    }


def _full_review_artifact(review: dict[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for compact in review["decisions"]:
        decision = {
            field: deepcopy(compact[field])
            for field in _signature(leader=None, alternatives=[], status="retain")
        }
        decision["case_kind"] = compact["legacy"]["kind"]
        records.append(
            {
                "schema": "opensocrates.eval-adjudication-decision/1.0.0",
                "protocol_version": "1.2.0",
                "pair_id": compact["pair_id"],
                "locales": ["en", "ko"],
                "legacy": deepcopy(compact["legacy"]),
                "semantic_review": {
                    "en_ko_equivalent": True,
                    "translation_mismatch": False,
                    "notes": [],
                },
                "decision": decision,
                "decisive_features": ["synthetic"],
                "rationale": compact["rationale"],
                "review": {},
                "blinding": {},
                "provenance": {},
            }
        )
    return {"decisions": records}


def _expect_reviewer_rejection(
    *,
    label: str,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    packet_manifest: dict[str, Any],
    comparison: dict[str, Any],
    schema: dict[str, Any],
    primary_sha256: str,
    secondary_sha256: str,
    expected_error: str,
    failures: list[str],
) -> None:
    for operation in ("build", "validate"):
        try:
            if operation == "build":
                build_comparison_artifact(
                    primary,
                    secondary,
                    packet_manifest,
                    primary_sha256=primary_sha256,
                    secondary_sha256=secondary_sha256,
                )
            else:
                validate_comparison_artifact(
                    comparison,
                    schema,
                    primary,
                    secondary,
                    packet_manifest,
                    primary_sha256=primary_sha256,
                    secondary_sha256=secondary_sha256,
                )
        except ComparisonValidationError as exc:
            if expected_error not in str(exc):
                failures.append(
                    f"comparison validation: {label} {operation} returned unexpected "
                    f"error {str(exc)!r}"
                )
        else:
            failures.append(f"comparison validation: {label} was accepted by {operation}")


def _malformed_enum_regressions(  # noqa: C901 - matrix covers each provenance surface
    fixture: Path,
    primary: dict[str, Any],
    secondary: dict[str, Any],
    packet_manifest: dict[str, Any],
    packet_path: Path,
    schema: dict[str, Any],
    schema_path: Path,
    failures: list[str],
) -> None:
    """Reject list/object enum scalars for primary/secondary compact/full reviews."""

    formats = {
        "compact": (primary, secondary),
        "full": (_full_review_artifact(primary), _full_review_artifact(secondary)),
    }
    fields = {
        "status": ("decision", "status"),
        "intervention_policy": ("decision", "intervention_policy"),
        "legacy.kind": ("legacy", "kind"),
        "legacy.assertion": ("legacy", "assertion"),
    }
    for format_name, (valid_primary, valid_secondary) in formats.items():
        valid_primary_path = fixture / f"enum-{format_name}-primary-valid.json"
        valid_secondary_path = fixture / f"enum-{format_name}-secondary-valid.json"
        _write_json(valid_primary_path, valid_primary)
        _write_json(valid_secondary_path, valid_secondary)
        valid_primary_hash = _sha256(valid_primary_path)
        valid_secondary_hash = _sha256(valid_secondary_path)
        baseline_comparison = build_comparison_artifact(
            valid_primary,
            valid_secondary,
            packet_manifest,
            primary_sha256=valid_primary_hash,
            secondary_sha256=valid_secondary_hash,
        )

        for side in ("primary", "secondary"):
            for field_name, (container_name, key) in fields.items():
                for shape_name, malformed_value in (("list", []), ("object", {})):
                    candidate_primary = deepcopy(valid_primary)
                    candidate_secondary = deepcopy(valid_secondary)
                    candidate = candidate_primary if side == "primary" else candidate_secondary
                    record = candidate["decisions"][0]
                    if container_name == "legacy":
                        record["legacy"][key] = malformed_value
                    elif format_name == "full":
                        record["decision"][key] = malformed_value
                    else:
                        record[key] = malformed_value

                    slug = f"{format_name}-{side}-{field_name.replace('.', '-')}-{shape_name}"
                    primary_path = fixture / f"enum-{slug}-primary.json"
                    secondary_path = fixture / f"enum-{slug}-secondary.json"
                    output_path = fixture / f"enum-{slug}-comparison.json"
                    _write_json(primary_path, candidate_primary)
                    _write_json(secondary_path, candidate_secondary)
                    primary_hash = _sha256(primary_path)
                    secondary_hash = _sha256(secondary_path)
                    expected_error = f"{field_name}: must be a string"

                    _expect_reviewer_rejection(
                        label=f"malformed enum {slug}",
                        primary=candidate_primary,
                        secondary=candidate_secondary,
                        packet_manifest=packet_manifest,
                        comparison=baseline_comparison,
                        schema=schema,
                        primary_sha256=primary_hash,
                        secondary_sha256=secondary_hash,
                        expected_error=expected_error,
                        failures=failures,
                    )

                    process = subprocess.run(
                        [
                            sys.executable,
                            str(COMPARISON_TOOL),
                            "--primary",
                            str(primary_path),
                            "--secondary",
                            str(secondary_path),
                            "--packet-manifest",
                            str(packet_path),
                            "--schema",
                            str(schema_path),
                            "--output",
                            str(output_path),
                        ],
                        cwd=ROOT,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        check=False,
                        timeout=10,
                    )
                    if (
                        process.returncode == 0
                        or expected_error not in process.stdout
                        or "Traceback" in process.stdout
                        or output_path.exists()
                    ):
                        failures.append(
                            f"comparison CLI malformed enum {slug}: expected controlled "
                            f"nonzero with {expected_error!r}; code={process.returncode} "
                            f"output={process.stdout[:500]!r}"
                        )


def _contract_regressions(failures: list[str]) -> None:
    if not {"output", "status"} <= FORBIDDEN_PACKET_KEYS:
        failures.append("packet-contract: output/status missing")
    hits = find_forbidden_packet_keys({"nested": {"output": "secret", "status": "pass"}})
    if hits != ["$.nested.output", "$.nested.status"]:
        failures.append(f"packet-contract: unexpected hits {hits}")

    empty_a = _signature(leader=None, alternatives=[], status="retain")
    empty_b = _signature(leader=None, alternatives=[], status="relabel")
    if comparison_class(empty_a, empty_b) != "compatible_agreement":
        failures.append("comparison: both-empty leaders must be compatible")

    one_empty = _signature(leader=None, alternatives=[], status="retain")
    one_named = _signature(leader="deduction", alternatives=["deduction"], status="relabel")
    if comparison_class(one_empty, one_named) != "substantive_disagreement":
        failures.append("comparison: empty vs non-empty leaders must disagree")

    overlap_a = _signature(leader="deduction", alternatives=["deduction"], status="retain")
    overlap_b = _signature(
        leader="critical-thinking",
        alternatives=["critical-thinking", "deduction"],
        status="relabel",
    )
    if comparison_class(overlap_a, overlap_b) != "compatible_agreement":
        failures.append("comparison: non-empty intersection must be compatible")

    disjoint = _signature(leader="abduction", alternatives=["abduction"], status="relabel")
    if comparison_class(overlap_a, disjoint) != "substantive_disagreement":
        failures.append("comparison: disjoint leader sets must disagree")


def _comparison_regressions(parent: Path, failures: list[str]) -> None:  # noqa: C901
    """Exercise the complete comparison generation path with synthetic private inputs."""

    fixture = parent / "synthetic-comparison"
    fixture.mkdir()
    pair_ids = [f"synthetic-pair-{index:02d}" for index in range(51)]
    primary_rows: list[dict[str, Any]] = []
    secondary_rows: list[dict[str, Any]] = []
    legacy = {
        "kind": "insufficiency",
        "owner_method": "deduction",
        "expected_route": "deduction",
        "assertion": "exact_route",
    }
    for index, pair_id in enumerate(pair_ids):
        primary_rows.append(
            {
                "pair_id": pair_id,
                "legacy": deepcopy(legacy),
                "rationale": f"Synthetic primary rationale {index}.",
                **_signature(leader="deduction", alternatives=["deduction"], status="retain"),
            }
        )
        secondary_rows.append(
            {
                "pair_id": pair_id,
                "legacy": deepcopy(legacy),
                "rationale": f"Synthetic secondary rationale {index}.",
                **_signature(
                    leader="deduction" if index < 2 else "abduction",
                    alternatives=["deduction" if index < 2 else "abduction"],
                    status="relabel",
                ),
            }
        )
    primary = {"decisions": primary_rows}
    secondary = {"decisions": secondary_rows}
    packet_manifest = {"pair_ids": pair_ids, "packet_set_sha256": "a" * 64}
    primary_path = fixture / "primary.json"
    secondary_path = fixture / "secondary.json"
    packet_path = fixture / "packet-manifest.json"
    output_path = fixture / "comparison.json"
    _write_json(primary_path, primary)
    _write_json(secondary_path, secondary)
    _write_json(packet_path, packet_manifest)
    schema_path = ROOT / COMPARISON_SCHEMA_RELATIVE
    try:
        code = compare_main(
            [
                "--primary",
                str(primary_path),
                "--secondary",
                str(secondary_path),
                "--packet-manifest",
                str(packet_path),
                "--schema",
                str(schema_path),
                "--output",
                str(output_path),
            ]
        )
    except (ComparisonValidationError, SystemExit, KeyError, TypeError, ValueError) as exc:
        failures.append(f"comparison generation: synthetic path failed: {exc}")
        return
    if code != 0 or not output_path.is_file():
        failures.append("comparison generation: synthetic path did not publish an artifact")
        return

    comparison = _json(output_path)
    schema = _json(schema_path)
    try:
        rows = validate_comparison_artifact(
            comparison,
            schema,
            primary,
            secondary,
            packet_manifest,
            primary_sha256=_sha256(primary_path),
            secondary_sha256=_sha256(secondary_path),
        )
    except ComparisonValidationError as exc:
        failures.append(f"comparison validation: generated synthetic artifact failed: {exc}")
        return
    if len(rows) != 51 or comparison["classification_counts"] != {
        "exact_agreement": 0,
        "compatible_agreement": 2,
        "substantive_disagreement": 49,
    }:
        failures.append("comparison validation: synthetic artifact counts are not 0/2/49")

    invalid: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    empty = {}
    invalid.append(("empty", empty, primary, packet_manifest))
    malformed = deepcopy(comparison)
    malformed["unexpected"] = True
    invalid.append(("malformed", malformed, primary, packet_manifest))
    invalid.append(("swapped", comparison, secondary, packet_manifest))
    stale_manifest = deepcopy(packet_manifest)
    stale_manifest["packet_set_sha256"] = "b" * 64
    invalid.append(("stale packet set", comparison, primary, stale_manifest))
    count_mismatch = deepcopy(comparison)
    count_mismatch["classification_counts"]["compatible_agreement"] = 1
    invalid.append(("count mismatch", count_mismatch, primary, packet_manifest))
    missing_zero_count = deepcopy(comparison)
    del missing_zero_count["classification_counts"]["exact_agreement"]
    invalid.append(("missing exact zero count", missing_zero_count, primary, packet_manifest))
    row_tamper = deepcopy(comparison)
    row_tamper["comparisons"][0]["classification"] = "substantive_disagreement"
    invalid.append(("row tamper", row_tamper, primary, packet_manifest))
    missing_row = deepcopy(comparison)
    missing_row["comparisons"].pop()
    invalid.append(("missing row", missing_row, primary, packet_manifest))

    for label, candidate, first_review, candidate_manifest in invalid:
        first_hash = _sha256(secondary_path) if label == "swapped" else _sha256(primary_path)
        second_review = primary if label == "swapped" else secondary
        second_hash = _sha256(primary_path) if label == "swapped" else _sha256(secondary_path)
        try:
            validate_comparison_artifact(
                candidate,
                schema,
                first_review,
                second_review,
                candidate_manifest,
                primary_sha256=first_hash,
                secondary_sha256=second_hash,
            )
        except ComparisonValidationError:
            continue
        failures.append(f"comparison validation: {label} artifact was accepted")

    malformed_reviews: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []

    malformed_primary = deepcopy(primary)
    malformed_primary["decisions"][2]["acceptable_leading_methods"] = "deduction"
    malformed_reviews.append(
        (
            "primary scalar acceptable_leading_methods",
            malformed_primary,
            secondary,
            "acceptable_leading_methods: must be an array of strings",
        )
    )
    malformed_secondary = deepcopy(secondary)
    malformed_secondary["decisions"][3]["allowed_behaviors"] = "hold"
    malformed_reviews.append(
        (
            "secondary scalar allowed_behaviors",
            primary,
            malformed_secondary,
            "allowed_behaviors: must be an array of strings",
        )
    )
    invalid_item = deepcopy(primary)
    invalid_item["decisions"][4]["acceptable_inclusion_methods"] = [7]
    malformed_reviews.append(
        (
            "primary invalid acceptable_inclusion_methods item",
            invalid_item,
            secondary,
            "acceptable_inclusion_methods: every item must be a non-empty string",
        )
    )
    duplicate_item = deepcopy(secondary)
    duplicate_item["decisions"][5]["prohibited_methods"] = ["deduction", "deduction"]
    malformed_reviews.append(
        (
            "secondary duplicate prohibited_methods",
            primary,
            duplicate_item,
            "prohibited_methods: duplicate items are forbidden",
        )
    )
    invalid_status = deepcopy(primary)
    invalid_status["decisions"][6]["status"] = "approved"
    malformed_reviews.append(
        ("invalid status enum", invalid_status, secondary, "status: invalid enum value")
    )
    invalid_policy = deepcopy(secondary)
    invalid_policy["decisions"][7]["intervention_policy"] = "sometimes"
    malformed_reviews.append(
        (
            "invalid intervention policy enum",
            primary,
            invalid_policy,
            "intervention_policy: invalid enum value",
        )
    )
    invalid_scalar = deepcopy(primary)
    invalid_scalar["decisions"][8]["leading_method"] = 7
    malformed_reviews.append(
        (
            "invalid leading method scalar",
            invalid_scalar,
            secondary,
            "leading_method: string or null required",
        )
    )
    invalid_boolean = deepcopy(secondary)
    invalid_boolean["decisions"][9]["policy_metric_eligible"] = 1
    malformed_reviews.append(
        (
            "invalid eligibility boolean",
            primary,
            invalid_boolean,
            "policy_metric_eligible: boolean required",
        )
    )
    missing_key = deepcopy(primary)
    missing_key["decisions"][10].pop("leading_method")
    malformed_reviews.append(
        ("missing required decision key", missing_key, secondary, "missing=['leading_method']")
    )
    extra_key = deepcopy(secondary)
    extra_key["decisions"][11]["invented_field"] = True
    malformed_reviews.append(("extra decision key", primary, extra_key, "extra=['invented_field']"))

    for index_value, (label, first_review, second_review, expected_error) in enumerate(
        malformed_reviews
    ):
        first_candidate_path = fixture / f"malformed-primary-{index_value:02d}.json"
        second_candidate_path = fixture / f"malformed-secondary-{index_value:02d}.json"
        _write_json(first_candidate_path, first_review)
        _write_json(second_candidate_path, second_review)
        first_hash = _sha256(first_candidate_path)
        second_hash = _sha256(second_candidate_path)
        _expect_reviewer_rejection(
            label=label,
            primary=first_review,
            secondary=second_review,
            packet_manifest=packet_manifest,
            comparison=comparison,
            schema=schema,
            primary_sha256=first_hash,
            secondary_sha256=second_hash,
            expected_error=expected_error,
            failures=failures,
        )

    _malformed_enum_regressions(
        fixture,
        primary,
        secondary,
        packet_manifest,
        packet_path,
        schema,
        schema_path,
        failures,
    )


def _overwrite_regressions(parent: Path, failures: list[str]) -> None:  # noqa: C901 - exercises each overwrite failure stage explicitly
    parent = parent.resolve()
    for label, publish, patch_target in (
        (
            "packet",
            publish_packet_directory,
            "build_v12_adjudication_packets.os.replace",
        ),
        (
            "final",
            publish_final_directory,
            "finalize_v12_ai_adjudication.os.replace",
        ),
    ):
        target = parent / f"{label}-existing"
        target.mkdir()
        (target / "lock.json").write_text("old", encoding="utf-8")
        staged = parent / f"{label}-staged"
        staged.mkdir()
        (staged / "lock.json").write_text("new", encoding="utf-8")
        try:
            publish(staged, target, allow_overwrite=False)
        except SystemExit:
            pass
        else:
            failures.append(f"{label}-publish: existing lock was not refused")
        if (target / "lock.json").read_text(encoding="utf-8") != "old":
            failures.append(f"{label}-publish: refused target was modified")

        sentinel = parent / f"{label}-symlink-sentinel"
        sentinel.mkdir()
        (sentinel / "lock.json").write_text("sentinel", encoding="utf-8")
        symlink_target = parent / f"{label}-symlink-output"
        symlink_target.symlink_to(sentinel, target_is_directory=True)
        symlink_staged = parent / f"{label}-symlink-staged"
        symlink_staged.mkdir()
        (symlink_staged / "lock.json").write_text("replacement", encoding="utf-8")
        try:
            publish(symlink_staged, symlink_target, allow_overwrite=True)
        except SystemExit:
            pass
        else:
            failures.append(f"{label}-publish: symlink output was accepted")
        if (
            not symlink_target.is_symlink()
            or (sentinel / "lock.json").read_text(encoding="utf-8") != "sentinel"
            or not symlink_staged.is_dir()
        ):
            failures.append(f"{label}-publish: symlink refusal did not preserve sentinel/stage")

        real_parent = parent / f"{label}-real-parent"
        real_parent.mkdir()
        nested_sentinel = real_parent / "target"
        nested_sentinel.mkdir()
        (nested_sentinel / "lock.json").write_text("nested-sentinel", encoding="utf-8")
        linked_parent = parent / f"{label}-linked-parent"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        parent_staged = parent / f"{label}-parent-link-staged"
        parent_staged.mkdir()
        try:
            publish(parent_staged, linked_parent / "target", allow_overwrite=True)
        except SystemExit:
            pass
        else:
            failures.append(f"{label}-publish: symlink parent component was accepted")
        if (nested_sentinel / "lock.json").read_text(encoding="utf-8") != "nested-sentinel":
            failures.append(f"{label}-publish: symlink parent target was modified")

        rollback_target = parent / f"{label}-rollback-target"
        rollback_target.mkdir()
        (rollback_target / "lock.json").write_text("old", encoding="utf-8")
        rollback_staged = parent / f"{label}-rollback-staged"
        rollback_staged.mkdir()
        (rollback_staged / "lock.json").write_text("new", encoding="utf-8")
        original_replace = os.replace
        replace_calls = 0

        def fail_second_replace(
            source: object,
            destination: object,
            replace: Callable[[object, object], None] = original_replace,
        ) -> None:
            nonlocal replace_calls
            replace_calls += 1
            if replace_calls == 2:
                raise OSError("synthetic interrupted replacement")
            replace(source, destination)

        try:
            with patch(patch_target, side_effect=fail_second_replace):
                publish(rollback_staged, rollback_target, allow_overwrite=True)
        except OSError:
            pass
        else:
            failures.append(f"{label}-publish: interrupted replacement did not fail")
        if (
            not rollback_target.is_dir()
            or (rollback_target / "lock.json").read_text(encoding="utf-8") != "old"
        ):
            failures.append(f"{label}-publish: interrupted replacement did not roll back")

    locked_output = parent / "final-publication-lock-output"
    locked_output.mkdir()
    publication_lock = locked_output / "adjudication-publication-lock-v1.0.0.json"
    publication_lock.write_text("pinned", encoding="utf-8")
    locked_staged = parent / "final-publication-lock-staged"
    locked_staged.mkdir()
    (locked_staged / "replacement.json").write_text("new", encoding="utf-8")
    try:
        with patch(
            "finalize_v12_ai_adjudication.PUBLICATION_LOCK_PATH",
            publication_lock,
        ):
            publish_final_directory(locked_staged, locked_output, allow_overwrite=True)
    except SystemExit as exc:
        if "pinned publication lock" not in str(exc):
            failures.append(f"final-publish: unexpected publication-lock error {exc!s}")
    else:
        failures.append("final-publish: pinned publication-lock directory was accepted")
    if publication_lock.read_text(encoding="utf-8") != "pinned" or not locked_staged.is_dir():
        failures.append("final-publish: publication-lock refusal did not preserve target/stage")


def _json_schema_numeric_regressions(failures: list[str]) -> None:
    """Keep the supported subset aligned with AJV Draft 2020-12 numeric equality."""

    differential_cases: tuple[tuple[str, Any, dict[str, Any], bool], ...] = (
        ("integral float is integer", 1.0, {"type": "integer"}, True),
        ("integral float equals integer const", 1.0, {"const": 1}, True),
        ("integral float equals integer enum", 1.0, {"enum": [1]}, True),
        ("boolean differs from integer const", True, {"const": 1}, False),
        (
            "numeric equivalents violate uniqueItems",
            [1, 1.0],
            {"type": "array", "uniqueItems": True},
            False,
        ),
        (
            "nested numeric equivalents violate uniqueItems",
            [{"value": 1}, {"value": 1.0}],
            {"type": "array", "uniqueItems": True},
            False,
        ),
    )
    for label, instance, schema, expected_valid in differential_cases:
        valid = not validate(instance, schema)
        if valid is not expected_valid:
            failures.append(
                f"json-schema AJV differential {label}: expected valid={expected_valid}, "
                f"got {valid}"
            )

    duplicate_enum_schema = {
        "$schema": DRAFT_2020_12,
        "enum": [1, 1.0],
    }
    if not check_schema(duplicate_enum_schema):
        failures.append("json-schema AJV differential: enum [1, 1.0] was treated as unique")

    for label, value in (("NaN", math.nan), ("Infinity", math.inf)):
        if not validate(value, {}) or not check_schema({"$schema": DRAFT_2020_12, "const": value}):
            failures.append(f"json-schema non-JSON boundary: {label} was accepted")


def _semantic_review_regressions(failures: list[str]) -> None:  # noqa: C901
    schema = _semantic_review_schema(
        _json(ROOT / EVAL_RELATIVE / "schemas/adjudication-decision.schema.json")
    )

    primary_review = {
        "en_ko_equivalent": True,
        "translation_mismatch": False,
        "notes": ["Primary reviewer note."],
    }
    primary_record = {"semantic_review": primary_review}
    eligible_decision = {"policy_metric_eligible": True}
    preserved = _final_semantic_review(
        "synthetic-equivalent",
        primary_record,
        eligible_decision,
        schema,
        None,
    )
    if preserved != primary_review or preserved is primary_review:
        failures.append("finalizer semantic review: true/false primary value was not copied")

    uncertainty_fixture = [
        {
            "issue": f"Synthetic uncertainty issue {index}.",
            "pair_id": f"synthetic-uncertainty-{index}",
            "residual": index >= 4,
            "resolution": f"Synthetic uncertainty resolution {index}.",
        }
        for index in range(7)
    ]
    indexed_uncertainties = _uncertainty_index(
        uncertainty_fixture,
        {item["pair_id"] for item in uncertainty_fixture},
    )
    residual_counts = {
        state: sum(item["residual"] is state for item in indexed_uncertainties.values())
        for state in (False, True)
    }
    if len(indexed_uncertainties) != 7 or residual_counts != {False: 4, True: 3}:
        failures.append(
            "finalizer uncertainty shape: expected seven records with residual false/true 4/3, "
            f"got count={len(indexed_uncertainties)} residual={residual_counts}"
        )

    non_residual = {
        "pair_id": "synthetic-equivalent",
        "residual": False,
        "issue": "The secondary reviewer considered a possible nuance.",
        "resolution": "The uncertainty did not remain after review.",
    }
    unchanged = _final_semantic_review(
        "synthetic-equivalent",
        primary_record,
        eligible_decision,
        schema,
        non_residual,
    )
    if unchanged != primary_review:
        failures.append(
            "finalizer semantic review: residual=false changed the primary semantic review"
        )

    nuance = {
        "pair_id": "synthetic-equivalent",
        "residual": True,
        "issue": "The EN and KO wording has a non-decision-changing nuance.",
        "resolution": "The primary semantic judgment remains unchanged.",
    }
    merged = _final_semantic_review(
        "synthetic-equivalent",
        primary_record,
        eligible_decision,
        schema,
        nuance,
    )
    expected_note = (
        "Secondary-review residual uncertainty: The EN and KO wording has a "
        "non-decision-changing nuance. The primary semantic judgment remains unchanged."
    )
    if merged["notes"] != ["Primary reviewer note.", expected_note]:
        failures.append(f"finalizer semantic review: secondary nuance was not merged: {merged}")
    if primary_record["semantic_review"] != primary_review:
        failures.append("finalizer semantic review: primary input was mutated")

    mismatch_review = {
        "en_ko_equivalent": False,
        "translation_mismatch": True,
        "notes": ["Material mismatch remains."],
    }
    preserved_mismatch = _final_semantic_review(
        "synthetic-mismatch",
        {"semantic_review": mismatch_review},
        {"policy_metric_eligible": False},
        schema,
        None,
    )
    if preserved_mismatch != mismatch_review:
        failures.append("finalizer semantic review: false/true primary value was not preserved")

    invalid_cases: tuple[tuple[str, dict[str, Any], dict[str, Any], str], ...] = (
        (
            "missing",
            {},
            {"policy_metric_eligible": False},
            "invalid primary semantic_review",
        ),
        (
            "malformed boolean",
            {
                "semantic_review": {
                    "en_ko_equivalent": "true",
                    "translation_mismatch": False,
                    "notes": [],
                }
            },
            {"policy_metric_eligible": True},
            "invalid primary semantic_review",
        ),
        (
            "malformed shape",
            {
                "semantic_review": {
                    "en_ko_equivalent": True,
                    "translation_mismatch": False,
                    "notes": [],
                    "fabricated": True,
                }
            },
            {"policy_metric_eligible": True},
            "invalid primary semantic_review",
        ),
        (
            "contradictory booleans",
            {
                "semantic_review": {
                    "en_ko_equivalent": True,
                    "translation_mismatch": True,
                    "notes": [],
                }
            },
            {"policy_metric_eligible": False},
            "must record exactly one",
        ),
        (
            "metric contradiction",
            {"semantic_review": mismatch_review},
            {"policy_metric_eligible": True},
            "translation_mismatch=true conflicts",
        ),
    )
    for label, record, decision, expected in invalid_cases:
        try:
            _final_semantic_review("synthetic-invalid", record, decision, schema, None)
        except SystemExit as exc:
            if expected not in str(exc):
                failures.append(f"finalizer semantic review {label}: unexpected error {str(exc)!r}")
        else:
            failures.append(f"finalizer semantic review {label}: invalid input was accepted")

    invalid_uncertainties: tuple[tuple[str, Any, str], ...] = (
        (
            "non-boolean residual",
            {
                "issue": "Issue.",
                "pair_id": "synthetic-invalid",
                "residual": "false",
                "resolution": "Resolution.",
            },
            "residual must be boolean",
        ),
        (
            "missing resolution",
            {
                "issue": "Issue.",
                "pair_id": "synthetic-invalid",
                "residual": False,
            },
            "malformed secondary uncertainty fields",
        ),
        (
            "identity mismatch",
            {
                "issue": "Issue.",
                "pair_id": "different-pair",
                "residual": False,
                "resolution": "Resolution.",
            },
            "does not match",
        ),
    )
    for label, uncertainty, expected in invalid_uncertainties:
        try:
            _final_semantic_review(
                "synthetic-invalid",
                {"semantic_review": primary_review},
                eligible_decision,
                schema,
                uncertainty,
            )
        except SystemExit as exc:
            if expected not in str(exc):
                failures.append(f"finalizer uncertainty {label}: unexpected error {str(exc)!r}")
        else:
            failures.append(f"finalizer uncertainty {label}: invalid input was accepted")


def main() -> int:  # noqa: C901
    failures: list[str] = []
    passed = 0

    with tempfile.TemporaryDirectory(prefix="opensocrates-adjudication-mutations-") as directory:
        temporary = Path(directory)
        baseline = _fixture(temporary, "baseline")
        code, output = _run(baseline)
        if code != 0:
            print("adjudication-mutations: FAIL baseline")
            print(output)
            return 1
        passed += 1

        decisions = EVAL_RELATIVE / "adjudication-decisions-v1.0.0.jsonl"
        disagreements = EVAL_RELATIVE / "adjudication-disagreements-v1.0.0.jsonl"
        manifest = EVAL_RELATIVE / "adjudication-manifest-v1.0.0.json"
        policy = EVAL_RELATIVE / "adjudication-policy-v1.0.0.json"
        freeze = EVAL_RELATIVE / "adjudication-freeze-v1.0.0.json"
        guide = EVAL_RELATIVE / "ADJUDICATION_GUIDE.md"
        amendment = EVAL_RELATIVE / "ADJUDICATION_AI_AMENDMENT.md"
        publication_lock = PUBLICATION_LOCK_RELATIVE
        decision_schema = EVAL_RELATIVE / "schemas/adjudication-decision.schema.json"
        disagreement_schema = EVAL_RELATIVE / "schemas/adjudication-disagreement.schema.json"

        cases: list[tuple[str, Callable[[Path], None], str]] = [
            (
                "missing publication lock",
                lambda root: (root / publication_lock).unlink(),
                "committed.publication_lock.missing",
            ),
            (
                "malformed publication lock",
                lambda root: (root / publication_lock).write_text("{", encoding="utf-8"),
                "committed.publication_lock.json",
            ),
            (
                "publication lock path traversal",
                _mutate_json(
                    publication_lock,
                    lambda value: value["artifacts"]["report"].__setitem__(
                        "path", "../docs/v1.2-adjudication-report.md"
                    ),
                ),
                "committed.publication_lock.entry.report.path.safe",
            ),
            (
                "publication lock extra artifact",
                _mutate_json(
                    publication_lock,
                    lambda value: value["artifacts"].__setitem__(
                        "private_review",
                        {"path": "build/private-review.json", "sha256": "0" * 64},
                    ),
                ),
                "committed.publication_lock.artifacts_fields",
            ),
            (
                "publication lock missing artifact",
                _mutate_json(
                    publication_lock,
                    lambda value: value["artifacts"].pop("report"),
                ),
                "committed.publication_lock.artifacts_fields",
            ),
            (
                "publication lock entry additional property",
                _mutate_json(
                    publication_lock,
                    lambda value: value["artifacts"]["report"].__setitem__("unexpected", True),
                ),
                "committed.publication_lock.entry.report.fields",
            ),
            (
                "publication lock top-level additional property",
                _mutate_json(
                    publication_lock,
                    lambda value: value.__setitem__("unexpected", True),
                ),
                "committed.publication_lock.fields",
            ),
            (
                "manifest digest drift from publication lock",
                _mutate_json(
                    manifest,
                    lambda value: value.__setitem__("decision_locked_at", "2026-08-13T02:55:09Z"),
                ),
                "committed.publication_lock.artifact.manifest.mismatch",
            ),
            (
                "missing decisions",
                lambda root: (root / decisions).unlink(),
                "committed.decisions.missing",
            ),
            (
                "empty decisions",
                lambda root: (root / decisions).write_text("", encoding="utf-8"),
                "committed.decisions.records_empty",
            ),
            (
                "incomplete decision count",
                _mutate_jsonl(decisions, lambda rows: rows.pop()),
                "committed.decisions.count",
            ),
            (
                "decision additionalProperties",
                _mutate_jsonl(decisions, lambda rows: rows[0].__setitem__("unexpected", True)),
                "additional property 'unexpected' is forbidden",
            ),
            (
                "decision date-time",
                _mutate_jsonl(
                    decisions,
                    lambda rows: rows[0]["review"].__setitem__(
                        "primary_decision_locked_at", "2026-99-99"
                    ),
                ),
                "is not an RFC 3339 date-time",
            ),
            (
                "decision SHA-256 pattern",
                _mutate_jsonl(
                    decisions,
                    lambda rows: rows[0]["provenance"]["source_case_sha256"].__setitem__(
                        "en", "not-a-sha"
                    ),
                ),
                "does not match pattern",
            ),
            (
                "decision uniqueItems",
                _mutate_jsonl(
                    decisions,
                    lambda rows: rows[0].__setitem__("locales", ["en", "en"]),
                ),
                "duplicates an earlier item",
            ),
            (
                "decision evidence grade",
                _mutate_jsonl(decisions, lambda rows: rows[0].pop("evidence_grade")),
                "committed.decisions.evidence_grade",
            ),
            (
                "inclusion boundary",
                _mutate_jsonl(
                    decisions,
                    lambda rows: next(
                        row for row in rows if row["pair_id"] == "design-thinking-positive-03"
                    )["decision"].__setitem__(
                        "acceptable_inclusion_methods", ["socratic-questioning"]
                    ),
                ),
                "committed.decisions.inclusion_boundary",
            ),
            (
                "unknown method",
                _mutate_jsonl(
                    decisions,
                    lambda rows: rows[0]["decision"].__setitem__(
                        "acceptable_inclusion_methods", ["not-a-public-method"]
                    ),
                ),
                "committed.decisions.unknown_method",
            ),
            (
                "disagreement additionalProperties",
                _mutate_jsonl(disagreements, lambda rows: rows[0].__setitem__("unexpected", True)),
                "additional property 'unexpected' is forbidden",
            ),
            (
                "disagreement date-time",
                _mutate_jsonl(
                    disagreements,
                    lambda rows: rows[0]["resolution"].__setitem__("resolved_at", "yesterday"),
                ),
                "is not an RFC 3339 date-time",
            ),
            (
                "disagreement final decision",
                _mutate_jsonl(
                    disagreements,
                    lambda rows: rows[0]["resolution"]["final_decision"].__setitem__(
                        "policy_metric_eligible", False
                    ),
                ),
                "committed.disagreements.final_decision",
            ),
            (
                "disagreement evidence grade",
                _mutate_jsonl(disagreements, lambda rows: rows[0].pop("evidence_grade")),
                "committed.disagreements.evidence_grade",
            ),
            (
                "disagreement count",
                _mutate_jsonl(disagreements, lambda rows: rows.pop()),
                "committed.disagreements.count",
            ),
            (
                "gold-suffixed status",
                _mutate_jsonl(
                    disagreements,
                    lambda rows: rows[0]["resolution"].__setitem__(
                        "status", "resolved_for_provisional_development_gold"
                    ),
                ),
                "committed.status.gold_suffix",
            ),
            (
                "manifest status counts",
                _mutate_json(
                    manifest, lambda value: value["status_counts"].__setitem__("retain", 0)
                ),
                "committed.manifest.status_counts",
            ),
            (
                "manifest agreement counts",
                _mutate_json(
                    manifest,
                    lambda value: value["agreement_counts"].__setitem__("minor_revision", 0),
                ),
                "committed.manifest.agreement_counts",
            ),
            (
                "manifest policy counts",
                _mutate_json(
                    manifest,
                    lambda value: value["intervention_policy_counts"].__setitem__("required", 0),
                ),
                "committed.manifest.intervention_policy_counts",
            ),
            (
                "manifest metric counts",
                _mutate_json(
                    manifest,
                    lambda value: value["metric_eligibility_counts"].__setitem__("policy", 0),
                ),
                "committed.manifest.metric_eligibility_counts",
            ),
            (
                "manifest pair count",
                _mutate_json(manifest, lambda value: value.__setitem__("pair_count", 50)),
                "committed.manifest.pair_count",
            ),
            (
                "manifest additional property",
                _mutate_json(manifest, lambda value: value.__setitem__("unexpected", True)),
                "committed.manifest.additional_properties",
            ),
            (
                "manifest date-time",
                _mutate_json(
                    manifest,
                    lambda value: value.__setitem__("decision_locked_at", "not-a-date"),
                ),
                "committed.manifest.decision_locked_at",
            ),
            (
                "manifest maintainer evidence fields",
                _mutate_json(
                    manifest,
                    lambda value: value["maintainer_evidence"].__setitem__("unexpected", "0" * 64),
                ),
                "committed.manifest.maintainer_evidence_fields",
            ),
            (
                "policy date-time",
                _mutate_json(policy, lambda value: value.__setitem__("locked_at", "not-a-date")),
                "committed.policy.locked_at",
            ),
            (
                "private citation token",
                _mutate_json(
                    policy,
                    lambda value: value.__setitem__("source_citations", ["\ue200filecite\ue201"]),
                ),
                "committed.privacy.private_citation",
            ),
            (
                "colliding evaluation identifier",
                lambda root: (root / REPORT_RELATIVE).write_text(
                    (root / REPORT_RELATIVE).read_text(encoding="utf-8") + "\nHistorical #65.\n",
                    encoding="utf-8",
                ),
                "committed.identifier.stale_65",
            ),
            (
                "freeze evidence boundary",
                _mutate_json(
                    freeze,
                    lambda value: value.__setitem__("evidence_availability", "public"),
                ),
                "committed.freeze.evidence_boundary",
            ),
            (
                "freeze date-time",
                _mutate_json(freeze, lambda value: value.__setitem__("frozen_at", "not-a-date")),
                "committed.freeze.frozen_at",
            ),
            (
                "unsupported schema keyword",
                _mutate_json(decision_schema, lambda value: value.__setitem__("oneOf", [])),
                "unsupported schema keyword 'oneOf'",
            ),
            (
                "schema uniqueItems type",
                _mutate_json(
                    decision_schema,
                    lambda value: value["properties"]["locales"].__setitem__("uniqueItems", "yes"),
                ),
                "uniqueItems: must be boolean",
            ),
            (
                "missing disagreement schema",
                lambda root: (root / disagreement_schema).unlink(),
                "committed.disagreement_schema.missing",
            ),
        ]

        positive_claim = (
            "This is confirmation-grade human gold, held-out, and answer-quality evidence."
        )
        report_provides_claim = (
            "This report provides confirmation-grade human gold, held-out, and "
            "answer-quality evidence."
        )
        release_certification_claim = (
            "We certify this snapshot as confirmation-grade human gold, held-out, "
            "and answer-quality evidence."
        )
        mixed_claim = (
            "This report is not confirmation-grade human gold, not held-out, and not "
            "answer-quality evidence, but it nevertheless provides confirmation-grade "
            "human gold."
        )
        unicode_nonbreaking_claim = (
            "This snapshot is confirmation\u2011grade human gold, held\u2011out, and "
            "answer\u2011quality evidence."
        )
        unicode_dash_variant_claim = (
            "This snapshot is confirmation\u2010grade human gold, held\u2212out, and "
            "answer\u2013quality evidence."
        )
        report_safe_conditional = (
            "A later confirmation claim requires a new version, an output-blind independent\n"
            "human review, separately authored held-out cases, and no retroactive editing of\n"
            "this history."
        )
        positive_context_replacement = (
            "The committed snapshot consists of separately authored held-out cases."
        )
        guide_safe_context = (
            "Held-out cases are separately authored with no model exposure, EN/KO semantic\n"
            "pairing, author/translator separated from output judges, labels fixed before\n"
            "freeze, and per-case leading/inclusion/prohibited routes recorded before any\n"
            "model output is opened."
        )
        amendment_restriction = "They may not be used as:"
        amendment_scope_reversal = "They may be used as:"
        report_disclaimer = (
            "This is not confirmation-grade human gold, not held-out, and not\n"
            "answer-quality evidence."
        )
        report_false_wrapper = (
            "The statement “This is not confirmation-grade human gold, not held-out, "
            "and not answer-quality evidence.” is false."
        )
        coherent_cases: list[tuple[str, Callable[[Path], None], str]] = [
            (
                "coherent semantic both false",
                _with_rehashed_manifest(
                    _mutate_jsonl(
                        decisions,
                        lambda rows: rows[0]["semantic_review"].update(
                            {"en_ko_equivalent": False, "translation_mismatch": False}
                        ),
                    ),
                    "decisions",
                ),
                "committed.decisions.semantic_review_exactly_one",
            ),
            (
                "coherent case kind contradiction",
                _with_rehashed_manifest(
                    _mutate_jsonl(
                        decisions,
                        lambda rows: rows[0]["decision"].__setitem__(
                            "case_kind",
                            "positive" if rows[0]["legacy"]["kind"] != "positive" else "negative",
                        ),
                    ),
                    "decisions",
                ),
                "committed.decisions.case_kind",
            ),
            (
                "coherent resolved review with unresolved ledger",
                _with_rehashed_manifest(
                    _mutate_jsonl(
                        disagreements,
                        lambda rows: rows[0]["resolution"].update(
                            {
                                "status": "unresolved",
                                "selected_source": "unresolved",
                                "resolution_reviewer": None,
                                "resolved_at": None,
                            }
                        ),
                    ),
                    "disagreements",
                ),
                "committed.disagreements.resolved_status",
            ),
            (
                "coherent resolution timestamp contradiction",
                _with_rehashed_manifest(
                    _mutate_jsonl(
                        disagreements,
                        lambda rows: rows[0]["resolution"].__setitem__(
                            "resolved_at", "2026-08-13T00:00:00Z"
                        ),
                    ),
                    "disagreements",
                ),
                "committed.disagreements.resolved_at",
            ),
            (
                "coherent resolved source contradiction",
                _with_rehashed_manifest(
                    _mutate_jsonl(
                        disagreements,
                        lambda rows: rows[0]["resolution"].__setitem__(
                            "selected_source", "unresolved"
                        ),
                    ),
                    "disagreements",
                ),
                "committed.disagreements.resolved_source",
            ),
            (
                "coherent resolution reviewer contradiction",
                _with_rehashed_manifest(
                    _mutate_jsonl(
                        disagreements,
                        lambda rows: rows[0]["resolution"].__setitem__(
                            "resolution_reviewer", "different-maintainer"
                        ),
                    ),
                    "disagreements",
                ),
                "committed.disagreements.resolution_reviewer",
            ),
            (
                "coherent decision creation timestamp contradiction",
                _with_rehashed_manifest(
                    _mutate_jsonl(
                        decisions,
                        lambda rows: rows[0]["provenance"].__setitem__(
                            "decision_created_at", "2026-08-13T00:00:00Z"
                        ),
                    ),
                    "decisions",
                ),
                "committed.decisions.created_at",
            ),
            (
                "coherent freeze schema",
                _with_rehashed_manifest(
                    _mutate_json(freeze, lambda value: value.__setitem__("schema", "wrong")),
                    "freeze",
                ),
                "committed.freeze.schema",
            ),
            (
                "coherent freeze protocol",
                _with_rehashed_manifest(
                    _mutate_json(
                        freeze, lambda value: value.__setitem__("protocol_version", "9.9.9")
                    ),
                    "freeze",
                ),
                "committed.freeze.protocol",
            ),
            (
                "coherent freeze guide version",
                _with_rehashed_manifest(
                    _mutate_json(freeze, lambda value: value.__setitem__("guide_version", "9.9.9")),
                    "freeze",
                ),
                "committed.freeze.guide_version",
            ),
            (
                "coherent freeze counts",
                _with_rehashed_manifest(
                    _mutate_json(freeze, lambda value: value.__setitem__("unique_pair_count", 50)),
                    "freeze",
                ),
                "committed.freeze.counts",
            ),
            (
                "coherent report provides positive claim",
                _with_rehashed_manifest(
                    _append_text(REPORT_RELATIVE, report_provides_claim),
                    "report",
                ),
                "committed.claim_boundary.report",
            ),
            (
                "coherent policy positive claim",
                _with_rehashed_manifest(
                    _mutate_json(
                        policy,
                        lambda value: value.__setitem__("publication_boundary", positive_claim),
                    ),
                    "policy",
                ),
                "committed.claim_boundary.policy",
            ),
            (
                "coherent guide positive claim",
                _with_rehashed_manifest(
                    lambda root: (root / guide).write_text(
                        (root / guide).read_text(encoding="utf-8") + "\n" + positive_claim + "\n",
                        encoding="utf-8",
                    ),
                    "annotation_guide",
                ),
                "committed.claim_boundary.guide",
            ),
            (
                "coherent amendment positive claim",
                _with_rehashed_manifest(
                    lambda root: (root / amendment).write_text(
                        (root / amendment).read_text(encoding="utf-8")
                        + "\n"
                        + positive_claim
                        + "\n",
                        encoding="utf-8",
                    ),
                    "ai_amendment",
                ),
                "committed.claim_boundary.amendment",
            ),
            (
                "manifest positive claim",
                _mutate_json(
                    manifest,
                    lambda value: value.__setitem__("publication_boundary", positive_claim),
                ),
                "committed.claim_boundary.manifest",
            ),
            (
                "coherent release notes certification claim",
                _with_rehashed_manifest(
                    _append_text(RELEASE_NOTES_RELATIVE, release_certification_claim),
                    "release_notes",
                ),
                "committed.claim_boundary.release_notes",
            ),
            (
                "coherent mixed negative and positive report claim",
                _with_rehashed_manifest(
                    _append_text(REPORT_RELATIVE, mixed_claim),
                    "report",
                ),
                "committed.claim_boundary.report",
            ),
            (
                "coherent grammar-free held-out claim variant",
                _with_rehashed_manifest(
                    _append_text(REPORT_RELATIVE, "Held-out evidence is hereby established."),
                    "report",
                ),
                "committed.claim_boundary.report",
            ),
            (
                "coherent grammar-free answer-quality claim variant",
                _with_rehashed_manifest(
                    _append_text(
                        RELEASE_NOTES_RELATIVE,
                        "Answer-quality evidence now follows from this snapshot.",
                    ),
                    "release_notes",
                ),
                "committed.claim_boundary.release_notes",
            ),
            (
                "coherent Unicode non-breaking-hyphen report claim",
                _with_rehashed_manifest(
                    _append_text(REPORT_RELATIVE, unicode_nonbreaking_claim),
                    "report",
                ),
                "committed.claim_boundary.report",
            ),
            (
                "coherent Unicode dash variants report claim",
                _with_rehashed_manifest(
                    _append_text(REPORT_RELATIVE, unicode_dash_variant_claim),
                    "report",
                ),
                "committed.claim_boundary.report",
            ),
            (
                "coherent report safe-context positive replacement",
                _with_rehashed_manifest(
                    _replace_text(
                        REPORT_RELATIVE,
                        report_safe_conditional,
                        positive_context_replacement,
                    ),
                    "report",
                ),
                "committed.claim_boundary.report",
            ),
            (
                "coherent guide safe-context positive replacement",
                _with_rehashed_manifest(
                    _replace_text(
                        guide,
                        guide_safe_context,
                        positive_context_replacement,
                    ),
                    "annotation_guide",
                ),
                "committed.claim_boundary.guide",
            ),
            (
                "coherent amendment permission reversal",
                _with_rehashed_manifest(
                    _replace_text(
                        amendment,
                        amendment_restriction,
                        amendment_scope_reversal,
                    ),
                    "ai_amendment",
                ),
                "committed.publication_lock.artifact.ai_amendment.mismatch",
            ),
            (
                "coherent amendment permission reversal with rehashed lock",
                _with_rehashed_manifest_and_publication_lock(
                    _replace_text(
                        amendment,
                        amendment_restriction,
                        amendment_scope_reversal,
                    ),
                    "ai_amendment",
                ),
                "committed.publication_lock.root",
            ),
            (
                "coherent report false-wrapper reversal",
                _with_rehashed_manifest(
                    _replace_text(
                        REPORT_RELATIVE,
                        report_disclaimer,
                        report_false_wrapper,
                    ),
                    "report",
                ),
                "committed.publication_lock.artifact.report.mismatch",
            ),
            (
                "coherent report false-wrapper reversal with rehashed lock",
                _with_rehashed_manifest_and_publication_lock(
                    _replace_text(
                        REPORT_RELATIVE,
                        report_disclaimer,
                        report_false_wrapper,
                    ),
                    "report",
                ),
                "committed.publication_lock.root",
            ),
            (
                "comparison classification count tamper",
                _mutate_json(
                    manifest,
                    lambda value: value["comparison_provenance"][
                        "classification_counts"
                    ].__setitem__("compatible_agreement", 3),
                ),
                "committed.comparison_provenance.classification_counts",
            ),
            (
                "comparison pair classification tamper",
                _mutate_json(
                    manifest,
                    lambda value: value["comparison_provenance"][
                        "classification_by_pair"
                    ].__setitem__("abduction-insufficiency-01", "compatible_agreement"),
                ),
                "committed.comparison_provenance.pair_counts",
            ),
        ]
        cases.extend(coherent_cases)

        hash_fields = (
            "annotation_guide",
            "ai_amendment",
            "policy",
            "decisions",
            "disagreements",
            "decision_schema",
            "disagreement_schema",
            "comparison_schema",
            "freeze",
            "report",
            "release_notes",
        )
        for field in hash_fields:
            cases.append(
                (
                    f"committed hash {field}",
                    _mutate_json(
                        manifest,
                        lambda value, key=field: value["committed_artifact_sha256"].__setitem__(
                            key, "0" * 64
                        ),
                    ),
                    f"committed.hash.{field}.mismatch",
                )
            )

        for index, (name, mutate, expected) in enumerate(cases):
            case_root = _fixture(temporary, f"case-{index:02d}")
            mutate(case_root)
            code, output = _run(case_root)
            if code == 0 or expected not in output:
                failures.append(
                    f"{name}: expected nonzero and {expected!r}; code={code}\n{output[:1200]}"
                )
            else:
                passed += 1

        evidence_root = _fixture(temporary, "evidence-missing")
        code, output = _run(evidence_root, mode="maintainer-evidence")
        required_evidence_errors = (
            "evidence.packet_manifest.missing",
            "evidence.review.primary.missing",
            "evidence.raw.screening-results.jsonl.missing",
            "evidence.queue.missing",
        )
        if code == 0 or any(error not in output for error in required_evidence_errors):
            failures.append(f"maintainer evidence absence was not explicit\n{output[:1600]}")
        else:
            passed += 1

        _contract_regressions(failures)
        _comparison_regressions(temporary, failures)
        _overwrite_regressions(temporary, failures)
        _json_schema_numeric_regressions(failures)
        _semantic_review_regressions(failures)

    if failures:
        print(f"adjudication-mutations: FAIL ({len(failures)} failures; {passed} passed)")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        "adjudication-mutations: PASS "
        f"({passed} validator scenarios, {len(coherent_cases)} coherent mutations, "
        "plus comparison/contracts/tooling)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
