"""Execute the existing frozen qualification on disposable, unmodified copies.

No model calls, candidate repairs or changed scoring rules. Results are exclusive.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "v2"
sys.path.insert(0, str(BASE))
import api_check
import office_check
import runner as frozen


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def environment(base, manifest):
    tools = manifest["tools"]
    home = base / "home"
    home.mkdir()
    (base / "tmp").mkdir()
    return {
        "PATH": str(Path(tools["python"]).parent) + ":" + str(Path(tools["node"]).parent) + ":/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(home), "TMPDIR": str(base / "tmp"),
        "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTHON": tools["python"], "PYTHON_BIN": tools["python"],
        "NODE_PATH": tools["node_modules"],
        "EVAL_CHROMIUM": tools["browser_executable"],
    }


def policy(base, manifest):
    tools = manifest["tools"]
    text = f'''(version 1)
(allow default)
(deny file-read-data (require-all (require-any (subpath "/Users") (subpath "/private/tmp") (subpath "/private/var/folders")) (require-not (require-any (subpath "{base}") (subpath "{tools['runtime_root']}") (subpath "{tools['browser_root']}")))))
(deny file-write* (require-not (subpath "{base}")))
'''
    p = base / "execution.sb"
    p.write_text(text)
    return p


def prepare(cell, storage, manifest, workroot):
    base = workroot / cell["id"]
    base.mkdir()
    original = storage / cell["id"] / "locked-artifacts"
    snapshot = read(BASE / "results" / cell["id"] / "snapshot.json")
    assert frozen.inventory(original) == snapshot["files"], "Original lock mismatch"
    shutil.copytree(original, base / "workspace")
    assert frozen.inventory(base / "workspace") == snapshot["files"], "Copy mismatch"
    env = environment(base, manifest)
    sb = policy(base, manifest)
    result = HERE / "results" / cell["id"]
    result.mkdir(parents=True)
    save(result / "started.json", {
        "utc": now(), "cell": cell, "manifest_sha256": sha(HERE / "manifest.json"),
        "snapshot_sha256": sha(BASE / "results" / cell["id"] / "snapshot.json"),
        "original_and_copy_verified": True,
        "environment": {k: v.replace(str(base), "<QUALIFICATION_CELL>") for k, v in env.items()},
        "subject_repairs": 0, "model_calls": 0,
    })
    return base, env, sb, result


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(base, env, sb, phase, data, port=None):
    port = port or free_port()
    data.mkdir(exist_ok=True)
    env = {**env, "PORT": str(port), "DATA_DIR": str(data), "SEED_DEMO": "1"}
    log = (base / f"{phase}-server.log").open("wb")
    command = ["/usr/bin/sandbox-exec", "-f", str(sb), str(base / "workspace/run.sh")]
    proc = subprocess.Popen(command, cwd=base / "workspace", env=env, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True)
    url = f"http://127.0.0.1:{port}"
    while proc.poll() is None:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.5):
                return proc, log, url
        except OSError:
            time.sleep(.1)
    log.close()
    raise RuntimeError(f"Server exited before listening: {proc.returncode}; see {phase}-server.log")


def stop(proc, log):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait()
    log.close()


def restart_check(url, output, expectation):
    probe = api_check.Probe(url, output)
    output.mkdir()
    probe.group("fresh_login_after_restart", probe.login, True)
    probe.group("stock_preserved", lambda: probe.stock() == expectation.get("stock"), True)
    probe.group("order_count_preserved", lambda: sum(probe.ok("GET", "/api/dashboard")["orders_by_status"].values()) == expectation.get("order_count"), True)

    def replay():
        original = expectation["replay"]
        first = probe.req("POST", "/api/orders", original["body"], key="replay-create")
        return list(first) == list(original["response"])

    probe.group("successful_response_replayed_after_restart", replay, True)
    return {"groups": probe.groups, "pass": all(g["pass"] for g in probe.groups)}


def performance(url, output, concurrency):
    output.mkdir()
    probe = api_check.Probe(url, output)
    probe.login()
    token = probe.tokens["admin"]
    summary = []
    for kind, count in (("inventory_get", 500), ("draft_order_post", 200)):
        def request(i):
            body = None if kind == "inventory_get" else {"client_ref": f"PERF-{concurrency}-{i}", "lines": [{"sku": "BOLT", "quantity": 1}]}
            path = "/api/inventory" if body is None else "/api/orders"
            method = "GET" if body is None else "POST"
            headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
            if body is not None:
                headers["Idempotency-Key"] = f"perf-{concurrency}-{i}"
            req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
            begin = time.monotonic()
            status, error, raw = None, None, b""
            try:
                with urllib.request.urlopen(req) as response:
                    status, raw = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, raw = exc.code, exc.read()
            except Exception as exc:
                error = repr(exc)
            elapsed = time.monotonic() - begin
            return {"request": i, "method": method, "path": path, "status": status,
                    "seconds": elapsed, "error": error, "response_sha256": hashlib.sha256(raw).hexdigest(),
                    "error_body": raw.decode("utf-8", "replace")[:3000] if status is not None and status >= 400 else None}
        begin = time.monotonic()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            records = list(pool.map(request, range(count)))
        elapsed = time.monotonic() - begin
        with (output / f"{kind}-requests.jsonl").open("x") as stream:
            for record in records:
                stream.write(json.dumps(record) + "\n")
        latencies = sorted(r["seconds"] * 1000 for r in records)
        failures = sum(r["status"] is None or not 200 <= r["status"] < 300 for r in records)
        summary.append({"workload": kind, "concurrency": concurrency, "requests": count,
                        "wall_seconds": elapsed, "requests_per_second": count / elapsed,
                        "errors": failures, **{f"p{q}_ms": latencies[math.ceil(count * q / 100) - 1] for q in (50, 95, 99)}})
    return summary


def coding(cell, storage, manifest, workroot):
    base, env, sb, result = prepare(cell, storage, manifest, workroot)
    summary = {"cell": cell["id"], "started_utc": now(), "candidate_repairs": 0}
    proc = log = None
    try:
        proc, log, url = start(base, env, sb, "api", base / "api-data")
        api = api_check.Probe(url, result / "api").run()
        save(result / "api.json", api)
        summary["api"] = {k: api[k] for k in ("passed", "total", "critical_pass")}
        stop(proc, log); proc = log = None
        proc, log, url = start(base, env, sb, "restart", base / "api-data")
        restart = restart_check(url, result / "restart", api["persistence_expectation"])
        save(result / "restart.json", restart)
        summary["restart"] = restart["pass"]
        stop(proc, log); proc = log = None
        proc, log, url = start(base, env, sb, "browser", base / "browser-data")
        shutil.copyfile(BASE / "browser_check.cjs", base / "browser_check.cjs")
        browser_output = base / "browser-output"
        browser = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(sb), manifest["tools"]["node"], str(base / "browser_check.cjs"), url, str(browser_output)], env=env, cwd=base / "workspace", capture_output=True, text=True)
        if browser_output.exists():
            shutil.copytree(browser_output, result / "browser")
        save(result / "browser-process.json", {"exit_code": browser.returncode, "stderr": browser.stderr.replace(str(base), "<QUALIFICATION_CELL>")})
        summary["browser"] = {k: read(browser_output / "browser.json")[k] for k in ("passed", "total")} if (browser_output / "browser.json").exists() else {"harness_error": True}
        stop(proc, log); proc = log = None
        summary["performance_eligible"] = api["critical_pass"] and restart["pass"]
        if summary["performance_eligible"]:
            perf = []
            for concurrency in (1, 8):
                proc, log, url = start(base, env, sb, f"performance-{concurrency}", base / f"performance-data-{concurrency}")
                perf.extend(performance(url, result / f"performance-{concurrency}", concurrency))
                stop(proc, log); proc = log = None
            save(result / "performance.json", {"eligibility": "frozen critical API checks and restart pass", "serial_across_cells": True, "fresh_database_per_concurrency": True, "measurements": perf})
            summary["performance"] = perf
        else:
            summary["performance"] = None
            summary["performance_not_run_reason"] = "Failed critical API behavior or durable restart; not performance-equivalent."
    except Exception as exc:
        summary["harness_error"] = repr(exc).replace(str(base), "<QUALIFICATION_CELL>")
    finally:
        if proc is not None:
            stop(proc, log)
        for p in base.glob("*-server.log"):
            (result / p.name).write_text(p.read_text(errors="replace").replace(str(base), "<QUALIFICATION_CELL>"))
        original = storage / cell["id"] / "locked-artifacts"
        summary["original_still_matches_snapshot"] = frozen.inventory(original) == read(BASE / "results" / cell["id"] / "snapshot.json")["files"]
        summary["ended_utc"] = now()
        save(result / "result.json", summary)
        print(json.dumps(summary), flush=True)


def office(cell, storage, manifest, workroot):
    base, env, sb, result = prepare(cell, storage, manifest, workroot)
    value = office_check.check(base / "workspace")
    save(result / "office.json", value)
    save(result / "result.json", {"cell": cell["id"], "passed": value["passed"], "total": value["total"], "ended_utc": now(), "qualification": "frozen numerical/file checks only; semantic and rendered review pending", "original_still_matches_snapshot": frozen.inventory(storage / cell["id"] / "locked-artifacts") == read(BASE / "results" / cell["id"] / "snapshot.json")["files"]})
    print(json.dumps({"cell": cell["id"], "office": f"{value['passed']}/{value['total']}", "failed_groups": [g['name'] for g in value['groups'] if not g['pass_']]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["coding", "office"])
    parser.add_argument("--storage", type=Path, required=True)
    parser.add_argument("--workroot", type=Path, required=True)
    args = parser.parse_args()
    args.workroot = args.workroot.resolve()
    args.storage = args.storage.resolve()
    manifest = read(BASE / "manifest.json")
    frozen_qualification = read(HERE / "manifest.json")
    for name, digest in frozen_qualification["qualification_files"].items():
        assert sha(HERE / name) == digest, name
    for name, digest in manifest["frozen_files"].items():
        assert sha(BASE / name) == digest, name
    args.workroot.mkdir(exist_ok=True)
    for cell in manifest["cells"]:
        if cell["task"] != ("fullstack" if args.phase == "coding" else "consulting"):
            continue
        target = HERE / "results" / cell["id"]
        if target.exists():
            if (target / "result.json").exists():
                continue
            raise RuntimeError(f"Unfinished existing qualification; inspect, never auto-retry: {cell['id']}")
        (coding if args.phase == "coding" else office)(cell, args.storage, manifest, args.workroot)
