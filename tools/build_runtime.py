#!/usr/bin/env python3
"""Build the self-contained runtime and emit privacy-safe build evidence.

The runtime is built with PyInstaller, which is a build-only dependency.  This
module deliberately keeps the runtime entry point and the synthetic packaging
probe separate: the probe can establish packaging feasibility before the
application package exists, while the runtime build fails clearly when the
S01-owned source entry point is not present.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

SUPPORTED_TARGETS = (
    "darwin-arm64",
    "darwin-x64",
    "linux-x64",
    "windows-x64",
)
SUPPORTED_SYSTEMS = {"darwin": "Darwin", "linux": "Linux", "windows": "Windows"}
SUPPORTED_ARCHITECTURES = {
    "arm64": "arm64",
    "aarch64": "arm64",
    "x86_64": "x64",
    "amd64": "x64",
}
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
PROBE_PROTOCOL = "opensocrates.synthetic-probe/1.0.0"
CODEX_SDK_VERSION = "0.144.4"
CODEX_CLI_RUNTIME_PACKAGE = "openai-codex-cli-bin"
CODEX_RUNTIME_WHEEL_MARKERS = {
    "darwin-arm64": ("macosx_11_0_arm64",),
    "darwin-x64": ("macosx_10_9_x86_64",),
    "linux-x64": ("manylinux_2_17_x86_64", "musllinux_1_1_x86_64"),
    "windows-x64": ("win_amd64",),
}
RUNTIME_CONTENT_ASSETS = (
    "content/compiled-content.bundle.json",
    "content/compiled-reasoning-content.bundle.json",
)


class BuildError(RuntimeError):
    """Raised for a safe, actionable build failure."""


@dataclass(frozen=True)
class Target:
    """A normalized OS/architecture pair used by the package layout."""

    name: str
    system: str
    architecture: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8")


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rooted(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _detect_target() -> Target | None:
    system_key = platform.system().strip().lower()
    architecture_key = platform.machine().strip().lower()
    normalized_system = {
        "darwin": "darwin",
        "macos": "darwin",
        "linux": "linux",
        "windows": "windows",
    }.get(system_key)
    normalized_architecture = SUPPORTED_ARCHITECTURES.get(architecture_key)
    if normalized_system is None or normalized_architecture is None:
        return None
    name = f"{normalized_system}-{normalized_architecture}"
    if name not in SUPPORTED_TARGETS:
        return None
    return Target(
        name=name,
        system=SUPPORTED_SYSTEMS[normalized_system],
        architecture=normalized_architecture,
    )


def _target_from_name(name: str, current: Target | None) -> Target:
    if name == "auto":
        if current is None:
            raise BuildError(
                "unsupported platform: OS/architecture is not in the DG-01 candidate set"
            )
        return current
    if name not in SUPPORTED_TARGETS:
        raise BuildError(f"unsupported target: {name}")
    system, architecture = name.split("-", 1)
    return Target(name=name, system=SUPPORTED_SYSTEMS[system], architecture=architecture)


def _version(root: Path, *, required: bool) -> tuple[str | None, str]:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BuildError("could not parse pyproject.toml for the package version") from exc
        project = document.get("project", {})
        value = project.get("version")
        if isinstance(value, str) and VERSION_PATTERN.fullmatch(value):
            return value, "pyproject.toml"
    version_file = root / "VERSION"
    if version_file.is_file():
        value = version_file.read_text(encoding="utf-8").strip()
        if VERSION_PATTERN.fullmatch(value):
            return value, "VERSION"
        if required:
            raise BuildError("VERSION does not contain a valid semantic version")
    if required:
        raise BuildError(
            "a valid VERSION or pyproject.toml project.version is required for a runtime build"
        )
    return None, "unavailable"


def _normalized_name(value: str) -> str:
    return value.lower().replace("_", "-").replace(".", "-")


def _version_at_least(value: str, minimum: tuple[int, int]) -> bool:
    components = value.split(".")
    if len(components) < 2 or not all(part.isdigit() for part in components[:2]):
        return False
    return (int(components[0]), int(components[1])) >= minimum


def _locked_packages(root: Path) -> dict[str, dict[str, Any]]:
    try:
        document = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return {}
    packages = document.get("package", [])
    if not isinstance(packages, list):
        return {}
    return {
        _normalized_name(item["name"]): item
        for item in packages
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _locked_dependency_names(package: dict[str, Any]) -> set[str]:
    dependencies = package.get("dependencies", [])
    if not isinstance(dependencies, list):
        return set()
    return {
        _normalized_name(item["name"])
        for item in dependencies
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _distribution_files(name: str) -> set[str] | None:
    try:
        distribution = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return None
    return {str(item).replace("\\", "/") for item in (distribution.files or [])}


def _runtime_dependency_manifest(  # noqa: C901  # Explicit release policy.
    root: Path, target: Target, *, require_installed: bool
) -> dict[str, Any]:
    """Validate the locked SDK/runtime pair without exposing install paths."""

    errors: list[str] = []
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        project = {}
        errors.append("pyproject_unreadable")
    expected_dependencies = (
        "openai-codex==0.144.4",
        "openai-codex-cli-bin==0.144.4",
        "pydantic>=2.12,<3",
    )
    dependencies = project.get("project", {}).get("dependencies", [])
    if tuple(dependencies) != expected_dependencies:
        errors.append("runtime_dependency_declaration_mismatch")

    packages = _locked_packages(root)
    sdk = packages.get("openai-codex")
    cli_runtime = packages.get(CODEX_CLI_RUNTIME_PACKAGE)
    pydantic = packages.get("pydantic")
    pydantic_core = packages.get("pydantic-core")
    if sdk is None or sdk.get("version") != CODEX_SDK_VERSION:
        errors.append("openai_codex_pin_invalid")
    if cli_runtime is None or cli_runtime.get("version") != CODEX_SDK_VERSION:
        errors.append("codex_cli_runtime_pin_invalid")
    if sdk is not None and not {CODEX_CLI_RUNTIME_PACKAGE, "pydantic"} <= _locked_dependency_names(
        sdk
    ):
        errors.append("openai_codex_closure_invalid")
    pydantic_version = pydantic.get("version") if pydantic is not None else None
    if not isinstance(pydantic_version, str) or not _version_at_least(pydantic_version, (2, 12)):
        errors.append("pydantic_bound_invalid")
    elif not pydantic_version.startswith("2."):
        errors.append("pydantic_major_invalid")
    if pydantic_core is None or not isinstance(pydantic_core.get("version"), str):
        errors.append("pydantic_core_missing")

    wheel_urls = (
        [
            item["url"].lower()
            for item in cli_runtime.get("wheels", [])
            if isinstance(item, dict) and isinstance(item.get("url"), str)
        ]
        if cli_runtime is not None and isinstance(cli_runtime.get("wheels", []), list)
        else []
    )
    wheel_markers = CODEX_RUNTIME_WHEEL_MARKERS[target.name]
    target_wheel_locked = all(any(marker in url for url in wheel_urls) for marker in wheel_markers)
    if not target_wheel_locked:
        errors.append("target_cli_runtime_wheel_missing")

    installed: dict[str, bool] = {}
    cli_resources_present: bool | None = None
    if require_installed:
        expected_versions = {
            "openai-codex": CODEX_SDK_VERSION,
            CODEX_CLI_RUNTIME_PACKAGE: CODEX_SDK_VERSION,
            "pydantic": pydantic_version,
            "pydantic-core": pydantic_core.get("version") if pydantic_core is not None else None,
        }
        for name, expected_version in expected_versions.items():
            try:
                installed_version = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                installed[name] = False
                errors.append(f"installed_distribution_missing:{name}")
                continue
            installed[name] = installed_version == expected_version
            if not installed[name]:
                errors.append(f"installed_distribution_version_mismatch:{name}")
        cli_files = _distribution_files(CODEX_CLI_RUNTIME_PACKAGE)
        binary_name = "codex.exe" if target.name.startswith("windows-") else "codex"
        required_files = {
            "codex_cli_bin/__init__.py",
            "codex_cli_bin/codex-package.json",
            f"codex_cli_bin/bin/{binary_name}",
        }
        cli_resources_present = cli_files is not None and required_files <= cli_files
        if not cli_resources_present:
            errors.append("installed_cli_runtime_resources_missing")

    status = "blocked" if errors else "ready" if require_installed else "locked"
    return {
        "status": status,
        "sdk": {"name": "openai-codex", "version": CODEX_SDK_VERSION},
        "cli_runtime": {
            "name": CODEX_CLI_RUNTIME_PACKAGE,
            "version": CODEX_SDK_VERSION,
            "target_wheel": "locked" if target_wheel_locked else "missing",
            "artifact_verification": "not_attempted",
        },
        "pydantic": {
            "version": pydantic_version,
            "required_range": ">=2.12,<3",
            "core_version": pydantic_core.get("version") if pydantic_core is not None else None,
        },
        "installed_distributions": installed if require_installed else "not_checked",
        "cli_runtime_resources_present": cli_resources_present,
        "bundling": {
            "method": "PyInstaller collect_all in the runtime spec",
            "cross_platform_status": "not_supported_by_this_native_builder",
        },
        "error_codes": sorted(set(errors)),
    }


def _report_path(root: Path, value: str | None, default_name: str) -> Path:
    if value is None:
        return root / "build" / "evidence" / default_name
    return _rooted(root, value)


def _artifact_path(output_dir: Path, name: str, target: Target) -> Path:
    suffix = ".exe" if target.name.startswith("windows-") else ""
    return output_dir / name / f"{name}{suffix}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_content_assets(root: Path) -> dict[str, dict[str, int | str]]:
    """Inventory the two generated content assets required by the native runtime."""

    assets: dict[str, dict[str, int | str]] = {}
    for relative in RUNTIME_CONTENT_ASSETS:
        source = root / relative
        if source.is_symlink() or not source.is_file():
            raise BuildError(f"required runtime content asset is missing: {relative}")
        assets[relative] = {
            "size_bytes": source.stat().st_size,
            "sha256": f"sha256:{_sha256(source)}",
        }
    return assets


def _verify_packaged_runtime_content(
    artifact: Path, expected_assets: Mapping[str, Mapping[str, int | str]]
) -> dict[str, int | str]:
    """Confirm PyInstaller retained every generated content asset byte-for-byte."""

    errors: list[str] = []
    for relative, expected in expected_assets.items():
        expected_hash = expected.get("sha256")
        if not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
            errors.append(relative)
            continue
        candidates = (
            path
            for path in artifact.parent.rglob(Path(relative).name)
            if path.is_file() and not path.is_symlink()
        )
        if not any(f"sha256:{_sha256(path)}" == expected_hash for path in candidates):
            errors.append(relative)
    if errors:
        raise BuildError("PyInstaller output is missing a required generated content asset")
    return {"status": "pass", "asset_count": len(expected_assets)}


def _record_packaged_runtime_content(
    report: dict[str, Any], artifact: Path, content_assets: dict[str, dict[str, int | str]] | None
) -> None:
    if content_assets is None:
        return
    report["content_assets"] = {
        "source": content_assets,
        "packaged": _verify_packaged_runtime_content(artifact, content_assets),
    }


def _ensure_python() -> None:
    if sys.version_info < (3, 12):
        raise BuildError(
            "Python 3.12 or newer is required; system Python is not a release requirement"
        )


def _spec_for(root: Path, mode: str, explicit: str | None) -> Path:
    if explicit:
        spec = _rooted(root, explicit)
    elif mode == "probe":
        spec = root / "packaging" / "pyinstaller" / "opensocrates-probe.spec"
    else:
        spec = root / "packaging" / "pyinstaller" / "opensocrates-runtime.spec"
    if not spec.is_file():
        raise BuildError(
            f"PyInstaller spec not found: {spec.relative_to(root) if spec.is_relative_to(root) else spec}"
        )
    return spec


def _entrypoint(root: Path, mode: str) -> Path:
    if mode == "probe":
        return root / "packaging" / "pyinstaller" / "probe_entry.py"
    return root / "src" / "opensocrates" / "__main__.py"


def _run_binary(
    binary: Path, *, mode: str = "probe", timeout: float = 3.0
) -> tuple[dict[str, Any] | None, float, str]:
    if mode == "runtime":
        command = [str(binary), "version", "--json"]
        payload = None
    else:
        command = [str(binary)]
        payload = (
            json.dumps(
                {"schema": PROBE_PROTOCOL, "event": "session_started"},
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, (time.perf_counter() - started) * 1000, type(exc).__name__
    elapsed_ms = (time.perf_counter() - started) * 1000
    if completed.returncode != 0:
        return None, elapsed_ms, f"exit_{completed.returncode}"
    try:
        parsed = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, elapsed_ms, "non_json_stdout"
    if not isinstance(parsed, dict):
        return None, elapsed_ms, "non_object_stdout"
    return parsed, elapsed_ms, "ok"


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[index], 3)


def _measure(binary: Path, runs: int, *, mode: str) -> dict[str, Any]:
    latencies: list[float] = []
    errors: list[str] = []
    for _ in range(runs):
        response, elapsed_ms, error = _run_binary(binary, mode=mode)
        if response is None:
            errors.append(error)
        else:
            latencies.append(elapsed_ms)
    result: dict[str, Any] = {
        "runs": runs,
        "successful_runs": len(latencies),
        "failed_runs": len(errors),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50) if latencies else None,
            "p95": _percentile(latencies, 0.95) if latencies else None,
            "min": round(min(latencies), 3) if latencies else None,
            "max": round(max(latencies), 3) if latencies else None,
        },
        "budget_ms": {"p50_lt": 100, "p95_lt": 250},
        "budget_pass": bool(latencies)
        and _percentile(latencies, 0.50) < 100
        and _percentile(latencies, 0.95) < 250,
    }
    if errors:
        result["error_codes"] = sorted(set(errors))
    return result


def _pyinstaller_command(spec: Path, output_dir: Path, work_dir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(output_dir),
        "--workpath",
        str(work_dir),
        str(spec),
    ]


def _safe_command(command: Sequence[str], root: Path) -> list[str]:
    """Describe a build argv without persisting host-specific absolute paths."""

    safe: list[str] = []
    for index, token in enumerate(command):
        if index == 0:
            safe.append("<build-python>")
            continue
        if not os.path.isabs(token):
            safe.append(token)
            continue
        path = Path(token)
        try:
            safe.append(f"<root>/{path.resolve().relative_to(root).as_posix()}")
        except (ValueError, OSError):
            safe.append("<external-build-path>")
    return safe


def _emit_report(report_path: Path, report: dict[str, Any], *, stderr: bool) -> None:
    _write_json(report_path, report)
    stream = sys.stderr if stderr else sys.stdout
    print(_canonical_json(report), end="", file=stream)


def _target_unavailable_report(
    report_path: Path,
    args: argparse.Namespace,
    current: Target | None,
    version: str | None,
    version_source: str,
    error: BuildError,
) -> int:
    report = {
        "schema": "opensocrates.runtime-build-evidence/1.0.0",
        "generated_at": _iso_now(),
        "mode": args.mode,
        "target": None,
        "current_target": current.name if current else None,
        "buildable_here": False,
        "version": version,
        "version_source": version_source,
        "status": "unavailable",
        "diagnostic": str(error)[:240],
    }
    _emit_report(report_path, report, stderr=True)
    return 2


def _relative_or_outside(root: Path, path: Path) -> str:
    if path.is_relative_to(root):
        return path.relative_to(root).as_posix()
    return "outside-root"


def _build_report(
    args: argparse.Namespace,
    root: Path,
    current: Target | None,
    target: Target,
    version: str | None,
    version_source: str,
    entrypoint: Path,
    spec: Path,
    output_dir: Path,
    artifact: Path,
    runtime_dependencies: dict[str, Any] | None,
    content_assets: dict[str, dict[str, int | str]] | None,
) -> dict[str, Any]:
    artifact_layout = "onedir"
    report = {
        "schema": "opensocrates.runtime-build-evidence/1.0.0",
        "generated_at": _iso_now(),
        "mode": args.mode,
        "target": target.name,
        "current_target": current.name if current else None,
        "buildable_here": current is not None and current.name == target.name,
        "version": version,
        "version_source": version_source,
        "entrypoint": _relative_or_outside(root, entrypoint),
        "entrypoint_present": entrypoint.is_file(),
        "spec": _relative_or_outside(root, spec),
        "output": _relative_or_outside(root, output_dir),
        "artifact": _relative_or_outside(root, artifact),
        "artifact_layout": artifact_layout,
        "signing_status": "not_attempted",
        "status": "planned" if args.dry_run else "started",
    }
    if runtime_dependencies is not None:
        report["runtime_dependencies"] = runtime_dependencies
    if content_assets is not None:
        report["content_assets"] = {"source": content_assets, "packaged": "not_checked"}
    return report


def _finish_status(
    report_path: Path,
    report: dict[str, Any],
    status: str,
    diagnostic: str,
    exit_code: int,
    *,
    stderr: bool,
) -> int:
    report["status"] = status
    report["diagnostic"] = diagnostic
    _emit_report(report_path, report, stderr=stderr)
    return exit_code


def _dry_run_result(
    report_path: Path,
    report: dict[str, Any],
    current: Target | None,
    buildable_here: bool,
) -> int:
    if current is None:
        return _finish_status(
            report_path,
            report,
            "unavailable",
            "unknown OS/architecture; no build claim",
            2,
            stderr=False,
        )
    if not buildable_here:
        return _finish_status(
            report_path,
            report,
            "unavailable",
            "cross-compilation is not attempted by this helper",
            2,
            stderr=False,
        )
    _emit_report(report_path, report, stderr=False)
    return 0


def _run_pyinstaller(
    args: argparse.Namespace,
    root: Path,
    target: Target,
    spec: Path,
    output_dir: Path,
    artifact: Path,
    report_path: Path,
    report: dict[str, Any],
    content_assets: dict[str, dict[str, int | str]] | None,
) -> int:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        work_dir = _rooted(root, args.work_dir or Path("build") / "pyinstaller" / target.name)
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        command = _pyinstaller_command(spec, output_dir, work_dir)
        report["command"] = _safe_command(command, root)
        completed = subprocess.run(command, cwd=root, check=False)
        if completed.returncode != 0:
            raise BuildError(f"PyInstaller exited with status {completed.returncode}")
        if not artifact.is_file():
            raise BuildError(f"PyInstaller completed but artifact is missing: {artifact}")
        if not target.name.startswith("windows-"):
            artifact.chmod(artifact.stat().st_mode | 0o111)
        report["artifact_size_bytes"] = artifact.stat().st_size
        report["artifact_sha256"] = _sha256(artifact)
        _record_packaged_runtime_content(report, artifact, content_assets)
        if args.smoke_test:
            response, elapsed_ms, error = _run_binary(artifact, mode=args.mode)
            report["smoke_test"] = {
                "status": "pass" if response is not None else "fail",
                "elapsed_ms": round(elapsed_ms, 3),
            }
            if response is None:
                raise BuildError(f"smoke test failed: {error}")
        if args.measure_runs:
            measurement = _measure(artifact, args.measure_runs, mode=args.mode)
            report["startup_measurement"] = measurement
            if not measurement["budget_pass"]:
                return _finish_status(
                    report_path,
                    report,
                    "fail",
                    "startup_budget_exceeded",
                    1,
                    stderr=True,
                )
        report["status"] = "pass"
    except (BuildError, OSError, subprocess.SubprocessError) as exc:
        report["status"] = (
            "blocked" if isinstance(exc, BuildError) and "PyInstaller" not in str(exc) else "fail"
        )
        report["diagnostic"] = type(exc).__name__
        report["message"] = str(exc)[:240]
        _emit_report(report_path, report, stderr=True)
        return 1
    _emit_report(report_path, report, stderr=False)
    return 0


def _build(args: argparse.Namespace) -> int:
    _ensure_python()
    root = _rooted(Path.cwd(), args.root)
    current = _detect_target()
    report_path = _report_path(root, args.report, "runtime-build.json")
    version, version_source = _version(root, required=args.mode == "runtime")
    try:
        target = _target_from_name(args.target, current)
    except BuildError as exc:
        return _target_unavailable_report(report_path, args, current, version, version_source, exc)
    entrypoint = _entrypoint(root, args.mode)
    spec = _spec_for(root, args.mode, args.spec)
    output_dir = _rooted(root, args.output_dir or Path("dist") / "runtime" / target.name)
    artifact_name = "opensocrates-probe" if args.mode == "probe" else "opensocrates-runtime"
    artifact = _artifact_path(output_dir, artifact_name, target)
    buildable_here = current is not None and current.name == target.name
    runtime_dependencies = (
        _runtime_dependency_manifest(root, target, require_installed=not args.dry_run)
        if args.mode == "runtime"
        else None
    )
    content_assets = _runtime_content_assets(root) if args.mode == "runtime" else None
    report = _build_report(
        args,
        root,
        current,
        target,
        version,
        version_source,
        entrypoint,
        spec,
        output_dir,
        artifact,
        runtime_dependencies,
        content_assets,
    )
    if runtime_dependencies is not None:
        expected_status = "locked" if args.dry_run else "ready"
        if runtime_dependencies["status"] != expected_status:
            return _finish_status(
                report_path,
                report,
                "blocked",
                "codex_sdk_runtime_metadata_invalid",
                2,
                stderr=not args.dry_run,
            )
    if args.dry_run:
        return _dry_run_result(report_path, report, current, buildable_here)
    if current is None:
        return _finish_status(
            report_path,
            report,
            "unavailable",
            "unknown OS/architecture; safe failure",
            2,
            stderr=True,
        )
    if not buildable_here:
        return _finish_status(
            report_path,
            report,
            "unavailable",
            "cross-compilation is not attempted; build on the native runner",
            2,
            stderr=True,
        )
    if not entrypoint.is_file():
        return _finish_status(
            report_path,
            report,
            "blocked",
            "runtime entry point is not present; S01-owned source is required",
            2,
            stderr=True,
        )
    return _run_pyinstaller(
        args,
        root,
        target,
        spec,
        output_dir,
        artifact,
        report_path,
        report,
        content_assets,
    )


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument(
        "--target",
        default="auto",
        metavar="TARGET",
        help=(
            "native target or dry-run candidate; unsupported values fail safe "
            f"(supported: auto, {', '.join(SUPPORTED_TARGETS)})"
        ),
    )
    parser.add_argument(
        "--output-dir", help="artifact directory; defaults to dist/runtime/<target>"
    )
    parser.add_argument("--work-dir", help="PyInstaller work directory")
    parser.add_argument("--report", help="machine-readable evidence JSON path")
    parser.add_argument("--spec", help="override the mode-specific PyInstaller spec")
    parser.add_argument("--dry-run", action="store_true", help="plan without invoking PyInstaller")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="launch the built artifact with synthetic JSON",
    )
    parser.add_argument(
        "--measure-runs",
        type=int,
        default=0,
        metavar="N",
        help="measure N cold process starts after building",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("probe", "runtime"):
        subparser = subparsers.add_parser(mode, help=f"build the {mode} executable")
        _add_common_arguments(subparser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.measure_runs < 0:
        print("--measure-runs must be non-negative", file=sys.stderr)
        return 2
    if args.measure_runs and not args.smoke_test:
        args.smoke_test = True
    try:
        return _build(args)
    except (BuildError, OSError, ValueError) as exc:
        print(f"build_runtime: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
