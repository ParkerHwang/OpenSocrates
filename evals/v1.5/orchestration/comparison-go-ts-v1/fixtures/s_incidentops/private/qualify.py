"""External black-box checks for a disposable Go/TypeScript IncidentOps copy."""
from __future__ import annotations

import json
import os
import concurrent.futures
import hashlib
import http.client
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def record(checks: list[dict], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"id": name, "passed": bool(passed), "detail": detail[:200]})


def port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(base: str, path: str, *, tenant: str = "north", role: str = "operator", body=None) -> tuple[int, dict]:
    headers = {"X-Tenant": tenant, "X-Role": role}
    payload = None
    if body is not None:
        payload = json.dumps(body, separators=(",", ":")).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=payload, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except json.JSONDecodeError:
            return exc.code, {}


def launch(candidate: Path, db: Path, env: dict) -> tuple[subprocess.Popen, str]:
    p = port()
    base = f"http://127.0.0.1:{p}"
    launched = subprocess.Popen(locked([str(candidate / ".eval-server")], env), cwd=candidate, env={**env, "INCIDENTOPS_DB": str(db), "INCIDENTOPS_ADDR": f"127.0.0.1:{p}"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if launched.poll() is not None:
            raise RuntimeError("server exited during startup")
        try:
            if request(base, "/api/health")[0] == 200:
                return launched, base
        except (OSError, ValueError):
            time.sleep(0.05)
    launched.terminate()
    raise RuntimeError("server readiness timeout")


def stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def launch_browser(candidate: Path, deps: Path, env: dict) -> tuple[subprocess.Popen, str]:
    executable = deps / "browsers/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"
    if not executable.is_file():
        raise RuntimeError("pinned Chromium executable missing")
    cdp_port = port()
    profile = candidate / ".eval-browser-profile"
    profile.mkdir(exist_ok=True)
    argv = [str(executable), "--no-sandbox", "--disable-gpu", "--disable-background-networking", f"--remote-debugging-port={cdp_port}", f"--user-data-dir={profile}", "about:blank"]
    proc = subprocess.Popen(locked(argv, env), cwd=candidate, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    endpoint = f"http://127.0.0.1:{cdp_port}"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("sandboxed browser exited during startup")
        try:
            with urllib.request.urlopen(endpoint + "/json/version", timeout=1) as response:
                if response.status == 200:
                    return proc, endpoint
        except OSError:
            time.sleep(0.1)
    stop(proc)
    raise RuntimeError("sandboxed browser readiness timeout")


def locked(argv: list[str], env: dict) -> list[str]:
    policy = env.get("OPENSOCRATES_CANDIDATE_POLICY")
    if not policy or not Path(policy).is_file():
        raise RuntimeError("candidate child policy missing")
    return ["/usr/bin/sandbox-exec", "-f", policy, *argv]


def go_env(candidate: Path, deps: Path) -> dict:
    for directory in (candidate / ".eval-home", candidate / ".eval-tmp", candidate / ".eval-go-build", candidate / ".eval-go-path", candidate / ".eval-clang-cache"):
        directory.mkdir(exist_ok=True)
    env = {
        "PATH": "/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(candidate / ".eval-home"),
        "TMPDIR": str(candidate / ".eval-tmp"),
        "GOTMPDIR": str(candidate / ".eval-tmp"),
        "GOMODCACHE": str(deps / "go-modcache"),
        "GOCACHE": os.environ.get("GOCACHE", str(candidate / ".eval-go-build")),
        "GOPATH": str(candidate / ".eval-go-path"),
        "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOSUMDB": "off",
        "CGO_ENABLED": "1", "CC": "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang",
        "DEVELOPER_DIR": "/Applications/Xcode.app/Contents/Developer",
        "SDKROOT": "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk",
        "CLANG_MODULE_CACHE_PATH": str(candidate / ".eval-clang-cache"),
        "OPENSOCRATES_CANDIDATE_POLICY": os.environ.get("OPENSOCRATES_CANDIDATE_POLICY", ""),
    }
    return env


def event(event_id: str, incident_id: str, seq: int, kind: str, when: str, *, severity: str = "", note: str = "") -> dict:
    return {"event_id": event_id, "incident_id": incident_id, "sequence": seq, "kind": kind, "occurred_at": when, "severity": severity, "note": note}


def check_api(candidate: Path, deps: Path, env: dict, checks: list[dict]) -> bool:
    db = candidate / ".eval-functional.db"
    if db.exists():
        raise RuntimeError("functional database already exists; use a fresh disposable copy")
    process, base = launch(candidate, db, env)
    try:
        health = request(base, "/api/health")[1]
        record(checks, "s_active_durability", health.get("status") == "ok" and str(health.get("journal_mode", "")).lower() == "wal" and health.get("synchronous") == 2, "active connection reports WAL/FULL")
        unauthorized, _ = request(base, "/api/incidents", tenant="", role="viewer")
        viewer_write, _ = request(base, "/api/events", role="viewer", body=event("no", "forbidden", 1, "OPEN", "2026-06-01T10:00:00Z", severity="P1"))
        forbidden_items = request(base, "/api/incidents")[1].get("items", [])
        record(checks, "s_identity_viewer", 400 <= unauthorized < 500 and 400 <= viewer_write < 500 and not forbidden_items, "rejects identity and viewer write without persistence")

        older = {"effective_at": "2026-01-01T00:00:00Z", "severity": "P1", "delay_minutes": 120}
        later = {"effective_at": "2026-05-01T00:00:00Z", "severity": "P1", "delay_minutes": 30}
        handover_a = {"starts_at": "2026-06-01T09:00:00Z", "ends_at": "2026-06-01T12:00:00Z", "person": "A"}
        handover_b = {"starts_at": "2026-06-01T10:00:00Z", "ends_at": "2026-06-01T11:00:00Z", "person": "B"}
        config_statuses = [request(base, "/api/policies", body=x)[0] for x in (older, later)] + [request(base, "/api/oncall", body=x)[0] for x in (handover_a, handover_b)]
        opening = event("event-a", "incident-a", 1, "OPEN", "2026-06-01T10:00:00Z", severity="P1", note="Network edge")
        first_status, first_body = request(base, "/api/events", body=opening)
        outbox = request(base, "/api/outbox")[1].get("items", [])
        record(checks, "s_effective_policy_handover", config_statuses == [201] * 4 and first_status == 201 and len(outbox) == 1 and outbox[0].get("due_at") == "2026-06-01T10:30:00Z" and outbox[0].get("assignee") == "B", "later lower delay and latest overlapping handover")
        same_status, same = request(base, "/api/events", body=opening)
        changed = dict(opening, note="different")
        conflict_status, _ = request(base, "/api/events", body=changed)
        record(checks, "s_replay_conflict", same_status == 200 and same.get("duplicate") is True and conflict_status == 409 and len(request(base, "/api/outbox")[1].get("items", [])) == 1, "same-key replay versus different-payload conflict")
        changed_policy = {"effective_at": "2026-05-15T00:00:00Z", "severity": "P1", "delay_minutes": 15}
        request(base, "/api/policies", body=changed_policy)
        revised = request(base, "/api/outbox")[1].get("items", [])
        record(checks, "s_config_reconcile", len(revised) == 1 and revised[0].get("due_at") == "2026-06-01T10:15:00Z" and revised[0].get("state") == "pending", "pending effect updated without duplicate")

        resolved = event("event-resolve", "incident-a", 4, "RESOLVE", "2026-06-01T11:00:00Z", note="done")
        resolve_status, _ = request(base, "/api/events", body=resolved)
        late_ack = event("event-ack", "incident-a", 2, "ACK", "2026-06-01T10:30:00Z", note="taken")
        late_status, late_body = request(base, "/api/events", body=late_ack)
        before_invalid_state = request(base, "/api/incidents")[1]
        before_invalid_outbox = request(base, "/api/outbox")[1]
        invalid_late = event("event-invalid", "incident-a", 3, "ACK", "2026-06-01T10:40:00Z")
        invalid_status, _ = request(base, "/api/events", body=invalid_late)
        state = request(base, "/api/incidents")[1].get("items", [])
        effect = request(base, "/api/outbox")[1].get("items", [])
        record(checks, "s_late_fold_atomicity", resolve_status == 201 and late_status == 201 and invalid_status == 422 and late_body.get("incident", {}).get("status") == "resolved" and any(x.get("incident_id") == "incident-a" and x.get("sequence") == 4 and x.get("status") == "resolved" for x in state) and len(effect) == 1 and effect[0].get("state") == "cancelled", "late valid fold, invalid late rollback, cancellation")
        record(checks, "s_invalid_insert_rollback", before_invalid_state == request(base, "/api/incidents")[1] and before_invalid_outbox == request(base, "/api/outbox")[1], "observable projections unchanged after 422")
        reopened = event("event-reopen", "incident-a", 5, "REOPEN", "2026-06-02T10:00:00Z", severity="P2", note="again")
        reopen_status, _ = request(base, "/api/events", body=reopened)
        effect = request(base, "/api/outbox")[1].get("items", [])
        record(checks, "s_reopen_generation", reopen_status == 201 and len(effect) == 2 and effect[0].get("state") == "cancelled" and effect[1].get("generation") == 2 and effect[1].get("state") == "pending", "obsolete effect remains cancelled; new generation pending")
        cross_status, _ = request(base, "/api/events", tenant="south", body=opening)
        north = request(base, "/api/incidents")[1].get("items", [])
        south = request(base, "/api/incidents", tenant="south")[1].get("items", [])
        record(checks, "s_tenant_isolation", cross_status == 201 and len(north) == 1 and len(south) == 1 and north[0].get("status") == "open" and south[0].get("status") == "open", "same external event ID isolated by tenant")
        race = event("race-event", "race-incident", 1, "OPEN", "2026-06-03T10:00:00Z", severity="P2")
        def race_call(_: int):
            try:
                return request(base, "/api/events", tenant="race", body=race)[0]
            except Exception as exc:
                return f"transport:{type(exc).__name__}"
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            race_results = list(pool.map(race_call, range(32)))
        race_effect = request(base, "/api/outbox", tenant="race")[1].get("items", [])
        checks.append({"id": "s_concurrent_effect_uniqueness", "passed": race_results.count(201) == 1 and race_results.count(200) == 31 and len(race_effect) == 1 and race_effect[0].get("state") == "pending", "detail": "32 simultaneous same-key requests", "response_statuses": race_results, "observable_effects": len(race_effect)})
        filters = urllib.parse.urlencode({"status": "open", "severity": "P2", "q": "AGAIN"})
        selected = request(base, "/api/incidents?" + filters)[1].get("items", [])
        summary = request(base, "/api/summary?" + filters)[1]
        zero = request(base, "/api/summary?status=resolved&severity=P2")[1]
        record(checks, "s_filters_derived_summary", len(selected) == 1 and selected[0].get("incident_id") == "incident-a" and summary == {"total": 1, "open": 1, "acknowledged": 0, "resolved": 0} and zero == {"total": 0, "open": 0, "acknowledged": 0, "resolved": 0}, "same filtered result set drives zero-inclusive counts")
        browser_a = event("browser-a", "browser-alpha", 1, "OPEN", "2026-06-01T09:00:00Z", severity="P1", note="browser one")
        browser_b = event("browser-b", "browser-beta", 1, "OPEN", "2026-06-01T09:10:00Z", severity="P2", note="browser two")
        request(base, "/api/events", body=browser_a)
        request(base, "/api/events", body=browser_b)
        transport_incomplete = False
        try:
            with urllib.request.urlopen(base + "/", timeout=8) as page_response:
                page_response.read()
        except http.client.IncompleteRead as exc:
            transport_incomplete = True
            checks.append({"id": "s_browser_transport", "passed": False, "status": "unassessable", "detail": f"static response advertised more bytes than delivered; observed={len(exc.partial)}; known FileServer sandbox signature"})
        if transport_incomplete:
            checks.append({"id": "s_browser_network_ui", "passed": False, "status": "unassessable", "detail": "browser blocked by sandbox static transport truncation"})
        else:
            record(checks, "s_browser_transport", True, "complete main HTML response")
            chrome, endpoint = launch_browser(candidate, deps, env)
            try:
                browser_env = {**env, "OPENSOCRATES_EVAL_DEPS": str(deps), "EVAL_BASE_URL": base, "EVAL_CANDIDATE": str(candidate), "EVAL_CDP_URL": endpoint}
                browser = subprocess.run(["/usr/local/bin/node", str(Path(__file__).resolve().with_name("browser_probe.cjs"))], cwd=candidate, env=browser_env, capture_output=True, timeout=45)
            finally:
                stop(chrome)
            try:
                browser_receipt = json.loads(browser.stdout)
            except json.JSONDecodeError:
                browser_receipt = {}
            failures = browser_receipt.get("network_failures", [])
            truncated_asset = any(any(signature in str(item.get("error", "")) for signature in ("ERR_CONTENT_LENGTH_MISMATCH", "ERR_INCOMPLETE_CHUNKED_ENCODING")) for item in failures)
            if truncated_asset:
                checks.append({"id": "s_browser_network_ui", "passed": False, "status": "unassessable", "detail": "browser asset transport truncated under sandbox"})
            else:
                record(checks, "s_browser_network_ui", browser.returncode == 0 and browser_receipt.get("passed") is True, f"network_posts={browser_receipt.get('network_posts')}; filters={browser_receipt.get('filtered_responses')}; mobile={browser_receipt.get('mobile_width')}; error={browser_receipt.get('error')}")
        before_restart = request(base, "/api/incidents")[1]
    finally:
        stop(process)
    with sqlite3.connect(db) as connection:
        wal = connection.execute("PRAGMA journal_mode").fetchone()[0]
    header = db.read_bytes()[:16]
    record(checks, "s_sqlite_file", header == b"SQLite format 3\x00" and wal.lower() == "wal", f"SQLite header and WAL journal={wal}")
    process, base = launch(candidate, db, env)
    try:
        after_restart = request(base, "/api/incidents")[1]
        restart_outbox = request(base, "/api/outbox")[1].get("items", [])
        record(checks, "s_restart_continuity", before_restart == after_restart and len(restart_outbox) >= 2, "same SQLite path after process restart")
    finally:
        stop(process)
    return all(item["passed"] for item in checks)


def qualify(candidate: Path, deps: Path, *, performance: bool = True) -> tuple[list[dict], dict | None]:
    checks: list[dict] = []
    locked_names = ("go.mod", "go.sum", "package.json", "package-lock.json", "tsconfig.json", "main.go", "api.go", "store.go", "domain.go", "main_test.go", "web/app.ts", "web/api.ts", "web/view.ts", "web/index.html", "web/style.css", "RUNBOOK.md", "design.json", "design.md")
    def hashes() -> dict[str, str]:
        return {name: hashlib.sha256((candidate / name).read_bytes()).hexdigest() for name in locked_names if (candidate / name).is_file()}
    before = hashes()
    env = go_env(candidate, deps)
    build = subprocess.run(locked(["/usr/local/go/bin/go", "build", "-o", str(candidate / ".eval-server"), "."], env), cwd=candidate, env=env, capture_output=True, timeout=180)
    record(checks, "s_go_build", build.returncode == 0, f"exit={build.returncode}")
    if build.returncode != 0:
        record(checks, "s_locked_source_integrity", hashes() == before, "no candidate source rewrite")
        return checks, None
    tests = subprocess.run(locked(["/usr/local/go/bin/go", "test", "./..."], env), cwd=candidate, env=env, capture_output=True, timeout=180)
    record(checks, "s_go_tests", tests.returncode == 0, f"exit={tests.returncode}")
    tsc = deps / "npm/node_modules/.bin/tsc"
    frontend = subprocess.run(locked([str(tsc), "-p", "tsconfig.json"], env), cwd=candidate, env=env, capture_output=True, timeout=90)
    record(checks, "s_typescript_build", frontend.returncode == 0, f"exit={frontend.returncode}")
    if frontend.returncode != 0:
        record(checks, "s_locked_source_integrity", hashes() == before, "no candidate source rewrite")
        return checks, None
    try:
        eligible = check_api(candidate, deps, env, checks)
    except Exception as exc:
        record(checks, "s_api_probe", False, type(exc).__name__)
        eligible = False
    if eligible and performance:
        sys.path.insert(0, str(Path(__file__).parent))
        from performance import measure
        perf = measure(candidate, env)
        record(checks, "s_performance_completion", perf["all_requests_accounted"] and perf["all_post_states_valid"], f"measured={perf['measured_requests']}; warmups={perf['warmup_requests']}; seeds={perf['seed_requests']}")
        record(checks, "s_locked_source_integrity", hashes() == before, "no candidate source rewrite")
        return checks, perf
    record(checks, "s_locked_source_integrity", hashes() == before, "no candidate source rewrite")
    return checks, None
