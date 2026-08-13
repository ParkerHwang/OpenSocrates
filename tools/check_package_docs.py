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
CLAUDE_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
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
        "claude_readme_teacher_questions_missing",
        (
            "deterministically assembles the selected teacher questions",
            "hidden `additionalContext` message that leads with teacher questions",
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

CURSOR_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "cursor_readme_explicit_skill_boundary_missing",
        (
            "Manual `/opensocrates` invocation",
            "a live Cursor receipt is pending",
        ),
    ),
    (
        "cursor_readme_no_selector_cost_missing",
        (
            "no separate OpenSocrates selector model call is added",
            "automatic per-prompt hook selection: not included",
        ),
    ),
    (
        "cursor_readme_content_only_boundary_missing",
        (
            "There is no launcher, native runtime, executable, hook, MCP server",
            "background service",
        ),
    ),
    (
        "cursor_readme_teacher_questions_missing",
        (
            "complete procedure begins with three authored teacher questions",
            "content-only skill behavior, not an OpenSocrates hook claim",
        ),
    ),
)

ANTIGRAVITY_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "antigravity_readme_explicit_tier_missing",
        (
            "experimental, explicit-skill Antigravity boundary",
            "Automatic per-prompt selection: **not included**",
            "Native hook delivery: **not claimed**",
        ),
    ),
    (
        "antigravity_readme_quota_boundary_missing",
        (
            "Additional model calls: **none**",
            "does not consume a separate Google AI Pro request",
        ),
    ),
    (
        "antigravity_readme_file_drop_contract_missing",
        (
            "`~/.gemini/config/plugins/<plugin-name>/`",
            "required plugin marker",
            "refuses to replace a directory without its exact ownership marker",
        ),
    ),
    (
        "antigravity_readme_teacher_questions_missing",
        (
            "complete procedure begins with three authored teacher questions",
            "content delivered by the skill, not hidden hook injection",
        ),
    ),
)

GROK_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "grok_readme_native_skill_contract_missing",
        (
            "one user-visible `opensocrates` skill",
            "same turn through its native skill-selection surface",
            "explicitly with `/opensocrates`",
        ),
    ),
    (
        "grok_readme_content_only_boundary_missing",
        (
            "contains no hooks, MCP server, agent, command, launcher, native runtime",
            "without requiring another API key or hardcoded model ID",
        ),
    ),
    (
        "grok_readme_grounding_gate_missing",
        (
            "complete procedure, including its leading teacher questions, must be read in "
            "the current conversation",
        ),
    ),
    (
        "grok_readme_teacher_questions_missing",
        (
            "complete procedure begins with three authored teacher questions",
            "does not claim OpenSocrates hook injection",
        ),
    ),
)

OPENCODE_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "opencode_stable_same_turn_boundary_missing",
        (
            "Stable `chat.message` same-turn mutation",
            "minimum verified host version of OpenCode 1.18.18",
            "an interactive TUI receipt were all live-validated",
            "Native skill invocation remains",
        ),
    ),
    (
        "opencode_provider_neutrality_missing",
        (
            "not a product dependency",
            "credentials, endpoints, and model IDs are never embedded",
            "no network call, subprocess call, recursive OpenCode call",
        ),
    ),
    (
        "opencode_owned_path_boundary_missing",
        (
            "owned bridge, its ownership sidecar",
            "owned `opensocrates` skill directory",
            "does not rewrite `opencode.json`",
        ),
    ),
    (
        "opencode_teacher_question_delivery_missing",
        (
            "first section contains its three authored teacher questions",
            "same generated question-led procedure",
            "preventing a duplicate question preamble",
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

# Deliberately bounded semantic patterns for three high-risk claim classes.
# They operate within one sentence/Markdown line, require both a strong claim
# and its sensitive scope/authority, and do not attempt to lint general prose.
SEMANTIC_OVERCLAIMS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "claude_readme_universal_support_overclaim",
        (
            re.compile(
                r"\b(?:fully|completely|universally)\s+"
                r"(?:validated|supported|compatible)\b.{0,96}"
                r"\b(?:all|every)\s+(?:claude\s+)?"
                r"(?:surface|platform|environment)s?\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:validated|supported|compatible)\b.{0,48}"
                r"\b(?:across|on|for)\s+(?:all|every)\s+"
                r"(?:claude\s+)?(?:surface|platform|environment)s?\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "claude_readme_endorsement_overclaim",
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
        "claude_readme_managed_safety_overclaim",
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


def _package_readmes(root: Path) -> Iterator[tuple[str, str, Path]]:
    for host in ("antigravity", "claude", "codex", "cursor", "grok", "opencode"):
        candidates = (
            ("generated", root / "build" / "generated" / "plugins" / host / README),
            ("distributable", root / "dist" / host / README),
        )
        for label, path in candidates:
            if path.is_file():
                yield host, label, path


def _readme_errors(path: Path, host: str = "claude") -> list[str]:
    raw_text = path.read_text(encoding="utf-8")
    text = _normalize(raw_text)
    requirements = {
        "antigravity": ANTIGRAVITY_REQUIRED,
        "claude": CLAUDE_REQUIRED,
        "codex": CODEX_REQUIRED,
        "cursor": CURSOR_REQUIRED,
        "grok": GROK_REQUIRED,
        "opencode": OPENCODE_REQUIRED,
    }[host]
    errors = [
        code for code, phrases in requirements if any(_normalize(p) not in text for p in phrases)
    ]
    if host == "claude":
        errors.extend(code for code, phrase in FORBIDDEN if _normalize(phrase) in text)
        errors.extend(_semantic_overclaim_errors(raw_text))
    return errors


def check_root(root: Path) -> dict[str, Any]:
    readmes = list(_package_readmes(root))
    present_hosts = {host for host, _label, _path in readmes}
    missing_hosts = sorted(
        {"antigravity", "claude", "codex", "cursor", "grok", "opencode"} - present_hosts
    )
    if not readmes:
        return {
            "status": "fail",
            "documents": {},
            "error_codes": [f"{host}_package_readme_missing" for host in missing_hosts],
        }
    documents: dict[str, Any] = {}
    errors: list[str] = [f"{host}_package_readme_missing" for host in missing_hosts]
    for host, label, path in readmes:
        found = _readme_errors(path, host)
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
