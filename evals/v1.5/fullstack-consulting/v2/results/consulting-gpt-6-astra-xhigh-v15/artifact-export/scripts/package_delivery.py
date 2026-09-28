"""Create a self-contained delivery bundle without caches or a recursive ZIP."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
files=[ROOT/name for name in ['README.md','requirements.txt','TASK.md','TOOLING.md']]
for dirname in ['raw','scripts','deliverables','verification']:
    files += [p for p in (ROOT/dirname).rglob('*') if p.is_file() and '__pycache__' not in p.parts
              and p.suffix!='.zip' and p.name!='delivery-manifest.json']
# ECB's original ZIP is evidence and must remain in the bundle.
files.append(ROOT/'raw'/'ecb-history.zip')
files=sorted(set(files))
manifest=[dict(file=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
mp=OUT/'delivery-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
bundle=OUT/'Meridian_delivery_bundle.zip'
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for path in files+[mp]:z.write(path,path.relative_to(ROOT))
with zipfile.ZipFile(bundle) as z:
    assert z.testzip() is None
    for item in manifest:assert hashlib.sha256(z.read(item['file'])).hexdigest()==item['sha256']
print(f'Packaged and checked {len(files)+1} files: {bundle.name} ({bundle.stat().st_size:,} bytes)')
