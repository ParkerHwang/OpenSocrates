"""Package the complete reproducible handoff and verify the archive inventory."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
DEST=OUT/'Meridian_complete_handoff.zip'
MANIFEST=OUT/'handoff_manifest.json'
paths=[ROOT/n for n in ['README.md','VERIFICATION.md','requirements.txt','TASK.md','TOOLING.md']]
for folder in ['analysis','deliverables','evidence','verification']:
    paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p not in [DEST,MANIFEST] and p.suffix!='.pyc' and '__pycache__' not in p.parts)
paths=sorted(set(paths))
inventory=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]
MANIFEST.write_text(json.dumps({'generated_at_utc':datetime.now(timezone.utc).isoformat(),'files':inventory,'note':'Manifest excludes itself and the enclosing ZIP. All listed files are contained in the archive.'},indent=2)+'\n')
with zipfile.ZipFile(DEST,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in paths+[MANIFEST]:z.write(p,'Meridian_parts/'+str(p.relative_to(ROOT)))
with zipfile.ZipFile(DEST) as z:
    assert z.testzip() is None
    for r in inventory:assert hashlib.sha256(z.read('Meridian_parts/'+r['path'])).hexdigest()==r['sha256']
print(f'Packaged and verified {len(inventory)+1} files: {DEST.name} ({DEST.stat().st_size/1e6:.2f} MB)')
