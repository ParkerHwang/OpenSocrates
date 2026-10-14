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
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from opensocrates.cli.runtime import build_runtime_services
from opensocrates.constants import MAX_CONTROL_DEPTH, MAX_HOOK_INPUT_BYTES
from opensocrates.content.injection import ProjectionInstructionAssembler
from opensocrates.content.loader import load_reasoning_content_projections
from opensocrates.hooks.entrypoint import run_hook
from opensocrates.hosts.codex.adapter import CodexAdapter, CodexAdapterConfig
from opensocrates.hosts.codex.native import (
    MAX_NATIVE_BYTES,
    try_parse_codex_entry_event,
    try_parse_codex_event,
)
from opensocrates.persistence.paths import DataRoot, DataRootLayout
from opensocrates.persistence.permissions import secure_mode
from opensocrates.selector.artifacts import InstructionFileStore
from opensocrates.selector.entry import ENTRY_GUIDANCE

ROOT = Path(__file__).resolve().parents[1]


class SubmissionEntryChecks(unittest.TestCase):
    def setUp(self):
        self.store, self.selector = Mock(), Mock()
        self.adapter = CodexAdapter(
            CodexAdapterConfig(
                decision_point_mode=True,
                selector_mode=True,
                selector_application=self.selector,
                instruction_file_store=self.store,
            )
        )
        self.services = SimpleNamespace(adapter_for=Mock(return_value=self.adapter))

    @staticmethod
    def envelope(prompt="synthetic", **overrides):
        return dict(
            hook_event_name="UserPromptSubmit", session_id="fixture", prompt=prompt, **overrides
        )

    @classmethod
    def raw_size(cls, size):
        empty = json.dumps(cls.envelope(""), separators=(",", ":")).encode()
        return json.dumps(cls.envelope("x" * (size - len(empty))), separators=(",", ":")).encode()

    def invoke(self, raw, *, lane="user_prompt_submitted"):
        if isinstance(raw, dict):
            raw = json.dumps(raw, ensure_ascii=False).encode()
        output = io.StringIO()
        self.assertEqual(
            run_hook(("codex", lane), stdin=io.BytesIO(raw), stdout=output, services=self.services),
            0,
        )
        return output.getvalue()

    def test_large_submission_delivers_same_entry_without_selector(self):
        expected = self.invoke(self.envelope())
        self.assertEqual(
            json.loads(expected)["hookSpecificOutput"]["additionalContext"], ENTRY_GUIDANCE
        )
        for size in (MAX_NATIVE_BYTES, MAX_NATIVE_BYTES + 1, 96_822):
            with self.subTest(envelope_bytes=size):
                raw = self.raw_size(size)
                self.assertEqual(len(raw), size)
                self.assertEqual(self.invoke(raw), expected)
        for prompt in ("x" * 96_732, "한" * 32_244, '\\"' * 24_000):
            with self.subTest(prompt_bytes=len(prompt.encode())):
                self.assertEqual(self.invoke(self.envelope(prompt)), expected)
        self.selector.select_for_user_prompt_submit.assert_not_called()
        self.assertEqual(self.store.method_calls, [call.delete_session("fixture")] * 7)

    def test_ingress_bound_is_shared_and_inclusive(self):
        at_limit = self.raw_size(MAX_HOOK_INPUT_BYTES)
        self.assertEqual(len(at_limit), MAX_HOOK_INPUT_BYTES)
        self.assertTrue(self.invoke(at_limit))
        self.services.adapter_for.reset_mock()
        self.assertEqual(self.invoke(self.raw_size(MAX_HOOK_INPUT_BYTES + 1)), "")
        self.services.adapter_for.assert_not_called()
        self.assertEqual(
            try_parse_codex_entry_event(self.raw_size(MAX_HOOK_INPUT_BYTES + 1)).error_code,
            "input_too_large",
        )

    def test_projection_drops_task_content_and_unneeded_metadata(self):
        payload = self.envelope(
            "PRIVATE_SENTINEL" * 8000,
            turn_id="PRIVATE_SENTINEL",
            cwd="/PRIVATE_SENTINEL",
            transcript_path="/PRIVATE_SENTINEL",
            model="PRIVATE_SENTINEL",
            PRIVATE_SENTINEL={"tool_response": "PRIVATE_SENTINEL"},
        )
        parsed = try_parse_codex_entry_event(payload)
        self.assertTrue(parsed.accepted)
        event = parsed.event
        self.assertIsNotNone(event)
        for field in ("prompt", "turn_id", "cwd", "transcript_path", "model", "final_message"):
            self.assertIsNone(getattr(event, field))
        self.assertEqual(event.ignored_fields, ())
        self.assertEqual(parsed.diagnostics, ())
        result = self.adapter.handle(payload)
        self.assertEqual(result.projection, {})
        self.assertIsNone(result.normalized_event)
        self.assertNotIn("PRIVATE_SENTINEL", repr(parsed) + repr(result) + result.stdout)
        self.store.delete_session.assert_called_once_with("fixture")

    def test_legacy_selector_and_other_event_bounds_are_unchanged(self):
        raw = self.raw_size(MAX_NATIVE_BYTES + 1)
        self.assertEqual(try_parse_codex_event(raw).error_code, "input_too_large")
        legacy = CodexAdapter(
            CodexAdapterConfig(selector_mode=True, selector_application=self.selector)
        )
        self.assertEqual(legacy.handle(raw).stdout, "")
        self.selector.select_for_user_prompt_submit.assert_not_called()
        for native_name, lane in (
            ("Stop", "completion_candidate"),
            ("PostToolUse", "tool_succeeded"),
        ):
            payload = dict(hook_event_name=native_name, extra="x" * 96_732)
            self.assertEqual(self.invoke(payload, lane=lane), "")
            self.assertEqual(
                try_parse_codex_entry_event(payload, event_name=native_name).error_code,
                "input_too_large",
            )

    def test_malformed_or_mismatched_envelopes_fail_open_without_cleanup(self):
        nested = None
        for _ in range(MAX_CONTROL_DEPTH + 1):
            nested = [nested]
        invalid = [
            b"{",
            b"[]",
            b"\xff",
            self.envelope(None),
            self.envelope(1),
            self.envelope(["text"]),
            dict(hook_event_name="UserPromptSubmit", session_id="fixture"),
            dict(hook_event_name="Stop", prompt="synthetic"),
            dict(hook_event_name="user_prompt_submitted", prompt="synthetic"),
            dict(hook_event_name="UserPromptSubmit", prompt="synthetic", session_id=1),
            dict(hook_event_name="UserPromptSubmit", prompt="synthetic", session_id="x" * 257),
            dict(hook_event_name="UserPromptSubmit", prompt="synthetic", session_id="bad\x00id"),
            self.envelope("bad\x00prompt"),
            self.envelope("synthetic", extra=nested),
            self.envelope("synthetic", extra=[None] * 257),
            self.envelope("synthetic", extra={str(n): None for n in range(129)}),
        ]
        for payload in invalid:
            with self.subTest(payload_type=type(payload).__name__):
                self.assertEqual(self.invoke(payload), "")
        self.assertEqual(self.invoke(self.envelope(), lane="completion_candidate"), "")
        self.store.delete_session.assert_not_called()
        self.selector.select_for_user_prompt_submit.assert_not_called()
        raw_surrogate = b'{"hook_event_name":"UserPromptSubmit","prompt":"\\ud800"}'
        self.assertFalse(try_parse_codex_entry_event(raw_surrogate).accepted)
        self.assertFalse(try_parse_codex_entry_event(self.envelope(), event_name="Stop").accepted)


class HookCompositionChecks(unittest.TestCase):
    def test_real_entry_does_not_initialize_or_load_content(self):
        for host in ("codex",):
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
            for mode in (
                (None, "short", "wide") if os.name == "nt" else (None, "short", "wide", "symlink")
            ):
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

    @unittest.skipIf(
        os.name == "nt", "POSIX mode semantics; native Windows ACL regression in check_windows.py"
    )
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

    @unittest.skipIf(
        os.name == "nt", "POSIX UID mutation; native Windows ACL regression in check_windows.py"
    )
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
            secure_mode(root, directory=True)
            key = root / "installation.key"
            key.write_bytes(b"f" * 32)
            secure_mode(key, directory=False)
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
            for host in ("codex",):
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
