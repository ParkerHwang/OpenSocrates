"""Final Chat ZIP mutations; staged-tree presence cannot substitute for archive bytes."""

from __future__ import annotations

import json
import shutil
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from claude_chat_evidence import export_only_contract
from release_check import (
    _build_claude_chat_skills,
    _verify_claude_chat_provenance,
    _verify_claude_chat_skills,
    _write_deterministic_zip,
)

ROOT = Path(__file__).resolve().parents[1]


class ChatArchiveIntegrityChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stage = _build_claude_chat_skills(ROOT)
        cls.bundle = json.loads((ROOT / "content/compiled-content.bundle.json").read_text())

    def test_exact_archive_and_mutations(self):
        for mutation in (
            "none",
            "missing-ko",
            "altered-body",
            "duplicate",
            "extra",
            "special",
            "trivial",
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                stage = root / "dist/claude-chat-skills"
                shutil.copytree(self.stage, stage)
                (root / "content").mkdir()
                shutil.copy2(
                    ROOT / "content/compiled-reasoning-content.bundle.json",
                    root / "content/compiled-reasoning-content.bundle.json",
                )
                shutil.copytree(
                    ROOT / "plugin-src/shared/decision", root / "plugin-src/shared/decision"
                )
                receipt = root / "docs/evidence/claude-chat-upload-probe-v1.3.0.json"
                receipt.parent.mkdir(parents=True)
                receipt.write_text(json.dumps(export_only_contract("1.3.0", 3)))
                archive = root / "dist/opensocrates-1.3.0-claude-chat-skills.zip"
                _write_deterministic_zip(stage, archive)
                if mutation != "none":
                    with zipfile.ZipFile(archive) as z:
                        entries = [(i, z.read(i)) for i in z.infolist()]
                    target = "opensocrates/references/decision/methods/ko/trade-off-analysis.md"
                    with warnings.catch_warnings(), zipfile.ZipFile(archive, "w") as z:
                        warnings.simplefilter("ignore", UserWarning)
                        for info, data in entries:
                            if mutation == "trivial" and info.filename != "opensocrates/SKILL.md":
                                continue
                            if mutation == "missing-ko" and info.filename == target:
                                continue
                            if mutation == "altered-body" and info.filename == target:
                                data += b"changed"
                            if mutation == "special" and info.filename == target:
                                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                            z.writestr(info, data)
                            if mutation == "duplicate" and info.filename == target:
                                z.writestr(info, data)
                        if mutation == "extra":
                            z.writestr("opensocrates/unexpected.txt", "extra")
                expected = "pass" if mutation == "none" else "fail"
                self.assertEqual(
                    _verify_claude_chat_skills(root, "1.3.0", self.bundle)["status"], expected
                )
                self.assertEqual(
                    _verify_claude_chat_provenance(root, "1.3.0", 3)["status"], expected
                )


if __name__ == "__main__":
    unittest.main()
