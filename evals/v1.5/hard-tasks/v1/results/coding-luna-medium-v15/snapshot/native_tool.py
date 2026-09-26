"""Transparent evaluation adapter; optional enrolled memory only, no semantic help."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    config=json.loads(Path(__file__).with_suffix('.json').read_text())
    if len(sys.argv)!=2 or sys.argv[1] in ('--help','-h'):
        print('Usage: python3 native_tool.py memory|assistance|documentation < request.json');return
    mode=sys.argv[1]; receipt={'mode':mode,'operation':None,'request_id':None,'response_request_id':None,'status':None,'exit_code':None}
    start=time.monotonic()
    try:
        assert mode in ('memory','assistance','documentation')
        raw=sys.stdin.buffer.read(262145);assert len(raw)<=262144
        req=json.loads(raw);receipt.update(operation=req.get('operation'),request_id=req.get('request_id'),schema=req.get('schema'))
        if mode=='memory':
            assert req['project_id']==config['project_id'] and req['workspace_id']==config['workspace_id']
            assert req['operation'] in ('prepare','recall','inspect','checkpoint','observe','refresh','record','export')
            if req['operation'] in ('prepare','recall','checkpoint'):assert req['task_id']==config['task_id']
        p=subprocess.run([config['launcher'],mode,'codex'],input=raw,capture_output=True,timeout=45)
        result=json.loads(p.stdout);receipt.update(status=result.get('status'),response_request_id=result.get('request_id'),exit_code=p.returncode,response_sha256=hashlib.sha256(p.stdout).hexdigest())
        sys.stdout.buffer.write(p.stdout);code=p.returncode
    except Exception as error:
        receipt['adapter_error']=type(error).__name__;code=2
        print(json.dumps({'status':'adapter_rejected','error_type':type(error).__name__}))
    finally:
        receipt['wall_seconds']=round(time.monotonic()-start,3)
        fd=os.open(config['audit_log'],os.O_APPEND|os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a') as f:f.write(json.dumps(receipt)+'\n')
    raise SystemExit(code)


if __name__=='__main__':main()
