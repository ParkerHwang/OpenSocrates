#!/usr/bin/env python3
"""Focused mutation and regression tests for the v1.2 adjudication gate."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from build_v12_adjudication_packets import _publish_directory as publish_packet_directory
from compare_v12_adjudication_reviews import comparison_class
from finalize_v12_ai_adjudication import (
    _final_semantic_review,
    _semantic_review_schema,
    _uncertainty_index,
)
from finalize_v12_ai_adjudication import _publish_directory as publish_final_directory
from v12_adjudication_contract import FORBIDDEN_PACKET_KEYS, find_forbidden_packet_keys

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check_v12_adjudication.py"
EVAL_RELATIVE = Path("evals/v1.2")
REPORT_RELATIVE = Path("docs/v1.2-adjudication-report.md")


def _fixture(parent: Path, name: str) -> Path:
    target = parent / name
    shutil.copytree(ROOT / EVAL_RELATIVE, target / EVAL_RELATIVE)
    report = target / REPORT_RELATIVE
    report.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / REPORT_RELATIVE, report)
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


def _overwrite_regressions(parent: Path, failures: list[str]) -> None:
    for label, publish in (
        ("packet", publish_packet_directory),
        ("final", publish_final_directory),
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
        decision_schema = EVAL_RELATIVE / "schemas/adjudication-decision.schema.json"
        disagreement_schema = EVAL_RELATIVE / "schemas/adjudication-disagreement.schema.json"

        cases: list[tuple[str, Callable[[Path], None], str]] = [
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

        hash_fields = (
            "annotation_guide",
            "ai_amendment",
            "policy",
            "decisions",
            "disagreements",
            "decision_schema",
            "disagreement_schema",
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
        _overwrite_regressions(temporary, failures)
        _semantic_review_regressions(failures)

    if failures:
        print(f"adjudication-mutations: FAIL ({len(failures)} failures; {passed} passed)")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"adjudication-mutations: PASS ({passed} validator scenarios plus contracts/tooling)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
