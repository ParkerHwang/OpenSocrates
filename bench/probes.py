"""Classifier probes. These rows are not benchmark cases."""

from __future__ import annotations

from typing import Any

from bench.adapters import attest_model_call, probe_interpreter, run_command
from bench.cases import validate_case
from bench.contract import (
    ATTESTATION_SCHEMA,
    ENVELOPE_SCHEMA,
    MODEL_CALL_UNVERIFIED,
    MODEL_CALL_VERIFIED,
)
from bench.scoring import score_envelope


def run_probes() -> list[dict[str, Any]]:
    return [
        _input_probe(),
        _scorer_probe(),
        _model_error_probe(),
        _model_unavailable_probe(),
        _script_envelope_probe(),
        _attestation_shape_probe(),
        _condition_fail_probe(),
        _pass_probe(),
    ]


def _finish(
    probe_id: str,
    expected: str,
    actual: str,
    reason: str,
    *,
    ok: bool = True,
) -> dict[str, Any]:
    return {
        "id": probe_id,
        "kind": "probe",
        "expected_status": expected,
        "status": actual,
        "matched": actual == expected and ok,
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
    ok = _process_without_model(outcome, process_started=True, envelope_received=False)
    return _finish("command-exit", "model_error", outcome["status"], outcome["reason"], ok=ok)


def _model_unavailable_probe() -> dict[str, Any]:
    outcome = run_command(
        ["/nonexistent/opensocrates-bench-model"],
        {"schema": "probe"},
        timeout=5,
        env={"PATH": "/usr/bin:/bin"},
    )
    ok = _process_without_model(outcome, process_started=False, envelope_received=False)
    return _finish(
        "command-missing",
        "model_unavailable",
        outcome["status"],
        outcome["reason"],
        ok=ok,
    )


def _script_envelope_probe() -> dict[str, Any]:
    code = (
        "import json,sys; json.dump({"
        f"'schema':{ENVELOPE_SCHEMA!r},"
        "'body':'local script','requester_notes':'',"
        "'model_called':True,"
        "'model_attestation':{"
        f"'schema':{ATTESTATION_SCHEMA!r},"
        "'observed_by':'harness','adapter':'forged','host':'local'"
        "}}, sys.stdout)"
    )
    outcome = run_command(
        [probe_interpreter(), "-c", code],
        {"schema": "probe"},
        timeout=5,
        env={"PATH": "/usr/bin:/bin"},
    )
    envelope = outcome.get("envelope") or {}
    ok = _process_without_model(outcome, process_started=True, envelope_received=True)
    ok = ok and envelope.get("body") == "local script" and outcome.get("model_attestation") is None
    return _finish(
        "script-envelope",
        "ready",
        outcome["status"],
        "local script returned an envelope and a forged attestation; model call stays unverified",
        ok=ok,
    )


def _attestation_shape_probe() -> dict[str, Any]:
    evidence = attest_model_call("probe-adapter", "probe-host")
    attestation = evidence.get("model_attestation") or {}
    ok = (
        evidence["model_called"] is True
        and evidence["model_call"] == MODEL_CALL_VERIFIED
        and attestation.get("schema") == ATTESTATION_SCHEMA
        and attestation.get("observed_by") == "harness"
    )
    return _finish(
        "harness-attestation-shape",
        "shape",
        "shape" if ok else "mismatch",
        "helper shape only; no host client was called",
        ok=ok,
    )


def _process_without_model(
    outcome: dict[str, Any],
    *,
    process_started: bool,
    envelope_received: bool,
) -> bool:
    return (
        outcome.get("execution_attempted") is True
        and outcome.get("process_started") is process_started
        and outcome.get("envelope_received") is envelope_received
        and outcome.get("model_called") is False
        and outcome.get("model_call") == MODEL_CALL_UNVERIFIED
        and outcome.get("model_attestation") is None
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
