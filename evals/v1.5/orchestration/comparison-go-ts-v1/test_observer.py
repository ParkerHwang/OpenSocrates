"""No-model control for observer failure and incomplete-start accounting."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opensocrates.orchestration.adapter import CallResult, CodexAdapter
from observer import ObservedAdapter, reconcile


class ObserverControls(unittest.TestCase):
    def test_write_failure_preserves_native_role_and_check_receipts(self):
        with tempfile.TemporaryDirectory() as raw:
            missing_parent = Path(raw) / "missing" / "journal.jsonl"
            adapter = ObservedAdapter("/bin/true", missing_parent)
            native = CallResult({"files": []}, {
                "status": "completed", "provider_error_events": 0,
                "failed_turn_events": 0, "usage": {"input_tokens": 11},
            })
            with patch.object(CodexAdapter, "invoke", return_value=native), patch.object(
                CodexAdapter, "check", return_value={"status": "passed", "exit_code": 0}
            ):
                role = adapter.invoke({"assignment_id": "a", "unit_id": "u", "role": "production"}, Path(raw))
                check = adapter.check({"check_id": "c"}, Path(raw), {}, "sha256:" + "0" * 64)
            self.assertIs(role, native)
            self.assertEqual(role.receipt["usage"]["input_tokens"], 11)
            self.assertEqual(check["status"], "passed")
            self.assertEqual(len(adapter.observation_failures), 4)
            self.assertEqual({x["phase"] for x in adapter.observation_failures}, {"start", "terminal"})

    def test_start_without_terminal_is_visible(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "journal.jsonl"
            path.write_text(json.dumps({"kind": "role", "assignment_id": "a", "phase": "start"}) + "\n")
            self.assertEqual(reconcile(path)["start_without_terminal"], [
                {"kind": "role", "identity": "a", "unmatched_starts": 1}
            ])

    def test_command_and_unclassified_error_are_separate(self):
        events = [
            {"type": "item.completed", "item": {"type": "error", "id": "e1"}},
            {"type": "item.started", "item": {"type": "command_execution", "id": "c1"}},
            {"type": "item.completed", "item": {"type": "command_execution", "id": "c1",
                                          "command": "private command discarded", "aggregated_output": "private output discarded",
                                          "exit_code": 0}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
            {"type": "turn.completed", "usage": {"input_tokens": 11, "output_tokens": 3}},
        ]
        class Process:
            stdout = io.BytesIO(b"".join((json.dumps(event) + "\n").encode() for event in events))
        with tempfile.TemporaryDirectory() as raw:
            adapter = ObservedAdapter("/bin/true", Path(raw) / "journal.jsonl")
            summary = {"event_stream_observed": False}
            adapter._current_event_summary = summary
            receipt = {"provider_error_events": 0, "failed_turn_events": 0,
                       "usage": None, "thread_sha256": None}
            final, complete = adapter._events(Process(), receipt)
            self.assertEqual((final, complete), ("{}", True))
            self.assertEqual(summary["command_started"], 1)
            self.assertEqual(summary["command_completed"], 1)
            self.assertEqual(summary["unclassified_error_items"], 1)
            self.assertEqual(summary["other_tool_completed"], 0)
            self.assertEqual(receipt["usage"]["input_tokens"], 11)
            self.assertNotIn("private command", json.dumps(summary))
            self.assertNotIn("private output", json.dumps(summary))


if __name__ == "__main__":
    unittest.main()
