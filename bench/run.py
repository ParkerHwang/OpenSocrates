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
    run_command,
    unavailable_reason,
)
from bench.cases import (
    expected_fixture_path,
    load_case_files,
    load_fixture,
    unexpected_fixture_paths,
)
from bench.conditions import audit_status, load_conditions
from bench.contract import ENVELOPE_SCHEMA, REPORT_SCHEMA
from bench.probes import run_probes
from bench.report import count_rows, exit_code, render_summary, write_outputs
from bench.scoring import score_envelope

_NOTE = (
    "This report scores public synthetic cases with deterministic rules on a "
    "bench-only envelope (body and requester_notes). Skill text is not rewritten "
    "to require English section headings. Fixture rows marked authored_example "
    "were written to exercise the scorer; they are not model outputs. "
    "model_unavailable means this run did not call a model for that row. "
    "Row counts are not pass rates and are not effect sizes."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--report", type=Path, default=Path("build/bench/report.json"))
    parser.add_argument("--summary", type=Path, default=Path("build/bench/summary.md"))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    report = build_report(root, mode=args.mode, timeout=args.timeout, env=dict(os.environ))
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
) -> dict[str, Any]:
    conditions, condition_errors = load_conditions(root)
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
    live_called = any(row["model_called"] for row in results)
    return {
        "schema": REPORT_SCHEMA,
        "mode": mode,
        "live_models_invoked": live_called,
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
        "counts": {"results": count_rows(results), "probes": count_rows(probes)},
        "classifier_probes": probes,
    }


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
            model_called=False,
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
    return _scored_row(case, condition["id"], fixture["envelope"], fixture, source)


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
            model_called=False,
        )
    outcome = run_command(argv, build_request(case, condition), timeout=timeout, env=env)
    if outcome["status"] != "ready":
        return _row(
            case_id=case["id"],
            condition=condition["id"],
            status=outcome["status"],
            reason=outcome["reason"],
            model_called=bool(outcome["model_called"]),
            origin="live_command",
        )
    return _scored_row(
        case,
        str(condition["id"]),
        outcome["envelope"],
        {
            "origin": "live_command",
            "model_called": True,
            "illustrates": "envelope returned by the opted-in local command",
        },
        None,
    )


def _scored_row(
    case: Mapping[str, Any],
    condition_id: str,
    envelope: Mapping[str, str],
    fixture: Mapping[str, Any],
    source: str | None,
) -> dict[str, Any]:
    scored = score_envelope(case, envelope)
    illustrates = str(fixture.get("illustrates") or "")
    reason = f"{scored['reason']}; origin={fixture['origin']}; model_called={str(fixture['model_called']).lower()}"
    if illustrates:
        reason = f"{reason}; {illustrates}"
    return _row(
        case_id=case["id"],
        condition=condition_id,
        status=scored["status"],
        reason=reason,
        model_called=bool(fixture["model_called"]),
        origin=str(fixture["origin"]),
        illustrates=illustrates or None,
        failed_checks=scored["failed_checks"],
        source=source,
    )


def _row(
    *,
    case_id: str | None,
    condition: str | None,
    status: str,
    reason: str,
    source: str | None = None,
    model_called: bool = False,
    origin: str | None = None,
    illustrates: str | None = None,
    failed_checks: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "case",
        "case_id": case_id,
        "condition": condition,
        "status": status,
        "reason": reason,
        "origin": origin,
        "model_called": model_called,
        "illustrates": illustrates,
        "failed_checks": failed_checks or [],
        "source": source,
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
        "forces_fixed_english_headers": item["forces_fixed_english_headers"],
        "forced_headers": item["forced_headers"],
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
