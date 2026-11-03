"""Classifier probes. These rows are not benchmark cases."""

from __future__ import annotations

from typing import Any

from bench.adapters import probe_interpreter, run_command
from bench.cases import validate_case
from bench.scoring import score_envelope


def run_probes() -> list[dict[str, Any]]:
    return [
        _input_probe(),
        _scorer_probe(),
        _model_error_probe(),
        _model_unavailable_probe(),
        _condition_fail_probe(),
        _pass_probe(),
    ]


def _finish(probe_id: str, expected: str, actual: str, reason: str) -> dict[str, Any]:
    return {
        "id": probe_id,
        "kind": "probe",
        "expected_status": expected,
        "status": actual,
        "matched": actual == expected,
        "reason": reason,
    }


def _input_probe() -> dict[str, Any]:
    errors = validate_case({}, source="empty.json")
    actual = "input_error" if errors else "pass"
    return _finish("empty-case", "input_error", actual, "; ".join(errors) or "case accepted")


def _scorer_probe() -> dict[str, Any]:
    scored = score_envelope(
        {
            "checks": [
                {
                    "id": "bad-denominator",
                    "rule": "arithmetic_claim",
                    "section": "body",
                    "numerator": 1,
                    "denominator": 0,
                    "pretended_verification": ["verified"],
                }
            ]
        },
        {"body": "1/0", "requester_notes": ""},
    )
    return _finish("zero-denominator", "scorer_error", scored["status"], scored["reason"])


def _model_error_probe() -> dict[str, Any]:
    outcome = run_command(
        [probe_interpreter(), "-c", "import sys; sys.exit(3)"],
        {"schema": "probe"},
        timeout=5,
        env={"PATH": "/usr/bin:/bin"},
    )
    return _finish("command-exit", "model_error", outcome["status"], outcome["reason"])


def _model_unavailable_probe() -> dict[str, Any]:
    outcome = run_command(
        ["/nonexistent/opensocrates-bench-model"],
        {"schema": "probe"},
        timeout=5,
        env={"PATH": "/usr/bin:/bin"},
    )
    return _finish(
        "command-missing",
        "model_unavailable",
        outcome["status"],
        outcome["reason"],
    )


def _condition_fail_probe() -> dict[str, Any]:
    scored = score_envelope(
        {
            "checks": [
                {
                    "id": "no-invented-agreement",
                    "rule": "forbid_text",
                    "section": "body",
                    "patterns": ["예약이 확정"],
                }
            ]
        },
        {"body": "예약이 확정되었습니다.", "requester_notes": ""},
    )
    return _finish("forbid-hit", "condition_fail", scored["status"], scored["reason"])


def _pass_probe() -> dict[str, Any]:
    scored = score_envelope(
        {
            "checks": [
                {
                    "id": "keeps-operand",
                    "rule": "require_text",
                    "section": "body",
                    "text": "18/20",
                }
            ]
        },
        {"body": "자료상 18/20입니다.", "requester_notes": ""},
    )
    return _finish("require-hit", "pass", scored["status"], scored["reason"])
