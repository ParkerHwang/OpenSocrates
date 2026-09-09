"""Native Windows regressions, including real packaged bytes when --packages is set."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from opensocrates.persistence.atomic import append_fsync, atomic_replace_bytes, read_bytes
from opensocrates.persistence.permissions import check_permissions, secure_mode

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = "--packages" in sys.argv
if PACKAGES:
    sys.argv.remove("--packages")


@unittest.skipUnless(sys.platform == "win32", "native Windows regression")
class WindowsChecks(unittest.TestCase):
    def test_acl_private_and_binary_atomic_io(self):
        with tempfile.TemporaryDirectory(prefix="OpenSocrates 한글 space ") as name:
            root = Path(name)
            secure_mode(root, directory=True)
            self.assertTrue(check_permissions(root, directory=True).write_allowed)
            path = root / "한글 state.json"
            value = '{"value":"한글\u001a"}\n'.encode()
            atomic_replace_bytes(path, value)
            self.assertEqual(read_bytes(path, max_bytes=1024), value)
            atomic_replace_bytes(path, b"first\n")
            append_fsync(path, b"second\n", max_bytes=1024)
            self.assertEqual(path.read_bytes(), b"first\nsecond\n")

    def test_long_private_artifact_path(self):
        from check_selector import _METHODS, _REVISION, _projections
        from opensocrates.content.injection import assemble_canonical_instruction
        from opensocrates.selector.artifacts import InstructionFileStore

        with tempfile.TemporaryDirectory(prefix="OpenSocrates long 한글 space ") as name:
            directory = Path(name) / ("nested" * 15)
            directory.mkdir()
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
            root = Path(name)
            secure_mode(root, directory=True)
            # Add a real Everyone read ACE using Windows' native ACL utility.
            subprocess.run(
                ["icacls.exe", str(root), "/grant", "*S-1-1-0:(R)"], check=True, capture_output=True
            )
            self.assertEqual(inspect_acl(root), (True, False))
            self.assertFalse(check_permissions(root, directory=True).write_allowed)

    def test_junction_is_not_a_private_directory(self):
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

    def test_lock_excludes_second_process(self):
        from opensocrates.persistence.locks import FileLock

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            secure_mode(root, directory=True)
            lock = root / "state.lock"
            code = "from pathlib import Path; from opensocrates.persistence.locks import FileLock; FileLock(Path(__import__('sys').argv[1])).acquire()"
            with FileLock(lock):
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
