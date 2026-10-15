#!/usr/bin/env python3
"""Focused S098-F01 public-fixture regressions; no host or model calls.

Run only against the selected integrated candidate. All status, identity, freeze
and approval values below are invented test data, never study observations or
execution permission. Credential/path probes are public dummy strings. Temporary
files contain only these authored fixtures and the public canonical rubric.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any

import swarm_blind_packets as packets

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "evals/swarm-20261015/scoring-rubric.json"
FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
LOCALES = ("en", "ko")
ARMS = ("plain", "general-check", "native-opensocrates")
PUBLIC_ANSWER = (
    "  Public synthetic answer with OpenSocrates method attribution.\n\n"
    "See https://example.org/public/task_key_contract for this invented example.\n"
    "  방법 언급과 공백을 포함한 원문을 그대로 보존합니다.\n"
)
PRIVATE_CATEGORY_PROBES = (
    ("windows-backslash", r"C:\S047_PUBLIC_FIXTURE\blocked.txt"),
    ("windows-forward-slash", "c:/S047_PUBLIC_FIXTURE/blocked.txt"),
    ("quoted-windows-path", r'path="D:\S047_PUBLIC_FIXTURE\blocked.txt"'),
    ("unix-home", "/home/S047_PUBLIC_FIXTURE/blocked.txt"),
    ("unc-share", r"\\S047_PUBLIC_FIXTURE\share\blocked.txt"),
    ("file-url", "file:///S047_PUBLIC_FIXTURE/blocked.txt"),
    ("account-marker", "account_id=S047_PUBLIC_DUMMY"),
    ("private-url", "http://127.0.0.1/S047_PUBLIC_FIXTURE"),
    ("bearer", "Bearer S047_PUBLIC_DUMMY_NOT_A_SECRET"),
    ("private-key-marker", "-----BEGIN PRIVATE KEY-----\nS047_PUBLIC_DUMMY\n"),
    *(
        (prefix, prefix + "S047_PUBLIC_DUMMY_NOT_A_SECRET")
        for prefix in (
            "sk-",
            "sk_",
            "ghp_",
            "github_pat_",
            "xoxb-",
            "xoxp-",
            "xoxa-",
            "xoxr-",
            "xoxs-",
        )
    ),
)


def canonical_result(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def authored_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": f"{family}-{locale}",
            "family": family,
            "locale": locale,
            "public_synthetic_input": "Invented public facts at https://example.org/public.",
            "required_outcome": ["Keep the supplied public facts and requested deliverable."],
            "critical_errors": ["invented-fact"],
        }
        for family, locale in product(FAMILIES, LOCALES)
    ]


def authored_cells() -> list[dict[str, Any]]:
    cells = []
    for order, (family, locale, arm, repeat) in enumerate(
        product(FAMILIES, LOCALES, ARMS, (1, 2, 3)), start=1
    ):
        case_id = f"{family}-{locale}"
        cells.append(
            {
                "cell_id": f"{case_id}-{arm}-r{repeat}",
                "case_id": case_id,
                "arm": arm,
                "repeat": repeat,
                "order_index": order,
                "assignment_seed": "S047-public-regression-only",
                "status": "NOT_RUN",
            }
        )
    return cells


def authored_result(answer: str) -> dict[str, Any]:
    return {
        "cell_id": "email-agreement-en-plain-r1",
        "status": "COMPLETED",
        "public_final_answer": answer,
        "started_at": "2026-01-01T00:01:00Z",
        "ended_at": "2026-01-01T00:01:01Z",
        "elapsed_ms": 1000,
        "input_tokens": None,
        "output_tokens": None,
        "critical_error_labels": [],
        "task_complete": True,
        "entry_emitted": None,
        "canonical_full_read": None,
        "application_evidence": "unverified",
        "failure_reason": None,
        "identity": {
            "repository": "https://github.com/ParkerHwang/OpenSocrates",
            "source_sha": None,
            "product_version": None,
            "content_revision": None,
            "host": None,
            "platform": None,
            "model_requested": None,
            "model_observed": None,
            "effort": None,
            "service_tier_requested": None,
            "service_tier_observed": None,
        },
    }


def authored_control(result: dict[str, Any]) -> dict[str, Any]:
    null_reasons = {key: "NOT_OBSERVED" for key, value in result.items() if value is None}
    null_reasons["failure_reason"] = "NOT_APPLICABLE"
    null_reasons.update(
        {
            f"identity.{key}": "NOT_OBSERVED"
            for key, value in result["identity"].items()
            if value is None
        }
    )
    return {
        "schema_version": 1,
        "source_id": "manual-public-synthetic",
        "run_id": "S047-public-repair-regression",
        "attempt_id": f"S047-public-repair-regression:{result['cell_id']}:a1",
        "case_id": "email-agreement-en",
        "locale": "en",
        "manual_review": {
            "status": "APPROVED",
            "synthetic_only": True,
            "sensitive_content_checked": True,
            "final_answer_only": True,
        },
        "delivery_mode": "none",
        "independent_evaluation": "unavailable",
        "unknown_reasons": null_reasons,
        "cell_id": result["cell_id"],
        "result_sha256": sha256(canonical_result(result)),
    }


class PublicScreenRegression(unittest.TestCase):
    def test_public_urls_and_identifiers_are_not_private_categories(self) -> None:
        examples = (
            "https://github.com/ParkerHwang/OpenSocrates",
            "http://example.org/public",
            "https://example.org/public/task_key_contract#reference",
            "task_key_contract",
            "longer_task_key_contract_reference",
            "See https://example.org/public. Keep task_key_contract unchanged.",
        )
        for value in examples:
            with self.subTest(public_example=value):
                packets.scan_text(value)

    def test_complete_canonical_rubric_is_screened_without_editing(self) -> None:
        original_bytes = RUBRIC_PATH.read_bytes()
        rubric = json.loads(original_bytes)
        original = deepcopy(rubric)
        packets.public_text(rubric)
        self.assertEqual(rubric, original)
        self.assertEqual(RUBRIC_PATH.read_bytes(), original_bytes)

    def test_standalone_private_categories_still_reject(self) -> None:
        for category, value in PRIVATE_CATEGORY_PROBES:
            for wrapped in (value, f'fixture="{value}"', f"({value})"):
                with self.subTest(category=category):
                    with self.assertRaisesRegex(packets.PacketError, "^private_content_category$"):
                        packets.scan_text(wrapped)


class CanonicalPacketRegression(unittest.TestCase):
    def setUp(self) -> None:
        # Resolve the platform temp root so a macOS /var alias is not mistaken
        # for a linked output component. No user home or auth state is copied.
        self.temporary = tempfile.TemporaryDirectory(
            prefix="opensocrates-blind-regression-", dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.invocations = 0
        self.cases = self.root / "cases.json"
        self.assignments = self.root / "assignments.json"
        self.seed = self.root / "public-fixture-seed.txt"
        self.freeze = self.root / "synthetic-fixture-freeze.json"
        write_json(self.cases, {"cases": authored_cases()})
        write_json(self.assignments, {"cells": authored_cells()})
        self.seed.write_bytes(b"S047-public-regression-seed-only-not-authentication")
        pinned = (self.cases, RUBRIC_PATH, self.assignments, self.seed, Path(packets.__file__))
        write_json(
            self.freeze,
            {
                "schema_version": 1,
                "state": "FROZEN",
                "source_sha": "0" * 40,
                "approved_by": "S001",
                "quota": 54,
                "isolation_state": "VERIFIED",
                "frozen_at": "2026-01-01T00:00:00Z",
                "input_files": [
                    {"path": path.name, "sha256": sha256(path.read_bytes())} for path in pinned
                ],
            },
        )

    def invoke(self, results: list[dict[str, Any]]) -> tuple[int, str, str, Path, Path]:
        self.invocations += 1
        results_file = self.root / f"results-{self.invocations}.jsonl"
        controls_file = self.root / f"controls-{self.invocations}.jsonl"
        results_file.write_bytes(b"".join(canonical_result(row) + b"\n" for row in results))
        controls_file.write_bytes(
            b"".join(canonical_result(authored_control(row)) + b"\n" for row in results)
        )
        reviewer_dir = self.root / f"reviewer-{self.invocations}"
        custodian_dir = self.root / f"custodian-{self.invocations}"
        reviewer_dir.mkdir()
        custodian_dir.mkdir()
        reviewer = reviewer_dir / "blind-packets.json"
        custodian = custodian_dir / "blind-map.json"
        args = [
            "--input",
            str(results_file),
            "--review-input",
            str(controls_file),
            "--cases",
            str(self.cases),
            "--rubric",
            str(RUBRIC_PATH),
            "--assignments",
            str(self.assignments),
            "--freeze",
            str(self.freeze),
            "--seed-file",
            str(self.seed),
            "--output",
            str(reviewer),
            "--map-output",
            str(custodian),
        ]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = packets.main(args)
        return code, stdout.getvalue(), stderr.getvalue(), reviewer, custodian

    def assert_public_rubric_preserved(self, reviewer: dict[str, Any]) -> None:
        canonical = json.loads(RUBRIC_PATH.read_bytes())
        for section in ("verdicts", "dimensions", "common_critical_errors", "evidence_contract"):
            self.assertEqual(reviewer["rubric"][section], canonical[section])
        self.assertEqual(
            reviewer["rubric"]["task_key_contract"]["precedence"],
            canonical["task_key_contract"]["precedence"],
        )

    def test_empty_results_accept_full_canonical_rubric_and_keep_54(self) -> None:
        before = RUBRIC_PATH.read_bytes()
        code, stdout, stderr, reviewer_path, map_path = self.invoke([])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout)["packet_count"], 54)
        reviewer = json.loads(reviewer_path.read_bytes())
        custody = json.loads(map_path.read_bytes())
        self.assertEqual(len(reviewer["packets"]), 54)
        self.assertTrue(all(item["public_final_answer"] is None for item in reviewer["packets"]))
        self.assertEqual(len(custody["mapping"]), 54)
        self.assertEqual(custody["execution_status_counts"], {"NOT_RUN": 54})
        self.assert_public_rubric_preserved(reviewer)
        self.assertEqual(RUBRIC_PATH.read_bytes(), before)

    def test_url_and_method_mentions_survive_in_the_whole_answer(self) -> None:
        result = authored_result(PUBLIC_ANSWER)
        code, _stdout, stderr, reviewer_path, map_path = self.invoke([result])
        self.assertEqual((code, stderr), (0, ""))
        reviewer = json.loads(reviewer_path.read_bytes())
        custody = json.loads(map_path.read_bytes())
        answers = [item for item in reviewer["packets"] if item["public_final_answer"] is not None]
        self.assertEqual(len(reviewer["packets"]), 54)
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["public_final_answer"], PUBLIC_ANSWER)
        self.assertIsNone(answers[0]["decision_form"]["verdict"])
        for item in reviewer["packets"]:
            self.assertEqual(
                set(item), {"blind_id", "case", "public_final_answer", "decision_form"}
            )
        original = next(item for item in custody["mapping"] if item["cell_id"] == result["cell_id"])
        self.assertEqual(original["blind_id"], answers[0]["blind_id"])
        self.assertEqual(original["public_answer_sha256"], sha256(PUBLIC_ANSWER.encode("utf-8")))
        self.assertEqual(original["execution_status"], "COMPLETED")
        self.assertEqual(len(custody["mapping"]), 54)
        self.assert_public_rubric_preserved(reviewer)

    def test_private_dummy_answer_is_refused_without_redaction_or_outputs(self) -> None:
        for category, value in (
            ("windows-path", r"C:\S047_PUBLIC_FIXTURE\blocked.txt"),
            ("credential", "sk_S047_PUBLIC_DUMMY_NOT_A_SECRET"),
        ):
            with self.subTest(category=category):
                code, stdout, stderr, reviewer, custodian = self.invoke([authored_result(value)])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "packet_generation_refused:private_content_category\n")
                self.assertNotIn(value, stderr)
                self.assertFalse(reviewer.exists())
                self.assertFalse(custodian.exists())


if __name__ == "__main__":
    unittest.main()
