#!/usr/bin/env python3
"""Validate durable coordination fields in a GitHub pull request body."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
)
REQUIRED_SECTIONS = (
    "Summary",
    "Impact",
    "Tracking",
    "Validation",
    "Evidence level",
    "Remaining limitations",
    "Handoff",
)
PLACEHOLDERS = {"", "n/a", "none", "todo", "tbd", "pending", "-"}
ISSUE_PATTERN = re.compile(r"(?im)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\d+\b")
NO_ISSUE_PATTERN = re.compile(r"(?im)^[ \t]*No issue:[ \t]*(\S.*)$")
PRIORITY_PATTERN = re.compile(r"(?im)^[ \t]*(?:-\s*)?Priority:[ \t]*(.*)$")
WORKSTREAM_PATTERN = re.compile(r"(?im)^[ \t]*(?:-\s*)?Workstream:[ \t]*(.*)$")
CHECKED_EVIDENCE_PATTERN = re.compile(
    r"(?im)^\s*-\s*\[[xX]\]\s*(?:Implemented|Locally validated|Release-validated|"
    r"Live host receipt captured|Required evidence is unavailable)\b"
)
FIELD_PATTERN = re.compile(
    r"(?im)^[ \t]*(Last verified commit|Commands run|Commands not run|Remaining work|Known limitations):[ \t]*(.*)$"
)
HANDOFF_FIELDS = (
    "Last verified commit",
    "Commands run",
    "Commands not run",
    "Remaining work",
    "Known limitations",
)
REQUIRED_PHRASES = {
    "AGENTS.md": (
        "protected `main`",
        "hand-edit",
        "semantically aligned",
        "telemetry",
        "last verified commit",
    ),
    "CLAUDE.md": (
        "repository development only",
        "AGENTS.md",
        "do not load project `CLAUDE.md`",
    ),
    ".github/copilot-instructions.md": (
        "AGENTS.md",
        "protected `main`",
        "hand-edit",
    ),
}


def section_body(body: str, heading: str) -> str | None:
    pattern = re.compile(rf"(?ims)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)")
    match = pattern.search(body)
    return match.group(1).strip() if match else None


def meaningful(value: str) -> bool:
    cleaned = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL).strip()
    return cleaned.casefold() not in PLACEHOLDERS


def _tracking_errors(tracking: str) -> list[str]:
    errors: list[str] = []
    no_issue = NO_ISSUE_PATTERN.search(tracking)
    if not ISSUE_PATTERN.search(tracking) and not (no_issue and meaningful(no_issue.group(1))):
        errors.append(
            "Tracking must contain Closes/Fixes/Resolves #N or 'No issue: <specific explanation>'."
        )
    if tracking:
        priority = PRIORITY_PATTERN.search(tracking)
        if not priority or not meaningful(priority.group(1)):
            errors.append("Tracking must contain a non-empty Priority: value.")
        workstream = WORKSTREAM_PATTERN.search(tracking)
        if not workstream or not meaningful(workstream.group(1)):
            errors.append("Tracking must contain a non-empty Workstream: value.")
    return errors


def _evidence_errors(evidence: str) -> list[str]:
    if evidence and not CHECKED_EVIDENCE_PATTERN.search(evidence):
        return ["Evidence level must have at least one recognized checked option."]
    return []


def _handoff_errors(handoff: str, draft: bool) -> list[str]:
    errors: list[str] = []
    fields = {name: value for name, value in FIELD_PATTERN.findall(handoff)}
    for name in HANDOFF_FIELDS:
        if name not in fields:
            errors.append(f"Handoff is missing field: {name}:")
        elif not meaningful(fields[name]):
            if draft and name in {"Last verified commit", "Commands run"}:
                continue
            errors.append(f"Handoff field is empty or placeholder-only: {name}:")
    return errors


def _validation_errors(validation: str, draft: bool) -> list[str]:
    if not validation or draft:
        return []
    errors: list[str] = []
    if not re.search(r"(?im)^\s*-\s*\[[xX]\]\s*Relevant tests pass\.", validation):
        errors.append("A non-draft PR must check 'Relevant tests pass.'")
    if re.search(
        r"(?im)^\s*-\s*\[[ xX]\]\s*Required checks not run are explained below\.", validation
    ) and not re.search(
        r"(?im)^\s*-\s*\[[xX]\]\s*Required checks not run are explained below\.",
        validation,
    ):
        errors.append("A non-draft PR must confirm that checks not run are explained below.")
    return errors


def validate_pull_request(event: dict[str, Any]) -> list[str]:
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        return []

    body = str(pull_request.get("body") or "")
    draft = bool(pull_request.get("draft"))
    errors: list[str] = []

    sections: dict[str, str] = {}
    for heading in REQUIRED_SECTIONS:
        content = section_body(body, heading)
        if content is None:
            errors.append(f"missing required section: ## {heading}")
        elif not meaningful(content):
            errors.append(f"required section is empty or placeholder-only: ## {heading}")
        else:
            sections[heading] = content

    errors.extend(_tracking_errors(sections.get("Tracking", "")))
    errors.extend(_evidence_errors(sections.get("Evidence level", "")))
    errors.extend(_handoff_errors(sections.get("Handoff", ""), draft))
    errors.extend(_validation_errors(sections.get("Validation", ""), draft))
    return errors


def _required_file_errors(root: Path) -> list[str]:
    return [
        f"missing governance file: {relative}"
        for relative in REQUIRED_FILES
        if not (root / relative).is_file()
    ]


def _policy_phrase_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for relative, phrases in REQUIRED_PHRASES.items():
        path = root / relative
        if not path.is_file():
            continue
        folded = path.read_text(encoding="utf-8").casefold()
        for phrase in phrases:
            if phrase.casefold() not in folded:
                errors.append(f"{relative} is missing required policy: {phrase}")
    return errors


def _template_section_errors(root: Path) -> list[str]:
    template_path = root / ".github/pull_request_template.md"
    if not template_path.is_file():
        return []
    template = template_path.read_text(encoding="utf-8")
    return [
        f"PR template is missing section: ## {heading}"
        for heading in REQUIRED_SECTIONS
        if section_body(template, heading) is None
    ]


def _toolchain_errors(root: Path) -> list[str]:
    errors: list[str] = []
    workflow_path = root / ".github/workflows/ci.yml"
    if not workflow_path.is_file() or "make governance-check" not in workflow_path.read_text(
        encoding="utf-8"
    ):
        errors.append("CI product contracts must run make governance-check")
    makefile_path = root / "Makefile"
    if not makefile_path.is_file():
        errors.append("missing Makefile")
        return errors
    makefile = makefile_path.read_text(encoding="utf-8")
    for relative in REQUIRED_FILES:
        if relative not in makefile:
            errors.append(f"Makefile docs-check is missing governance path: {relative}")
    return errors


def validate_repository(root: Path) -> list[str]:
    return [
        *_required_file_errors(root),
        *_policy_phrase_errors(root),
        *_template_section_errors(root),
        *_toolchain_errors(root),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--event", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    errors = validate_repository(args.root.resolve())
    event_checked = False
    if args.event is not None:
        try:
            event = json.loads(args.event.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"governance-check: unable to read event: {exc}", file=sys.stderr)
            return 2
        event_checked = "pull_request" in event
        errors.extend(validate_pull_request(event))

    report = {
        "schema_version": 1,
        "status": "fail" if errors else "pass",
        "event_checked": event_checked,
        "errors": sorted(errors),
    }
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if errors:
        print("governance-check: FAIL", file=sys.stderr)
        for error in sorted(errors):
            print(f"- {error}", file=sys.stderr)
        return 1

    print("governance-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
