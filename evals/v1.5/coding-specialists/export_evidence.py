"""Publish synthetic terminal evidence while retaining original local locks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def export(boundary):
    output = boundary / "evidence"
    entries = []
    for source in sorted((boundary / "results").rglob('*')):
        if not source.is_file() or source.name in {"progress.json", ".progress.tmp"}:
            continue
        assert not source.is_symlink()
        relative = source.relative_to(boundary / "results")
        raw = source.read_bytes()
        public, note = raw, None
        if source.name == "TOOLING.md":
            text = raw.decode()
            text = re.sub(r"/Users/[^\s]+/python/bin/python3", "<BUNDLED_PYTHON>", text)
            public = text.encode()
            if public != raw:
                note = "Only the local interpreter path in environment instructions was replaced by BUNDLED_PYTHON. Business source is unchanged."
        assert b"/Users/" not in public, relative
        assert not re.search(rb"(?<![A-Za-z0-9_])sk-(?:proj-)?[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{30,}\.", public), relative
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == public, relative
        else:
            with target.open('xb') as stream:
                stream.write(public)
        entries.append({'path':relative.as_posix(),'original_sha256':digest(raw),'export_sha256':digest(public),'redaction':note})
    record={'schema':'opensocrates.specialist-public-evidence/1','boundary':boundary.name,
            'original_results_preserved':True,'business_source_changed':False,
            'snapshot_lock_note':'snapshot.json preserves original local hashes. This export map binds public bytes and explicitly identifies environment-only redactions.',
            'excluded_transient_files':['progress.json','.progress.tmp'],'files':entries}
    target=boundary/'export-map.json'
    if target.exists():
        assert json.loads(target.read_text())==record
    else:
        target.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'boundary':boundary.name,'files':len(entries),'environment_redactions':sum(x['redaction'] is not None for x in entries)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('boundary',type=Path)
    export(parser.parse_args().boundary.resolve())
