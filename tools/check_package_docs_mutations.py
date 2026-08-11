#!/usr/bin/env python3
"""Mutation checks for bounded packaged-README overclaim patterns."""

from __future__ import annotations

import sys
from pathlib import Path

from check_package_docs import _readme_errors, _semantic_overclaim_errors

MUTATIONS = (
    (
        "claude_readme_universal_support_overclaim",
        "This plugin is fully validated on every Claude surface.",
    ),
    (
        "claude_readme_universal_support_overclaim",
        "The integration is supported across all Claude platforms.",
    ),
    (
        "claude_readme_universal_support_overclaim",
        "It is not shipped on Windows, but is fully validated on every Claude surface.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "The package is signed by Anthropic for production use.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "This is an Anthropic-approved integration.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "It is not signed by Apple, but it is endorsed by Anthropic.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "The release has been notarized for distribution.",
    ),
    (
        "claude_readme_managed_safety_overclaim",
        "The selector is safe on managed machines.",
    ),
    (
        "claude_readme_managed_safety_overclaim",
        "Managed policy hooks can never observe the selector prompt.",
    ),
    (
        "claude_readme_managed_safety_overclaim",
        "The sandbox guarantees complete isolation in enterprise environments.",
    ),
)

ACCURATE_LIMITATIONS = (
    "This package is not validated on all Claude surfaces.",
    "Signing and notarization are not claimed as validated.",
    "The selector is not isolated in organization-managed environments.",
    "Managed hooks can observe the selector prompt under managed policy.",
    "The package supports local Claude surfaces only where hooks are available.",
)

COMBINED_REVIEW_MUTATION = (
    "Fully validated on every Claude surface, signed by Anthropic, and safe on managed machines."
)


def main() -> int:  # noqa: C901  # One linear mutation matrix with bounded branches.
    root = Path(__file__).resolve().parent.parent
    readme = root / "build" / "generated" / "plugins" / "claude" / "README.md"
    try:
        baseline = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"package-doc-mutations: FAIL generated README unavailable: {type(exc).__name__}")
        return 1
    baseline_errors = _semantic_overclaim_errors(baseline)
    if baseline_errors:
        print(f"package-doc-mutations: FAIL baseline errors={','.join(baseline_errors)}")
        return 1
    failures: list[str] = []
    for expected, mutation in MUTATIONS:
        errors = _semantic_overclaim_errors(f"{baseline}\n\n{mutation}\n")
        if expected not in errors:
            failures.append(f"missed:{expected}")
    combined_errors = set(_semantic_overclaim_errors(f"{baseline}\n\n{COMBINED_REVIEW_MUTATION}\n"))
    expected_combined = {expected for expected, _mutation in MUTATIONS}
    if combined_errors != expected_combined:
        failures.append("missed:combined-review-mutation")
    for limitation in ACCURATE_LIMITATIONS:
        errors = _semantic_overclaim_errors(f"{baseline}\n\n{limitation}\n")
        if errors:
            failures.append(f"false-positive:{','.join(errors)}")
    codex_readme = root / "build" / "generated" / "plugins" / "codex" / "README.md"
    try:
        codex_baseline = codex_readme.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        failures.append("missing:codex-generated-readme")
    else:
        if _readme_errors(codex_readme, "codex"):
            failures.append("baseline:codex-readme")
        mutated = codex_baseline.replace("one-time interactive hook approval", "hook approval", 1)
        temporary = root / "build" / "package-doc-codex-mutation.md"
        try:
            temporary.write_text(mutated, encoding="utf-8")
            if "codex_readme_hook_approval_missing" not in _readme_errors(temporary, "codex"):
                failures.append("missed:codex-hook-approval")
        finally:
            temporary.unlink(missing_ok=True)
    if failures:
        print("package-doc-mutations: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        "package-doc-mutations: PASS "
        f"overclaims={len(MUTATIONS)} limitations={len(ACCURATE_LIMITATIONS)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
