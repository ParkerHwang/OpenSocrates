#!/usr/bin/env python3
"""Prepare or explicitly run one new synthetic orchestration episode; never overwrite evidence."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workflow', choices=['software', 'office', 'continuation', 'repair'], required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', action='store_true', help='Explicitly invoke actual model roles; default only prepares.')
    args = parser.parse_args()
    selected = 'live-v3/repair.request.json' if args.workflow == 'repair' else f'live-v2/{args.workflow}.request.json'
    source = ROOT / 'live' / selected
    request = json.loads(source.read_text())
    if args.workflow == 'continuation':
        request['source_root'] = str(ROOT / 'live/live-v2/continuation-source')
    elif args.workflow == 'repair':
        request['source_root'] = str(ROOT / 'live/live-v3/sources')
    else:
        request['source_root'] = str(ROOT / 'fixture')
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    request['run_id'], request['task_id'] = str(uuid.uuid4()), str(uuid.uuid4())
    request['candidate_root'] = str(target / 'candidates')
    request['client_path'] = str(args.client.resolve())
    request['model'] = {'name': 'gpt-6-astra', 'effort': 'max'}
    for unit in request['units']:
        for check in unit['checks']:
            check['argv'][0] = str(args.python.resolve())
    for item in request['sources']:
        actual = digest((Path(request['source_root']) / item['path']).read_bytes())
        if 'sha256:' + actual != item['sha256']:
            raise SystemExit('Frozen synthetic source digest mismatch')
    encoded = (json.dumps(request, ensure_ascii=False, indent=2) + '\n').encode()
    (target / 'request.json').write_bytes(encoded)
    binding = {'schema': 'opensocrates.orchestration.replay/1',
               'frozen_utc': datetime.now(timezone.utc).isoformat(),
               'protocol_template': selected, 'template_sha256': digest(source.read_bytes()),
               'request_sha256': digest(encoded), 'model': request['model'],
               'model_wall_clock_cutoff': None, 'outer_retries': 0,
               'original_results_are_not_modified': True, 'execute_requested': args.run}
    (target / 'manifest.json').write_text(json.dumps(binding, indent=2) + '\n')
    if not args.run:
        print('Prepared a new request. No model was invoked. Use --run with a different new output directory to execute.')
        return
    launcher = args.package.resolve() / 'bin/launch.sh'
    completed = subprocess.run([str(launcher), 'orchestrate', 'codex'], input=encoded,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    receipt = {'exit_code': completed.returncode, 'stdout_sha256': digest(completed.stdout),
               'stderr_sha256': digest(completed.stderr), 'raw_output_retained': False}
    try:
        result = json.loads(completed.stdout)
        if result.get('schema') != 'opensocrates.orchestration.response/1.0.0':
            raise ValueError('Unexpected output schema')
        (target / 'response.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        receipt['semantic_status'] = result['status']
    except (ValueError, AttributeError):
        receipt['semantic_status'] = 'unavailable_or_invalid_output'
    (target / 'invocation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))

if __name__ == '__main__':
    main()
