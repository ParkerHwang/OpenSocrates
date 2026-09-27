#!/usr/bin/env python3
"""Repeatable local DepotFlow read/write workload.

The driver intentionally uses the public HTTP API rather than internal helpers.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PASSWORD = "DepotDemo!2026"


def request(base_url: str, method: str, path: str, token: str | None = None, payload=None, key: str | None = None):
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, separators=(",", ":")).encode()
    if key:
        headers["Idempotency-Key"] = key
    req = Request(base_url.rstrip("/") + path, method=method, headers=headers, data=body)
    started = time.perf_counter()
    try:
        with urlopen(req, timeout=20) as response:
            response.read()
            return response.status, (time.perf_counter() - started) * 1000, None
    except HTTPError as exc:
        exc.read()
        return exc.code, (time.perf_counter() - started) * 1000, f"http_{exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return 0, (time.perf_counter() - started) * 1000, type(exc).__name__


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def login(base_url: str, email: str) -> str:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    request_body = json.dumps({"email": email, "password": PASSWORD}).encode()
    req = Request(base_url.rstrip("/") + "/api/session", method="POST", headers=headers, data=request_body)
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())["token"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="admin@north.example")
    parser.add_argument("--read-count", type=int, default=200)
    parser.add_argument("--write-count", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    if min(args.read_count, args.write_count, args.concurrency) < 0 or args.concurrency == 0:
        parser.error("counts must be non-negative and concurrency must be positive")

    try:
        token = login(args.base_url, args.email)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"login failed: {type(exc).__name__}") from exc

    jobs: list[tuple[str, int]] = [("read", index) for index in range(args.read_count)]
    jobs.extend(("write", index) for index in range(args.write_count))

    def run(job: tuple[str, int]):
        kind, index = job
        if kind == "read":
            paths = ["/api/inventory", "/api/dashboard", "/api/orders?limit=20"]
            return kind, request(args.base_url, "GET", paths[index % len(paths)], token=token)
        payload = {"client_ref": f"load-{os.getpid()}-{index}", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        return kind, request(args.base_url, "POST", "/api/orders", token=token, payload=payload, key=f"load-{os.getpid()}-{index}")

    results = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(run, job) for job in jobs]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.perf_counter() - started

    output = {"base_url": args.base_url, "concurrency": args.concurrency, "elapsed_seconds": round(elapsed, 4), "results": {}}
    for kind in ("read", "write"):
        values = [latency for result_kind, (_, latency, _) in results if result_kind == kind]
        errors = [error for result_kind, (_, _, error) in results if result_kind == kind and error]
        successes = len(values) - len(errors)
        output["results"][kind] = {
            "requests": len(values),
            "successes": successes,
            "errors": len(errors),
            "throughput_rps": round(len(values) / elapsed, 2) if elapsed else 0.0,
            "latency_ms": {
                "min": round(min(values), 3) if values else 0.0,
                "mean": round(statistics.mean(values), 3) if values else 0.0,
                "p50": round(percentile(values, 0.50), 3),
                "p95": round(percentile(values, 0.95), 3),
                "max": round(max(values), 3) if values else 0.0,
            },
            "error_types": sorted({error for error in errors}),
        }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
