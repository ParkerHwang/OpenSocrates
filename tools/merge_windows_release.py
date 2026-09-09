"""Bind separately validated Windows assets into the macOS-built release inventory."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from release_check import _write_root_checksums


def merge(root: Path) -> None:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    dist = root / "dist"
    manifest_path = dist / f"opensocrates-{version}-release-manifest.json"
    limitations_path = dist / f"opensocrates-{version}-limitations.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    limitations = json.loads(limitations_path.read_text(encoding="utf-8"))
    windows = {}
    for host in ("claude", "codex"):
        archive = dist / f"opensocrates-{version}-{host}-plugin-windows-x64.zip"
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        expected = archive.with_suffix(".zip.sha256").read_text(encoding="utf-8").split()
        if expected != [digest, archive.name]:
            raise ValueError("Windows transport checksum mismatch")
        with zipfile.ZipFile(archive) as bundle:
            identity = json.loads(bundle.read("release-manifest.json"))
        if (
            identity["product_version"] != version
            or identity["host"] != host
            or identity["runtime_targets"] != ["windows-x64"]
            or identity["source_tree_hash"] != manifest["source_tree_hash"]
            or identity["normalized_semantic_hash"] != manifest["normalized_semantic_hash"]
        ):
            raise ValueError("Windows archive source/platform identity mismatch")
        windows[host] = {"archive": archive.name, "sha256": digest, "target": "windows-x64"}
    manifest["windows_packages"] = windows
    limitations["native_release_targets"] = ["darwin-arm64", "windows-x64"]
    limitations["windows"] = {
        "launcher": "bin/launch.mjs",
        "automatic_updates": "unavailable; manual update required",
        "legacy_context_and_credential_copy": "unavailable",
        "clean_machine": "unvalidated",
        "arm64": "unvalidated",
        "live_delivery": "see candidate worklog; CI is not live evidence",
    }
    for path, document in ((manifest_path, manifest), (limitations_path, limitations)):
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
    _write_root_checksums(dist, version)


if __name__ == "__main__":
    merge(Path(__file__).resolve().parents[1])
