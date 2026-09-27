#!/usr/bin/env python3
"""Repeatable loopback HTTP read/write exercise; always uses a fresh local store."""
import argparse
import concurrent.futures
import http.client
import json
import os
import platform
import sqlite3
import statistics
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.support import RunningServer


class Client:
    def __init__(self, base, token):
        url = urlsplit(base)
        self.conn = http.client.HTTPConnection(url.hostname, url.port, timeout=25)
        self.token = token

    def call(self, method, path, payload=None):
        headers = {'Authorization': f'Bearer {self.token}'}
        body = None
        if payload is not None:
            headers.update({'Content-Type': 'application/json', 'Idempotency-Key': str(uuid.uuid4())})
            body = json.dumps(payload)
        started = time.perf_counter()
        try:
            self.conn.request(method, path, body, headers)
            response = self.conn.getresponse()
            data = json.loads(response.read())
            return response.status, data, (time.perf_counter() - started) * 1000
        except Exception as error:
            return 0, {'error': str(error)}, (time.perf_counter() - started) * 1000

    def close(self):
        self.conn.close()


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    pos = (len(values) - 1) * fraction
    low = int(pos)
    high = min(low + 1, len(values) - 1)
    return round(values[low] + (values[high] - values[low]) * (pos - low), 3)


def summary(samples, elapsed, errors):
    latencies = [latency for _, latency in samples]
    return {'requests': len(samples), 'elapsed_seconds': round(elapsed, 4),
            'throughput_rps': round(len(samples) / elapsed, 2),
            'status_counts': dict(Counter(str(code) for code, _ in samples)),
            'errors': len(errors), 'error_examples': errors[:5],
            'latency_ms': {'mean': round(statistics.mean(latencies), 3), 'p50': percentile(latencies, .5),
                           'p95': percentile(latencies, .95), 'p99': percentile(latencies, .99), 'max': round(max(latencies), 3)}}


def phase(server, tokens, concurrency, count, mode, label):
    barrier = threading.Barrier(concurrency)
    def worker(index):
        client = Client(server.base, tokens[index % len(tokens)])
        samples, errors = [], []
        barrier.wait()
        def request(method, path, payload=None, expected=200):
            code, data, latency = client.call(method, path, payload)
            samples.append((code, latency))
            if code != expected:
                errors.append({'method': method, 'path': path, 'status': code, 'body': data})
                return None
            return data
        try:
            for i in range(index, count, concurrency):
                client.token = tokens[i % len(tokens)]
                if mode == 'read':
                    request('GET', ['/api/inventory', '/api/dashboard', '/api/orders?limit=20', '/api/audit?limit=20'][i % 4])
                else:
                    order = request('POST', '/api/orders', {'client_ref': f'{label}-{index}-{i}', 'lines': [{'sku': 'BOLT', 'quantity': 2}]}, 201)
                    if order is None:
                        continue
                    for action in ('reserve', 'ship', 'returns', 'returns'):
                        payload = {'expected_version': order['version']}
                        if action == 'returns':
                            payload['lines'] = [{'sku': 'BOLT', 'quantity': 1}]
                        order = request('POST', f'/api/orders/{order["id"]}/{action}', payload)
                        if order is None:
                            break
        finally:
            client.close()
        return samples, errors
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(worker, range(concurrency)))
    elapsed = time.perf_counter() - started
    return summary([s for samples, _ in results for s in samples], elapsed, [e for _, errors in results for e in errors])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency', type=int, default=8)
    parser.add_argument('--read-requests', type=int, default=30000)
    parser.add_argument('--write-workflows', type=int, default=6000, help='Five mutations each: create, reserve, ship, partial return, full return')
    parser.add_argument('--prefill', type=int, default=200)
    parser.add_argument('--output', default='evidence/load-results.json')
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 32 or min(args.read_requests, args.write_workflows, args.prefill) < 1:
        parser.error('Use concurrency 1..32 and positive workload sizes.')
    server = RunningServer()
    try:
        tokens = [server.login('operator', tenant) for tenant in ('north', 'south')]
        for i in range(args.prefill):
            status, data = server.request('POST', '/api/orders', {'client_ref': f'prefill-{i}', 'lines': [{'sku': 'SAMPLE', 'quantity': 1}]}, tokens[i % 2], str(uuid.uuid4()))
            if status != 201:
                raise RuntimeError(data)
        warm_read = phase(server, tokens, args.concurrency, 100, 'read', 'warm-read')
        warm_write = phase(server, tokens, args.concurrency, 20, 'write', 'warm-write')
        read = phase(server, tokens, args.concurrency, args.read_requests, 'read', 'measured-read')
        write = phase(server, tokens, args.concurrency, args.write_workflows, 'write', 'measured-write')
        with sqlite3.connect(server.directory / 'depotflow.sqlite3') as conn:
            integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys = conn.execute('PRAGMA foreign_key_check').fetchall()
            audit_count = conn.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
            expected_events = args.prefill + (20 + args.write_workflows) * 5
            stock = conn.execute('SELECT tenant,sku,on_hand,reserved FROM inventory ORDER BY tenant,sku').fetchall()
            expected_stock = [(tenant, sku, units, 0) for tenant in ('north', 'south') for sku, units in [('BOLT', 100), ('CABLE', 60), ('SAMPLE', 20)]]
            final_orders = dict(conn.execute('SELECT status,COUNT(*) FROM orders GROUP BY status').fetchall())
        checks = {'integrity_check': integrity, 'foreign_key_violations': foreign_keys,
                  'audit_events': audit_count, 'expected_audit_events': expected_events,
                  'stock_restored': stock == expected_stock, 'orders_by_status': final_orders,
                  'passed': integrity == 'ok' and not foreign_keys and audit_count == expected_events and stock == expected_stock}
        report = {'date': datetime.now(timezone.utc).isoformat(),
                  'environment': {'platform': platform.platform(), 'architecture': platform.machine(),
                                  'logical_cpus': os.cpu_count(), 'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
                                  'cpu_model': 'Not exposed by the sandbox', 'memory': 'Not exposed by the sandbox'},
                  'methodology': {'transport': 'HTTP/1.1 loopback, one persistent connection per worker, closed-loop concurrency',
                                  'concurrency': args.concurrency, 'tenants': 2, 'prefill_orders': args.prefill,
                                  'read_mix': 'Equal inventory/dashboard/orders(first 20)/audit(first 20)',
                                  'write_workflow': 'BOLT quantity 2: create/reserve/ship/return 1/return 1; five HTTP mutations',
                                  'latency': 'Per request send through complete response body, milliseconds; linear-interpolated percentiles',
                                  'excluded': 'Startup, login, prefill, and warmup; client and server share hardware; no think time',
                                  'durability': 'SQLite WAL, synchronous FULL; fresh store per run'},
                  'warmup': {'reads': warm_read, 'writes': warm_write}, 'reads': read, 'writes': write,
                  'persisted_state_checks': checks}
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        if not checks['passed'] or any(part['errors'] for part in (warm_read, warm_write, read, write)):
            return 1
        return 0
    finally:
        server.close()


if __name__ == '__main__':
    raise SystemExit(main())
