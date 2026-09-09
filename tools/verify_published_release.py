"""Verify immutable public release bytes against this run's validated local assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from release_identity import remote_tag_commit

HOSTS = ("antigravity", "claude", "codex", "cursor", "grok", "opencode")


def expected_asset_names(version: str) -> set[str]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("invalid release version")
    zips = {f"opensocrates-{version}-{host}-plugin.zip" for host in HOSTS}
    zips.add(f"opensocrates-{version}-claude-chat-skills.zip")
    windows = tuple(map(int, version.split("."))) >= (1, 4, 0)
    if windows:
        zips.update(
            f"opensocrates-{version}-{host}-plugin-windows-x64.zip" for host in ("claude", "codex")
        )
    return (
        ({"windows.ps1"} if windows else set())
        | zips
        | {name + ".sha256" for name in zips}
        | {
            f"opensocrates-{version}-release-manifest.json",
            f"opensocrates-{version}-limitations.json",
            f"opensocrates-{version}-sbom.spdx.json",
            f"opensocrates-{version}-checksums.sha256",
            "opensocrates.mjs",
        }
    )


def sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("release member is not a regular file")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify_public_bytes(
    metadata: dict[str, Any],
    version: str,
    commit: str,
    tag_commit: str,
    local: Path,
    downloaded: Path,
    installer: Path,
) -> dict[str, Any]:
    expected = expected_asset_names(version)
    names = [asset.get("name") for asset in metadata.get("assets", [])]
    if (
        metadata.get("tag_name") != f"v{version}"
        or metadata.get("draft") is not False
        or not metadata.get("published_at")
    ):
        raise ValueError("release is not the exact published tag")
    if metadata.get("immutable") is not True:
        raise ValueError("GitHub immutable release protection is not enabled for this release")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or tag_commit != commit:
        raise ValueError("published tag source mismatch")
    if len(names) != len(set(names)) or set(names) != expected:
        raise ValueError("public asset inventory mismatch")
    files = []
    for name in sorted(expected):
        original = installer if name == "opensocrates.mjs" else local / name
        public = downloaded / name
        digest = sha256(original)
        if sha256(public) != digest:
            raise ValueError(f"published bytes mismatch: {name}")
        if name.endswith(".zip"):
            sidecar = (downloaded / (name + ".sha256")).read_text().strip()
            if sidecar != f"{digest}  {name}":
                raise ValueError(f"published checksum mismatch: {name}")
        files.append({"name": name, "bytes": public.stat().st_size, "sha256": "sha256:" + digest})
    return {
        "schema": "opensocrates.public-release-verification/1.0.0",
        "status": "pass",
        "version": version,
        "tag": f"v{version}",
        "source_commit": commit,
        "public_release_id": metadata.get("id"),
        "github_release_immutable": True,
        "files": files,
        "scope": (
            "published bytes equal this run's prevalidated local assets and GitHub protects the "
            "release assets and tag; no cloud activation inference"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument(
        "--report", type=Path, default=Path("build/evidence/public-release-verified.json")
    )
    args = parser.parse_args()
    version = Path("VERSION").read_text().strip()
    tag = f"v{version}"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        raise SystemExit("invalid repository")
    metadata = json.loads(
        subprocess.check_output(["gh", "api", f"repos/{args.repo}/releases/tags/{tag}"], text=True)
    )
    names = [x.get("name") for x in metadata.get("assets", [])]
    if len(names) != len(set(names)) or set(names) != expected_asset_names(version):
        raise SystemExit("public asset inventory mismatch")
    refs = subprocess.check_output(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        text=True,
    )
    with tempfile.TemporaryDirectory(prefix="opensocrates-public-verify-") as name:
        subprocess.run(
            ["gh", "release", "download", tag, "--repo", args.repo, "--dir", name],
            check=True,
            timeout=300,
        )
        report = verify_public_bytes(
            metadata,
            version,
            args.commit,
            remote_tag_commit(refs, tag),
            args.dist,
            Path(name),
            Path("installer/opensocrates.mjs"),
        )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print("public release verification: PASS (immutable GitHub release, exact assets and tag)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
