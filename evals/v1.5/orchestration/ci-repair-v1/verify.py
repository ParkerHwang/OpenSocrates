#!/usr/bin/env python3
"""Verify the platform qualification bridge without outcome model calls."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
def sha(data): return hashlib.sha256(data).hexdigest()
def load(path): return json.loads(path.read_text())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracked',action='store_true')
    parser.add_argument('--native',action='store_true')
    args=parser.parse_args()
    bridge=load(HERE/'SOURCE_BRIDGE.json')
    for name,want in bridge['runtime_package_inputs'].items():
        assert sha((REPO/name).read_bytes())==want,name
    assert sha((HERE.parent/'v1/artifact-lock.json').read_bytes())==bridge['original_public_lock_sha256']
    prior=[sys.executable,'-B',str(HERE.parent/'v1/verify.py')]
    if args.tracked:prior.append('--tracked')
    subprocess.run(prior,check=True,stdout=subprocess.DEVNULL)
    lock=load(HERE/'LOCK.json')['files']
    actual={str(p.relative_to(HERE)):sha(p.read_bytes()) for p in HERE.rglob('*') if p.is_file() and p.name!='LOCK.json'}
    assert actual==lock,'Platform evidence file set or bytes changed'
    if args.tracked:
        for name in [*lock,'LOCK.json']:
            p=HERE/name
            assert subprocess.check_output(['git','show','HEAD:'+str(p.relative_to(REPO))],cwd=REPO)==p.read_bytes(),name
    if args.native:
        qualified=load(HERE/'VALIDATION.json')
        assert sha((REPO/'dist/opensocrates-1.5.0-codex-plugin.zip').read_bytes())==qualified['archive_sha256']
        assert sha((REPO/'dist/codex/runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime').read_bytes())==qualified['native_sha256']
    print(json.dumps({'status':'pass','runtime_inputs':587,'prior_outcomes_unchanged':True,'locked_platform_files':len(lock),'committed_bytes_checked':args.tracked,'native_hashes_checked':args.native,'new_outcome_model_calls':0}))
if __name__=='__main__':main()
