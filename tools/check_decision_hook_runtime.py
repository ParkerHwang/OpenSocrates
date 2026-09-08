"""Credential-free normal-hook composition, cleanup and public stream regressions."""

from __future__ import annotations

import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from opensocrates.cli.runtime import build_runtime_services
from opensocrates.content.injection import ProjectionInstructionAssembler
from opensocrates.content.loader import load_reasoning_content_projections
from opensocrates.hooks.entrypoint import run_hook
from opensocrates.persistence.paths import DataRoot, DataRootLayout
from opensocrates.selector.artifacts import InstructionFileStore

ROOT = Path(__file__).resolve().parents[1]


class HookCompositionChecks(unittest.TestCase):
    def test_real_entry_does_not_initialize_or_load_content(self):
        for host in ("codex", "claude"):
            with tempfile.TemporaryDirectory() as name:
                root = Path(name) / "fresh-product-root"
                with (
                    patch("opensocrates.persistence.paths.resolve_data_root", return_value=root),
                    patch(
                        "opensocrates.cli.runtime.ensure_data_root", side_effect=AssertionError
                    ) as ensure,
                    patch(
                        "opensocrates.cli.runtime.BundleRepository.load", side_effect=AssertionError
                    ) as load,
                    patch(
                        "opensocrates.cli.runtime.TurnStateStore", side_effect=AssertionError
                    ) as turn,
                ):
                    for event, lane in (
                        ("UserPromptSubmit", "user_prompt_submitted"),
                        ("Stop", "completion_candidate"),
                    ):
                        payload = {
                            "hook_event_name": event,
                            "session_id": "fixture",
                            "turn_id": "turn",
                            "prompt": "synthetic",
                            "stop_hook_active": False,
                        }
                        out = io.StringIO()
                        self.assertEqual(
                            run_hook(
                                (host, lane), stdin=io.StringIO(json.dumps(payload)), stdout=out
                            ),
                            0,
                        )
                        if event == "UserPromptSubmit":
                            self.assertIn("additionalContext", out.getvalue())
                        else:
                            self.assertEqual(out.getvalue(), "")
                    ensure.assert_not_called()
                    load.assert_not_called()
                    turn.assert_not_called()
                self.assertFalse(root.exists())

    def test_missing_or_unsafe_existing_key_is_not_created_or_repaired(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            data = DataRoot(DataRootLayout.from_root(root))
            key = root / "installation.key"
            for mode in (None, "short", "wide", "symlink"):
                if key.exists() or key.is_symlink():
                    key.unlink()
                if mode == "short":
                    key.write_bytes(b"x")
                    key.chmod(0o600)
                elif mode == "wide":
                    key.write_bytes(b"x" * 32)
                    key.chmod(0o644)
                elif mode == "symlink":
                    target = root / "fixture-key"
                    target.write_bytes(b"x" * 32)
                    target.chmod(0o600)
                    key.symlink_to(target)
                before = sorted(
                    (p.name, p.lstat().st_mode, p.lstat().st_size) for p in root.iterdir()
                )
                services = build_runtime_services(host="codex", hook_only=True, data_root=data)
                self.assertIsNone(services.instruction_file_store)
                after = sorted(
                    (p.name, p.lstat().st_mode, p.lstat().st_size) for p in root.iterdir()
                )
                self.assertEqual(before, after)

    def test_read_only_root_skips_cleanup_without_repair(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            key = root / "installation.key"
            key.write_bytes(b"r" * 32)
            key.chmod(0o600)
            root.chmod(0o500)
            try:
                services = build_runtime_services(
                    host="codex", hook_only=True, data_root=DataRoot(DataRootLayout.from_root(root))
                )
                self.assertIsNone(services.instruction_file_store)
                self.assertEqual(root.stat().st_mode & 0o777, 0o500)
                self.assertEqual(key.read_bytes(), b"r" * 32)
            finally:
                root.chmod(0o700)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO fixture")
    def test_fifo_and_open_race_cannot_block_normal_hook(self):
        code = """
import io,json,os,sys
from pathlib import Path
from unittest.mock import patch
from opensocrates.hooks.entrypoint import run_hook
root=Path(sys.argv[1]);key=root/'installation.key'
mode=sys.argv[2]
if mode=='fifo': os.mkfifo(key,0o600)
else:
 key.write_bytes(b'f'*32);key.chmod(0o600)
original_open=os.open
replaced=False
def raced_open(path,flags,*args,**kwargs):
 global replaced
 if mode=='race' and Path(path)==key and not replaced:
  replaced=True;key.unlink();os.mkfifo(key,0o600)
 return original_open(path,flags,*args,**kwargs)
with patch('opensocrates.persistence.paths.resolve_data_root',return_value=root), patch('os.open',side_effect=raced_open):
 out=io.StringIO()
 run_hook(('codex','user_prompt_submitted'),stdin=io.StringIO(json.dumps({'hook_event_name':'UserPromptSubmit','session_id':'fixture','turn_id':'turn','prompt':'synthetic'})),stdout=out)
 assert 'additionalContext' in out.getvalue()
assert key.is_fifo()
assert sorted(p.name for p in root.iterdir())==['installation.key']
print('nonblocking fail-open')
"""
        for mode in ("fifo", "race"):
            with tempfile.TemporaryDirectory() as name:
                result = subprocess.run(
                    [sys.executable, "-c", code, name, mode],
                    text=True,
                    capture_output=True,
                    timeout=3,
                    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "nonblocking fail-open\n")

    def test_opened_key_owner_is_validated_before_read(self):
        from opensocrates.persistence.turn_store import (
            TurnStoreError,
            load_existing_installation_key,
        )

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            key = root / "installation.key"
            key.write_bytes(b"o" * 32)
            key.chmod(0o600)
            values = list(key.stat())
            values[4] = os.getuid() + 1
            with patch("os.fstat", return_value=os.stat_result(values)), patch("os.read") as read:
                with self.assertRaises(TurnStoreError):
                    load_existing_installation_key(DataRootLayout.from_root(root))
                read.assert_not_called()

    def test_existing_ttl_and_session_cleanup_survive(self):
        assembled = ProjectionInstructionAssembler(
            load_reasoning_content_projections(
                ROOT / "content/compiled-reasoning-content.bundle.json"
            )
        ).assemble(("deduction",), requested_locale="en")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "product"
            root.mkdir(mode=0o700)
            key = root / "installation.key"
            key.write_bytes(b"f" * 32)
            key.chmod(0o600)
            artifacts = Path(name) / "artifacts"
            store = InstructionFileStore(installation_key=b"f" * 32, directory=artifacts)
            expired = store.create("expired", "turn", assembled)
            live = store.create("fixture", "turn", assembled)
            old = time.time() - 25 * 3600
            os.utime(expired.path, (old, old))
            with patch("opensocrates.cli.runtime.InstructionFileStore", return_value=store):
                services = build_runtime_services(
                    host="codex", hook_only=True, data_root=DataRoot(DataRootLayout.from_root(root))
                )
            self.assertFalse(expired.path.exists())
            self.assertTrue(live.path.exists())
            self.assertEqual(key.read_bytes(), b"f" * 32)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["installation.key"])
            result = services.adapter_for("codex").handle(
                {
                    "hook_event_name": "Stop",
                    "session_id": "fixture",
                    "turn_id": "turn",
                    "stop_hook_active": False,
                },
                event_name="Stop",
            )
            self.assertEqual(result.stdout, "")
            self.assertFalse(live.path.exists())
            self.assertIsNone(services.bundle)
            self.assertIsNone(services.turn_store)
            self.assertIsNone(services.selector_application)

    @unittest.skipUnless(
        platform.system() == "Darwin" and platform.machine() == "arm64",
        "packaged runtime target is Apple-silicon macOS",
    )
    def test_public_launcher_exact_stream_argument_contract(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "bin").mkdir()
            launcher = root / "bin/launch.sh"
            shutil.copy2(ROOT / "packaging/launchers/launch.sh", launcher)
            launcher.chmod(0o755)
            runtime = root / "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime"
            runtime.parent.mkdir(parents=True)
            runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            runtime.chmod(0o755)
            for host in ("codex", "claude"):
                direct = subprocess.run(
                    [str(launcher), "decision", host], text=True, capture_output=True, check=True
                )
                stream = subprocess.run(
                    [str(launcher), "decision", host, "--stream"],
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assertEqual(direct.stdout, "decision\n")
                self.assertEqual(stream.stdout, "decision\n--stream\n")
                for args in (
                    ("decision", host, "--unknown"),
                    ("control", host, "--stream"),
                    ("decision", "unknown", "--stream"),
                ):
                    denied = subprocess.run(
                        [str(launcher), *args], text=True, capture_output=True, check=True
                    )
                    self.assertEqual(
                        json.loads(denied.stdout)["diagnostic"]["code"], "invalid_arguments"
                    )


if __name__ == "__main__":
    unittest.main()
