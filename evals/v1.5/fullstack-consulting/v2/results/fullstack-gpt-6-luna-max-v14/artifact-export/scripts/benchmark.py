#!/usr/bin/env python3
"""Run an isolated, repeatable HTTP read/write workload against DepotFlow."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import random
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(base: str, method: str, path: str, token: str | None = None, body: dict | None = None, key: str | None = None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            response.read()
            return {"latency_ms": (time.perf_counter() - started) * 1000, "status": response.status}
    except urllib.error.HTTPError as error:
        error.read()
        return {"latency_ms": (time.perf_counter() - started) * 1000, "status": error.code}
    except Exception as error:
        return {"latency_ms": (time.perf_counter() - started) * 1000, "status": 0, "error": str(error)}


def wait_healthy(base: str, process: subprocess.Popen) -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        if process.poll() is not None:
            message = process.stderr.read().decode(errors="replace") if process.stderr else ""
            raise RuntimeError(f"server exited early ({process.returncode}): {message}")
        result = request(base, "GET", "/api/health")
        if result["status"] == 200:
            return
        time.sleep(0.05)
    raise RuntimeError("server health check timed out")


def summarize(results: list[dict], elapsed: float) -> dict:
    latencies = sorted(item["latency_ms"] for item in results)
    statuses = Counter(str(item["status"]) for item in results)
    errors = sum(item["status"] < 200 or item["status"] >= 300 for item in results)

    def percentile(fraction: float) -> float | None:
        if not latencies:
            return None
        return round(latencies[min(len(latencies) - 1, int((len(latencies) - 1) * fraction))], 3)

    return {
        "requests": len(results),
        "throughput_per_second": round(len(results) / elapsed, 2) if elapsed else None,
        "latency_ms": {"p50": percentile(0.50), "p95": percentile(0.95), "p99": percentile(0.99), "mean": round(sum(latencies) / len(latencies), 3) if latencies else None},
        "errors": errors,
        "status_counts": dict(sorted(statuses.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reads", type=int, default=600, help="number of authenticated GET requests")
    parser.add_argument("--writes", type=int, default=100, help="number of order creation requests")
    parser.add_argument("--concurrency", type=int, default=8, help="client worker threads")
    args = parser.parse_args()
    if args.reads < 0 or args.writes < 0 or args.concurrency < 1 or not (args.reads + args.writes):
        parser.error("reads and writes must be nonnegative with at least one request; concurrency must be positive")

    with tempfile.TemporaryDirectory(prefix="depotflow-benchmark-") as temp_dir:
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update({"PORT": str(port), "DATA_DIR": str(Path(temp_dir) / "state"), "SEED_DEMO": "1", "QUIET_HTTP": "1"})
        process = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            wait_healthy(base, process)
            session_req = urllib.request.Request(
                base + "/api/session",
                data=json.dumps({"email": "operator@north.example", "password": "DepotDemo!2026"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(session_req, timeout=10) as response:
                session = json.loads(response.read())
            token = session["token"]
            run_id = uuid.uuid4().hex[:10]
            read_paths = ["/api/inventory", "/api/dashboard", "/api/orders?limit=20"]
            reads = [("read", read_paths[index % 3], None, None) for index in range(args.reads)]
            writes = [
                ("write", "/api/orders", {"client_ref": f"LOAD-{run_id}-{index:06d}", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, f"load-{run_id}-{index}")
                for index in range(args.writes)
            ]
            tasks = reads + writes
            random.Random(41).shuffle(tasks)

            def execute(task):
                kind, path, body, key = task
                method = "POST" if kind == "write" else "GET"
                return kind, request(base, method, path, token=token, body=body, key=key)

            results = {"read": [], "write": []}
            started = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = [pool.submit(execute, task) for task in tasks]
                for future in concurrent.futures.as_completed(futures):
                    kind, result = future.result()
                    results[kind].append(result)
            elapsed = time.perf_counter() - started
            output = {
                "environment": {
                    "os": platform.platform(),
                    "machine": platform.machine(),
                    "processor": platform.processor() or "not reported by Python",
                    "logical_cpus": os.cpu_count(),
                    "python": platform.python_version(),
                    "storage": "SQLite WAL on local temporary directory",
                },
                "method": {
                    "server": "local DepotFlow process on 127.0.0.1",
                    "workers": args.concurrency,
                    "request_mix": "authenticated inventory/dashboard/order-list reads plus unique zero-price SAMPLE order creates",
                    "timed_seconds": round(elapsed, 4),
                    "total_requests": len(tasks),
                },
                "read": summarize(results["read"], elapsed),
                "write": summarize(results["write"], elapsed),
                "combined": summarize(results["read"] + results["write"], elapsed),
            }
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0 if output["combined"]["errors"] == 0 else 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
