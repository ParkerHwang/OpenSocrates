#!/usr/bin/env python3
"""Black-box HTTP checks for DepotFlow's real server and persistent store."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "DepotDemo!2026"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class Harness:
    def __init__(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="depotflow-test-")
        self.data_dir = self.tempdir.name
        self.port = free_port()
        self.process: subprocess.Popen[str] | None = None
        self.start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        env = os.environ.copy()
        env.update({"PORT": str(self.port), "DATA_DIR": self.data_dir, "SEED_DEMO": "1"})
        self.process = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                status, body = self.request("GET", "/api/health")
                if status == 200 and body.get("status") == "ok":
                    return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.05)
        output = ""
        if self.process and self.process.poll() is not None:
            output = (self.process.stdout.read() if self.process.stdout else "")
            output += (self.process.stderr.read() if self.process.stderr else "")
        raise RuntimeError(f"server did not start: {output}")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.process:
            if self.process.stdout:
                self.process.stdout.close()
            if self.process.stderr:
                self.process.stderr.close()
        self.process = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def close(self) -> None:
        self.stop()
        self.tempdir.cleanup()

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        token: str | None = None,
        key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if key is not None:
            headers["Idempotency-Key"] = key
        if extra_headers:
            headers.update(extra_headers)
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            raw = error.read().decode()
            return error.code, json.loads(raw) if raw else {}


class DepotFlowIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = Harness()

    def tearDown(self) -> None:
        self.server.close()

    def login(self, tenant: str = "north", role: str = "admin") -> tuple[str, dict]:
        status, body = self.server.request(
            "POST",
            "/api/session",
            {"email": f"{role}@{tenant}.example", "password": PASSWORD},
        )
        self.assertEqual(status, 200, body)
        return body["token"], body["user"]

    def test_auth_roles_and_tenant_isolation(self) -> None:
        status, body = self.server.request("GET", "/api/health")
        self.assertEqual((status, body), (200, {"status": "ok"}))
        status, body = self.server.request("GET", "/api/inventory")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")
        north_admin, user = self.login()
        self.assertEqual(user, {"email": "admin@north.example", "role": "admin", "tenant": "north"})
        north_viewer, _ = self.login(role="viewer")
        north_operator, _ = self.login(role="operator")
        south_admin, _ = self.login(tenant="south")
        status, me = self.server.request("GET", "/api/me", token=north_admin)
        self.assertEqual(status, 200)
        self.assertEqual(me["tenant"], "north")
        status, body = self.server.request(
            "POST",
            "/api/orders",
            {"client_ref": "viewer-write", "lines": [{"sku": "SAMPLE", "quantity": 1}]},
            north_viewer,
            "viewer-write-key",
        )
        self.assertEqual(status, 403)
        status, body = self.server.request(
            "POST",
            "/api/stock/adjustments",
            {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "no"},
            north_operator,
            "operator-stock-key",
        )
        self.assertEqual(status, 403)
        status, created = self.server.request(
            "POST",
            "/api/orders",
            {"client_ref": "north-private", "lines": [{"sku": "SAMPLE", "quantity": 1}]},
            north_operator,
            "north-order-key",
        )
        self.assertEqual(status, 201)
        order_id = created["id"]
        status, body = self.server.request("GET", f"/api/orders/{order_id}", token=south_admin)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")
        status, inventory = self.server.request(
            "GET", "/api/inventory", token=north_admin,
            extra_headers={"X-Tenant": "south", "X-Role": "viewer"}
        )
        self.assertEqual(status, 200)
        self.assertEqual({row["sku"] for row in inventory["items"]}, {"BOLT", "CABLE", "SAMPLE"})
        self.assertEqual(next(row for row in inventory["items"] if row["sku"] == "SAMPLE")["on_hand"], 20)

    def test_validation_pricing_zero_price_pagination_and_audit(self) -> None:
        admin, _ = self.login()
        invalid_cases = [
            ({"client_ref": "duplicate", "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 2}]}, "duplicate_sku"),
            ({"client_ref": "unknown", "lines": [{"sku": "NOPE", "quantity": 1}]}, "unknown_sku"),
            ({"client_ref": "fraction", "lines": [{"sku": "BOLT", "quantity": 1.5}]}, "invalid_payload"),
            ({"client_ref": "boolean", "lines": [{"sku": "BOLT", "quantity": True}]}, "invalid_payload"),
        ]
        for index, (payload, code) in enumerate(invalid_cases):
            status, body = self.server.request("POST", "/api/orders", payload, admin, f"invalid-{index}")
            self.assertEqual(status, 400, body)
            self.assertEqual(body["error"]["code"], code)
        status, zero_order = self.server.request(
            "POST",
            "/api/orders",
            {"client_ref": "sample-zero", "lines": [{"sku": "SAMPLE", "quantity": 2, "unit_price_cents": 999999}]},
            admin,
            "zero-order-key",
        )
        self.assertEqual(status, 201)
        self.assertEqual(zero_order["total_cents"], 0)
        self.assertEqual(zero_order["lines"][0]["unit_price_cents"], 0)
        status, conflict = self.server.request(
            "POST",
            "/api/orders",
            {"client_ref": "sample-zero", "lines": [{"sku": "SAMPLE", "quantity": 3}]},
            admin,
            "different-key",
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict["error"]["code"], "client_ref_conflict")
        for i in range(3):
            status, _ = self.server.request(
                "POST",
                "/api/orders",
                {"client_ref": f"page-ref-{i}", "lines": [{"sku": "SAMPLE", "quantity": 1}]},
                admin,
                f"page-key-{i}",
            )
            self.assertEqual(status, 201)
        status, first = self.server.request("GET", "/api/orders?limit=2", token=admin)
        self.assertEqual(status, 200)
        self.assertEqual(len(first["items"]), 2)
        self.assertIsNotNone(first["next_cursor"])
        status, second = self.server.request(
            "GET", f"/api/orders?limit=2&cursor={first['next_cursor']}", token=admin
        )
        self.assertEqual(status, 200)
        self.assertTrue({row["id"] for row in first["items"]}.isdisjoint({row["id"] for row in second["items"]}))
        status, body = self.server.request("GET", "/api/orders?limit=0", token=admin)
        self.assertEqual(status, 400)
        status, body = self.server.request("GET", "/api/orders?status=bogus", token=admin)
        self.assertEqual(status, 400)
        status, body = self.server.request("GET", "/api/orders?cursor=not-a-cursor", token=admin)
        self.assertEqual(status, 400)
        status, audit = self.server.request("GET", "/api/audit?limit=2", token=admin)
        self.assertEqual(status, 200)
        self.assertEqual(len(audit["items"]), 2)
        self.assertEqual([event["action"] for event in audit["items"]], ["order_created", "order_created"])

    def test_atomic_reservation_concurrency_transitions_and_returns(self) -> None:
        operator, _ = self.login(role="operator")
        status, before = self.server.request("GET", "/api/inventory", token=operator)
        self.assertEqual(status, 200)
        before_by_sku = {item["sku"]: item for item in before["items"]}
        status, failed = self.server.request(
            "POST",
            "/api/orders",
            {"client_ref": "atomic-failure", "lines": [{"sku": "BOLT", "quantity": 1000}, {"sku": "CABLE", "quantity": 1}]},
            operator,
            "atomic-create",
        )
        self.assertEqual(status, 201)
        status, conflict = self.server.request(
            "POST", f"/api/orders/{failed['id']}/reserve", {"expected_version": 1}, operator, "atomic-reserve"
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict["error"]["code"], "insufficient_stock")
        status, unchanged = self.server.request("GET", "/api/inventory", token=operator)
        self.assertEqual(status, 200)
        self.assertEqual(unchanged["items"], before["items"])
        status, failed_order = self.server.request("GET", f"/api/orders/{failed['id']}", token=operator)
        self.assertEqual(status, 200)
        self.assertEqual((failed_order["status"], failed_order["version"]), ("draft", 1))
        status, audit = self.server.request("GET", "/api/audit?limit=100", token=operator)
        self.assertEqual(status, 200)
        self.assertEqual(sum(event["action"] == "order_reserved" for event in audit["items"]), 0)

        reserve_ids = []
        for suffix in ("a", "b"):
            status, order = self.server.request(
                "POST",
                "/api/orders",
                {"client_ref": f"race-{suffix}", "lines": [{"sku": "SAMPLE", "quantity": 15}]},
                operator,
                f"race-create-{suffix}",
            )
            self.assertEqual(status, 201)
            reserve_ids.append(order["id"])

        def reserve(order_id: int) -> tuple[int, dict]:
            return self.server.request(
                "POST", f"/api/orders/{order_id}/reserve", {"expected_version": 1}, operator, f"race-reserve-{order_id}"
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, reserve_ids))
        self.assertEqual(sorted(result[0] for result in results), [200, 409])
        status, inventory = self.server.request("GET", "/api/inventory", token=operator)
        sample = next(item for item in inventory["items"] if item["sku"] == "SAMPLE")
        self.assertGreaterEqual(sample["available"], 0)
        self.assertEqual(sample["reserved"], 15)
        admin, _ = self.login()
        status, body = self.server.request(
            "POST",
            "/api/stock/adjustments",
            {"sku": "SAMPLE", "delta": -6, "expected_version": sample["version"], "reason": "too much"},
            admin,
            "below-reserved",
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "insufficient_stock")
        status, after_failed_adjustment = self.server.request("GET", "/api/inventory", token=operator)
        self.assertEqual(after_failed_adjustment["items"], inventory["items"])

        status, cancel_order = self.server.request(
            "POST",
            "/api/orders",
            {"client_ref": "cancel-me", "lines": [{"sku": "CABLE", "quantity": 1}]},
            operator,
            "cancel-create",
        )
        self.assertEqual(status, 201)
        status, _ = self.server.request("POST", f"/api/orders/{cancel_order['id']}/reserve", {"expected_version": 1}, operator, "cancel-reserve")
        self.assertEqual(status, 200)
        status, cancelled = self.server.request("POST", f"/api/orders/{cancel_order['id']}/cancel", {"expected_version": 2}, operator, "cancel-transition")
        self.assertEqual(status, 200)
        self.assertEqual(cancelled["status"], "cancelled")

        status, return_order = self.server.request(
            "POST",
            "/api/orders",
            {"client_ref": "returnable", "lines": [{"sku": "BOLT", "quantity": 2}]},
            operator,
            "return-create",
        )
        self.assertEqual(status, 201)
        order_id = return_order["id"]
        status, return_order = self.server.request("POST", f"/api/orders/{order_id}/reserve", {"expected_version": 1}, operator, "return-reserve")
        self.assertEqual(status, 200)
        status, return_order = self.server.request("POST", f"/api/orders/{order_id}/ship", {"expected_version": 2}, operator, "return-ship")
        self.assertEqual(status, 200)
        self.assertEqual(return_order["status"], "shipped")
        status, partial = self.server.request(
            "POST", f"/api/orders/{order_id}/returns", {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}, operator, "return-partial"
        )
        self.assertEqual(status, 200)
        self.assertEqual((partial["status"], partial["version"], partial["lines"][0]["returned_quantity"]), ("shipped", 4, 1))
        status, full = self.server.request(
            "POST", f"/api/orders/{order_id}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 1}]}, operator, "return-full"
        )
        self.assertEqual(status, 200)
        self.assertEqual((full["status"], full["version"]), ("returned", 5))
        status, body = self.server.request(
            "POST", f"/api/orders/{order_id}/returns", {"expected_version": 5, "lines": [{"sku": "BOLT", "quantity": 1}]}, operator, "return-again"
        )
        self.assertEqual(status, 409)
        status, body = self.server.request(
            "POST", f"/api/orders/{order_id}/ship", {"expected_version": 3}, operator, "stale-ship"
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "stale_version")

    def test_idempotency_replay_and_restart_durability(self) -> None:
        admin, _ = self.login()
        adjust_payload = {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "cycle count"}
        status, adjusted = self.server.request("POST", "/api/stock/adjustments", adjust_payload, admin, "stock-retry")
        self.assertEqual(status, 200)
        status, replay = self.server.request("POST", "/api/stock/adjustments", adjust_payload, admin, "stock-retry")
        self.assertEqual((status, replay), (200, adjusted))
        status, inventory = self.server.request("GET", "/api/inventory", token=admin)
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        self.assertEqual((bolt["on_hand"], bolt["version"]), (101, 2))
        status, conflict = self.server.request(
            "POST", "/api/stock/adjustments", {**adjust_payload, "delta": 2}, admin, "stock-retry"
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict["error"]["code"], "idempotency_conflict")
        same_payload = {"client_ref": "concurrent-create", "lines": [{"sku": "SAMPLE", "quantity": 1}]}

        def create_same_order(_: int) -> tuple[int, dict]:
            return self.server.request("POST", "/api/orders", same_payload, admin, "concurrent-create-key")

        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_results = list(pool.map(create_same_order, (1, 2)))
        self.assertEqual([result[0] for result in concurrent_results], [201, 201])
        self.assertEqual(concurrent_results[0][1], concurrent_results[1][1])
        status, order = self.server.request(
            "POST", "/api/orders", {"client_ref": "durable-order", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, admin, "durable-create"
        )
        self.assertEqual(status, 201)
        self.server.restart()
        status, me = self.server.request("GET", "/api/me", token=admin)
        self.assertEqual(status, 200)
        self.assertEqual(me["tenant"], "north")
        status, replay_order = self.server.request(
            "POST", "/api/orders", {"client_ref": "durable-order", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, admin, "durable-create"
        )
        self.assertEqual((status, replay_order), (201, order))
        status, persisted = self.server.request("GET", f"/api/orders/{order['id']}", token=admin)
        self.assertEqual((status, persisted), (200, order))
        status, inventory = self.server.request("GET", "/api/inventory", token=admin)
        self.assertEqual(next(item for item in inventory["items"] if item["sku"] == "BOLT")["on_hand"], 101)
        status, audit = self.server.request("GET", "/api/audit?limit=100", token=admin)
        self.assertEqual(status, 200)
        self.assertEqual(
            [event["action"] for event in audit["items"]],
            ["stock_adjusted", "order_created", "order_created"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
