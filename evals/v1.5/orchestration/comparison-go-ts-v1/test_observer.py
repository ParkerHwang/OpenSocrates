"""No-model control for observer failure and incomplete-start accounting."""

from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
