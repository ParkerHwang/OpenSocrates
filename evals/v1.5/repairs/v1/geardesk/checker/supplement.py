#!/usr/bin/env python3
"""Isolated synthetic scenarios; invoke only public adapters and exported domain functions."""
import argparse, json, subprocess, tempfile
from pathlib import Path
from checks import Harness, REQUEST, require, historical_equal


def assert_rejected(result, before, after):
    require(not result['ok'] and result['error']['code'] in ('VALIDATION','INVALID_TRANSITION'), 'expected explicit rejection')
    require(before == after, 'rejected operation persisted partial write')


def run(project, arm, baseline, output):
    checks=[];receipts=[]
    def scenario(name,fn):
        with tempfile.TemporaryDirectory(prefix='checker-isolated-') as tmp:
            h=Harness(project,Path(tmp),3)
            try:
                h.start();fn(h);status='pass';detail=None
            except AssertionError as e:status='fail';detail=str(e)
            except Exception as e:status='error';detail=f'{type(e).__name__}: {e}'
            finally:h.close();receipts.extend(h.receipts)
        checks.append(dict(name=name,group=name,status=status,detail=detail))
    def seed(h):
        h.reserve('cli','date');h.good_command('cli',dict(type='checkout',id='date'))
    for adapter in ('cli','http'):
        for label,value in [('omitted',...),('null',None),('invalid','2026-02-30')]:
            def dates(h,a=adapter,v=value):
                seed(h);before=(h.data/'store.json').read_bytes()
                content=dict(type='return.partial',id='date',lines=[dict(itemId='camera',quantity=1)])
                if v is not ...:content['returnedOn']=v
                result=h.command(a,content)
                assert_rejected(result,before,(h.data/'store.json').read_bytes())
            scenario(f'{adapter} partial date {label}',dates)
        def full(h,a=adapter):
            seed(h);r=h.good_command(a,dict(type='return',id='date'))['data']
            require(r['refund']==5000 and r['lateFee']==0,'full scheduled-end default')
        scenario(f'{adapter} full date default',full)
        for position in (0,1,2):
            def rollback(h,a=adapter,p=position):
                seed(h);before=(h.data/'store.json').read_bytes()
                commands=[dict(type='maintenance.add',id=f'm{i}',itemId='tripod',quantity=1,start='2026-11-20',end='2026-11-21') for i in range(2)]
                commands.insert(p,dict(type='return.partial',id='date',lines=[dict(itemId='camera',quantity=1)]))
                result=h.call(a,'batch',dict(expectedRevision=2,idempotencyKey='rollback',commands=commands))
                assert_rejected(result,before,(h.data/'store.json').read_bytes())
            scenario(f'{adapter} invalid date batch position {position}',rollback)
    # Both genuine stage-2 formats: one lacks allocation; the other retains 5000/1000 line evidence.
    for fixture_arm in (('v1.4.0','v1.5.0-rc') if arm == 'v1.4.0' else ('v1.5.0-rc',)):
        def mixed(h,fa=fixture_arm):
            old=baseline/'snapshots'/fa/'stage2'
            olddata=h.root/'old-data';olddata.mkdir()
            def oldcall(body):
                p=subprocess.run(['node','cli.mjs','--data-dir',str(olddata),'--catalog',str(old/'fixtures/catalog.json'),'command'],cwd=old,input=json.dumps(body),text=True,capture_output=True,timeout=12)
                r=json.loads(p.stdout);require(r['ok'],str(r));receipts.append(dict(fixture_source=fa,request=body,response=r));return r
            oldcall(dict(REQUEST,type='reserve',id='mixed',lines=[dict(itemId='camera',quantity=1),dict(itemId='tripod',quantity=1)],expectedRevision=0,idempotencyKey='s'))
            oldcall(dict(type='checkout',id='mixed',expectedRevision=1,idempotencyKey='c'))
            raw=(olddata/'store.json').read_bytes();source=json.loads(raw)
            require(source['schemaVersion']==1,'genuine prior format required')
            (h.data/'store.json').write_bytes(raw)
            # Change current catalog: historical allocation may never be recovered from it.
            h.catalog['items'][0]['deposit']=7777;h.catalog['items'][1]['deposit']=8888;h.write_catalog()
            before=(h.data/'store.json').read_bytes()
            content=dict(type='return.partial',id='mixed',returnedOn='2026-11-09',lines=[dict(itemId='camera',quantity=1)])
            result=h.command('cli',content,key='historical-partial')
            known=fa=='v1.5.0-rc'
            if known:
                require(result['ok'] and result['data']['refund']==5000,'known historical camera refund must be 5000')
                require(h.ok('cli','report')['data']['depositHeld']==1000,'known tripod remainder must be 1000')
                replay=h.command('http',content,revision=0,key='historical-partial')
                require(replay['ok'] and replay['data']==result['data'],'historical replay')
                expected=1000
            else:
                assert_rejected(result,before,(h.data/'store.json').read_bytes())
                require('histor' in result['error']['message'].lower() or 'allocat' in result['error']['message'].lower() or 'ambig' in result['error']['message'].lower(),'explicit historical limitation missing')
                expected=6000
            full=h.good_command('http',dict(type='return',id='mixed'))['data']
            require(full['refund']==expected,'aggregate full return conservation')
            report=h.ok('cli','report')['data']
            require(report['refunded']==6000 and report['depositHeld']==0,'total historical conservation')
            rows=h.ok('cli','reservations')['data']
            require(historical_equal(source['reservations'][0]['quote'],rows[0]['quote']),'historical quote fields')
            before=(h.data/'store.json').read_bytes();r=h.command('cli',dict(type='return',id='mixed'))
            require(not r['ok'] and before==(h.data/'store.json').read_bytes(),'repeat return mutation')
        scenario(f'genuine mixed {fixture_arm}: '+('known line refund' if fixture_arm=='v1.5.0-rc' else 'ambiguous reject and aggregate return'),mixed)
    p=subprocess.run(['node',str(Path(__file__).with_name('domain-probes.mjs')),str(project),arm],capture_output=True,text=True,timeout=30)
    require(p.returncode==0,p.stderr)
    checks.extend(json.loads(p.stdout))
    summary=dict(label='new-checker-original' if project.parent.name=='apps' and 'repairs' not in str(project) else 'new-checker-derivative',project=str(project),counts={s:sum(c['status']==s for c in checks) for s in ('pass','fail','error','unassessable')},checks=checks,receipts=receipts,limitations=['Cross-format known allocation requires consumer support; unsupported import is a limitation, not missing historical evidence.','Output alias failures concern mutable result ownership, not input purity or determinism.','No model judgments collected; historical counts unchanged.'])
    with output.open('x') as f:json.dump(summary,f,indent=2)
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--arm',required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.project.resolve(),a.arm,a.baseline.resolve(),a.output.resolve())['counts']))
