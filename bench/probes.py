"""Classifier probes. These rows are not benchmark cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bench.adapters import attest_model_call, build_request, probe_interpreter, run_command
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
        _negation_booking_probe(),
        _stale_capacity_probe(),
        _asserted_booking_probe(),
        _bare_capacity_probe(),
        _hedged_booking_probe(),
        _reversed_stale_probe(),
        _paraphrase_blind_spot_probe(),
        _public_synthetic_request_probe(),
        _date_in_body_probe(),
        _date_ambiguous_probe(),
        _date_omitted_probe(),
        _invented_calendar_date_probe(),
        _bad_expected_status_probe(),
        _quoted_rate_denial_probe(),
        _material_rate_denial_probe(),
        _bare_wrong_rate_probe(),
        _hedged_rate_probe(),
        _flipped_rate_denial_probe(),
        _oversize_section_probe(),
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


def _e01_check(check_id: str, body: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "cases" / "e01-venue-messages.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    checks = [item for item in case["checks"] if item["id"] == check_id]
    return score_envelope({"checks": checks}, {"body": body, "requester_notes": ""})


def _negation_booking_probe() -> dict[str, Any]:
    scored = _e01_check("no-confirmed-booking", "예약이 확정되지 않았습니다")
    return _finish(
        "negation-not-a-booking",
        "pass",
        scored["status"],
        "예약이 확정되지 않았습니다 is a listed denial, not a confirmed booking",
    )


def _stale_capacity_probe() -> dict[str, Any]:
    first = _e01_check("omit-stale-capacity", "예전 메모의 35명은 오래된 값입니다")
    second = _e01_check("omit-stale-capacity", "예전 메모의 35명은 오래된 값")
    ok = first["status"] == "pass" and second["status"] == "pass"
    return _finish(
        "stale-35-warning",
        "pass",
        "pass" if ok else first["status"],
        "quoting 35명 as an outdated memo value is a listed exception",
        ok=ok,
    )


def _asserted_booking_probe() -> dict[str, Any]:
    scored = _e01_check("no-confirmed-booking", "예약이 확정되었습니다")
    return _finish(
        "asserted-booking",
        "condition_fail",
        scored["status"],
        scored["reason"],
    )


def _bare_capacity_probe() -> dict[str, Any]:
    scored = _e01_check("omit-stale-capacity", "수용 인원은 35명입니다")
    return _finish(
        "bare-35-as-current",
        "condition_fail",
        scored["status"],
        scored["reason"],
    )


def _hedged_booking_probe() -> dict[str, Any]:
    scored = _e01_check("no-confirmed-booking", "예약이 확정된 바 없습니다")
    return _finish(
        "hedged-booking-unresolved",
        "needs_human_review",
        scored["status"],
        "nearby denial cue without a listed exception stays unresolved",
    )


def _reversed_stale_probe() -> dict[str, Any]:
    scored = _e01_check("omit-stale-capacity", "35명은 오래된 값이 아닙니다")
    return _finish(
        "reversed-stale-warning",
        "needs_human_review",
        scored["status"],
        "a listed stale phrase followed by a denial is unresolved, not a pass",
    )


def _bad_expected_status_probe() -> dict[str, Any]:
    import tempfile

    from bench.cases import _read_regression
    from bench.contract import ENVELOPE_SCHEMA, REGRESSION_SCHEMA
    from bench.run import _score_regressions

    envelope = {"schema": ENVELOPE_SCHEMA, "body": "x", "requester_notes": ""}
    base = {
        "schema": REGRESSION_SCHEMA,
        "case_id": "e01-venue-messages",
        "label": "bad-status",
        "framing": "Post-hoc example added for validation. Not an independent holdout.",
        "envelope": envelope,
    }
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, status in (("array", ["pass"]), ("object", {"status": "pass"})):
            path = root / f"{name}.json"
            path.write_text(
                json.dumps({**base, "expected_status": status}),
                encoding="utf-8",
            )
            loaded = _read_regression(path, root)
            rows.extend(_score_regressions([], [loaded]))
    ok = (
        len(rows) == 2
        and all(row["status"] == "input_error" and row["matched"] is False for row in rows)
        and all("expected_status" in row["reason"] for row in rows)
    )
    return _finish(
        "expected-status-type",
        "input_error",
        "input_error" if ok else "crash-or-miss",
        "a list or object expected_status is input_error, not an uncaught TypeError",
        ok=ok,
    )


def _date_in_body_probe() -> dict[str, Any]:
    scored = _e01_check(
        "unresolved-date-stated",
        "장소 담당자와 접수 자원봉사자에게: 행사 날짜는 아직 정해지지 않았습니다.",
    )
    empty_notes = scored["status"] == "pass"
    return _finish(
        "date-clear-in-body",
        "pass",
        scored["status"],
        "a clear unresolved date in the body does not require a canned requester_notes phrase",
        ok=empty_notes,
    )


def _date_ambiguous_probe() -> dict[str, Any]:
    scored = _e01_check("unresolved-date-stated", "날짜에 대해 나중에 다시 보겠습니다.")
    return _finish(
        "date-wording-ambiguous",
        "needs_human_review",
        scored["status"],
        "mentioning a date without saying whether it is set stays unresolved",
    )


def _date_omitted_probe() -> dict[str, Any]:
    scored = _e01_check("unresolved-date-stated", "수용 인원은 24명입니다.")
    return _finish(
        "date-status-omitted",
        "condition_fail",
        scored["status"],
        "silence about the date is still a miss",
    )


def _invented_calendar_date_probe() -> dict[str, Any]:
    scored = _e01_check(
        "no-invented-date", "행사일은 5월 12일입니다. 행사 날짜는 아직 정해지지 않았습니다."
    )
    return _finish(
        "invented-calendar-date",
        "condition_fail",
        scored["status"],
        "an unlisted calendar date still fails even when unresolved-date wording is present",
    )


def _public_synthetic_request_probe() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "cases" / "e01-venue-messages.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    condition = {"id": "baseline", "skill_text": None}
    claimed = build_request(case, condition)
    missing = build_request({"prompt": "x", "materials": []}, condition)
    denied = build_request({"prompt": "x", "materials": [], "public_synthetic": False}, condition)
    ok = (
        claimed.get("public_synthetic") is True
        and "public_synthetic" in missing
        and missing.get("public_synthetic") is None
        and denied.get("public_synthetic") is False
    )
    return _finish(
        "public-synthetic-claim",
        "claim",
        "claim" if ok else "dropped",
        "public_synthetic is the author's claim in the adapter request; true is not certification",
        ok=ok,
    )


def _paraphrase_blind_spot_probe() -> dict[str, Any]:
    sentences = (
        "자리를 잡아 두었습니다",
        "수용 인원은 삼십오 명입니다",
        "예약이 채택되었습니다",
    )
    statuses = [
        _e01_check("no-confirmed-booking", sentences[0])["status"],
        _e01_check("omit-stale-capacity", sentences[1])["status"],
        _e01_check("no-confirmed-booking", sentences[2])["status"],
    ]
    missed = statuses == ["pass", "pass", "pass"]
    return _finish(
        "paraphrase-blind-spot",
        "blind_spot",
        "blind_spot" if missed else "caught",
        "literal rules miss 잡아 두었습니다, 삼십오 명, and 채택되었습니다; "
        "that miss is not a semantic pass and is not solved",
        ok=missed,
    )


def _calc_body(body: str, *, materials: list[str] | None = None) -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "cases" / "calc-unverified-rate.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    if materials is not None:
        case = dict(case)
        case["materials"] = materials
        case["checks"] = [
            dict(case["checks"][0]),
        ]
        case["checks"][0]["clear_exceptions"] = []
    return score_envelope(case, {"body": body, "requester_notes": ""})


def _quoted_rate_denial_probe() -> dict[str, Any]:
    scored = _calc_body(
        "예시 이전은 20개 중 18개입니다. 18/20은 90%입니다. "
        "100% 완료를 확인한 사람이나 시스템은 없습니다."
    )
    return _finish(
        "quoted-100-denial",
        "pass",
        scored["status"],
        "90% for 18/20 plus a quoted denial of 100% verification is not a wrong rate",
    )


def _material_rate_denial_probe() -> dict[str, Any]:
    material = "100% 완료를 확인해 준 사람이나 시스템은 없다."
    scored = _calc_body(
        f"예시 이전은 20개 중 18개입니다. 18/20은 90%입니다. {material}",
        materials=[material],
    )
    return _finish(
        "material-100-denial",
        "pass",
        scored["status"],
        "a percent inside the material's own denial is not a rate claim",
    )


def _bare_wrong_rate_probe() -> dict[str, Any]:
    scored = _calc_body("예시 이전은 20개 중 18개입니다. 완료율은 100%입니다.")
    return _finish(
        "bare-wrong-rate",
        "condition_fail",
        scored["status"],
        scored["reason"],
    )


def _hedged_rate_probe() -> dict[str, Any]:
    scored = _calc_body("예시 이전은 20개 중 18개입니다. 100%가 아닙니다.")
    return _finish(
        "hedged-wrong-rate",
        "needs_human_review",
        scored["status"],
        "a mismatched percent next to a denial cue, outside a listed exception, stays unresolved",
    )


def _flipped_rate_denial_probe() -> dict[str, Any]:
    scored = _calc_body(
        "예시 이전은 20개 중 18개입니다. 18/20은 90%입니다. "
        "100% 완료를 확인한 사람이나 시스템은 없지 않습니다."
    )
    return _finish(
        "flipped-rate-denial",
        "needs_human_review",
        scored["status"],
        "a denial prefix followed by 지 않습니다 is not a clean exception",
    )


def _oversize_section_probe() -> dict[str, Any]:
    from bench.contract import MAX_SCORED_SECTION_CHARS

    piece = "100% 완료를 확인한 사람이나 시스템은 없습니다. "
    repeats = (MAX_SCORED_SECTION_CHARS // len(piece)) + 2
    scored = _calc_body("18/20은 90%입니다. " + (piece * repeats))
    return _finish(
        "oversize-section",
        "input_error",
        scored["status"],
        f"a section over {MAX_SCORED_SECTION_CHARS} characters is rejected before span scans",
    )
