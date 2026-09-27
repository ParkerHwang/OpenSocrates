"""Versioned diagnostics; preserve all frozen first-pass results and subjects."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "qualification-v1"))
import qualify as q

BASE = ROOT / "v2"
MANIFEST = q.read(HERE / "manifest.json")
SOURCE = q.read(BASE / "manifest.json")
STORAGE = Path(sys.argv[1]).resolve()
WORK = Path(sys.argv[2]).resolve()
CELLS = {c["id"]: c for c in SOURCE["cells"]}
original_policy = q.policy


def policy(base, manifest):
    p = original_policy(base, manifest)
    s = p.read_text()
    old = f'(deny file-write* (require-not (subpath "{base}")))'
    assert s.count(old) == 1
    p.write_text(s.replace(old, f'(deny file-write* (require-not (require-any (subpath "{base}") (literal "/dev/null"))))'))
    return p


q.policy = policy
q.HERE = HERE


def fresh(name, phase):
    base = WORK / (name + "-" + phase)
    base.mkdir()
    original = STORAGE / name / "locked-artifacts"
    assert q.frozen.inventory(original) == q.read(BASE / "results" / name / "snapshot.json")["files"]
    shutil.copytree(original, base / "workspace")
    env = q.environment(base, SOURCE)
    sb = policy(base, SOURCE)
    output = HERE / phase / name
    output.mkdir(parents=True)
    return base, env, sb, output


def browser(name):
    base, env, sb, output = fresh(name, "browser")
    proc = log = None
    try:
        proc, log, url = q.start(base, env, sb, "browser", base / "data")
        shutil.copyfile(HERE / "browser_check.cjs", base / "browser_check.cjs")
        target = base / "output"
        p = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(sb), SOURCE["tools"]["node"], str(base / "browser_check.cjs"), url, str(target)], env=env, cwd=base / "workspace", capture_output=True, text=True)
        if target.exists():
            shutil.copytree(target, output / "evidence")
        result = {"cell": name, "exit_code": p.returncode, "stderr": p.stderr.replace(str(base), "<DIAGNOSTIC_CELL>"), "scope": "Auto-wait for asynchronous controls and client reference only; same flow and assertions; original score unchanged"}
        if (target / "browser.json").exists():
            r = q.read(target / "browser.json")
            result.update({k: r[k] for k in ("passed", "total", "groups")})
        q.save(output / "result.json", result)
        print(json.dumps(result), flush=True)
    finally:
        if proc:
            q.stop(proc, log)


def synchronized_requests(url, requests):
    """Pre-send headers; release bodies concurrently to separate accept backlog."""
    host, port = url.removeprefix("http://").split(":")
    pending = []
    for index, (path, body, token, key) in enumerate(requests):
        raw = json.dumps(body).encode()
        connection = http.client.HTTPConnection(host, int(port))
        try:
            connection.connect()
            connection.putrequest("POST", path)
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Authorization", "Bearer " + token)
            connection.putheader("Idempotency-Key", key)
            connection.putheader("Content-Length", str(len(raw)))
            connection.endheaders()
            pending.append((index, connection, raw, None))
        except Exception as exc:
            pending.append((index, connection, raw, repr(exc)))
        time.sleep(.02)

    def release(entry):
        index, connection, raw, error = entry
        record = {"index": index, "status": None, "body": None, "error": error}
        begin = time.monotonic()
        try:
            if error is None:
                connection.send(raw)
                response = connection.getresponse()
                record["status"] = response.status
                payload = response.read().decode("utf-8", "replace")
                try:
                    record["body"] = json.loads(payload)
                except ValueError:
                    record["body"] = payload
        except Exception as exc:
            record["error"] = repr(exc)
        finally:
            connection.close()
        record["seconds_after_body_release"] = time.monotonic() - begin
        return record

    with ThreadPoolExecutor(max_workers=len(requests)) as pool:
        return list(pool.map(release, pending))


def transport(name):
    base, env, sb, output = fresh(name, "transport")
    proc = log = None
    result = {"cell": name, "scope": "Application-state concurrency diagnostic; does not erase original burst connection failures or confer original performance eligibility"}
    try:
        proc, log, url = q.start(base, env, sb, "transport", base / "data")
        probe = q.api_check.Probe(url, output)
        probe.login()
        stock = probe.stock("south")["BOLT"]
        probe.ok("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 10-stock["on_hand"], "expected_version": stock["version"], "reason": "diagnostic fixture"}, "south", "stock")
        orders = [probe.create([{"sku": "BOLT", "quantity": 1}], who="south") for _ in range(20)]
        requests = [(f"/api/orders/{o['id']}/reserve", {"expected_version": o["version"]}, probe.tokens["south"], "reserve-" + str(o["id"])) for o in orders]
        reservations = synchronized_requests(url, requests)
        final = probe.stock("south")["BOLT"]
        codes = [r["status"] for r in reservations]
        result["reservations"] = {"requests": reservations, "final_stock": final, "pass": sum(c is not None and 200 <= c < 300 for c in codes) == 10 and codes.count(409) == 10 and (final["on_hand"], final["reserved"], final["available"]) == (10, 10, 0)}
        body = {"client_ref": "DIAGNOSTIC-DUPLICATE", "lines": [{"sku": "BOLT", "quantity": 1}]}
        before = len(probe.audit())
        records = synchronized_requests(url, [("/api/orders", body, probe.tokens["admin"], "duplicate") for _ in range(12)])
        after = len(probe.audit())
        pairs = [(r["status"], r["body"]) for r in records]
        result["idempotent_create"] = {"requests": records, "audit_delta": after-before, "pass": pairs[0][0] in (200, 201) and all(p == pairs[0] for p in pairs) and after-before == 1}
    except Exception as exc:
        result["harness_error"] = repr(exc).replace(str(base), "<DIAGNOSTIC_CELL>")
    finally:
        if proc:
            q.stop(proc, log)
        q.save(output / "result.json", result)
        print(json.dumps({"cell": name, "transport_diagnostic": {k: v.get("pass") for k,v in result.items() if isinstance(v,dict)}, "harness_error": result.get("harness_error")}), flush=True)


if __name__ == "__main__":
    for name, digest in MANIFEST["files"].items():
        assert q.sha(HERE / name) == digest
    assert q.sha(ROOT / "qualification-v1/qualify.py") == MANIFEST["original_orchestrator_sha256"]
    # Runtime repair performs the original qualification for two setup failures.
    for name in MANIFEST["runtime_repair_targets"]:
        if (HERE / "results" / name).exists():
            raise RuntimeError("Existing runtime diagnostic; no automatic retry")
        q.coding(CELLS[name], STORAGE, SOURCE, WORK)
    for name in MANIFEST["transport_targets"]:
        transport(name)
    for name in MANIFEST["browser_targets"]:
        browser(name)
