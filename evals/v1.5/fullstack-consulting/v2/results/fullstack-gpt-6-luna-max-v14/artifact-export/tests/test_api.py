from __future__ import annotations

import concurrent.futures
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "DepotDemo!2026"


class DepotFlowHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="depotflow-tests-")
        cls.data_dir = Path(cls.temp.name) / "state"
        cls.port = cls.free_port()
        cls.process = None
        cls.start_server()
        cls.tokens = {
            "admin": cls.login("admin@north.example"),
            "operator": cls.login("operator@north.example"),
            "viewer": cls.login("viewer@north.example"),
            "south": cls.login("admin@south.example"),
        }

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        cls.temp.cleanup()

    @staticmethod
    def free_port():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    @classmethod
    def start_server(cls):
        env = os.environ.copy()
        env.update({"PORT": str(cls.port), "DATA_DIR": str(cls.data_dir), "SEED_DEMO": "1", "QUIET_HTTP": "1"})
        cls.process = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 12
        while time.time() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError(f"DepotFlow failed to start (exit {cls.process.returncode})")
            try:
                status, body = cls.request("GET", "/api/health")
                if status == 200 and body == {"status": "ok"}:
                    return
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("DepotFlow did not become healthy within 12 seconds")

    @classmethod
    def stop_server(cls):
        if cls.process is not None and cls.process.poll() is None:
            cls.process.terminate()
            try:
                cls.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.wait(timeout=5)

    @classmethod
    def request(cls, method, path, body=None, token=None, key=None, extra_headers=None):
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if key is not None:
            headers["Idempotency-Key"] = key
        if extra_headers:
            headers.update(extra_headers)
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{cls.port}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else None

    @classmethod
    def login(cls, email):
        status, body = cls.request("POST", "/api/session", {"email": email, "password": PASSWORD})
        if status != 200:
            raise RuntimeError(f"Login failed for {email}: {status} {body}")
        return body["token"]

    def create_order(self, ref, lines, token="operator", key=None, extra=None):
        body = {"client_ref": ref, "lines": lines}
        if extra:
            body.update(extra)
        return self.request("POST", "/api/orders", body, self.tokens[token], key or f"create-{ref}")

    def test_01_health_auth_roles_seed_and_tenant_isolation(self):
        status, body = self.request("GET", "/api/health")
        self.assertEqual((status, body), (200, {"status": "ok"}))
        self.assertEqual(self.request("POST", "/api/session", {"email": "admin@north.example", "password": "wrong"})[0], 401)
        self.assertEqual(self.request("GET", "/api/me")[0], 401)
        self.assertEqual(self.request("GET", "/api/me", token="not-a-real-token")[0], 401)
        self.assertEqual(self.request("GET", "/api/me", token=self.tokens["viewer"])[1], {"email": "viewer@north.example", "role": "viewer", "tenant": "north"})
        for token in ("admin", "south"):
            status, inventory = self.request("GET", "/api/inventory", token=self.tokens[token])
            self.assertEqual(status, 200)
            self.assertEqual([(x["sku"], x["on_hand"], x["reserved"], x["price_cents"]) for x in inventory["items"]], [
                ("BOLT", 100, 0, 1250), ("CABLE", 60, 0, 2499), ("SAMPLE", 20, 0, 0),
            ])
        status, created = self.create_order("TENANT-ISOLATION", [{"sku": "SAMPLE", "quantity": 1}], extra={"tenant": "south", "role": "admin", "unit_price_cents": 1})
        self.assertEqual(status, 201)
        self.assertEqual(created["lines"][0]["unit_price_cents"], 0)
        self.assertEqual(self.request("GET", f"/api/orders/{created['id']}", token=self.tokens["south"])[0], 404)
        self.assertEqual(self.request("GET", "/api/orders", token=self.tokens["south"], extra_headers={"X-Tenant": "north", "X-Role": "admin"})[1]["items"], [])
        self.assertEqual(self.request("POST", "/api/orders", {"client_ref": "VIEWER-DENIED", "lines": [{"sku": "BOLT", "quantity": 1}]}, self.tokens["viewer"])[0], 403)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {"sku": "SAMPLE", "delta": 1, "expected_version": 1, "reason": "test"}, self.tokens["operator"], "operator-adjust")[0], 403)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {"sku": "SAMPLE", "delta": 1, "expected_version": 1, "reason": "test"}, self.tokens["viewer"], "viewer-adjust")[0], 403)

    def test_02_validation_zero_price_and_server_catalog_snapshot(self):
        cases = [
            ({"client_ref": "EMPTY-LINES", "lines": []}, 400),
            ({"client_ref": "UNKNOWN-SKU", "lines": [{"sku": "NOPE", "quantity": 1}]}, 400),
            ({"client_ref": "DUPLICATE-SKU", "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 1}]}, 400),
            ({"client_ref": "FRACTION", "lines": [{"sku": "BOLT", "quantity": 1.5}]}, 400),
            ({"client_ref": "BOOLEAN", "lines": [{"sku": "BOLT", "quantity": True}]}, 400),
            ({"client_ref": "ZERO-QTY", "lines": [{"sku": "BOLT", "quantity": 0}]}, 400),
        ]
        for body, expected in cases:
            status, _ = self.request("POST", "/api/orders", body, self.tokens["operator"], f"bad-{body['client_ref']}")
            self.assertEqual(status, expected, body)
        status, sample = self.create_order("ZERO-PRICE-SAMPLE", [{"sku": "SAMPLE", "quantity": 3}], extra={"price_cents": 9_999_999})
        self.assertEqual(status, 201)
        self.assertEqual(sample["total_cents"], 0)
        self.assertEqual(sample["lines"], [{"sku": "SAMPLE", "quantity": 3, "unit_price_cents": 0, "returned_quantity": 0}])
        self.assertEqual((sample["status"], sample["version"]), ("draft", 1))
        status, draft = self.create_order("DRAFT-CANCEL", [{"sku": "SAMPLE", "quantity": 1}])
        self.assertEqual(status, 201)
        status, cancelled = self.request("POST", f"/api/orders/{draft['id']}/cancel", {"expected_version": 1}, self.tokens["operator"], "cancel-draft")
        self.assertEqual((status, cancelled["status"], cancelled["version"]), (200, "cancelled", 2))
        self.assertEqual(self.request("POST", f"/api/orders/{draft['id']}/cancel", {"expected_version": 2}, self.tokens["operator"], "cancel-draft-again")[0], 409)
        status, _ = self.request("POST", "/api/orders", {"client_ref": "MISSING-KEY", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, self.tokens["operator"])
        self.assertEqual(status, 400)
        self.assertEqual(self.request("GET", "/api/orders?status=unknown", token=self.tokens["operator"])[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?limit=101", token=self.tokens["operator"])[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?cursor=not-a-cursor", token=self.tokens["operator"])[0], 400)

    def test_03_idempotency_replay_conflict_and_failed_key_retry(self):
        status, body = self.create_order("IDEMPOTENT-CREATE", [{"sku": "SAMPLE", "quantity": 2}], key="persisted-create-key")
        self.assertEqual(status, 201)
        audit_before = self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"]
        replay_status, replay = self.create_order("IDEMPOTENT-CREATE", [{"sku": "SAMPLE", "quantity": 2}], key="persisted-create-key")
        self.assertEqual((replay_status, replay), (201, body))
        audit_after = self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"]
        self.assertEqual(len(audit_after), len(audit_before))
        self.assertEqual(self.request("POST", "/api/orders", {"client_ref": "CHANGED", "lines": [{"sku": "SAMPLE", "quantity": 2}]}, self.tokens["operator"], "persisted-create-key")[0], 409)
        self.assertEqual(self.request("POST", "/api/orders", {"client_ref": "IDEMPOTENT-CREATE", "lines": [{"sku": "SAMPLE", "quantity": 2}]}, self.tokens["operator"], "different-create-key")[0], 409)
        self.assertEqual(self.request("POST", f"/api/orders/{body['id']}/cancel", {"expected_version": 1}, self.tokens["operator"], "persisted-create-key")[0], 409)
        failed_key = "retry-after-validation"
        self.assertEqual(self.request("POST", "/api/orders", {"client_ref": "WILL-RETRY", "lines": [{"sku": "NO-SUCH-SKU", "quantity": 1}]}, self.tokens["operator"], failed_key)[0], 400)
        status, valid = self.request("POST", "/api/orders", {"client_ref": "WILL-RETRY", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, self.tokens["operator"], failed_key)
        self.assertEqual(status, 201)
        self.assertEqual(valid["client_ref"], "WILL-RETRY")
        # Authorization still applies before a successful key can be replayed.
        self.assertEqual(self.request("POST", "/api/orders", {"client_ref": "IDEMPOTENT-CREATE", "lines": [{"sku": "SAMPLE", "quantity": 2}]}, self.tokens["viewer"], "persisted-create-key")[0], 403)
        self.assertEqual(self.request("POST", "/api/orders", {"client_ref": "NO-KEY", "lines": []}, self.tokens["operator"], " ")[0], 400)
        same_key_north = {"client_ref": "SHARED-KEY-NORTH", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        same_key_south = {"client_ref": "SHARED-KEY-SOUTH", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        self.assertEqual(self.request("POST", "/api/orders", same_key_north, self.tokens["operator"], "tenant-scoped-key")[0], 201)
        self.assertEqual(self.request("POST", "/api/orders", same_key_south, self.tokens["south"], "tenant-scoped-key")[0], 201)
        concurrent_body = {"client_ref": "CONCURRENT-IDEMPOTENT", "lines": [{"sku": "SAMPLE", "quantity": 2}]}
        before = len(self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.request("POST", "/api/orders", concurrent_body, self.tokens["operator"], "concurrent-create-key"), range(4)))
        self.assertEqual([status for status, _ in results], [201, 201, 201, 201])
        self.assertTrue(all(response == results[0][1] for _, response in results))
        after = len(self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"])
        self.assertEqual(after, before + 1)

    def test_04_atomic_multi_line_failure_and_concurrent_reservation(self):
        status, atomic = self.create_order("ATOMIC-FAILURE", [{"sku": "CABLE", "quantity": 5}, {"sku": "BOLT", "quantity": 101}])
        self.assertEqual(status, 201)
        before = self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"]
        audit_before = len(self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"])
        status, error = self.request("POST", f"/api/orders/{atomic['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], "atomic-fail-reserve")
        self.assertEqual(status, 409)
        self.assertEqual(error["error"]["code"], "insufficient_stock")
        after = self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"]
        self.assertEqual(after, before)
        self.assertEqual(self.request("GET", f"/api/orders/{atomic['id']}", token=self.tokens["operator"])[1]["version"], 1)
        self.assertEqual(len(self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"]), audit_before)

        status, same_operation = self.create_order("RACE-IDEMPOTENT-RESERVE", [{"sku": "BOLT", "quantity": 10}])
        self.assertEqual(status, 201)
        audit_before_reserve = len(self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"])
        def reserve_same(_):
            return self.request("POST", f"/api/orders/{same_operation['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], "same-reserve-key")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            duplicate_results = list(pool.map(reserve_same, range(2)))
        self.assertEqual([status for status, _ in duplicate_results], [200, 200])
        self.assertEqual(duplicate_results[0][1], duplicate_results[1][1])
        self.assertEqual(len(self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"]), audit_before_reserve + 1)
        bolt_after_replay = next(x for x in self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"] if x["sku"] == "BOLT")
        self.assertEqual(bolt_after_replay["reserved"], 10)
        self.assertEqual(self.request("POST", f"/api/orders/{same_operation['id']}/cancel", {"expected_version": 2}, self.tokens["operator"], "same-reserve-cleanup")[0], 200)

        orders = [self.create_order(f"RACE-{i}", [{"sku": "BOLT", "quantity": 80}])[1] for i in range(2)]
        def reserve(order):
            return self.request("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], f"race-{order['id']}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, orders))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        winner = next(order for order, (status, _) in zip(orders, results) if status == 200)
        loser = next(order for order, (status, _) in zip(orders, results) if status == 409)
        inventory = self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"]
        bolt = next(x for x in inventory if x["sku"] == "BOLT")
        self.assertEqual(bolt["reserved"], 80)
        self.assertEqual(self.request("GET", f"/api/orders/{loser['id']}", token=self.tokens["operator"])[1]["version"], 1)
        status, canceled = self.request("POST", f"/api/orders/{winner['id']}/cancel", {"expected_version": 2}, self.tokens["operator"], "race-cleanup-cancel")
        self.assertEqual((status, canceled["status"]), (200, "cancelled"))
        self.assertEqual(next(x for x in self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"] if x["sku"] == "BOLT")["reserved"], 0)

    def test_05_order_versions_shipping_partial_and_full_return(self):
        status, order = self.create_order("RETURN-FLOW", [{"sku": "CABLE", "quantity": 3}])
        self.assertEqual(status, 201)
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/ship", {"expected_version": 1}, self.tokens["operator"], "ship-draft")[0], 409)
        status, reserved = self.request("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], "reserve-return-flow")
        self.assertEqual((status, reserved["status"], reserved["version"]), (200, "reserved", 2))
        cable = next(x for x in self.request("GET", "/api/inventory", token=self.tokens["admin"])[1]["items"] if x["sku"] == "CABLE")
        self.assertEqual(cable["reserved"], 3)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {"sku": "CABLE", "delta": -58, "expected_version": cable["version"], "reason": "must preserve reservations"}, self.tokens["admin"], "reserved-floor-check")[0], 409)
        status, stale = self.request("POST", f"/api/orders/{order['id']}/ship", {"expected_version": 1}, self.tokens["operator"], "stale-ship")
        self.assertEqual((status, stale["error"]["code"]), (409, "stale_version"))
        status, shipped = self.request("POST", f"/api/orders/{order['id']}/ship", {"expected_version": 2}, self.tokens["operator"], "ship-return-flow")
        self.assertEqual((status, shipped["status"], shipped["version"]), (200, "shipped", 3))
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/cancel", {"expected_version": 3}, self.tokens["operator"], "cancel-shipped")[0], 409)
        for invalid_lines in (
            [{"sku": "CABLE", "quantity": 1}, {"sku": "CABLE", "quantity": 1}],
            [{"sku": "UNKNOWN", "quantity": 1}],
            [{"sku": "CABLE", "quantity": True}],
        ):
            self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 3, "lines": invalid_lines}, self.tokens["operator"], f"invalid-return-{len(str(invalid_lines))}")[0], 400)
        self.assertEqual(self.request("GET", f"/api/orders/{order['id']}", token=self.tokens["operator"])[1]["version"], 3)
        status, partial = self.request("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 3, "lines": [{"sku": "CABLE", "quantity": 1}]}, self.tokens["operator"], "partial-return")
        self.assertEqual((status, partial["status"], partial["version"], partial["lines"][0]["returned_quantity"]), (200, "shipped", 4, 1))
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "CABLE", "quantity": 3}]}, self.tokens["operator"], "too-many-return")[0], 409)
        status, returned = self.request("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "CABLE", "quantity": 2}]}, self.tokens["operator"], "final-return")
        self.assertEqual((status, returned["status"], returned["version"], returned["lines"][0]["returned_quantity"]), (200, "returned", 5, 3))
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/returns", {"expected_version": 5, "lines": [{"sku": "CABLE", "quantity": 1}]}, self.tokens["operator"], "after-full-return")[0], 409)
        cable = next(x for x in self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"] if x["sku"] == "CABLE")
        self.assertEqual((cable["on_hand"], cable["reserved"]), (60, 0))
        dashboard = self.request("GET", "/api/dashboard", token=self.tokens["operator"])[1]
        self.assertGreaterEqual(dashboard["orders_by_status"]["returned"], 1)
        all_inventory = self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"]
        self.assertEqual(dashboard["inventory_units"], sum(item["on_hand"] for item in all_inventory))
        self.assertEqual(dashboard["reserved_units"], sum(item["reserved"] for item in all_inventory))

    def test_06_admin_adjustment_version_reserved_floor_and_idempotent_replay(self):
        admin = self.tokens["admin"]
        body = {"sku": "SAMPLE", "delta": 4, "expected_version": 1, "reason": "Cycle count correction"}
        audit_before = self.request("GET", "/api/audit?limit=100", token=admin)[1]["items"]
        status, adjusted = self.request("POST", "/api/stock/adjustments", body, admin, "adjust-sample-once")
        self.assertEqual((status, adjusted["on_hand"], adjusted["version"]), (200, 24, 2))
        self.assertEqual(self.request("POST", "/api/stock/adjustments", body, admin, "adjust-sample-once"), (status, adjusted))
        audit_after = self.request("GET", "/api/audit?limit=100", token=admin)[1]["items"]
        self.assertEqual(len(audit_after), len(audit_before) + 1)
        self.assertEqual(audit_after[-1]["action"], "stock.adjusted")
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {**body, "expected_version": 2}, admin, "adjust-sample-once")[0], 409)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {**body, "delta": -25, "expected_version": 2}, admin, "below-zero-adjust")[0], 409)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {**body, "delta": True}, admin, "boolean-adjust")[0], 400)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {**body, "delta": 0}, admin, "zero-adjust")[0], 400)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {**body, "sku": "UNKNOWN"}, admin, "unknown-adjust")[0], 400)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", {**body, "expected_version": 1, "delta": 1}, admin, "stale-adjust")[0], 409)

    def test_07_cursor_pages_are_stable_and_filters_are_tenant_local(self):
        refs = [f"page-cursor-{i}" for i in range(5)]
        for ref in refs:
            status, _ = self.create_order(ref, [{"sku": "SAMPLE", "quantity": 1}])
            self.assertEqual(status, 201)
        seen = []
        cursor = None
        while True:
            params = {"limit": "2", "q": "PAGE-CURSOR"}
            if cursor:
                params["cursor"] = cursor
            status, result = self.request("GET", f"/api/orders?{urllib.parse.urlencode(params)}", token=self.tokens["operator"])
            self.assertEqual(status, 200)
            seen.extend(order["client_ref"] for order in result["items"])
            cursor = result["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(seen, refs)
        audit_ids = []
        cursor = None
        while True:
            query = {"limit": "2"}
            if cursor:
                query["cursor"] = cursor
            result = self.request("GET", f"/api/audit?{urllib.parse.urlencode(query)}", token=self.tokens["operator"])[1]
            audit_ids.extend(event["id"] for event in result["items"])
            cursor = result["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(audit_ids, sorted(set(audit_ids)))
        north_page = self.request("GET", "/api/orders?limit=1", token=self.tokens["operator"])[1]
        self.assertIsNotNone(north_page["next_cursor"])
        self.assertEqual(self.request("GET", f"/api/orders?cursor={north_page['next_cursor']}", token=self.tokens["south"])[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?q=does-not-exist", token=self.tokens["operator"])[1], {"items": [], "next_cursor": None})
        self.assertEqual(self.request("GET", "/api/orders?unknown_filter=1", token=self.tokens["operator"])[0], 400)
        self.assertEqual(self.request("GET", "/api/audit?limit=0", token=self.tokens["operator"])[0], 400)

    def test_08_restart_preserves_orders_stock_audit_sessions_and_idempotency(self):
        status, order = self.create_order("DURABLE-ORDER", [{"sku": "BOLT", "quantity": 2}], key="durable-create-key")
        self.assertEqual(status, 201)
        status, reserved = self.request("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], "durable-reserve-key")
        self.assertEqual((status, reserved["version"], reserved["status"]), (200, 2, "reserved"))
        before_audit = self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"]
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", "/api/me", token=self.tokens["operator"])[0], 200)
        self.assertEqual(self.request("GET", f"/api/orders/{order['id']}", token=self.tokens["operator"])[1], reserved)
        self.assertEqual(self.request("GET", "/api/inventory", token=self.tokens["operator"])[1]["items"][0]["reserved"], 2)
        replay_status, replay = self.request("POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], "durable-reserve-key")
        self.assertEqual((replay_status, replay), (200, reserved))
        after_audit = self.request("GET", "/api/audit?limit=100", token=self.tokens["operator"])[1]["items"]
        self.assertEqual(after_audit, before_audit)
        self.assertEqual(self.request("GET", "/api/inventory", token=self.tokens["south"])[1]["items"][0]["reserved"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
