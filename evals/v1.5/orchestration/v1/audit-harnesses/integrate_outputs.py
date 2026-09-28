"""Primary integration of byte-identical qualified synthetic artifacts, with native checks."""
import json, sys, tempfile
from pathlib import Path
repo=Path('$REPO')
sys.path.insert(0,str(repo/'src'))
from opensocrates.orchestration.adapter import CodexAdapter
from opensocrates.orchestration.paths import write_files, manifest, identity, verify_files
root=Path(__file__).parent
live=root/'live-v2'
fixture=Path('$FIXTURE')
dest=root/'integrated'
dest.mkdir(exist_ok=False)
origins={'software/design.json':live/'candidates/software/artifacts/design.json','software/pricing.py':live/'candidates/continuation/artifacts/pricing.py','office/calculation.json':live/'candidates/office/artifacts/calculation.json','office/report.md':live/'candidates/office/artifacts/report.md'}
files={name:path.read_bytes() for name,path in origins.items()}
write_files(dest,files)
assert verify_files(dest,files)
req=json.loads((live/'software.request.json').read_text())
python=req['units'][0]['checks'][0]['argv'][0]
adapter=CodexAdapter(req['client_path']);adapter.probe()
inputs={**files,'fixtures/cost_cases.json':(fixture/'fixtures/cost_cases.json').read_bytes(),'fixtures/country_effects.json':(fixture/'fixtures/country_effects.json').read_bytes(),'fixtures/prior.py':(live/'continuation-source/prior.py').read_bytes()}
for name in ['check_design.py','check_cost.py','check_calculation.py','check_report.py']:
 inputs['oracles/'+name]=(fixture/'oracles'/name).read_bytes()
inputs['oracles/check_continuation_v2.py']=(root/'check_continuation_v2.py').read_bytes()
args=[['design','oracles/check_design.py','software/design.json'],['cost','oracles/check_cost.py','software/pricing.py','fixtures/cost_cases.json'],['calculation','oracles/check_calculation.py','office/calculation.json','fixtures/country_effects.json'],['report','oracles/check_report.py','office/report.md','office/calculation.json','fixtures/country_effects.json'],['continuation','oracles/check_continuation_v2.py','software/pricing.py','fixtures/prior.py']]
receipts=[]
with tempfile.TemporaryDirectory(prefix='opensocrates-integrated-check-') as raw:
 cwd=Path(raw).resolve();write_files(cwd,inputs)
 for label,*argv in args:
  check={'check_id':label,'argv':[python,'-B',*argv],'obligation_ids':[label],'authorization_reference':'fixture:approved-final-byte-checks','expected_exit_code':0}
  receipts.append(adapter.check(check,cwd,inputs,identity(manifest(files))))
 assert verify_files(cwd,inputs)
report={'scope':'Primary integration of synthetic final delivery copies; no real project changed.','source_commit':'7893996357b7fcfaa058e91d4bc2694d5f1cb63c','artifacts':manifest(files),'origin_paths':{k:str(v.relative_to(root)) for k,v in origins.items()},'checks':receipts,'all_passed':all(x['status']=='passed' for x in receipts),'source_candidate_bytes_unchanged':all(path.read_bytes()==files[name] for name,path in origins.items()),'integration':'reconciled' if all(x['status']=='passed' for x in receipts) else 'blocked','model_calls':0,'client_version':adapter.version,'client_sha256':adapter.sha256}
(dest/'integration.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'integration':report['integration'],'checks':[(x['check_id'],x['status']) for x in receipts]}))
