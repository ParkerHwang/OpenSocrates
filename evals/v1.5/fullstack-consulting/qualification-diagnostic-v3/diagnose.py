"""Confirm actual transition responses/render changes and viewer readiness."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
manifest=json.loads((HERE/'manifest.json').read_text())
spec=importlib.util.spec_from_file_location('prior_diagnostics',HERE.parent/'qualification-diagnostic-v1/diagnose.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.HERE=HERE;module.q.HERE=HERE
for name,digest in manifest['files'].items():assert module.q.sha(HERE/name)==digest
assert module.q.sha(HERE.parent/'qualification-diagnostic-v1/diagnose.py')==manifest['prior_helper_sha256']
old_save=module.q.save
def save(path,value):
 if path.name=='result.json':value={**value,'scope':manifest['scope'],'diagnostic_version':3}
 old_save(path,value)
module.q.save=save
for name in manifest['targets']:module.browser(name)
