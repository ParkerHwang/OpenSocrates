#!/usr/bin/env python3
"""Opt-in aggregate structured-output reliability matrix for Claude Code."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

from check_real_claude import (
    LiveCheckBlocked,
    _claude_version,
    _require_authenticated,
    _selector_inputs,
    _write_report,
)
from opensocrates.domain.models import SelectionCatalog
from opensocrates.selector import SelectorConfig, SelectorRequest, handles_for_request
from opensocrates.selector.claude_cli import ClaudeCliReasoningSelector, SelectorOutcome

ROOT = Path(__file__).resolve().parents[1]
OPT_IN_ENV = "OPENSOCRATES_CLAUDE_RELIABILITY"
RUNS_ENV = "OPENSOCRATES_CLAUDE_RELIABILITY_RUNS"
MODELS_ENV = "OPENSOCRATES_CLAUDE_RELIABILITY_MODELS"
MINIMUM_RUNS = 20
MAXIMUM_RUNS = 50
MAXIMUM_MODELS = 4
REQUIRED_PERCENT = 95
FIXTURES = (
    "Choose whether a reversible pilot should precede a wider rollout using explicit evidence.",
    "Compare two measurement plans and select the one with the clearer falsification test.",
    "Decide whether one additional bounded experiment has enough information value to run.",
    "Assess two low-risk options and identify the more robust choice under uncertainty.",
)


class MatrixConfigurationError(Exception):
    """An invalid bounded matrix request."""


def _runs() -> int:
    raw = os.environ.get(RUNS_ENV, str(MINIMUM_RUNS))
    try:
        value = int(raw)
    except ValueError as error:
        raise MatrixConfigurationError("runs_not_an_integer") from error
    if not MINIMUM_RUNS <= value <= MAXIMUM_RUNS:
        raise MatrixConfigurationError("runs_out_of_bounds")
    return value


def _models() -> tuple[str | None, ...]:
    raw = os.environ.get(MODELS_ENV, "").strip()
    if not raw:
        return (None,)
    values = tuple(item.strip() for item in raw.split(","))
    if (
        not values
        or len(values) > MAXIMUM_MODELS
        or any(not item for item in values)
        or len(set(values)) != len(values)
        or "host-default" in values
    ):
        raise MatrixConfigurationError("model_list_invalid")
    return values


def _required_valid(attempts: int) -> int:
    return (attempts * REQUIRED_PERCENT + 99) // 100


def _row(
    *,
    executable: str,
    cli_version: str,
    model: str | None,
    attempts: int,
    catalog: SelectionCatalog,
) -> dict[str, Any]:
    try:
        selector = ClaudeCliReasoningSelector(catalog, executable=executable, model=model)
    except ValueError as error:
        raise MatrixConfigurationError("model_identifier_invalid") from error
    counts = {outcome: 0 for outcome in SelectorOutcome.ALL}
    for index in range(attempts):
        request = SelectorRequest(
            prompt=FIXTURES[index % len(FIXTURES)],
            session_id=f"claude-reliability-{index}",
        )
        effective, context = handles_for_request(
            request,
            SelectorConfig(transcript_access_enabled=False),
        )
        selector.select(
            effective,
            context,
            deadline_seconds=30,
            reasoning_effort="medium",
        )
    observed = selector.outcome_counts()
    for outcome, count in observed.items():
        if outcome not in counts or type(count) is not int or count < 0:
            raise MatrixConfigurationError("selector_outcome_invalid")
        counts[outcome] = count
    if sum(counts.values()) != attempts:
        raise MatrixConfigurationError("selector_attempt_count_mismatch")
    valid = counts[SelectorOutcome.SELECTED] + counts[SelectorOutcome.NO_INTERVENTION]
    required = _required_valid(attempts)
    return {
        "cli_version": cli_version,
        "model": model or "host-default",
        "attempts": attempts,
        "valid_structured_outputs": valid,
        "required_valid_structured_outputs": required,
        "valid_percent": (valid * 100) // attempts,
        "outcomes": counts,
        "threshold_met": valid >= required,
        "supported": valid >= required,
    }


def check(report_path: Path) -> int:
    report: dict[str, Any] = {
        "schema": "opensocrates.claude-structured-output-matrix/1.0.0",
        "status": "blocked",
        "threshold": {
            "minimum_attempts_per_row": MINIMUM_RUNS,
            "required_valid_percent": REQUIRED_PERCENT,
            "max_turns": 1,
        },
        "fallback": "fail_open_with_fixed_content_free_outcome",
        "rows": [],
        "privacy": {
            "prompts_persisted": False,
            "raw_output_persisted": False,
            "credentials_persisted": False,
            "candidates_persisted": False,
            "reasoning_persisted": False,
        },
    }
    if os.environ.get(OPT_IN_ENV) != "1":
        report["status"] = "skipped"
        report["blocker"] = "opt_in_required"
        _write_report(report_path, report)
        print("claude-structured-output-matrix: SKIP blocker=opt_in_required")
        return 0

    executable = shutil.which(os.environ.get("CLAUDE_BIN", "claude"))
    if executable is None:
        report["blocker"] = "claude_executable_missing"
        _write_report(report_path, report)
        print("claude-structured-output-matrix: BLOCKED blocker=claude_executable_missing")
        return 2
    try:
        attempts = _runs()
        models = _models()
        cli_version = _claude_version(executable)
        report["cli_version"] = cli_version
        _require_authenticated(executable)
        _request, _context, catalog = _selector_inputs()
        rows = [
            _row(
                executable=executable,
                cli_version=cli_version,
                model=model,
                attempts=attempts,
                catalog=catalog,
            )
            for model in models
        ]
    except LiveCheckBlocked as error:
        report["blocker"] = str(error)
        _write_report(report_path, report)
        print(f"claude-structured-output-matrix: BLOCKED blocker={error}")
        return 2
    except MatrixConfigurationError as error:
        report["status"] = "fail"
        report["diagnostic"] = str(error)
        _write_report(report_path, report)
        print(f"claude-structured-output-matrix: FAIL diagnostic={error}")
        return 1

    report["rows"] = rows
    if all(row["threshold_met"] is True for row in rows):
        report["status"] = "pass"
        _write_report(report_path, report)
        print("claude-structured-output-matrix: PASS")
        return 0
    report["status"] = "fail"
    report["diagnostic"] = "reliability_threshold_not_met"
    _write_report(report_path, report)
    print("claude-structured-output-matrix: FAIL diagnostic=reliability_threshold_not_met")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default="build/evidence/claude-structured-output-matrix.json",
        help="privacy-safe aggregate report path",
    )
    args = parser.parse_args(argv)
    return check((ROOT / args.report).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
