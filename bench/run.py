"""Run the public synthetic bench in offline or opted-in live mode."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bench.adapters import (
    build_request,
    command_argv,
    execution_evidence,
    not_run_evidence,
    run_command,
    unavailable_reason,
)
from bench.cases import (
    expected_fixture_path,
    load_case_files,
    load_fixture,
    load_regression_files,
    unexpected_fixture_paths,
)
from bench.conditions import audit_status, load_conditions
from bench.contract import (
    ATTESTATION_SCHEMA,
    ENVELOPE_SCHEMA,
    MODEL_CALL_NOT_APPLICABLE,
    MODEL_CALL_UNVERIFIED,
    MODEL_CALL_VERIFIED,
    REPORT_SCHEMA,
)
from bench.probes import run_probes
from bench.report import count_rows, exit_code, render_summary, write_outputs
from bench.scoring import score_envelope

_NOTE = (
    "This report scores public synthetic cases with deterministic rules on a "
    "bench-only envelope (body and requester_notes). Skill text is not rewritten "
    "to require English section headings. Fixture rows marked authored_example "
    "were written to exercise the scorer; they are not model outputs. "
    "A parsed envelope does not verify a model call. model_called is true only "
    "for a host attestation recorded by harness code. Row counts are not pass "
    "rates and are not effect sizes. A forbid match that is only a nearby "
    "hedge or denial cue is needs_human_review, not pass or fail. Literal "
    "rules miss paraphrases; that miss is a blind spot, not a semantic pass. "
    "A product evidence scanner is not this judge."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--report", type=Path, default=Path("build/bench/report.json"))
    parser.add_argument("--summary", type=Path, default=Path("build/bench/summary.md"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--output-brief-pin",
        type=Path,
        help="Compare another output_brief file without replacing the documented pin",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    report = build_report(
        root,
        mode=args.mode,
        timeout=args.timeout,
        env=dict(os.environ),
        output_brief_pin=args.output_brief_pin,
    )
    try:
        write_outputs(report, args.report, args.summary)
    except OSError as exc:
        print(f"bench: could not write the report: {exc}", file=sys.stderr)
        return 2
    print(render_summary(report), end="")
    print(f"bench: wrote {args.report} and {args.summary}")
    return exit_code(report)


def build_report(
    root: Path,
    *,
    mode: str,
    timeout: float,
    env: Mapping[str, str],
    output_brief_pin: Path | None = None,
) -> dict[str, Any]:
    conditions, condition_errors = load_conditions(root, output_brief_pin=output_brief_pin)
    records = load_case_files(root)
    results: list[dict[str, Any]] = []
    expected: list[Path] = []
    if condition_errors:
        results.append(
            _row(
                case_id=None,
                condition=None,
                status="input_error",
                reason="input_error: " + "; ".join(condition_errors),
                source="bench/conditions/manifest.json",
            )
        )
    for record in records:
        if record["case"] is None:
            results.append(
                _row(
                    case_id=record.get("case_id"),
                    condition=None,
                    status="input_error",
                    reason="input_error: " + "; ".join(record["errors"]),
                    source=record["source"],
                )
            )
            continue
        case = record["case"]
        for condition in conditions:
            path = expected_fixture_path(root, case["id"], condition["id"])
            expected.append(path)
            results.append(_condition_row(root, case, condition, path, mode, timeout, env))
    for path in unexpected_fixture_paths(root, set(expected)):
        results.append(
            _row(
                case_id=None,
                condition=None,
                status="input_error",
                reason="input_error: fixture is outside the case and condition slots",
                source=path.relative_to(root).as_posix(),
            )
        )
    probes = run_probes()
    regressions = _score_regressions(records, load_regression_files(root))
    evidence = _model_evidence(results)
    return {
        "schema": REPORT_SCHEMA,
        "mode": mode,
        "live_models_invoked": evidence["verified_model_calls"] > 0,
        "model_evidence": evidence,
        "codex_selector_invoked": False,
        "effect_sizes_computed": False,
        "comparison_allowed": False,
        "envelope": ENVELOPE_SCHEMA,
        "commit": _git_head(root),
        "note": _NOTE,
        "conditions": [_public_condition(item) for item in conditions],
        "skill_audit": {
            "status": audit_status(conditions, condition_errors),
            "errors": condition_errors,
        },
        "results": results,
        "regressions": regressions,
        "regression_framing": (
            "Regression envelopes are post-hoc examples added after a rule change. "
            "They are not independent holdouts and are not a performance estimate."
        ),
        "counts": {"results": count_rows(results), "probes": count_rows(probes)},
        "classifier_probes": probes,
    }


def _score_regressions(
    records: list[dict[str, Any]],
    loaded: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cases = {
        record["case"]["id"]: record["case"] for record in records if record.get("case") is not None
    }
    rows: list[dict[str, Any]] = []
    for item in loaded:
        if item["errors"]:
            rows.append(
                {
                    "source": item["source"],
                    "label": None,
                    "case_id": None,
                    "expected_status": None,
                    "status": "input_error",
                    "matched": False,
                    "framing": None,
                    "reason": "; ".join(item["errors"]),
                }
            )
            continue
        case = cases.get(item["case_id"])
        if case is None:
            rows.append(
                {
                    "source": item["source"],
                    "label": item["label"],
                    "case_id": item["case_id"],
                    "expected_status": item["expected_status"],
                    "status": "input_error",
                    "matched": False,
                    "framing": item["framing"],
                    "reason": "case id is not loaded",
                }
            )
            continue
        scored = score_envelope(case, item["envelope"])
        rows.append(
            {
                "source": item["source"],
                "label": item["label"],
                "case_id": item["case_id"],
                "expected_status": item["expected_status"],
                "status": scored["status"],
                "matched": scored["status"] == item["expected_status"],
                "framing": item["framing"],
                "reason": scored["reason"],
            }
        )
    return rows


def _condition_row(
    root: Path,
    case: Mapping[str, Any],
    condition: Mapping[str, Any],
    path: Path,
    mode: str,
    timeout: float,
    env: Mapping[str, str],
) -> dict[str, Any]:
    if mode == "live":
        return _live_row(case, condition, timeout, env)
    if not path.is_file():
        return _row(
            case_id=case["id"],
            condition=condition["id"],
            status="model_unavailable",
            reason=unavailable_reason(condition, live=False),
            evidence=not_run_evidence(),
        )
    fixture, errors = load_fixture(
        path,
        root=root,
        case_id=case["id"],
        condition=condition["id"],
    )
    source = path.relative_to(root).as_posix()
    if fixture is None:
        return _row(
            case_id=case["id"],
            condition=condition["id"],
            status="input_error",
            reason="input_error: " + "; ".join(errors or ["fixture could not be read"]),
            source=source,
        )
    return _scored_row(
        case,
        condition["id"],
        fixture["envelope"],
        fixture,
        source,
        evidence=_fixture_evidence(str(fixture["origin"])),
    )


def _live_row(
    case: Mapping[str, Any],
    condition: Mapping[str, Any],
    timeout: float,
    env: Mapping[str, str],
) -> dict[str, Any]:
    argv = command_argv(str(condition["id"]), env)
    if argv is None:
        return _row(
            case_id=case["id"],
            condition=condition["id"],
            status="model_unavailable",
            reason=unavailable_reason(condition, live=True),
            evidence=not_run_evidence(),
        )
    outcome = run_command(argv, build_request(case, condition), timeout=timeout, env=env)
    if outcome["status"] != "ready":
        return _row(
            case_id=case["id"],
            condition=condition["id"],
            status=outcome["status"],
            reason=outcome["reason"],
            origin="live_command",
            evidence=outcome,
        )
    return _scored_row(
        case,
        str(condition["id"]),
        outcome["envelope"],
        {
            "origin": "live_command",
            "illustrates": (
                "command returned a bench envelope; that envelope is not host evidence "
                "of a model call"
            ),
        },
        None,
        evidence=outcome,
    )


def _scored_row(
    case: Mapping[str, Any],
    condition_id: str,
    envelope: Mapping[str, str],
    fixture: Mapping[str, Any],
    source: str | None,
    *,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    scored = score_envelope(case, envelope)
    illustrates = str(fixture.get("illustrates") or "")
    reason = (
        f"{scored['reason']}; origin={fixture['origin']}; "
        f"model_call={evidence['model_call']}; "
        f"process_started={str(bool(evidence['process_started'])).lower()}; "
        f"envelope_received={str(bool(evidence['envelope_received'])).lower()}"
    )
    if illustrates:
        reason = f"{reason}; {illustrates}"
    return _row(
        case_id=case["id"],
        condition=condition_id,
        status=scored["status"],
        reason=reason,
        origin=str(fixture["origin"]),
        illustrates=illustrates or None,
        failed_checks=scored["failed_checks"],
        unresolved_checks=scored["unresolved_checks"],
        source=source,
        evidence=evidence,
    )


def _fixture_evidence(origin: str) -> dict[str, Any]:
    model_call = MODEL_CALL_NOT_APPLICABLE
    if origin == "recorded_model_output":
        model_call = MODEL_CALL_UNVERIFIED
    return execution_evidence(
        execution_attempted=False,
        process_started=False,
        envelope_received=True,
        model_call=model_call,
    )


def _row(
    *,
    case_id: str | None,
    condition: str | None,
    status: str,
    reason: str,
    source: str | None = None,
    origin: str | None = None,
    illustrates: str | None = None,
    failed_checks: list[dict[str, str]] | None = None,
    unresolved_checks: list[dict[str, str]] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    fields = _normalized_evidence(evidence or not_run_evidence())
    return {
        "kind": "case",
        "case_id": case_id,
        "condition": condition,
        "status": status,
        "reason": reason,
        "origin": origin,
        "illustrates": illustrates,
        "failed_checks": failed_checks or [],
        "unresolved_checks": unresolved_checks or [],
        "source": source,
        **fields,
    }


def _public_condition(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "future": item["future"],
        "description": item["description"],
        "skill_path": item["skill_path"],
        "skill_sha256": item["skill_sha256"],
        "skill_bytes": item["skill_bytes"],
        "provenance": item["provenance"],
        "pin": item.get("pin"),
        "forces_fixed_english_headers": item["forces_fixed_english_headers"],
        "forced_headers": item["forced_headers"],
    }


def _normalized_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    model_call = evidence.get("model_call")
    attestation = evidence.get("model_attestation")
    if model_call not in {MODEL_CALL_VERIFIED, MODEL_CALL_UNVERIFIED, MODEL_CALL_NOT_APPLICABLE}:
        model_call = MODEL_CALL_UNVERIFIED
    if model_call == MODEL_CALL_VERIFIED and not _trusted_attestation(attestation):
        model_call = MODEL_CALL_UNVERIFIED
        attestation = None
    if model_call != MODEL_CALL_VERIFIED:
        attestation = None
    return {
        "execution_attempted": bool(evidence.get("execution_attempted")),
        "process_started": bool(evidence.get("process_started")),
        "envelope_received": bool(evidence.get("envelope_received")),
        "model_call": model_call,
        "model_called": model_call == MODEL_CALL_VERIFIED,
        "model_attestation": attestation,
    }


def _trusted_attestation(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    adapter = value.get("adapter")
    host = value.get("host")
    return (
        value.get("schema") == ATTESTATION_SCHEMA
        and value.get("observed_by") == "harness"
        and isinstance(adapter, str)
        and bool(adapter.strip())
        and isinstance(host, str)
        and bool(host.strip())
    )


def _model_evidence(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rule": (
            "model_called and live_models_invoked are true only when harness "
            "code records a host attestation. A valid envelope does not verify a model call."
        ),
        "verified_model_calls": sum(row["model_call"] == MODEL_CALL_VERIFIED for row in results),
        "unverified_model_calls": sum(
            row["model_call"] == MODEL_CALL_UNVERIFIED for row in results
        ),
        "command_processes_started": sum(bool(row["process_started"]) for row in results),
        "command_envelopes_received": sum(
            bool(row["process_started"] and row["envelope_received"]) for row in results
        ),
    }


def _git_head(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


if __name__ == "__main__":
    raise SystemExit(main())
