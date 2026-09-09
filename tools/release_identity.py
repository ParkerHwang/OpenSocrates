"""Read-only exact-tag release target checks, before any publication mutation."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def remote_tag_commit(output: str, tag: str) -> str:
    refs = {f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"}
    rows = {}
    for line in output.splitlines():
        fields = line.split()
        if (
            len(fields) != 2
            or fields[1] not in refs
            or not re.fullmatch(r"[0-9a-f]{40}", fields[0])
            or fields[1] in rows
        ):
            raise ValueError("remote tag response invalid")
        rows[fields[1]] = fields[0]
    if f"refs/tags/{tag}" not in rows:
        raise ValueError("release tag missing; create the exact reviewed tag first")
    return rows.get(f"refs/tags/{tag}^{{}}", rows[f"refs/tags/{tag}"])


def validate_target(version: str, ref: str, commit: str, output: str) -> None:
    tag = f"v{version}"
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or ref != f"refs/tags/{tag}":
        raise ValueError("publication requires the exact version tag, not a branch")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or remote_tag_commit(output, tag) != commit:
        raise ValueError("release tag points to a different source commit")


def main() -> int:
    version = Path("VERSION").read_text().strip()
    commit = os.environ.get("GITHUB_SHA", "")
    ref = os.environ.get("GITHUB_REF", "")
    tag = f"v{version}"
    try:
        output = subprocess.check_output(
            ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
            text=True,
        )
        validate_target(version, ref, commit, output)
        if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != commit:
            raise ValueError("checked-out source differs from release commit")
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"], check=True)
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"release identity: FAIL ({error})")
        return 1
    print("release identity: PASS (exact remote tag, checkout and merged main ancestor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
