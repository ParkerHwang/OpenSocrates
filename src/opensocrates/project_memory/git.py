"""Bounded Git metadata calls with no repository-controlled executable lookup."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


def _git_binary(root: Path) -> Path:
    found = shutil.which("git")
    if not found:
        raise ValueError("git_unavailable")
    binary = Path(found).absolute()
    try:
        info = binary.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or (getattr(info, "st_file_attributes", 0) & 0x400)
        ):
            raise ValueError("unsafe_git_executable")
        binary = binary.resolve(strict=True)
        root_info = root.stat(follow_symlinks=False)
        for ancestor in binary.parents:
            try:
                candidate = ancestor.lstat()
            except OSError:
                continue
            if stat.S_ISLNK(candidate.st_mode) or (
                getattr(candidate, "st_file_attributes", 0) & 0x400
            ):
                raise ValueError("unsafe_git_executable")
            if (candidate.st_dev, candidate.st_ino) == (root_info.st_dev, root_info.st_ino):
                raise ValueError("unsafe_git_executable")
    except OSError as error:
        raise ValueError("git_unavailable") from error
    return binary


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run an installed Git executable for read-only metadata, without hooks or locks."""
    binary = _git_binary(root)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "NUL" if os.name == "nt" else "/dev/null",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    try:
        return subprocess.run(
            [binary, "-c", "core.fsmonitor=false", "-C", str(root), *args],
            capture_output=True,
            timeout=3,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("git_unavailable") from error
