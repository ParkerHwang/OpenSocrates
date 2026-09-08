"""Public-byte verifier mutations against synthetic local/downloaded asset sets."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from verify_published_release import expected_asset_names, verify_public_bytes


def fixture(root: Path):
    local = root / "local"
    public = root / "public"
    local.mkdir()
    public.mkdir()
    names = expected_asset_names("1.3.0")
    installer = root / "installer.mjs"
    installer.write_text("synthetic installer")
    for asset in names:
        if asset.endswith(".zip.sha256"):
            continue
        data = (
            installer.read_bytes()
            if asset == "opensocrates.mjs"
            else ("synthetic " + asset).encode()
        )
        if asset != "opensocrates.mjs":
            (local / asset).write_bytes(data)
        (public / asset).write_bytes(data)
    for asset in names:
        if asset.endswith(".zip.sha256"):
            zipname = asset.removesuffix(".sha256")
            digest = hashlib.sha256((local / zipname).read_bytes()).hexdigest()
            text = f"{digest}  {zipname}\n"
            (local / asset).write_text(text)
            (public / asset).write_text(text)
    metadata = {
        "id": 1,
        "tag_name": "v1.3.0",
        "draft": False,
        "published_at": "2026-09-08T00:00:00Z",
        "assets": [{"name": n} for n in names],
    }
    metadata = deepcopy(metadata)
    return local, public, installer, metadata


class PublicReleaseVerificationChecks(unittest.TestCase):
    def test_public_identity_and_bytes(self):
        for mutation in (
            "none",
            "draft",
            "wrong-tag",
            "wrong-commit",
            "missing",
            "extra",
            "changed-zip",
            "changed-checksum",
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                local, public, installer, metadata = fixture(root)
                tag_commit = "a" * 40
                if mutation == "draft":
                    metadata["draft"] = True
                if mutation == "wrong-tag":
                    metadata["tag_name"] = "v1.2.1"
                if mutation == "wrong-commit":
                    tag_commit = "b" * 40
                if mutation == "missing":
                    metadata["assets"].pop()
                if mutation == "extra":
                    metadata["assets"].append({"name": "extra.zip"})
                zipname = "opensocrates-1.3.0-codex-plugin.zip"
                if mutation == "changed-zip":
                    (public / zipname).write_bytes(b"altered")
                if mutation == "changed-checksum":
                    (public / (zipname + ".sha256")).write_text("0" * 64 + "  " + zipname + "\n")
                if mutation == "none":
                    self.assertEqual(
                        verify_public_bytes(
                            metadata, "1.3.0", "a" * 40, tag_commit, local, public, installer
                        )["status"],
                        "pass",
                    )
                else:
                    with self.assertRaises(ValueError):
                        verify_public_bytes(
                            metadata, "1.3.0", "a" * 40, tag_commit, local, public, installer
                        )


if __name__ == "__main__":
    unittest.main()
