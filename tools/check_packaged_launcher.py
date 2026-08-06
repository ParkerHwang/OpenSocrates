#!/usr/bin/env python3
"""Execute the generated package launchers against the generated package layout.

The generated host packages ship the POSIX launcher at ``<plugin-root>/bin``
and the native runtime at ``<plugin-root>/runtime/<target>/...``.  A launcher
that resolves the runtime relative to its own directory therefore never finds
it, and because hook mode fails open with literal-empty stdout the breakage is
silent.  This check runs the *actual* launcher shipped in each generated
package, dispatching the *actual* hook arguments declared in that package's
``hooks/hooks.json``, and proves the runtime is reached from ``runtime/``.
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
RUNTIME_DIR = "runtime"
RUNTIME_LEAF = ("opensocrates-runtime", "opensocrates-runtime")
LAUNCHER = ("bin", "launch.sh")
STDOUT_TOKEN = "opensocrates-packaged-launcher-stdout\n"
CONTROL_EXIT_CODE = 7

# Kept in sync with the platform table in packaging/launchers/launch.sh.
TARGET_UNAME: dict[str, tuple[str, str]] = {
    "darwin-arm64": ("Darwin", "arm64"),
    "darwin-x64": ("Darwin", "x86_64"),
    "linux-x64": ("Linux", "x86_64"),
}
NATIVE_TARGET: dict[tuple[str, str], str] = {
    ("Darwin", "arm64"): "darwin-arm64",
    ("Darwin", "aarch64"): "darwin-arm64",
    ("Darwin", "x86_64"): "darwin-x64",
    ("Darwin", "amd64"): "darwin-x64",
    ("Linux", "x86_64"): "linux-x64",
    ("Linux", "amd64"): "linux-x64",
}
UNSUPPORTED_UNAME = ("Linux", "aarch64")

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

    stage = Path(tempfile.mkdtemp(prefix="opensocrates-launcher-"))
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

    env = dict(os.environ)
    system, machine = TARGET_UNAME.get(target or "", UNSUPPORTED_UNAME)
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
        raise CheckFailure("the packaged launcher never invoked the runtime under runtime/")
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


def _check_hook_dispatch(package: Path, host: str, target: str) -> list[str]:
    """Dispatch every declared hook through the real launcher for one target."""

    specs = _dispatch_specs(package / "hooks" / "hooks.json")
    stage, runtime = _stage(package, target, runtime_parent=RUNTIME_DIR)
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


def _check_control_mode(package: Path, host: str, target: str) -> None:
    """Control mode must exec the runtime and propagate its exit status."""

    stage, runtime = _stage(package, target, runtime_parent=RUNTIME_DIR)
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
            "the launcher invoked a runtime outside runtime/",
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


def _assert_unsupported_platform(package: Path, host: str) -> None:
    stage, _runtime = _stage(package, "darwin-arm64", runtime_parent=RUNTIME_DIR)
    try:
        result = _run(stage, ["hook", host, "user_prompt_submitted"], _environment(stage, None))
        _require(result.returncode == 0, f"unsupported-platform hook exited {result.returncode}")
        _require(result.stdout == b"", f"unsupported-platform hook wrote {result.stdout!r}")
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _assert_package_layout(package: Path, targets: Sequence[str]) -> None:
    """The shipped package must carry its runtime under runtime/, never bin/."""

    for target in targets:
        expected = package.joinpath(RUNTIME_DIR, target, *RUNTIME_LEAF)
        _require(
            expected.is_file() and os.access(expected, os.X_OK),
            f"package is missing the executable runtime at {RUNTIME_DIR}/{target}",
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


def _exercised_targets() -> list[str]:
    """Cover every target the packaged launcher can select, native or not.

    A uname shim lets a Linux runner exercise the released ``darwin-arm64``
    selection and an Apple-silicon runner exercise the Linux selection, so the
    shared launcher contract is covered wherever the gate runs.
    """

    return sorted(TARGET_UNAME)


def _check_package(package: Path, host: str) -> dict[str, Any]:
    targets = _exercised_targets()
    _assert_package_layout(package, _manifest_targets(package))
    events: list[str] = []
    for target in targets:
        events = _check_hook_dispatch(package, host, target)
        _check_control_mode(package, host, target)
        _assert_fail_open(package, host, target, runtime_parent=None)
        # The pre-fix launcher probed <plugin-root>/bin/<target>/...; a runtime
        # planted there must not satisfy the lookup.
        _assert_fail_open(package, host, target, runtime_parent="bin")
        _assert_control_diagnostic(package, host, target)
    _assert_unsupported_platform(package, host)
    return {
        "package": package.name,
        "targets": targets,
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
        trees = list(_package_trees(root, host))
        if not trees:
            errors.append(f"{host}_package_launcher_missing")
            continue
        host_result: dict[str, Any] = {}
        for label, package in trees:
            try:
                host_result[label] = _check_package(package, host)
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
