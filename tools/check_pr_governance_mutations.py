#!/usr/bin/env python3
"""Mutation tests for the pull-request governance validator."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from check_pr_governance import REQUIRED_FILES, validate_pull_request, validate_repository

GOVERNANCE_FILES = (*REQUIRED_FILES, ".github/workflows/ci.yml", "Makefile")

BASE_BODY = """## Summary

Add durable cross-machine coordination rules.

## Impact

Contributor workflow only; no runtime or privacy behavior changes.

## Tracking

No issue: repository-maintainer governance setup approved directly.

- Project status: In Review
- Priority: P1
- Workstream: Documentation

## Validation

- [x] Relevant tests pass.
- [x] Generated files were produced by their canonical generators or no generated inputs changed.
- [x] English and Korean user-facing documentation remain aligned or no localized user-facing text changed.
- [x] No credentials, private prompts, transcripts, sensitive paths, or local-only artifacts were added.
- [x] Required checks not run are explained below.

## Evidence level

- [x] Implemented
- [ ] Locally validated
- [ ] Release-validated
- [ ] Live host receipt captured
- [ ] Required evidence is unavailable

## Remaining limitations

The Project workflow configuration remains GitHub-hosted state.

## Handoff

Last verified commit: abc1234
Commands run: python tools/check_pr_governance_mutations.py
Commands not run: release-check; no native package behavior changed
Remaining work: review and merge after required checks pass
Known limitations: no runtime behavior is claimed
"""


def event(body: str = BASE_BODY, *, draft: bool = False) -> dict[str, object]:
    return {"pull_request": {"body": body, "draft": draft}}


def fixture(tmp: Path, root: Path) -> Path:
    repo = Path(tmp) / "repo"
    for relative in GOVERNANCE_FILES:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    return repo


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    assert validate_repository(root) == []
    assert validate_pull_request(event()) == []
    assert validate_pull_request({"ref": "refs/heads/main"}) == []

    failures = {
        "missing section": BASE_BODY.replace("## Impact", "## Effects"),
        "missing tracking": BASE_BODY.replace(
            "No issue: repository-maintainer governance setup approved directly.", "TBD"
        ),
        "no evidence": BASE_BODY.replace("- [x] Implemented", "- [ ] Implemented"),
        "missing handoff field": BASE_BODY.replace("Last verified commit: abc1234\n", ""),
        "unchecked tests": BASE_BODY.replace(
            "- [x] Relevant tests pass.", "- [ ] Relevant tests pass."
        ),
    }
    for name, body in failures.items():
        errors = validate_pull_request(event(body))
        assert errors, f"mutation unexpectedly passed: {name}"

    draft_body = BASE_BODY.replace(
        "Last verified commit: abc1234", "Last verified commit: TBD"
    ).replace("Commands run: python tools/check_pr_governance_mutations.py", "Commands run: TBD")
    assert validate_pull_request(event(draft_body, draft=True)) == []

    blank_limitations = BASE_BODY.replace(
        "Known limitations: no runtime behavior is claimed",
        "Known limitations:\nThis is trailing handoff prose.",
    )
    blank_limitation_errors = validate_pull_request(event(blank_limitations))
    assert any(
        "empty or placeholder-only: Known limitations:" in item for item in blank_limitation_errors
    ), blank_limitation_errors

    blank_commands = BASE_BODY.replace(
        "Commands run: python tools/check_pr_governance_mutations.py",
        "Commands run:",
    )
    blank_command_errors = validate_pull_request(event(blank_commands))
    assert any(
        "empty or placeholder-only: Commands run:" in item for item in blank_command_errors
    ), blank_command_errors
    assert not any("missing field: Commands run:" in item for item in blank_command_errors), (
        blank_command_errors
    )

    draft_blank = BASE_BODY.replace(
        "Last verified commit: abc1234", "Last verified commit:"
    ).replace(
        "Commands run: python tools/check_pr_governance_mutations.py",
        "Commands run:",
    )
    assert validate_pull_request(event(draft_blank, draft=True)) == []

    bare_no_issue = BASE_BODY.replace(
        "No issue: repository-maintainer governance setup approved directly.",
        "No issue:\n\n- Project status: In Review\n- Priority:\n- Workstream:",
    )
    tracking_errors = validate_pull_request(event(bare_no_issue))
    assert any("Tracking must contain" in item for item in tracking_errors), tracking_errors

    blank_priority = BASE_BODY.replace("- Priority: P1", "- Priority:")
    priority_errors = validate_pull_request(event(blank_priority))
    assert any("non-empty Priority:" in item for item in priority_errors), priority_errors

    missing_workstream = BASE_BODY.replace("- Workstream: Documentation\n", "")
    workstream_errors = validate_pull_request(event(missing_workstream))
    assert any("non-empty Workstream:" in item for item in workstream_errors), workstream_errors

    with tempfile.TemporaryDirectory() as tmp:
        mutated = fixture(Path(tmp), root)
        agents = mutated / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace(
                "Do not add telemetry", "Telemetry must not be added"
            ),
            encoding="utf-8",
        )
        assert validate_repository(mutated) == []

    with tempfile.TemporaryDirectory() as tmp:
        mutated = fixture(Path(tmp), root)
        (mutated / "CLAUDE.md").unlink()
        errors = validate_repository(mutated)
        assert any("missing governance file: CLAUDE.md" in item for item in errors)

    with tempfile.TemporaryDirectory() as tmp:
        mutated = fixture(Path(tmp), root)
        template = mutated / ".github/pull_request_template.md"
        template.write_text(
            template.read_text(encoding="utf-8").replace("## Handoff", "## Transfer"),
            encoding="utf-8",
        )
        errors = validate_repository(mutated)
        assert any("PR template is missing section: ## Handoff" in item for item in errors)

    print("governance-check-tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
