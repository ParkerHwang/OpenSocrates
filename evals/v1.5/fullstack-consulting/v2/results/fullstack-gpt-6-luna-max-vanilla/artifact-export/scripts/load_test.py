#!/usr/bin/env python3
"""Repeatable mixed read/write local workload against a running DepotFlow instance."""
import argparse
import concurrent.futures
import json
import os
import platform
import time
import urllib.error
import urllib.request
import uuid


def request(url, method="GET", data=None, headers=None):
    request_headers = {"Accept": "application/json", **(headers or {})}
    body = None
    if data is not None:
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(data, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            response.read()
            return response.status, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as error:
        error.read()
        return error.code, (time.perf_counter() - started) * 1000
    except Exception:
        return 0, (time.perf_counter() - started) * 1000


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((pct / 100) * len(ordered) + 0.999999) - 1))
    return ordered[index]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="DepotFlow origin")
    parser.add_argument("--email", default="operator@north.example")
    parser.add_argument("--password", default="DepotDemo!2026")
    parser.add_argument("--requests", type=int, default=1000, help="number of measured requests")
    parser.add_argument("--concurrency", type=int, default=16)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")
    origin = args.url.rstrip("/")
    status, _ = request(origin + "/api/health")
    if status != 200:
        raise SystemExit("DepotFlow health check failed")
    login_req = urllib.request.Request(origin + "/api/session", data=json.dumps({"email": args.email, "password": args.password}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(login_req, timeout=30) as response:
        token = json.loads(response.read())["token"]
    auth = {"Authorization": f"Bearer {token}"}
    run_id = uuid.uuid4().hex[:12]
    failures = []
    started = time.perf_counter()

    def task(index):
        # Fixed 4:1 mix: inventory, dashboard, order list, inventory, create.
        kind = index % 5
        if kind == 0:
            route, write = "/api/inventory", False
        elif kind == 1:
            route, write = "/api/dashboard", False
        elif kind == 2:
            route, write = "/api/orders?status=draft&limit=10", False
        elif kind == 3:
            route, write = "/api/inventory", False
        else:
            route, write = "/api/orders", True
        if write:
            payload = {"client_ref": f"load-{run_id}-{index}", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
            result, latency = request(origin + route, "POST", payload, {**auth, "Idempotency-Key": f"load-{run_id}-{index}"})
        else:
            result, latency = request(origin + route, headers=auth)
        category = "write" if write else "read"
        if result not in ((201,) if write else (200,)):
            failures.append({"kind": category, "status": result})
        return category, latency

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(task, range(args.requests)))
    duration = time.perf_counter() - started
    read_latencies = [latency for category, latency in results if category == "read"]
    write_latencies = [latency for category, latency in results if category == "write"]
    read_count, write_count = len(read_latencies), len(write_latencies)
    print(json.dumps({
        "workload": "80% reads (inventory/dashboard/order list), 20% unique SAMPLE order creates",
        "requests": args.requests,
        "concurrency": args.concurrency,
        "duration_seconds": round(duration, 3),
        "throughput_requests_per_second": round(args.requests / duration, 2),
        "read": {"count": read_count, "throughput_per_second": round(read_count / duration, 2), "p50_ms": round(percentile(read_latencies, 50), 2), "p95_ms": round(percentile(read_latencies, 95), 2)},
        "write": {"count": write_count, "throughput_per_second": round(write_count / duration, 2), "p50_ms": round(percentile(write_latencies, 50), 2), "p95_ms": round(percentile(write_latencies, 95), 2)},
        "errors": len(failures),
        "error_sample": failures[:5],
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "logical_cpus": os.cpu_count()},
    }, indent=2))


if __name__ == "__main__":
    main()
