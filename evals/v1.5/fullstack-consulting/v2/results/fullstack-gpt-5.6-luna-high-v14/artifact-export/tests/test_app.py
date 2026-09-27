#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "DepotDemo!2026"


def request(base, method, path, payload=None, token=None, idem=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idem:
        headers["Idempotency-Key"] = idem
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class DepotFlowRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory(prefix=".depotflow-test-", dir=ROOT)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        env = {**os.environ, "PORT": str(cls.port), "DATA_DIR": cls.tempdir.name, "SEED_DEMO": "1"}
        cls.proc = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        cls.base = f"http://127.0.0.1:{cls.port}"
        for _ in range(100):
            try:
                if request(cls.base, "GET", "/api/health")[0] == 200:
                    break
            except Exception:
                time.sleep(.05)
        else:
            raise RuntimeError("server did not start")
        cls.tokens = {}
        for role in ("admin", "operator", "viewer"):
            status, data = request(cls.base, "POST", "/api/session", {"email": f"{role}@north.example", "password": PASSWORD})
            assert status == 200
            cls.tokens[role] = data["token"]
        status, data = request(cls.base, "POST", "/api/session", {"email": "operator@south.example", "password": PASSWORD})
        assert status == 200
        cls.tokens["south"] = data["token"]

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tempdir.cleanup()

    def test_health_auth_and_isolation(self):
        self.assertEqual(request(self.base, "GET", "/api/health"), (200, {"status": "ok"}))
        self.assertEqual(request(self.base, "GET", "/api/inventory")[0], 401)
        self.assertEqual(request(self.base, "POST", "/api/session", {"email": "admin@north.example", "password": "bad"})[0], 401)
        self.assertEqual(request(self.base, "GET", "/api/me", token=self.tokens["admin"])[1]["tenant"], "north")
        status, south_orders = request(self.base, "GET", "/api/orders", token=self.tokens["south"])
        self.assertEqual((status, south_orders["items"]), (200, []))

    def test_viewer_and_idempotent_create(self):
        body = {"client_ref": "viewer-nope", "lines": [{"sku": "SAMPLE", "quantity": 1}]}
        self.assertEqual(request(self.base, "POST", "/api/orders", body, self.tokens["viewer"], "viewer-key")[0], 403)
        body = {"client_ref": "zero-price", "lines": [{"sku": "SAMPLE", "quantity": 2}], "total_cents": 999999}
        status, first = request(self.base, "POST", "/api/orders", body, self.tokens["operator"], "create-zero")
        self.assertEqual(status, 201)
        self.assertEqual(first["total_cents"], 0)
        status, replay = request(self.base, "POST", "/api/orders", body, self.tokens["operator"], "create-zero")
        self.assertEqual((status, replay), (201, first))
        self.assertEqual(request(self.base, "POST", "/api/orders", {"client_ref": "other", "lines": body["lines"]}, self.tokens["operator"], "create-zero")[0], 409)
        self.assertEqual(request(self.base, "GET", f"/api/orders/{first['id']}", token=self.tokens["south"])[0], 404)
        status, audit = request(self.base, "GET", "/api/audit", token=self.tokens["operator"])
        self.assertEqual(status, 200)
        self.assertEqual(sum(item["action"] == "order_created" and item["entity_id"] == first["id"] for item in audit["items"]), 1)

    def test_atomic_reservation_stale_and_returns(self):
        def create(ref, lines, key):
            status, data = request(self.base, "POST", "/api/orders", {"client_ref": ref, "lines": lines}, self.tokens["operator"], key)
            self.assertEqual(status, 201)
            return data
        failed = create("atomic-fail", [{"sku": "BOLT", "quantity": 1}, {"sku": "CABLE", "quantity": 1000}], "atomic-create")
        status, result = request(self.base, "POST", f"/api/orders/{failed['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], "atomic-reserve")
        self.assertEqual(status, 409)
        status, inventory = request(self.base, "GET", "/api/inventory", token=self.tokens["operator"])
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        self.assertEqual(bolt["reserved"], 0)
        order = create("returnable", [{"sku": "BOLT", "quantity": 2}], "returnable-create")
        status, order = request(self.base, f"POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], "returnable-reserve")
        self.assertEqual(status, 200)
        status, order = request(self.base, "POST", f"/api/orders/{order['id']}/ship", {"expected_version": 2}, self.tokens["operator"], "returnable-ship")
        self.assertEqual((status, order["status"]), (200, "shipped"))
        status, partial = request(self.base, "POST", f"/api/orders/{order['id']}/returns", {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}, self.tokens["operator"], "returnable-partial")
        self.assertEqual((status, partial["status"], partial["lines"][0]["returned_quantity"]), (200, "shipped", 1))
        self.assertEqual(request(self.base, "POST", f"/api/orders/{order['id']}/returns", {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}, self.tokens["operator"], "stale-return")[0], 409)
        status, full = request(self.base, "POST", f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 1}]}, self.tokens["operator"], "returnable-full")
        self.assertEqual((status, full["status"]), (200, "returned"))

    def test_concurrent_reservation_never_oversells(self):
        orders = []
        for n in range(2):
            status, order = request(self.base, "POST", "/api/orders", {"client_ref": f"race-{n}", "lines": [{"sku": "CABLE", "quantity": 40}]}, self.tokens["operator"], f"race-create-{n}")
            self.assertEqual(status, 201)
            orders.append(order)
        def reserve(order):
            return request(self.base, "POST", f"/api/orders/{order['id']}/reserve", {"expected_version": 1}, self.tokens["operator"], f"race-reserve-{order['id']}")[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(reserve, orders))
        self.assertEqual(sorted(statuses), [200, 409])
        status, inventory = request(self.base, "GET", "/api/inventory", token=self.tokens["operator"])
        cable = next(item for item in inventory["items"] if item["sku"] == "CABLE")
        self.assertLessEqual(cable["reserved"], cable["on_hand"])

    def test_stock_validation_pagination_and_restart(self):
        status, inventory = request(self.base, "GET", "/api/inventory", token=self.tokens["admin"])
        bolt = next(item for item in inventory["items"] if item["sku"] == "BOLT")
        self.assertEqual(request(self.base, "POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 3, "expected_version": bolt["version"], "reason": "cycle count"}, self.tokens["admin"], "adjust-bolt")[0], 200)
        self.assertEqual(request(self.base, "POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": 3, "expected_version": bolt["version"], "reason": "cycle count"}, self.tokens["admin"], "adjust-bolt")[0], 200)
        self.assertEqual(request(self.base, "POST", "/api/stock/adjustments", {"sku": "BOLT", "delta": -1, "expected_version": bolt["version"], "reason": "stale"}, self.tokens["admin"], "stale-stock")[0], 409)
        self.assertEqual(request(self.base, "GET", "/api/orders?limit=0", token=self.tokens["operator"])[0], 400)
        self.assertEqual(request(self.base, "GET", "/api/orders?status=nope", token=self.tokens["operator"])[0], 400)
        self.assertEqual(request(self.base, "GET", "/api/orders?cursor=bad", token=self.tokens["operator"])[0], 400)
        self.assertEqual(request(self.base, "GET", "/api/orders?limit=1", token=self.tokens["operator"])[0], 200)

    def test_zz_durable_restart(self):
        self.proc.terminate()
        self.proc.wait(timeout=5)
        env = {**os.environ, "PORT": str(self.port), "DATA_DIR": self.tempdir.name, "SEED_DEMO": "1"}
        self.__class__.proc = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        for _ in range(100):
            try:
                if request(self.base, "GET", "/api/health")[0] == 200:
                    break
            except Exception:
                time.sleep(.05)
        status, session = request(self.base, "POST", "/api/session", {"email": "operator@north.example", "password": PASSWORD})
        self.assertEqual(status, 200)
        token = session["token"]
        status, orders = request(self.base, "GET", "/api/orders?q=zero-price", token=token)
        self.assertEqual((status, len(orders["items"])), (200, 1))
        status, audit = request(self.base, "GET", "/api/audit?limit=100", token=token)
        self.assertEqual(status, 200)
        self.assertTrue(any(item["action"] == "stock_adjusted" for item in audit["items"]))


if __name__ == "__main__":
    unittest.main()
