"""Reproducible local HTTP workload. Writes are create -> reserve -> ship."""
import argparse
import concurrent.futures
import json
import os
import platform
import socket
import statistics
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(base, path, token=None, body=None, key=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
        if key:
            headers["Idempotency-Key"] = key
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method="POST" if body is not None else "GET")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read()), (time.perf_counter() - start) * 1000
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read()), (time.perf_counter() - start) * 1000
    except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
        return 0, {"transport_error": str(error)}, (time.perf_counter() - start) * 1000


def summarize(samples, seconds):
    latencies = sorted(s[2] for s in samples)
    error_types = {}
    for status, body, _ in samples:
        if status < 200 or status >= 300:
            detail = body.get("error", {}).get("code") or body.get("transport_error") or str(status)
            error_types[detail] = error_types.get(detail, 0) + 1
    return {
        "requests": len(samples),
        "elapsed_seconds": round(seconds, 3),
        "requests_per_second": round(len(samples) / seconds, 1),
        "latency_ms_p50": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(latencies[max(0, int(len(latencies) * .95) - 1)], 2),
        "latency_ms_max": round(max(latencies), 2),
        "errors": sum(status < 200 or status >= 300 for status, _, _ in samples),
        "error_types": error_types,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reads", type=int, default=300)
    parser.add_argument("--workflows", type=int, default=80)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--output", default=str(ROOT / "performance-results.json"))
    args = parser.parse_args()
    if min(args.reads, args.workflows, args.concurrency) < 1:
        parser.error("all counts must be positive")
    if args.workflows > 10000:
        parser.error("workflows must be at most 10000")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(dir=ROOT) as data_dir:
        env = os.environ.copy()
        env.update({"PORT": str(port), "DATA_DIR": data_dir, "SEED_DEMO": "1"})
        process = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if request(base, "/api/health")[0] == 200:
                    break
                time.sleep(.05)
            else:
                raise RuntimeError("server did not start")
            status, session, _ = request(base, "/api/session", body={"email": "admin@north.example", "password": "DepotDemo!2026"})
            if status != 200:
                raise RuntimeError("login failed")
            token = session["token"]
            # Add enough stock for every one-unit shipment.
            status, _, _ = request(base, "/api/stock/adjustments", token,
                                   {"sku": "BOLT", "delta": args.workflows, "expected_version": 1, "reason": "load exercise"}, "load-stock")
            if status != 200:
                raise RuntimeError("stock setup failed")

            paths = ("/api/inventory", "/api/orders", "/api/dashboard")
            start = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                reads = list(pool.map(lambda i: request(base, paths[i % len(paths)], token), range(args.reads)))
            read_seconds = time.perf_counter() - start

            def workflow(i):
                samples = []
                status, order, latency = request(base, "/api/orders", token,
                    {"client_ref": f"load-{i:05d}", "lines": [{"sku": "BOLT", "quantity": 1}]}, f"create-{i}")
                samples.append((status, order, latency))
                if status != 201:
                    return samples
                order_id = order["id"]
                status, reserved, latency = request(base, f"/api/orders/{order_id}/reserve", token,
                    {"expected_version": 1}, f"reserve-{i}")
                samples.append((status, reserved, latency))
                if status != 200:
                    return samples
                samples.append(request(base, f"/api/orders/{order_id}/ship", token,
                    {"expected_version": 2}, f"ship-{i}"))
                return samples

            start = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                write_workflows = list(pool.map(workflow, range(args.workflows)))
            write_seconds = time.perf_counter() - start
            writes = [item for workflow_samples in write_workflows for item in workflow_samples]
            status, dashboard, _ = request(base, "/api/dashboard", token)
            result = {
                "methodology": "Local loopback HTTP, fresh SQLite store, seeded tenant, three round-robin GET routes followed by concurrent create/reserve/ship workflows; each worker runs its workflow sequentially.",
                "environment": {"platform": platform.platform(), "machine": platform.machine(), "logical_cpus": os.cpu_count(), "python": platform.python_version()},
                "settings": {"reads": args.reads, "workflows": args.workflows, "concurrency": args.concurrency},
                "reads": summarize(reads, read_seconds),
                "writes": summarize(writes, write_seconds),
                "final_dashboard": dashboard if status == 200 else {"error": status},
            }
            Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            if result["reads"]["errors"] or result["writes"]["errors"]:
                raise RuntimeError("workload had HTTP errors")
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
