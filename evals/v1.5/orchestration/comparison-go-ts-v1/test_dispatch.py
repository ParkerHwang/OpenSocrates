from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from run_main import dispatch_summary


class DispatchObservationControls(unittest.TestCase):
    def test_actual_overlap_and_pressure_are_from_markers(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            cells = [{"id": "a"}, {"id": "b"}]
            for cell, start, end in (
                ("a", "2026-09-28T00:00:00+00:00", "2026-09-28T00:00:04+00:00"),
                ("b", "2026-09-28T00:00:01+00:00", "2026-09-28T00:00:05+00:00"),
            ):
                path = root / cell
                path.mkdir()
                resource = {"host_load_1m_5m_15m": [2.0, 1.0, 1.0],
                            "host_codex_process_count": 3, "host_codex_rss_kib": 900}
                (path / "started.json").write_text(json.dumps({"utc": start, "resource": resource}))
                (path / "terminal.json").write_text(json.dumps({"utc": end, "resource": resource}))
                (path / "observation.jsonl").write_text("\n".join((
                    json.dumps({"kind": "role", "assignment_id": cell, "phase": "start", "utc": start}),
                    json.dumps({"kind": "role", "assignment_id": cell, "phase": "terminal", "utc": end}),
                )) + "\n")
            (root / "b/observation.jsonl").write_text(
                (root / "b/observation.jsonl").read_text() + "not-json\n")
            result = dispatch_summary(root, cells, [], 2)
            self.assertEqual(result["observed_peak_episode_overlap"], 2)
            self.assertEqual(result["observed_peak_role_overlap"], 2)
            self.assertEqual(result["malformed_observation_lines"], 1)
            self.assertEqual(result["max_host_codex_rss_kib"], 900)
            (root / "b/terminal.json").write_text("broken-marker\n")
            partial = dispatch_summary(root, cells, [], 2)
            self.assertEqual(partial["malformed_episode_markers"], 1)
            self.assertEqual(partial["observed_peak_episode_overlap"], 1)
            self.assertFalse(partial["episode_overlap_complete"])
            (root / "b/terminal.json").unlink()
            missing = dispatch_summary(root, cells, [], 2)
            self.assertEqual(missing["episodes_started_without_terminal"], ["b"])
            self.assertEqual(missing["pressure_samples"], 3)
            self.assertFalse(missing["episode_overlap_complete"])


if __name__ == "__main__":
    unittest.main()
