"""Native Windows regressions, including real packaged bytes when --packages is set."""

from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from uuid import uuid4

from opensocrates.persistence.atomic import append_fsync, atomic_replace_bytes, read_bytes
from opensocrates.persistence.permissions import (
    check_permissions,
    create_owner_only_directory,
    create_owner_only_file,
    secure_mode,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = "--packages" in sys.argv
if PACKAGES:
    sys.argv.remove("--packages")


def _grant_everyone_read(path: Path) -> None:
    subprocess.run(
        ["icacls.exe", str(path), "/grant", "*S-1-1-0:(R)"],
        check=True,
        capture_output=True,
    )


def _set_disposable_git_owner(git_directory: Path) -> None:
    """GitHub's elevated token creates Git children under Administrators."""
    account = subprocess.run(
        ["whoami.exe"], check=True, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(
        ["icacls.exe", str(git_directory), "/setowner", account, "/T"],
        check=True,
        capture_output=True,
    )


@unittest.skipUnless(sys.platform == "win32", "native Windows regression")
class WindowsChecks(unittest.TestCase):
    def test_project_memory_wal_sidecars_fail_closed_and_delete_exactly(self):
        from opensocrates.project_memory.registry import ProjectRegistry
        from opensocrates.project_memory.service import handle_memory

        with tempfile.TemporaryDirectory(prefix="OpenSocrates WAL lifecycle ") as name:
            parent = Path(name)
            source = parent / "plain-text"
            self.assertTrue(create_owner_only_directory(source))
            registry = ProjectRegistry(parent / "owned-data")
            policy = {
                "root": str(source),
                "apply": False,
                "mode": "read_write",
                "capture_policy": "milestones",
                "excluded_paths": [],
            }

            def call(operation, payload, project_id=None, workspace_id=None):
                return handle_memory(
                    {
                        "schema": "opensocrates.project-memory.request/1.0.0",
                        "operation": operation,
                        "request_id": str(uuid4()),
                        "project_id": project_id,
                        "workspace_id": workspace_id,
                        "task_id": None,
                        "payload": payload,
                    },
                    registry=registry,
                )

            preview = call("init", policy)
            self.assertEqual(preview["status"], "ok", preview)
            policy.update(
                {
                    "apply": True,
                    "disclosure_digest": preview["result"]["disclosure_digest"],
                    "authorization_basis": "fixture:windows-wal",
                    "authorization_attribution": "operator_declared",
                    "idempotency_key": str(uuid4()),
                }
            )
            enrolled = call("init", policy)
            self.assertEqual(enrolled["status"], "ok", enrolled)
            project_id = enrolled["result"]["project_id"]
            workspace_id = enrolled["result"]["workspace_id"]
            directory = registry.project_dir(project_id)
            for suffix in ("-wal", "-shm"):
                descriptor = create_owner_only_file(
                    directory / f"memory.sqlite3{suffix}", flags=os.O_RDWR
                )
                os.close(descriptor)
            status = call("status", {}, project_id, workspace_id)
            self.assertEqual(status["status"], "unavailable", status)
            self.assertIn("unsupported_journal_mode", status["limitations"])
            deleted = call(
                "delete",
                {
                    "intent": "delete_project",
                    "expected_policy_version": 1,
                    "idempotency_key": str(uuid4()),
                },
                project_id,
            )
            self.assertEqual(deleted["status"], "ok", deleted)
            self.assertFalse(directory.exists())

    def test_project_memory_linked_worktree_continuity(self):
        from opensocrates.project_memory.registry import ProjectRegistry
        from opensocrates.project_memory.service import handle_memory

        with tempfile.TemporaryDirectory(prefix="OpenSocrates linked worktree ") as name:
            parent = Path(name)
            first = parent / "first"
            second = parent / "second"
            self.assertTrue(create_owner_only_directory(first))
            self.assertTrue(create_owner_only_directory(first / ".git"))
            self.assertTrue(create_owner_only_directory(second))
            subprocess.run(["git", "init", "-q", str(first)], check=True, capture_output=True)
            (first / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(first), "add", "helper.py"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(first),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(first), "worktree", "add", "-q", "--detach", str(second)],
                check=True,
                capture_output=True,
            )
            _set_disposable_git_owner(first / ".git")
            registry = ProjectRegistry(parent / "owned-data")
            policy = {"mode": "read_write", "capture_policy": "milestones", "excluded_paths": []}

            def request(operation, payload, project_id=None, workspace_id=None, task_id=None):
                return handle_memory(
                    {
                        "schema": "opensocrates.project-memory.request/1.0.0",
                        "operation": operation,
                        "request_id": str(uuid4()),
                        "project_id": project_id,
                        "workspace_id": workspace_id,
                        "task_id": task_id,
                        "payload": payload,
                    },
                    registry=registry,
                )

            def enroll(root, project_id=None, expected_policy_version=None):
                payload = {"root": str(root), "apply": False, **policy}
                if expected_policy_version is not None:
                    payload["expected_policy_version"] = expected_policy_version
                preview = request("init", payload, project_id)
                self.assertEqual(preview["status"], "ok", preview)
                payload.update(
                    {
                        "apply": True,
                        "disclosure_digest": preview["result"]["disclosure_digest"],
                        "authorization_basis": "fixture:linked-worktree",
                        "authorization_attribution": "operator_declared",
                        "idempotency_key": str(uuid4()),
                    }
                )
                result = request("init", payload, project_id)
                self.assertEqual(result["status"], "ok", result)
                return result["result"]

            original = enroll(first)
            project_id = original["project_id"]
            first_id = original["workspace_id"]
            joined = enroll(second, project_id, original["policy_version"])
            second_id = joined["workspace_id"]
            self.assertEqual(joined["project_id"], project_id)
            self.assertNotEqual(second_id, first_id)
            task_id = str(uuid4())
            decision = request(
                "record",
                {
                    "idempotency_key": str(uuid4()),
                    "expected_record_version": 0,
                    "kind": "decision",
                    "scope": {"level": "project"},
                    "summary": "Keep the shared helper compatible.",
                    "origin": {
                        "producer_kind": "agent",
                        "source_reference": None,
                        "attestation": "agent_reported",
                    },
                    "support": "agent_reported",
                    "source_refs": [],
                    "revalidation": {
                        "dependency_paths": [],
                        "negative_claim": False,
                        "on_change": "not_applicable",
                    },
                },
                project_id,
                first_id,
            )
            self.assertEqual(decision["status"], "ok", decision)
            record_id = decision["result"]["record"]["record_id"]
            accepted = request(
                "accept",
                {
                    "record_id": record_id,
                    "expected_record_version": 1,
                    "idempotency_key": str(uuid4()),
                    "acceptance_basis": "fixture:accepted-intent",
                    "acceptance_attribution": "operator_declared",
                },
                project_id,
                first_id,
            )
            self.assertEqual(accepted["status"], "ok", accepted)
            observation = request(
                "observe",
                {"path": "helper.py", "idempotency_key": str(uuid4())},
                project_id,
                first_id,
            )
            self.assertEqual(observation["status"], "ok", observation)
            checkpoint = request(
                "checkpoint",
                {
                    "idempotency_key": str(uuid4()),
                    "expected_checkpoint_version": 0,
                    "objective": "Update helper",
                    "constraints": ["Keep callers compatible"],
                    "completion_conditions": ["Relevant tests pass"],
                    "completed_actions": [],
                    "remaining_actions": ["Inspect callers"],
                    "next_action": "Inspect callers",
                    "blockers": [],
                    "decision_refs": [record_id],
                    "source_refs": [],
                    "snapshot_id": None,
                    "conflict_ids": [],
                    "pending_effects": [],
                    "parent_checkpoint_id": None,
                },
                project_id,
                first_id,
                task_id,
            )
            self.assertEqual(checkpoint["status"], "ok", checkpoint)
            first_pack = request(
                "recall",
                {"need": "shared helper", "budget_bytes": 8192},
                project_id,
                first_id,
                task_id,
            )
            second_pack = request(
                "recall",
                {"need": "shared helper", "budget_bytes": 8192},
                project_id,
                second_id,
                task_id,
            )
            self.assertEqual(first_pack["status"], "ok", first_pack)
            self.assertEqual(second_pack["status"], "ok", second_pack)
            self.assertEqual(
                first_pack["result"]["checkpoint_reference"],
                checkpoint["result"]["record"]["record_id"],
            )
            self.assertEqual(second_pack["result"]["decisions"][0]["record_id"], record_id)
            self.assertEqual(second_pack["result"]["decisions"][0]["freshness"], "not_applicable")
            self.assertIsNone(second_pack["result"]["checkpoint_reference"])
            self.assertEqual(second_pack["result"]["source_evidence"], [])

    def test_project_memory_git_ref_dirty_and_untracked_freshness(self):
        from opensocrates.project_memory import sources

        with tempfile.TemporaryDirectory(prefix="OpenSocrates git freshness ") as name:
            root = Path(name) / "repo"
            self.assertTrue(create_owner_only_directory(root))
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            helper = root / "helper.py"
            helper.write_text("def helper():\n    return 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "helper.py"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
                capture_output=True,
            )
            first = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            subprocess.run(
                ["git", "-C", str(root), "switch", "-q", "-c", "fixture-next"],
                check=True,
                capture_output=True,
            )
            branch = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            ref_change = sources.revalidate_snapshot(first, branch)
            self.assertEqual(first["head_oid"], branch["head_oid"])
            self.assertEqual(ref_change["freshness"], "stale")
            self.assertTrue(ref_change["changes"]["ref_changed"])

            helper.write_text("def helper():\n    return 2\n", encoding="utf-8")
            unstaged = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            edit_change = sources.revalidate_snapshot(branch, unstaged)
            self.assertEqual(edit_change["freshness"], "stale")
            self.assertIn("helper.py", edit_change["changes"]["modified"])
            subprocess.run(["git", "-C", str(root), "add", "helper.py"], check=True)
            staged = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            staged_change = sources.revalidate_snapshot(unstaged, staged)
            self.assertEqual(staged_change["freshness"], "stale")
            self.assertTrue(staged_change["changes"]["dirty_changed"])
            (root / "new_caller.py").write_text(
                "from helper import helper\nhelper()\n", encoding="utf-8"
            )
            untracked = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            caller_change = sources.revalidate_snapshot(staged, untracked)
            self.assertEqual(caller_change["freshness"], "stale")
            self.assertIn("new_caller.py", caller_change["changes"]["added"])
            self.assertEqual(first["head_oid"], untracked["head_oid"])
            subprocess.run(["git", "-C", str(root), "add", "new_caller.py"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "changed",
                ],
                check=True,
                capture_output=True,
            )
            committed = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            head_change = sources.revalidate_snapshot(untracked, committed)
            self.assertEqual(head_change["freshness"], "stale")
            self.assertTrue(head_change["changes"]["head_changed"])

    def test_project_memory_rejects_copied_reparse_relocated_and_replaced_roots(self):
        from opensocrates.project_memory.registry import ProjectRegistry, RegistryError

        with tempfile.TemporaryDirectory(prefix="OpenSocrates root identity ") as name:
            parent = Path(name)
            first = parent / "first"
            second = parent / "linked"
            self.assertTrue(create_owner_only_directory(first))
            self.assertTrue(create_owner_only_directory(first / ".git"))
            self.assertTrue(create_owner_only_directory(second))
            subprocess.run(["git", "init", "-q", str(first)], check=True, capture_output=True)
            (first / "guide.md").write_text("Keep access.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(first), "add", "guide.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(first),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(first), "worktree", "add", "-q", "--detach", str(second)],
                check=True,
                capture_output=True,
            )
            _set_disposable_git_owner(first / ".git")
            registry = ProjectRegistry(parent / "owned-data")
            policy = {"mode": "read_write", "capture_policy": "milestones", "excluded_paths": []}
            preview = registry.preview(str(first), policy)
            enrolled = registry.enroll(
                str(first),
                policy,
                preview["disclosure_digest"],
                "fixture:root-identity",
                "operator_declared",
                idempotency_key=str(uuid4()),
            )
            project_id = enrolled["project_id"]
            workspace_id = enrolled["workspace_id"]

            copied = parent / "copied"
            shutil.copytree(second, copied)
            with self.assertRaises(RegistryError):
                registry.preview(
                    str(copied),
                    policy,
                    expected_policy_version=1,
                    target_project_id=project_id,
                )

            junction = parent / "junction"
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "New-Item -ItemType Junction -Path $env:TEST_JUNCTION -Target $env:TEST_TARGET | Out-Null",
                ],
                env={**os.environ, "TEST_JUNCTION": str(junction), "TEST_TARGET": str(second)},
                check=True,
                capture_output=True,
            )
            with self.assertRaises((OSError, ValueError)):
                registry.preview(str(junction), policy)

            relocated = parent / "relocated"
            first.rename(relocated)
            with self.assertRaises((OSError, ValueError)):
                registry.get(project_id, workspace_id)
            self.assertTrue(create_owner_only_directory(first))
            with self.assertRaises((OSError, ValueError)):
                registry.get(project_id, workspace_id)

    def test_project_memory_git_inventory_and_untracked_caller(self):
        from opensocrates.project_memory import sources
        from opensocrates.project_memory.registry import ProjectRegistry

        with tempfile.TemporaryDirectory(prefix="OpenSocrates git source ") as name:
            parent = Path(name)
            root = parent / "repo"
            self.assertTrue(create_owner_only_directory(root))
            self.assertTrue(create_owner_only_directory(root / ".git"))
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "helper.py"], check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
                capture_output=True,
            )
            policy = {"mode": "read_write", "capture_policy": "milestones", "excluded_paths": []}
            preview = ProjectRegistry(parent / "data").preview(str(root), policy)
            self.assertEqual(preview["disclosure"]["workspace_kind"], "git_worktree")
            first = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            self.assertTrue(first["coverage"]["complete_for_scope"])
            self.assertIn("helper.py", first["files"])
            (root / "new_caller.py").write_text(
                "from helper import helper\nhelper()\n", encoding="utf-8"
            )
            changed = sources.capture_snapshot(root, "git_worktree", "project", "workspace")
            self.assertEqual(sources.revalidate_snapshot(first, changed)["freshness"], "stale")
            self.assertIn("new_caller.py", changed["files"])

    def test_project_memory_source_root_and_reparse(self):
        from opensocrates import windows_security
        from opensocrates.project_memory import sources

        with tempfile.TemporaryDirectory(prefix="OpenSocrates source 한글 ") as name:
            parent = Path(name)
            root = parent / "enrolled"
            nested = root / "notes"
            self.assertTrue(create_owner_only_directory(root))
            self.assertTrue(create_owner_only_directory(nested))
            (nested / "brief.md").write_text("in-scope marker", encoding="utf-8")
            external = parent / "external"
            external.mkdir()
            (external / "private.md").write_text("outside-root canary", encoding="utf-8")
            with windows_security.open_source_root(root) as bound:
                self.assertTrue(windows_security.source_root_owner_is_current(bound))
                self.assertEqual(
                    windows_security.read_source_file(bound, "notes/brief.md", 1024)[0],
                    b"in-scope marker",
                )
                real_open = windows_security._open_source_path

                def try_replacing_parent(path: Path, *, directory: bool) -> int:
                    if path == nested / "brief.md":
                        with self.assertRaises(PermissionError):
                            nested.rename(root / "moved-notes")
                    return real_open(path, directory=directory)

                with mock.patch.object(
                    windows_security, "_open_source_path", side_effect=try_replacing_parent
                ):
                    self.assertEqual(
                        windows_security.read_source_file(bound, "notes/brief.md", 1024)[0],
                        b"in-scope marker",
                    )
                with self.assertRaises(ValueError):
                    windows_security.validate_source_relative("notes/../private.md")
                with self.assertRaises(ValueError):
                    windows_security.validate_source_relative("notes/file.md:stream")
                with self.assertRaises(PermissionError):
                    root.rename(parent / "moved-enrolled")

            first = sources.capture_snapshot(root, "directory", "project", "workspace")
            self.assertTrue(first["coverage"]["complete_for_scope"])
            self.assertEqual(list(first["files"]), ["notes/brief.md"])
            self.assertEqual(
                sources.lexical_matches(root, first, "marker")[0][0]["path"], "notes/brief.md"
            )
            self.assertNotIn("in-scope marker", str(first))

            junction = root / "outside"
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "New-Item -ItemType Junction -Path $env:TEST_JUNCTION -Target $env:TEST_TARGET | Out-Null",
                ],
                env={**os.environ, "TEST_JUNCTION": str(junction), "TEST_TARGET": str(external)},
                check=True,
                capture_output=True,
            )
            linked = sources.capture_snapshot(root, "directory", "project", "workspace")
            self.assertNotIn("outside/private.md", linked["files"])
            self.assertFalse(linked["coverage"]["complete_for_scope"])
            self.assertNotIn("outside-root canary", str(linked))
            with self.assertRaises((OSError, ValueError)):
                windows_security.open_source_root(junction)
            with windows_security.open_source_root(root) as bound:
                self.assertEqual(
                    windows_security.read_source_file(bound, "outside/private.md", 1024)[1],
                    "unsafe_path",
                )

    def test_acl_private_and_binary_atomic_io(self):
        with tempfile.TemporaryDirectory(prefix="OpenSocrates 한글 space ") as name:
            root = Path(name) / "private-root"
            self.assertTrue(create_owner_only_directory(root))
            secure_mode(root, directory=True)
            self.assertTrue(check_permissions(root, directory=True).write_allowed)
            path = root / "한글 state.json"
            value = '{"value":"한글\u001a"}\n'.encode("utf-8")
            atomic_replace_bytes(path, value)
            secure_mode(path, directory=False)
            self.assertTrue(check_permissions(path, directory=False).write_allowed)
            self.assertEqual(read_bytes(path, max_bytes=1024), value)
            atomic_replace_bytes(path, b"first\n")
            append_fsync(path, b"second\n", max_bytes=1024)
            self.assertEqual(path.read_bytes(), b"first\nsecond\n")
            fresh_append = root / "fresh append.jsonl"
            append_fsync(
                fresh_append,
                '{"value":"한글"}\n'.encode("utf-8"),
                max_bytes=1024,
            )
            self.assertEqual(fresh_append.read_text(encoding="utf-8"), '{"value":"한글"}\n')
            self.assertTrue(check_permissions(fresh_append, directory=False).write_allowed)
            short_path = root / "x"
            atomic_replace_bytes(short_path, b"one")
            atomic_replace_bytes(short_path, b"two")
            self.assertEqual(short_path.read_bytes(), b"two")

    def test_long_private_artifact_path(self):
        from check_selector import _METHODS, _REVISION, _projections
        from opensocrates.content.injection import assemble_canonical_instruction
        from opensocrates.selector.artifacts import InstructionFileStore

        with tempfile.TemporaryDirectory(prefix="OpenSocrates long 한글 space ") as name:
            directory = Path(name) / ("nested" * 15)
            self.assertTrue(create_owner_only_directory(directory))
            store = InstructionFileStore(installation_key=b"L" * 32, directory=directory)
            assembled = assemble_canonical_instruction(
                _projections(), (_METHODS[0],), "en", expected_content_revision=_REVISION
            )
            artifact = store.create("long-session", "long-turn", assembled)
            self.assertGreater(len(str(artifact.path)), 260)
            self.assertTrue(artifact.path.read_bytes())
            self.assertTrue(check_permissions(artifact.path, directory=False).write_allowed)
            self.assertGreaterEqual(store.delete_session("long-session"), 1)

    def test_broad_acl_is_rejected(self):
        from opensocrates.persistence.windows_acl import inspect_acl

        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "private-root"
            self.assertTrue(create_owner_only_directory(root))
            _grant_everyone_read(root)
            self.assertEqual(inspect_acl(root), (True, False))
            self.assertFalse(check_permissions(root, directory=True).write_allowed)

    def test_junction_is_not_a_private_directory(self):
        from opensocrates import windows_security

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            target = root / "target"
            target.mkdir()
            junction = root / "junction"
            environment = {**os.environ, "TEST_JUNCTION": str(junction), "TEST_TARGET": str(target)}
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "New-Item -ItemType Junction -Path $env:TEST_JUNCTION -Target $env:TEST_TARGET | Out-Null",
                ],
                env=environment,
                check=True,
                capture_output=True,
            )
            self.assertFalse(check_permissions(junction, directory=True).write_allowed)
            with self.assertRaises(PermissionError):
                secure_mode(junction, directory=True)
            with self.assertRaises(FileExistsError):
                windows_security.create_private_directory(junction)
            self.assertTrue(target.is_dir())

    def test_create_time_acl_is_exclusive_and_existing_paths_are_immutable(self):
        from opensocrates import windows_security

        self.assertNotIn("newly_created", inspect.signature(windows_security.secure_acl).parameters)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "private-root"
            self.assertTrue(create_owner_only_directory(root))
            path = root / "existing.bin"
            descriptor = create_owner_only_file(path, flags=os.O_RDWR)
            os.write(descriptor, b"preserve")
            os.close(descriptor)
            before_owner = windows_security._path_owner_sid(path)
            before_acl = windows_security.inspect_acl(path)
            with self.assertRaises(FileExistsError):
                windows_security.create_private_file(path, flags=os.O_RDWR)
            self.assertEqual(path.read_bytes(), b"preserve")
            self.assertEqual(windows_security._path_owner_sid(path), before_owner)
            self.assertEqual(windows_security.inspect_acl(path), before_acl)
            with self.assertRaises(TypeError):
                windows_security.CreatedPrivateTempfile(
                    descriptor=-1,
                    path=str(path),
                    parent_handle=-1,
                    parent_path=root,
                    file_identity=(0, 0, 0),
                    issuer=object(),
                )
            with self.assertRaises(PermissionError):
                windows_security.replace_created_file_descriptor(object(), root / "forged.bin")
            self.assertEqual(path.read_bytes(), b"preserve")
            with mock.patch.object(windows_security, "_dacl_is_protected", return_value=False):
                self.assertEqual(windows_security.inspect_acl(path), (True, False))

    def test_explicit_owner_creation_and_hosted_default_owner_diagnostic(self):
        from opensocrates import windows_security

        with tempfile.TemporaryDirectory() as name:
            inherited_root = Path(name)
            inherited_owner = windows_security._path_owner_sid(inherited_root)
            default_owner = windows_security.default_owner_sid()
            self.assertEqual(inherited_owner, default_owner)
            inherited_categories = windows_security._diagnostic_categories(inherited_root)
            if inherited_owner != windows_security.current_sid():
                with (
                    mock.patch.object(
                        windows_security,
                        "_private_descriptor",
                        wraps=windows_security._private_descriptor,
                    ) as descriptor_builder,
                    self.assertRaises(PermissionError),
                ):
                    windows_security.secure_acl(inherited_root, directory=True)
                descriptor_builder.assert_not_called()
            private_root = inherited_root / "private-root"
            with mock.patch.object(
                windows_security,
                "default_owner_sid",
                return_value=windows_security._ADMINISTRATORS_SID,
            ) as default_owner_probe:
                self.assertTrue(create_owner_only_directory(private_root))
            default_owner_probe.assert_not_called()
            self.assertEqual(
                windows_security._path_owner_sid(private_root), windows_security.current_sid()
            )
            self.assertEqual(windows_security.inspect_acl(private_root), (True, True))
            final_categories = windows_security._diagnostic_categories(private_root)
            print(
                "windows-acl-diagnostic:"
                + json.dumps(
                    {
                        "token_user_matches_current_sid": windows_security._token_sid(
                            windows_security._TOKEN_USER
                        )
                        == windows_security.current_sid(),
                        "token_owner_kind": windows_security._sid_category(default_owner),
                        "temporary_directory_owner_kind": inherited_categories["owner_kind"],
                        "temporary_owner_matches_token_owner": inherited_owner == default_owner,
                        "temporary_directory_reparse": inherited_categories["reparse"],
                        "temporary_dacl_principal_kinds": inherited_categories[
                            "dacl_principal_kinds"
                        ],
                        "normalization_attempted": False,
                        "normalization_result": "not-used",
                        "final_owner_kind": final_categories["owner_kind"],
                        "final_dacl_protected": final_categories["dacl_protected"],
                        "final_acl_private": windows_security.inspect_acl(private_root)
                        == (True, True),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            if default_owner == windows_security._ADMINISTRATORS_SID:
                self.assertEqual(inherited_owner, windows_security._ADMINISTRATORS_SID)

    def test_foreign_owner_and_path_replacement_remain_fail_closed(self):
        from opensocrates import windows_security

        with tempfile.TemporaryDirectory() as name:
            parent = Path(name)
            root = parent / "original"
            self.assertTrue(create_owner_only_directory(root))
            _grant_everyone_read(root)

            for owner_kind in ("administrators", "system", "other-user", "arbitrary-group"):
                with (
                    self.subTest(owner_kind=owner_kind),
                    mock.patch.object(
                        windows_security, "_inspect_handle", return_value=(False, False)
                    ),
                    mock.patch.object(
                        windows_security,
                        "_private_descriptor",
                        wraps=windows_security._private_descriptor,
                    ) as descriptor_builder,
                    self.assertRaises(PermissionError),
                ):
                    windows_security.secure_acl(root, directory=True)
                descriptor_builder.assert_not_called()

            moved = parent / "opened-object"
            real_descriptor = windows_security._private_descriptor

            def replace_path(*, directory: bool, include_owner: bool):
                root.rename(moved)
                root.mkdir()
                _grant_everyone_read(root)
                return real_descriptor(directory=directory, include_owner=include_owner)

            with mock.patch.object(
                windows_security, "_private_descriptor", side_effect=replace_path
            ):
                windows_security.secure_acl(root, directory=True)
            self.assertEqual(windows_security.inspect_acl(moved), (True, True))
            self.assertFalse(windows_security.inspect_acl(root)[1])
            self.assertFalse(check_permissions(root, directory=True).write_allowed)

            junction_path = parent / "junction-transition"
            opened_path = parent / "junction-opened-object"
            junction_target = parent / "junction-target"
            self.assertTrue(create_owner_only_directory(junction_path))
            self.assertTrue(create_owner_only_directory(junction_target))
            _grant_everyone_read(junction_path)
            _grant_everyone_read(junction_target)

            def insert_junction(*, directory: bool, include_owner: bool):
                junction_path.rename(opened_path)
                environment = {
                    **os.environ,
                    "TEST_JUNCTION": str(junction_path),
                    "TEST_TARGET": str(junction_target),
                }
                subprocess.run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "New-Item -ItemType Junction -Path $env:TEST_JUNCTION -Target $env:TEST_TARGET | Out-Null",
                    ],
                    env=environment,
                    check=True,
                    capture_output=True,
                )
                return real_descriptor(directory=directory, include_owner=include_owner)

            with mock.patch.object(
                windows_security, "_private_descriptor", side_effect=insert_junction
            ):
                windows_security.secure_acl(junction_path, directory=True)
            self.assertEqual(windows_security.inspect_acl(opened_path), (True, True))
            self.assertEqual(windows_security.inspect_acl(junction_path), (False, False))
            self.assertEqual(windows_security.inspect_acl(junction_target), (True, False))

    def test_failed_new_file_paths_use_handle_bound_cleanup(self):
        from check_selector import _METHODS, _REVISION, _projections
        from opensocrates import windows_security
        from opensocrates.content.injection import assemble_canonical_instruction
        from opensocrates.persistence import atomic, locks, turn_store
        from opensocrates.persistence.paths import DataRootLayout
        from opensocrates.selector import artifacts as artifact_module
        from opensocrates.selector.artifacts import InstructionFileStore

        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "private-root"
            self.assertTrue(create_owner_only_directory(root))

            path = root / "created.bin"
            moved = root / "created-moved.bin"

            def replace_created_handle(_handle: int):
                path.rename(moved)
                path.write_bytes(b"replacement")
                return False, False

            with (
                mock.patch.object(
                    windows_security, "_inspect_handle", side_effect=replace_created_handle
                ),
                self.assertRaises(PermissionError),
            ):
                windows_security.create_private_file(path, flags=os.O_RDWR, share_delete=True)
            self.assertEqual(path.read_bytes(), b"replacement")
            self.assertFalse(moved.exists())

            atomic_target = root / "atomic-swap.json"
            atomic_moved = root / "atomic-original.tmp"
            replacement_blocked = False
            real_replace = atomic.replace_created_file

            def replace_atomic_source(created, destination: Path):
                nonlocal replacement_blocked
                try:
                    created.path.rename(atomic_moved)
                except PermissionError:
                    replacement_blocked = True
                else:
                    created.path.write_bytes(b"replacement")
                real_replace(created, destination)

            with mock.patch.object(
                atomic, "replace_created_file", side_effect=replace_atomic_source
            ):
                atomic.atomic_replace_bytes(atomic_target, b"intended")
            self.assertTrue(replacement_blocked)
            self.assertEqual(atomic_target.read_bytes(), b"intended")
            self.assertFalse(atomic_moved.exists())
            self.assertFalse(tuple(root.glob(".atomic-swap.json.*.tmp")))

            race_root = Path(name) / "atomic-parent-race"
            moved_race_root = Path(name) / "atomic-parent-original"
            self.assertTrue(create_owner_only_directory(race_root))
            real_create_tempfile = atomic.create_owner_only_tempfile

            def replace_atomic_parent(**kwargs: object):
                race_root.rename(moved_race_root)
                race_root.mkdir()
                _grant_everyone_read(race_root)
                return real_create_tempfile(**kwargs)

            raced_target = race_root / "state.json"
            with (
                mock.patch.object(
                    atomic,
                    "create_owner_only_tempfile",
                    side_effect=replace_atomic_parent,
                ),
                self.assertRaises(atomic.AtomicWriteError),
            ):
                atomic.atomic_replace_bytes(raced_target, b"must-not-publish")
            self.assertFalse(raced_target.exists())
            self.assertFalse(tuple(race_root.glob(".state.json.*.tmp")))
            self.assertFalse(windows_security.inspect_acl(race_root)[1])
            self.assertFalse(check_permissions(race_root, directory=True).write_allowed)
            self.assertEqual(windows_security.inspect_acl(moved_race_root), (True, True))

            bound_root = Path(name) / "atomic-parent-bound"
            bound_moved_root = Path(name) / "atomic-parent-bound-moved"
            self.assertTrue(create_owner_only_directory(bound_root))
            bound_target = bound_root / "state.json"
            parent_replacement_blocked = False
            real_relative_create = windows_security._create_private_file_at

            def attempt_private_parent_replacement(
                parent_handle: int, filename: str, *, flags: int
            ):
                nonlocal parent_replacement_blocked
                try:
                    bound_root.rename(bound_moved_root)
                except PermissionError:
                    parent_replacement_blocked = True
                else:
                    create_owner_only_directory(bound_root)
                return real_relative_create(parent_handle, filename, flags=flags)

            with mock.patch.object(
                windows_security,
                "_create_private_file_at",
                side_effect=attempt_private_parent_replacement,
            ):
                atomic.atomic_replace_bytes(bound_target, b"parent-bound")
            self.assertTrue(parent_replacement_blocked)
            self.assertEqual(bound_target.read_bytes(), b"parent-bound")
            self.assertFalse(bound_moved_root.exists())
            self.assertFalse(tuple(bound_root.glob(".state.json.*.tmp")))

            append_path = root / "append.jsonl"
            with (
                mock.patch.object(atomic.os, "fsync", side_effect=OSError("synthetic")),
                self.assertRaises(atomic.AtomicWriteError),
            ):
                atomic.append_fsync(append_path, b"{}\n", max_bytes=1024)
            self.assertFalse(append_path.exists())

            replace_path = root / "atomic.json"
            with (
                mock.patch.object(atomic.os, "fsync", side_effect=OSError("synthetic")),
                self.assertRaises(atomic.AtomicWriteError),
            ):
                atomic.atomic_replace_bytes(replace_path, b"{}\n")
            self.assertFalse(replace_path.exists())
            self.assertFalse(tuple(root.glob(".atomic.json.*.tmp")))

            lock_path = root / "state.lock"
            with (
                mock.patch.object(
                    locks,
                    "check_permissions",
                    return_value=mock.Mock(write_allowed=False),
                ),
                self.assertRaises(locks.LockError),
            ):
                locks.FileLock(lock_path).acquire()
            self.assertFalse(lock_path.exists())

            key_path = root / "installation.key"
            with (
                mock.patch.object(turn_store.os, "write", side_effect=OSError("synthetic")),
                self.assertRaises(turn_store.TurnStoreError),
            ):
                turn_store._InstallationKey(
                    DataRootLayout.from_root(root),
                    turn_store.PermissionManager(),
                    create=True,
                )
            self.assertFalse(key_path.exists())

            assembled = assemble_canonical_instruction(
                _projections(),
                (_METHODS[0],),
                "en",
                expected_content_revision=_REVISION,
            )
            artifact_root = root / "artifact-failure"
            store = InstructionFileStore(installation_key=b"F" * 32, directory=artifact_root)
            with (
                mock.patch.object(artifact_module.os, "fsync", side_effect=OSError("synthetic")),
                self.assertRaises(OSError),
            ):
                store.create("failed-session", "failed-turn", assembled)
            self.assertFalse(tuple(artifact_root.rglob("instruction-*.md")))

            receipt_store = InstructionFileStore(
                installation_key=b"R" * 32, directory=root / "receipt-failure"
            )
            artifact = receipt_store.create("receipt-session", "receipt-turn", assembled)
            with (
                mock.patch.object(artifact_module.os, "fsync", side_effect=OSError("synthetic")),
                self.assertRaises(OSError),
            ):
                receipt_store._write_receipt(artifact, {})
            self.assertFalse(tuple(artifact.path.parent.glob(".grounding-receipt-*")))

    def test_new_directory_verification_blocks_replacement_and_cleans_failure(self):
        from opensocrates import windows_security

        with tempfile.TemporaryDirectory() as name:
            parent = Path(name)
            path = parent / "created-directory"
            moved = parent / "created-directory-moved"

            def attempt_replace_created_handle(_handle: int):
                path.rename(moved)
                path.mkdir()
                (path / "marker").write_bytes(b"replacement")
                return False, False

            with (
                mock.patch.object(
                    windows_security,
                    "_inspect_handle",
                    side_effect=attempt_replace_created_handle,
                ),
                self.assertRaises(PermissionError),
            ):
                windows_security.create_private_directory(path)
            self.assertFalse(path.exists())
            self.assertFalse(moved.exists())

            existing = parent / "existing"
            self.assertTrue(create_owner_only_directory(existing))
            marker = existing / "marker"
            marker.write_bytes(b"preserve")
            self.assertFalse(create_owner_only_directory(existing))
            self.assertEqual(marker.read_bytes(), b"preserve")

    def test_lock_excludes_second_process(self):
        from opensocrates.persistence.locks import FileLock

        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "private-root"
            self.assertTrue(create_owner_only_directory(root))
            lock = root / "state.lock"
            code = "from pathlib import Path; from opensocrates.persistence.locks import FileLock; FileLock(Path(__import__('sys').argv[1])).acquire()"
            with FileLock(lock):
                moved = root / "renamed.lock"
                with self.assertRaises(PermissionError):
                    lock.rename(moved)
                self.assertFalse(moved.exists())
                child = subprocess.run(
                    [sys.executable, "-c", code, str(lock)], capture_output=True, timeout=10
                )
                self.assertNotEqual(child.returncode, 0)
                self.assertIn(b"LockTimeoutError", child.stderr)
            child = subprocess.run(
                [sys.executable, "-c", code, str(lock)], capture_output=True, timeout=10
            )
            self.assertEqual(child.returncode, 0, child.stderr)

    def test_artifact_cleanup_preserves_junction_targets(self):
        from opensocrates.selector.artifacts import InstructionFileStore

        for operation in ("session", "turn", "superseded", "sweep"):
            for junction_level in ("root", "session", "turn"):
                with self.subTest(operation=operation, junction_level=junction_level):
                    with tempfile.TemporaryDirectory() as name:
                        parent = Path(name)
                        root = parent / "private"
                        external = parent / "external"
                        self.assertTrue(create_owner_only_directory(root))
                        self.assertTrue(create_owner_only_directory(external))
                        store = InstructionFileStore(installation_key=b"J" * 32, directory=root)
                        root = store.directory
                        session = store._session_directory("session", root=root)
                        turn = store._turn_directory("session", "old", root=root)
                        self.assertTrue(create_owner_only_directory(session))
                        self.assertTrue(create_owner_only_directory(turn))
                        junction = {"root": root, "session": session, "turn": turn}[junction_level]
                        # Mirror the expected suffix so every cleanup entry point
                        # would reach the external file if it followed the junction.
                        target = external / turn.relative_to(junction)
                        create_owner_only_directory(target, parents=True)
                        sentinel = target / "instruction-sentinel.md"
                        descriptor = create_owner_only_file(sentinel, flags=os.O_WRONLY)
                        os.write(descriptor, b"unrelated fixture")
                        os.close(descriptor)
                        os.utime(sentinel, (1, 1))
                        junction.rename(Path(str(junction) + "-saved"))
                        subprocess.run(
                            [
                                "powershell.exe",
                                "-NoProfile",
                                "-NonInteractive",
                                "-Command",
                                "New-Item -ItemType Junction -Path $env:TEST_JUNCTION -Target $env:TEST_TARGET | Out-Null",
                            ],
                            env={
                                **os.environ,
                                "TEST_JUNCTION": str(junction),
                                "TEST_TARGET": str(external),
                            },
                            check=True,
                            capture_output=True,
                        )
                        self.assertTrue(junction.lstat().st_file_attributes & 0x400)
                        if operation == "session":
                            store.delete_session("session")
                        elif operation == "turn":
                            store.delete_turn("session", "old")
                        elif operation == "superseded":
                            store.delete_superseded_turns("session", "active")
                        else:
                            store.sweep_expired()
                        self.assertEqual(sentinel.read_bytes(), b"unrelated fixture")

    def test_artifact_cleanup_pins_objects_and_preserves_changed_names(self):
        from opensocrates import windows_security
        from opensocrates.selector.artifacts import InstructionFileStore

        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "private"
            self.assertTrue(create_owner_only_directory(root))
            store = InstructionFileStore(installation_key=b"K" * 32, directory=root)
            root = store.directory
            session = store._session_directory("session", root=root)
            self.assertTrue(create_owner_only_directory(session))
            path = session / "instruction-sentinel.md"
            descriptor = create_owner_only_file(path, flags=os.O_WRONLY)
            os.write(descriptor, b"original")
            os.close(descriptor)
            real_delete = windows_security._mark_handle_for_deletion
            attempts = []

            def attempt_replacement(handle):
                if path.exists():
                    for candidate in (path, session, root):
                        with self.assertRaises(PermissionError):
                            candidate.rename(Path(str(candidate) + "-moved"))
                        attempts.append(candidate.name)
                real_delete(handle)

            with mock.patch.object(
                windows_security, "_mark_handle_for_deletion", side_effect=attempt_replacement
            ):
                self.assertGreaterEqual(store.delete_session("session"), 2)
            self.assertEqual(len(attempts), 3)
            self.assertFalse(path.exists())
            self.assertFalse(root.exists())

            self.assertTrue(create_owner_only_directory(root))
            self.assertTrue(create_owner_only_directory(session))
            descriptor = create_owner_only_file(path, flags=os.O_WRONLY)
            os.close(descriptor)
            moved = session / "original-saved.md"
            real_open = windows_security._open_path_handle

            def replace_before_open(candidate, *, access):
                if candidate == path:
                    path.rename(moved)
                    descriptor = create_owner_only_file(path, flags=os.O_WRONLY)
                    os.write(descriptor, b"replacement")
                    os.close(descriptor)
                return real_open(candidate, access=access)

            with mock.patch.object(
                windows_security, "_open_path_handle", side_effect=replace_before_open
            ):
                self.assertEqual(store._remove_tree(path, root=root), 0)
            self.assertTrue(moved.exists())
            self.assertEqual(path.read_bytes(), b"replacement")

    def test_zip_rejects_windows_aliases_before_extract(self):
        import hashlib

        version = (ROOT / "VERSION").read_text().strip()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for entries in [
                ("../escape",),
                ("file:stream",),
                ("NUL.txt",),
                ("file.",),
                ("A.txt", "a.txt"),
            ]:
                archive = root / f"opensocrates-{version}-codex-plugin-windows-x64.zip"
                with zipfile.ZipFile(archive, "w") as bundle:
                    for entry in entries:
                        bundle.writestr(entry, "synthetic")
                checksum = archive.with_suffix(".zip.sha256")
                checksum.write_text(
                    f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n"
                )
                result = subprocess.run(
                    [
                        "node",
                        "installer/opensocrates.mjs",
                        "verify",
                        "--host",
                        "codex",
                        "--asset",
                        str(archive),
                        "--checksum",
                        str(checksum),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    timeout=30,
                )
                self.assertNotEqual(result.returncode, 0, entries)
                self.assertFalse((root / "escape").exists())

    @unittest.skipUnless(PACKAGES, "requires --packages after build_windows.py")
    def test_real_packaged_runtime_and_checksum(self):
        version = (ROOT / "VERSION").read_text().strip()
        for host in ("codex",):
            archive = ROOT / "dist" / f"opensocrates-{version}-{host}-plugin-windows-x64.zip"
            subprocess.run(
                [
                    "node",
                    "installer/opensocrates.mjs",
                    "verify",
                    "--host",
                    host,
                    "--asset",
                    str(archive),
                    "--checksum",
                    str(archive) + ".sha256",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                timeout=180,
            )
            with tempfile.TemporaryDirectory(prefix="OpenSocrates 배포 space ") as name:
                package = Path(name)
                with zipfile.ZipFile(archive) as bundle:
                    bundle.extractall(package)
                environment = {
                    key: value
                    for key, value in os.environ.items()
                    if key
                    not in {"PYTHONPATH", "VIRTUAL_ENV", "UV_PYTHON_INSTALL_DIR", "PYTHONHOME"}
                }
                environment["PATH"] = os.pathsep.join(
                    (
                        str(Path(shutil.which("node")).parent),
                        str(Path(os.environ["SystemRoot"]) / "System32"),
                    )
                )
                environment["PYTHONUTF8"] = "0"
                launcher = package / "bin/launch.mjs"
                result = subprocess.run(
                    ["node", str(launcher), "decision", host],
                    input=json.dumps({"operation": "catalog", "locale": "ko"}),
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    cwd=package,
                    env=environment,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(json.loads(result.stdout)["methods"]), 48)
                payload = (
                    package / "skills/opensocrates/references/decision/request.json"
                ).read_text(encoding="utf-8")
                for arguments, data, count in (
                    ([], payload, 1),
                    (["--stream"], (json.dumps(json.loads(payload)) + "\n") * 2, 2),
                ):
                    selected = subprocess.run(
                        ["node", str(launcher), "decision", host, *arguments],
                        input=data,
                        text=True,
                        encoding="utf-8",
                        capture_output=True,
                        cwd=package,
                        env=environment,
                        timeout=30,
                    )
                    self.assertEqual(selected.returncode, 0, selected.stderr)
                    rows = [json.loads(line) for line in selected.stdout.splitlines()]
                    self.assertEqual(len(rows), count)
                    for row in rows:
                        self.assertEqual(row["status"], "selected")
                        self.assertEqual(row["selected"], ["critical-thinking"])
                        self.assertEqual(row["applied"], "unverified")
                    if count == 2:
                        self.assertFalse(rows[0]["selection_reused"])
                        self.assertTrue(rows[1]["selection_reused"])

                result = subprocess.run(
                    ["node", str(launcher), "hook", host, "user_prompt_submitted"],
                    input='{"hook_event_name":"UserPromptSubmit","session_id":"windows-fixture","prompt":"synthetic"}',
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    cwd=package,
                    env=environment,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("opensocrates", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
