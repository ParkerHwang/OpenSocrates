#!/usr/bin/env python3
"""Build a pinned, standard-library-only portable office evaluation kit."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from opensocrates.evaluation.hosts import PAYLOADS, payload_bytes  # noqa: E402

RUNTIME_FILES = (
    "__init__.py",
    "engine.py",
    "storage.py",
    "model.py",
    "pack.py",
    "report.py",
    "hosts.py",
    "server.py",
    "assets/index.html",
    "assets/style.css",
    "assets/app.js",
)
GUIDE_FILES = (
    "evaluation-lab.md",
    "evaluation-lab.ko.md",
    "evaluation-lab-casepacks.md",
    "evaluation-lab-casepacks.ko.md",
    "evaluation-lab-design.md",
    "evaluation-lab-contract.md",
    "evaluation-lab-review.md",
)


def _source_files() -> list[tuple[str, Path]]:
    from opensocrates.evaluation.pack import load_pack

    files = [("start-lab.py", ROOT / "tools/evaluation_lab.py")]
    for name in ("__init__.py", "version.py"):
        files.append(("src/opensocrates/" + name, ROOT / "src/opensocrates" / name))
    for name in RUNTIME_FILES:
        source = ROOT / "src/opensocrates/evaluation" / name
        files.append(("src/opensocrates/evaluation/" + name, source))
    pack_root = ROOT / "evals/office-work-v1"
    _, materials, _ = load_pack(pack_root)
    for name in ("pack.json", *sorted(materials)):
        files.append(("evals/office-work-v1/" + name, pack_root / name))
    for name in (
        "Start Lab.command",
        "Start Lab.cmd",
        "README.txt",
        "merge-exports.py",
        "payloads/manifest.json",
    ):
        files.append((name, ROOT / "tools/evaluation-lab" / name))
    for name in GUIDE_FILES:
        source = ROOT / "docs" / name
        if source.exists():
            files.append(("guides/" + name, source))
    files.append(("LICENSE", ROOT / "LICENSE"))
    return files


def _safe_source(source: Path) -> bool:
    try:
        relative = source.relative_to(ROOT)
        for candidate in (
            ROOT,
            *(ROOT / Path(*relative.parts[:end]) for end in range(1, len(relative.parts) + 1)),
        ):
            info = candidate.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                return False
        return source.is_file()
    except (OSError, ValueError):
        return False


def build(output: Path, payloads: Path) -> None:
    entries: dict[str, tuple[bytes, int]] = {}
    for name, source in _source_files():
        if not _safe_source(source):
            raise ValueError("unsafe_source")
        entries[name] = (source.read_bytes(), 0o755 if name.endswith(".command") else 0o644)
    for host, (name, _) in PAYLOADS.items():
        entries["payloads/" + name] = (payload_bytes(payloads, host), 0o644)
    identity = {
        "schema": "opensocrates.office-kit/1",
        "content_version": "1.5.3",
        "payload_release": "https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3",
        "files": {
            name: hashlib.sha256(raw).hexdigest() for name, (raw, _) in sorted(entries.items())
        },
    }
    entries["kit-manifest.json"] = (
        (json.dumps(identity, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        0o644,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, (raw, mode) in sorted(entries.items()):
            info = zipfile.ZipInfo(
                "OpenSocrates-Office-Lab/" + name, date_time=(2026, 10, 15, 0, 0, 0)
            )
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payloads-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist/opensocrates-office-evaluation-lab.zip"
    )
    args = parser.parse_args()
    try:
        build(args.output, args.payloads_dir)
    except Exception:
        print("Kit build unavailable: check pinned payloads, source files and a new output path.")
        return 1
    print(f"Portable kit created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
