#!/usr/bin/env python3
"""Focused offline Claude normalization, privacy, and native-launcher contracts."""

from __future__ import annotations

import contextlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensocrates.cli.claude_hook import run_claude_hook  # noqa: E402
from opensocrates.hosts.claude.adapter import REFERENCE_PATHS  # noqa: E402
from opensocrates.hosts.claude.commands import build_hooks  # noqa: E402
from opensocrates.hosts.claude.native import (  # noqa: E402
    MAX_PAYLOAD_CHARS,
    parse_claude_event,
)
from opensocrates.hosts.claude.responses import entry_response  # noqa: E402
from opensocrates.selector.entry import ENTRY_GUIDANCE  # noqa: E402


def _payload(event: str = "SessionStart", **fields: object) -> str:
    value: dict[str, object] = {"hook_event_name": event, "session_id": "synthetic-session"}
    if event == "SessionStart":
        value["source"] = "startup"
    if event == "UserPromptSubmit":
        value["prompt"] = "synthetic-private-prompt"
    value.update(fields)
    return json.dumps(value)


def _install_references(root: Path) -> None:
    for relative in REFERENCE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic-complete-reference\n", encoding="utf-8")


def _directory_link(path: Path, target: Path) -> None:
    """Use a native junction on unprivileged Windows; never follow it on cleanup."""

    if os.name != "nt":
        path.symlink_to(target, target_is_directory=True)
        return
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item -ItemType Junction -Path $env:OPENSOCRATES_TEST_LINK "
            "-Target $env:OPENSOCRATES_TEST_TARGET | Out-Null",
        ],
        env={
            **os.environ,
            "OPENSOCRATES_TEST_LINK": str(path),
            "OPENSOCRATES_TEST_TARGET": str(target),
        },
        capture_output=True,
        check=True,
        timeout=10,
    )


class ClaudeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory(prefix="opensocrates-claude-contract-")
        self.root = Path(self.scratch.name).resolve() / "installed package 한글"
        _install_references(self.root)

    def tearDown(self) -> None:
        self.scratch.cleanup()

    def call(self, raw: str, root: Path | None = None) -> str:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = run_claude_hook(io.StringIO(raw), stdout, plugin_root=root or self.root)
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        return stdout.getvalue()

    def test_session_start_exact_envelope(self) -> None:
        value = json.loads(self.call(_payload()))
        self.assertEqual(set(value), {"hookSpecificOutput"})
        specific = value["hookSpecificOutput"]
        self.assertEqual(set(specific), {"hookEventName", "additionalContext"})
        self.assertEqual(specific["hookEventName"], "SessionStart")
        self.assertIn(ENTRY_GUIDANCE, specific["additionalContext"])
        for path in REFERENCE_PATHS:
            self.assertIn(
                json.dumps(str(self.root / path), ensure_ascii=False), specific["additionalContext"]
            )

    def test_submit_ignores_private_and_new_host_fields(self) -> None:
        raw = _payload(
            "UserPromptSubmit",
            cwd="/synthetic-attacker-workspace",
            transcript_path="/synthetic-private-transcript",
            new_host_field={"future": [1, True]},
        )
        response = self.call(raw)
        self.assertEqual(
            json.loads(response)["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit"
        )
        self.assertNotIn("synthetic-private", response)
        self.assertNotIn("synthetic-attacker", response)
        event = parse_claude_event(raw)
        self.assertIsNotNone(event)
        self.assertFalse(hasattr(event, "prompt"))
        self.assertFalse(hasattr(event, "session_id"))

    def test_compact_session_start_restores_entry(self) -> None:
        self.assertTrue(self.call(_payload(source="compact")))

    def test_other_start_sources(self) -> None:
        for source in ("resume", "clear", "fork"):
            with self.subTest(source=source):
                self.assertTrue(self.call(_payload(source=source)))

    def test_noop_events(self) -> None:
        for event in ("Stop", "SessionEnd", "PostCompact"):
            with self.subTest(event=event):
                self.assertEqual(
                    self.call(_payload(event, compact_summary="synthetic-private")), ""
                )

    def test_unknown_event(self) -> None:
        self.assertEqual(self.call(_payload("PermissionRequest")), "")

    def test_invalid_json_and_non_objects(self) -> None:
        for raw in ("", "{", "[]", "null", '"scalar"', "{}", "{} {}"):
            with self.subTest(raw=raw):
                self.assertEqual(self.call(raw), "")

    def test_duplicate_fields_rejected(self) -> None:
        self.assertEqual(
            self.call('{"hook_event_name":"Stop","hook_event_name":"SessionStart"}'), ""
        )

    def test_non_json_numeric_constant(self) -> None:
        self.assertEqual(self.call(_payload()[:-1] + ',"future":NaN}'), "")

    def test_known_field_types(self) -> None:
        cases = (
            _payload(hook_event_name=1),
            _payload(source="unknown"),
            _payload(source=None),
            _payload(session_id={"private": True}),
            _payload(prompt_id=12),
            _payload("UserPromptSubmit", prompt=None),
            _payload("Stop", stop_hook_active="false"),
        )
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.call(raw), "")

    def test_excessive_input(self) -> None:
        self.assertEqual(
            self.call(_payload("UserPromptSubmit", prompt="x" * MAX_PAYLOAD_CHARS)), ""
        )

    def test_bounded_read(self) -> None:
        class BoundedStream(io.StringIO):
            def read(self, size: int = -1) -> str:
                if size != MAX_PAYLOAD_CHARS + 1:
                    raise AssertionError("unbounded native input read")
                return super().read(size)

        output = io.StringIO()
        self.assertEqual(
            run_claude_hook(BoundedStream(_payload()), output, plugin_root=self.root), 0
        )
        self.assertTrue(output.getvalue())

    def test_deep_nesting_fails_open(self) -> None:
        self.assertEqual(self.call("[" * 2000 + "]" * 2000), "")

    def test_invalid_unicode_fails_open(self) -> None:
        self.assertEqual(self.call(_payload()[:-1] + ',"private":"' + "\ud800" + '"}'), "")

    def test_missing_reference(self) -> None:
        (self.root / REFERENCE_PATHS[1]).unlink()
        self.assertEqual(self.call(_payload()), "")

    def test_empty_reference(self) -> None:
        (self.root / REFERENCE_PATHS[0]).write_text("", encoding="utf-8")
        self.assertEqual(self.call(_payload()), "")

    def test_outside_symlink_rejected(self) -> None:
        path = self.root / REFERENCE_PATHS[0]
        path.unlink()
        outside = Path(self.scratch.name) / "outside.md"
        outside.write_text("synthetic-outside", encoding="utf-8")
        try:
            path.symlink_to(outside)
        except OSError as error:
            if os.name == "nt" and error.winerror == 1314:
                self.skipTest("native file symlink creation requires Windows privilege")
            raise
        self.assertEqual(self.call(_payload()), "")

    def test_parent_symlink_rejected(self) -> None:
        original = self.root / "skills"
        moved = Path(self.scratch.name) / "moved-skills"
        original.rename(moved)
        _directory_link(original, moved)
        self.assertEqual(self.call(_payload()), "")

    def test_relative_root_rejected(self) -> None:
        self.assertEqual(self.call(_payload(), Path(".")), "")

    def test_source_root_and_cwd_are_not_fallbacks(self) -> None:
        output = io.StringIO()
        with patch("opensocrates.cli.claude_hook.sys.frozen", False, create=True):
            with patch("pathlib.Path.cwd", return_value=self.root):
                run_claude_hook(io.StringIO(_payload(cwd=str(self.root))), output)
        self.assertEqual(output.getvalue(), "")

    def test_frozen_root_is_derived_from_executable(self) -> None:
        executable = self.root / "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime"
        executable.parent.mkdir(parents=True)
        executable.touch()
        output = io.StringIO()
        with patch("opensocrates.cli.claude_hook.sys.frozen", True, create=True):
            with patch("opensocrates.cli.claude_hook.sys.executable", str(executable)):
                run_claude_hook(io.StringIO(_payload()), output)
        self.assertTrue(output.getvalue())

    def test_no_disk_reads_writes_or_private_logs(self) -> None:
        before = {path.relative_to(self.root) for path in self.root.rglob("*")}
        with contextlib.ExitStack() as stack:
            for seam in (
                "builtins.open",
                "pathlib.Path.read_text",
                "pathlib.Path.read_bytes",
                "pathlib.Path.write_text",
                "pathlib.Path.write_bytes",
            ):
                stack.enter_context(patch(seam, side_effect=AssertionError("unexpected disk IO")))
            response = self.call(_payload("UserPromptSubmit"))
        self.assertTrue(response)
        self.assertEqual(before, {path.relative_to(self.root) for path in self.root.rglob("*")})
        self.assertNotIn("synthetic-private-prompt", response)

    def test_response_event_and_size_boundaries(self) -> None:
        self.assertIsNone(entry_response("context", "PostCompact"))
        self.assertIsNone(entry_response("context", "Stop"))
        self.assertIsNone(entry_response("x" * 16385, "SessionStart"))
        self.assertIsNone(entry_response("bad\x00context", "SessionStart"))

    def test_generated_hook_commands(self) -> None:
        hooks = build_hooks()["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"})
        for groups in hooks.values():
            command = groups[0]["hooks"][0]
            self.assertEqual(command["command"], "${CLAUDE_PLUGIN_ROOT}/bin/launch.sh")
            self.assertEqual(command["args"][:2], ["hook", "claude"])
            self.assertNotIn("control", json.dumps(command))
            self.assertLessEqual(command["timeout"], 3)

    def test_native_metadata_and_launcher_executable(self) -> None:
        metadata = json.loads((ROOT / "plugin-src/claude/generator.json").read_text())
        self.assertEqual(metadata["release_targets"], ["darwin-arm64"])
        self.assertEqual(metadata["public_skills"], ["opensocrates"])
        self.assertEqual(
            metadata["hooks_builder"], "opensocrates.hosts.claude.commands:build_hooks"
        )
        self.assertEqual(metadata["manifest_output"], ".claude-plugin/plugin.json")
        self.assertTrue(os.access(ROOT / "packaging/launchers/claude-launch.sh", os.X_OK))


@unittest.skipUnless(
    platform.system() == "Darwin" and platform.machine() == "arm64", "native Mac launcher"
)
class ClaudeLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory(prefix="opensocrates-claude-launcher-")
        self.root = Path(self.scratch.name).resolve() / "package with spaces 한글"
        self.launcher = self.root / "bin/launch.sh"
        self.launcher.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "packaging/launchers/claude-launch.sh", self.launcher)
        self.launcher.chmod(0o755)
        self.runtime = self.root / "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime"
        self.runtime.parent.mkdir(parents=True)
        self.runtime.write_text('#!/bin/sh\nprintf "argv:%s\\n" "$*"\ncat\n', encoding="utf-8")
        self.runtime.chmod(0o755)

    def tearDown(self) -> None:
        self.scratch.cleanup()

    def invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.launcher), *args],
            input="synthetic-stdin\n",
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
            cwd=self.scratch.name,
        )

    def test_exact_hook_dispatch(self) -> None:
        for event in ("session_started", "user_prompt_submitted"):
            result = self.invoke("hook", "claude", event)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "argv:claude-hook\nsynthetic-stdin\n")
            self.assertEqual(result.stderr, "")

    def test_decision_and_stream_dispatch(self) -> None:
        self.assertEqual(
            self.invoke("decision", "claude").stdout, "argv:decision\nsynthetic-stdin\n"
        )
        self.assertEqual(
            self.invoke("decision", "claude", "--stream").stdout,
            "argv:decision --stream\nsynthetic-stdin\n",
        )

    def test_noops_and_bad_host_arguments(self) -> None:
        for args in (
            ("hook", "claude", "completion_candidate"),
            ("hook", "claude", "session_ended"),
            ("hook", "claude", "post_compaction"),
            ("hook", "codex", "user_prompt_submitted"),
            ("hook", "claude", "user_prompt_submitted;bad"),
            ("control", "claude"),
        ):
            with self.subTest(args=args):
                result = self.invoke(*args)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_missing_runtime_ignores_cwd_runtime(self) -> None:
        self.runtime.unlink()
        planted = (
            Path(self.scratch.name)
            / "runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime"
        )
        planted.parent.mkdir(parents=True)
        planted.write_text("#!/bin/sh\nprintf attacker\n", encoding="utf-8")
        planted.chmod(0o755)
        result = self.invoke("hook", "claude", "session_started")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(
            json.loads(self.invoke("decision", "claude").stdout)["status"], "unavailable"
        )

    def test_runtime_symlink_rejected(self) -> None:
        target = self.runtime.with_name("outside-runtime")
        self.runtime.rename(target)
        self.runtime.symlink_to(target)
        self.assertEqual(self.invoke("hook", "claude", "session_started").stdout, "")

    def test_uname_path_tamper_cannot_select_windows(self) -> None:
        shim = Path(self.scratch.name) / "shim"
        shim.mkdir()
        fake = shim / "uname"
        fake.write_text("#!/bin/sh\nprintf Windows\\n\n", encoding="utf-8")
        fake.chmod(0o755)
        environment = dict(os.environ)
        environment["PATH"] = f"{shim}{os.pathsep}{environment.get('PATH', '')}"
        result = subprocess.run(
            [str(self.launcher), "hook", "claude", "session_started"],
            input="",
            text=True,
            capture_output=True,
            env=environment,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.stdout, "argv:claude-hook\n")


if __name__ == "__main__":
    unittest.main(verbosity=1)
