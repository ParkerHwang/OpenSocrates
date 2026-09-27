#!/usr/bin/env python3
"""Reproducible HTTP exercise against a disposable subprocess, never customer data."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.support import RunningApp


def summary(samples, seconds):
    latencies = sorted(s['ms'] for s in samples)
    def percentile(p):
        return round(latencies[max(0, math.ceil(len(latencies)*p)-1)], 3) if latencies else None
    return {'requests': len(samples), 'seconds': round(seconds, 4),
            'requests_per_second': round(len(samples)/seconds, 2),
            'latency_ms': {'p50': percentile(.5), 'p95': percentile(.95), 'p99': percentile(.99),
                           'max': round(max(latencies),3) if latencies else None},
            'errors': sum(not s['ok'] for s in samples),
            'statuses': dict(Counter(str(s['status']) for s in samples))}


def hardware():
    result = {'platform': platform.platform(), 'architecture': platform.machine(),
              'logical_cpus': os.cpu_count(), 'python': platform.python_version(),
              'sqlite': sqlite3.sqlite_version}
    if sys.platform == 'darwin':
        for name, field in [('machdep.cpu.brand_string','cpu'),('hw.memsize','memory_bytes'),('hw.physicalcpu','physical_cpus')]:
            probe = subprocess.run(['/usr/sbin/sysctl','-n',name], text=True, capture_output=True)
            result[field] = probe.stdout.strip() if probe.returncode == 0 else 'unavailable: local permission restriction'
    return result


def run(args):
    app = RunningApp()
    samples = []
    try:
        token = app.login()
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        tag = uuid.uuid4().hex[:12]

        def request(connection, method, path, payload=None, expected=200):
            start = time.perf_counter()
            try:
                connection.request(method, path, body=json.dumps(payload) if payload is not None else None,
                                   headers={**headers, **({'Idempotency-Key': uuid.uuid4().hex} if method=='POST' else {})})
                response = connection.getresponse()
                body = json.loads(response.read())
                status = response.status
                ok = status == expected
            except Exception as error:
                status, body, ok = 'transport', {'error': str(error)}, False
                connection.close()
            return body, {'method': method, 'route': path if method=='GET' else '/api/orders' if path=='/api/orders' else '/api/orders/:id/'+path.rsplit('/',1)[1],
                          'status': status, 'ok': ok, 'ms': (time.perf_counter()-start)*1000}

        def writer(worker):
            connection = http.client.HTTPConnection('127.0.0.1', app.port, timeout=30)
            records = []
            try:
                for index in range(worker, args.orders, args.concurrency):
                    lines = [{'sku':'BOLT','quantity':2},{'sku':'CABLE','quantity':1},{'sku':'SAMPLE','quantity':1}]
                    order, record = request(connection,'POST','/api/orders',{'client_ref':f'LOAD-{tag}-{index}','lines':lines},201)
                    records.append(record)
                    if not record['ok']: continue
                    for action in ('reserve','ship','returns'):
                        payload = {'expected_version':order['version']}
                        if action == 'returns': payload['lines'] = lines
                        order, record = request(connection,'POST',f'/api/orders/{order["id"]}/{action}',payload)
                        records.append(record)
                        if not record['ok']: break
            finally:
                connection.close()
            return records

        routes = ['/api/inventory','/api/dashboard','/api/orders?limit=20','/api/audit?limit=20']
        def reader(worker):
            connection = http.client.HTTPConnection('127.0.0.1',app.port,timeout=30)
            records=[]
            try:
                for index in range(worker,args.reads,args.concurrency):
                    _, record = request(connection,'GET',routes[index % len(routes)])
                    records.append(record)
            finally:
                connection.close()
            return records

        for _ in range(args.warmup):
            status, _ = app.request('GET','/api/inventory',token=token)
            assert status == 200

        phases = {}
        for name, worker in [('writes',writer),('reads',reader)]:
            start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                records=[record for group in pool.map(worker,range(args.concurrency)) for record in group]
            duration=time.perf_counter()-start
            phases[name]=summary(records,duration)
            groups=defaultdict(list)
            for record in records: groups[record['route']].append(record)
            phases[name]['by_route']={route:summary(group,duration) for route,group in groups.items()}
            samples.extend(dict(phase=name,**record) for record in records)
            print(f'{name}: {phases[name]["requests_per_second"]} requests/s; '
                  f'p95 {phases[name]["latency_ms"]["p95"]} ms; errors {phases[name]["errors"]}')

        with sqlite3.connect(app.db_path) as db:
            integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys=db.execute('PRAGMA foreign_key_check').fetchall()
            counts={table:db.execute(f'SELECT COUNT(*) FROM {table} WHERE tenant=?',('north',)).fetchone()[0]
                    for table in ('orders','audit','idempotency')}
            inventory=db.execute("SELECT sku,on_hand,reserved FROM inventory WHERE tenant='north' ORDER BY sku").fetchall()
            order_states=dict(db.execute("SELECT status,COUNT(*) FROM orders WHERE tenant='north' GROUP BY status").fetchall())
            db_bytes=sum(p.stat().st_size for p in app.directory.glob('depotflow.sqlite3*'))
        passed=(not any(p['errors'] for p in phases.values()) and integrity=='ok' and not foreign_keys
                and counts=={'orders':args.orders,'audit':args.orders*4,'idempotency':args.orders*4}
                and inventory==[('BOLT',100,0),('CABLE',60,0),('SAMPLE',20,0)]
                and order_states=={'returned':args.orders})
        result={'recorded_at':datetime.now(timezone.utc).isoformat(), 'hardware':hardware(),
                'configuration':{'concurrency':args.concurrency,'orders':args.orders,'read_requests':args.reads,'warmup_requests':args.warmup,
                                 'transport':'HTTP/1.1 loopback; one persistent connection per worker',
                                 'workload':'write phase: 3-line create/reserve/ship/full return; then equal inventory/dashboard/orders/audit reads',
                                 'timing':'HTTP serialization, round trip, and JSON parsing; excludes startup, login, warmup; closed-loop, no pacing or retries',
                                 'database':'SQLite WAL, synchronous FULL; new store per run; same host as load generator'},
                'phases':phases, 'postconditions':{'passed':passed,'integrity_check':integrity,'foreign_key_violations':foreign_keys,
                                               'counts':counts,'inventory':inventory,'order_states':order_states,'database_bytes_including_wal':db_bytes},
                'limitations':['One host and one short synthetic workload; no production capacity claim.',
                               'Write/read phases are separate, not a sustained mixed soak.',
                               'Authentication cost, WAN/TLS, large catalogs, and disk failure are outside measured phases.',
                               'Closed-loop clients wait for each response, so this does not measure open-loop overload behavior.']}
        output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n')
        output.with_name(output.stem+'-samples.json').write_text(json.dumps(samples,indent=2)+'\n')
        if not passed: raise SystemExit('Benchmark failed a request or persisted-state postcondition. See output.')
    finally:
        app.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency',type=int,default=8)
    parser.add_argument('--orders',type=int,default=250)
    parser.add_argument('--reads',type=int,default=2000)
    parser.add_argument('--warmup',type=int,default=40)
    parser.add_argument('--output',default='evidence/performance.json')
    args=parser.parse_args()
    if not 1<=args.concurrency<=20 or args.orders<1 or args.reads<1 or args.warmup<0:
        parser.error('Use concurrency 1..20, positive orders/reads, and nonnegative warmup.')
    run(args)
