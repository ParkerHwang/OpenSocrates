"""Failure and ambiguity controls for original-receipt accounting."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from summarize import (duplicate_id_counts, episode_read, event_reconciliation, peak_overlap,
                       summary_usage_errors, usage_profile)


def call(identity: str = "call-1", *, input_tokens: int | None = 20,
         cached: int | None = 5, output: int | None = 8,
         reasoning: int | None = 3) -> dict:
    return {"assignment_id": identity, "thread_sha256": "thread-" + identity,
            "usage": {"input_tokens": input_tokens, "cached_input_tokens": cached,
                      "cache_write_input_tokens": 0, "output_tokens": output,
                      "reasoning_output_tokens": reasoning}}


def marker(kind: str, phase: str, identity: str, when: str) -> dict:
    name = "assignment_id" if kind == "role" else "check_id"
    return {"kind": kind, "phase": phase, name: identity, "utc": when,
            **({"elapsed_ns": 1_000_000_000} if phase == "terminal" else {})}


START = "2026-09-28T00:00:00+00:00"
END = "2026-09-28T00:00:01+00:00"


class FailureCases(unittest.TestCase):
    def test_missing_usage_is_not_zero_imputed(self):
        profile, errors = usage_profile([call(), call("call-2", input_tokens=None, cached=None,
                                                      output=None, reasoning=None)])
        self.assertFalse(errors)
        self.assertEqual(profile["fields"]["input_tokens"]["known_sum"], 20)
        self.assertIsNone(profile["fields"]["input_tokens"]["complete_sum"])
        self.assertEqual(profile["fields"]["input_tokens"]["missing_calls"], 1)
        self.assertIsNone(profile["derived"]["input_plus_output_tokens"]["complete_sum"])

    def test_cached_and_reasoning_subset_violations_fail(self):
        profile, errors = usage_profile([call(cached=21, reasoning=9)])
        self.assertIn("cached_input_exceeds_input", errors)
        self.assertIn("reasoning_output_exceeds_output", errors)
        self.assertIsNone(profile["derived"]["uncached_input_tokens"]["complete_sum"])
        self.assertIsNone(profile["derived"]["nonreasoning_output_tokens"]["complete_sum"])

    def test_cache_and_reasoning_attributes_are_not_added_twice(self):
        item = call()
        item["usage"]["cache_write_input_tokens"] = 7
        profile, errors = usage_profile([item])
        self.assertFalse(errors)
        self.assertEqual(profile["fields"]["cache_write_input_tokens"]["complete_sum"], 7)
        self.assertEqual(profile["derived"]["input_plus_output_tokens"]["complete_sum"], 28)

    def test_all_marker_count_includes_checks_without_spurious_model_call(self):
        calls = [call()]
        checks = [{"checks": [{"check_id": "static"}]}]
        observed = [marker("role", "start", "call-1", START),
                    marker("role", "terminal", "call-1", END),
                    marker("native_check", "start", "static", START),
                    marker("native_check", "terminal", "static", END)]
        summary = {"role_event_summaries": [{"assignment_id": "call-1"}],
                   "observation_reconciliation": {"start_count": 2, "terminal_count": 2,
                                                  "start_without_terminal": []}}
        result, errors = event_reconciliation(calls, checks, observed, summary)
        self.assertFalse(errors)
        self.assertEqual(result["call_receipts"], 1)
        self.assertEqual(result["native_check_receipts"], 1)
        self.assertEqual(result["all_start_markers"], 2)

    def test_repeated_assignment_identity_is_detected_not_deduplicated(self):
        calls = [call(), call()]
        observed = [marker("role", "start", "call-1", START),
                    marker("role", "terminal", "call-1", END),
                    marker("role", "start", "call-1", START),
                    marker("role", "terminal", "call-1", END)]
        summary = {"role_event_summaries": [{"assignment_id": "call-1"},
                                             {"assignment_id": "call-1"}],
                   "observation_reconciliation": {"start_count": 2, "terminal_count": 2,
                                                  "start_without_terminal": []}}
        result, errors = event_reconciliation(calls, [], observed, summary)
        self.assertIn("repeated_assignment_identity", errors)
        self.assertEqual(result["call_receipts"], 2)

    def test_cross_episode_identity_reuse_is_detected(self):
        assignments, threads = duplicate_id_counts([
            {"cell_id": "first", "_assignment_id": "same", "_thread_sha256": "thread"},
            {"cell_id": "second", "_assignment_id": "same", "_thread_sha256": "thread"},
        ])
        self.assertEqual((assignments, threads), (1, 1))

    def test_missing_role_or_check_markers_fail_independently(self):
        calls = [call()]
        checks = [{"checks": [{"check_id": "static"}]}]
        observed = [marker("role", "start", "call-1", START)]
        summary = {"role_event_summaries": [{"assignment_id": "call-1"}],
                   "observation_reconciliation": {"start_count": 1, "terminal_count": 0,
                                                  "start_without_terminal": [{"kind": "role"}]}}
        _, errors = event_reconciliation(calls, checks, observed, summary)
        self.assertIn("role_assignment_markers_do_not_match_call_receipts", errors)
        self.assertIn("native_check_markers_do_not_match_check_receipts", errors)
        self.assertIn("role_open_intervals", errors)

    def test_summary_usage_mismatch_is_not_accepted(self):
        calls = [call()]
        profile, _ = usage_profile(calls)
        summary = {"usage": {"call_count": 2,
                             "reported_usage": {key: 0 for key in profile["fields"]},
                             "missing_call_count": {key: 0 for key in profile["fields"]},
                             "derived_uncached_input_tokens": 0,
                             "combined_input_plus_output_tokens": 0}}
        errors = summary_usage_errors(summary, calls, profile)
        self.assertIn("summary_call_count_mismatch", errors)
        self.assertIn("summary_usage_mismatch:input_tokens", errors)
        self.assertIn("summary_input_output_mismatch", errors)

    def test_missing_terminal_is_incomplete_not_zero_latency(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            episode = root / "cell"
            episode.mkdir()
            (episode / "started.json").write_text(json.dumps({"utc": START}))
            record, calls, _, errors = episode_read(root, {"id": "cell"}, require_complete=True)
            self.assertFalse(record["complete"])
            self.assertIsNone(record["episode_elapsed_seconds"])
            self.assertFalse(calls)
            self.assertIn("episode_missing_terminal", errors)

    def test_negative_interval_refused(self):
        with self.assertRaisesRegex(ValueError, "negative_overlap_interval"):
            peak_overlap([(END, START)])


if __name__ == "__main__":
    unittest.main()
