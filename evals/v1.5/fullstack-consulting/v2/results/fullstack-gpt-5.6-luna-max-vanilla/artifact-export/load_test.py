#!/usr/bin/env python3
"""Repeatable local read/write exercise for the real DepotFlow HTTP server."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PASSWORD = "DepotDemo!2026"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def request(base: str, method: str, path: str, token: str, body=None, key=None):
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if key:
        headers["Idempotency-Key"] = key
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            response.read()
            return response.status, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as error:
        error.read()
        return error.code, (time.perf_counter() - started) * 1000
    except (OSError, TimeoutError):
        return None, (time.perf_counter() - started) * 1000


def login(base: str) -> str:
    req = urllib.request.Request(
        base + "/api/session",
        data=json.dumps({"email": "operator@north.example", "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())["token"]


def summarize(name: str, samples: list[tuple[int | None, float]], expected: int, elapsed: float) -> dict:
    latencies = sorted(sample[1] for sample in samples)
    successful = sum(1 for status, _ in samples if status == expected)
    errors = len(samples) - successful

    def percentile(fraction: float) -> float:
        if not latencies:
            return 0.0
        index = min(len(latencies) - 1, int(round((len(latencies) - 1) * fraction)))
        return round(latencies[index], 2)

    return {
        "workload": name,
        "requests": len(samples),
        "successful": successful,
        "errors": errors,
        "throughput_rps": round(len(samples) / elapsed, 2) if elapsed else 0,
        "latency_ms": {
            "p50": percentile(0.50),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
            "max": round(max(latencies), 2) if latencies else 0,
        },
    }


def run_phase(name, duration, concurrency, worker):
    barrier = __import__("threading").Barrier(concurrency)

    def loop(worker_number):
        barrier.wait()
        deadline = time.perf_counter() + duration
        samples = []
        sequence = 0
        while time.perf_counter() < deadline:
            samples.append(worker(worker_number, sequence))
            sequence += 1
        return samples

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = [future.result() for future in [pool.submit(loop, worker_number) for worker_number in range(concurrency)]]
    elapsed = time.perf_counter() - started
    samples = [sample for worker_samples in results for sample in worker_samples]
    expected = 200 if name == "read" else 201
    return summarize(name, samples, expected, elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=5.0, help="seconds per phase (default: 5)")
    parser.add_argument("--concurrency", type=int, default=8, help="parallel HTTP workers per phase (default: 8)")
    parser.add_argument("--data-dir", help="persistent directory; defaults to a disposable local directory")
    args = parser.parse_args()
    if args.duration <= 0 or args.concurrency < 1:
        parser.error("duration must be positive and concurrency must be at least 1")
    owned_dir = None
    data_dir = args.data_dir
    if not data_dir:
        owned_dir = tempfile.mkdtemp(prefix=".depotflow-load-", dir=ROOT)
        data_dir = owned_dir
    port = free_port()
    env = os.environ.copy()
    env.update({"PORT": str(port), "DATA_DIR": data_dir, "SEED_DEMO": "1"})
    process = subprocess.Popen([sys.executable, str(ROOT / "server.py")], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.04)
        else:
            raise RuntimeError("server did not become healthy")
        token = login(base)
        # Warmup requests are intentionally excluded from both measured phases.
        request(base, "GET", "/api/inventory", token)
        request(base, "POST", "/api/orders", token, {"client_ref": "load-warmup", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, "load-warmup")

        read_result = run_phase("read", args.duration, args.concurrency, lambda _worker, _sequence: request(base, "GET", "/api/inventory", token))

        def write_request(worker_number, sequence):
            reference = f"load-{worker_number}-{sequence}-{uuid.uuid4().hex[:8]}"
            payload = {"client_ref": reference, "lines": [{"sku": "SAMPLE", "quantity": 1}]}
            return request(base, "POST", "/api/orders", token, payload, f"load-{reference}")

        write_result = run_phase("write", args.duration, args.concurrency, write_request)
        print(json.dumps({
            "server": "DepotFlow local HTTP/SQLite",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "duration_seconds_per_phase": args.duration,
            "concurrency": args.concurrency,
            "read": read_result,
            "write": write_result,
            "notes": [
                "Reads are GET /api/inventory; writes are unique SAMPLE draft-order creates.",
                "Latency is client-observed wall time; startup, login, and one warmup request are excluded.",
                "This is a single-process loopback measurement, not a production capacity claim.",
            ],
        }, indent=2))
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if owned_dir:
            import shutil
            shutil.rmtree(owned_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
