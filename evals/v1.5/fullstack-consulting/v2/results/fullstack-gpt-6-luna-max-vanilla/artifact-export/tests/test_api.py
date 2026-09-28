import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DepotFlowIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="depotflow-test-")
        cls.data_dir = Path(cls.tmp.name) / "state"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.proc = None
        cls.start_server()

    @classmethod
    def start_server(cls):
        env = os.environ.copy()
        env.update({"DATA_DIR": str(cls.data_dir), "SEED_DEMO": "1", "PORT": str(cls.port)})
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if cls.proc.poll() is not None:
                raise RuntimeError("DepotFlow test server exited unexpectedly")
            try:
                status, body, _ = cls.call("GET", "/api/health")
                if status == 200 and body == {"status": "ok"}:
                    return
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("DepotFlow test server did not become ready")

    @classmethod
    def stop_server(cls):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.terminate()
            cls.proc.wait(timeout=10)

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        cls.tmp.cleanup()

    @classmethod
    def call(cls, method, path, data=None, token=None, key=None, extra_headers=None):
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if key is not None:
            headers["Idempotency-Key"] = key
        if extra_headers:
            headers.update(extra_headers)
        raw = json.dumps(data, separators=(",", ":")).encode() if data is not None else None
        request = urllib.request.Request(cls.base + path, data=raw, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read()), response.headers
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read()), error.headers

    @classmethod
    def login(cls, email, password="DepotDemo!2026"):
        status, body, _ = cls.call("POST", "/api/session", {"email": email, "password": password})
        if status != 200:
            raise AssertionError((status, body))
        return body["token"], body["user"]

    def test_routes_transactions_idempotency_roles_tenants_and_restart(self):
        status, body, _ = self.call("GET", "/api/health")
        self.assertEqual((status, body), (200, {"status": "ok"}))
        self.assertEqual(self.call("GET", "/api/inventory")[0], 401)
        self.assertEqual(self.call("GET", "/api/inventory", token="not-a-session-token")[0], 401)
        self.assertEqual(self.call("POST", "/api/session", {"email": "admin@north.example", "password": "wrong"})[0], 401)

        north, north_user = self.login("operator@north.example")
        admin, _ = self.login("admin@north.example")
        viewer, _ = self.login("viewer@north.example")
        south, south_user = self.login("operator@south.example")
        self.assertEqual(north_user, {"email": "operator@north.example", "role": "operator", "tenant": "north"})
        self.assertEqual(south_user["tenant"], "south")
        self.assertEqual(self.call("GET", "/api/me", token=north)[1], north_user)
        n_inventory = self.call("GET", "/api/inventory", token=north, extra_headers={"X-Tenant": "south", "X-Role": "admin"})[1]["items"]
        s_inventory = self.call("GET", "/api/inventory", token=south)[1]["items"]
        self.assertEqual(len(n_inventory), 3)
        self.assertEqual(n_inventory, s_inventory)
        self.assertTrue(all(type(item[field]) is int for item in n_inventory for field in ("on_hand", "reserved", "available", "price_cents", "version")))
        self.assertEqual(self.call("GET", "/api/orders?status=not-a-status", token=north)[0], 400)
        self.assertEqual(self.call("GET", "/api/orders?limit=1.5", token=north)[0], 400)
        self.assertEqual(self.call("GET", "/api/audit?cursor=nope", token=north)[0], 400)
        self.assertEqual(self.call("GET", "/api/orders?q=absent", token=north)[1]["items"], [])

        writable = {"client_ref": "viewer-denied", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        self.assertEqual(self.call("POST", "/api/orders", writable, viewer, "viewer-key")[0], 403)
        self.assertEqual(self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "test"}, north, "operator-adjust")[0], 403)
        self.assertEqual(self.call("POST", "/api/orders", writable, north)[0], 400)

        invalid_payloads = [
            {"client_ref": "bad-bool", "lines": [{"sku": "BOLT", "quantity": True}]},
            {"client_ref": "bad-fraction", "lines": [{"sku": "BOLT", "quantity": 1.5}]},
            {"client_ref": "bad-duplicate", "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 2}]},
            {"client_ref": "bad-sku", "lines": [{"sku": "NOPE", "quantity": 1}]},
            {"client_ref": "empty-lines", "lines": []},
        ]
        for index, payload in enumerate(invalid_payloads):
            self.assertEqual(self.call("POST", "/api/orders", payload, north, f"invalid-{index}")[0], 400)

        identical_payload = {"client_ref": "concurrent-identical", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        same_gate = threading.Barrier(2)
        def create_identical(_):
            same_gate.wait()
            return self.call("POST", "/api/orders", identical_payload, north, "same-concurrent-create")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            duplicate_results = list(pool.map(create_identical, range(2)))
        self.assertEqual([result[0] for result in duplicate_results], [201, 201])
        self.assertEqual(duplicate_results[0][1], duplicate_results[1][1])
        duplicate_id = duplicate_results[0][1]["id"]
        self.assertEqual(sum(item["entity_id"] == duplicate_id for item in self.call("GET", "/api/audit", token=north)[1]["items"]), 1)

        sample_payload = {"client_ref": "sample-zero", "lines": [{"sku": "SAMPLE", "quantity": 2, "unit_price_cents": 999999}], "tenant": "south", "role": "admin"}
        status, sample, _ = self.call("POST", "/api/orders", sample_payload, north, "sample-create")
        self.assertEqual(status, 201)
        self.assertEqual((sample["total_cents"], sample["lines"][0]["unit_price_cents"]), (0, 0))
        audit_before_replay = self.call("GET", "/api/audit", token=north)[1]["items"]
        self.assertEqual(self.call("POST", "/api/orders", sample_payload, north, "sample-create")[:2], (201, sample))
        self.assertEqual(self.call("GET", "/api/audit", token=north)[1]["items"], audit_before_replay)
        altered = dict(sample_payload, client_ref="changed-ref")
        self.assertEqual(self.call("POST", "/api/orders", altered, north, "sample-create")[0], 409)
        self.assertEqual(self.call("POST", f"/api/orders/{sample['id']}/cancel", {"expected_version": 1}, north, "sample-create")[0], 409)
        self.assertEqual(self.call("POST", "/api/orders", sample_payload, north, "sample-new-key")[0], 409)
        self.assertEqual(self.call("GET", f"/api/orders/{sample['id']}", token=south)[0], 404)
        south_same_ref = {"client_ref": "sample-zero", "lines": [{"sku": "SAMPLE", "quantity": 2}]}
        self.assertEqual(self.call("POST", "/api/orders", south_same_ref, south, "south-ref")[0], 201)

        for suffix in ("a", "b", "c"):
            payload = {"client_ref": f"Page-{suffix}", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
            self.assertEqual(self.call("POST", "/api/orders", payload, north, f"page-{suffix}")[0], 201)
        pages, cursor = [], None
        while True:
            path = "/api/orders?q=PAGE&limit=1" + (f"&cursor={cursor}" if cursor else "")
            status, result, _ = self.call("GET", path, token=north)
            self.assertEqual(status, 200)
            pages.extend(order["client_ref"] for order in result["items"])
            cursor = result["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(pages, ["Page-a", "Page-b", "Page-c"])
        self.assertEqual(self.call("GET", "/api/orders?cursor=999999", token=north)[0], 400)

        concurrent_orders = []
        for suffix in ("one", "two"):
            payload = {"client_ref": f"race-{suffix}", "lines": [{"sku": "BOLT", "quantity": 70}]}
            status, order, _ = self.call("POST", "/api/orders", payload, north, f"race-create-{suffix}")
            self.assertEqual(status, 201)
            concurrent_orders.append(order)
        gate = threading.Barrier(2)
        def reserve(order):
            gate.wait()
            return self.call("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, north, f"race-reserve-{order['client_ref']}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            race_results = list(pool.map(reserve, concurrent_orders))
        self.assertEqual(sorted(result[0] for result in race_results), [200, 409])
        current = self.call("GET", "/api/inventory", token=north)[1]["items"]
        bolt = next(item for item in current if item["sku"] == "BOLT")
        self.assertEqual((bolt["on_hand"], bolt["reserved"], bolt["available"]), (100, 70, 30))
        winner = next(result[1] for result in race_results if result[0] == 200)
        self.assertEqual(self.call("POST", f"/api/orders/{winner['id']}/cancel", {"expected_version": 2}, north, "race-cancel")[0], 200)

        multi = {"client_ref": "atomic-failure", "lines": [{"sku": "BOLT", "quantity": 101}, {"sku": "CABLE", "quantity": 1}]}
        _, atomic_order, _ = self.call("POST", "/api/orders", multi, north, "atomic-create")
        before_atomic = self.call("GET", "/api/inventory", token=north)[1]["items"]
        audit_before_atomic = self.call("GET", "/api/audit", token=north)[1]["items"]
        failure = self.call("POST", f"/api/orders/{atomic_order['id']}/reserve", {"expected_version": 1}, north, "atomic-reserve")
        self.assertEqual(failure[0], 409)
        after_atomic = self.call("GET", "/api/inventory", token=north)[1]["items"]
        self.assertEqual(before_atomic, after_atomic)
        self.assertEqual(self.call("GET", f"/api/orders/{atomic_order['id']}", token=north)[1]["status"], "draft")
        self.assertEqual(self.call("GET", "/api/audit", token=north)[1]["items"], audit_before_atomic)
        bolt = next(item for item in after_atomic if item["sku"] == "BOLT")
        self.assertEqual(self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 1, "expected_version": bolt["version"], "reason": "test receiving"}, admin, "add-one")[0], 200)
        self.assertEqual(self.call("POST", f"/api/orders/{atomic_order['id']}/reserve", {"expected_version": 1}, north, "atomic-reserve")[0], 200)
        atomic_replay = self.call("POST", f"/api/orders/{atomic_order['id']}/reserve", {"expected_version": 1}, north, "atomic-reserve")
        self.assertEqual(atomic_replay[0], 200)
        current = self.call("GET", "/api/inventory", token=north)[1]["items"]
        self.assertEqual(next(item["available"] for item in current if item["sku"] == "BOLT"), 0)
        bolt = next(item for item in current if item["sku"] == "BOLT")
        self.assertEqual(self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": -1, "expected_version": bolt["version"], "reason": "bad count"}, admin, "below-reserved")[0], 409)
        self.assertEqual(self.call("POST", f"/api/orders/{atomic_order['id']}/cancel", {"expected_version": 2}, north, "atomic-cancel")[0], 200)

        # Failed keys do not get consumed: the atomic reserve key succeeded above after new stock arrived.
        self.assertEqual(self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": True, "expected_version": 1, "reason": "bad bool"}, admin, "bad-adjust")[0], 400)
        self.assertEqual(self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 0, "expected_version": 1, "reason": "bad zero"}, admin, "bad-zero")[0], 400)

        order_payload = {"client_ref": "return-flow", "lines": [{"sku": "BOLT", "quantity": 3}, {"sku": "CABLE", "quantity": 2}]}
        status, order, _ = self.call("POST", "/api/orders", order_payload, north, "return-create")
        self.assertEqual(status, 201)
        self.assertEqual(order["total_cents"], 8748)
        reserved = self.call("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, north, "return-reserve")
        self.assertEqual((reserved[0], reserved[1]["status"], reserved[1]["version"]), (200, "reserved", 2))
        shipped = self.call("POST", f"/api/orders/{order['id']}/ship", {"expected_version": 2}, north, "return-ship")
        self.assertEqual((shipped[1]["status"], shipped[1]["version"]), ("shipped", 3))
        partial_payload = {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}
        partial = self.call("POST", f"/api/orders/{order['id']}/returns", partial_payload, north, "partial-return")
        self.assertEqual((partial[0], partial[1]["status"], partial[1]["version"]), (200, "shipped", 4))
        before_bad_return = self.call("GET", "/api/inventory", token=north)[1]["items"]
        overreturn = self.call("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 3}]}, north, "over-return")
        self.assertEqual(overreturn[0], 409)
        self.assertEqual(before_bad_return, self.call("GET", "/api/inventory", token=north)[1]["items"])
        duplicate_return = self.call("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 1}]}, north, "duplicate-return")
        self.assertEqual(duplicate_return[0], 400)
        full_payload = {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 2}, {"sku": "CABLE", "quantity": 2}]}
        full = self.call("POST", f"/api/orders/{order['id']}/returns", full_payload, north, "full-return")
        self.assertEqual((full[0], full[1]["status"], full[1]["version"]), (200, "returned", 5))
        self.assertEqual([line["returned_quantity"] for line in full[1]["lines"]], [3, 2])
        self.assertEqual(self.call("POST", f"/api/orders/{order['id']}/cancel", {"expected_version": 4}, north, "stale-cancel")[1]["error"]["code"], "stale_version")
        self.assertEqual(self.call("POST", f"/api/orders/{order['id']}/cancel", {"expected_version": 5}, north, "cancel-returned")[0], 409)
        inv = self.call("GET", "/api/inventory", token=north)[1]["items"]
        self.assertEqual(next(item["on_hand"] for item in inv if item["sku"] == "BOLT"), 101)
        self.assertTrue(all(item["available"] >= 0 and item["reserved"] <= item["on_hand"] for item in inv))

        dashboard = self.call("GET", "/api/dashboard", token=north)[1]
        self.assertEqual(dashboard["orders_by_status"]["returned"], 1)
        self.assertEqual(dashboard["reserved_units"], 0)
        audit = self.call("GET", "/api/audit?limit=100", token=north)[1]["items"]
        self.assertTrue(any(item["action"] == "order.returns" and item["entity_id"] == order["id"] for item in audit))
        south_audit = self.call("GET", "/api/audit", token=south)[1]["items"]
        self.assertTrue(south_audit)
        self.assertTrue(all(item["actor"] == "operator@south.example" for item in south_audit))

        # Persisted session, stock, orders, audit, and replay response all survive process restart.
        self.stop_server()
        self.start_server()
        self.assertEqual(self.call("GET", "/api/me", token=north)[1], north_user)
        self.assertEqual(self.call("GET", f"/api/orders/{order['id']}", token=north)[1], full[1])
        self.assertEqual(self.call("GET", "/api/inventory", token=north)[1]["items"], inv)
        audit_after_restart = self.call("GET", "/api/audit?limit=100", token=north)[1]["items"]
        self.assertEqual(audit_after_restart, audit)
        self.assertEqual(self.call("POST", f"/api/orders/{order['id']}/returns", full_payload, north, "full-return")[:2], (200, full[1]))
        self.assertEqual(self.call("GET", "/api/audit?limit=100", token=north)[1]["items"], audit)
        self.assertEqual(self.call("GET", "/api/dashboard", token=north)[1], dashboard)


if __name__ == "__main__":
    unittest.main()
