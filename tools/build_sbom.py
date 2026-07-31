#!/usr/bin/env python3
"""Generate a privacy-safe SPDX 2.3 SBOM for runtime/build inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
CODEX_SDK_VERSION = "0.144.4"
CODEX_CLI_RUNTIME_PACKAGE = "openai-codex-cli-bin"
CODEX_RUNTIME_WHEEL_MARKERS = {
    "darwin-arm64": ("macosx_11_0_arm64",),
    "darwin-x64": ("macosx_10_9_x86_64",),
    "linux-x64": ("manylinux_2_17_x86_64", "musllinux_1_1_x86_64"),
    "windows-x64": ("win_amd64",),
}


class SbomError(RuntimeError):
    """Raised for invalid SBOM input or a blocked strict build."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8")


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
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _version(root: Path) -> tuple[str, str]:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        value = document.get("project", {}).get("version")
        if isinstance(value, str) and VERSION_PATTERN.fullmatch(value):
            return value, "pyproject.toml"
    version_file = root / "VERSION"
    if version_file.is_file():
        value = version_file.read_text(encoding="utf-8").strip()
        if VERSION_PATTERN.fullmatch(value):
            return value, "VERSION"
    raise SbomError("a valid VERSION or pyproject.toml project.version is required")


def _spdx_id(prefix: str, value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-") or "unknown"
    return f"SPDXRef-{prefix}-{safe}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_project(root: Path) -> tuple[dict[str, Any], bool]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}, False
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), True
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SbomError("could not parse pyproject.toml") from exc


def _load_lock(root: Path) -> tuple[list[dict[str, Any]], bool]:
    path = root / "uv.lock"
    if not path.is_file():
        return [], False
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SbomError("could not parse uv.lock") from exc
    packages = document.get("package", [])
    if not isinstance(packages, list):
        raise SbomError("uv.lock package table is not a list")
    normalized: list[dict[str, Any]] = []
    for package in packages:
        if not isinstance(package, dict):
            raise SbomError("uv.lock contains a non-object package")
        name = package.get("name")
        version = package.get("version")
        if isinstance(name, str) and isinstance(version, str):
            dependencies = package.get("dependencies", [])
            wheels = package.get("wheels", [])
            normalized.append(
                {
                    "name": name,
                    "version": version,
                    "dependencies": dependencies if isinstance(dependencies, list) else [],
                    "wheels": wheels if isinstance(wheels, list) else [],
                }
            )
    return normalized, True


def _normalized_name(value: str) -> str:
    return value.lower().replace("_", "-").replace(".", "-")


def _version_at_least(value: str, minimum: tuple[int, int]) -> bool:
    components = value.split(".")
    if len(components) < 2 or not all(part.isdigit() for part in components[:2]):
        return False
    return (int(components[0]), int(components[1])) >= minimum


def _runtime_closure(  # noqa: C901  # Explicit release policy.
    project: dict[str, Any], locked_packages: list[dict[str, Any]]
) -> tuple[set[str], dict[str, Any], list[str]]:
    """Return the locked runtime closure and bounded SDK/runtime evidence."""

    runtime_dependencies = project.get("project", {}).get("dependencies", [])
    if not isinstance(runtime_dependencies, list) or not all(
        isinstance(item, str) for item in runtime_dependencies
    ):
        raise SbomError("project.dependencies must be a list of strings")

    expected_dependencies = (
        "openai-codex==0.144.4",
        "openai-codex-cli-bin==0.144.4",
        "pydantic>=2.12,<3",
    )
    index = {_normalized_name(item["name"]): item for item in locked_packages}
    errors: list[str] = []
    required = {"openai-codex", CODEX_CLI_RUNTIME_PACKAGE, "pydantic"}
    if tuple(runtime_dependencies) != expected_dependencies:
        errors.append("runtime_dependency_declaration_mismatch")

    openai_codex = index.get("openai-codex")
    cli_runtime = index.get(CODEX_CLI_RUNTIME_PACKAGE)
    pydantic = index.get("pydantic")
    pydantic_core = index.get("pydantic-core")
    if openai_codex is None or openai_codex["version"] != CODEX_SDK_VERSION:
        errors.append("openai_codex_pin_invalid")
    if cli_runtime is None or cli_runtime["version"] != CODEX_SDK_VERSION:
        errors.append("codex_cli_runtime_pin_invalid")
    if pydantic is None or not _version_at_least(pydantic["version"], (2, 12)):
        errors.append("pydantic_bound_invalid")
    if pydantic is not None and not pydantic["version"].startswith("2."):
        errors.append("pydantic_major_invalid")
    if pydantic_core is None:
        errors.append("pydantic_core_missing")

    opensocrates = index.get("opensocrates")
    if opensocrates is None:
        errors.append("project_package_missing_from_lock")
        direct_dependencies: set[str] = set()
    else:
        direct_dependencies = {
            _normalized_name(item["name"])
            for item in opensocrates["dependencies"]
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if not required <= direct_dependencies:
            errors.append("runtime_dependency_missing_from_lock")

    closure: set[str] = set()
    pending = list(sorted(direct_dependencies))
    while pending:
        package_name = pending.pop()
        if package_name in closure:
            continue
        package = index.get(package_name)
        if package is None:
            errors.append(f"locked_dependency_missing:{package_name}")
            continue
        closure.add(package_name)
        for dependency in package["dependencies"]:
            if isinstance(dependency, dict) and isinstance(dependency.get("name"), str):
                pending.append(_normalized_name(dependency["name"]))

    wheel_urls = (
        [
            item["url"].lower()
            for item in cli_runtime["wheels"]
            if isinstance(item, dict) and isinstance(item.get("url"), str)
        ]
        if cli_runtime is not None
        else []
    )
    wheel_coverage = {
        target: "locked"
        if all(any(marker in url for url in wheel_urls) for marker in markers)
        else "missing"
        for target, markers in CODEX_RUNTIME_WHEEL_MARKERS.items()
    }
    if any(status == "missing" for status in wheel_coverage.values()):
        errors.append("codex_cli_runtime_platform_wheel_missing")

    evidence = {
        "sdk": {
            "name": "openai-codex",
            "version": openai_codex["version"] if openai_codex is not None else None,
        },
        "cli_runtime": {
            "name": CODEX_CLI_RUNTIME_PACKAGE,
            "version": cli_runtime["version"] if cli_runtime is not None else None,
            "locked_candidate_wheels": wheel_coverage,
            "artifact_verification": "not_attempted",
        },
        "pydantic": {
            "name": "pydantic",
            "version": pydantic["version"] if pydantic is not None else None,
            "required_range": ">=2.12,<3",
            "core_version": pydantic_core["version"] if pydantic_core is not None else None,
        },
    }
    return closure, evidence, sorted(set(errors))


def _artifact(root: Path, raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = _resolve(root, raw)
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise SbomError(f"SBOM artifact must be inside the repository root: {raw}") from exc
    if path.is_symlink() or not path.is_file():
        raise SbomError(f"SBOM artifact is not a regular file: {raw}")
    file_id = _spdx_id("File", relative)
    file_object = {
        "SPDXID": file_id,
        "fileName": relative,
        "checksums": [{"algorithm": "SHA256", "checksumValue": _sha256(path)}],
        "licenseConcluded": "NOASSERTION",
        "copyrightText": "NOASSERTION",
    }
    relation = {
        "spdxElementId": "SPDXRef-Package-opensocrates",
        "relationshipType": "CONTAINS",
        "relatedSpdxElement": file_id,
    }
    return file_object, relation


def build(  # noqa: C901  # Explicit release policy.
    root: Path, artifact_paths: list[str], *, allow_missing_lock: bool
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    version, version_source = _version(root)
    project, project_present = _load_project(root)
    locked_packages, lock_present = _load_lock(root)
    runtime_names: set[str] = set()
    runtime_evidence: dict[str, Any] = {}
    runtime_errors: list[str] = []
    if project_present and lock_present:
        runtime_names, runtime_evidence, runtime_errors = _runtime_closure(project, locked_packages)
    if not lock_present and not allow_missing_lock:
        status = "blocked"
    elif runtime_errors:
        status = "fail"
    else:
        status = "pass" if lock_present else "incomplete"

    packages: list[dict[str, Any]] = [
        {
            "SPDXID": "SPDXRef-Package-opensocrates",
            "name": "opensocrates",
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "filesAnalyzed": False,
            "supplier": "NOASSERTION",
        },
        {
            "SPDXID": "SPDXRef-Package-python",
            "name": "Python",
            "versionInfo": platform.python_version(),
            "downloadLocation": "https://www.python.org/",
            "licenseConcluded": "PSF-2.0",
            "licenseDeclared": "PSF-2.0",
            "filesAnalyzed": False,
            "supplier": "Organization: Python Software Foundation",
            "packagePurpose": "RUNTIME",
        },
    ]
    package_ids: dict[str, str] = {"opensocrates": "SPDXRef-Package-opensocrates"}
    seen: set[tuple[str, str]] = set()
    for item in sorted(
        locked_packages, key=lambda value: (value["name"].lower(), value["version"])
    ):
        key = (item["name"].lower(), item["version"])
        if key in seen or item["name"].lower() == "opensocrates":
            continue
        seen.add(key)
        package_id = _spdx_id("Package", f"{item['name']}-{item['version']}")
        package_ids[_normalized_name(item["name"])] = package_id
        packages.append(
            {
                "SPDXID": package_id,
                "name": item["name"],
                "versionInfo": item["version"],
                "downloadLocation": "NOASSERTION",
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "filesAnalyzed": False,
                "supplier": "NOASSERTION",
                "packagePurpose": (
                    "RUNTIME" if _normalized_name(item["name"]) in runtime_names else "BUILD"
                ),
            }
        )

    files: list[dict[str, Any]] = []
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package-opensocrates",
        }
    ]
    for item in sorted(locked_packages, key=lambda value: value["name"].lower()):
        package_name = _normalized_name(item["name"])
        if package_name not in runtime_names:
            continue
        runtime_package_id = package_ids.get(package_name)
        if runtime_package_id is None:
            continue
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package-opensocrates",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": runtime_package_id,
            }
        )
        for dependency in item["dependencies"]:
            if not isinstance(dependency, dict) or not isinstance(dependency.get("name"), str):
                continue
            dependency_name = _normalized_name(dependency["name"])
            dependency_id = package_ids.get(dependency_name)
            if dependency_name in runtime_names and dependency_id is not None:
                relationships.append(
                    {
                        "spdxElementId": runtime_package_id,
                        "relationshipType": "DEPENDS_ON",
                        "relatedSpdxElement": dependency_id,
                    }
                )
    for raw in artifact_paths:
        file_object, relation = _artifact(root, raw)
        files.append(file_object)
        relationships.append(relation)

    document_seed = _canonical_json({"version": version, "packages": packages, "files": files})
    namespace_hash = hashlib.sha256(document_seed.encode("utf-8")).hexdigest()
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"OpenSocrates {version} build SBOM",
        "documentNamespace": f"https://spdx.org/spdxdocs/opensocrates-{version}-{namespace_hash}",
        "creationInfo": {
            "created": _iso_now(),
            "creators": ["Tool: OpenSocrates build_sbom.py"],
            "licenseListVersion": "3.26",
        },
        "packages": packages,
        "files": files,
        "relationships": relationships,
    }
    report = {
        "schema": "opensocrates.sbom-evidence/1.0.0",
        "generated_at": _iso_now(),
        "status": status,
        "version": version,
        "version_source": version_source,
        "pyproject_present": project_present,
        "lockfile_present": lock_present,
        "package_count": len(packages),
        "build_dependency_count": sum(
            1 for package in packages if package.get("packagePurpose") == "BUILD"
        ),
        "runtime_dependency_count": len(runtime_names),
        "artifact_count": len(files),
        "runtime_policy": "codex-sdk-selector-only",
        "runtime_dependencies": [
            {"name": item["name"], "version": item["version"]}
            for item in sorted(
                locked_packages,
                key=lambda value: value["name"].lower(),
            )
            if _normalized_name(item["name"]) in runtime_names
        ],
        "codex_runtime": runtime_evidence,
    }
    if not lock_present:
        report["diagnostic"] = "uv.lock is required for a complete release SBOM"
    if runtime_errors:
        report["diagnostic"] = ",".join(runtime_errors)
    return (
        (0 if status in {"pass", "incomplete"} else 2 if status == "blocked" else 1),
        sbom,
        report,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output", help="SPDX JSON output path")
    parser.add_argument("--report", help="machine-readable summary path")
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="build artifact to hash into the SBOM; repeatable",
    )
    parser.add_argument(
        "--allow-missing-lock",
        action="store_true",
        help="emit an incomplete local SBOM when uv.lock is absent",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _resolve(Path.cwd(), args.root)
    output = _resolve(root, args.output or "build/evidence/sbom.spdx.json")
    report_path = _resolve(root, args.report or "build/evidence/sbom.json")
    try:
        status, sbom, report = build(
            root, args.artifact, allow_missing_lock=args.allow_missing_lock
        )
    except (OSError, SbomError, tomllib.TOMLDecodeError) as exc:
        status = 2
        sbom = {}
        report = {
            "schema": "opensocrates.sbom-evidence/1.0.0",
            "generated_at": _iso_now(),
            "status": "blocked",
            "diagnostic": type(exc).__name__,
            "message": str(exc)[:240],
        }
    if sbom:
        _write_json(output, sbom)
    _write_json(report_path, report)
    print(_canonical_json(report), end="")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
