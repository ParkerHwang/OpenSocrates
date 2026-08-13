#!/usr/bin/env python3
"""Check that `make generated-check` only diffs paths a clean checkout can have.

The generated-check recipe compares committed artifacts against a fresh
rebuild. A reference path that is neither committed nor produced by the recipe
itself makes the target pass only on a machine that happens to hold a stale
build tree, and fail on every clean checkout. This check keeps that class of
break out of CI.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
TARGET = "generated-check"
OUTPUT_FLAGS = frozenset({"--output", "--output-dir"})


def _recipe(text: str, target: str) -> str:
    """Return the recipe body of one Makefile target with continuations joined."""

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(f"{target}:"):
            continue
        body: list[str] = []
        for candidate in lines[index + 1 :]:
            if not candidate.startswith("\t"):
                break
            body.append(candidate[1:].removeprefix("@"))
        return "\n".join(body).replace("\\\n", " ")
    raise SystemExit(f"generated contract: FAIL (Makefile target {target} is missing)")


def _tokens(recipe: str) -> list[list[str]]:
    """Split a recipe into shell commands, tolerating unbalanced shell quoting."""

    commands: list[list[str]] = []
    for statement in recipe.replace("\n", ";").split(";"):
        try:
            tokens = shlex.split(statement)
        except ValueError:
            tokens = statement.split()
        if tokens:
            commands.append(tokens)
    return commands


def _repository_path(token: str) -> str | None:
    """Return a repository-relative path for a `$(ROOT)`-anchored token."""

    if not token.startswith("$(ROOT)/"):
        return None
    return token.removeprefix("$(ROOT)/")


def _tracked(path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    listed = subprocess.run(
        ["git", "ls-files", "--", path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return listed.returncode == 0 and bool(listed.stdout.strip())


def check() -> list[str]:
    commands = _tokens(_recipe(MAKEFILE.read_text(encoding="utf-8"), TARGET))
    produced: set[str] = set()
    violations: list[str] = []
    for tokens in commands:
        for index, token in enumerate(tokens):
            if token in OUTPUT_FLAGS and index + 1 < len(tokens):
                path = _repository_path(tokens[index + 1])
                if path is not None:
                    produced.add(path)
        if Path(tokens[0]).name != "diff":
            continue
        for token in tokens[1:]:
            if token.startswith("-"):
                continue
            path = _repository_path(token)
            if path is None or _tracked(path):
                continue
            if any(path == item or path.startswith(f"{item}/") for item in produced):
                continue
            violations.append(
                f"{TARGET} diffs {path}, which is neither committed nor generated "
                "earlier in the same recipe; a clean checkout has no such path"
            )
    return violations


def main() -> int:
    violations = check()
    if violations:
        print("generated contract: FAIL", file=sys.stderr)
        print("\n".join(violations), file=sys.stderr)
        return 1
    print(f"generated contract: PASS ({TARGET} reference paths are committed or regenerated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
