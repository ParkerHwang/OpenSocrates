"""No-model runner controls: capture boundaries, task inventory and fixture hashes."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('hard_runner',HERE/'runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
raw='\n'.join(json.dumps(x) for x in [
 {'type':'item.completed','item':{'id':'a','type':'agent_message','text':'Visible question before final.'}},
 {'type':'item.completed','item':{'id':'b','type':'command_execution','command':'cat task-checkpoint.schema.json','exit_code':1,'status':'failed','aggregated_output':'irrelevant'}},
 {'type':'item.completed','item':{'id':'c','type':'command_execution','command':'native_tool.py memory','exit_code':0,'status':'completed','aggregated_output':'{"schema":"opensocrates.project-memory.response/1.0.0","status":"invalid_request","request_id":null}\n{"schema":"opensocrates.project-memory.response/1.0.0","status":"ok","request_id":null}'}},
 {'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':4}},
])
value=runner.capture(raw,Path('/private/tmp/selfcheck'))
assert len(value['public_messages'])==1 and len(value['commands'])==2
assert [x['status'] for x in value['native_output_projections']]==['invalid_request','ok']
assert value['usage']['cached_input_tokens'] is None
assert runner.sanitize('task-checkpoint.schema.json',HERE)=='task-checkpoint.schema.json'
for kind,name,key in [('coding','metadata.json','files_sha256'),('office','author_manifest.json','sha256')]:
    directory=HERE/kind;manifest=json.loads((directory/name).read_text())
    for rel,digest in manifest[key].items():assert hashlib.sha256((directory/rel).read_bytes()).hexdigest()==digest,rel
print('PASS: pre-final public messages, all command attempts, batched native statuses, null usage and author hashes')
