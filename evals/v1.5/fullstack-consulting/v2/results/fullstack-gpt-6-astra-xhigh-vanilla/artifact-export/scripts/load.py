#!/usr/bin/env python3
"""Repeatable HTTP workload against a new local store; never modifies demo data."""
import argparse
import http.client
import json
import math
import os
import platform
import sqlite3
import statistics
import subprocess
import sys
import time
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.support import App, new_key


def summary(samples, elapsed):
    latencies = sorted(sample['ms'] for sample in samples)
    def percentile(p):
        return round(latencies[min(len(latencies) - 1, math.ceil(len(latencies) * p) - 1)], 3)
    errors = [sample for sample in samples if sample['status'] not in (200, 201)]
    return {'requests': len(samples), 'wall_seconds': round(elapsed, 4),
            'requests_per_second': round(len(samples) / elapsed, 2),
            'latency_ms': {'mean': round(statistics.mean(latencies), 3), 'p50': percentile(.5), 'p95': percentile(.95), 'p99': percentile(.99), 'max': round(latencies[-1], 3)},
            'status_counts': dict(Counter(str(sample['status']) for sample in samples)), 'error_count': len(errors), 'error_examples': errors[:5]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency', type=int, default=8)
    parser.add_argument('--reads', type=int, default=10000)
    parser.add_argument('--workflows', type=int, default=2000, help='Each workflow sends create, reserve, ship, and full return (4 writes).')
    parser.add_argument('--output', default='evidence/performance.json')
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 32 or args.reads < 1 or args.workflows < 1:
        parser.error('Use concurrency 1..32 and positive workload counts.')
    app = App()
    try:
        app.start()
        token = app.login()
        local = threading.local()
        connections = []
        def measured(method, route, body=None):
            start = time.perf_counter()
            try:
                if not getattr(local, 'connection', None):
                    local.connection = http.client.HTTPConnection('127.0.0.1', app.port, timeout=40)
                    connections.append(local.connection)
                headers = {'Authorization': 'Bearer ' + token}
                if body is not None:
                    headers.update({'Content-Type': 'application/json', 'Idempotency-Key': new_key()})
                local.connection.request(method, '/api' + route, json.dumps(body) if body is not None else None, headers)
                incoming = local.connection.getresponse()
                status, response = incoming.status, json.loads(incoming.read())
            except Exception as exc:
                status, response = 0, {'error': str(exc)}
                if getattr(local, 'connection', None):
                    local.connection.close()
                    local.connection = None
            sample = {'ms': (time.perf_counter() - start) * 1000, 'status': status, 'route': route}
            if status not in (200, 201):
                sample['error'] = response
            return sample, response
        # Prime HTTP, filesystem, and interpreter paths without including login or startup.
        for _ in range(20):
            measured('GET', '/inventory')
        def workflow(index):
            samples = []
            sample, order = measured('POST', '/orders', {'client_ref': f'LOAD-{index:06}', 'lines': [{'sku': 'BOLT', 'quantity': 1}, {'sku': 'CABLE', 'quantity': 1}]})
            samples.append(sample)
            for action in ('reserve', 'ship', 'returns'):
                if sample['status'] not in (200, 201):
                    break
                payload = {'expected_version': order['version']}
                if action == 'returns':
                    payload['lines'] = [{'sku': 'BOLT', 'quantity': 1}, {'sku': 'CABLE', 'quantity': 1}]
                sample, order = measured('POST', f"/orders/{order['id']}/{action}", payload)
                samples.append(sample)
            return samples
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            writes = [sample for workflow_samples in pool.map(workflow, range(args.workflows)) for sample in workflow_samples]
        write_time = time.perf_counter() - start
        routes = ['/inventory', '/dashboard', '/orders?limit=20', '/audit?limit=20']
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            reads = list(pool.map(lambda i: measured('GET', routes[i % len(routes)])[0], range(args.reads)))
        read_time = time.perf_counter() - start
        _, inventory = app.request('GET', '/api/inventory', token=token)
        _, dashboard = app.request('GET', '/api/dashboard', token=token)
        with sqlite3.connect(app.data / 'depotflow.sqlite3') as db:
            audit_count = db.execute('SELECT COUNT(*) FROM audit WHERE tenant=?', ('north',)).fetchone()[0]
            retry_count = db.execute('SELECT COUNT(*) FROM idempotency WHERE tenant=?', ('north',)).fetchone()[0]
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys = db.execute('PRAGMA foreign_key_check').fetchall()
        invariants = {
            'all_workflows_returned': dashboard['orders_by_status']['returned'] == args.workflows,
            'stock_restored': {i['sku']: i['on_hand'] for i in inventory['items']} == {'BOLT': 100, 'CABLE': 60, 'SAMPLE': 20},
            'no_reservations_left': dashboard['reserved_units'] == 0,
            'exact_audit_count': audit_count == args.workflows * 4,
            'exact_retry_record_count': retry_count == args.workflows * 4,
            'database_integrity': integrity == 'ok' and not foreign_keys,
        }
        hardware = {'platform': platform.platform(), 'machine': platform.machine(), 'logical_cpus': os.cpu_count(), 'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version}
        if platform.system() == 'Darwin':
            for name in ('machdep.cpu.brand_string', 'hw.memsize'):
                try:
                    hardware[name] = subprocess.check_output(['sysctl', '-n', name], text=True).strip()
                except (OSError, subprocess.CalledProcessError):
                    hardware[name] = 'unavailable'
        report = {'measured_at': datetime.now(timezone.utc).isoformat(), 'hardware': hardware,
                  'configuration': vars(args), 'methodology': 'Loopback HTTP/1.1, one persistent connection per worker, one token, fixed thread pool, closed-loop workers. Fresh seeded SQLite WAL/FULL database. Writes first; four-request workflows sequential within a worker. Mixed reads after writes. Twenty unmeasured inventory warmups. Startup and login excluded. Latency includes HTTP and client JSON work; throughput uses phase wall time. Client and server share host.',
                  'writes': summary(writes, write_time), 'reads': summary(reads, read_time), 'invariants': invariants,
                  'audit_count': audit_count, 'idempotency_count': retry_count,
                  'database_bytes': sum(p.stat().st_size for p in app.data.glob('depotflow.sqlite3*'))}
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        if not all(invariants.values()) or report['writes']['error_count'] or report['reads']['error_count']:
            raise SystemExit(1)
    finally:
        for connection in locals().get('connections', []):
            connection.close()
        app.close()


if __name__ == '__main__':
    main()
