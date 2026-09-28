from __future__ import annotations

import tempfile
import json
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from export import export


class ExportControls(unittest.TestCase):
    def test_allowlist_excludes_profile_and_refuses_auth(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            results = root / "results"
            episode = results / "c"
            artifact = episode / "candidate/artifacts/a.go"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("package main\n")
            (episode / "started.json").write_text("{}\n")
            profile = episode / "home/.codex"
            profile.mkdir(parents=True)
            (profile / "config.toml").write_text("synthetic config\n")
            quarantine = episode / "quarantine/a1"
            quarantine.mkdir(parents=True)
            owned = b"package main\n"
            (quarantine / "a.go").write_bytes(owned)
            (quarantine / "metadata.json").write_text(json.dumps({
                "schema": "opensocrates.go-ts.candidate-diagnostic/2",
                "quarantined_owned_paths": ["a.go"],
                "owned_file_hashes": {"a.go": "sha256:" + hashlib.sha256(owned).hexdigest()},
            }))
            freeze = root / "freeze.json"
            freeze.write_text("{}\n")
            with patch("export.verify_freeze", return_value={"cell_ids": ["c"]}):
                target = root / "out.zip"
                export(results, freeze, "synthetic-sha", target)
                with ZipFile(target) as archive:
                    names = set(archive.namelist())
                self.assertIn("episodes/c/candidate/artifacts/a.go", names)
                self.assertIn("episodes/c/quarantine/a1/a.go", names)
                self.assertNotIn("episodes/c/home/.codex/config.toml", names)
                (profile / "auth.json").write_text("synthetic auth\n")
                with self.assertRaisesRegex(ValueError, "auth_copy_present"):
                    export(results, freeze, "synthetic-sha", root / "blocked.zip")
                (profile / "auth.json").unlink()
                (quarantine / "unexpected.py").write_text("unowned\n")
                with self.assertRaisesRegex(ValueError, "unallowlisted_quarantine_file"):
                    export(results, freeze, "synthetic-sha", root / "blocked-unowned.zip")


if __name__ == "__main__":
    unittest.main()
