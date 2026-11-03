#!/usr/bin/env python3
"""Build experimental skill-only archives from the same candidate source."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "plugin-src" / "experimental-output-brief"
OUTPUT = ROOT / "build" / "experiments" / "v2-output-brief"


def write_archive(path: Path, entries: dict[str, Path]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in sorted(entries.items()):
            item = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, source.read_bytes())


def main() -> None:
    skill = SOURCE / "skills" / "output-brief" / "SKILL.md"
    scanner = SOURCE / "skills" / "output-brief" / "scripts" / "evidence_scan.py"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    claude = OUTPUT / "output-brief-claude-skill.zip"
    plugin = OUTPUT / "output-brief-openai-plugin.zip"
    write_archive(
        claude,
        {
            "output-brief/SKILL.md": skill,
            "output-brief/scripts/evidence_scan.py": scanner,
        },
    )
    write_archive(
        plugin,
        {
            "plugin.json": SOURCE / "plugin.json",
            "skills/output-brief/SKILL.md": skill,
            "skills/output-brief/scripts/evidence_scan.py": scanner,
        },
    )
    print(f"Built {claude}")
    print(f"Built {plugin}")


if __name__ == "__main__":
    main()
