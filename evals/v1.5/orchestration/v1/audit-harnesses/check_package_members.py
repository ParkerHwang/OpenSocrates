"""Compare exact public and embedded ZIP members with canonical source bytes."""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    embedded = "runtime/darwin-arm64/opensocrates-runtime/_internal/"
    pairs = []
    for path in sorted((root / "schemas/v1").glob("*.json")):
        relative = "schemas/v1/" + path.name
        pairs.extend([(path, relative), (path, embedded + relative)])
    for group in ("orchestration", "coding-specialists"):
        for path in sorted((root / "plugin-src/shared" / group).rglob("*")):
            if path.is_file():
                relative = str(path.relative_to(root / "plugin-src/shared" / group))
                pairs.extend([(path, "skills/opensocrates/references/" + group + "/" + relative),
                              (path, embedded + "plugin-src/shared/" + group + "/" + relative)])
    for locale in ("en", "ko"):
        path = root / f"plugin-src/shared/assistance/verification.{locale}.md"
        pairs.extend([(path, f"skills/opensocrates/references/assistance/verification.{locale}.md"),
                      (path, embedded + f"plugin-src/shared/assistance/verification.{locale}.md")])
    rows = []
    with zipfile.ZipFile(args.archive) as archive:
        names = archive.namelist()
        for source, member in pairs:
            expected = source.read_bytes()
            match = names.count(member) == 1 and archive.read(member) == expected
            rows.append({"source": str(source.relative_to(root)), "member": member,
                         "match": match, "sha256": hashlib.sha256(expected).hexdigest()})
    result = {
        "schema": "opensocrates.orchestration.package-members/1",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "checked_members": len(rows), "all_match": all(row["match"] for row in rows),
        "matching_rule": "Exact ZIP paths; external and embedded schemas are distinct members.",
        "members": rows,
    }
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("checked_members", "all_match", "archive_sha256")}))
    return 0 if result["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
