"""Offline rebuild from the saved evidence; no source refresh or global changes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def main():
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT/'.deps')+os.pathsep+env.get('PYTHONPATH','')
    env['MPLCONFIGDIR']=str(ROOT/'.cache/matplotlib')
    path=ROOT/'deliverables/metrics.json'
    before=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    (ROOT/'deliverables/audit').mkdir(parents=True,exist_ok=True)
    for name in ['analyze.py','build_workbook.py','build_documents.py','verify.py','workbook_preview.py']:
        print('Running '+name,flush=True)
        if name=='analyze.py':
            with (ROOT/'deliverables/audit/analysis-summary.json').open('w') as out:
                subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,env=env,stdout=out,check=True)
        else:subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,env=env,check=True)
    after=hashlib.sha256(path.read_bytes()).hexdigest()
    result=dict(offline_rebuild_passed=True,prior_metrics_sha256=before,rebuilt_metrics_sha256=after,identical_metrics_to_prior_build=(before==after) if before else None,
                note='PDF/XLSX container metadata may change on rebuild; financial JSON is deterministic from saved inputs.')
    (ROOT/'deliverables/verification/reproduction.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
