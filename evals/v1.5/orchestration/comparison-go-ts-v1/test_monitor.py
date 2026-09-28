"""Read-only monitor excludes qualification workspaces from cell counts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import monitor


class MonitorControls(unittest.TestCase):
    def test_S_qualification_directory_is_not_a_25th_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cells = ["S-gpt-6-sol-high-A", "S-gpt-6-sol-high-B"]
            for cell in cells:
                episode = root / cell
                episode.mkdir()
                (episode / "started.json").write_text("{}\n")
                (episode / "terminal.json").write_text('{"status":"terminal"}\n')
                (episode / "observation.jsonl").write_text(
                    '{"kind":"role","phase":"start"}\n'
                    '{"kind":"role","phase":"terminal"}\n')
            qualification = root / "external-qualification-S"
            qualification.mkdir()
            (qualification / "index.json").write_text(json.dumps({"variants": [
                {"status": "deterministic_pass"}, {"status": "deterministic_failure"}]}))
            (root / "dispatch-index.json").write_text(json.dumps({"cell_results": [
                {"cell_id": cell} for cell in cells]}))
            client = root / "codex"
            client.write_bytes(b"synthetic client")
            with patch.object(monitor, "CLIENT", client):
                result = monitor.snapshot(root)
                self.assertEqual(set(result["by_arm"]), {"A", "B"})
                self.assertEqual(sum(row["claimed"] for row in result["by_arm"].values()), 2)
                self.assertEqual((result["role_started"], result["role_terminal"]), (2, 2))
                self.assertTrue(result["external_index_present"])
                self.assertEqual(result["externally_deterministic_passed_variants"], 1)
                (root / "dispatch-index.json").unlink()
                fallback = monitor.snapshot(root)
                self.assertEqual(set(fallback["by_arm"]), {"A", "B"})
                self.assertTrue(fallback["external_index_present"])

    def test_O_path_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode = root / "O-gpt-6-sol-high-D"
            episode.mkdir()
            (episode / "started.json").write_text("{}\n")
            (root / "external-qualification").mkdir()
            (root / "external-qualification/index.json").write_text('{"variants":[]}\n')
            client = root / "codex"
            client.write_bytes(b"synthetic client")
            with patch.object(monitor, "CLIENT", client):
                result = monitor.snapshot(root, frozen_cell_ids={episode.name})
            self.assertEqual(result["by_arm"]["D"]["claimed"], 1)
            self.assertTrue(result["external_index_present"])


if __name__ == "__main__":
    unittest.main()
