#!/usr/bin/env python3
"""HTTP integration checks for DepotFlow.

The suite starts the real server, talks to its JSON routes, restarts it against
the same SQLite directory, and prints a compact verification summary.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PASSWORD = "DepotDemo!2026"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def http_request(base: str, method: str, path: str, body=None, token=None, key=None):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key is not None:
        headers["Idempotency-Key"] = key
    request = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode()) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read()
        return error.code, json.loads(raw.decode()) if raw else None


def assert_status(result, expected):
    status, body = result
    assert status == expected, (status, body)
    return body


def login(base: str, email: str):
    body = assert_status(
        http_request(base, "POST", "/api/session", {"email": email, "password": PASSWORD}), 200
    )
    return body["token"]


def wait_for_health(base: str, process: subprocess.Popen):
    deadline = time.time() + 8
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited early with {process.returncode}")
        try:
            if http_request(base, "GET", "/api/health")[0] == 200:
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.04)
    raise RuntimeError("server did not become healthy")


def start_server(data_dir: str):
    port = free_port()
    env = os.environ.copy()
    env.update({"PORT": str(port), "DATA_DIR": data_dir, "SEED_DEMO": "1"})
    process = subprocess.Popen(
        [PYTHON, str(ROOT / "server.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    wait_for_health(base, process)
    return process, base


def stop_server(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def inventory_by_sku(base, token):
    return {item["sku"]: item for item in assert_status(http_request(base, "GET", "/api/inventory", token=token), 200)["items"]}


def create_order(base, token, client_ref, lines, key=None):
    return assert_status(
        http_request(
            base,
            "POST",
            "/api/orders",
            {"client_ref": client_ref, "lines": lines},
            token=token,
            key=key or f"create-{client_ref}",
        ),
        201,
    )


def main():
    data_dir = tempfile.mkdtemp(prefix=".depotflow-test-", dir=ROOT)
    process = None
    checks = []
    try:
        process, base = start_server(data_dir)
        checks.append("health and seeded startup")
        assert_status(http_request(base, "GET", "/api/health"), 200)
        assert_status(http_request(base, "GET", "/api/inventory"), 401)
        north_operator = login(base, "operator@north.example")
        north_admin = login(base, "admin@north.example")
        north_viewer = login(base, "viewer@north.example")
        south_operator = login(base, "operator@south.example")
        me = assert_status(http_request(base, "GET", "/api/me", token=north_operator), 200)
        assert me == {"email": "operator@north.example", "role": "operator", "tenant": "north"}
        checks.append("authentication, me, and tenant identity")

        initial = inventory_by_sku(base, north_operator)
        assert initial["BOLT"]["on_hand"] == 100 and initial["BOLT"]["reserved"] == 0
        assert all(isinstance(value, int) and not isinstance(value, bool) for value in initial["BOLT"].values() if isinstance(value, int))

        # Authorization is evaluated before mutation/idempotency replay.
        assert_status(http_request(base, "POST", "/api/orders", {"client_ref": "viewer-nope", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=north_viewer, key="viewer-mutation"), 403)
        assert_status(http_request(base, "POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "nope"}, token=north_operator, key="operator-stock"), 403)
        checks.append("viewer and operator authorization")

        # Payload validation and server-side price snapshot, including zero-price SAMPLE.
        assert_status(http_request(base, "POST", "/api/orders", {"client_ref": "missing-key", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=north_operator), 400)
        zero_payload = {"client_ref": "zero-sample", "lines": [{"sku": "SAMPLE", "quantity": 2, "unit_price_cents": 999999}], "tenant": "south", "role": "admin"}
        zero = assert_status(http_request(base, "POST", "/api/orders", zero_payload, token=north_operator, key="zero-create"), 201)
        assert zero["total_cents"] == 0 and zero["lines"][0]["unit_price_cents"] == 0
        replay = assert_status(http_request(base, "POST", "/api/orders", zero_payload, token=north_operator, key="zero-create"), 201)
        assert replay == zero
        assert_status(http_request(base, "POST", "/api/orders", {"client_ref": "different", "lines": [{"sku": "SAMPLE", "quantity": 2}]}, token=north_operator, key="zero-create"), 409)
        zero_events = [event for event in assert_status(http_request(base, "GET", "/api/audit?limit=100", token=north_operator), 200)["items"] if event["entity_id"] == zero["id"]]
        assert [event["action"] for event in zero_events] == ["order.created"]
        assert_status(http_request(base, "POST", "/api/orders", {"client_ref": "bad-number", "lines": [{"sku": "SAMPLE", "quantity": 1.5}]}, token=north_operator, key="bad-number"), 400)
        assert_status(http_request(base, "POST", "/api/orders", {"client_ref": "unknown-sku", "lines": [{"sku": "NOPE", "quantity": 1}]}, token=north_operator, key="unknown-sku"), 400)
        assert_status(http_request(base, "POST", "/api/orders", {"client_ref": "duplicate-lines", "lines": [{"sku": "SAMPLE", "quantity": 1}, {"sku": "SAMPLE", "quantity": 1}]}, token=north_operator, key="duplicate-lines"), 400)
        checks.append("validation, zero-price order, server pricing, and replay/conflict")

        # A multi-line reservation must fail as a unit.
        atomic = create_order(base, north_operator, "atomic-failure", [{"sku": "BOLT", "quantity": 1}, {"sku": "CABLE", "quantity": 1000}])
        before_atomic = inventory_by_sku(base, north_operator)
        assert_status(http_request(base, "POST", f"/api/orders/{atomic['id']}/reserve", {"expected_version": 1}, token=north_operator, key="atomic-reserve"), 409)
        after_atomic = inventory_by_sku(base, north_operator)
        assert before_atomic == after_atomic
        atomic_detail = assert_status(http_request(base, "GET", f"/api/orders/{atomic['id']}", token=north_operator), 200)
        assert atomic_detail["status"] == "draft" and atomic_detail["version"] == 1
        checks.append("atomic insufficient-stock reservation")

        # Concurrent identical create requests collapse to one effect and one audit event.
        concurrent_payload = {"client_ref": "concurrent-create", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        def concurrent_create(_):
            return http_request(base, "POST", "/api/orders", concurrent_payload, token=north_operator, key="same-concurrent-create")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_results = list(pool.map(concurrent_create, range(2)))
        assert [result[0] for result in concurrent_results] == [201, 201]
        assert concurrent_results[0][1] == concurrent_results[1][1]
        concurrent_events = [event for event in assert_status(http_request(base, "GET", "/api/audit?limit=100", token=north_operator), 200)["items"] if event["entity_id"] == concurrent_results[0][1]["id"]]
        assert [event["action"] for event in concurrent_events] == ["order.created"]
        checks.append("concurrent identical idempotent create")

        # Concurrent reservations of 60 CABLE units: exactly one can reserve.
        race_a = create_order(base, north_operator, "race-a", [{"sku": "CABLE", "quantity": 60}])
        race_b = create_order(base, north_operator, "race-b", [{"sku": "CABLE", "quantity": 60}])
        def concurrent_reserve(order, request_key):
            return http_request(base, "POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, token=north_operator, key=request_key)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            race_results = list(pool.map(lambda args: concurrent_reserve(*args), [(race_a, "race-a-reserve"), (race_b, "race-b-reserve")]))
        assert sorted(result[0] for result in race_results) == [200, 409]
        race_inventory = inventory_by_sku(base, north_operator)
        assert race_inventory["CABLE"]["reserved"] == 60
        checks.append("serialized concurrent reservation without oversell")

        # Normal lifecycle, stale version, shipping invariants, partial and full return.
        workflow = create_order(base, north_operator, "workflow-1", [{"sku": "BOLT", "quantity": 2}, {"sku": "SAMPLE", "quantity": 1}])
        reserved = assert_status(http_request(base, "POST", f"/api/orders/{workflow['id']}/reserve", {"expected_version": 1}, token=north_operator, key="workflow-reserve"), 200)
        assert reserved["status"] == "reserved" and reserved["version"] == 2
        stale = http_request(base, "POST", f"/api/orders/{workflow['id']}/ship", {"expected_version": 1}, token=north_operator, key="workflow-stale-ship")
        assert_status(stale, 409)
        shipped = assert_status(http_request(base, "POST", f"/api/orders/{workflow['id']}/ship", {"expected_version": 2}, token=north_operator, key="workflow-ship"), 200)
        assert shipped["status"] == "shipped" and shipped["version"] == 3
        after_ship = inventory_by_sku(base, north_operator)
        assert after_ship["BOLT"]["on_hand"] == 98 and after_ship["BOLT"]["reserved"] == 0 and after_ship["BOLT"]["available"] == 98
        partial = assert_status(http_request(base, "POST", f"/api/orders/{workflow['id']}/returns", {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}, token=north_operator, key="workflow-return-partial"), 200)
        assert partial["status"] == "shipped" and partial["lines"][0]["returned_quantity"] == 1
        full = assert_status(http_request(base, "POST", f"/api/orders/{workflow['id']}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "SAMPLE", "quantity": 1}]}, token=north_operator, key="workflow-return-full"), 200)
        assert full["status"] == "returned" and full["version"] == 5
        assert_status(http_request(base, "POST", f"/api/orders/{workflow['id']}/returns", {"expected_version": 5, "lines": [{"sku": "BOLT", "quantity": 1}]}, token=north_operator, key="workflow-return-again"), 409)
        checks.append("stale version, ship accounting, partial/full returns")

        # Cancel a reserved order and ensure reservation is released.
        cancellable = create_order(base, north_operator, "cancel-me", [{"sku": "BOLT", "quantity": 3}])
        assert_status(http_request(base, "POST", f"/api/orders/{cancellable['id']}/reserve", {"expected_version": 1}, token=north_operator, key="cancel-reserve"), 200)
        cancelled = assert_status(http_request(base, "POST", f"/api/orders/{cancellable['id']}/cancel", {"expected_version": 2}, token=north_operator, key="cancel-order"), 200)
        assert cancelled["status"] == "cancelled"
        assert inventory_by_sku(base, north_operator)["BOLT"]["reserved"] == 0
        checks.append("reserved cancellation release")

        # Admin-only stock adjustment and replay, then durable restart.
        stock_before = inventory_by_sku(base, north_admin)["BOLT"]
        adjust_payload = {"sku": "BOLT", "delta": 4, "expected_version": stock_before["version"], "reason": "cycle count"}
        adjusted = assert_status(http_request(base, "POST", "/api/stock/adjustments", adjust_payload, token=north_admin, key="stock-replay"), 200)
        assert adjusted["on_hand"] == stock_before["on_hand"] + 4
        assert assert_status(http_request(base, "POST", "/api/stock/adjustments", adjust_payload, token=north_admin, key="stock-replay"), 200) == adjusted
        assert_status(http_request(base, "POST", "/api/stock/adjustments", {**adjust_payload, "delta": 5}, token=north_admin, key="stock-replay"), 409)
        checks.append("admin stock adjustment and durable idempotent replay preparation")

        # Tenant isolation includes object lookup and audit streams.
        assert_status(http_request(base, "GET", f"/api/orders/{workflow['id']}", token=south_operator), 404)
        assert_status(http_request(base, "POST", f"/api/orders/{workflow['id']}/cancel", {"expected_version": 5}, token=south_operator, key="south-cross-tenant"), 404)
        south_items = inventory_by_sku(base, south_operator)
        assert south_items["BOLT"]["on_hand"] == 100 and south_items["BOLT"]["reserved"] == 0
        south_audit = assert_status(http_request(base, "GET", "/api/audit", token=south_operator), 200)
        assert south_audit["items"] == []
        checks.append("tenant object and audit isolation")

        # Pagination has stable filters and no duplicate IDs.
        first_page = assert_status(http_request(base, "GET", "/api/orders?limit=2", token=north_operator), 200)
        all_ids = [order["id"] for order in first_page["items"]]
        cursor = first_page["next_cursor"]
        while cursor:
            page = assert_status(http_request(base, "GET", "/api/orders?limit=2&cursor=" + urllib.parse.quote(cursor), token=north_operator), 200)
            all_ids.extend(order["id"] for order in page["items"])
            cursor = page["next_cursor"]
        assert len(all_ids) == len(set(all_ids)) and len(all_ids) >= 7
        assert_status(http_request(base, "GET", "/api/orders?status=not-a-status", token=north_operator), 400)
        assert_status(http_request(base, "GET", "/api/orders?limit=0", token=north_operator), 400)
        assert_status(http_request(base, "GET", "/api/orders?cursor=not-a-cursor", token=north_operator), 400)
        audit_page = assert_status(http_request(base, "GET", "/api/audit?limit=2", token=north_operator), 200)
        assert audit_page["items"] and all(isinstance(item["id"], int) for item in audit_page["items"])
        checks.append("stable order/audit pagination and filter validation")

        # Restart against the identical directory: changes, sessions, and idempotency survive.
        stop_server(process)
        process = None
        process, base = start_server(data_dir)
        assert_status(http_request(base, "POST", "/api/stock/adjustments", adjust_payload, token=north_admin, key="stock-replay"), 200)
        persisted_inventory = inventory_by_sku(base, north_operator)
        assert persisted_inventory["BOLT"]["on_hand"] == adjusted["on_hand"]
        persisted_workflow = assert_status(http_request(base, "GET", f"/api/orders/{workflow['id']}", token=north_operator), 200)
        assert persisted_workflow["status"] == "returned" and persisted_workflow["version"] == 5
        persisted_dashboard = assert_status(http_request(base, "GET", "/api/dashboard", token=north_operator), 200)
        assert persisted_dashboard["orders_by_status"]["returned"] >= 1
        checks.append("restart durability for state, session, and idempotency")

        print(f"PASS: {len(checks)} integration areas")
        for check in checks:
            print(f"  - {check}")
    finally:
        if process is not None:
            stop_server(process)
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
