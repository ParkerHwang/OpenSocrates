#!/usr/bin/env python3
"""Route-level integration coverage for DepotFlow."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "DepotDemo!2026"


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class DepotFlowIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="depotflow-test-")
        self.port = free_port()
        self.proc: subprocess.Popen[str] | None = None
        self.start_server(seed=True)

    def tearDown(self) -> None:
        self.stop_server()
        self.tempdir.cleanup()

    def start_server(self, seed: bool = True) -> None:
        env = os.environ.copy()
        env.update({"PORT": str(self.port), "DATA_DIR": self.tempdir.name, "SEED_DEMO": "1" if seed else "0"})
        self.proc = subprocess.Popen(
            [str(ROOT / "run.sh")],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                status, body = self.request("GET", "/api/health")
                if status == 200 and body == {"status": "ok"}:
                    return
            except (URLError, ConnectionError):
                pass
            if self.proc.poll() is not None:
                self.proc.wait(timeout=1)
                self.fail("server exited during startup")
            time.sleep(0.05)
        self.fail("server did not become healthy")

    def stop_server(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=2)
        self.proc = None

    def restart_server(self) -> None:
        self.stop_server()
        self.start_server(seed=True)

    def request(self, method: str, path: str, payload=None, token: str | None = None, key: str | None = None):
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if key is not None:
            headers["Idempotency-Key"] = key
        request = Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=8) as response:
                body = json.loads(response.read().decode())
                return response.status, body
        except HTTPError as exc:
            body = json.loads(exc.read().decode())
            return exc.code, body

    def login(self, email: str) -> str:
        status, body = self.request("POST", "/api/session", {"email": email, "password": PASSWORD})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["user"]["email"], email)
        return body["token"]

    def assert_error(self, status: int, body: dict, expected_status: int, code: str) -> None:
        self.assertEqual(status, expected_status, body)
        self.assertEqual(body.get("error", {}).get("code"), code, body)

    def test_auth_roles_and_tenant_isolation(self) -> None:
        status, body = self.request("GET", "/api/health")
        self.assertEqual((status, body), (200, {"status": "ok"}))
        status, body = self.request("GET", "/api/inventory")
        self.assert_error(status, body, 401, "unauthorized")

        north_viewer = self.login("viewer@north.example")
        north_operator = self.login("operator@north.example")
        south_operator = self.login("operator@south.example")
        status, body = self.request("GET", "/api/me", token=north_viewer)
        self.assertEqual(body, {"email": "viewer@north.example", "role": "viewer", "tenant": "north"})
        status, body = self.request("GET", "/api/inventory", token=north_viewer)
        self.assertEqual(status, 200)
        self.assertEqual([item["sku"] for item in body["items"]], ["BOLT", "CABLE", "SAMPLE"])

        status, body = self.request(
            "POST",
            "/api/orders",
            {"client_ref": "viewer-attempt", "lines": [{"sku": "SAMPLE", "quantity": 1}]},
            token=north_viewer,
            key="viewer-mutation",
        )
        self.assert_error(status, body, 403, "forbidden")
        status, body = self.request(
            "POST",
            "/api/stock/adjustments",
            {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "no"},
            token=north_viewer,
            key="viewer-stock",
        )
        self.assert_error(status, body, 403, "forbidden")

        status, body = self.request(
            "POST",
            "/api/orders",
            {"client_ref": "south-private", "lines": [{"sku": "SAMPLE", "quantity": 1}]},
            token=south_operator,
            key="south-create",
        )
        self.assertEqual(status, 201, body)
        south_order_id = body["id"]
        status, body = self.request("GET", f"/api/orders/{south_order_id}", token=north_operator)
        self.assert_error(status, body, 404, "order_not_found")

    def test_validation_zero_price_atomic_and_idempotency(self) -> None:
        operator = self.login("operator@north.example")
        admin = self.login("admin@north.example")
        status, body = self.request("GET", "/api/audit", token=operator)
        self.assertEqual(body["items"], [])

        sample_payload = {
            "client_ref": "sample-zero",
            "lines": [{"sku": "SAMPLE", "quantity": 2, "unit_price_cents": 999999}],
            "tenant": "south",
            "role": "admin",
        }
        first_status, first = self.request("POST", "/api/orders", sample_payload, token=operator, key="sample-key")
        replay_status, replay = self.request("POST", "/api/orders", sample_payload, token=operator, key="sample-key")
        self.assertEqual(first_status, 201)
        self.assertEqual((replay_status, replay), (first_status, first))
        self.assertEqual(first["total_cents"], 0)
        self.assertEqual(first["lines"][0]["unit_price_cents"], 0)
        status, body = self.request("POST", "/api/orders", {**sample_payload, "client_ref": "other"}, token=operator, key="sample-key")
        self.assert_error(status, body, 409, "idempotency_conflict")
        status, body = self.request("POST", "/api/orders", sample_payload, token=operator, key="different-key")
        self.assert_error(status, body, 409, "client_ref_conflict")

        status, body = self.request(
            "POST", "/api/orders", {"client_ref": "bad-duplicate", "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 1}]}, token=operator, key="bad-key"
        )
        self.assert_error(status, body, 400, "duplicate_sku")
        status, body = self.request(
            "POST", "/api/orders", {"client_ref": "fixed-after-failure", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=operator, key="bad-key"
        )
        self.assertEqual(status, 201, body)
        status, body = self.request("POST", "/api/orders", {"client_ref": "missing-key", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=operator)
        self.assert_error(status, body, 400, "idempotency_key_required")

        before_status, before = self.request("GET", "/api/inventory", token=operator)
        before_bolt = next(item for item in before["items"] if item["sku"] == "BOLT")
        status, body = self.request(
            "POST", "/api/orders", {"client_ref": "atomic-failure", "lines": [{"sku": "BOLT", "quantity": 101}, {"sku": "CABLE", "quantity": 1}]}, token=operator, key="atomic-create"
        )
        self.assertEqual(status, 201)
        atomic_id = body["id"]
        status, body = self.request("POST", f"/api/orders/{atomic_id}/reserve", {"expected_version": 1}, token=operator, key="atomic-reserve")
        self.assert_error(status, body, 409, "insufficient_stock")
        _, after = self.request("GET", "/api/inventory", token=operator)
        after_bolt = next(item for item in after["items"] if item["sku"] == "BOLT")
        self.assertEqual(after_bolt, before_bolt)

        status, body = self.request("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": -101, "expected_version": 1, "reason": "too low"}, token=admin, key="bad-adjust")
        self.assert_error(status, body, 409, "insufficient_stock")
        status, body = self.request("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "cycle count"}, token=admin, key="good-adjust")
        self.assertEqual(status, 200)

        _, audit = self.request("GET", "/api/audit", token=operator)
        actions = [item["action"] for item in audit["items"]]
        self.assertEqual(actions.count("order.created"), 3)
        self.assertEqual(actions.count("stock.adjusted"), 1)

    def test_concurrent_reservation_stale_version_and_returns(self) -> None:
        operator = self.login("operator@north.example")

        def create(ref: str, key: str):
            return self.request("POST", "/api/orders", {"client_ref": ref, "lines": [{"sku": "BOLT", "quantity": 60}]}, token=operator, key=key)

        status, first = create("race-one", "race-create-one")
        self.assertEqual(status, 201)
        status, second = create("race-two", "race-create-two")
        self.assertEqual(status, 201)
        barrier = threading.Barrier(2)
        results: list[tuple[int, dict]] = []

        def reserve(order_id: str, key: str):
            barrier.wait()
            results.append(self.request("POST", f"/api/orders/{order_id}/reserve", {"expected_version": 1}, token=operator, key=key))

        threads = [
            threading.Thread(target=reserve, args=(first["id"], "race-reserve-one")),
            threading.Thread(target=reserve, args=(second["id"], "race-reserve-two")),
        ]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=8)
        self.assertEqual(len(results), 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        winner = first if next(result[0] for result in results if result[0] == 200) == 200 and self.request("GET", f"/api/orders/{first['id']}", token=operator)[1]["status"] == "reserved" else second
        loser = second if winner["id"] == first["id"] else first
        status, body = self.request("GET", "/api/inventory", token=operator)
        bolt = next(item for item in body["items"] if item["sku"] == "BOLT")
        self.assertEqual((bolt["reserved"], bolt["available"]), (60, 40))

        status, body = self.request("POST", f"/api/orders/{loser['id']}/reserve", {"expected_version": 1}, token=operator, key="loser-stale-retry")
        self.assert_error(status, body, 409, "insufficient_stock")
        status, body = self.request("POST", f"/api/orders/{winner['id']}/reserve", {"expected_version": 1}, token=operator, key="winner-stale-retry")
        self.assert_error(status, body, 409, "stale_version")

        status, shipped = self.request("POST", f"/api/orders/{winner['id']}/ship", {"expected_version": 2}, token=operator, key="ship-race-winner")
        self.assertEqual(status, 200, shipped)
        status, partial = self.request("POST", f"/api/orders/{winner['id']}/returns", {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 30}]}, token=operator, key="partial-return")
        self.assertEqual(status, 200, partial)
        self.assertEqual((partial["status"], partial["version"], partial["lines"][0]["returned_quantity"]), ("shipped", 4, 30))
        status, complete = self.request("POST", f"/api/orders/{winner['id']}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 30}]}, token=operator, key="full-return")
        self.assertEqual(status, 200, complete)
        self.assertEqual((complete["status"], complete["version"]), ("returned", 5))
        status, body = self.request("POST", f"/api/orders/{winner['id']}/returns", {"expected_version": 5, "lines": [{"sku": "BOLT", "quantity": 1}]}, token=operator, key="extra-return")
        self.assert_error(status, body, 409, "invalid_transition")
        status, body = self.request("POST", f"/api/orders/{loser['id']}/cancel", {"expected_version": 1}, token=operator, key="cancel-loser")
        self.assertEqual(status, 200, body)
        _, inventory = self.request("GET", "/api/inventory", token=operator)
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        self.assertEqual((bolt["on_hand"], bolt["reserved"], bolt["available"]), (100, 0, 100))

    def test_concurrent_identical_mutation_replays_once(self) -> None:
        operator = self.login("operator@north.example")
        payload = {"client_ref": "identical-race", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        barrier = threading.Barrier(2)
        results: list[tuple[int, dict]] = []

        def create_once() -> None:
            barrier.wait()
            results.append(self.request("POST", "/api/orders", payload, token=operator, key="identical-race-key"))

        threads = [threading.Thread(target=create_once), threading.Thread(target=create_once)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=8)
        self.assertEqual([status for status, _ in results], [201, 201])
        self.assertEqual(results[0][1], results[1][1])
        _, audit = self.request("GET", "/api/audit", token=operator)
        self.assertEqual([item["action"] for item in audit["items"]], ["order.created"])

    def test_pagination_stock_restart_and_durability(self) -> None:
        admin = self.login("admin@north.example")
        status, adjustment = self.request("POST", "/api/stock/adjustments", {"sku": "SAMPLE", "delta": 3, "expected_version": 1, "reason": "receiving"}, token=admin, key="durable-adjust")
        self.assertEqual(status, 200)
        self.restart_server()
        status, replay = self.request("POST", "/api/stock/adjustments", {"sku": "SAMPLE", "delta": 3, "expected_version": 1, "reason": "receiving"}, token=admin, key="durable-adjust")
        self.assertEqual((status, replay), (200, adjustment))
        _, inventory = self.request("GET", "/api/inventory", token=admin)
        sample = next(item for item in inventory["items"] if item["sku"] == "SAMPLE")
        self.assertEqual((sample["on_hand"], sample["version"]), (23, 2))

        for index in range(25):
            status, body = self.request("POST", "/api/orders", {"client_ref": f"page-{index:02d}", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=admin, key=f"page-{index}")
            self.assertEqual(status, 201, body)
        cursor = None
        seen: list[str] = []
        while True:
            path = "/api/orders?limit=4" + (f"&cursor={cursor}" if cursor else "")
            status, body = self.request("GET", path, token=admin)
            self.assertEqual(status, 200)
            seen.extend(item["client_ref"] for item in body["items"])
            cursor = body["next_cursor"]
            if not cursor: break
        self.assertEqual(seen, [f"page-{index:02d}" for index in range(25)])
        self.assertEqual(len(seen), len(set(seen)))
        status, body = self.request("GET", "/api/orders?status=wat", token=admin)
        self.assert_error(status, body, 400, "invalid_filter")
        status, body = self.request("GET", "/api/orders?cursor=not-a-cursor", token=admin)
        self.assert_error(status, body, 400, "invalid_cursor")

        cursor = None
        audit_ids: list[int] = []
        while True:
            path = "/api/audit?limit=7" + (f"&cursor={cursor}" if cursor else "")
            status, body = self.request("GET", path, token=admin)
            self.assertEqual(status, 200)
            audit_ids.extend(item["id"] for item in body["items"])
            cursor = body["next_cursor"]
            if not cursor: break
        self.assertEqual(audit_ids, sorted(audit_ids))
        self.assertGreaterEqual(len(audit_ids), 26)


if __name__ == "__main__":
    unittest.main()
