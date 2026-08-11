#!/usr/bin/env python3
"""Execute the generated package launchers against the generated package layout.

The generated host packages ship the POSIX launcher at ``<plugin-root>/bin``
and the native runtime under the host generator's canonical ``runtime_output``.
A launcher that resolves a different root therefore never finds it, and because
hook mode fails open with literal-empty stdout the breakage is silent. This
check runs the *actual* launcher shipped in each generated package, dispatching
the *actual* hook arguments declared in that package's ``hooks/hooks.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

HOSTS = ("claude", "codex")
RUNTIME_LEAF = ("opensocrates-runtime", "opensocrates-runtime")
LAUNCHER = ("bin", "launch.sh")
STDOUT_TOKEN = "opensocrates-packaged-launcher-stdout\n"
CONTROL_EXIT_CODE = 7

# Kept in sync with the platform table in packaging/launchers/launch.sh.
TARGET_UNAME: dict[str, tuple[str, str]] = {
    "darwin-arm64": ("Darwin", "arm64"),
}
NATIVE_TARGET: dict[tuple[str, str], str] = {
    ("Darwin", "arm64"): "darwin-arm64",
    ("Darwin", "aarch64"): "darwin-arm64",
}
UNSUPPORTED_UNAMES = (
    ("Darwin", "x86_64"),
    ("Linux", "x86_64"),
    ("Linux", "aarch64"),
)

# Automatic selection and both cleanup events must never silently no-op.
REQUIRED_EVENTS = frozenset({"user_prompt_submitted", "completion_candidate", "session_ended"})

STUB_TEMPLATE = """#!/bin/sh
{{
    printf 'self:%s\\n' "$0"
    printf 'argv:'
    for argument in "$@"; do
        printf ' %s' "$argument"
    done
    printf '\\n'
}} >> {marker}
printf '%s' {stdout_token}
exit {exit_code}
"""

UNAME_TEMPLATE = """#!/bin/sh
case "${{1:-}}" in
    -s) printf '%s\\n' {system} ;;
    -m) printf '%s\\n' {machine} ;;
    *) printf '%s\\n' unknown ;;
esac
"""


class CheckFailure(Exception):
    """A packaged-launcher contract violation."""


def _quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _native_target() -> str | None:
    return NATIVE_TARGET.get((platform.system(), platform.machine()))


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CheckFailure(f"{path.name} is unreadable: {type(error).__name__}") from error
    if not isinstance(value, Mapping):
        raise CheckFailure(f"{path.name} is not a JSON object")
    return value


def _runtime_output(root: Path, host: str) -> str:
    """Read one safe canonical runtime root from the host generator metadata."""

    value = _load_json(root / "plugin-src" / host / "generator.json").get("runtime_output")
    if not isinstance(value, str) or not value:
        raise CheckFailure(f"{host} generator runtime_output is missing")
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise CheckFailure(f"{host} generator runtime_output is unsafe")
    return relative.as_posix()


def _launcher_argv(entry: Mapping[str, Any]) -> list[str] | None:
    """Return the launcher arguments declared by one hook entry, if any."""

    command = entry.get("command")
    if not isinstance(command, str) or "launch.sh" not in command:
        return None
    args = entry.get("args")
    if isinstance(args, list) and all(isinstance(item, str) for item in args):
        return [str(item) for item in args]
    # Codex declares the launcher and its arguments as a single command string.
    parts = command.split()
    return parts[1:] if len(parts) > 1 else None


def _dispatch_specs(hooks_file: Path) -> list[tuple[str, list[str]]]:
    """Collect every launcher dispatch the generated package actually declares."""

    hooks = _load_json(hooks_file).get("hooks")
    if not isinstance(hooks, Mapping) or not hooks:
        raise CheckFailure("generated hooks.json declares no hooks")
    specs: list[tuple[str, list[str]]] = []
    for native_event, groups in sorted(hooks.items()):
        for group in groups if isinstance(groups, list) else []:
            entries = group.get("hooks") if isinstance(group, Mapping) else None
            for entry in entries if isinstance(entries, list) else []:
                argv = _launcher_argv(entry) if isinstance(entry, Mapping) else None
                if argv is not None:
                    specs.append((str(native_event), argv))
    if not specs:
        raise CheckFailure("generated hooks.json dispatches nothing through bin/launch.sh")
    return specs


def _stage(package: Path, target: str, *, runtime_parent: str | None) -> tuple[Path, Path | None]:
    """Copy the package's real bin/ tree and place a stub runtime.

    ``runtime_parent`` selects where the stub is written relative to the plugin
    root.  ``None`` omits the runtime entirely so the genuine missing-runtime
    fail-open path can be observed.  The launcher itself is always the byte
    identical file shipped in the generated package.
    """

    # macOS exposes /var as a symlink to /private/var. The launcher resolves
    # its directory physically with ``pwd -P``, so keep the staged root in the
    # same canonical form before comparing the runtime's recorded argv[0].
    stage = Path(tempfile.mkdtemp(prefix="opensocrates-launcher-")).resolve()
    shutil.copytree(package / "bin", stage / "bin")
    launcher = stage / Path(*LAUNCHER)
    if launcher.read_bytes() != (package / Path(*LAUNCHER)).read_bytes():
        raise CheckFailure("staged launcher is not byte identical to the packaged launcher")
    launcher.chmod(0o755)
    if runtime_parent is None:
        return stage, None
    runtime = stage.joinpath(runtime_parent, target, *RUNTIME_LEAF)
    marker = stage / "marker.txt"
    _write_executable(
        runtime,
        STUB_TEMPLATE.format(
            marker=_quote(str(marker)),
            stdout_token=_quote(STDOUT_TOKEN),
            exit_code=0,
        ),
    )
    return stage, runtime


def _environment(stage: Path, target: str | None) -> dict[str, str]:
    """Return a launcher environment, optionally pinning the reported platform."""

    reported = TARGET_UNAME.get(target or "", UNSUPPORTED_UNAMES[-1])
    return _environment_for_uname(stage, reported)


def _environment_for_uname(stage: Path, reported: tuple[str, str]) -> dict[str, str]:
    """Return a launcher environment with an exact synthetic uname pair."""

    env = dict(os.environ)
    system, machine = reported
    shim = stage / "shim"
    _write_executable(
        shim / "uname",
        UNAME_TEMPLATE.format(system=_quote(system), machine=_quote(machine)),
    )
    env["PATH"] = f"{shim}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run(stage: Path, argv: Sequence[str], env: Mapping[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(stage / Path(*LAUNCHER)), *argv],
        cwd=tempfile.gettempdir(),
        env=dict(env),
        capture_output=True,
        timeout=60.0,
        check=False,
    )


def _marker_fields(marker: Path) -> dict[str, str]:
    if not marker.is_file():
        raise CheckFailure("the packaged launcher never invoked the canonical runtime root")
    fields: dict[str, str] = {}
    for line in marker.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        fields[key] = value.strip()
    return fields


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _assert_dispatch(
    stage: Path, runtime: Path, argv: Sequence[str], expected: Sequence[str], target: str
) -> None:
    result = _run(stage, argv, _environment(stage, target))
    _require(result.returncode == 0, f"hook dispatch {list(argv)} exited {result.returncode}")
    fields = _marker_fields(stage / "marker.txt")
    _require(
        fields.get("self") == str(runtime),
        f"runtime reached at {fields.get('self')!r}, expected {str(runtime)!r}",
    )
    _require(
        fields.get("argv") == " ".join(expected),
        f"runtime received {fields.get('argv')!r}, expected {' '.join(expected)!r}",
    )
    _require(
        result.stdout.decode("utf-8") == STDOUT_TOKEN,
        "the launcher did not relay runtime stdout unchanged",
    )
    (stage / "marker.txt").unlink()


def _check_hook_dispatch(
    package: Path, host: str, target: str, *, runtime_output: str
) -> list[str]:
    """Dispatch every declared hook through the real launcher for one target."""

    specs = _dispatch_specs(package / "hooks" / "hooks.json")
    stage, runtime = _stage(package, target, runtime_parent=runtime_output)
    assert runtime is not None
    events: list[str] = []
    try:
        for _native_event, argv in specs:
            _require(
                len(argv) == 3 and argv[0] == "hook" and argv[1] == host,
                f"unexpected packaged hook arguments {argv}",
            )
            _assert_dispatch(stage, runtime, argv, ["hook", argv[2], "--host", host], target)
            events.append(argv[2])
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    missing = sorted(REQUIRED_EVENTS - set(events))
    _require(not missing, f"{host} package never dispatches {missing}")
    return sorted(set(events))


def _check_control_mode(package: Path, host: str, target: str, *, runtime_output: str) -> None:
    """Control mode must exec the runtime and propagate its exit status."""

    stage, runtime = _stage(package, target, runtime_parent=runtime_output)
    assert runtime is not None
    try:
        _write_executable(
            runtime,
            STUB_TEMPLATE.format(
                marker=_quote(str(stage / "marker.txt")),
                stdout_token=_quote(STDOUT_TOKEN),
                exit_code=CONTROL_EXIT_CODE,
            ),
        )
        result = _run(stage, ["control", host], _environment(stage, target))
        _require(
            result.returncode == CONTROL_EXIT_CODE,
            f"control mode exited {result.returncode}, expected {CONTROL_EXIT_CODE}",
        )
        fields = _marker_fields(stage / "marker.txt")
        _require(
            fields.get("argv") == f"control apply --host {host}",
            f"control mode dispatched {fields.get('argv')!r}",
        )
        _require(fields.get("self") == str(runtime), "control mode reached the wrong runtime")
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _assert_fail_open(package: Path, host: str, target: str, runtime_parent: str | None) -> None:
    """A hook that cannot reach the runtime exits 0 with literal-empty stdout."""

    stage, _runtime = _stage(package, target, runtime_parent=runtime_parent)
    try:
        result = _run(stage, ["hook", host, "user_prompt_submitted"], _environment(stage, target))
        _require(result.returncode == 0, f"fail-open hook exited {result.returncode}")
        _require(result.stdout == b"", f"fail-open hook wrote stdout {result.stdout!r}")
        _require(
            not (stage / "marker.txt").is_file(),
            "the launcher invoked a runtime outside its canonical root",
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _assert_canonical_runtime_precedence(
    package: Path, host: str, target: str, *, runtime_output: str
) -> None:
    """A stray executable under bin/ must never compete with the package runtime."""

    stage, runtime = _stage(package, target, runtime_parent=runtime_output)
    assert runtime is not None
    stray = stage.joinpath("bin", "runtime", target, *RUNTIME_LEAF)
    _write_executable(
        stray,
        STUB_TEMPLATE.format(
            marker=_quote(str(stage / "marker.txt")),
            stdout_token=_quote("opensocrates-stray-bin-runtime\n"),
            exit_code=0,
        ),
    )
    try:
        _assert_dispatch(
            stage,
            runtime,
            ["hook", host, "user_prompt_submitted"],
            ["hook", "user_prompt_submitted", "--host", host],
            target,
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _assert_control_diagnostic(package: Path, host: str, target: str) -> None:
    """Control mode keeps its structured diagnostic when the runtime is absent."""

    stage, _runtime = _stage(package, target, runtime_parent=None)
    try:
        result = _run(stage, ["control", host], _environment(stage, target))
        _require(result.returncode == 0, f"control diagnostic exited {result.returncode}")
        payload = json.loads(result.stdout.decode("utf-8"))
        _require(
            payload.get("decision") == "pass"
            and payload.get("diagnostic", {}).get("code") == "missing_runtime",
            f"control diagnostic payload was {result.stdout!r}",
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _assert_unsupported_platform(package: Path, host: str, *, runtime_output: str) -> None:
    stage, _runtime = _stage(package, "darwin-arm64", runtime_parent=runtime_output)
    try:
        for reported in UNSUPPORTED_UNAMES:
            result = _run(
                stage,
                ["hook", host, "user_prompt_submitted"],
                _environment_for_uname(stage, reported),
            )
            _require(
                result.returncode == 0,
                f"unsupported-platform {reported} hook exited {result.returncode}",
            )
            _require(
                result.stdout == b"",
                f"unsupported-platform {reported} hook wrote {result.stdout!r}",
            )
            _require(
                not (stage / "marker.txt").exists(),
                f"unsupported-platform {reported} reached the runtime",
            )
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _assert_package_layout(package: Path, targets: Sequence[str], *, runtime_output: str) -> None:
    """The shipped package must use the generator runtime root, never bin/."""

    for target in targets:
        expected = package.joinpath(runtime_output, target, *RUNTIME_LEAF)
        _require(
            expected.is_file() and os.access(expected, os.X_OK),
            f"package is missing the executable runtime at {runtime_output}/{target}",
        )
        _require(
            not package.joinpath("bin", target).exists(),
            f"package places a runtime tree under bin/{target}",
        )


def _manifest_targets(package: Path) -> list[str]:
    manifest = package / "release-manifest.json"
    if not manifest.is_file():
        return []
    targets = _load_json(manifest).get("runtime_targets")
    return [item for item in targets if isinstance(item, str)] if isinstance(targets, list) else []


def _runtime_integrity_diagnose(
    package: Path,
    host: str,
    target: str,
    *,
    runtime_output: str,
) -> Mapping[str, Any]:
    runtime = package.joinpath(runtime_output, target, *RUNTIME_LEAF)
    _require(runtime.is_file(), "integrity diagnose runtime is missing")
    with tempfile.TemporaryDirectory(prefix="opensocrates-integrity-data-") as data_name:
        environment = dict(os.environ)
        environment["XDG_DATA_HOME"] = data_name
        completed = subprocess.run(
            (str(runtime), "diagnose", "--host", host, "--json"),
            cwd=package,
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    _require(completed.returncode == 0, "packaged integrity diagnose failed")
    try:
        decoded = json.loads(completed.stdout)
    except (TypeError, ValueError) as error:
        raise CheckFailure("packaged integrity diagnose returned invalid JSON") from error
    _require(isinstance(decoded, Mapping), "packaged integrity diagnose returned no object")
    manifest = decoded.get("manifest")
    _require(isinstance(manifest, Mapping), "packaged integrity diagnose omitted manifest status")
    return manifest


def _assert_integrity_tamper_detection(
    package: Path,
    host: str,
    target: str,
    *,
    runtime_output: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix="opensocrates-integrity-tamper-") as name:
        staged = Path(name) / package.name
        shutil.copytree(package, staged, symlinks=False)
        readme = staged / "README.md"
        _require(readme.is_file(), "tamper probe README is missing")
        readme.write_bytes(readme.read_bytes() + b"\nsynthetic-integrity-tamper\n")
        manifest = _runtime_integrity_diagnose(
            staged,
            host,
            target,
            runtime_output=runtime_output,
        )
        _require(
            manifest.get("status") == "verified" and manifest.get("checksum_status") == "mismatch",
            "packaged runtime did not report a staged checksum mismatch",
        )


def _exercised_targets() -> list[str]:
    """Cover the one target the released launcher is allowed to select."""

    return sorted(TARGET_UNAME)


def _assert_runtime_output_mismatch_fails(
    package: Path, host: str, target: str, *, runtime_output: str
) -> None:
    """Prove a wrong generator root fails without relying on native targets."""

    mismatched_output = f"{runtime_output}-mismatch"
    stage, runtime = _stage(package, target, runtime_parent=mismatched_output)
    assert runtime is not None
    try:
        try:
            _assert_dispatch(
                stage,
                runtime,
                ["hook", host, "user_prompt_submitted"],
                ["hook", "user_prompt_submitted", "--host", host],
                target,
            )
        except CheckFailure:
            return
        raise CheckFailure("generator/runtime-root mismatch unexpectedly reached the runtime")
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _check_package(package: Path, host: str, *, runtime_output: str) -> dict[str, Any]:
    targets = _exercised_targets()
    _require(
        not (package / "bin" / "launch.ps1").exists(),
        "package ships an unvalidated PowerShell launcher",
    )
    _assert_package_layout(
        package,
        _manifest_targets(package),
        runtime_output=runtime_output,
    )
    _assert_runtime_output_mismatch_fails(
        package,
        host,
        targets[0],
        runtime_output=runtime_output,
    )
    events: list[str] = []
    for target in targets:
        events = _check_hook_dispatch(
            package,
            host,
            target,
            runtime_output=runtime_output,
        )
        _check_control_mode(package, host, target, runtime_output=runtime_output)
        _assert_canonical_runtime_precedence(
            package,
            host,
            target,
            runtime_output=runtime_output,
        )
        _assert_fail_open(package, host, target, runtime_parent=None)
        # A runtime planted below bin/runtime/ must not satisfy the lookup when
        # the canonical package runtime is absent either.
        _assert_fail_open(package, host, target, runtime_parent="bin/runtime")
        _assert_control_diagnostic(package, host, target)
    _assert_unsupported_platform(package, host, runtime_output=runtime_output)
    return {
        "package": package.name,
        "runtime_output": runtime_output,
        "runtime_output_mismatch_rejected_without_native_targets": True,
        "bin_runtime_never_selected": True,
        "targets": targets,
        "unsupported_platforms_rejected": [
            f"{system}/{machine}" for system, machine in UNSUPPORTED_UNAMES
        ],
        "native_target": _native_target(),
        "events": events,
    }


def _package_trees(root: Path, host: str) -> Iterator[tuple[str, Path]]:
    candidates = (
        ("generated", root / "build" / "generated" / "plugins" / host),
        ("distributable", root / "dist" / host),
    )
    for label, path in candidates:
        if (path / Path(*LAUNCHER)).is_file():
            yield label, path


def check_root(root: Path) -> dict[str, Any]:
    results: dict[str, Any] = {"hosts": {}, "error_codes": []}
    errors: list[str] = []
    for host in HOSTS:
        try:
            runtime_output = _runtime_output(root, host)
        except CheckFailure as failure:
            results["hosts"][host] = {"generator": {"error": str(failure)}}
            errors.append(f"{host}_generator_runtime_output_invalid")
            continue
        trees = list(_package_trees(root, host))
        if not trees:
            errors.append(f"{host}_package_launcher_missing")
            continue
        host_result: dict[str, Any] = {}
        for label, package in trees:
            try:
                host_result[label] = _check_package(
                    package,
                    host,
                    runtime_output=runtime_output,
                )
                if label == "distributable":
                    target = _exercised_targets()[0]
                    integrity = _runtime_integrity_diagnose(
                        package,
                        host,
                        target,
                        runtime_output=runtime_output,
                    )
                    _require(
                        integrity.get("status") == "verified"
                        and integrity.get("checksum_status") == "verified",
                        f"{host} distributable integrity was not verified",
                    )
                    host_result[label]["integrity"] = dict(integrity)
                    if host == "claude":
                        _assert_integrity_tamper_detection(
                            package,
                            host,
                            target,
                            runtime_output=runtime_output,
                        )
                        host_result[label]["tamper_mismatch_detected"] = True
            except CheckFailure as failure:
                host_result[label] = {"error": str(failure)}
                errors.append(f"{host}_{label}_packaged_launcher_unreachable")
        results["hosts"][host] = host_result
    results["error_codes"] = sorted(set(errors))
    results["status"] = "fail" if errors else "pass"
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--report", default=None, help="optional JSON evidence path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    report = check_root(root)
    if args.report:
        destination = Path(args.report)
        if not destination.is_absolute():
            destination = root / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8")
    if report["status"] != "pass":
        print("opensocrates-packaged-launcher: FAIL")
        for host, trees in sorted(report["hosts"].items()):
            for label, value in sorted(trees.items()):
                if "error" in value:
                    print(f"- {host}/{label}: {value['error']}")
        for code in report["error_codes"]:
            print(f"- {code}")
        return 1
    covered = sorted({host for host in report["hosts"]})
    print(f"opensocrates-packaged-launcher: PASS hosts={','.join(covered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
