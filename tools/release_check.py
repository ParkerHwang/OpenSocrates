#!/usr/bin/env python3
"""Assemble and verify the local v1 release surfaces.

This is a deliberately narrow release gate.  It invokes the existing schema,
content, link, security, runtime, plugin, and SBOM tools with argument vectors
and validates only machine-readable contracts.  Evidence contains counts,
statuses, hashes, and bounded reason codes; it never contains authored content,
host payloads, absolute paths, or command output.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claude_chat_evidence import evidence_path, validation_errors
from measure_codex_hook_timing import PROCESS_MODEL

SCHEMA = "opensocrates.release-check-evidence/1.0.0"
HOSTS = ("antigravity", "claude", "codex", "cursor", "grok", "opencode")
RUNTIME_HOSTS = ("claude", "codex")
# Grok ships content only. OpenCode additionally ships an owned plugin bridge,
# so it is not content-only, but it still carries no native runtime payload.
CONTENT_ONLY_HOSTS = frozenset({"antigravity", "cursor", "grok"})
NO_NATIVE_RUNTIME_HOSTS = CONTENT_ONLY_HOSTS | frozenset({"opencode"})
GROK_LIVE_PROBE_STATUS = (
    "native_skill_headless_verified; explicit_headless_verified; "
    "tui_hook_execution_verified; plugin_hooks_unavailable"
)
OPENCODE_LIVE_PROBE_STATUS = "validated_same_turn_run_and_tui_opencode_1.18.18"


def _live_host_probe_status(*, opencode_validated: bool) -> dict[str, str]:
    """Per-host live probe status, each host tied to its own recorded evidence."""

    status = {host: "unvalidated" for host in HOSTS}
    status["grok"] = GROK_LIVE_PROBE_STATUS
    if opencode_validated:
        status["opencode"] = OPENCODE_LIVE_PROBE_STATUS
    return status


EXPECTED_METHOD_COUNT = 48
LEGACY_CONTENT_BUNDLE = "content/compiled-content.bundle.json"
REASONING_CONTENT_BUNDLE = "content/compiled-reasoning-content.bundle.json"
RUNTIME_ENTRY = "packaging/pyinstaller/runtime_entry.py"
RUNTIME_ENTRY_APPROVED_IMPORTS = frozenset({"json", "multiprocessing", "opensocrates", "sys"})
THIRD_PARTY_NOTICE = "THIRD_PARTY_NOTICES.md"
RELEASE_TARGET = "darwin-arm64"
RELEASE_LAUNCHERS = ["bin/launch.sh"]
RUNTIME_NOTICE_REQUIRED_TOKENS = frozenset(
    {
        "openai-codex",
        "openai-codex-cli-bin",
        "0.144.4",
        "pydantic",
        "sbom",
        "license",
    }
)
CLAUDE_RUNTIME_NOTICE_REQUIRED_TOKENS = frozenset(
    {
        "claude code cli",
        "excludes the openai codex sdk",
        "pydantic",
        "sbom",
        "license",
    }
)
# Cowork documents these limits in decimal MB.  Use the conservative byte
# interpretation until the product exposes an exact binary-unit contract.
CLAUDE_ARCHIVE_COMPRESSED_LIMIT_BYTES = 50_000_000
CLAUDE_ARCHIVE_UNCOMPRESSED_LIMIT_BYTES = 200_000_000
CLAUDE_PLUGIN_RENDER_PROFILE = "plugin"
CLAUDE_CHAT_RENDER_PROFILE = "chat-standalone"
CLAUDE_PLUGIN_INVOCATION_MARKER = (
    "`/opensocrates:opensocrates` is the canonical explicit invocation for this "
    "Claude Code/Cowork plugin skill."
)
CLAUDE_CHAT_INVOCATION_MARKER = (
    "`/opensocrates` is the canonical explicit invocation for this standalone Claude Chat skill."
)
_SAFE_ENVIRONMENT = {
    "PATH",
    "HOME",
    "USER",
    "TMPDIR",
    "TEMP",
    "TMP",
    "CI",
    "GITHUB_ACTIONS",
    "RUNNER_OS",
    "UV_CACHE_DIR",
    "SOURCE_DATE_EPOCH",
    "PYTHONUTF8",
    "PYTHONDONTWRITEBYTECODE",
}


class ReleaseCheckError(RuntimeError):
    """Raised for a bounded release assembly or validation failure."""


class AssemblyUnavailable(ReleaseCheckError):
    """Raised when a native build-only capability is not available."""


@dataclass(frozen=True)
class CommandResult:
    status: str
    code: str


def _valid_codex_session_start_timing_evidence(
    value: object, *, expected_artifact_identity: str
) -> bool:
    """Independently enforce the closed packaged-hook timing contract."""

    expected_keys = {
        "target",
        "artifact_identity",
        "process_model",
        "sample_count",
        "latency_ms",
        "configured_timeout_ms",
        "pass",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        return False

    artifact_identity = value.get("artifact_identity")
    process_model = value.get("process_model")
    sample_count = value.get("sample_count")
    configured_timeout_ms = value.get("configured_timeout_ms")
    latencies = value.get("latency_ms")
    if (
        value.get("target") != RELEASE_TARGET
        or not isinstance(artifact_identity, str)
        or len(artifact_identity) != len("sha256:") + 64
        or not artifact_identity.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in artifact_identity[7:])
        or artifact_identity != expected_artifact_identity
        or process_model != PROCESS_MODEL
        or type(sample_count) is not int
        or sample_count != 20
        or type(configured_timeout_ms) is not int
        or configured_timeout_ms != 2000
        or value.get("pass") is not True
        or not isinstance(latencies, Mapping)
        or set(latencies) != {"first", "p50", "p95", "max"}
    ):
        return False

    observed: dict[str, int | float] = {}
    for key in ("first", "p50", "p95", "max"):
        latency = latencies[key]
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or (isinstance(latency, float) and not math.isfinite(latency))
            or latency < 0
        ):
            return False
        observed[key] = latency
    return (
        observed["p50"] <= observed["p95"] <= observed["max"]
        and observed["first"] <= observed["max"]
        and observed["first"] < 2000
        and observed["max"] < 2000
        and observed["p95"] <= 1000
    )


def _codex_session_start_timing_check(
    root: Path, assembly_status: str, timing_evidence: object
) -> dict[str, Any]:
    """Project only validated timing evidence into the aggregate release report."""

    expected_identity = _codex_package_manifest_identity(root)
    timing_evidence_valid = expected_identity is not None and (
        _valid_codex_session_start_timing_evidence(
            timing_evidence, expected_artifact_identity=expected_identity
        )
    )
    return {
        "status": (
            "pass"
            if timing_evidence_valid
            else assembly_status
            if assembly_status in {"fail", "unavailable"}
            else "fail"
        ),
        "evidence": (
            dict(timing_evidence)
            if timing_evidence_valid and isinstance(timing_evidence, Mapping)
            else None
        ),
        "error_codes": (
            [] if timing_evidence_valid else ["codex_session_start_timing_not_passing"]
        ),
    }


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _pretty_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_pretty_json(value), encoding="utf-8")


def _iso_now() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.isdigit():
        return (
            datetime.fromtimestamp(int(epoch), UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "outside-root"


def _safe_environment(root: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key in _SAFE_ENVIRONMENT}
    environment["PYTHONPATH"] = str(root / "src")
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return environment


def _run(
    command: Sequence[str],
    root: Path,
    *,
    timeout: float = 300.0,
    interpreter: str | None = None,
) -> CommandResult:
    argv = list(command)
    if interpreter is not None:
        argv.insert(0, interpreter)
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            env=_safe_environment(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        return CommandResult("unavailable", "executable_missing")
    except subprocess.TimeoutExpired:
        return CommandResult("unavailable", "timeout")
    except OSError:
        return CommandResult("unavailable", "process_error")
    return (
        CommandResult("pass", "ok")
        if completed.returncode == 0
        else CommandResult("fail", f"exit_{completed.returncode}")
    )


def _load_json(path: Path) -> Mapping[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _codex_package_manifest_identity(root: Path) -> str | None:
    manifest = root / "dist" / "codex" / "release-manifest.json"
    try:
        if manifest.is_symlink() or not manifest.is_file():
            return None
        return f"sha256:{_sha256(manifest)}"
    except OSError:
        return None


def _snapshot(path: Path) -> dict[str, tuple[int, str]]:
    if not path.exists():
        return {}
    if path.is_file():
        return {path.name: (path.stat().st_size, _sha256(path))}
    result: dict[str, tuple[int, str]] = {}
    for child in sorted(
        path.rglob("*"),
        key=lambda item: item.relative_to(path).as_posix().encode("utf-8"),
    ):
        if child.is_file() and not child.is_symlink():
            result[child.relative_to(path).as_posix()] = (
                child.stat().st_size,
                _sha256(child),
            )
    return result


def _read_version(root: Path) -> str:
    try:
        document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseCheckError("project_version_unavailable") from exc
    value = document.get("project", {}).get("version")
    if not isinstance(value, str) or not value:
        raise ReleaseCheckError("project_version_invalid")
    version_file = root / "VERSION"
    if not version_file.is_file():
        raise ReleaseCheckError("version_file_missing")
    try:
        legacy_value = version_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise ReleaseCheckError("version_file_unavailable") from exc
    if legacy_value != value:
        raise ReleaseCheckError("version_sources_mismatch")
    return value


def _load_bundle(root: Path) -> tuple[Mapping[str, Any], bytes]:
    path = root / LEGACY_CONTENT_BUNDLE
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseCheckError("compiled_bundle_unavailable") from exc
    if not isinstance(value, Mapping):
        raise ReleaseCheckError("compiled_bundle_not_object")
    return value, raw


def _load_reasoning_content_bundle(root: Path) -> tuple[Mapping[str, Any], bytes]:
    path = root / REASONING_CONTENT_BUNDLE
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseCheckError("reasoning_content_bundle_unavailable") from exc
    if not isinstance(value, Mapping):
        raise ReleaseCheckError("reasoning_content_bundle_not_object")
    return value, raw


def _check_bundle_shape(bundle: Mapping[str, Any], version: str) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    expected_fields = {
        "schema",
        "product_version",
        "content_revision",
        "method_ids",
        "methods",
        "locale_messages",
        "prompt_fragments",
        "policy_versions",
        "source_tree_hash",
        "normalized_semantic_hash",
    }
    errors: set[str] = set()
    if set(bundle) != expected_fields:
        errors.add("bundle_fields_mismatch")
    if bundle.get("product_version") != version:
        errors.add("bundle_version_mismatch")
    method_ids = bundle.get("method_ids")
    methods = bundle.get("methods")
    if not isinstance(method_ids, list) or not isinstance(methods, list):
        errors.add("bundle_methods_invalid")
        method_ids = []
        methods = []
    if len(method_ids) != EXPECTED_METHOD_COUNT or len(methods) != EXPECTED_METHOD_COUNT:
        errors.add("bundle_method_count_invalid")
    if [item.get("id") for item in methods if isinstance(item, Mapping)] != method_ids:
        errors.add("bundle_method_order_mismatch")
    if len(set(method_ids)) != len(method_ids):
        errors.add("bundle_method_ids_not_unique")
    locales = bundle.get("locale_messages")
    fragments = bundle.get("prompt_fragments")
    if not isinstance(locales, Mapping) or set(locales) != {"en", "ko"}:
        errors.add("bundle_locales_invalid")
    if not isinstance(fragments, Mapping) or set(fragments) != {
        "controller",
        "participation_rigor",
        "routing_classifier",
        "framing",
        "evidence_card_completion",
        "cross_exam",
        "strict_second_pass",
        "capability_notice",
    }:
        errors.add("bundle_fragments_invalid")
    for field in ("source_tree_hash", "normalized_semantic_hash"):
        value = bundle.get(field)
        if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
            errors.add(f"bundle_{field}_invalid")
    return {
        "status": "fail" if errors else "pass",
        "method_count": len(methods),
        "locale_count": len(locales) if isinstance(locales, Mapping) else 0,
        "source_tree_hash": bundle.get("source_tree_hash")
        if isinstance(bundle.get("source_tree_hash"), str)
        else None,
        "normalized_semantic_hash": bundle.get("normalized_semantic_hash")
        if isinstance(bundle.get("normalized_semantic_hash"), str)
        else None,
        "error_codes": sorted(errors),
    }


def _check_reasoning_content_bundle_shape(
    bundle: Mapping[str, Any], expected_content_revision: object
) -> dict[str, Any]:
    expected_fields = {"schema", "content_revision", "selection_catalog", "injectable_content"}
    errors: set[str] = set()
    if set(bundle) != expected_fields:
        errors.add("reasoning_content_bundle_fields_mismatch")
    if bundle.get("schema") != "opensocrates.reasoning-content-projections/1.0.0":
        errors.add("reasoning_content_bundle_schema_invalid")
    if bundle.get("content_revision") != expected_content_revision:
        errors.add("reasoning_content_bundle_revision_mismatch")
    if not isinstance(bundle.get("selection_catalog"), Mapping):
        errors.add("reasoning_content_bundle_catalog_invalid")
    if not isinstance(bundle.get("injectable_content"), list) or not bundle["injectable_content"]:
        errors.add("reasoning_content_bundle_injectable_content_invalid")
    return {"status": "fail" if errors else "pass", "error_codes": sorted(errors)}


def _schema_manifest_files(root: Path) -> set[str]:
    """Return the canonical schema filenames registered by the source manifest."""

    try:
        lines = (
            (root / "schemas" / "source" / "schema-manifest.yaml")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    except (OSError, UnicodeError):
        return set()
    prefix = "  - file: "
    files = [line.removeprefix(prefix) for line in lines if line.startswith(prefix)]
    if not files or len(files) != len(set(files)) or any("/" in name for name in files):
        return set()
    return set(files)


def _schema_surface(root: Path) -> dict[str, Any]:
    directory = root / "schemas" / "v1"
    files = sorted(directory.glob("*.json"), key=lambda item: item.name.encode("utf-8"))
    errors: set[str] = set()
    if {path.name for path in files} != _schema_manifest_files(root):
        errors.add("schema_count_invalid")
    for path in files:
        if _load_json(path) is None:
            errors.add("schema_json_invalid")
    return {
        "status": "fail" if errors else "pass",
        "schema_count": len(files),
        "error_codes": sorted(errors),
    }


def _content_validator(
    root: Path, expected_legacy: bytes, expected_reasoning_content: bytes
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="opensocrates-content-check-") as directory:
        output_root = Path(directory)
        output = output_root / "compiled-content.bundle.json"
        reasoning_content_output = output_root / "compiled-reasoning-content.bundle.json"
        result = _run(
            [
                str(root / "tools" / "validate_content.py"),
                "--content-root",
                str(root / "content"),
                "--output",
                str(output),
                "--reasoning-projections-output",
                str(reasoning_content_output),
            ],
            root,
            interpreter=sys.executable,
            timeout=300.0,
        )
        if result.status != "pass":
            return {"status": result.status, "error_codes": [f"content_{result.code}"]}
        if not output.is_file() or output.read_bytes() != expected_legacy:
            return {"status": "fail", "error_codes": ["content_bundle_byte_mismatch"]}
        if (
            not reasoning_content_output.is_file()
            or reasoning_content_output.read_bytes() != expected_reasoning_content
        ):
            return {
                "status": "fail",
                "error_codes": ["reasoning_content_bundle_byte_mismatch"],
            }
    return {"status": "pass", "error_codes": []}


def _generation_run(root: Path, output_root: Path) -> CommandResult:
    commands = [
        [
            str(root / "tools" / "generate_schemas.py"),
            "--output-dir",
            str(output_root / "schemas"),
        ],
        [
            str(root / "tools" / "validate_content.py"),
            "--content-root",
            str(root / "content"),
            "--output",
            str(output_root / "content" / "compiled-content.bundle.json"),
            "--reasoning-projections-output",
            str(output_root / "content" / "compiled-reasoning-content.bundle.json"),
        ],
    ]
    for command in commands:
        result = _run(command, root, interpreter=sys.executable, timeout=300.0)
        if result.status != "pass":
            return result
    for host in HOSTS:
        result = _run(
            [
                str(root / "tools" / "build_plugins.py"),
                "--root",
                str(root),
                "--host",
                host,
                "--runtime-root",
                str(root / "dist" / "runtime" / host),
                "--output",
                str(output_root / "plugins" / host),
            ],
            root,
            interpreter=sys.executable,
            timeout=300.0,
        )
        if result.status != "pass":
            return result
    return CommandResult("pass", "ok")


def _determinism_check(root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="opensocrates-generation-") as directory:
        base = Path(directory)
        first = base / "first output — 日本語"
        second = base / "second output — 한국어"
        first.mkdir()
        second.mkdir()
        first_result = _generation_run(root, first)
        second_result = _generation_run(root, second)
        if first_result.status != "pass" or second_result.status != "pass":
            code = first_result.code if first_result.status != "pass" else second_result.code
            status = first_result.status if first_result.status != "pass" else second_result.status
            return {
                "status": status,
                "run_count": 2,
                "error_codes": [f"generation_{code}"],
            }
        surfaces = (
            ("schemas/v1", first / "schemas" / "v1", second / "schemas" / "v1"),
            (
                LEGACY_CONTENT_BUNDLE,
                first / LEGACY_CONTENT_BUNDLE,
                second / LEGACY_CONTENT_BUNDLE,
            ),
            (
                REASONING_CONTENT_BUNDLE,
                first / REASONING_CONTENT_BUNDLE,
                second / REASONING_CONTENT_BUNDLE,
            ),
            *(
                (
                    f"plugins/{host}",
                    first / "plugins" / host,
                    second / "plugins" / host,
                )
                for host in HOSTS
            ),
        )
        total_files = 0
        differences = 0
        for _, left, right in surfaces:
            left_snapshot = _snapshot(left)
            right_snapshot = _snapshot(right)
            total_files += len(left_snapshot)
            differences += sum(
                left_snapshot.get(key) != right_snapshot.get(key)
                for key in set(left_snapshot) | set(right_snapshot)
            )
        return {
            "status": "pass" if differences == 0 else "fail",
            "run_count": 2,
            "file_count": total_files,
            "differences": differences,
            "path_shape": "spaces-and-unicode",
            "error_codes": [] if differences == 0 else ["generation_output_mismatch"],
        }


def _generated_output_check(root: Path) -> dict[str, Any]:
    """Rebuild once in a path-shaped temp tree and compare current outputs."""

    with tempfile.TemporaryDirectory(prefix="opensocrates-generated-check-") as directory:
        output = Path(directory) / "generated output — 日本語"
        output.mkdir()
        result = _generation_run(root, output)
        if result.status != "pass":
            return {
                "status": result.status,
                "run_count": 1,
                "error_codes": [f"generation_{result.code}"],
            }
        surfaces = (
            (root / "schemas" / "v1", output / "schemas" / "v1"),
            (
                root / LEGACY_CONTENT_BUNDLE,
                output / LEGACY_CONTENT_BUNDLE,
            ),
            (
                root / REASONING_CONTENT_BUNDLE,
                output / REASONING_CONTENT_BUNDLE,
            ),
            *(
                (
                    root / "build" / "generated" / "plugins" / host,
                    output / "plugins" / host,
                )
                for host in HOSTS
            ),
        )
        total_files = 0
        differences = 0
        for reference, candidate in surfaces:
            reference_snapshot = _snapshot(reference)
            candidate_snapshot = _snapshot(candidate)
            total_files += len(reference_snapshot)
            differences += sum(
                reference_snapshot.get(key) != candidate_snapshot.get(key)
                for key in set(reference_snapshot) | set(candidate_snapshot)
            )
        return {
            "status": "pass" if differences == 0 else "fail",
            "run_count": 1,
            "file_count": total_files,
            "differences": differences,
            "path_shape": "spaces-and-unicode",
            "error_codes": [] if differences == 0 else ["committed_output_mismatch"],
        }


def _is_main_guard(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.Eq)
        and len(node.test.comparators) == 1
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == "__main__"
    )


def _is_freeze_support_call(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "multiprocessing"
        and node.value.func.attr == "freeze_support"
        and not node.value.args
        and not node.value.keywords
    )


def _is_multiprocessing_import(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Import)
        and len(node.names) == 1
        and node.names[0].name == "multiprocessing"
        and node.names[0].asname is None
    )


def _is_main_import(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module == "opensocrates.__main__"
        and any(alias.name == "main" and alias.asname is None for alias in node.names)
    )


def _is_main_dispatch(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "SystemExit"
        and len(node.exc.args) == 1
        and isinstance(node.exc.args[0], ast.Call)
        and isinstance(node.exc.args[0].func, ast.Name)
        and node.exc.args[0].func.id == "main"
    )


def _runtime_entry_check(root: Path) -> dict[str, Any]:  # noqa: C901  # Contract sequence.
    """Require unconditional PyInstaller child dispatch before application code."""

    path = root / RUNTIME_ENTRY
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename="<runtime-entry>")
    except FileNotFoundError:
        return {"status": "unavailable", "error_codes": ["runtime_entry_source_missing"]}
    except (OSError, UnicodeError, SyntaxError):
        return {"status": "fail", "error_codes": ["runtime_entry_source_parse_error"]}

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module != "__future__":
            imports.add(node.module.split(".", 1)[0] if node.module else "")

    errors: set[str] = set()
    if imports != RUNTIME_ENTRY_APPROVED_IMPORTS:
        errors.add("runtime_entry_import_set_invalid")
    guard = next((node for node in tree.body if _is_main_guard(node)), None)
    if not isinstance(guard, ast.If):
        errors.add("runtime_entry_main_guard_missing")
    else:
        main_import_index = next(
            (index for index, node in enumerate(guard.body) if _is_main_import(node)),
            None,
        )
        dispatch_index = next(
            (index for index, node in enumerate(guard.body) if _is_main_dispatch(node)),
            None,
        )
        if len(guard.body) < 2 or not _is_multiprocessing_import(guard.body[0]):
            errors.add("runtime_entry_multiprocessing_import_missing")
        if len(guard.body) < 2 or not _is_freeze_support_call(guard.body[1]):
            errors.add("runtime_entry_freeze_support_missing")
        if main_import_index is None or dispatch_index is None:
            errors.add("runtime_entry_dispatch_missing")
        elif not (1 < main_import_index < dispatch_index):
            errors.add("runtime_entry_freeze_support_order_invalid")
    return {
        "status": "fail" if errors else "pass",
        "approved_imports": sorted(RUNTIME_ENTRY_APPROVED_IMPORTS),
        "error_codes": sorted(errors),
    }


def _discover_build_python() -> str | None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    candidates: list[Path] = [Path(sys.executable)]
    launcher = shutil.which("pyinstaller")
    if launcher:
        path = Path(launcher)
        try:
            first_line = path.read_text(encoding="utf-8").splitlines()[0]
        except (OSError, UnicodeError, IndexError):
            first_line = ""
        if first_line.startswith("#!"):
            shebang = first_line[2:].strip().split()
            if shebang and shebang[0].endswith("env") and len(shebang) > 1:
                resolved = shutil.which(shebang[-1])
                if resolved:
                    candidates.append(Path(resolved))
            elif shebang:
                candidates.append(Path(shebang[0]))
        candidates.append(path.parent / "python")
    seen: set[str] = set()
    for candidate in candidates:
        try:
            # Preserve a virtual-environment symlink: resolving it to the
            # shared interpreter can discard that environment's site-packages.
            resolved = os.path.abspath(os.fspath(candidate))
        except OSError:
            continue
        if resolved in seen or not Path(resolved).is_file():
            continue
        seen.add(resolved)
        try:
            completed = subprocess.run(
                [resolved, "-c", "import PyInstaller"],
                env=_safe_environment(Path.cwd()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10.0,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0:
            return resolved
    return None


def _runtime_build(  # noqa: C901  # Explicit host release build validation.
    root: Path, host: str
) -> tuple[dict[str, Any], str]:
    if host not in RUNTIME_HOSTS:
        raise ReleaseCheckError("runtime_host_invalid")
    build_python = _discover_build_python()
    if build_python is None:
        raise AssemblyUnavailable("pyinstaller_unavailable")
    result = _run(
        [
            str(root / "tools" / "build_runtime.py"),
            "runtime",
            "--root",
            str(root),
            "--target",
            "auto",
            "--runtime-profile",
            host,
            "--smoke-test",
            "--measure-runs",
            "20" if host == "codex" else "10",
            "--report",
            f"build/evidence/runtime-build-{host}.json",
        ],
        root,
        interpreter=build_python,
        timeout=900.0,
    )
    report = _load_json(root / "build" / "evidence" / f"runtime-build-{host}.json")
    if result.status != "pass":
        reason = result.code
        if report is not None and isinstance(report.get("status"), str):
            reason = f"runtime_{report['status']}"
        raise (
            AssemblyUnavailable(reason)
            if result.status == "unavailable"
            else ReleaseCheckError(reason)
        )
    if report is None or report.get("status") != "pass":
        raise ReleaseCheckError("runtime_evidence_not_passing")
    if report.get("runtime_profile") != host:
        raise ReleaseCheckError("runtime_profile_evidence_invalid")
    artifact = report.get("artifact")
    target = report.get("target")
    runtime_dependencies = report.get("runtime_dependencies")
    content_assets = report.get("content_assets")
    if not isinstance(artifact, str) or not isinstance(target, str):
        raise ReleaseCheckError("runtime_evidence_shape_invalid")
    if target != RELEASE_TARGET:
        raise AssemblyUnavailable("native_release_target_unavailable")
    if (
        not isinstance(runtime_dependencies, Mapping)
        or runtime_dependencies.get("status") != "ready"
    ):
        raise ReleaseCheckError("runtime_dependency_evidence_invalid")
    if (
        not isinstance(content_assets, Mapping)
        or not isinstance(content_assets.get("source"), Mapping)
        or not isinstance(content_assets.get("packaged"), Mapping)
        or content_assets["packaged"].get("status") != "pass"
        or set(content_assets["source"]) != {LEGACY_CONTENT_BUNDLE, REASONING_CONTENT_BUNDLE}
    ):
        raise ReleaseCheckError("runtime_content_asset_evidence_invalid")
    artifact_path = _resolve(root, artifact)
    if not artifact_path.is_file():
        raise ReleaseCheckError("runtime_artifact_missing")
    return dict(report), target


def _generate_plugins(root: Path) -> None:
    for host in HOSTS:
        result = _run(
            [
                str(root / "tools" / "build_plugins.py"),
                "--root",
                str(root),
                "--host",
                host,
                "--runtime-root",
                str(root / "dist" / "runtime" / host),
                "--output",
                str(root / "build" / "generated" / "plugins" / host),
            ],
            root,
            interpreter=sys.executable,
            timeout=300.0,
        )
        if result.status != "pass":
            raise ReleaseCheckError(f"plugin_generation_{host}_{result.code}")


def _safe_remove(path: Path, root: Path) -> None:
    resolved = path.resolve()
    if resolved in {root.resolve(), Path("/")} or not resolved.is_relative_to(root.resolve()):
        raise ReleaseCheckError("unsafe_output_path")
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _copy_packages(root: Path) -> None:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    for host in HOSTS:
        source = root / "build" / "generated" / "plugins" / host
        if not source.is_dir():
            raise ReleaseCheckError(f"generated_package_{host}_missing")
        destination = dist / host
        if destination.exists():
            _safe_remove(destination, dist)
        shutil.copytree(source, destination, symlinks=False)


def _codex_session_start_timing(root: Path) -> dict[str, Any]:
    """Run the final generated Codex hook before any final-package version smoke."""

    report_path = root / "build" / "evidence" / "codex-session-start-timing.json"
    result = _run(
        [
            str(root / "tools" / "measure_codex_hook_timing.py"),
            "--package",
            str(root / "dist" / "codex"),
            "--runs",
            "20",
            "--report",
            str(report_path),
        ],
        root,
        interpreter=sys.executable,
        timeout=300.0,
    )
    report = _load_json(report_path)
    if result.status != "pass" or report is None:
        raise ReleaseCheckError("codex_session_start_timing_failed")
    expected_identity = _codex_package_manifest_identity(root)
    if expected_identity is None or not _valid_codex_session_start_timing_evidence(
        report, expected_artifact_identity=expected_identity
    ):
        raise ReleaseCheckError("codex_session_start_timing_invalid")
    return dict(report)


def _build_claude_chat_skills(root: Path) -> Path:
    """Render the standalone profile into the single-root Chat upload shape."""

    destination = root / "dist" / "claude-chat-skills"
    if destination.exists():
        _safe_remove(destination, root / "dist")
    with tempfile.TemporaryDirectory(prefix="opensocrates-claude-chat-render-") as directory:
        temporary = Path(directory)
        source = temporary / "generated"
        result = _run(
            [
                str(root / "tools" / "build_plugins.py"),
                "--root",
                str(root),
                "--host",
                "claude",
                "--render-profile",
                CLAUDE_CHAT_RENDER_PROFILE,
                "--runtime-root",
                str(temporary / "runtime-not-shipped"),
                "--output",
                str(source),
            ],
            root,
            interpreter=sys.executable,
            timeout=300.0,
        )
        if result.status != "pass":
            raise ReleaseCheckError(f"claude_chat_generation_{result.code}")
        source_skill = source / "skills" / "opensocrates"
        if not (source_skill / "SKILL.md").is_file():
            raise ReleaseCheckError("claude_chat_source_missing")
        destination.mkdir(parents=True)
        skill_root = destination / "opensocrates"
        shutil.copytree(source_skill, skill_root, symlinks=False)
    shutil.copy2(root / "LICENSE", skill_root / "LICENSE", follow_symlinks=False)
    return destination


def _write_package_checksums(directory: Path) -> Path:
    destination = directory / "checksums.sha256"
    rows: list[str] = []
    for path in sorted(
        directory.rglob("*"),
        key=lambda item: item.relative_to(directory).as_posix().encode("utf-8"),
    ):
        if not path.is_file() or path == destination or path.is_symlink():
            continue
        rows.append(f"{_sha256(path)}  {path.relative_to(directory).as_posix()}\n")
    destination.write_text("".join(rows), encoding="utf-8")
    return destination


class _StrictUtf8ZipInfo(zipfile.ZipInfo):
    """Emit an explicit UTF-8 flag even when a member name is ASCII-only."""

    def _encodeFilenameFlags(self) -> tuple[bytes, int]:  # noqa: N802
        return self.filename.encode("utf-8"), self.flag_bits | 0x0800


def _write_deterministic_zip(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(
            source.rglob("*"),
            key=lambda item: item.relative_to(source).as_posix().encode("utf-8"),
        ):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(source).as_posix()
            info = _StrictUtf8ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.create_version = 20
            info.extract_version = 20
            info.external_attr = ((stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)) & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


def _candidate_platforms(root: Path, target: str) -> dict[str, str]:
    document = _load_json(root / "packaging" / "platforms.json") or {}
    candidates = document.get("candidate_platforms", [])
    observed = document.get("observed_local_platforms", [])
    released = document.get("release_targets", [])
    if not isinstance(candidates, list):
        candidates = []
    if not isinstance(observed, list):
        observed = []
    if not isinstance(released, list):
        released = []
    result = {
        str(value): (
            "observed_local"
            if value == target and value in observed and value in released
            else "not_shipped"
        )
        for value in candidates
        if isinstance(value, str)
    }
    if target not in result:
        result[target] = "observed_local" if target in released else "not_shipped"
    return dict(sorted(result.items()))


def _write_root_checksums(directory: Path, version: str) -> Path:
    destination = directory / f"opensocrates-{version}-checksums.sha256"
    rows: list[str] = []
    for path in sorted(
        directory.rglob("*"),
        key=lambda item: item.relative_to(directory).as_posix().encode("utf-8"),
    ):
        if not path.is_file() or path == destination or path.is_symlink():
            continue
        rows.append(f"{_sha256(path)}  {path.relative_to(directory).as_posix()}\n")
    destination.write_text("".join(rows), encoding="utf-8")
    return destination


def _assemble(  # noqa: C901  # Explicit runtime/content-only release assembly.
    root: Path,
) -> dict[str, Any]:
    version = _read_version(root)
    bundle, bundle_bytes = _load_bundle(root)
    reasoning_content_bundle, reasoning_content_bytes = _load_reasoning_content_bundle(root)
    runtime_entry = _runtime_entry_check(root)
    if runtime_entry["status"] != "pass":
        raise ReleaseCheckError("runtime_entry_contract_invalid")
    bundle_shape = _check_bundle_shape(bundle, version)
    if bundle_shape["status"] != "pass":
        raise ReleaseCheckError("bundle_shape_invalid")
    reasoning_content_shape = _check_reasoning_content_bundle_shape(
        reasoning_content_bundle, bundle.get("content_revision")
    )
    if reasoning_content_shape["status"] != "pass":
        raise ReleaseCheckError("reasoning_content_bundle_shape_invalid")
    runtime_reports: dict[str, dict[str, Any]] = {}
    targets: set[str] = set()
    for host in RUNTIME_HOSTS:
        runtime_report, runtime_target = _runtime_build(root, host)
        runtime_reports[host] = runtime_report
        targets.add(runtime_target)
    if targets != {RELEASE_TARGET}:
        raise AssemblyUnavailable("native_release_target_unavailable")
    target = RELEASE_TARGET
    _generate_plugins(root)
    _copy_packages(root)
    dist = root / "dist"
    claude_chat_package = _build_claude_chat_skills(root)
    package_checksums = {host: _write_package_checksums(dist / host) for host in HOSTS}
    # This is the first process execution from the final Codex package path.
    # Runtime version validation happens later in _full_check.
    codex_session_start_timing = _codex_session_start_timing(root)
    archives: dict[str, Path] = {}
    for host in HOSTS:
        archive = dist / f"opensocrates-{version}-{host}-plugin.zip"
        _write_deterministic_zip(dist / host, archive)
        archives[host] = archive
    claude_chat_archive = dist / f"opensocrates-{version}-claude-chat-skills.zip"
    _write_deterministic_zip(claude_chat_package, claude_chat_archive)
    runtime_artifacts = {host: str(runtime_reports[host]["artifact"]) for host in RUNTIME_HOSTS}
    sbom_arguments = [
        str(root / "tools" / "build_sbom.py"),
        "--root",
        str(root),
        "--output",
        "build/evidence/sbom.spdx.json",
        "--report",
        "build/evidence/sbom.json",
        "--artifact",
        LEGACY_CONTENT_BUNDLE,
        "--artifact",
        REASONING_CONTENT_BUNDLE,
    ]
    for host in RUNTIME_HOSTS:
        sbom_arguments.extend(["--artifact", runtime_artifacts[host]])
    for host in HOSTS:
        sbom_arguments.extend(["--artifact", _relative(root, archives[host])])
    sbom_arguments.extend(["--artifact", _relative(root, claude_chat_archive)])
    sbom_result = _run(sbom_arguments, root, interpreter=sys.executable, timeout=300.0)
    if sbom_result.status != "pass":
        raise ReleaseCheckError(f"sbom_generation_{sbom_result.code}")
    sbom_source = root / "build" / "evidence" / "sbom.spdx.json"
    if not sbom_source.is_file():
        raise ReleaseCheckError("sbom_artifact_missing")
    sbom_destination = dist / f"opensocrates-{version}-sbom.spdx.json"
    sbom_destination.write_bytes(sbom_source.read_bytes())
    opencode_evidence = _opencode_compatibility_evidence(root)
    live_host_probe_status = _live_host_probe_status(
        opencode_validated=opencode_evidence["status"] == "pass"
    )
    limitations = {
        "schema": "opensocrates.limitations/1.0.0",
        "product_version": version,
        "native_release_targets": [RELEASE_TARGET],
        "native_launchers": RELEASE_LAUNCHERS,
        "platforms": _candidate_platforms(root, target),
        "signing_status": "unvalidated",
        "live_host_probe_status": live_host_probe_status,
        "clean_machine_install_status": "unvalidated",
        "source_archive_status": "not_attempted",
        "provenance_status": "not_attempted",
        "codex_sdk_runtime_status": "native_bundle_only; host and clean-install verification unvalidated",
    }
    limitations_path = dist / f"opensocrates-{version}-limitations.json"
    _write_json(limitations_path, limitations)
    aggregate = {
        "schema": "opensocrates.release-manifest/1.0.0",
        "product_version": version,
        "content_revision": bundle["content_revision"],
        "source_tree_hash": bundle["source_tree_hash"],
        "normalized_semantic_hash": bundle["normalized_semantic_hash"],
        "reasoning_content_bundle": {
            "path": REASONING_CONTENT_BUNDLE,
            "content_revision": reasoning_content_bundle["content_revision"],
            "size_bytes": len(reasoning_content_bytes),
            "sha256": f"sha256:{hashlib.sha256(reasoning_content_bytes).hexdigest()}",
        },
        "runtimes": {
            host: {
                "target": target,
                "artifact": runtime_artifacts[host],
                "artifact_size_bytes": runtime_reports[host].get("artifact_size_bytes"),
                "artifact_sha256": (f"sha256:{_sha256(_resolve(root, runtime_artifacts[host]))}"),
                "signing_status": "unvalidated",
                "dependencies": runtime_reports[host]["runtime_dependencies"],
                "dependency_inventory": runtime_reports[host].get("runtime_dependency_inventory"),
            }
            for host in RUNTIME_HOSTS
        },
        "codex_session_start_timing": codex_session_start_timing,
        "hosts": {
            host: {
                "package_tree": host,
                "release_targets": [] if host in NO_NATIVE_RUNTIME_HOSTS else [RELEASE_TARGET],
                "launchers": [] if host in NO_NATIVE_RUNTIME_HOSTS else RELEASE_LAUNCHERS,
                "package_file_count": len(_snapshot(dist / host)),
                "package_checksum_file": package_checksums[host].relative_to(dist).as_posix(),
                "archive": archives[host].relative_to(dist).as_posix(),
                "archive_sha256": f"sha256:{_sha256(archives[host])}",
            }
            for host in HOSTS
        },
        "portable_plugins": {
            "claude_chat_skills": {
                "package_tree": claude_chat_package.relative_to(dist).as_posix(),
                "package_file_count": len(_snapshot(claude_chat_package)),
                "archive": claude_chat_archive.relative_to(dist).as_posix(),
                "archive_sha256": f"sha256:{_sha256(claude_chat_archive)}",
                "automatic_hooks": False,
            }
        },
        "sbom": {
            "path": sbom_destination.relative_to(dist).as_posix(),
            "sha256": f"sha256:{_sha256(sbom_destination)}",
        },
        "limitations": limitations_path.relative_to(dist).as_posix(),
        "platforms": limitations["platforms"],
        "signing_status": "unvalidated",
        "live_host_probe_status": live_host_probe_status,
        "source_archive_status": "not_attempted",
        "provenance_status": "not_attempted",
    }
    manifest_path = dist / f"opensocrates-{version}-release-manifest.json"
    _write_json(manifest_path, aggregate)
    root_checksums = _write_root_checksums(dist, version)
    return {
        "status": "pass",
        "product_version": version,
        "content_revision": bundle["content_revision"],
        "bundle_size_bytes": len(bundle_bytes),
        "reasoning_content_bundle_size_bytes": len(reasoning_content_bytes),
        "reasoning_content_bundle_sha256": f"sha256:{hashlib.sha256(reasoning_content_bytes).hexdigest()}",
        "source_tree_hash": bundle["source_tree_hash"],
        "normalized_semantic_hash": bundle["normalized_semantic_hash"],
        "runtime_target": target,
        "runtime_artifacts": runtime_artifacts,
        "runtime_version_smoke": "pass",
        "codex_session_start_timing": codex_session_start_timing,
        "hosts": {
            host: {
                "generated_file_count": len(
                    _snapshot(root / "build" / "generated" / "plugins" / host)
                ),
                "package_file_count": len(_snapshot(dist / host)),
                "archive": archives[host].relative_to(dist).as_posix(),
            }
            for host in HOSTS
        },
        "claude_chat_skills": {
            "package_file_count": len(_snapshot(claude_chat_package)),
            "archive": claude_chat_archive.relative_to(dist).as_posix(),
        },
        "sbom": sbom_destination.relative_to(dist).as_posix(),
        "checksums": root_checksums.relative_to(dist).as_posix(),
        "limitations": limitations_path.relative_to(dist).as_posix(),
    }


def _verify_release_manifest(root: Path, host: str, bundle: Mapping[str, Any]) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    package = root / "build" / "generated" / "plugins" / host
    metadata = _load_json(package / "release-manifest.json")
    errors: set[str] = set()
    if metadata is None:
        return {
            "status": "unavailable",
            "error_codes": [f"{host}_release_manifest_missing"],
        }
    if metadata.get("product_version") != bundle.get("product_version"):
        errors.add("manifest_version_mismatch")
    expected_targets = [] if host in NO_NATIVE_RUNTIME_HOSTS else [RELEASE_TARGET]
    expected_launchers = [] if host in NO_NATIVE_RUNTIME_HOSTS else RELEASE_LAUNCHERS
    if metadata.get("release_targets") != expected_targets:
        errors.add("manifest_release_targets_invalid")
    if metadata.get("launchers") != expected_launchers:
        errors.add("manifest_launchers_invalid")
    for field in ("source_tree_hash", "normalized_semantic_hash"):
        if metadata.get(field) != bundle.get(field):
            errors.add(f"manifest_{field}_mismatch")
    if metadata.get("method_count") != EXPECTED_METHOD_COUNT or metadata.get(
        "method_ids"
    ) != bundle.get("method_ids"):
        errors.add("manifest_method_set_mismatch")
    if host == "claude" and metadata.get("render_profile") != CLAUDE_PLUGIN_RENDER_PROFILE:
        errors.add("claude_manifest_render_profile_invalid")
    files = metadata.get("files")
    if not isinstance(files, list):
        errors.add("manifest_files_invalid")
        files = []
    listed: set[str] = set()
    for item in files:
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("path"), str)
            or not isinstance(item.get("sha256"), str)
        ):
            errors.add("manifest_file_entry_invalid")
            continue
        relative = item["path"]
        listed.add(relative)
        candidate = package / relative
        if not candidate.is_file() or item["sha256"] != f"sha256:{_sha256(candidate)}":
            errors.add("manifest_file_hash_mismatch")
    actual = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file() and path.name != "release-manifest.json"
    }
    if listed != actual:
        errors.add("manifest_file_inventory_mismatch")
    return {
        "status": "fail" if errors else "pass",
        "file_count": len(actual) + 1,
        "method_count": metadata.get("method_count"),
        "runtime_target_count": len(metadata.get("runtime_targets", []))
        if isinstance(metadata.get("runtime_targets"), list)
        else 0,
        "error_codes": sorted(errors),
    }


def _verify_third_party_notice(package: Path, host: str) -> set[str]:
    notice = package / THIRD_PARTY_NOTICE
    try:
        text = notice.read_text(encoding="utf-8").casefold()
    except (OSError, UnicodeError):
        return {"third_party_notice_unreadable"}
    errors: set[str] = set()
    if host in CONTENT_ONLY_HOSTS:
        required = frozenset({"content-only", "no bundled", "runtime", "license"})
    elif host == "opencode":
        required = frozenset({"dependency-free", "does not bundle", "opencode", "license"})
    else:
        required = (
            CLAUDE_RUNTIME_NOTICE_REQUIRED_TOKENS
            if host == "claude"
            else RUNTIME_NOTICE_REQUIRED_TOKENS
        )
    if not all(token in text for token in required):
        errors.add("third_party_notice_runtime_disclosure_invalid")
    if host == "claude" and any(
        token in text for token in ("`openai-codex`", "`openai-codex-cli-bin`")
    ):
        errors.add("claude_third_party_notice_claims_excluded_runtime")
    return errors


def _contains_eval_or_adjudication_path(entries: Sequence[str]) -> bool:
    """Keep source-only evaluation evidence out of every shipped ZIP."""

    for entry in entries:
        parts = tuple(part.casefold() for part in entry.split("/") if part)
        if "evals" in parts or any("adjudication" in part for part in parts):
            return True
    return False


def _verify_host_surface(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    root: Path, host: str, bundle: Mapping[str, Any], bundle_bytes: bytes, target: str
) -> dict[str, Any]:
    generated = root / "build" / "generated" / "plugins" / host
    dist_package = root / "dist" / host
    errors: set[str] = set()
    metadata = _load_json(root / "plugin-src" / host / "generator.json")
    if metadata is None:
        return {
            "status": "unavailable",
            "error_codes": [f"{host}_generator_metadata_missing"],
        }
    raw_method_ids = bundle.get("method_ids")
    method_ids: set[str] = set()
    if isinstance(raw_method_ids, list) and all(
        isinstance(method_id, str) for method_id in raw_method_ids
    ):
        method_ids = set(raw_method_ids)
    else:
        errors.add("bundle_method_ids_invalid")
    skills = generated / "skills"
    method_output = metadata.get("method_output")
    method_outputs = (
        {str(method_output).replace("{method_id}", method_id) for method_id in method_ids}
        if isinstance(method_output, str)
        else set()
    )
    existing_method_outputs = {
        output for output in method_outputs if (generated / output).is_file()
    }
    if existing_method_outputs != method_outputs:
        errors.add("method_content_count_or_set_invalid")
    shared_templates = metadata.get("shared_templates", [])
    shared_outputs = {
        str(item.get("output"))
        for item in shared_templates
        if isinstance(item, Mapping) and isinstance(item.get("output"), str)
    }
    missing_shared = [output for output in shared_outputs if not (generated / output).is_file()]
    if missing_shared:
        errors.add("shared_skill_missing")
    top_level_shared_skills = {
        Path(output).parts[1]
        for output in shared_outputs
        if len(Path(output).parts) == 3
        and Path(output).parts[0] == "skills"
        and Path(output).parts[2] == "SKILL.md"
    }
    configured_public_skills = metadata.get("public_skills")
    expected_public_skills = (
        {str(value) for value in configured_public_skills if isinstance(value, str)}
        if isinstance(configured_public_skills, list)
        else method_ids | top_level_shared_skills
    )
    actual_public_skills = (
        {path.name for path in skills.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()}
        if skills.is_dir()
        else set()
    )
    if actual_public_skills != expected_public_skills:
        errors.add("public_skill_set_invalid")
    command_templates = metadata.get("command_templates", [])
    command_outputs = {
        str(item.get("output"))
        for item in command_templates
        if isinstance(item, Mapping)
        and isinstance(item.get("output"), str)
        and str(item.get("output")).startswith("commands/")
    }
    if any(not (generated / output).is_file() for output in command_outputs):
        errors.add("command_surface_missing")
    if host == "claude" and any((generated / "commands").glob("*.md")):
        errors.add("claude_duplicate_command_surface_present")
    if host == "codex":
        host_only_notice = "Never execute that control command directly"
        controller = generated / "skills" / "opensocrates" / "SKILL.md"
        rigor = generated / "skills" / "rigor" / "SKILL.md"
        guarded_surfaces = [controller, rigor, *(generated / output for output in method_outputs)]
        for surface in guarded_surfaces:
            try:
                contents = surface.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                errors.add("codex_control_boundary_notice_missing")
                break
            if host_only_notice not in contents:
                errors.add("codex_control_boundary_notice_missing")
                break
    schema_files = {
        path.name for path in (generated / "schemas" / "v1").glob("*.json") if path.is_file()
    }
    expected_schema_files = (
        set() if host in NO_NATIVE_RUNTIME_HOSTS else _schema_manifest_files(root)
    )
    schema_count = len(schema_files)
    if schema_files != expected_schema_files:
        errors.add("package_schema_count_invalid")
    required_files = ["LICENSE", THIRD_PARTY_NOTICE]
    if host not in NO_NATIVE_RUNTIME_HOSTS:
        required_files.append("bin/launch.sh")
    for required in required_files:
        if not (generated / required).is_file():
            errors.add("package_license_notice_or_launcher_missing")
    if (generated / "bin" / "launch.ps1").exists() or (
        dist_package / "bin" / "launch.ps1"
    ).exists():
        errors.add("unvalidated_powershell_launcher_present")
    errors.update(_verify_third_party_notice(generated, host))
    generated_notice = generated / THIRD_PARTY_NOTICE
    dist_notice = dist_package / THIRD_PARTY_NOTICE
    if not dist_notice.is_file() or (
        generated_notice.is_file() and dist_notice.read_bytes() != generated_notice.read_bytes()
    ):
        errors.add("packaged_third_party_notice_mismatch")
    if (generated / "bin" / "launch.sh").is_file() and not os.access(
        generated / "bin" / "launch.sh", os.X_OK
    ):
        errors.add("posix_launcher_not_executable")
    if host == "claude":
        plugin_manifest = _load_json(generated / ".claude-plugin" / "plugin.json")
        if plugin_manifest is None:
            errors.add("claude_plugin_manifest_missing")
        elif "hooks" in plugin_manifest:
            # Claude auto-loads the standard hooks/hooks.json path. Declaring
            # it again in plugin.json leaves every install in a permanent
            # duplicate-hooks error state even though the fallback auto-load
            # still happens to execute the hooks.
            errors.add("claude_plugin_manifest_duplicates_standard_hooks")
        for package in (generated, dist_package):
            try:
                controller_text = (package / "skills" / "opensocrates" / "SKILL.md").read_text(
                    encoding="utf-8"
                )
                readme_text = (package / "README.md").read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                errors.add("claude_plugin_invocation_surface_unreadable")
                continue
            normalized_controller = " ".join(controller_text.split())
            normalized_readme = " ".join(readme_text.split())
            if (
                CLAUDE_PLUGIN_INVOCATION_MARKER not in normalized_controller
                or CLAUDE_CHAT_INVOCATION_MARKER in normalized_controller
            ):
                errors.add("claude_plugin_invocation_contract_invalid")
            if (
                "canonical explicit plugin invocation is `/opensocrates:opensocrates`"
                not in normalized_readme
                or "standalone Claude Chat upload ZIP uses `/opensocrates`" not in normalized_readme
            ):
                errors.add("claude_plugin_readme_invocation_boundary_invalid")
    embedded = [path for path in generated.rglob("compiled-content.bundle.json") if path.is_file()]
    if not embedded or any(path.read_bytes() != bundle_bytes for path in embedded):
        errors.add("embedded_bundle_mismatch")
    manifest_check = _verify_release_manifest(root, host, bundle)
    if manifest_check["status"] != "pass":
        errors.update(str(code) for code in manifest_check.get("error_codes", []))
    package_checksum = dist_package / "checksums.sha256"
    checksum_check = _verify_checksums(dist_package, package_checksum)
    if checksum_check["status"] != "pass":
        errors.update(str(code) for code in checksum_check.get("error_codes", []))
    archive = root / "dist" / f"opensocrates-{bundle.get('product_version')}-{host}-plugin.zip"
    if not archive.is_file() or not zipfile.is_zipfile(archive):
        errors.add("package_archive_missing_or_invalid")
        archive_compressed_bytes = 0
        archive_uncompressed_bytes = 0
    else:
        archive_compressed_bytes = archive.stat().st_size
        with zipfile.ZipFile(archive) as package_archive:
            archive_entries = [item.filename for item in package_archive.infolist()]
            archive_uncompressed_bytes = sum(
                item.file_size for item in package_archive.infolist() if not item.is_dir()
            )
        if _contains_eval_or_adjudication_path(archive_entries):
            errors.add("package_contains_eval_or_adjudication_artifact")
    excluded_runtime_entries = {
        path.relative_to(generated).as_posix()
        for path in generated.rglob("*")
        if path.is_file()
        and any(
            part in {"openai_codex", "codex_cli_bin"}
            or part.startswith(("openai_codex-", "openai_codex_cli_bin-"))
            for part in path.parts
        )
    }
    nested_zip_entries = {
        path.relative_to(generated).as_posix()
        for path in generated.rglob("*")
        if path.is_file() and path.suffix.casefold() == ".zip"
    }
    if host == "claude":
        if excluded_runtime_entries:
            errors.add("claude_package_contains_codex_runtime")
        if nested_zip_entries:
            errors.add("claude_package_contains_nested_zip")
        if archive_compressed_bytes > CLAUDE_ARCHIVE_COMPRESSED_LIMIT_BYTES:
            errors.add("claude_archive_compressed_limit_exceeded")
        if archive_uncompressed_bytes > CLAUDE_ARCHIVE_UNCOMPRESSED_LIMIT_BYTES:
            errors.add("claude_archive_uncompressed_limit_exceeded")
        if archive.is_file() and zipfile.is_zipfile(archive):
            try:
                with zipfile.ZipFile(archive) as package_archive:
                    archived_controller = package_archive.read(
                        "skills/opensocrates/SKILL.md"
                    ).decode("utf-8")
            except (KeyError, UnicodeError, OSError, zipfile.BadZipFile):
                errors.add("claude_plugin_archive_invocation_unreadable")
            else:
                normalized_archived_controller = " ".join(archived_controller.split())
                if (
                    CLAUDE_PLUGIN_INVOCATION_MARKER not in normalized_archived_controller
                    or CLAUDE_CHAT_INVOCATION_MARKER in normalized_archived_controller
                ):
                    errors.add("claude_plugin_archive_invocation_contract_invalid")
    runtime_targets = _load_json(generated / "release-manifest.json")
    listed_targets = runtime_targets.get("runtime_targets", []) if runtime_targets else []
    expected_runtime_targets = [] if host in NO_NATIVE_RUNTIME_HOSTS else [RELEASE_TARGET]
    if target != RELEASE_TARGET or listed_targets != expected_runtime_targets:
        errors.add("runtime_target_boundary_invalid")
    if host == "cursor":
        if any((generated / name).exists() for name in ("bin", "hooks", "runtime", "mcp.json")):
            errors.add("cursor_content_only_boundary_invalid")
        plugin_manifest = _load_json(generated / "plugin.json")
        if plugin_manifest is None or plugin_manifest.get("$schema") != (
            "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        ):
            errors.add("cursor_agent_plugin_manifest_missing")
    if host == "antigravity":
        if any((generated / name).exists() for name in ("bin", "hooks", "runtime")):
            errors.add("antigravity_content_only_boundary_invalid")
        plugin_manifest = _load_json(generated / "plugin.json")
        if plugin_manifest is None:
            errors.add("antigravity_plugin_manifest_missing")
    if host == "opencode":
        if any((generated / name).exists() for name in ("bin", "hooks", "runtime", "schemas")):
            errors.add("opencode_native_runtime_boundary_invalid")
        package_manifest = _load_json(generated / "opencode-plugin.json")
        if (
            package_manifest is None
            or package_manifest.get("schema") != "opensocrates.opencode-package/1.0.0"
            or package_manifest.get("minimum_opencode_version") != "1.18.18"
            or package_manifest.get("stable_plugin_hook") != "chat.message"
            or package_manifest.get("beta_v2_api") is not False
        ):
            errors.add("opencode_package_manifest_invalid")
        bridge = generated / "plugins" / "opensocrates.js"
        skill = generated / "skills" / "opensocrates" / "SKILL.md"
        if not bridge.is_file() or not skill.is_file():
            errors.add("opencode_bridge_or_skill_missing")
        else:
            try:
                bridge_text = bridge.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                errors.add("opencode_bridge_unreadable")
            else:
                if "chat.message" not in bridge_text or "@opencode-ai/plugin/v2" in bridge_text:
                    errors.add("opencode_stable_hook_boundary_invalid")
    if host == "grok":
        if any(
            (generated / name).exists()
            for name in ("bin", "hooks", "runtime", "commands", "agents", "mcp.json", ".mcp.json")
        ):
            errors.add("grok_content_only_boundary_invalid")
        plugin_manifest = _load_json(generated / "plugin.json")
        if (
            plugin_manifest is None
            or plugin_manifest.get("name") != "opensocrates"
            or plugin_manifest.get("version") != bundle.get("product_version")
            or plugin_manifest.get("skills") != "./skills"
        ):
            errors.add("grok_plugin_manifest_invalid")
        capability_evidence = metadata.get("capability_evidence")
        if (
            not isinstance(capability_evidence, Mapping)
            or capability_evidence.get("status") != "verified"
            or capability_evidence.get("probe_id") != "grok-build-1.0.3-2026-08-13"
        ):
            errors.add("grok_capability_evidence_invalid")
    return {
        "status": "fail" if errors else "pass",
        "method_count": len(existing_method_outputs),
        "shared_skill_count": len(top_level_shared_skills),
        "public_skill_count": len(actual_public_skills),
        "command_count": len(command_outputs),
        "schema_count": schema_count,
        "embedded_bundle_count": len(embedded),
        "generated_file_count": len(_snapshot(generated)),
        "package_file_count": len(_snapshot(dist_package)),
        "archive_compressed_bytes": archive_compressed_bytes,
        "archive_uncompressed_bytes": archive_uncompressed_bytes,
        "excluded_runtime_entry_count": len(excluded_runtime_entries),
        "nested_zip_entry_count": len(nested_zip_entries),
        "error_codes": sorted(errors),
    }


_CLAUDE_CHAT_SKILL_ROOT = "opensocrates"
_CLAUDE_CHAT_FORBIDDEN_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    "hooks.json",
    "launch.sh",
    "launch.ps1",
    "opensocrates-runtime",
)


def _claude_chat_archive_markdown_errors(bundle: zipfile.ZipFile, entries: list[str]) -> set[str]:
    errors: set[str] = set()
    for entry in entries:
        if not entry.lower().endswith(".md"):
            continue
        try:
            markdown_text = bundle.read(entry).decode("utf-8")
        except (KeyError, UnicodeError):
            errors.add("claude_chat_archive_markdown_unreadable")
            continue
        if "/opensocrates:opensocrates" in markdown_text:
            errors.add("claude_chat_archive_plugin_namespace_present")
    return errors


def _claude_chat_tree_markdown_errors(skill: Path) -> set[str]:
    errors: set[str] = set()
    for markdown in skill.rglob("*.md"):
        try:
            markdown_text = markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            errors.add("claude_chat_markdown_unreadable")
            continue
        if "/opensocrates:opensocrates" in markdown_text:
            errors.add("claude_chat_plugin_namespace_present")
    return errors


def _claude_chat_archive_errors(archive: Path) -> set[str]:
    """Assert the Chat ZIP is one directly uploadable skill folder.

    Checked against the archive itself rather than the staged tree so nothing
    can be introduced between assembly and packaging.
    """

    errors: set[str] = set()
    with zipfile.ZipFile(archive) as bundle:
        entries = [name for name in bundle.namelist() if not name.endswith("/")]
        errors |= _claude_chat_archive_markdown_errors(bundle, entries)
        try:
            skill_text = bundle.read(f"{_CLAUDE_CHAT_SKILL_ROOT}/SKILL.md").decode("utf-8")
        except (KeyError, UnicodeError):
            skill_text = ""
    if _contains_eval_or_adjudication_path(entries):
        errors.add("claude_chat_archive_contains_eval_or_adjudication_artifact")
    for entry in entries:
        if entry.split("/", 1)[0] != _CLAUDE_CHAT_SKILL_ROOT:
            errors.add("claude_chat_archive_unexpected_entry")
        if entry.startswith("/") or ".." in entry.split("/"):
            errors.add("claude_chat_archive_unsafe_path")
        if entry.lower().endswith(_CLAUDE_CHAT_FORBIDDEN_SUFFIXES):
            errors.add("claude_chat_archive_forbidden_file")
    if f"{_CLAUDE_CHAT_SKILL_ROOT}/SKILL.md" not in entries:
        errors.add("claude_chat_archive_top_level_skill_missing")
    if any("/.claude-plugin/" in f"/{entry}" for entry in entries):
        errors.add("claude_chat_archive_plugin_manifest_present")
    normalized_skill = " ".join(skill_text.split())
    if (
        CLAUDE_CHAT_INVOCATION_MARKER not in normalized_skill
        or CLAUDE_PLUGIN_INVOCATION_MARKER in normalized_skill
    ):
        errors.add("claude_chat_archive_invocation_contract_invalid")
    return errors


def _verify_claude_chat_skills(
    root: Path, version: str, bundle: Mapping[str, Any]
) -> dict[str, Any]:
    package = root / "dist" / "claude-chat-skills"
    archive = root / "dist" / f"opensocrates-{version}-claude-chat-skills.zip"
    errors: set[str] = set()
    raw_method_ids = bundle.get("method_ids", [])
    method_ids = (
        {value for value in raw_method_ids if isinstance(value, str)}
        if isinstance(raw_method_ids, list)
        else set()
    )
    actual_skill_roots = (
        {
            path.name
            for path in package.iterdir()
            if package.is_dir() and path.is_dir() and (path / "SKILL.md").is_file()
        }
        if package.is_dir()
        else set()
    )
    if actual_skill_roots != {_CLAUDE_CHAT_SKILL_ROOT}:
        errors.add("claude_chat_skill_set_invalid")
    skill = package / _CLAUDE_CHAT_SKILL_ROOT
    method_references = {
        method_id
        for method_id in method_ids
        if (skill / "references" / "methods" / f"{method_id}.md").is_file()
    }
    if method_references != method_ids or not (skill / "references" / "catalog.md").is_file():
        errors.add("claude_chat_internal_method_references_invalid")
    if not (skill / "LICENSE").is_file():
        errors.add("claude_chat_license_missing")
    try:
        skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        errors.add("claude_chat_skill_unreadable")
    else:
        normalized_skill = " ".join(skill_text.split())
        if (
            CLAUDE_CHAT_INVOCATION_MARKER not in normalized_skill
            or CLAUDE_PLUGIN_INVOCATION_MARKER in normalized_skill
        ):
            errors.add("claude_chat_invocation_contract_invalid")
    errors |= _claude_chat_tree_markdown_errors(skill)
    forbidden_trees = ("bin", "commands", "content", "hooks", "runtime", "schemas")
    if any((package / name).exists() for name in forbidden_trees):
        errors.add("claude_chat_runtime_surface_present")
    if not archive.is_file() or not zipfile.is_zipfile(archive):
        errors.add("claude_chat_archive_missing_or_invalid")
        archive_bytes = 0
    else:
        archive_bytes = archive.stat().st_size
        if archive_bytes > 16 * 1024 * 1024:
            errors.add("claude_chat_archive_too_large")
        errors |= _claude_chat_archive_errors(archive)
    return {
        "status": "fail" if errors else "pass",
        "skill_count": len(actual_skill_roots),
        "skill_upload_root": _CLAUDE_CHAT_SKILL_ROOT,
        "archive_size_bytes": archive_bytes,
        "automatic_hooks": False,
        "error_codes": sorted(errors),
    }


def _verify_claude_chat_provenance(
    root: Path, version: str, content_revision: int
) -> dict[str, Any]:
    """Bind a live-pass claim to this exact candidate without upgrading pending evidence."""

    report = _load_json(evidence_path(root, version))
    archive = root / "dist" / f"opensocrates-{version}-claude-chat-skills.zip"
    if report is None:
        return {
            "status": "fail",
            "evidence_state": "unavailable",
            "exact_release_artifact_status": "unavailable",
            "error_codes": ["claude_chat_current_evidence_missing"],
        }
    candidate_sha256: str | None = None
    candidate_file_count: int | None = None
    if archive.is_file() and zipfile.is_zipfile(archive):
        candidate_sha256 = f"sha256:{_sha256(archive)}"
        with zipfile.ZipFile(archive) as bundle:
            candidate_file_count = len(
                [entry for entry in bundle.namelist() if not entry.endswith("/")]
            )
    errors = validation_errors(
        report,
        product_version=version,
        content_revision=content_revision,
        candidate_archive_sha256=candidate_sha256,
        candidate_file_count=candidate_file_count,
    )
    evidence_state = str(report.get("status", "unavailable"))
    live_validated = not errors and evidence_state == "pass"
    return {
        "status": "fail" if errors else "pass",
        "evidence_state": evidence_state,
        "exact_release_artifact_status": "verified" if live_validated else "unavailable",
        "live_upload_status": "verified" if live_validated else "pending",
        "candidate_archive_sha256": candidate_sha256,
        "candidate_file_count": candidate_file_count,
        "error_codes": list(errors),
    }


def _verify_checksums(directory: Path, checksum_file: Path) -> dict[str, Any]:
    if not checksum_file.is_file():
        return {"status": "unavailable", "error_codes": ["checksum_file_missing"]}
    errors: set[str] = set()
    entries: list[tuple[str, str]] = []
    try:
        lines = checksum_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {"status": "unavailable", "error_codes": ["checksum_file_unreadable"]}
    for line in lines:
        if "  " not in line:
            errors.add("checksum_line_invalid")
            continue
        digest, relative = line.split("  ", 1)
        path = Path(relative)
        if (
            len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or path.is_absolute()
            or ".." in path.parts
        ):
            errors.add("checksum_entry_invalid")
            continue
        candidate = directory / path
        if not candidate.is_file() or _sha256(candidate) != digest:
            errors.add("checksum_value_mismatch")
        entries.append((digest, relative))
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != checksum_file and not path.is_symlink()
    }
    if {relative for _, relative in entries} != actual:
        errors.add("checksum_inventory_mismatch")
    return {
        "status": "fail" if errors else "pass",
        "entry_count": len(entries),
        "error_codes": sorted(errors),
    }


def _evidence_check(  # noqa: C901  # Explicit release evidence matrix.
    root: Path, version: str, *, assembly_status: str
) -> dict[str, Any]:
    errors: set[str] = set()
    unavailable: set[str] = set()
    security = _load_json(root / "build" / "evidence" / "security-scan.json")
    sbom = _load_json(root / "build" / "evidence" / "sbom.json")
    spdx = _load_json(root / "build" / "evidence" / "sbom.spdx.json")
    runtimes = {
        host: _load_json(root / "build" / "evidence" / f"runtime-build-{host}.json")
        for host in RUNTIME_HOSTS
    }
    codex_timing = _load_json(root / "build" / "evidence" / "codex-session-start-timing.json")
    expected_identity = _codex_package_manifest_identity(root)
    codex_timing_valid = expected_identity is not None and (
        _valid_codex_session_start_timing_evidence(
            codex_timing, expected_artifact_identity=expected_identity
        )
    )

    if security is None:
        unavailable.add("security_evidence_missing")
    elif (
        security.get("schema") != "opensocrates.security-scan-evidence/1.0.0"
        or security.get("status") != "pass"
    ):
        errors.add("security_evidence_invalid")
    if sbom is None:
        unavailable.add("sbom_evidence_missing")
    elif sbom.get("schema") != "opensocrates.sbom-evidence/1.0.0" or sbom.get("status") != "pass":
        errors.add("sbom_evidence_invalid")
    if spdx is None:
        unavailable.add("spdx_evidence_missing")
    elif spdx.get("spdxVersion") != "SPDX-2.3":
        errors.add("spdx_evidence_invalid")
    if assembly_status == "unavailable":
        # Do not treat an older runtime report as evidence for a build that
        # could not run in this environment.
        unavailable.add("runtime_build_unavailable")
    else:
        for host, runtime in runtimes.items():
            if runtime is None:
                unavailable.add(f"runtime_evidence_missing:{host}")
            elif (
                runtime.get("schema") != "opensocrates.runtime-build-evidence/1.0.0"
                or runtime.get("status") != "pass"
                or runtime.get("version") != version
                or runtime.get("runtime_profile") != host
            ):
                errors.add(f"runtime_evidence_invalid:{host}")
        if codex_timing is None:
            unavailable.add("codex_session_start_timing_missing")
        elif not codex_timing_valid:
            errors.add("codex_session_start_timing_invalid")
    return {
        "status": "fail" if errors else "unavailable" if unavailable else "pass",
        "security_status": security.get("status") if security else None,
        "sbom_status": sbom.get("status") if sbom else None,
        "runtime_statuses": {
            host: runtime.get("status") if runtime else None for host, runtime in runtimes.items()
        },
        "codex_session_start_timing": "pass" if codex_timing_valid else None,
        "error_codes": sorted(errors | unavailable),
    }


def _opencode_compatibility_evidence(  # noqa: C901  # Explicit evidence matrix.
    root: Path,
) -> dict[str, Any]:
    document = _load_json(root / "docs" / "evidence" / "opencode-compatibility-2026-08-13.json")
    errors: set[str] = set()
    if document is None:
        return {"status": "unavailable", "error_codes": ["opencode_evidence_missing"]}
    if document.get("schema") != "opensocrates.opencode-compatibility-evidence/1.0.0":
        errors.add("opencode_evidence_schema_invalid")
    target = document.get("target")
    live = document.get("production_bridge_live_probe")
    isolated = document.get("isolated_live_probe")
    privacy = document.get("privacy")
    if not isinstance(target, Mapping) or target.get("opencode_version") != "1.18.18":
        errors.add("opencode_evidence_target_invalid")
    required_live = {
        "automatic_judgment_activation_same_turn",
        "interactive_tui_same_turn_grounding_observed",
        "complete_authored_method_grounding_observed",
        "mechanical_control_unchanged",
        "explicit_skill_discovery",
    }
    if not isinstance(live, Mapping) or any(live.get(key) is not True for key in required_live):
        errors.add("opencode_evidence_live_probe_invalid")
    # The bridge has no activation deadline: OpenCode awaits chat.message
    # without a host-side timeout, and the selection work is synchronous, so a
    # timeout observation is not a property this evidence can assert.
    required_isolated = {
        "global_plugin_discovered",
        "global_skill_discovered",
        "current_user_text_available",
        "in_place_part_mutation_visible_same_turn",
        "exception_failed_open",
    }
    if not isinstance(isolated, Mapping) or any(
        isolated.get(key) is not True for key in required_isolated
    ):
        errors.add("opencode_evidence_isolated_probe_invalid")
    if not isinstance(privacy, Mapping) or any(value is not False for value in privacy.values()):
        errors.add("opencode_evidence_privacy_invalid")
    return {
        "status": "fail" if errors else "pass",
        "opencode_version": target.get("opencode_version") if isinstance(target, Mapping) else None,
        "same_turn": live.get("automatic_judgment_activation_same_turn")
        if isinstance(live, Mapping)
        else None,
        "interactive_tui": live.get("interactive_tui_same_turn_grounding_observed")
        if isinstance(live, Mapping)
        else None,
        "error_codes": sorted(errors),
    }


def _source_version_smoke(root: Path, version: str) -> dict[str, Any]:
    result = _run(
        ["-m", "opensocrates", "version", "--json"],
        root,
        interpreter=sys.executable,
        timeout=30.0,
    )
    if result.status != "pass":
        return {
            "status": result.status,
            "error_codes": [f"source_version_{result.code}"],
        }
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "opensocrates", "version", "--json"],
            cwd=root,
            env=_safe_environment(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30.0,
        )
        value = json.loads(completed.stdout.decode("utf-8"))
    except (OSError, subprocess.SubprocessError, UnicodeError, json.JSONDecodeError):
        return {"status": "fail", "error_codes": ["source_version_output_invalid"]}
    if not isinstance(value, Mapping) or value.get("product_version") != version:
        return {"status": "fail", "error_codes": ["source_version_mismatch"]}
    return {"status": "pass", "error_codes": []}


def _runtime_version_smoke(
    root: Path, runtime_report: Mapping[str, Any] | None, version: str
) -> dict[str, Any]:
    if runtime_report is None or not isinstance(runtime_report.get("artifact"), str):
        return {
            "status": "unavailable",
            "error_codes": ["runtime_artifact_unavailable"],
        }
    binary = _resolve(root, str(runtime_report["artifact"]))
    if not binary.is_file():
        return {"status": "unavailable", "error_codes": ["runtime_artifact_missing"]}
    try:
        completed = subprocess.run(
            [str(binary), "version", "--json"],
            cwd=root,
            env=_safe_environment(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10.0,
        )
        value = json.loads(completed.stdout.decode("utf-8"))
    except (OSError, subprocess.SubprocessError, UnicodeError, json.JSONDecodeError):
        return {"status": "fail", "error_codes": ["runtime_version_output_invalid"]}
    if (
        completed.returncode != 0
        or not isinstance(value, Mapping)
        or value.get("product_version") != version
    ):
        return {"status": "fail", "error_codes": ["runtime_version_mismatch"]}
    return {"status": "pass", "error_codes": []}


def _full_check(
    root: Path, *, assembly_result: Mapping[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    version = _read_version(root)
    bundle, bundle_bytes = _load_bundle(root)
    reasoning_content_bundle, reasoning_content_bytes = _load_reasoning_content_bundle(root)
    checks: dict[str, Any] = {
        "bundle": _check_bundle_shape(bundle, version),
        "reasoning_content_bundle": _check_reasoning_content_bundle_shape(
            reasoning_content_bundle, bundle.get("content_revision")
        ),
        "schemas": _schema_surface(root),
        "runtime_entry": _runtime_entry_check(root),
        "source_version": _source_version_smoke(root, version),
        "content": _content_validator(root, bundle_bytes, reasoning_content_bytes),
        "deterministic_generation": _determinism_check(root),
    }
    runtime_reports: dict[str, Mapping[str, Any] | None] = {host: None for host in RUNTIME_HOSTS}
    if assembly_result is not None:
        checks["package_assembly"] = dict(assembly_result)
        runtime_reports = {
            host: _load_json(root / "build" / "evidence" / f"runtime-build-{host}.json")
            for host in RUNTIME_HOSTS
        }
    else:
        try:
            assembly = _assemble(root)
            checks["package_assembly"] = assembly
            runtime_reports = {
                host: _load_json(root / "build" / "evidence" / f"runtime-build-{host}.json")
                for host in RUNTIME_HOSTS
            }
        except AssemblyUnavailable as exc:
            checks["package_assembly"] = {
                "status": "unavailable",
                "error_codes": [str(exc)],
            }
        except ReleaseCheckError as exc:
            checks["package_assembly"] = {"status": "fail", "error_codes": [str(exc)]}
    assembly_status = str(checks["package_assembly"].get("status", "unavailable"))
    timing_evidence = checks["package_assembly"].get("codex_session_start_timing")
    checks["codex_session_start_timing"] = _codex_session_start_timing_check(
        root, assembly_status, timing_evidence
    )
    primary_runtime = runtime_reports.get("codex")
    target = primary_runtime.get("target") if primary_runtime else None
    if not isinstance(target, str):
        target = "unavailable"
    checks["generated_outputs"] = (
        _generated_output_check(root)
        if assembly_status == "pass"
        else {
            "status": assembly_status
            if assembly_status in {"fail", "unavailable"}
            else "unavailable",
            "error_codes": ["package_assembly_not_available"],
        }
    )
    runtime_versions = {
        host: _runtime_version_smoke(root, runtime_reports[host], version) for host in RUNTIME_HOSTS
    }
    checks["runtime_version"] = {
        "status": (
            "fail"
            if any(value["status"] == "fail" for value in runtime_versions.values())
            else "unavailable"
            if any(value["status"] == "unavailable" for value in runtime_versions.values())
            else "pass"
        ),
        "hosts": runtime_versions,
        "error_codes": sorted(
            {
                str(code)
                for value in runtime_versions.values()
                for code in value.get("error_codes", [])
            }
        ),
    }
    checks["hosts"] = (
        {host: _verify_host_surface(root, host, bundle, bundle_bytes, target) for host in HOSTS}
        if assembly_status == "pass"
        else {
            host: {
                "status": assembly_status
                if assembly_status in {"fail", "unavailable"}
                else "unavailable",
                "error_codes": ["package_assembly_not_available"],
            }
            for host in HOSTS
        }
    )
    checks["claude_chat_skills"] = (
        _verify_claude_chat_skills(root, version, bundle)
        if assembly_status == "pass"
        else {
            "status": assembly_status
            if assembly_status in {"fail", "unavailable"}
            else "unavailable",
            "error_codes": ["package_assembly_not_available"],
        }
    )
    checks["claude_chat_provenance"] = (
        _verify_claude_chat_provenance(root, version, int(bundle.get("content_revision", -1)))
        if assembly_status == "pass"
        else {
            "status": assembly_status
            if assembly_status in {"fail", "unavailable"}
            else "unavailable",
            "evidence_state": "unavailable",
            "exact_release_artifact_status": "unavailable",
            "live_upload_status": "pending",
            "error_codes": ["package_assembly_not_available"],
        }
    )
    # The generated package's own launcher and README are the artifacts users
    # receive, so both are exercised against the assembled package trees.
    checks["packaged_launcher"] = _package_tool_check(
        root,
        "check_packaged_launcher.py",
        "build/evidence/packaged-launcher.json",
        "packaged_launcher",
        assembly_status,
    )
    checks["package_docs"] = _package_tool_check(
        root,
        "check_package_docs.py",
        "build/evidence/package-docs.json",
        "package_docs",
        assembly_status,
    )
    checks["docs"] = _run_tool_check(
        root,
        [
            str(root / "tools" / "check_links.py"),
            "--root",
            str(root),
            "--report",
            "build/evidence/links.json",
        ],
        "docs",
    )
    checks["security"] = _run_tool_check(
        root,
        [
            str(root / "tools" / "security_scan.py"),
            "--root",
            str(root),
            "--report",
            "build/evidence/security-scan.json",
        ],
        "security",
    )
    checks["opencode_bridge"] = {
        "status": (
            bridge_result := _run(
                ["node", "--test", str(root / "tools" / "opencode_bridge.test.mjs")],
                root,
                timeout=60.0,
            )
        ).status,
        "error_codes": []
        if bridge_result.status == "pass"
        else [f"opencode_bridge_{bridge_result.code}"],
    }
    checks["opencode_compatibility_evidence"] = _opencode_compatibility_evidence(root)
    checks["evidence"] = _evidence_check(root, version, assembly_status=assembly_status)
    statuses: list[str] = []
    for name, value in checks.items():
        if name == "hosts":
            continue
        if isinstance(value, Mapping):
            statuses.append(str(value.get("status", "unavailable")))
    for host in HOSTS:
        statuses.append(str(checks["hosts"][host].get("status", "unavailable")))
    status = (
        "fail" if "fail" in statuses else "unavailable" if "unavailable" in statuses else "pass"
    )
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": _iso_now(),
        "status": status,
        "product_version": version,
        "bundle": {
            "size_bytes": len(bundle_bytes),
            "content_revision": bundle.get("content_revision"),
            "source_tree_hash": bundle.get("source_tree_hash"),
            "normalized_semantic_hash": bundle.get("normalized_semantic_hash"),
        },
        "reasoning_content_bundle": {
            "size_bytes": len(reasoning_content_bytes),
            "content_revision": reasoning_content_bundle.get("content_revision"),
            "sha256": f"sha256:{hashlib.sha256(reasoning_content_bytes).hexdigest()}",
        },
        "checks": checks,
        "unvalidated": {
            "platforms": _candidate_platforms(root, target),
            "signing_status": "unvalidated",
            "live_host_probe_status": _live_host_probe_status(
                opencode_validated=checks["opencode_compatibility_evidence"]["status"] == "pass"
            ),
            "clean_machine_install_status": "unvalidated",
            "source_archive_status": "not_attempted",
            "provenance_status": "not_attempted",
            "codex_sdk_runtime_status": "native_bundle_only; host and clean-install verification unvalidated",
        },
        "privacy": {
            "source_content_recorded": False,
            "absolute_paths_recorded": False,
            "host_payloads_recorded": False,
            "command_output_recorded": False,
        },
    }
    exit_code = 0 if status == "pass" else 1 if status == "fail" else 2
    return exit_code, report


def _package_tool_check(
    root: Path, tool: str, report: str, name: str, assembly_status: str
) -> dict[str, Any]:
    """Run a generated-package check, or record why it could not run."""

    if assembly_status != "pass":
        return {
            "status": assembly_status
            if assembly_status in {"fail", "unavailable"}
            else "unavailable",
            "error_codes": ["package_assembly_not_available"],
        }
    return _run_tool_check(
        root,
        [str(root / "tools" / tool), "--root", str(root), "--report", report],
        name,
    )


def _run_tool_check(root: Path, command: Sequence[str], name: str) -> dict[str, Any]:
    result = _run(command, root, interpreter=sys.executable, timeout=300.0)
    return {
        "status": result.status,
        "error_codes": [] if result.status == "pass" else [f"{name}_{result.code}"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--report", default="build/evidence/release-check.json")
    parser.add_argument(
        "--assemble",
        action="store_true",
        help="freshly assemble artifacts and run the complete release gate",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _resolve(Path.cwd(), args.root)
    report_path = _resolve(root, args.report)
    if args.assemble:
        try:
            assembly = _assemble(root)
        except AssemblyUnavailable as exc:
            report = {
                "schema": SCHEMA,
                "generated_at": _iso_now(),
                "status": "unavailable",
                "error_codes": [str(exc)],
                "privacy": {
                    "source_content_recorded": False,
                    "absolute_paths_recorded": False,
                    "host_payloads_recorded": False,
                    "command_output_recorded": False,
                },
            }
            _write_json(report_path, report)
            print(f"release-check: UNAVAILABLE report={_relative(root, report_path)}")
            return 2
        except ReleaseCheckError as exc:
            report = {
                "schema": SCHEMA,
                "generated_at": _iso_now(),
                "status": "fail",
                "error_codes": [str(exc)],
                "privacy": {
                    "source_content_recorded": False,
                    "absolute_paths_recorded": False,
                    "host_payloads_recorded": False,
                    "command_output_recorded": False,
                },
            }
            _write_json(report_path, report)
            print(f"release-check: FAIL report={_relative(root, report_path)}")
            return 1
        exit_code, report = _full_check(root, assembly_result=assembly)
        _write_json(report_path, report)
        print(
            f"release-check: {str(report.get('status', 'unavailable')).upper()} report={_relative(root, report_path)}"
        )
        return exit_code
    try:
        exit_code, report = _full_check(root)
    except AssemblyUnavailable as exc:
        report = {
            "schema": SCHEMA,
            "generated_at": _iso_now(),
            "status": "unavailable",
            "error_codes": [str(exc)],
            "privacy": {
                "source_content_recorded": False,
                "absolute_paths_recorded": False,
                "host_payloads_recorded": False,
                "command_output_recorded": False,
            },
        }
        exit_code = 2
    except ReleaseCheckError as exc:
        report = {
            "schema": SCHEMA,
            "generated_at": _iso_now(),
            "status": "fail",
            "error_codes": [str(exc)],
            "privacy": {
                "source_content_recorded": False,
                "absolute_paths_recorded": False,
                "host_payloads_recorded": False,
                "command_output_recorded": False,
            },
        }
        exit_code = 1
    _write_json(report_path, report)
    print(
        f"release-check: {str(report.get('status', 'unavailable')).upper()} report={_relative(root, report_path)}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
