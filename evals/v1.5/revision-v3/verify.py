"""Offline checks for the single repair call and its unchanged predecessor."""
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('revision_integrity',HERE.parent/'revision-v2/verify.py')
integrity=importlib.util.module_from_spec(spec);spec.loader.exec_module(integrity)
integrity.outcomes()
integrity.HERE=HERE
integrity.outcomes()
assert len(list((HERE/'results').glob('*/call.started.json')))==1
summary=json.loads((HERE/'summary.json').read_text())
call=json.loads((HERE/'results/ko/call.json').read_text())
assert summary['row']['usage']==call['usage']
assert summary['row']['wall_seconds']==call['wall_seconds']
assert all(json.loads((HERE/'results/ko/checks.json').read_text()).values())
assert call['turn_completed'] and call['exit_code']==0 and not call['timeout']
print('PASS: one targeted repair call, all required artifact/state checks; original two calls preserved')

validation=json.loads((HERE/'validation.json').read_text())
for name,digest in validation['runtime_input_hashes'].items():
    assert integrity.sha(integrity.ROOT/name)==digest,name
print(f"PASS: {len(validation['runtime_input_hashes'])} runtime input hashes match the qualified package source")
