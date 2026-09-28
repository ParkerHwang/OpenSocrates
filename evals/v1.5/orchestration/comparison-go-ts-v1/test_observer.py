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
            native = CallResult(None, {
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

    def test_completed_role_receipt_survives_later_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            journal = Path(raw) / "journal.jsonl"
            adapter = ObservedAdapter("/bin/true", journal)
            native = CallResult({"files": []}, {
                "status": "completed", "reason": "structured_result",
                "process_exit_code": 0, "input_sha256": "sha256:input",
                "output_sha256": "sha256:output", "thread_sha256": "sha256:thread",
                "model": {"name": "synthetic", "effort": "high"},
                "usage": {"input_tokens": 17, "cached_input_tokens": 4,
                          "cache_write_input_tokens": 0, "output_tokens": 5,
                          "reasoning_output_tokens": 2},
                "provider_error_events": 0, "failed_turn_events": 0,
                "backend_attempts": None,
            })
            with patch.object(CodexAdapter, "invoke", return_value=native):
                adapter.invoke({"assignment_id": "role1", "unit_id": "u", "role": "production"}, Path(raw))
            # Simulate a later role/check failure in the same episode. The
            # first role's native usage is already durable on disk.
            try:
                raise RuntimeError("later step failed")
            except RuntimeError:
                pass
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual([row["phase"] for row in rows], ["start", "terminal"])
            self.assertEqual(rows[1]["usage"]["input_tokens"], 17)
            self.assertEqual(rows[1]["process_exit_code"], 0)
            self.assertEqual(rows[1]["output_sha256"], "sha256:output")

    def test_rejected_candidate_quarantines_only_declared_owned_text(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            adapter = ObservedAdapter("/bin/true", root / "journal.jsonl")
            value = {"blocked_reason": "missing_input", "files": [
                {"path": "a.go", "content": "package main\n"},
                {"path": "../private/oracle.py", "content": "must not persist\n"},
            ]}
            native = CallResult(value, {"status": "completed", "reason": "structured_result",
                                        "provider_error_events": 0, "failed_turn_events": 0,
                                        "process_exit_code": 0, "usage": {"input_tokens": 9}})
            assignment = {"assignment_id": "a1", "unit_id": "u", "role": "production",
                          "owned_paths": ["a.go", "b.go"], "model": {"name": "synthetic", "effort": "high"}}
            with patch.object(CodexAdapter, "invoke", return_value=native):
                self.assertIs(adapter.invoke(assignment, root), native)
            quarantine = root / "quarantine/a1"
            self.assertEqual((quarantine / "a.go").read_text(), "package main\n")
            self.assertFalse((root / "private/oracle.py").exists())
            metadata = json.loads((quarantine / "metadata.json").read_text())
            self.assertEqual(metadata["blocked_reason"], "missing_input")
            self.assertEqual(metadata["unowned_path_count"], 1)
            self.assertFalse(metadata["owned_path_set_matches"])
            self.assertEqual(metadata["quarantined_owned_paths"], ["a.go"])
            self.assertNotIn("../private/oracle.py", json.dumps(metadata))


if __name__ == "__main__":
    unittest.main()
