#!/usr/bin/env python3
"""Repeatable local read/write exercise for DepotFlow."""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


BASE = os.environ.get("DEPOTFLOW_BASE", "http://127.0.0.1:8000").rstrip("/")
PASSWORD = "DepotDemo!2026"


def request(method: str, path: str, body: dict | None = None, token: str | None = None, key: str | None = None):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["Idempotency-Key"] = key
    raw = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=raw, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            response.read()
            return response.status, time.perf_counter() - started, ""
    except urllib.error.HTTPError as error:
        error.read()
        return error.code, time.perf_counter() - started, "http_error"
    except Exception as error:
        return 0, time.perf_counter() - started, f"{type(error).__name__}: {error}"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reads", type=int, default=240)
    parser.add_argument("--writes", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=12)
    args = parser.parse_args()
    req = urllib.request.Request(
        BASE + "/api/session",
        data=json.dumps({"email": "admin@north.example", "password": PASSWORD}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.status != 200:
                raise SystemExit(f"login failed with status {response.status}")
            token = json.loads(response.read().decode())["token"]
    except urllib.error.HTTPError as error:
        raise SystemExit(f"login failed with status {error.code}") from error
    run_prefix = f"{os.getpid()}-{time.time_ns()}"

    def read_one(index: int):
        return request("GET", "/api/inventory", token=token)

    def write_one(index: int):
        return request(
            "POST",
            "/api/orders",
            {"client_ref": f"load-{run_prefix}-{index}", "lines": [{"sku": "SAMPLE", "quantity": 1}]},
            token=token,
            key=f"load-{run_prefix}-{index}",
        )

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        read_results = list(pool.map(read_one, range(args.reads)))
    read_elapsed = time.perf_counter() - started
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        write_results = list(pool.map(write_one, range(args.writes)))
    write_elapsed = time.perf_counter() - started

    def report(name: str, results: list[tuple[int, float, str]], elapsed: float) -> None:
        latencies = [latency for _, latency, _ in results]
        errors = sum(status < 200 or status >= 300 for status, _, _ in results)
        error_types = collections.Counter(error for status, _, error in results if status < 200 or status >= 300)
        print(
            f"{name}: requests={len(results)} concurrency={args.concurrency} "
            f"throughput={len(results) / elapsed:.2f} req/s elapsed={elapsed:.3f}s "
            f"avg={statistics.mean(latencies) * 1000:.2f}ms p95={percentile(latencies, .95) * 1000:.2f}ms "
            f"errors={errors} error_types={dict(error_types)}"
        )

    print(f"base={BASE} reads={args.reads} writes={args.writes}")
    report("reads", read_results, read_elapsed)
    report("writes", write_results, write_elapsed)


if __name__ == "__main__":
    main()
