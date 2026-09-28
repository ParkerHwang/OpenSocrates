"""Disposable-fixture checks for the project-memory source adapter."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from opensocrates.project_memory import sources


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def snapshot(root: Path, kind: sources.WorkspaceKind) -> dict[str, object]:
    return sources.capture_snapshot(root, kind, "project-1", "workspace-1")


def check_directory() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "brief.md").write_text("original", encoding="utf-8")
        first = snapshot(root, "directory")
        assert first["head_oid"] is None and first["coverage"]["complete_for_scope"]
        assert "original" not in str(first)
        assert (
            sources.revalidate_snapshot(first, snapshot(root, "directory"))["freshness"]
            == "current"
        )
        (root / "brief.md").write_text("changed", encoding="utf-8")
        edited = snapshot(root, "directory")
        assert sources.revalidate_snapshot(first, edited)["changes"]["modified"] == ["brief.md"]
        (root / "more.md").write_text("new", encoding="utf-8")
        assert sources.revalidate_snapshot(edited, snapshot(root, "directory"))["changes"][
            "added"
        ] == ["more.md"]
        (root / "more.md").rename(root / "renamed.md")
        report = sources.revalidate_snapshot(first, snapshot(root, "directory"))
        assert report["changes"]["added"] == ["renamed.md"]
        assert (
            sources.revalidate_snapshot(first, {**first, "workspace_id": "other"})["reason"]
            == "identity_mismatch"
        )
        try:
            sources.capture_snapshot(root, "directory", "p", "w", ("../outside",))
        except ValueError as error:
            assert str(error) == "unsafe_path"
        else:
            raise AssertionError("path escape accepted")


def check_rename_and_symlink() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "root"
        root.mkdir()
        (root / "old.md").write_text("same", encoding="utf-8")
        first = snapshot(root, "directory")
        (root / "old.md").rename(root / "new.md")
        report = sources.revalidate_snapshot(first, snapshot(root, "directory"))
        assert report["freshness"] == "stale"
        assert report["changes"]["renamed"] == [{"from": "old.md", "to": "new.md"}]
        outside = Path(temporary) / "outside.md"
        outside.write_text("canary-outside-root", encoding="utf-8")
        (root / "link.md").symlink_to(outside)
        linked = snapshot(root, "directory")
        assert "link.md" not in linked["files"]
        assert linked["coverage"]["omitted_categories"]["unsafe_path"] == 1
        assert "canary-outside-root" not in str(linked)
        assert sources.revalidate_snapshot(linked, linked)["freshness"] == "unknown"
        replacement = Path(temporary) / "replacement"
        replacement.mkdir()
        (replacement / "new.md").write_text("same", encoding="utf-8")
        root.rename(Path(temporary) / "old-root")
        replacement.rename(root)
        assert (
            sources.revalidate_snapshot(first, snapshot(root, "directory"))["reason"]
            == "identity_mismatch"
        )


def check_git() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        git(root, "init", "-q")
        git(root, "config", "user.email", "fixture@example.test")
        git(root, "config", "user.name", "Fixture")
        (root / "module.py").write_text(
            "import os\ndef helper():\n    return 1\n", encoding="utf-8"
        )
        (root / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-qm", "fixture")
        first = snapshot(root, "git_worktree")
        assert not first["dirty"] and first["head_oid"]
        assert first["files"]["module.py"]["python"]["definitions"][0]["name"] == "helper"
        (root / "module.py").write_text(
            "import os\ndef helper():\n    return 2\n", encoding="utf-8"
        )
        edited = snapshot(root, "git_worktree")
        report = sources.revalidate_snapshot(first, edited)
        assert report["freshness"] == "stale" and report["changes"]["modified"] == ["module.py"]
        assert not report["changes"]["head_changed"]
        git(root, "add", "module.py")
        staged = snapshot(root, "git_worktree")
        assert sources.revalidate_snapshot(edited, staged)["changes"]["dirty_changed"]
        (root / "caller.py").write_text("from module import helper\n", encoding="utf-8")
        untracked = snapshot(root, "git_worktree")
        assert sources.revalidate_snapshot(staged, untracked)["changes"]["added"] == ["caller.py"]
        (root / "pyproject.toml").write_text("[project]\nname='changed'\n", encoding="utf-8")
        configured = snapshot(root, "git_worktree")
        assert sources.revalidate_snapshot(untracked, configured)["changes"][
            "configuration_changed"
        ]
        git(root, "add", ".")
        git(root, "commit", "-qm", "changed")
        committed = snapshot(root, "git_worktree")
        assert sources.revalidate_snapshot(configured, committed)["changes"]["head_changed"]
        git(root, "checkout", "-qb", "other")
        switched = snapshot(root, "git_worktree")
        assert sources.revalidate_snapshot(committed, switched)["changes"]["ref_changed"]


def check_mid_read_change() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        target = root / "brief.md"
        target.write_text("before", encoding="utf-8")
        real_read = sources._read_file
        reads = 0

        def changing_read(root_fd: int, relative: str):  # type: ignore[no-untyped-def]
            nonlocal reads
            result = real_read(root_fd, relative)
            reads += 1
            if reads == 1:
                target.write_text("after!", encoding="utf-8")
            return result

        with patch.object(sources, "_read_file", side_effect=changing_read):
            unstable = snapshot(root, "directory")
        assert unstable["coverage"]["unstable_files"] == ["brief.md"]
        assert not unstable["coverage"]["complete_for_scope"]
        assert sources.revalidate_snapshot(unstable, unstable)["freshness"] == "unknown"


def check_repository_git_executable_is_never_run() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        git(root, "init", "-q")
        git(root, "config", "user.email", "fixture@example.test")
        git(root, "config", "user.name", "Fixture")
        (root / "module.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        git(root, "add", "module.py")
        git(root, "commit", "-qm", "fixture")
        sentinel = root / "executed.txt"
        binary = root / "git"
        binary.write_text(f"#!/bin/sh\nprintf executed > {sentinel}\n", encoding="utf-8")
        binary.chmod(0o700)
        with patch.dict(os.environ, {"PATH": str(root) + os.pathsep + os.environ["PATH"]}):
            try:
                snapshot(root, "git_worktree")
            except ValueError as error:
                assert str(error) == "unsafe_git_executable"
            else:
                raise AssertionError("repository Git executable was accepted")
        assert not sentinel.exists()


if __name__ == "__main__":
    check_directory()
    check_rename_and_symlink()
    check_git()
    check_mid_read_change()
    check_repository_git_executable_is_never_run()
    print("memory source fixtures passed")
