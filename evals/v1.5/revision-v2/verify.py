"""Offline integrity, old-source preservation and bounded outcome accounting."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE='b70d9f1a60b7256febe0e62498a46f8cd0cd2507'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical():
    with tempfile.TemporaryDirectory(prefix='os-revision-history-') as temporary:
        tree=Path(temporary)
        process=subprocess.Popen(['git','archive',BASE],cwd=ROOT,stdout=subprocess.PIPE)
        with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
            archive.extractall(tree,filter='data')
        assert process.wait()==0
        checked=0
        for previous in (tree/'evals/v1.5').rglob('*'):
            if previous.is_file() and previous.relative_to(tree).as_posix()!='evals/v1.5/STATUS.md':
                assert sha(previous)==sha(ROOT/previous.relative_to(tree)),str(previous.relative_to(tree))
                checked+=1
        for previous in (tree/'schemas/v1').glob('*.json'):
            assert sha(previous)==sha(ROOT/previous.relative_to(tree))
        subprocess.run([sys.executable,'evals/v1.5/repairs/v1/verify.py'],cwd=tree,check=True)
    # Older pilot/practical/review verifiers bind a still-earlier source candidate.
    path=ROOT/'evals/v1.5/repairs/v1/verify.py'
    spec=importlib.util.spec_from_file_location('historical_repair_verifier',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.historical_verifiers(json.loads((path.parent/'before.json').read_text())['source_commit'])
    for path in ('evals/v1.5/backend-queueforge/v1/review/verify_export.py','evals/v1.5/backend-queueforge/luna-v1/review/verify_export.py'):
        subprocess.run([sys.executable,path],cwd=ROOT,check=True)
    print(f'PASS: {checked} historical evaluation files and 41 original schemas unchanged; old verifiers run at their original source boundary')


def outcomes():
    manifest=json.loads((HERE/'manifest.json').read_text())
    for name,digest in manifest['hashes'].items():
        assert sha(ROOT/name)==digest,name
    starts=list((HERE/'results').glob('*/call.started.json'))
    assert 0 < len(starts) <= 2
    for start in starts:
        v=json.loads(start.read_text());assert (v['model'],v['effort'],v['attempt'])==('gpt-6-luna','medium',1)
        call=json.loads((start.parent/'call.json').read_text())
        assert call['requested_model']=='gpt-6-luna' and call['requested_effort']=='medium'
        for value in call['usage'].values():
            assert value is None or type(value) is int and value>=0
        assert json.loads((start.parent/'cleanup.json').read_text())['auth_copy_removed']
    lock=HERE/'outcomes.lock.json'
    if lock.exists():
        for name,digest in json.loads(lock.read_text())['files'].items():
            assert sha(HERE/name)==digest,name
    print(f'PASS: {len(starts)} counted calls, immutable input and outcome hashes, explicit null usage')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--historical',action='store_true');parser.add_argument('--outcomes',action='store_true');args=parser.parse_args()
    if args.historical: historical()
    if args.outcomes: outcomes()
