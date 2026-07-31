#!/usr/bin/env python3
"""Run the reproducible local packaging/startup feasibility measurement."""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from build_runtime import SUPPORTED_TARGETS, _detect_target, _percentile


class MeasurementError(RuntimeError):
    """Raised when the local spike cannot establish evidence."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8")


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _platform_matrix(observed: str | None) -> tuple[dict[str, Any], list[str]]:
    matrix: dict[str, Any] = {}
    for target in SUPPORTED_TARGETS:
        if target == observed:
            matrix[target] = {"status": "observed_local", "claim": "local spike only"}
        else:
            matrix[target] = {
                "status": "unvalidated",
                "claim": "no build or startup evidence in this run",
            }
    return matrix, [target for target in SUPPORTED_TARGETS if target != observed]


def _run_launcher(launcher: Path, stage: Path) -> float:
    payload = (
        json.dumps(
            {
                "schema": "opensocrates.synthetic-probe/1.0.0",
                "event": "session_started",
            },
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(launcher), "hook", "codex", "session_started"],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=stage,
            check=False,
            timeout=3.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MeasurementError(f"launcher failed to start: {type(exc).__name__}") from exc
    elapsed_ms = (time.perf_counter() - started) * 1000
    if completed.returncode != 0:
        raise MeasurementError(f"launcher returned status {completed.returncode}")
    try:
        response = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MeasurementError("launcher did not emit one JSON response") from exc
    if not isinstance(response, dict) or response.get("status") != "ok":
        raise MeasurementError("launcher response was not the synthetic probe success")
    return elapsed_ms


def measure(
    root: Path, binary: Path, target: str, runs: int, stage_root: Path | None
) -> tuple[int, dict[str, Any]]:
    if target not in SUPPORTED_TARGETS:
        raise MeasurementError(f"unsupported target: {target}")
    if target.startswith("windows-"):
        raise MeasurementError("PowerShell startup measurement must run on a native Windows host")
    if not binary.is_file():
        raise MeasurementError(f"probe binary does not exist: {binary}")
    launcher_source = root / "packaging" / "launchers" / "launch.sh"
    if not launcher_source.is_file():
        raise MeasurementError("packaging/launchers/launch.sh is missing")
    stage = stage_root or Path(tempfile.mkdtemp(prefix="opensocrates spike — "))
    stage_created = stage_root is None
    stage = stage.resolve()
    try:
        bin_dir = stage / "bin"
        target_dir = bin_dir / target
        target_dir.mkdir(parents=True, exist_ok=True)
        staged_bundle = target_dir / "opensocrates-runtime"
        runtime_executable_name = (
            "opensocrates-runtime.exe" if target.startswith("windows-") else "opensocrates-runtime"
        )
        staged_launcher = bin_dir / "launch.sh"
        if binary.parent.name == binary.stem and binary.parent.is_dir():
            staged_bundle.mkdir(parents=True, exist_ok=True)
            for item in binary.parent.iterdir():
                destination = staged_bundle / (
                    runtime_executable_name if item == binary else item.name
                )
                if item.is_dir():
                    shutil.copytree(item, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, destination)
            staged_binary = staged_bundle / runtime_executable_name
        else:
            staged_bundle.mkdir(parents=True, exist_ok=True)
            staged_binary = staged_bundle / runtime_executable_name
            shutil.copy2(binary, staged_binary)
        shutil.copy2(launcher_source, staged_launcher)
        staged_binary.chmod(
            staged_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )
        staged_launcher.chmod(
            staged_launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )
        latencies = [_run_launcher(staged_launcher, stage) for _ in range(runs)]
        observed = _detect_target()
        observed_name = observed.name if observed else None
        matrix, unvalidated = _platform_matrix(observed_name)
        report = {
            "schema": "opensocrates.dg-01-macos-evidence/1.0.0",
            "generated_at": _iso_now(),
            "status": "pass"
            if _percentile(latencies, 0.50) < 100 and _percentile(latencies, 0.95) < 250
            else "fail",
            "measurement": {
                "target": target,
                "runs": runs,
                "process_model": "new subprocess per sample",
                "latency_ms": {
                    "p50": _percentile(latencies, 0.50),
                    "p95": _percentile(latencies, 0.95),
                    "min": round(min(latencies), 3),
                    "max": round(max(latencies), 3),
                },
                "budget_ms": {"p50_lt": 100, "p95_lt": 250},
                "path_shape": "spaces-and-unicode",
                "path_content_recorded": False,
            },
            "platforms": matrix,
            "unvalidated_platforms": unvalidated,
            "signing_status": "not_evaluated",
            "clean_machine_install_status": "not_evaluated",
            "artifact_size_bytes": sum(
                item.stat().st_size for item in staged_bundle.rglob("*") if item.is_file()
            ),
        }
        return (0 if report["status"] == "pass" else 1), report
    finally:
        if stage_created:
            shutil.rmtree(stage, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument(
        "--binary", required=True, help="probe binary built by tools/build_runtime.py"
    )
    parser.add_argument("--target", choices=SUPPORTED_TARGETS, required=True)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument(
        "--stage-root",
        help="existing path containing spaces/Unicode; default creates a temporary one",
    )
    parser.add_argument("--report", help="machine-readable evidence JSON path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.runs < 5:
        print(
            "--runs must be at least 5 for a p95 feasibility measurement",
            file=sys.stderr,
        )
        return 2
    root = _resolve(Path.cwd(), args.root)
    binary = _resolve(root, args.binary)
    stage_root = _resolve(root, args.stage_root) if args.stage_root else None
    report_path = _resolve(root, args.report or "build/evidence/dg-01-macos.json")
    try:
        status, report = measure(root, binary, args.target, args.runs, stage_root)
    except (MeasurementError, OSError) as exc:
        status = 2
        report = {
            "schema": "opensocrates.dg-01-macos-evidence/1.0.0",
            "generated_at": _iso_now(),
            "status": "blocked",
            "diagnostic": type(exc).__name__,
            "message": str(exc)[:240],
            "unvalidated_platforms": list(SUPPORTED_TARGETS),
        }
    _write_json(report_path, report)
    print(_canonical_json(report), end="")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
