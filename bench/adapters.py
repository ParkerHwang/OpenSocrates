"""Offline fixture slot and an opt-in local command adapter.

The packaged OpenSocrates model path is the Codex SDK selector. That selector
returns a method-selection object and is not an artifact generator. This
harness does not import it and does not read ``auth.json``.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

from bench.contract import (
    ATTESTATION_SCHEMA,
    ENVELOPE_SCHEMA,
    MODEL_CALL_NOT_APPLICABLE,
    MODEL_CALL_UNVERIFIED,
    MODEL_CALL_VERIFIED,
    MODEL_CALLS,
    REQUEST_SCHEMA,
    TRANSPORT_INSTRUCTION,
)

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


def public_synthetic_claim(case: Mapping[str, Any]) -> bool | None:
    """Return the author's boolean claim, or None when it is absent or not boolean.

    ``True`` is the author's claim. It does not certify that the materials are
    public or synthetic.
    """

    value = case.get("public_synthetic")
    if isinstance(value, bool):
        return value
    return None


def build_request(case: Mapping[str, Any], condition: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": REQUEST_SCHEMA,
        "condition": condition["id"],
        "public_synthetic": public_synthetic_claim(case),
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
            f"model_unavailable: {slot}; no command process was started; model call not applicable"
        )
    return f"model_unavailable: {slot}; offline mode starts no command process"


def execution_evidence(
    *,
    execution_attempted: bool,
    process_started: bool,
    envelope_received: bool,
    model_call: str,
) -> dict[str, Any]:
    """Separate process evidence from a verified model call.

    ``model_call`` is ``verified`` only when harness code observed a host
    client. Command stdout cannot set it.
    """

    if model_call not in MODEL_CALLS:
        raise ValueError(f"unknown model_call: {model_call}")
    return {
        "execution_attempted": execution_attempted,
        "process_started": process_started,
        "envelope_received": envelope_received,
        "model_call": model_call,
        "model_called": model_call == MODEL_CALL_VERIFIED,
        "model_attestation": None,
    }


def attest_model_call(adapter_id: str, host: str) -> dict[str, Any]:
    """Attest a model call that this process invoked itself.

    No shipped adapter calls this. A command's JSON cannot substitute for it.
    """

    if not adapter_id.strip() or not host.strip():
        raise ValueError("adapter_id and host are required")
    evidence = execution_evidence(
        execution_attempted=True,
        process_started=True,
        envelope_received=False,
        model_call=MODEL_CALL_VERIFIED,
    )
    evidence["model_attestation"] = {
        "schema": ATTESTATION_SCHEMA,
        "adapter": adapter_id,
        "host": host,
        "observed_by": "harness",
    }
    return evidence


def not_run_evidence() -> dict[str, Any]:
    return execution_evidence(
        execution_attempted=False,
        process_started=False,
        envelope_received=False,
        model_call=MODEL_CALL_NOT_APPLICABLE,
    )


def run_command(
    argv: list[str],
    request: Mapping[str, Any],
    *,
    timeout: float,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run one opted-in command. Never invent an envelope or a model call."""

    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(os.environ if env is None else env),
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    except FileNotFoundError:
        return _execution_result(
            status="model_unavailable",
            detail="command executable was not found",
            process_started=False,
        )
    except OSError as exc:
        return _execution_result(
            status="model_error",
            detail=f"command could not start: {exc.__class__.__name__}",
            process_started=False,
        )
    try:
        stdout, _ = process.communicate(input=payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_process_group(process)
        return _execution_result(
            status="model_error",
            detail="command timed out; process-tree cleanup attempted",
            process_started=True,
        )
    if process.returncode != 0:
        return _execution_result(
            status="model_error",
            detail=f"command exited with status {process.returncode}",
            process_started=True,
        )
    if len(stdout) > _STDOUT_CAP:
        return _execution_result(
            status="model_error",
            detail="stdout exceeded the harness cap",
            process_started=True,
        )
    return _envelope_from_stdout(stdout)


def _stop_process_group(process: subprocess.Popen[bytes]) -> None:
    """Best-effort cleanup of a timed-out command and its ordinary children."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def _envelope_from_stdout(stdout: bytes) -> dict[str, Any]:
    parsed = _parse_envelope(stdout)
    if parsed is None:
        return _execution_result(
            status="model_error",
            detail="stdout was not a bench envelope",
            process_started=True,
        )
    body, notes = parsed
    if len(body) > _FIELD_CAP or len(notes) > _FIELD_CAP:
        return _execution_result(
            status="model_error",
            detail="stdout envelope exceeded the field cap",
            process_started=True,
        )
    return {
        "status": "ready",
        "reason": "command returned a bench envelope; model call unverified",
        "envelope": {"body": body, "requester_notes": notes},
        **execution_evidence(
            execution_attempted=True,
            process_started=True,
            envelope_received=True,
            model_call=MODEL_CALL_UNVERIFIED,
        ),
    }


def _parse_envelope(stdout: bytes) -> tuple[str, str] | None:
    try:
        document = json.loads(stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, Mapping) or document.get("schema") != ENVELOPE_SCHEMA:
        return None
    body = document.get("body")
    notes = document.get("requester_notes")
    if not isinstance(body, str) or not isinstance(notes, str):
        return None
    return body, notes


def _execution_result(*, status: str, detail: str, process_started: bool) -> dict[str, Any]:
    prefix = "model_error" if status == "model_error" else "model_unavailable"
    return {
        "status": status,
        "reason": f"{prefix}: {detail}; model call unverified",
        "envelope": None,
        **execution_evidence(
            execution_attempted=True,
            process_started=process_started,
            envelope_received=False,
            model_call=MODEL_CALL_UNVERIFIED,
        ),
    }


def probe_interpreter() -> str:
    return sys.executable
