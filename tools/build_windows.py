"""Build native Windows distributions without a Unix shell or development Python at use time."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from build_content_hosts import build_content_host
from build_plugins import generate_plugin
from release_check import _write_deterministic_zip, _write_package_checksums

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("Build on native Windows x64; cross-compilation is not supported")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    environment = {**os.environ, "PYTHONUTF8": "1"}
    for host in ("codex",):
        subprocess.run(
            [
                sys.executable,
                "tools/build_runtime.py",
                "runtime",
                "--target",
                "windows-x64",
                "--runtime-profile",
                host,
                "--report",
                f"build/evidence/runtime-build-windows-{host}.json",
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        package = ROOT / "dist" / f"{host}-windows-x64"
        generate_plugin(root=ROOT, host=host, target="windows-x64", output=package)
        _write_package_checksums(package)
        archive = ROOT / "dist" / f"opensocrates-{version}-{host}-plugin-windows-x64.zip"
        _write_deterministic_zip(package, archive)
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        archive.with_suffix(".zip.sha256").write_text(
            f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n"
        )
        print(
            json.dumps(
                {"host": host, "target": "windows-x64", "archive": archive.name, "sha256": digest}
            )
        )
    content_archives = []
    for host, kind in (("claude-chat", "skills"), ("antigravity", "plugin")):
        package = ROOT / "dist" / f"{host}-content"
        build_content_host(root=ROOT, host=host, output=package)
        archive = ROOT / "dist" / f"opensocrates-{version}-{host}-{kind}.zip"
        _write_deterministic_zip(package, archive, content_only=True)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.with_suffix(".zip.sha256").write_text(
            f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n"
        )
        content_archives.append(archive.relative_to(ROOT).as_posix())
        print(
            json.dumps(
                {"host": host, "target": "content-only", "archive": archive.name, "sha256": digest}
            )
        )
    subprocess.run(
        [
            sys.executable,
            "tools/build_sbom.py",
            "--root",
            str(ROOT),
            "--output",
            "build/evidence/windows-sbom.spdx.json",
            "--report",
            "build/evidence/windows-sbom.json",
            "--artifact",
            f"dist/opensocrates-{version}-codex-plugin-windows-x64.zip",
            *[part for name in content_archives for part in ("--artifact", name)],
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
