"""Observer regressions use synthetic receipts and never launch a subject."""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import summarize_observations as observer

STAMP = "2026-09-27T07:00:00+00:00"


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "results" / "synthetic-cell"
        self.output.mkdir(parents=True)
        (self.root / "manifest.json").write_text(json.dumps({"cells": [{"id": "synthetic-cell"}]}))

    def save(self, name, value):
        (self.output / name).write_text(json.dumps(value))

    def start(self):
        self.save("call.started.json", {"started_utc": STAMP})
        self.save("process.json", {"pid": 123, "started_utc": STAMP})

    def view(self, status="alive"):
        return observer.summarize(
            self.root,
            probe=lambda _: {"pid": 123, "status": status},
            checked_at=datetime(2026, 9, 28, tzinfo=timezone.utc),
        )

    def completed(self):
        self.start()
        self.save(
            "call.json",
            {
                "process_success": True,
                "started_utc": STAMP,
                "ended_utc": STAMP,
                "wall_seconds": 0,
                "usage": {**dict.fromkeys(observer.KEYS), "input_tokens": 100},
                "native_memory": {},
                "protected_inputs_unchanged": True,
                "package_members_unchanged": None,
            },
        )

    def test_pending_is_not_an_attempt(self):
        view = self.view()
        self.assertEqual(view["state_counts"], {"pending": 1})
        self.assertEqual(view["usage_totals"]["input_tokens"]["missing_attempted_cells"], 0)

    def test_live_and_quiet_is_running_without_a_deadline(self):
        self.start()
        (self.output / "resources.jsonl").write_text(
            json.dumps(
                {
                    "utc": STAMP,
                    "elapsed_seconds": 1,
                    "rss_kib": 100,
                }
            )
            + "\n"
        )
        view = self.view()
        self.assertEqual(view["state_counts"], {"running": 1})
        self.assertEqual(view["attention_cells"], [])
        self.assertGreater(
            view["cells"][0]["live_observation"]["resource_sample_age_seconds"], 3600
        )
        self.assertIsNone(view["usage_totals"]["input_tokens"]["reported_sum"])

    def test_dead_zombie_or_reused_pid_is_not_running_or_a_failed_outcome(self):
        self.start()
        for status in ("exited", "zombie", "identity_mismatch"):
            with self.subTest(status=status):
                view = self.view(status)
                self.assertEqual(view["state_counts"], {"awaiting_terminal_receipt": 1})
                self.assertIsNone(view["cells"][0]["process_outcome"])
                self.assertEqual(len(view["attention_cells"]), 1)
                self.assertEqual(view["usage_totals"]["input_tokens"]["missing_attempted_cells"], 1)

    def test_unavailable_probe_does_not_claim_liveness(self):
        self.start()
        self.assertEqual(self.view("unconfirmed")["state_counts"], {"unconfirmed": 1})

    def test_missing_process_receipt_is_unconfirmed(self):
        self.save("call.started.json", {"started_utc": STAMP})
        self.assertEqual(self.view()["state_counts"], {"unconfirmed": 1})

    def test_public_completion_without_receipt_is_finalizing(self):
        self.start()
        (self.output / "observation.jsonl").write_text(
            json.dumps(
                {
                    "utc": STAMP,
                    "elapsed_seconds": 1,
                    "event": {"type": "turn.completed"},
                }
            )
            + "\n"
        )
        self.assertEqual(self.view()["state_counts"], {"finalizing": 1})

    def test_terminal_receipt_is_authoritative_after_process_exits(self):
        self.completed()
        view = self.view("exited")
        self.assertEqual(view["state_counts"], {"complete": 1})
        self.assertEqual(view["usage_totals"]["input_tokens"]["reported_sum"], 100)
        self.assertIsNone(view["usage_totals"]["output_tokens"]["reported_sum"])

    def test_post_call_harness_failure_is_not_hidden_by_success(self):
        self.completed()
        self.save("harness-failure.json", {"call_attempted": True, "detail": "snapshot failed"})
        view = self.view()
        self.assertEqual(view["state_counts"], {"harness_failed": 1})
        self.assertEqual(view["cells"][0]["process_outcome"], "complete")
        self.assertEqual(view["usage_totals"]["input_tokens"]["reported_sum"], 100)

    def test_failed_harness_after_start_counts_missing_usage(self):
        self.start()
        self.save("harness-failure.json", {"call_attempted": True})
        view = self.view()
        self.assertEqual(view["usage_totals"]["input_tokens"]["missing_attempted_cells"], 1)

    def test_partial_live_line_is_not_rewritten(self):
        self.start()
        path = self.output / "observation.jsonl"
        path.write_text('{"utc":')
        self.assertEqual(self.view()["state_counts"], {"running": 1})
        self.assertEqual(path.read_text(), '{"utc":')


class ProcessProbeTests(unittest.TestCase):
    def probe(self, stdout="", returncode=0, stderr=""):
        with patch.object(
            observer.subprocess,
            "run",
            return_value=SimpleNamespace(
                stdout=stdout,
                returncode=returncode,
                stderr=stderr,
            ),
        ):
            return observer.process_health({"pid": 123, "started_utc": STAMP})["status"]

    def test_observed_start_time_and_executable_match(self):
        self.assertEqual(self.probe("123 Ss Sun Sep 27 07:00:00 2026 /app/codex"), "alive")

    def test_zombie_is_not_alive(self):
        self.assertEqual(self.probe("123 Z Sun Sep 27 07:00:00 2026 /app/codex"), "zombie")

    def test_pid_reuse_or_wrong_executable(self):
        for output in (
            "123 S Sun Sep 27 08:00:00 2026 /app/codex",
            "123 S Sun Sep 27 07:00:00 2026 /app/python3",
        ):
            self.assertEqual(self.probe(output), "identity_mismatch")

    def test_absent_pid(self):
        self.assertEqual(self.probe(returncode=1), "exited")

    def test_ps_error_or_malformed_output_is_unknown(self):
        self.assertEqual(self.probe(returncode=1, stderr="access denied"), "unconfirmed")
        self.assertEqual(self.probe("unsupported output"), "unconfirmed")

    def test_no_ps_is_unknown(self):
        with patch.object(observer.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(
                observer.process_health({"pid": 123, "started_utc": STAMP})["status"], "unconfirmed"
            )


if __name__ == "__main__":
    unittest.main()
