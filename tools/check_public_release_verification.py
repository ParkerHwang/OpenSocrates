"""Public-byte verifier mutations against synthetic local/downloaded asset sets."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from verify_published_release import expected_asset_names, verify_public_bytes

ROOT = Path(__file__).resolve().parents[1]


def workflow_script(name: str) -> str:
    lines = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8").splitlines()
    start = lines.index(f"      - name: {name}")
    run = next(index for index in range(start + 1, len(lines)) if lines[index] == "        run: |")
    result = []
    for line in lines[run + 1 :]:
        if line and not line.startswith("          "):
            break
        result.append(line[10:] if line else "")
    return "\n".join(result) + "\n"


def fixture(root: Path, version: str = "1.3.0"):
    local = root / "local"
    public = root / "public"
    local.mkdir()
    public.mkdir()
    names = expected_asset_names(version)
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
        "tag_name": f"v{version}",
        "draft": False,
        "immutable": True,
        "published_at": "2026-09-08T00:00:00Z",
        "assets": [{"name": n} for n in names],
    }
    metadata = deepcopy(metadata)
    return local, public, installer, metadata


class PublicReleaseVerificationChecks(unittest.TestCase):
    def _file_symlink(self, link: Path, target: Path) -> None:
        try:
            link.symlink_to(target)
        except OSError as error:
            if os.name == "nt" and error.winerror == 1314:
                self.skipTest(
                    f"{link.name}: file symlink fixture requires Windows privilege "
                    "(WinError 1314); other public-byte mutations still run"
                )
            raise

    @unittest.skipUnless(shutil.which("bash"), "release shell fixture requires Bash")
    def test_workflow_publishes_exact_1_4_and_1_5_assets_with_a_fake_publisher(self):
        script = workflow_script("Publish GitHub Release")
        for version in ("1.4.0", "1.5.0"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                binary = root / "bin"
                binary.mkdir()
                fake = binary / "gh"
                fake.write_text(
                    "#!/usr/bin/env python3\n"
                    "import json, os, sys\n"
                    "if sys.argv[1:3] == ['release', 'view']: sys.exit(1)\n"
                    "if sys.argv[1:3] != ['release', 'create']: sys.exit(2)\n"
                    "with open(os.environ['CAPTURE'], 'w') as out: json.dump(sys.argv[1:], out)\n",
                    encoding="utf-8",
                )
                fake.chmod(0o755)
                capture = root / "capture.json"
                environment = {
                    "PATH": f"{binary}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{os.defpath}",
                    "RELEASE_VERSION": version,
                    "RELEASE_TAG": f"v{version}",
                    "CAPTURE": str(capture),
                }
                subprocess.run(
                    [shutil.which("bash"), "-c", script],
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                arguments = json.loads(capture.read_text())
                assets = arguments[3 : arguments.index("--verify-tag")]
                self.assertEqual(
                    {Path(asset).name for asset in assets}, expected_asset_names(version)
                )
                self.assertEqual(len(assets), len(set(assets)))

    @unittest.skipUnless(shutil.which("bash"), "release shell fixture requires Bash")
    def test_dependency_staging_precedes_inventory_merge_and_preserves_source_bytes(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("Stage standalone installer dependency for the Mac release profiles"),
            workflow.index(".venv/bin/python tools/merge_windows_release.py"),
        )
        script = workflow_script(
            "Stage standalone installer dependency for the Mac release profiles"
        )
        for version in ("1.4.0", "1.5.0"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                installer = root / "installer"
                installer.mkdir()
                source = installer / "managed-hosts.mjs"
                source.write_bytes(b"synthetic standalone runtime dependency\n")
                subprocess.run(
                    [shutil.which("bash"), "-c", script],
                    cwd=root,
                    env={
                        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.defpath}",
                        "RELEASE_VERSION": version,
                    },
                    capture_output=True,
                    text=True,
                    check=True,
                )
                destination = root / "dist/managed-hosts.mjs"
                if version == "1.5.0":
                    self.assertEqual(destination.read_bytes(), source.read_bytes())
                else:
                    self.assertFalse(destination.exists())

    def test_versioned_asset_inventory_preserves_legacy_releases(self):
        before = expected_asset_names("1.3.0")
        windows = expected_asset_names("1.4.0")
        macos = expected_asset_names("1.5.0")
        self.assertEqual(len(before), 7)
        self.assertEqual(len(windows), 10)
        self.assertEqual(len(macos), 17)
        self.assertNotIn("managed-hosts.mjs", before | windows)
        self.assertIn("managed-hosts.mjs", macos)
        for host, kind in (
            ("claude", "plugin"),
            ("claude-chat", "skills"),
            ("antigravity", "plugin"),
        ):
            archive = f"opensocrates-1.5.0-{host}-{kind}.zip"
            self.assertIn(archive, macos)
            self.assertIn(archive + ".sha256", macos)
        self.assertEqual(
            expected_asset_names("1.5.1"), {name.replace("1.5.0", "1.5.1") for name in macos}
        )

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

    def test_mutable_github_release_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            local, public, installer, metadata = fixture(Path(name))
            metadata["immutable"] = False
            with self.assertRaisesRegex(ValueError, "immutable release protection"):
                verify_public_bytes(metadata, "1.3.0", "a" * 40, "a" * 40, local, public, installer)

    def test_1_4_public_bytes_still_verify_without_addon_assets(self):
        with tempfile.TemporaryDirectory() as name:
            local, public, installer, metadata = fixture(Path(name), "1.4.0")
            self.assertEqual(
                verify_public_bytes(
                    metadata, "1.4.0", "a" * 40, "a" * 40, local, public, installer
                )["status"],
                "pass",
            )

    def test_1_5_addon_archives_and_standalone_dependency_are_exact_public_bytes(self):
        additions = (
            "opensocrates-1.5.0-claude-plugin.zip",
            "opensocrates-1.5.0-claude-chat-skills.zip",
            "opensocrates-1.5.0-antigravity-plugin.zip",
            "managed-hosts.mjs",
        )
        for mutation in (
            "none",
            "missing",
            "changed",
            "changed-sidecar",
            "missing-local",
            "linked",
        ):
            for asset in additions:
                if mutation == "changed-sidecar" and not asset.endswith(".zip"):
                    continue
                with (
                    self.subTest(mutation=mutation, asset=asset),
                    tempfile.TemporaryDirectory() as name,
                ):
                    local, public, installer, metadata = fixture(Path(name), "1.5.0")
                    if mutation == "missing":
                        metadata["assets"] = [
                            row for row in metadata["assets"] if row["name"] != asset
                        ]
                    elif mutation == "changed":
                        (public / asset).write_bytes(b"tampered public asset")
                    elif mutation == "changed-sidecar":
                        sidecar = asset + ".sha256"
                        altered = "0" * 64 + "  " + asset + "\n"
                        # Equal altered local/public bytes must still fail the ZIP/digest relation.
                        (local / sidecar).write_text(altered)
                        (public / sidecar).write_text(altered)
                    elif mutation == "missing-local":
                        (local / asset).unlink()
                    elif mutation == "linked":
                        (public / asset).unlink()
                        self._file_symlink(public / asset, local / asset)
                    if mutation == "none":
                        result = verify_public_bytes(
                            metadata, "1.5.0", "a" * 40, "a" * 40, local, public, installer
                        )
                        self.assertEqual(result["status"], "pass")
                        self.assertEqual(len(result["files"]), 17)
                        self.assertTrue(
                            any(row["name"] == "managed-hosts.mjs" for row in result["files"])
                        )
                    else:
                        with self.assertRaises(ValueError):
                            verify_public_bytes(
                                metadata, "1.5.0", "a" * 40, "a" * 40, local, public, installer
                            )


if __name__ == "__main__":
    unittest.main()
