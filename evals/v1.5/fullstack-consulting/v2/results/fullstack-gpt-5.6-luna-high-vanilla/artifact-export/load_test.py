#!/usr/bin/env python3
"""Repeatable local HTTP workload. Usage: python3 load_test.py [base-url] [workers] [requests]."""
import concurrent.futures
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
REQUESTS = int(sys.argv[3]) if len(sys.argv) > 3 else 400

def request(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if token: headers["Authorization"] = "Bearer " + token
    if body is not None: headers.update({"Content-Type": "application/json", "Idempotency-Key": "load-" + str(time.time_ns())})
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            response.read(); status = response.status
    except urllib.error.HTTPError as exc:
        exc.read(); status = exc.code
    except Exception:
        status = 599
    return (time.perf_counter() - start) * 1000, status

with urllib.request.urlopen(BASE + "/api/health", timeout=5) as response:
    assert response.status == 200
payload = json.dumps({"email": "viewer@north.example", "password": "DepotDemo!2026"}).encode()
login_req = urllib.request.Request(BASE + "/api/session", data=payload, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(login_req, timeout=5) as response:
    token = json.load(response)["token"]
payload = json.dumps({"email": "admin@north.example", "password": "DepotDemo!2026"}).encode()
login_req = urllib.request.Request(BASE + "/api/session", data=payload, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(login_req, timeout=5) as response:
    admin_token = json.load(response)["token"]

def read_one(i):
    return request("GET", "/api/inventory", token=token)

def write_one(i):
    return request("POST", "/api/orders", token=admin_token, body={"client_ref": f"load-{time.time_ns()}-{i}", "lines": [{"sku": "SAMPLE", "quantity": 1}]})

def phase(label, fn, count):
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(fn, range(count)))
    elapsed = time.perf_counter() - start
    latencies = [x[0] for x in results]
    errors = sum(status >= 400 for _, status in results)
    return {"workload": label, "requests": count, "concurrency": WORKERS, "elapsed_s": round(elapsed, 3), "throughput_rps": round(count / elapsed, 2), "latency_ms_p50": round(statistics.median(latencies), 2), "latency_ms_p95": round(sorted(latencies)[int(len(latencies) * .95) - 1], 2), "errors": errors}

count = max(1, REQUESTS // 2)
print(json.dumps({"read": phase("GET /api/inventory", read_one, count), "write": phase("POST /api/orders (draft SAMPLE)", write_one, count)}, indent=2))
