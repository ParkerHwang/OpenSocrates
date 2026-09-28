"""Frozen, serial external workload. Never run inside native read-only checks."""
from __future__ import annotations

import concurrent.futures
import subprocess
import time
from pathlib import Path

from qualify import event, launch, request, stop

SEED = 10000
WARMUP = 100
MEASURED = 1000
CONCURRENCIES = (1, 8, 32)
OPERATIONS = ("incident_list", "unique_event_ingestion")


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    data = sorted(values)
    index = (len(data) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(data) - 1)
    return round(data[lower] + (data[upper] - data[lower]) * (index - lower), 3)


def process_sample(pid: int) -> dict:
    try:
        raw = subprocess.check_output(["/bin/ps", "-o", "rss=,time=", "-p", str(pid)], timeout=2, text=True).strip().split()
        return {"rss_kib": int(raw[0]), "cpu_time": raw[1]}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return {"rss_kib": None, "cpu_time": None}


def run_batch(base: str, operation: str, concurrency: int, count: int, offset: int) -> dict:
    def one(index: int) -> tuple[bool, float]:
        began = time.perf_counter()
        try:
            if operation == "incident_list":
                status, body = request(base, "/api/incidents?status=open&severity=P2&q=perf-04242")
                success = status == 200 and len(body.get("items", [])) == 1 and body["items"][0].get("incident_id") == "perf-04242"
            else:
                name = f"load-{concurrency}-{offset+index:04d}"
                status, body = request(base, "/api/events", body=event(name, name, 1, "OPEN", "2026-06-01T00:00:00Z", severity="P2"))
                success = status == 201 and body.get("duplicate") is False
        except Exception:
            success = False
        return success, (time.perf_counter() - began) * 1000

    wall_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(one, range(count)))
    wall = time.perf_counter() - wall_start
    latencies = [latency for _, latency in results]
    success_count = sum(success for success, _ in results)
    return {
        "scheduled": count,
        "completed": len(results),
        "succeeded": success_count,
        "failed": len(results) - success_count,
        "wall_seconds": round(wall, 3),
        "throughput_completed_per_second": round(len(results) / wall, 3) if wall else None,
        "throughput_success_per_second": round(success_count / wall, 3) if wall else None,
        "latency_all_ms": {"p50": percentile(latencies, .50), "p95": percentile(latencies, .95), "p99": percentile(latencies, .99)},
    }


def measure(candidate: Path, env: dict) -> dict:
    cases = []
    for operation in OPERATIONS:
        for concurrency in CONCURRENCIES:
            db = candidate / f".eval-perf-{operation}-{concurrency}.db"
            if db.exists():
                raise RuntimeError("performance database already exists; use a fresh disposable copy")
            process, base = launch(candidate, db, env)
            seed_success = 0
            warmup = measurement = None
            sample_before = sample_after = {"rss_kib": None, "cpu_time": None}
            try:
                for index in range(SEED):
                    name = f"perf-{index:05d}"
                    try:
                        status, body = request(base, "/api/events", body=event(f"seed-{index:05d}", name, 1, "OPEN", "2026-06-01T00:00:00Z", severity="P2"))
                        seed_success += status == 201 and body.get("duplicate") is False
                    except Exception:
                        pass
                try:
                    seed_summary = request(base, "/api/summary")[1]
                except Exception:
                    seed_summary = {}
                warmup = run_batch(base, operation, concurrency, WARMUP, 0)
                sample_before = process_sample(process.pid)
                measurement = run_batch(base, operation, concurrency, MEASURED, WARMUP)
                sample_after = process_sample(process.pid)
                try:
                    post_summary = request(base, "/api/summary")[1]
                    outbox_response = request(base, "/api/outbox")[1]
                except Exception:
                    post_summary, outbox_response = {}, {}
            finally:
                stop(process)
            expected = SEED if operation == "incident_list" else SEED + WARMUP + MEASURED
            outbox_items = outbox_response.get("items", []) if isinstance(outbox_response, dict) else []
            state_valid = post_summary.get("total") == len(outbox_items) == expected and seed_summary.get("total") == SEED
            cases.append({
                "operation": operation, "concurrency": concurrency,
                "seed": {"scheduled": SEED, "succeeded": seed_success, "failed": SEED - seed_success, "summary_total": seed_summary.get("total")},
                "warmup": warmup, "measurement": measurement,
                "post_state": {"summary_total": post_summary.get("total"), "outbox_items": len(outbox_items), "expected": expected, "valid": state_valid},
                "process_before": sample_before, "process_after": sample_after,
            })
    accounted = all(x["warmup"]["scheduled"] == x["warmup"]["completed"] == WARMUP and x["measurement"]["scheduled"] == x["measurement"]["completed"] == MEASURED for x in cases)
    valid = all(x["seed"]["succeeded"] == SEED and x["warmup"]["failed"] == 0 and x["measurement"]["failed"] == 0 and x["post_state"]["valid"] for x in cases)
    return {"workload_version": "incidentops-perf-v1", "cases": cases, "seed_requests": SEED * len(cases), "warmup_requests": WARMUP * len(cases), "measured_requests": MEASURED * len(cases), "all_requests_accounted": accounted, "all_post_states_valid": valid}
