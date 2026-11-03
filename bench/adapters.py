"""Offline fixture slot and an opt-in local command adapter.

The packaged OpenSocrates model path is the Codex SDK selector. That selector
returns a method-selection object and is not an artifact generator. This
harness does not import it and does not read ``auth.json``.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

from bench.contract import ENVELOPE_SCHEMA, REQUEST_SCHEMA, TRANSPORT_INSTRUCTION

_STDOUT_CAP = 100_000
_FIELD_CAP = 20_000


def command_argv(condition_id: str, env: Mapping[str, str]) -> list[str] | None:
    """Resolve an opted-in command. Return None when a live call must be skipped."""

    if env.get("OPENSOCRATES_BENCH_LIVE") != "1":
        return None
    specific = env.get(f"OPENSOCRATES_BENCH_COMMAND_{condition_id.upper()}")
    raw = specific if specific else env.get("OPENSOCRATES_BENCH_COMMAND")
    if not raw or not raw.strip():
        return None
    argv = shlex.split(raw)
    return argv or None


def build_request(case: Mapping[str, Any], condition: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": REQUEST_SCHEMA,
        "condition": condition["id"],
        "skill_text": condition.get("skill_text"),
        "prompt": case["prompt"],
        "materials": case["materials"],
        "transport": {
            "schema": ENVELOPE_SCHEMA,
            "instruction": TRANSPORT_INSTRUCTION,
        },
    }


def unavailable_reason(condition: Mapping[str, Any], *, live: bool) -> str:
    if condition.get("future"):
        slot = "future slot has no skill bytes"
    else:
        slot = "no recorded output for this condition"
    if live:
        return (
            "model_unavailable: "
            f"{slot}; OPENSOCRATES_BENCH_LIVE=1 and a command were not both set, "
            "so no model process was started"
        )
    return f"model_unavailable: {slot}; offline mode does not call a model"


def run_command(
    argv: list[str],
    request: Mapping[str, Any],
    *,
    timeout: float,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run one opted-in command. Never invent an envelope."""

    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    try:
        completed = subprocess.run(
            argv,
            input=payload,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=dict(os.environ if env is None else env),
        )
    except subprocess.TimeoutExpired:
        return _model_error("command timed out")
    except FileNotFoundError:
        return _unavailable("command executable was not found")
    except OSError as exc:
        return _model_error(f"command could not start: {exc.__class__.__name__}")
    if completed.returncode != 0:
        return _model_error(f"command exited with status {completed.returncode}")
    if len(completed.stdout) > _STDOUT_CAP:
        return _model_error("stdout exceeded the harness cap")
    return _envelope_from_stdout(completed.stdout)


def _envelope_from_stdout(stdout: bytes) -> dict[str, Any]:
    try:
        document = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return _model_error("stdout was not a bench envelope")
    if not isinstance(document, Mapping):
        return _model_error("stdout envelope was not a JSON object")
    if document.get("schema") != ENVELOPE_SCHEMA:
        return _model_error("stdout envelope schema did not match the bench transport")
    body = document.get("body")
    notes = document.get("requester_notes")
    if not isinstance(body, str) or not isinstance(notes, str):
        return _model_error("stdout envelope body and requester_notes must be strings")
    if len(body) > _FIELD_CAP or len(notes) > _FIELD_CAP:
        return _model_error("stdout envelope exceeded the field cap")
    return {
        "status": "ready",
        "reason": "command returned a bench envelope",
        "model_called": True,
        "envelope": {"body": body, "requester_notes": notes},
    }


def _model_error(reason: str) -> dict[str, Any]:
    return {
        "status": "model_error",
        "reason": f"model_error: {reason}",
        "model_called": True,
        "envelope": None,
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "model_unavailable",
        "reason": f"model_unavailable: {reason}",
        "model_called": False,
        "envelope": None,
    }


def probe_interpreter() -> str:
    return sys.executable
