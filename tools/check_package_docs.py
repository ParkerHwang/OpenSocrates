#!/usr/bin/env python3
"""Assert the generated package documentation keeps its stated limitations.

The repository README and SECURITY.md describe the Claude safe-mode trust
boundary and the per-surface validation grading.  Users who only ever read the
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

# Each requirement fails as one stable error code when any phrase is absent.
REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "claude_readme_safe_mode_scope_missing",
        (
            "user-, project-, and plugin-sourced customizations",
            "including the hooks those sources define",
        ),
    ),
    (
        "claude_readme_managed_policy_missing",
        (
            "Safe mode does not disable managed settings policy",
            "managed settings policy still applies, including policy-configured hooks",
        ),
    ),
    (
        "claude_readme_managed_hook_reachability_missing",
        (
            "policy-configured `UserPromptSubmit` hook still runs inside the selector process",
            "receives the current prompt on standard input",
            "`additionalContext` that influences selection",
        ),
    ),
    (
        "claude_readme_hook_blanket_claim_present",
        ("Not every hook is disabled inside the selector",),
    ),
    (
        "claude_readme_desktop_grading_missing",
        ("Implemented; no live hook-delivery probe receipt",),
    ),
    (
        "claude_readme_cowork_grading_missing",
        ("CLI marketplace visibility and live hook delivery are unvalidated",),
    ),
    (
        "claude_readme_chat_grading_missing",
        (
            "Anthropic does not run plugin hooks in Chat",
            "the customization ZIP upload path is unvalidated",
        ),
    ),
    (
        "claude_readme_grounding_gate_missing",
        (
            "Read-only `PostToolUse` hook accepts a grounding read only when",
            "file's terminal marker",
            "one bounded repair pass",
        ),
    ),
    (
        "claude_readme_grounding_privacy_missing",
        (
            "complete Read response is checked only in memory",
            "contains no prompt, tool output, workspace path, or artifact path",
        ),
    ),
    (
        "claude_readme_release_boundary_missing",
        (
            "released for Apple-silicon macOS (`darwin-arm64`) only",
            "ships only `bin/launch.sh`",
            "No PowerShell launcher is included",
            "macOS Intel, Linux, Windows",
            "Binary signing, notarization, clean-machine installation",
            "are not claimed as validated",
        ),
    ),
)

# Wording that would restore an overstated claim.
FORBIDDEN: tuple[tuple[str, str], ...] = (
    (
        "claude_readme_blanket_hooks_disabled_claim",
        "hooks, project instructions, and session persistence disabled",
    ),
    ("claude_readme_signing_overclaim", "signed and notarized"),
    ("claude_readme_platform_overclaim", "validated on all platforms"),
    ("claude_readme_host_delivery_overclaim", "live delivery is validated"),
)


def _normalize(text: str) -> str:
    """Collapse wrapping so phrase checks survive Markdown line breaks."""

    return re.sub(r"\s+", " ", text)


def _package_readmes(root: Path) -> Iterator[tuple[str, Path]]:
    candidates = (
        ("generated", root / "build" / "generated" / "plugins" / "claude" / README),
        ("distributable", root / "dist" / "claude" / README),
    )
    for label, path in candidates:
        if path.is_file():
            yield label, path


def _readme_errors(path: Path) -> list[str]:
    text = _normalize(path.read_text(encoding="utf-8"))
    errors = [code for code, phrases in REQUIRED if any(_normalize(p) not in text for p in phrases)]
    errors.extend(code for code, phrase in FORBIDDEN if _normalize(phrase) in text)
    return errors


def check_root(root: Path) -> dict[str, Any]:
    readmes = list(_package_readmes(root))
    if not readmes:
        return {
            "status": "fail",
            "documents": {},
            "error_codes": ["claude_package_readme_missing"],
        }
    documents: dict[str, Any] = {}
    errors: list[str] = []
    for label, path in readmes:
        found = _readme_errors(path)
        documents[label] = {"status": "fail" if found else "pass", "error_codes": found}
        errors.extend(f"{label}_{code}" for code in found)
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


def _portability_boundary_errors(root: Path) -> list[str]:
    """Keep source metadata and both shipped package surfaces darwin-arm64-only."""

    errors: list[str] = []
    if (root / "packaging" / "launchers" / "launch.ps1").exists():
        errors.append("powershell_launcher_source_present")
    try:
        platforms = json.loads((root / "packaging" / "platforms.json").read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        platforms = {}
    if platforms.get("release_targets") != ["darwin-arm64"] or platforms.get(
        "shipped_launchers"
    ) != {"darwin-arm64": "bin/launch.sh"}:
        errors.append("platform_manifest_release_boundary_invalid")
    for host in ("claude", "codex"):
        try:
            generator = json.loads(
                (root / "plugin-src" / host / "generator.json").read_text("utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            generator = {}
        copies = generator.get("copy_files", [])
        outputs = (
            {item.get("output") for item in copies if isinstance(item, dict)}
            if isinstance(copies, list)
            else set()
        )
        if (
            generator.get("release_targets") != ["darwin-arm64"]
            or generator.get("launchers") != ["bin/launch.sh"]
            or "bin/launch.ps1" in outputs
        ):
            errors.append(f"{host}_generator_release_boundary_invalid")
        for package_root in (
            root / "build" / "generated" / "plugins" / host,
            root / "dist" / host,
        ):
            if package_root.is_dir() and (package_root / "bin" / "launch.ps1").exists():
                errors.append(f"{host}_{package_root.parent.name}_powershell_launcher_present")
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
