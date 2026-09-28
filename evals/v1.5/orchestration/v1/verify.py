#!/usr/bin/env python3
"""Offline integrity/receipt audit. This does not call models or rerun generated programs."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens')

def sha(data): return hashlib.sha256(data).hexdigest()
def identity(value): return 'sha256:' + sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def load(path): return json.loads(path.read_text())

def collect_calls():
    calls=[]
    for path in sorted((ROOT/'live').glob('*/**/response.json')):
        response=load(path)
        for call in response['calls']:
            calls.append({'scope':str(path.relative_to(ROOT)), **call})
    for path in sorted((ROOT/'diagnostics').glob('*/result.json')):
        value=load(path)
        if 'receipt' in value:
            calls.append({'scope':str(path.relative_to(ROOT)), **value['receipt'],
                          'semantic_contract_accepted':value['contract_accepted']})
        else:
            thread=next((x.get('thread_sha256') for x in value.get('events',[]) if x['type']=='thread.started'),None)
            calls.append({'scope':str(path.relative_to(ROOT)),'role':'schema_diagnostic',
                          'model':value['model'],'status':'completed' if value['exit_code']==0 else 'failed',
                          'usage':value.get('usage') or dict.fromkeys(FIELDS),
                          'thread_sha256':thread,'process_exit_code':value['exit_code']})
    for path in sorted((ROOT/'diagnostics').glob('*/*.result.json')):
        value=load(path)
        thread=next((x.get('thread_sha256') for x in value.get('events',[]) if x['type']=='thread.started'),None)
        calls.append({'scope':str(path.relative_to(ROOT)),'role':'schema_diagnostic_'+value['kind'],
                      'model':value['model'],'status':'completed' if value['exit_code']==0 else 'failed',
                      'usage':value.get('usage') or dict.fromkeys(FIELDS),'thread_sha256':thread,
                      'process_exit_code':value['exit_code']})
    return calls

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true',help='Write derived public verification and usage receipts.')
    parser.add_argument('--tracked',action='store_true',help='Also verify that every locked public file exists with exact bytes in HEAD.')
    args=parser.parse_args()
    findings=[]
    if (ROOT/'artifact-lock.json').exists():
        locked=load(ROOT/'artifact-lock.json')['files']
        current={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in ROOT.rglob('*')
                 if p.is_file() and p.name!='artifact-lock.json'}
        assert current==locked, 'Frozen public evidence changed or file set differs'
        if args.tracked:
            repo=ROOT.parents[3]
            for name in [*locked, 'artifact-lock.json']:
                path=ROOT/name
                committed=subprocess.check_output(['git','show','HEAD:'+str(path.relative_to(repo))],cwd=repo)
                assert committed==path.read_bytes(), 'Missing or different committed public evidence: '+name

    exported=load(ROOT/'export-manifest.json')
    for item in exported['files']:
        data=(ROOT/item['path']).read_bytes()
        assert sha(data)==item['exported_sha256'],item['path']
        assert len(data)==item['bytes'],item['path']
    # All publication manifests bind exact unmodified public artifact bytes.
    workflows=[]
    for path in sorted((ROOT/'live').glob('*/**/response.json')):
        response=load(path);workflow=path.parent.name.removesuffix('-invocation')
        candidate=path.parent.parent/'candidates'/workflow
        for item in response['publication']['completed_files']:
            data=(candidate/item['path']).read_bytes()
            assert 'sha256:'+sha(data)==item['sha256']
            assert len(data)==item['bytes']
        call_ids=[x['assignment_id'] for x in response['calls']]
        assert len(call_ids)==len(set(call_ids))
        if response['status']=='integration_pending':
            assert response['publication']['status']=='complete' and response['publication']['location_verified']
            for unit in response['units']:
                assert unit['status']=='qualified_candidate' and not unit['required_open']
                version=unit['versions'][-1]
                assert version['qualified']
                assert len({version['producer_id'],version['reviewer_id'],version['verifier_id']})==3
                for role in ['review','verification']:
                    assessment=version[role]
                    assert assessment['candidate_sha256']==version['candidate_sha256']
                    assert assessment['verdict']=='pass'
                    assert all(x['status']=='passed' for x in assessment['obligations'])
                assert all(x['status']=='passed' and x['exit_code']==0 and x['candidate_sha256']==version['candidate_sha256'] for x in version['checks'])
        workflows.append({'scope':str(path.relative_to(ROOT)),'status':response['status'],
                          'calls':len(response['calls']),'publication':response['publication']['status']})
    integration=load(ROOT/'delivery/integration.json')
    for item in integration['artifacts']:
        data=(ROOT/'delivery'/item['path']).read_bytes()
        assert 'sha256:'+sha(data)==item['sha256']
        assert len(data)==item['bytes']
        origin=ROOT/'live'/integration['origin_paths'][item['path']]
        assert data==origin.read_bytes()
    combined=identity(integration['artifacts'])
    assert integration['integration']=='reconciled' and integration['all_passed']
    assert all(x['status']=='passed' and x['candidate_sha256']==combined for x in integration['checks'])
    calls=collect_calls()
    assert all(x['model']=={'name':'gpt-6-astra','effort':'max'} for x in calls)
    threads=[x['thread_sha256'].removeprefix('sha256:') for x in calls if x.get('thread_sha256')]
    assert len(threads)==len(set(threads))
    sums={key:sum(x['usage'][key] for x in calls if x['usage'].get(key) is not None) for key in FIELDS}
    coverage={key:sum(x['usage'].get(key) is not None for x in calls) for key in FIELDS}
    for x in calls:
        for key in FIELDS:
            assert x['usage'].get(key) is None or isinstance(x['usage'][key],int) and x['usage'][key]>=0
    usage={'schema':'opensocrates.orchestration.usage-audit/1','actual_model_invocations':len(calls),
           'status_counts':dict(Counter(x['status'] for x in calls)),
           'measured_sums':sums,'reported_call_counts':coverage,
           'calls':calls,'development_agent_usage':None,'primary_usage':None,'billed_cost':None,
           'limitations':['Cached input is included in input_tokens; reasoning output is included in output_tokens. Do not add subsets again.',
                          'Missing terminal usage remains null and is excluded from measured sums, never treated as zero.',
                          'Configured model/effort is not independent backend attestation.',
                          'Opaque tool_items in transport diagnostics is not a tool-call count. No complete action count is available.',
                          'Development-agent and primary reasoning costs are outside the measured evaluation calls.']}
    result={'schema':'opensocrates.orchestration.offline-verification/1','status':'pass',
            'exported_files_checked':len(exported['files']),'committed_bytes_checked':args.tracked,'workflows':workflows,
            'delivery_files_checked':len(integration['artifacts']),
            'actual_model_invocations_accounted':len(calls),'unique_reported_conversations':len(threads),
            'new_model_calls':0,'generated_program_execution':'not_rerun_by_this_offline_checker',
            'limitations':['Checks receipt consistency and exported bytes. Original redacted JSON hashes are attested separately, not reconstructable from public placeholders.',
                           'Does not validate hidden reading/application, backend identity, billing or broad quality improvement.']}
    if args.write:
        (ROOT/'usage.json').write_text(json.dumps(usage,ensure_ascii=False,indent=2)+'\n')
        (ROOT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__': main()
