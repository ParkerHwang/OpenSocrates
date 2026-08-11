#!/usr/bin/env python3
"""Opt-in, privacy-safe integration contract for the real Claude selector.

The default offline suite never invokes this file. Set
``OPENSOCRATES_REAL_CLAUDE=1`` to run it with the user's existing Claude Code
login. Reports contain only categorical results, booleans, and the CLI version;
the prompt, catalog, stdout, stderr, credentials, and model output are never
printed or persisted.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from opensocrates.content import load_reasoning_content_projections
from opensocrates.domain.models import SelectionCatalog
from opensocrates.selector import (
    SelectorConfig,
    SelectorContextHandles,
    SelectorRequest,
    handles_for_request,
)
from opensocrates.selector.claude_cli import (
    ClaudeCliReasoningSelector,
    SelectorOutcome,
    _selector_environment,
)

ROOT = Path(__file__).resolve().parents[1]
OPT_IN_ENV = "OPENSOCRATES_REAL_CLAUDE"
SENSITIVE_ENVIRONMENT = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_MODEL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS",
)


class LiveCheckFailure(Exception):
    """A content-free live contract failure."""


class LiveCheckBlocked(Exception):
    """A content-free prerequisite blocker."""


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _selector_inputs() -> tuple[SelectorRequest, SelectorContextHandles, SelectionCatalog]:
    projections = load_reasoning_content_projections(
        ROOT / "content" / "compiled-reasoning-content.bundle.json"
    )
    request = SelectorRequest(
        prompt="Compare two reversible options using explicit evidence and choose one.",
        session_id="real-claude-contract",
    )
    effective, context = handles_for_request(
        request,
        SelectorConfig(transcript_access_enabled=False),
    )
    return effective, context, projections.selection_catalog


def _flag_value(command: list[str], flag: str) -> str | None:
    try:
        return command[command.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def _command_contract(executable: str, catalog: SelectionCatalog) -> dict[str, bool]:
    selector = ClaudeCliReasoningSelector(catalog, executable=executable)
    command = selector._command()  # noqa: SLF001 - this test owns the exact CLI boundary.
    if command is None:
        raise LiveCheckBlocked("claude_executable_missing")
    contract = {
        "safe_mode": "--safe-mode" in command,
        "plugins_disabled_by_safe_mode": "--safe-mode" in command,
        "no_session_persistence": "--no-session-persistence" in command,
        "json_output": _flag_value(command, "--output-format") == "json",
        "json_schema": _flag_value(command, "--json-schema") is not None,
        "built_in_tools_disabled": _flag_value(command, "--tools") == "",
        "mcp_tools_disallowed": _flag_value(command, "--disallowedTools") == "mcp__*",
        "strict_mcp_config": "--strict-mcp-config" in command,
        "permissions_noninteractive": _flag_value(command, "--permission-mode") == "dontAsk",
        "one_turn": _flag_value(command, "--max-turns") == "1",
        "fixed_effort": _flag_value(command, "--effort") == "medium",
    }
    if not all(contract.values()):
        raise LiveCheckFailure("selector_command_contract_failed")
    return contract


def _environment_contract() -> dict[str, bool]:
    previous = {key: os.environ.get(key) for key in SENSITIVE_ENVIRONMENT}
    try:
        for key in SENSITIVE_ENVIRONMENT:
            os.environ[key] = "opensocrates-synthetic-secret"
        environment = _selector_environment()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    contract = {
        "sensitive_environment_removed": not any(
            key in environment for key in SENSITIVE_ENVIRONMENT
        ),
        "recursion_guard_present": environment.get("OPENSOCRATES_SELECTOR_ACTIVE") == "1",
        "prompt_history_disabled": environment.get("CLAUDE_CODE_SKIP_PROMPT_HISTORY") == "1",
    }
    if not all(contract.values()):
        raise LiveCheckFailure("selector_environment_contract_failed")
    return contract


def _write_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o700)


def _subprocess_failure_contract(
    request: SelectorRequest,
    context: SelectorContextHandles,
    catalog: SelectionCatalog,
) -> dict[str, str]:
    cases = {
        "nonzero_exit": ("dd of=/dev/null 2>/dev/null; exit 9", 5, SelectorOutcome.NONZERO_EXIT),
        "timeout": ("sleep 5", 1, SelectorOutcome.TIMEOUT),
        "unparseable_output": (
            "dd of=/dev/null 2>/dev/null; printf '%s' 'not-json'",
            5,
            SelectorOutcome.INVALID_OUTPUT,
        ),
    }
    outcomes: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="opensocrates-real-claude-failures-") as name:
        root = Path(name)
        for case, (body, deadline, expected) in cases.items():
            executable = root / case
            _write_executable(executable, body)
            selector = ClaudeCliReasoningSelector(catalog, executable=str(executable))
            result = selector.select(
                request,
                context,
                deadline_seconds=deadline,
                reasoning_effort="medium",
            )
            outcome = selector.outcome_counts()
            if result is not None or outcome != {expected: 1}:
                raise LiveCheckFailure(f"{case}_diagnostic_failed")
            outcomes[case] = expected
    return outcomes


def _workspace_contract(
    request: SelectorRequest,
    context: SelectorContextHandles,
    catalog: SelectionCatalog,
) -> dict[str, bool]:
    candidate = {
        "structured_output": {
            "intervene": False,
            "selected_reasoning_systems": [],
            "instructions": "",
        }
    }
    with tempfile.TemporaryDirectory(prefix="opensocrates-real-claude-workspace-check-") as name:
        root = Path(name)
        executable = root / "workspace-probe"
        receipt = root / "cwd.txt"
        _write_executable(
            executable,
            "dd of=/dev/null 2>/dev/null; "
            f"pwd > {shlex.quote(str(receipt))}; "
            f"printf '%s' {shlex.quote(json.dumps(candidate, separators=(',', ':')))}",
        )
        selector = ClaudeCliReasoningSelector(catalog, executable=str(executable))
        result = selector.select(
            request,
            context,
            deadline_seconds=5,
            reasoning_effort="medium",
        )
        workspace = Path(receipt.read_text(encoding="utf-8").strip())
        contract = {
            "fresh_temporary_workspace": workspace.name.startswith("opensocrates-claude-selector-"),
            "workspace_removed_after_call": not workspace.exists(),
            "no_intervention_envelope_accepted": result is not None
            and selector.outcome_counts() == {SelectorOutcome.NO_INTERVENTION: 1},
        }
    if not all(contract.values()):
        raise LiveCheckFailure("selector_workspace_contract_failed")
    return contract


def _claude_version(executable: str) -> str:
    try:
        result = subprocess.run(
            [executable, "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise LiveCheckBlocked("claude_version_unavailable") from error
    if result.returncode != 0:
        raise LiveCheckBlocked("claude_version_unavailable")
    value = result.stdout.strip().split(maxsplit=1)[0]
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise LiveCheckBlocked("claude_version_unsupported")
    if tuple(map(int, parts)) < (2, 1, 205):
        raise LiveCheckBlocked("claude_version_unsupported")
    return value


def _require_authenticated(executable: str) -> None:
    try:
        result = subprocess.run(
            [executable, "auth", "status"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        payload = json.loads(result.stdout.decode("utf-8"))
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LiveCheckBlocked("claude_auth_status_unavailable") from error
    if result.returncode != 0 or payload.get("loggedIn") is not True:
        raise LiveCheckBlocked("claude_not_authenticated")


def _live_success(
    executable: str,
    request: SelectorRequest,
    context: SelectorContextHandles,
    catalog: SelectionCatalog,
) -> str:
    selector = ClaudeCliReasoningSelector(catalog, executable=executable)
    candidate = selector.select(
        request,
        context,
        deadline_seconds=30,
        reasoning_effort="medium",
    )
    outcomes = selector.outcome_counts()
    if len(outcomes) != 1 or sum(outcomes.values()) != 1:
        raise LiveCheckFailure("real_claude_outcome_invalid")
    [outcome] = outcomes
    if outcome not in {SelectorOutcome.SELECTED, SelectorOutcome.NO_INTERVENTION}:
        raise LiveCheckFailure(f"real_claude_{outcome}")
    if candidate is None:
        raise LiveCheckFailure("real_claude_candidate_missing")
    return outcome


def check(report_path: Path) -> int:
    report: dict[str, Any] = {
        "schema": "opensocrates.real-claude-selector/1.0.0",
        "status": "blocked",
        "privacy": {
            "prompt_persisted": False,
            "raw_output_persisted": False,
            "credentials_persisted": False,
            "reasoning_persisted": False,
        },
    }
    if os.environ.get(OPT_IN_ENV) != "1":
        report["status"] = "skipped"
        report["blocker"] = "opt_in_required"
        _write_report(report_path, report)
        print("real-claude-selector: SKIP blocker=opt_in_required")
        return 0

    executable = shutil.which(os.environ.get("CLAUDE_BIN", "claude"))
    if executable is None:
        report["blocker"] = "claude_executable_missing"
        _write_report(report_path, report)
        print("real-claude-selector: BLOCKED blocker=claude_executable_missing")
        return 2

    request, context, catalog = _selector_inputs()
    try:
        report["command_contract"] = _command_contract(executable, catalog)
        report["environment_contract"] = _environment_contract()
        report["workspace_contract"] = _workspace_contract(request, context, catalog)
        report["failure_diagnostics"] = _subprocess_failure_contract(
            request,
            context,
            catalog,
        )
        report["cli_version"] = _claude_version(executable)
        _require_authenticated(executable)
        report["live_outcome"] = _live_success(executable, request, context, catalog)
    except LiveCheckBlocked as error:
        report["blocker"] = str(error)
        _write_report(report_path, report)
        print(f"real-claude-selector: BLOCKED blocker={error}")
        return 2
    except LiveCheckFailure as error:
        report["status"] = "fail"
        report["diagnostic"] = str(error)
        _write_report(report_path, report)
        print(f"real-claude-selector: FAIL diagnostic={error}")
        return 1

    report["status"] = "pass"
    _write_report(report_path, report)
    print("real-claude-selector: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default="build/evidence/real-claude-selector.json",
        help="privacy-safe categorical report path",
    )
    args = parser.parse_args(argv)
    return check((ROOT / args.report).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
