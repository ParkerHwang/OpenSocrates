from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from compat_probe_v6 import EXPECTED, HELPER_COMMAND, ProbeAdapter, approved_command, paired_tool_identity


class _Process:
    def __init__(self, events):
        self.stdout = io.BytesIO(b"".join(
            (json.dumps(event, separators=(",", ":")) + "\n").encode() for event in events
        ))


class CompatibilityParserControls(unittest.TestCase):
    def test_closed_command_grammar(self):
        cwd = Path("/private/tmp/synthetic-role")
        self.assertTrue(approved_command(HELPER_COMMAND, cwd))
        self.assertTrue(approved_command("/bin/zsh -lc " + json.dumps(HELPER_COMMAND), cwd))
        self.assertTrue(approved_command("cd . && " + HELPER_COMMAND, cwd))
        self.assertTrue(approved_command("cd " + str(cwd) + " && " + HELPER_COMMAND, cwd))
        for command in (
            HELPER_COMMAND + "; cat /tmp/other",
            HELPER_COMMAND + " | cat",
            HELPER_COMMAND + " >/tmp/out",
            "cd /tmp/other && " + HELPER_COMMAND,
            "/bin/zsh -lc " + json.dumps(HELPER_COMMAND + "; true"),
        ):
            self.assertFalse(approved_command(command, cwd), command)

    def test_every_tool_gets_safe_projection_even_when_unmatched(self):
        marker = "COMPAT_PROFILE_V1:" + json.dumps(EXPECTED, separators=(",", ":"))
        # The wrong command still gets its marker booleans projected; it cannot
        # qualify the boundary because the closed command grammar rejects it.
        wrong = "cat inputs/probe/probe_canary.py"
        events = [
            {"type": "item.started", "item": {"id": "tool-1", "type": "command_execution", "command": wrong}},
            {"type": "item.completed", "item": {"id": "tool-1", "type": "command_execution",
                 "command": wrong, "aggregated_output": marker, "exit_code": 0}},
            {"type": "item.completed", "item": {"id": "message-1", "type": "agent_message", "text": "{}"}},
        ]
        with tempfile.TemporaryDirectory() as raw:
            adapter = ProbeAdapter("/bin/true", Path(raw) / "observation.jsonl", Path(raw))
            receipt = {"provider_error_events": 0, "failed_turn_events": 0, "thread_sha256": None,
                       "usage": None}
            adapter._events(_Process(events), receipt)
            self.assertEqual(adapter.tool_started_count, 1)
            self.assertEqual(adapter.tool_call_count, 1)
            self.assertEqual(adapter.public_message_count, 1)
            self.assertEqual(len(adapter.tool_events), 2)
            self.assertEqual(adapter.tool_events[1]["helper_booleans"], EXPECTED)
            self.assertFalse(adapter.tool_events[1]["approved_command"])
            self.assertEqual(adapter.matching, [])
            self.assertNotIn(wrong, json.dumps(adapter.tool_events))
            self.assertNotIn(marker, json.dumps(adapter.tool_events))

    def test_approved_helper_marker_is_parsed_without_raw_retention(self):
        marker = "COMPAT_PROFILE_V1:" + json.dumps(EXPECTED, separators=(",", ":"))
        events = [
            {"type": "item.started", "item": {"id": "tool-2", "type": "command_execution",
                                      "command": HELPER_COMMAND}},
            {"type": "item.completed", "item": {"id": "tool-2", "type": "command_execution",
                                        "command": HELPER_COMMAND, "aggregated_output": marker,
                                        "exit_code": 0}},
        ]
        with tempfile.TemporaryDirectory() as raw:
            adapter = ProbeAdapter("/bin/true", Path(raw) / "observation.jsonl", Path(raw))
            receipt = {"provider_error_events": 0, "failed_turn_events": 0,
                       "thread_sha256": None, "usage": None}
            adapter._events(_Process(events), receipt)
            self.assertEqual(len(adapter.matching), 1)
            self.assertEqual(adapter.matching[0]["helper_booleans"], EXPECTED)
            self.assertTrue(adapter.matching[0]["approved_command"])
            self.assertTrue(paired_tool_identity(adapter.tool_events))
            self.assertNotIn(marker, json.dumps(adapter.tool_events))

    def test_mismatched_start_and_completion_cannot_qualify(self):
        marker = "COMPAT_PROFILE_V1:" + json.dumps(EXPECTED, separators=(",", ":"))
        events = [
            {"type": "item.started", "item": {"id": "A", "type": "command_execution",
                                      "command": "/bin/true"}},
            {"type": "item.completed", "item": {"id": "B", "type": "command_execution",
                                        "command": HELPER_COMMAND, "aggregated_output": marker,
                                        "exit_code": 0}},
        ]
        with tempfile.TemporaryDirectory() as raw:
            adapter = ProbeAdapter("/bin/true", Path(raw) / "observation.jsonl", Path(raw))
            receipt = {"provider_error_events": 0, "failed_turn_events": 0,
                       "thread_sha256": None, "usage": None}
            adapter._events(_Process(events), receipt)
            self.assertEqual(len(adapter.matching), 1)
            self.assertFalse(paired_tool_identity(adapter.tool_events))


if __name__ == "__main__":
    unittest.main()
