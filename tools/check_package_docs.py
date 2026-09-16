#!/usr/bin/env python3
"""Assert the generated package documentation keeps its stated limitations.

The repository README and SECURITY.md describe Codex trust and per-target
validation boundaries.  Users who only ever read the
README shipped *inside* the distributable must not receive a materially
narrower warning, so this check inspects the generated package README rather
than the source template.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

README = "README.md"
NATIVE_HOSTS = ("codex",)
NATIVE_TARGETS = {
    "darwin-arm64": {
        "launcher": "bin/launch.sh",
        "other_launcher": "bin/launch.mjs",
        "other_target": "windows-x64",
    },
    "windows-x64": {
        "launcher": "bin/launch.mjs",
        "other_launcher": "bin/launch.sh",
        "other_target": "darwin-arm64",
    },
}
NATIVE_README_REQUIRED: dict[str, tuple[str, ...]] = {
    "darwin-arm64": (
        "This archive targets Apple-silicon macOS (`darwin-arm64`)",
        "ships only `bin/launch.sh`",
        "`runtime/darwin-arm64/` runtime payload",
        "does not contain `bin/launch.mjs`",
        "`runtime/windows-x64/` payload",
    ),
    "windows-x64": (
        "This archive targets Windows x64 (`windows-x64`)",
        "ships only `bin/launch.mjs`",
        "`runtime/windows-x64/` runtime payload",
        "does not contain `bin/launch.sh`",
        "`runtime/darwin-arm64/` payload",
    ),
}

# Each requirement fails as one stable error code when any phrase is absent.

CODEX_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "codex_readme_hook_approval_missing",
        (
            "one-time interactive hook approval",
            "non-interactive `codex exec` silently skips untrusted hooks",
        ),
    ),
    (
        "codex_readme_live_evidence_boundary_missing",
        (
            "package and launcher are release-validated",
            "no live Codex hook-delivery receipt",
        ),
    ),
    (
        "codex_readme_teacher_questions_missing",
        ("message containing teacher questions to settle",),
    ),
)


# Wording that would restore an overstated claim.
FORBIDDEN: tuple[tuple[str, str], ...] = (
    (
        "native_readme_blanket_hooks_disabled_claim",
        "hooks, project instructions, and session persistence disabled",
    ),
    ("native_readme_signing_overclaim", "signed and notarized"),
    ("native_readme_platform_overclaim", "validated on all platforms"),
    ("native_readme_host_delivery_overclaim", "live delivery is validated"),
)

# Deliberately bounded semantic patterns for three high-risk claim classes.
# They operate within one sentence/Markdown line, require both a strong claim
# and its sensitive scope/authority, and do not attempt to lint general prose.
SEMANTIC_OVERCLAIMS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "native_readme_clean_machine_overclaim",
        (
            re.compile(
                r"\b(?:proves?|validates?|verifies?)\b.{0,24}"
                r"\bclean[- ]machine(?:\s+installation)?\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "native_readme_automatic_hook_overclaim",
        (
            re.compile(
                r"\bautomatic\b.{0,48}\bhook\s+delivery\b.{0,32}"
                r"\b(?:is|was|has\s+been)?\s*(?:validated|verified|passed|working)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "native_readme_public_release_overclaim",
        (
            re.compile(
                r"\b(?:candidate|package|plugin|archive|release)\b.{0,40}"
                r"\b(?:is|was|has\s+been)\s+(?:validated|verified|approved|ready)\b"
                r".{0,24}\b(?:as|for)\s+(?:a\s+)?public\s+release\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "native_readme_signing_overclaim",
        (
            re.compile(
                r"\b(?:code\s+)?signing\b.{0,24}"
                r"\b(?:is|was|has\s+been)?\s*(?:validated|verified|passed|complete)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "native_readme_universal_support_overclaim",
        (
            re.compile(
                r"\b(?:fully|completely|universally)\s+"
                r"(?:validated|supported|compatible)\b.{0,96}"
                r"\b(?:all|every)\s+(?:codex\s+)?"
                r"(?:surface|platform|environment)s?\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:validated|supported|compatible)\b.{0,48}"
                r"\b(?:across|on|for)\s+(?:all|every)\s+"
                r"(?:codex\s+)?(?:surface|platform|environment)s?\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "native_readme_endorsement_overclaim",
        (
            re.compile(
                r"\b(?:signed|notarized|approved|certified|endorsed)\s+by\s+"
                r"(?:anthropic|openai|apple|claude)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:anthropic|openai|apple|claude)[ -]"
                r"(?:approved|certified|endorsed|signed)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:package|plugin|archive|release)\s+"
                r"(?:is|was|has\s+been)\s+(?:cryptographically\s+)?"
                r"(?:signed|notarized)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "native_readme_managed_safety_overclaim",
        (
            re.compile(
                r"\b(?:(?:guaranteed|fully|completely|perfectly)\s+)?"
                r"(?:safe|secure|isolated)\s+(?:on|in|for)\s+(?:all\s+)?"
                r"(?:managed|enterprise|organization-managed)\s+"
                r"(?:machines?|environments?|systems?)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:managed|enterprise|organization-managed)\s+"
                r"(?:policy\s+)?(?:hooks?|environments?|machines?)\b.{0,64}"
                r"\b(?:cannot|can't|never)\b.{0,32}"
                r"\b(?:observe|access|receive|see)\b.{0,32}"
                r"\b(?:prompts?|data|credentials?)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bguarantees?\s+(?:(?:complete|full)\s+)?"
                r"(?:safety|security|isolation)\s+(?:on|in|for)\s+"
                r"(?:all\s+)?(?:managed|enterprise|organization-managed)\s+"
                r"(?:machines?|environments?|systems?)\b",
                re.IGNORECASE,
            ),
        ),
    ),
)

_NEGATED_CLAIM_PREFIX = re.compile(
    r"(?:\bnot\b|\bnever\b|\bno\b|\bwithout\b|\bdoes\s+not\b|\bcannot\b)"
    r"(?:\W+\w+){0,6}\W*$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Collapse wrapping so phrase checks survive Markdown line breaks."""

    return re.sub(r"\s+", " ", text)


def _claim_segments(text: str) -> Iterator[str]:
    """Yield bounded prose segments without matching across sentences or bullets."""

    for line in text.splitlines():
        normalized = _normalize(line).strip()
        if normalized:
            yield from (part for part in re.split(r"(?<=[.!?])\s+", normalized) if part)


def _semantic_overclaim_errors(text: str) -> list[str]:
    errors: set[str] = set()
    for segment in _claim_segments(text):
        for code, patterns in SEMANTIC_OVERCLAIMS:
            for pattern in patterns:
                for match in pattern.finditer(segment):
                    prefix = segment[max(0, match.start() - 96) : match.start()]
                    # A limitation in an earlier contrasting clause must not
                    # negate a later affirmative overclaim.
                    prefix = re.split(
                        r"[,;:]|\b(?:but|however|although|yet)\b",
                        prefix,
                        flags=re.IGNORECASE,
                    )[-1]
                    if not _NEGATED_CLAIM_PREFIX.search(prefix):
                        errors.add(code)
                        break
                if code in errors:
                    break
    return sorted(errors)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _manifest_target(package_root: Path) -> str | None:
    manifest = _read_json_object(package_root / "release-manifest.json")
    targets = manifest.get("release_targets")
    if isinstance(targets, list) and len(targets) == 1 and targets[0] in NATIVE_TARGETS:
        return str(targets[0])
    return None


def _package_readmes(root: Path) -> Iterator[tuple[str, str, Path, str | None]]:
    for host in ("codex",):
        candidates = [
            ("generated", root / "build" / "generated" / "plugins" / host / README),
            ("distributable", root / "dist" / host / README),
        ]
        if host in NATIVE_HOSTS:
            candidates.append(
                (
                    "windows-x64-distributable",
                    root / "dist" / f"{host}-windows-x64" / README,
                )
            )
        for label, path in candidates:
            if path.is_file():
                yield host, label, path, _manifest_target(path.parent)


def _readme_errors(path: Path, host: str = "codex", target: str | None = None) -> list[str]:
    raw_text = path.read_text(encoding="utf-8")
    text = _normalize(raw_text)
    requirements = {
        "codex": CODEX_REQUIRED,
    }[host]
    errors = [
        code for code, phrases in requirements if any(_normalize(p) not in text for p in phrases)
    ]
    if host in NATIVE_HOSTS and target in NATIVE_README_REQUIRED:
        if any(_normalize(phrase) not in text for phrase in NATIVE_README_REQUIRED[str(target)]):
            errors.append(f"{host}_readme_{target}_release_boundary_missing")
        pass
        helper_boundary = (
            "npm's `installer/windows.ps1` is a separate installer helper, not a plugin launcher"
        )
        if _normalize(helper_boundary) not in text:
            errors.append(f"{host}_readme_installer_helper_boundary_missing")
    if host in NATIVE_HOSTS:
        errors.extend(_semantic_overclaim_errors(raw_text))
    pass
    return errors


def check_root(root: Path) -> dict[str, Any]:
    readmes = list(_package_readmes(root))
    present_hosts = {host for host, _label, _path, _target in readmes}
    missing_hosts = sorted({"codex"} - present_hosts)
    if not readmes:
        return {
            "status": "fail",
            "documents": {},
            "error_codes": [f"{host}_package_readme_missing" for host in missing_hosts],
        }
    documents: dict[str, Any] = {}
    errors: list[str] = [f"{host}_package_readme_missing" for host in missing_hosts]
    for host, label, path, target in readmes:
        found = _readme_errors(path, host, target)
        key = f"{host}/{label}"
        documents[key] = {"status": "fail" if found else "pass", "error_codes": found}
        errors.extend(f"{host}_{label}_{code}" for code in found)
    boundary_errors = _portability_boundary_errors(root)
    documents["portability_boundary"] = {
        "status": "fail" if boundary_errors else "pass",
        "error_codes": boundary_errors,
    }
    errors.extend(boundary_errors)
    return {
        "status": "fail" if errors else "pass",
        "documents": documents,
        "error_codes": sorted(set(errors)),
    }


def _manifest_file_paths(manifest: dict[str, Any]) -> set[str]:
    files = manifest.get("files")
    if not isinstance(files, list):
        return set()
    return {
        str(item["path"])
        for item in files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _runtime_directories(package_root: Path) -> set[str]:
    runtime = package_root / "runtime"
    if not runtime.is_dir():
        return set()
    return {path.name for path in runtime.iterdir() if path.is_dir()}


def _native_archive_boundary_errors(
    package_root: Path, target: str, *, require_runtime: bool = True
) -> list[str]:
    """Validate one native package along one target axis, including actual files."""

    contract = NATIVE_TARGETS[target]
    expected_runtime = [target] if require_runtime else []
    manifest = _read_json_object(package_root / "release-manifest.json")
    if not manifest:
        return ["native_manifest_unavailable"]
    errors: list[str] = []
    if manifest.get("release_targets") != [target]:
        errors.append("native_release_targets_invalid")
    if manifest.get("launchers") != [contract["launcher"]]:
        errors.append("native_launchers_invalid")
    if manifest.get("runtime_targets") != expected_runtime:
        errors.append("native_runtime_targets_invalid")
    launcher_files = {
        launcher
        for launcher in ("bin/launch.sh", "bin/launch.mjs", "bin/launch.ps1")
        if (package_root / Path(launcher)).is_file()
    }
    if launcher_files != {contract["launcher"]}:
        errors.append("native_launcher_files_invalid")
    expected_runtime_directories = {target} if require_runtime else set()
    if _runtime_directories(package_root) != expected_runtime_directories:
        errors.append("native_runtime_directories_invalid")
    inventory = _manifest_file_paths(manifest)
    inventory_launchers = {
        path for path in inventory if path in {"bin/launch.sh", "bin/launch.mjs", "bin/launch.ps1"}
    }
    inventory_runtimes = {
        path.split("/", 2)[1]
        for path in inventory
        if path.startswith("runtime/") and len(path.split("/", 2)) > 1
    }
    if inventory_launchers != {contract["launcher"]} or inventory_runtimes != set(expected_runtime):
        errors.append("native_file_inventory_invalid")
    if (package_root / "installer" / "windows.ps1").exists():
        errors.append("native_archive_contains_npm_windows_helper")
    return sorted(set(errors))


def _platform_manifest_errors(platforms: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if platforms.get("release_targets") != ["darwin-arm64", "windows-x64"] or platforms.get(
        "shipped_launchers"
    ) != {"darwin-arm64": "bin/launch.sh", "windows-x64": "bin/launch.mjs"}:
        errors.append("platform_manifest_release_boundary_invalid")
    if platforms.get("release_claim_status") != "windows-x64_candidate_live_gates_pending":
        errors.append("platform_manifest_release_claim_invalid")
    if platforms.get("signing_status") != "unvalidated":
        errors.append("platform_manifest_signing_claim_invalid")
    return errors


def _portability_boundary_errors(root: Path) -> list[str]:  # noqa: C901
    """Keep candidate and per-archive boundaries disjoint and complete."""

    errors: list[str] = []
    if (root / "packaging" / "launchers" / "launch.ps1").exists():
        errors.append("powershell_launcher_source_present")
    platforms = _read_json_object(root / "packaging" / "platforms.json")
    errors.extend(_platform_manifest_errors(platforms))
    package_json = _read_json_object(root / "package.json")
    npm_files = package_json.get("files")
    if (
        not isinstance(npm_files, list)
        or npm_files.count("installer/windows.ps1") != 1
        or not (root / "installer" / "windows.ps1").is_file()
    ):
        errors.append("npm_windows_helper_boundary_invalid")
    for host in NATIVE_HOSTS:
        generator = _read_json_object(root / "plugin-src" / host / "generator.json")
        copies = generator.get("copy_files", [])
        outputs = (
            {item.get("output") for item in copies if isinstance(item, dict)}
            if isinstance(copies, list)
            else set()
        )
        if (
            generator.get("release_targets") != ["darwin-arm64"]
            or generator.get("launchers") != ["bin/launch.sh"]
            or outputs & {"bin/launch.mjs", "bin/launch.ps1", "installer/windows.ps1"}
        ):
            errors.append(f"{host}_generator_release_boundary_invalid")
    for host, label, path, target in _package_readmes(root):
        package_root = path.parent
        if host in NATIVE_HOSTS:
            if target not in NATIVE_TARGETS:
                errors.append(f"{host}_{label}_native_target_invalid")
                continue
            manifest = _read_json_object(package_root / "release-manifest.json")
            generated_has_runtime = bool(
                manifest.get("runtime_targets") or _runtime_directories(package_root)
            )
            package_errors = _native_archive_boundary_errors(
                package_root,
                target,
                require_runtime=label != "generated" or generated_has_runtime,
            )
        else:
            package_errors = ["unsupported_host_package"]
        errors.extend(f"{host}_{label}_{code}" for code in package_errors)
    return sorted(set(errors))


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
        print("opensocrates-package-docs: FAIL")
        for code in report["error_codes"]:
            print(f"- {code}")
        return 1
    print(f"opensocrates-package-docs: PASS documents={len(report['documents'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
