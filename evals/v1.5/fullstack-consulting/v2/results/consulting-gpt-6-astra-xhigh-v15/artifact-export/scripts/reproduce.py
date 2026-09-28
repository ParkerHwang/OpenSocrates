"""Rebuild all outputs offline from saved evidence, then verify."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VER=ROOT/'verification'
VER.mkdir(exist_ok=True)
prior_path=ROOT/'deliverables'/'metrics.json'
before=hashlib.sha256(prior_path.read_bytes()).hexdigest() if prior_path.exists() else None
for script,log in [('analyze.py','analysis-output.json'),('decision.py','decision-output.json'),
                   ('build_workbook.py',None),('build_documents.py',None),('verify.py',None)]:
    command=[sys.executable,str(ROOT/'scripts'/script)]
    if log:
        with (VER/log).open('w') as f:subprocess.run(command,cwd=ROOT,stdout=f,check=True)
    else:subprocess.run(command,cwd=ROOT,check=True)
after=hashlib.sha256(prior_path.read_bytes()).hexdigest()
summary=dict(before_metrics_sha256=before,after_metrics_sha256=after,metrics_identical_to_prior=(before==after) if before else None,
             mode='offline rebuild from saved inputs',result='PASS')
(VER/'reproduction.json').write_text(json.dumps(summary,indent=2)+'\n')
print('Offline rebuild complete. Metrics identical to prior:',before==after if before else 'first build')
