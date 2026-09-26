"""One frozen targeted KO retest; reuse execution mechanics without old outcomes."""
import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('revision_execution',HERE.parent/'revision-v2/runner.py')
execution=importlib.util.module_from_spec(spec);spec.loader.exec_module(execution)
execution.HERE=HERE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('preflight','execute'));parser.add_argument('--manifest-sha256',required=True);args=parser.parse_args()
    assert execution.sha(HERE/'manifest.json')==args.manifest_sha256
    manifest=json.loads((HERE/'manifest.json').read_text())
    assert manifest['model']=='gpt-6-luna' and manifest['effort']=='medium'
    assert manifest['fixture']['locales']==['ko'] and manifest['fixture']['limits']['model_invocations']==1
    assert execution.sha(execution.CLIENT)==manifest['client']['sha256']
    assert execution.sha(manifest['arm']['archive_path'])==manifest['arm']['archive_sha256']
    for name,digest in manifest['hashes'].items():
        assert execution.sha(ROOT/name)==digest,name
    if args.mode=='execute':
        execution.save(HERE/'execution-started.json',{'manifest_sha256':args.manifest_sha256,'started_unix':time.time(),'maximum_calls':1})
        execution.execute(manifest)
    else:
        print('PASS: targeted repair freeze; zero outcome calls')


if __name__=='__main__':
    main()
