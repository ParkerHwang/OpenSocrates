"""Package only the requested project outputs, evidence and reproducible source."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'

def main():
    bundle=OUT/'meridian_handover.zip'
    files=[ROOT/name for name in ['README.md','requirements.txt','TASK.md','TOOLING.md']]
    for dirname in ['scripts','evidence','deliverables']:
        files += [p for p in (ROOT/dirname).rglob('*') if p.is_file() and p!=bundle and p.name!='handover_manifest.json' and '__pycache__' not in p.parts]
    files=sorted(set(files))
    manifest=[dict(file=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    manifest_path=OUT/'handover_manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[manifest_path]:z.write(p,p.relative_to(ROOT))
    with zipfile.ZipFile(bundle) as z:
        assert z.testzip() is None
        for r in manifest:
            assert hashlib.sha256(z.read(r['file'])).hexdigest()==r['sha256']
        assert z.read('TASK.md')==(ROOT/'TASK.md').read_bytes()
        assert z.read('TOOLING.md')==(ROOT/'TOOLING.md').read_bytes()
    print(json.dumps(dict(bundle=str(bundle.relative_to(ROOT)),file_count=len(files)+1,bytes=bundle.stat().st_size,sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),zip_crc_and_member_hashes_verified=True),indent=2))

if __name__=='__main__':main()
