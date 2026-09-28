"""One actual negative-review diagnostic; retain only closed public result and receipts."""
import copy, json, sys, tempfile, uuid
from pathlib import Path
repo = Path('$REPO')
sys.path.insert(0, str(repo/'src'))
from opensocrates.orchestration.runtime import Coordinator, _assessment
from opensocrates.orchestration.paths import write_files, manifest, identity, verify_files
from opensocrates.project_memory.store import _public
from opensocrates.orchestration.contracts import checked, MAX_OUTPUT
root = Path(__file__).parent
out = root/'assessment-diagnostic-v1'
out.mkdir(exist_ok=False)
req = json.loads((root/'live-v2/software.request.json').read_text())
req['run_id'], req['task_id'] = str(uuid.uuid4()), str(uuid.uuid4())
req['candidate_root'] = str(out/'unused-candidate-root')
c = Coordinator(req)
try:
    unit = req['units'][1]
    candidate = {x['path']: x['content'].encode() for x in unit['seed']['files']}
    c.files['software-design'] = {'design.json': (root/'live-v2/candidates/software/artifacts/design.json').read_bytes()}
    assignment, files = c.assignment(unit,'review',candidate,[],[])
    binding = {'diagnostic':'one actual fresh negative reviewer, no production or acceptance claim', 'source_commit':'7893996357b7fcfaa058e91d4bc2694d5f1cb63c', 'model':req['model'], 'assignment_sha256':identity(assignment),'candidate_manifest':manifest(candidate),'input_manifest':assignment['inputs'],'guide_manifest':[{'id':g['id'],'sha256':g['sha256']} for g in assignment['guides']]}
    (out/'binding.json').write_text(json.dumps(binding,indent=2)+'\n')
    c.adapter.probe()
    with tempfile.TemporaryDirectory(prefix='opensocrates-assessment-diagnostic-') as raw:
        cwd=Path(raw).resolve()
        write_files(cwd,files)
        call=c.adapter.invoke(assignment,cwd)
        unchanged=verify_files(cwd,files)
    report={'receipt':call.receipt,'inputs_unchanged':unchanged,'assessment_public':None,'contract_accepted':False,'qualified':False,'rejection_reason':None}
    if call.value is not None:
        checked(call.value,'assessment',MAX_OUTPUT)
        _public(call.value,str(c.source_root))
        report['assessment_public']=call.value
        try:
            report['qualified']=_assessment(call.value,assignment,manifest(candidate))
            report['contract_accepted']=True
        except ValueError as exc:
            report['rejection_reason']=str(exc)
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':call.receipt['status'],'contract_accepted':report['contract_accepted'],'qualified':report['qualified'],'rejection_reason':report['rejection_reason']}))
finally:
    for b in (c.source_binding,c.output_binding):
        if b is not None:b.close()
