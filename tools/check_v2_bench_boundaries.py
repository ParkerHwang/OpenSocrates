"""Check live-benchmark boundaries with local fake processes only."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from bench.adapters import run_command
from bench.run import _live_row


class BenchBoundaryChecks(unittest.TestCase):
    def test_future_condition_never_runs_a_global_command(self):
        case = {"id": "example"}
        condition = {"id": "opensocrates_v2", "future": True}
        env = {"OPENSOCRATES_BENCH_LIVE": "1", "OPENSOCRATES_BENCH_COMMAND": "anything"}
        with patch("bench.run.run_command") as run:
            row = _live_row(case, condition, 1, env)
        run.assert_not_called()
        self.assertEqual(row["status"], "model_unavailable")
        self.assertFalse(row["process_started"])

    def test_timeout_stops_ordinary_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "child-finished"
            child = (
                "import pathlib,sys,time; time.sleep(1); "
                "pathlib.Path(sys.argv[1]).write_text('finished')"
            )
            parent = (
                "import subprocess,sys,time; "
                "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]]); "
                "time.sleep(10)"
            )
            result = run_command(
                [sys.executable, "-c", parent, child, str(marker)],
                {},
                timeout=0.25,
                env=os.environ,
            )
            self.assertEqual(result["status"], "model_error")
            self.assertIn("timed out", result["reason"])
            time.sleep(1.2)
            self.assertFalse(marker.exists(), "timed-out child kept running")


if __name__ == "__main__":
    unittest.main()
