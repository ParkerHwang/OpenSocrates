"""Build native Windows distributions without a Unix shell or development Python at use time."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from build_plugins import generate_plugin
from release_check import _write_deterministic_zip, _write_package_checksums

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("Build on native Windows x64; cross-compilation is not supported")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    environment = {**os.environ, "PYTHONUTF8": "1"}
    for host in ("claude", "codex"):
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
