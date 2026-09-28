from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from protocol import sha
from qualify_main import versions_for_cell


class VersionLineageControls(unittest.TestCase):
    def test_old_analysis_is_not_paired_with_later_memo(self):
        task = {"required_artifacts": ["analysis.go", "metrics.json", "sources.json", "memo.md"],
                "units": [
                    {"unit_id": "O-analysis", "owned_paths": ["analysis.go", "metrics.json", "sources.json"]},
                    {"unit_id": "O-document", "owned_paths": ["memo.md"]},
                ]}
        with tempfile.TemporaryDirectory() as raw:
            episode = Path(raw)
            analysis_versions = []
            for number, qualified in ((1, False), (2, True)):
                files = {name: f"analysis {number} {name}\n".encode()
                         for name in task["units"][0]["owned_paths"]}
                for name, data in files.items():
                    path = episode / f"candidate/versions/O-analysis/v{number}" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                analysis_versions.append({"version": number, "qualified": qualified,
                                          "artifacts": [{"path": name, "sha256": "sha256:" + sha(data)}
                                                        for name, data in files.items()]})
            memo = b"memo bound to analysis 2\n"
            path = episode / "candidate/versions/O-document/v1/memo.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(memo)
            document_versions = [{"version": 1, "qualified": True,
                                  "artifacts": [{"path": "memo.md", "sha256": "sha256:" + sha(memo)}]}]
            response = {"units": [
                {"unit_id": "O-analysis", "versions": analysis_versions},
                {"unit_id": "O-document", "versions": document_versions},
            ]}
            (episode / "response.json").write_text(json.dumps(response))
            cell = {"arm": "D"}
            variants = versions_for_cell(cell, task, episode)
            self.assertEqual([item[0] for item in variants], [
                "O-analysis-v1", "O-analysis-v2", "O-analysis-v2-O-document-v1"])
            self.assertEqual([item[1] for item in variants], ["analysis", "analysis", "full"])
            self.assertTrue(variants[2][2]["analysis.go"].startswith(b"analysis 2"))
            response["units"][1]["versions"] = []
            (episode / "response.json").write_text(json.dumps(response))
            self.assertEqual(len(versions_for_cell(cell, task, episode)), 2)


if __name__ == "__main__":
    unittest.main()
