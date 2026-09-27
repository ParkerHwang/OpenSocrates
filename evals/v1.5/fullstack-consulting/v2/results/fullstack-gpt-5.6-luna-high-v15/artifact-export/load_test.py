#!/usr/bin/env python3
"""Repeatable local smoke/load exercise: GET inventory plus idempotent order writes."""
import json, os, statistics, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.environ.get("TOKEN")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "8")); READS = int(os.environ.get("READS", "100")); WRITES = int(os.environ.get("WRITES", "40"))
lock = threading.Lock(); results = {"read": [], "write": [], "read_errors": 0, "write_errors": 0}

def call(method, path, body=None, key=None):
    req = urllib.request.Request(BASE + path, method=method)
    if TOKEN: req.add_header("Authorization", "Bearer " + TOKEN)
    if key: req.add_header("Idempotency-Key", key)
    if body is not None: req.data=json.dumps(body).encode(); req.add_header("Content-Type","application/json")
    start=time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as response: response.read(); status=response.status
    except Exception: status=0
    elapsed=(time.perf_counter()-start)*1000
    return status, elapsed

def read_one(_):
    status, ms=call("GET","/api/inventory")
    with lock: results["read"].append(ms); results["read_errors"] += status != 200
def write_one(n):
    body={"client_ref":f"load-{n}-{time.time_ns()}","lines":[{"sku":"SAMPLE","quantity":1}]}
    status, ms=call("POST","/api/orders",body,"load-"+str(n)+"-"+str(time.time_ns()))
    with lock: results["write"].append(ms); results["write_errors"] += status != 201

with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
    read_start = time.perf_counter(); list(pool.map(read_one, range(READS))); read_elapsed = time.perf_counter() - read_start
    write_start = time.perf_counter(); list(pool.map(write_one, range(WRITES))); write_elapsed = time.perf_counter() - write_start
for kind in ("read", "write"):
    vals=results[kind]; elapsed = read_elapsed if kind == "read" else write_elapsed; print(f"{kind}: count={len(vals)} throughput={len(vals)/elapsed:.2f}/s mean_ms={statistics.mean(vals):.2f} p95_ms={sorted(vals)[max(0,int(len(vals)*.95)-1)]:.2f} errors={results[kind+'_errors']}")
