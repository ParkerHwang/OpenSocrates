#!/usr/bin/env python3
"""Gate the first and repeated packaged Codex ``SessionStart`` hook latency."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

TARGET = "darwin-arm64"
MIN_GATE_SAMPLES = 20
MAX_GATE_SAMPLES = 100
REQUIRED_P95_BUDGET_FRACTION = 0.5
PROCESS_MODEL = (
    "new_process_per_sample; first_configured_hook_before_runtime_smoke; "
    "hermetic_generated_input_and_selector_availability_metadata"
)
EXPECTED_COMMAND = "${PLUGIN_ROOT}/bin/launch.sh hook codex session_started"


class CodexHookTimingError(RuntimeError):
    """Raised when a package cannot support the bounded timing observation."""


SampleRunner = Callable[[Path, bytes, Mapping[str, str], Path, float], tuple[float, bool]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CodexHookTimingError("package_metadata_unavailable") from error
    if not isinstance(value, dict):
        raise CodexHookTimingError("package_metadata_invalid")
    return value


def _package_contract(package: Path) -> tuple[Path, int, str]:
    manifest_path = package / "release-manifest.json"
    manifest = _load_object(manifest_path)
    if (
        manifest.get("host") != "codex"
        or manifest.get("release_targets") != [TARGET]
        or TARGET not in manifest.get("runtime_targets", [])
    ):
        raise CodexHookTimingError("package_identity_invalid")
    hooks = _load_object(package / "hooks" / "hooks.json").get("hooks")
    try:
        command = hooks["SessionStart"][0]["hooks"][0]
        command_text = command["command"]
        timeout_seconds = command["timeout"]
    except (KeyError, IndexError, TypeError) as error:
        raise CodexHookTimingError("session_start_hook_missing") from error
    if command_text != EXPECTED_COMMAND:
        raise CodexHookTimingError("session_start_command_invalid")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds != 2
    ):
        raise CodexHookTimingError("session_start_timeout_invalid")
    launcher = package / "bin" / "launch.sh"
    runtime = package / "runtime" / TARGET / "opensocrates-runtime" / "opensocrates-runtime"
    if (
        not launcher.is_file()
        or not os.access(launcher, os.X_OK)
        or not runtime.is_file()
        or not os.access(runtime, os.X_OK)
    ):
        raise CodexHookTimingError("packaged_launcher_runtime_missing")
    return launcher, int(float(timeout_seconds) * 1000), _sha256(manifest_path)


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def _payload(workspace: Path, sample_number: int) -> bytes:
    value = {
        "hook_event_name": "SessionStart",
        "session_id": f"synthetic-session-{sample_number}",
        "turn_id": f"synthetic-turn-{sample_number}",
        "cwd": str(workspace),
        "source": "startup",
        "version": "synthetic-version",
    }
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def _sample_environment(sample_root: Path) -> tuple[dict[str, str], Path]:
    home = sample_root / "home"
    temporary = sample_root / "tmp"
    codex_home = sample_root / "codex"
    workspace = sample_root / "workspace"
    for directory in (home, temporary, codex_home, workspace):
        directory.mkdir(parents=True, mode=0o700)
        directory.chmod(0o700)
    # Runtime composition checks only the owner-safe OAuth seam metadata.  An
    # empty generated marker exercises the available branch without copying or
    # reading a real credential and without ever starting selector work.
    auth_marker = codex_home / "auth.json"
    auth_marker.write_bytes(b"")
    auth_marker.chmod(0o600)
    # A fixed allowlist keeps credentials, developer overrides, Python import
    # controls, and host-session metadata outside the measured process entirely.
    environment = {
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "CODEX_HOME": str(codex_home),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
    }
    return environment, workspace


def _run_sample(
    launcher: Path,
    payload: bytes,
    environment: Mapping[str, str],
    workspace: Path,
    timeout_seconds: float,
) -> tuple[float, bool]:
    started = time.perf_counter()
    process = subprocess.Popen(
        [str(launcher), "hook", "codex", "session_started"],
        cwd=workspace,
        env=dict(environment),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name == "posix",
    )
    completed_in_budget = True
    try:
        stdout, stderr = process.communicate(payload, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        completed_in_budget = False
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        stdout, stderr = process.communicate()
    elapsed_ms = (time.perf_counter() - started) * 1000
    contract_pass = (
        completed_in_budget and process.returncode == 0 and stdout == b"" and stderr == b""
    )
    return elapsed_ms, contract_pass


def measure_codex_session_start(
    package: Path,
    runs: int,
    *,
    sample_runner: SampleRunner | None = None,
    require_native: bool = True,
) -> dict[str, Any]:
    """Measure one real generated command per fresh process without retaining input."""

    if not MIN_GATE_SAMPLES <= runs <= MAX_GATE_SAMPLES:
        raise CodexHookTimingError("sample_count_invalid")
    if require_native and (
        platform.system() != "Darwin" or platform.machine().casefold() not in {"arm64", "aarch64"}
    ):
        raise CodexHookTimingError("native_darwin_arm64_required")
    launcher, configured_timeout_ms, artifact_identity = _package_contract(package)
    runner = sample_runner or _run_sample
    latencies: list[float] = []
    sample_contracts: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="opensocrates-codex-hook-gate-") as name:
        root = Path(name)
        for index in range(runs):
            environment, workspace = _sample_environment(root / f"sample-{index}")
            elapsed_ms, contract_pass = runner(
                launcher,
                _payload(workspace, index),
                environment,
                workspace,
                configured_timeout_ms / 1000,
            )
            latencies.append(elapsed_ms)
            sample_contracts.append(contract_pass)
    p95_value = _percentile(latencies, 0.95)
    p95_ms = round(p95_value, 3)
    maximum_value = max(latencies)
    maximum_ms = round(maximum_value, 3)
    required_p95_max_ms = configured_timeout_ms * REQUIRED_P95_BUDGET_FRACTION
    passed = (
        all(sample_contracts)
        and latencies[0] < configured_timeout_ms
        and maximum_value < configured_timeout_ms
        and p95_value <= required_p95_max_ms
    )
    # Keep the persisted observation deliberately closed.  In particular, it
    # contains no environment, path, callback envelope, process output, or ID.
    return {
        "target": TARGET,
        "artifact_identity": artifact_identity,
        "process_model": PROCESS_MODEL,
        "sample_count": len(latencies),
        "latency_ms": {
            "first": round(latencies[0], 3),
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": p95_ms,
            "max": maximum_ms,
        },
        "configured_timeout_ms": configured_timeout_ms,
        "pass": passed,
    }


def _failed_evidence(runs: int) -> dict[str, Any]:
    return {
        "target": TARGET,
        "artifact_identity": "unavailable",
        "process_model": PROCESS_MODEL,
        "sample_count": 0,
        "latency_ms": {"first": None, "p50": None, "p95": None, "max": None},
        "configured_timeout_ms": 2000,
        "pass": False,
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="dist/codex")
    parser.add_argument("--runs", type=int, default=MIN_GATE_SAMPLES)
    parser.add_argument("--report", default="build/evidence/codex-session-start-timing.json")
    args = parser.parse_args()
    try:
        report = measure_codex_session_start(Path(args.package).resolve(), args.runs)
    except (CodexHookTimingError, OSError, ValueError):
        report = _failed_evidence(args.runs)
    _write_report(Path(args.report).resolve(), report)
    status = "PASS" if report["pass"] else "FAIL"
    print(f"codex-session-start-timing: {status} target={report['target']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
