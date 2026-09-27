import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "DepotDemo!2026"


class DepotFlowRoutes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="depotflow-test-")
        self.data_dir = Path(self.temp.name) / "state"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.start_server()
        self.north_admin = self.login("admin@north.example")
        self.north_operator = self.login("operator@north.example")
        self.north_viewer = self.login("viewer@north.example")
        self.south_operator = self.login("operator@south.example")

    def tearDown(self):
        self.stop_server()
        self.temp.cleanup()

    def start_server(self):
        env = os.environ.copy()
        env.update({"DATA_DIR": str(self.data_dir), "PORT": str(self.port), "SEED_DEMO": "1"})
        self.process = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(150):
            if self.process.poll() is not None:
                self.fail(f"server exited during startup with code {self.process.returncode}")
            try:
                status, result = self.call("GET", "/api/health", auth=False)
                if status == 200 and result == {"status": "ok"}:
                    return
            except Exception:
                pass
            time.sleep(0.05)
        self.fail("server did not become ready")

    def stop_server(self):
        process = getattr(self, "process", None)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def restart_server(self):
        self.stop_server()
        self.start_server()

    def call(self, method, path, body=None, token=None, key=None, extra_headers=None, auth=True):
        headers = {"Accept": "application/json"}
        if auth and token:
            headers["Authorization"] = f"Bearer {token}"
        if key is not None:
            headers["Idempotency-Key"] = key
        if extra_headers:
            headers.update(extra_headers)
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read()
                return response.status, json.loads(payload) if payload else None
        except urllib.error.HTTPError as error:
            payload = error.read()
            return error.code, json.loads(payload) if payload else None

    def login(self, email, password=PASSWORD):
        status, result = self.call("POST", "/api/session", {"email": email, "password": password}, auth=False)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["user"]["email"], email)
        return result["token"]

    def key(self):
        return str(uuid.uuid4())

    def create_order(self, ref, lines=None, token=None, key=None, extras=None):
        body = {"client_ref": ref, "lines": lines or [{"sku": "BOLT", "quantity": 1}]}
        if extras:
            body.update(extras)
        return self.call("POST", "/api/orders", body, token or self.north_operator, key or self.key())

    def test_auth_role_tenant_isolation_and_payload_validation(self):
        status, _ = self.call("GET", "/api/inventory", auth=False)
        self.assertEqual(status, 401)
        status, _ = self.call("GET", "/api/inventory", extra_headers={"Authorization": "Bearer invalid-token"})
        self.assertEqual(status, 401)
        status, error = self.call("POST", "/api/session", {"email": "admin@north.example", "password": "wrong"}, auth=False)
        self.assertEqual((status, error["error"]["code"]), (401, "invalid_credentials"))
        status, me = self.call("GET", "/api/me", token=self.north_operator, extra_headers={"X-Tenant-ID": "south", "X-Role": "admin"})
        self.assertEqual(status, 200)
        self.assertEqual(me, {"email": "operator@north.example", "role": "operator", "tenant": "north"})
        status, north = self.call("GET", "/api/inventory", token=self.north_operator)
        self.assertEqual(status, 200)
        self.assertEqual([(item["sku"], item["on_hand"], item["reserved"], item["available"], item["price_cents"], item["version"]) for item in north["items"]], [
            ("BOLT", 100, 0, 100, 1250, 1), ("CABLE", 60, 0, 60, 2499, 1), ("SAMPLE", 20, 0, 20, 0, 1),
        ])
        _, south = self.call("GET", "/api/inventory", token=self.south_operator)
        self.assertEqual(south["items"], north["items"])

        # Extra client fields are ignored; prices are read from the tenant catalog.
        status, order = self.create_order("safe-ref", [{"sku": "BOLT", "quantity": 2, "unit_price_cents": 1}], extras={"tenant": "south", "role": "admin", "price_cents": 1})
        self.assertEqual(status, 201)
        self.assertEqual(order["total_cents"], 2500)
        self.assertEqual(order["lines"][0]["unit_price_cents"], 1250)
        south_status, south_same_ref = self.create_order("safe-ref", token=self.south_operator)
        self.assertEqual(south_status, 201)
        self.assertNotEqual(south_same_ref["id"], order["id"])
        status, error = self.call("GET", f"/api/orders/{order['id']}", token=self.south_operator)
        self.assertEqual((status, error["error"]["code"]), (404, "not_found"))
        status, error = self.call("POST", f"/api/orders/{order['id']}/cancel", {"expected_version": 1}, token=self.south_operator, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (404, "not_found"))

        status, error = self.create_order("safe-ref")
        self.assertEqual((status, error["error"]["code"]), (409, "duplicate_client_ref"))
        status, error = self.create_order("unknown-sku", [{"sku": "MISSING", "quantity": 1}])
        self.assertEqual((status, error["error"]["code"]), (400, "unknown_sku"))
        status, error = self.create_order("dupe-lines", [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 2}])
        self.assertEqual((status, error["error"]["code"]), (400, "duplicate_sku"))
        status, error = self.create_order("bool-is-not-int", [{"sku": "BOLT", "quantity": True}])
        self.assertEqual((status, error["error"]["code"]), (400, "invalid_payload"))
        status, error = self.call("POST", "/api/orders", {"client_ref": "missing-key", "lines": [{"sku": "BOLT", "quantity": 1}]}, token=self.north_operator)
        self.assertEqual((status, error["error"]["code"]), (400, "idempotency_key_required"))
        status, error = self.call("POST", "/api/orders", {"client_ref": "viewer", "lines": []}, token=self.north_viewer)
        self.assertEqual((status, error["error"]["code"]), (403, "forbidden"))
        status, error = self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "test", "role": "admin", "tenant": "south"}, token=self.north_operator, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (403, "forbidden"))
        status, error = self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "test"}, token=self.north_viewer, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (403, "forbidden"))
        _, audit = self.call("GET", "/api/audit", token=self.north_operator)
        self.assertEqual(len(audit["items"]), 1)
        _, south_after = self.call("GET", "/api/inventory", token=self.south_operator)
        self.assertEqual(next(item for item in south_after["items"] if item["sku"] == "BOLT")["on_hand"], 100)
        _, south_audit = self.call("GET", "/api/audit", token=self.south_operator)
        self.assertEqual([item["entity_id"] for item in south_audit["items"]], [south_same_ref["id"]])

    def test_atomic_reserve_ship_partial_full_returns_cancel_and_audit(self):
        status, order = self.create_order("return-flow", [{"sku": "BOLT", "quantity": 3}, {"sku": "CABLE", "quantity": 2}])
        self.assertEqual(status, 201)
        self.assertEqual((order["status"], order["version"], order["total_cents"]), ("draft", 1, 8748))
        status, reserved = self.call("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, token=self.north_operator, key=self.key())
        self.assertEqual((status, reserved["status"], reserved["version"]), (200, "reserved", 2))
        _, inventory = self.call("GET", "/api/inventory", token=self.north_operator)
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        cable = next(item for item in inventory["items"] if item["sku"] == "CABLE")
        self.assertEqual((bolt["on_hand"], bolt["reserved"], bolt["available"]), (100, 3, 97))
        self.assertEqual((cable["on_hand"], cable["reserved"], cable["available"]), (60, 2, 58))

        status, error = self.call("POST", f"/api/orders/{order['id']}/ship", {"expected_version": 1}, token=self.north_operator, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (409, "stale_version"))
        status, shipped = self.call("POST", f"/api/orders/{order['id']}/ship", {"expected_version": 2}, token=self.north_operator, key=self.key())
        self.assertEqual((status, shipped["status"], shipped["version"]), (200, "shipped", 3))
        status, error = self.call("POST", f"/api/orders/{order['id']}/cancel", {"expected_version": 3}, token=self.north_operator, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (409, "invalid_transition"))
        _, inventory = self.call("GET", "/api/inventory", token=self.north_operator)
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        self.assertEqual((bolt["on_hand"], bolt["reserved"], bolt["available"]), (97, 0, 97))

        status, partial = self.call("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}, token=self.north_operator, key=self.key())
        self.assertEqual((status, partial["status"], partial["version"]), (200, "shipped", 4))
        self.assertEqual(next(line["returned_quantity"] for line in partial["lines"] if line["sku"] == "BOLT"), 1)
        status, error = self.call("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 3}]}, token=self.north_operator, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (409, "return_exceeds_shipped"))
        status, returned = self.call("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 2}, {"sku": "CABLE", "quantity": 2}]}, token=self.north_operator, key=self.key())
        self.assertEqual((status, returned["status"], returned["version"]), (200, "returned", 5))
        status, error = self.call("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 5, "lines": [{"sku": "BOLT", "quantity": 1}]}, token=self.north_operator, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (409, "invalid_transition"))
        _, inventory = self.call("GET", "/api/inventory", token=self.north_operator)
        self.assertEqual([(item["on_hand"], item["reserved"], item["available"]) for item in inventory["items"][:2]], [(100, 0, 100), (60, 0, 60)])

        status, cancel_order = self.create_order("cancel-flow", [{"sku": "BOLT", "quantity": 2}])
        self.assertEqual(status, 201)
        _, reserved_cancel = self.call("POST", f"/api/orders/{cancel_order['id']}/reserve", {"expected_version": 1}, token=self.north_operator, key=self.key())
        status, cancelled = self.call("POST", f"/api/orders/{cancel_order['id']}/cancel", {"expected_version": reserved_cancel["version"]}, token=self.north_operator, key=self.key())
        self.assertEqual((status, cancelled["status"], cancelled["version"]), (200, "cancelled", 3))
        _, inventory = self.call("GET", "/api/inventory", token=self.north_operator)
        self.assertEqual(next(item for item in inventory["items"] if item["sku"] == "BOLT")["reserved"], 0)
        _, dashboard = self.call("GET", "/api/dashboard", token=self.north_operator)
        self.assertEqual((dashboard["orders_by_status"]["returned"], dashboard["orders_by_status"]["cancelled"]), (1, 1))
        _, audit = self.call("GET", "/api/audit", token=self.north_operator)
        self.assertEqual(len(audit["items"]), 8)
        self.assertEqual(audit["items"][-1]["action"], "order.cancelled")

    def test_atomic_multi_line_failure_and_admin_adjustment_conflicts(self):
        status, order = self.create_order("atomic-fail", [{"sku": "BOLT", "quantity": 2}, {"sku": "CABLE", "quantity": 1000}])
        self.assertEqual(status, 201)
        _, audit_before = self.call("GET", "/api/audit", token=self.north_operator)
        _, before = self.call("GET", "/api/inventory", token=self.north_operator)
        status, error = self.call("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, token=self.north_operator, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (409, "insufficient_stock"))
        _, after_order = self.call("GET", f"/api/orders/{order['id']}", token=self.north_operator)
        _, after_inventory = self.call("GET", "/api/inventory", token=self.north_operator)
        _, audit_after = self.call("GET", "/api/audit", token=self.north_operator)
        self.assertEqual((after_order["status"], after_order["version"]), ("draft", 1))
        self.assertEqual(after_inventory["items"], before["items"])
        self.assertEqual(audit_after["items"], audit_before["items"])

        _, retry_order = self.create_order("retry-failed-key", [{"sku": "BOLT", "quantity": 101}])
        retry_key = self.key()
        status, error = self.call("POST", f"/api/orders/{retry_order['id']}/reserve", {"expected_version": 1}, token=self.north_operator, key=retry_key)
        self.assertEqual((status, error["error"]["code"]), (409, "insufficient_stock"))
        _, audit_after_failure = self.call("GET", "/api/audit", token=self.north_operator)

        status, adjusted = self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 5, "expected_version": 1, "reason": "cycle count"}, token=self.north_admin, key=self.key())
        self.assertEqual((status, adjusted["on_hand"], adjusted["version"]), (200, 105, 2))
        _, audit_after_adjustment = self.call("GET", "/api/audit", token=self.north_operator)
        self.assertEqual(len(audit_after_adjustment["items"]), len(audit_after_failure["items"]) + 1)
        status, retried = self.call("POST", f"/api/orders/{retry_order['id']}/reserve", {"expected_version": 1}, token=self.north_operator, key=retry_key)
        self.assertEqual((status, retried["status"], retried["version"]), (200, "reserved", 2))
        _, audit_after_retry = self.call("GET", "/api/audit", token=self.north_operator)
        self.assertEqual(len(audit_after_retry["items"]), len(audit_after_adjustment["items"]) + 1)
        status, error = self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 5, "expected_version": 1, "reason": "stale count"}, token=self.north_admin, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (409, "stale_version"))
        status, error = self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 0, "expected_version": 2, "reason": "no change"}, token=self.north_admin, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (400, "invalid_payload"))

        _, reserve_order = self.create_order("reserved-for-reduction", [{"sku": "BOLT", "quantity": 1}])
        _, reserved = self.call("POST", f"/api/orders/{reserve_order['id']}/reserve", {"expected_version": 1}, token=self.north_operator, key=self.key())
        status, error = self.call("POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": -105, "expected_version": 4, "reason": "below reservation"}, token=self.north_admin, key=self.key())
        self.assertEqual((status, error["error"]["code"]), (409, "insufficient_stock"))
        self.assertEqual(reserved["status"], "reserved")

    def test_zero_price_sample_and_order_cursor_pagination(self):
        status, zero = self.create_order("sample-zero", [{"sku": "SAMPLE", "quantity": 2}])
        self.assertEqual((status, zero["total_cents"], zero["lines"][0]["unit_price_cents"]), (201, 0, 0))
        refs = [f"Page-AbC-{index}" for index in range(3)]
        created = []
        for ref in refs:
            status, result = self.create_order(ref, [{"sku": "SAMPLE", "quantity": 1}])
            self.assertEqual(status, 201)
            created.append(result["id"])
        status, first = self.call("GET", "/api/orders?q=page-aBc&limit=1", token=self.north_operator)
        self.assertEqual(status, 200)
        self.assertIsNotNone(first["next_cursor"])
        status, second = self.call("GET", f"/api/orders?q=PAGE-abc&limit=1&cursor={first['next_cursor']}", token=self.north_operator)
        self.assertEqual(status, 200)
        status, third = self.call("GET", f"/api/orders?q=page-abc&limit=1&cursor={second['next_cursor']}", token=self.north_operator)
        self.assertEqual(status, 200)
        self.assertIsNone(third["next_cursor"])
        ids = [first["items"][0]["id"], second["items"][0]["id"], third["items"][0]["id"]]
        self.assertEqual(ids, created)
        status, error = self.call("GET", "/api/orders?status=unknown", token=self.north_operator)
        self.assertEqual((status, error["error"]["code"]), (400, "invalid_query"))
        status, error = self.call("GET", "/api/orders?limit=101", token=self.north_operator)
        self.assertEqual((status, error["error"]["code"]), (400, "invalid_query"))
        status, error = self.call("GET", "/api/orders?cursor=not-a-cursor!", token=self.north_operator)
        self.assertEqual((status, error["error"]["code"]), (400, "invalid_cursor"))
        status, error = self.call("GET", "/api/orders?sort=desc", token=self.north_operator)
        self.assertEqual((status, error["error"]["code"]), (400, "invalid_query"))
        status, empty = self.call("GET", "/api/orders?q=no-such-order", token=self.north_operator)
        self.assertEqual((status, empty["items"], empty["next_cursor"]), (200, [], None))

    def test_concurrent_same_key_replays_and_reservations_do_not_oversell(self):
        body = {"client_ref": "concurrent-create", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        same_key = self.key()

        def same_create(_):
            return self.call("POST", "/api/orders", body, token=self.north_operator, key=same_key)

        with ThreadPoolExecutor(max_workers=8) as pool:
            replay_results = list(pool.map(same_create, range(8)))
        self.assertEqual([status for status, _ in replay_results], [201] * 8)
        self.assertEqual(len({result["id"] for _, result in replay_results}), 1)
        _, audit = self.call("GET", "/api/audit", token=self.north_operator)
        self.assertEqual(sum(item["action"] == "order.created" for item in audit["items"]), 1)
        status, error = self.call("POST", "/api/orders", {"client_ref": "different", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=self.north_operator, key=same_key)
        self.assertEqual((status, error["error"]["code"]), (409, "idempotency_conflict"))

        _, same_reserve_order = self.create_order("concurrent-reserve", [{"sku": "BOLT", "quantity": 10}])
        reserve_body = {"expected_version": 1}
        reserve_key = self.key()

        def same_reserve(_):
            return self.call("POST", f"/api/orders/{same_reserve_order['id']}/reserve", reserve_body, token=self.north_operator, key=reserve_key)

        with ThreadPoolExecutor(max_workers=6) as pool:
            reserve_replays = list(pool.map(same_reserve, range(6)))
        self.assertEqual([status for status, _ in reserve_replays], [200] * 6)
        self.assertEqual({result["version"] for _, result in reserve_replays}, {2})

        _, first = self.create_order("race-one", [{"sku": "BOLT", "quantity": 60}])
        _, second = self.create_order("race-two", [{"sku": "BOLT", "quantity": 60}])

        def reserve(order):
            return self.call("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, token=self.north_operator, key=self.key())

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, [first, second]))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(sum(status == 200 for status, _ in results), 1)
        _, inventory = self.call("GET", "/api/inventory", token=self.north_operator)
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        self.assertEqual((bolt["on_hand"], bolt["reserved"], bolt["available"]), (100, 70, 30))
        self.assertGreaterEqual(bolt["available"], 0)

    def test_idempotency_and_committed_state_survive_restart(self):
        key = self.key()
        body = {"sku": "BOLT", "delta": 7, "expected_version": 1, "reason": "restart check"}
        status, first = self.call("POST", "/api/stock/adjustments", body, token=self.north_admin, key=key)
        self.assertEqual((status, first["on_hand"], first["version"]), (200, 107, 2))
        status, error = self.call("POST", "/api/stock/adjustments", body, token=self.north_viewer, key=key)
        self.assertEqual((status, error["error"]["code"]), (403, "forbidden"))
        status, south_scoped = self.call("POST", "/api/orders", {"client_ref": "same-key-other-tenant", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=self.south_operator, key=key)
        self.assertEqual(status, 201)
        _, before_audit = self.call("GET", "/api/audit", token=self.north_operator)
        self.restart_server()
        status, replay = self.call("POST", "/api/stock/adjustments", body, token=self.north_admin, key=key)
        self.assertEqual((status, replay), (200, first))
        _, me = self.call("GET", "/api/me", token=self.north_admin)
        self.assertEqual(me["tenant"], "north")
        _, inventory = self.call("GET", "/api/inventory", token=self.north_operator)
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        self.assertEqual((bolt["on_hand"], bolt["version"]), (107, 2))
        _, after_audit = self.call("GET", "/api/audit", token=self.north_operator)
        self.assertEqual(after_audit["items"], before_audit["items"])

        status, error = self.call("POST", "/api/stock/adjustments", {**body, "reason": "changed"}, token=self.north_admin, key=key)
        self.assertEqual((status, error["error"]["code"]), (409, "idempotency_conflict"))
        status, error = self.call("POST", "/api/orders", {"client_ref": "same-key-other-path", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, token=self.north_admin, key=key)
        self.assertEqual((status, error["error"]["code"]), (409, "idempotency_conflict"))

    def test_audit_cursor_and_mutation_versions(self):
        for index in range(3):
            self.create_order(f"audit-page-{index}", [{"sku": "SAMPLE", "quantity": 1}])
        pages = []
        cursor = None
        while True:
            path = "/api/audit?limit=1" + (f"&cursor={cursor}" if cursor else "")
            status, result = self.call("GET", path, token=self.north_operator)
            self.assertEqual(status, 200)
            pages.extend(result["items"])
            cursor = result["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(len(pages), 3)
        self.assertEqual([item["action"] for item in pages], ["order.created"] * 3)
        self.assertEqual([item["actor"] for item in pages], ["operator@north.example"] * 3)


if __name__ == "__main__":
    unittest.main()
