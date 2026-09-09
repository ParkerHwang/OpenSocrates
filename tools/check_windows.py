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


@unittest.skipUnless(sys.platform == "win32", "native Windows regression")
class WindowsChecks(unittest.TestCase):
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
        for host in ("claude", "codex"):
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
