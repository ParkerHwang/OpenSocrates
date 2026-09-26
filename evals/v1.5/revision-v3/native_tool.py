"""Evaluation-only unchanged-request forwarding; no semantic help or product logging."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    config = json.loads(Path(__file__).with_suffix('.json').read_text())
    receipt = {'mode': None, 'operation': None, 'request_id': None, 'response_request_id': None,
               'status': None, 'exit_code': None, 'response_sha256': None}
    started = time.monotonic()
    try:
        mode = sys.argv[1]
        assert mode in ('memory', 'documentation', 'assistance')
        receipt['mode'] = mode
        raw = sys.stdin.buffer.read(262145)
        assert len(raw) <= 262144
        request = json.loads(raw)
        receipt.update(operation=request.get('operation'), request_id=request.get('request_id'), schema=request.get('schema'))
        if mode == 'memory':
            assert (request['project_id'], request['workspace_id']) == (config['project_id'], config['workspace_id'])
            assert request['operation'] in ('prepare', 'recall', 'inspect', 'checkpoint', 'delete', 'export')
            if request['operation'] in ('prepare', 'recall', 'checkpoint'):
                assert request['task_id'] == config['task_id']
            if request['operation'] == 'delete':
                assert request['payload']['intent'] == 'delete_record'
                assert request['payload']['record_id'] == config['delete_id']
            receipt['target_record_id'] = request['payload'].get('record_id')
        result = subprocess.run([config['launcher'], mode, 'codex'], input=raw, capture_output=True, timeout=45, check=False)
        response = json.loads(result.stdout)
        receipt.update(status=response.get('status'), exit_code=result.returncode,
                       response_request_id=response.get('request_id'), response_sha256=hashlib.sha256(result.stdout).hexdigest())
        sys.stdout.buffer.write(result.stdout)
        code = result.returncode
    except Exception as error:
        receipt['adapter_error'] = type(error).__name__
        code = 2
        print(json.dumps({'status':'adapter_rejected','error_type':type(error).__name__}))
    finally:
        receipt['wall_seconds'] = round(time.monotonic()-started, 3)
        descriptor = os.open(config['audit_log'], os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor,'a') as stream:
            stream.write(json.dumps(receipt)+'\n')
    raise SystemExit(code)


if __name__ == '__main__':
    main()
