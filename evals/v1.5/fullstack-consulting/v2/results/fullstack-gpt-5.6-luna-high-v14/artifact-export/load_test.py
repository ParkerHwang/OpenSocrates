#!/usr/bin/env python3
"""Repeatable small local workload: concurrent reads plus idempotent writes."""
import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def call(base, method, path, token, body=None, idem=None):
    started = time.perf_counter()
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Idempotency-Key"] = idem
        data = json.dumps(body).encode()
    request = urllib.request.Request(base + path, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        error.read()
        status = error.code
    except (urllib.error.URLError, TimeoutError, ConnectionResetError, ConnectionAbortedError) as error:
        status = 599
    return (time.perf_counter() - started) * 1000, status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--token", required=True)
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    read_count = max(1, args.requests // 2)
    write_count = args.requests - read_count
    jobs = [("GET", "/api/inventory", None, None)] * read_count
    jobs += [("POST", "/api/orders", {"client_ref": f"load-{i}", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, f"load-create-{i}") for i in range(write_count)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda job: call(args.base, job[0], job[1], args.token, job[2], job[3]), jobs))
    elapsed = time.perf_counter() - started
    latencies = [item[0] for item in results]
    errors = sum(status >= 400 for _, status in results)
    print(json.dumps({"requests": len(results), "concurrency": args.concurrency, "elapsed_seconds": round(elapsed, 4), "throughput_rps": round(len(results) / elapsed, 2), "errors": errors, "status_counts": dict(sorted(Counter(status for _, status in results).items())), "latency_ms": {"p50": round(statistics.median(latencies), 2), "p95": round(sorted(latencies)[int(len(latencies) * .95) - 1], 2), "max": round(max(latencies), 2)}}))


if __name__ == "__main__":
    main()
