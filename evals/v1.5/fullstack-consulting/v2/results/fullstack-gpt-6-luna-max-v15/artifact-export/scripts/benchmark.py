#!/usr/bin/env python3
"""Repeatable local DepotFlow read/write workload; uses only the Python stdlib."""

import argparse
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
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "DepotDemo!2026"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def json_request(url, method="GET", headers=None, body=None):
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    data = None
    if body is not None:
        request_headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        payload = error.read()
        try:
            result = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            result = None
        return error.code, result


def wait_ready(base, process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError(f"DepotFlow stopped during startup (exit {process.returncode}).")
        try:
            status, result = json_request(base + "/api/health")
            if status == 200 and result == {"status": "ok"}:
                return
        except Exception:
            pass
        time.sleep(0.05)
    raise RuntimeError("DepotFlow did not become ready within 10 seconds.")


def summarize(name, samples, statuses, errors, elapsed):
    ordered = sorted(samples)
    p50 = statistics.median(ordered) if ordered else 0.0
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))] if ordered else 0.0
    return {
        "phase": name,
        "requests": len(samples),
        "elapsed_seconds": round(elapsed, 4),
        "requests_per_second": round(len(samples) / elapsed, 2) if elapsed else 0,
        "latency_ms": {
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "max": round(max(ordered), 3) if ordered else 0,
        },
        "errors": errors,
        "status_counts": statuses,
    }


def run_phase(name, count, concurrency, task):
    samples = []
    errors = 0
    statuses = {}
    start = time.perf_counter()

    def timed(index):
        before = time.perf_counter()
        try:
            status = task(index)
        except Exception:
            status = 0
        return status, (time.perf_counter() - before) * 1000

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for status, latency in pool.map(timed, range(count)):
            samples.append(latency)
            statuses[str(status)] = statuses.get(str(status), 0) + 1
            if not 200 <= status < 300:
                errors += 1
    elapsed = time.perf_counter() - start
    return summarize(name, samples, statuses, errors, elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-requests", type=int, default=300)
    parser.add_argument("--write-requests", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    if args.read_requests < 1 or args.write_requests < 1 or args.concurrency < 1:
        parser.error("request counts and concurrency must be positive")

    with tempfile.TemporaryDirectory(prefix="depotflow-benchmark-") as temp:
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update({"DATA_DIR": str(Path(temp) / "data"), "PORT": str(port), "SEED_DEMO": "1"})
        process = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            wait_ready(base, process)
            status, session = json_request(base + "/api/session", "POST", body={"email": "operator@north.example", "password": PASSWORD})
            if status != 200:
                raise RuntimeError(f"Unable to log in to benchmark instance (HTTP {status}).")
            token = session["token"]
            auth = {"Authorization": f"Bearer {token}"}
            read_paths = ["/api/inventory", "/api/dashboard", "/api/orders?limit=20", "/api/audit?limit=20"]

            def read_task(index):
                return json_request(base + read_paths[index % len(read_paths)], headers=auth)[0]

            read_result = run_phase("authenticated_reads", args.read_requests, args.concurrency, read_task)
            run_id = uuid.uuid4().hex[:10]

            def write_task(index):
                body = {"client_ref": f"bench-{run_id}-{index}", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
                headers = {**auth, "Idempotency-Key": f"bench-{run_id}-{index}"}
                return json_request(base + "/api/orders", "POST", headers=headers, body=body)[0]

            write_result = run_phase("order_create_writes", args.write_requests, args.concurrency, write_task)
            print(json.dumps({
                "workload": {
                    "read_requests": args.read_requests,
                    "write_requests": args.write_requests,
                    "concurrency": args.concurrency,
                    "read_mix": read_paths,
                    "write_operation": "POST /api/orders with one SAMPLE unit and a unique reference/key",
                    "seed": "fresh temporary SQLite data directory per run",
                },
                "environment": {
                    "platform": platform.platform(),
                    "processor": platform.processor() or "not reported by Python",
                    "logical_cpu_count": os.cpu_count(),
                    "python": platform.python_version(),
                },
                "results": [read_result, write_result],
            }, indent=2))
            if read_result["errors"] or write_result["errors"]:
                raise SystemExit(1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
