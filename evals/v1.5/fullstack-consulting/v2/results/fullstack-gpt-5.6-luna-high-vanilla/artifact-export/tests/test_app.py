#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import unittest
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 18765
BASE = f"http://127.0.0.1:{PORT}"
DATA = os.path.join(ROOT, ".test-data")

def call(method, path, token=None, body=None, key=None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if token: headers["Authorization"] = "Bearer " + token
    if key: headers["Idempotency-Key"] = key
    if body is not None: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)

def login(email):
    status, body = call("POST", "/api/session", body={"email": email, "password": "DepotDemo!2026"})
    assert status == 200, body
    return body["token"]

class DepotFlowRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(DATA): shutil.rmtree(DATA)
        os.mkdir(DATA)
        env = os.environ.copy(); env.update(PORT=str(PORT), DATA_DIR=DATA, SEED_DEMO="1")
        cls.proc = subprocess.Popen([os.path.join(ROOT, "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                if call("GET", "/api/health")[0] == 200: break
            except Exception: time.sleep(.05)
        else: raise RuntimeError(cls.proc.stdout.read())
        cls.north = login("operator@north.example"); cls.admin = login("admin@north.example"); cls.viewer = login("viewer@north.example"); cls.south = login("operator@south.example")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.wait(timeout=5)
        # Keep the test data until the process has exited; it is safe disposable evidence.
        shutil.rmtree(DATA, ignore_errors=True)

    def post(self, path, body, token=None, key=None):
        return call("POST", path, token or self.north, body, key or uuid.uuid4().hex)

    def test_auth_tenant_and_seed(self):
        self.assertEqual(call("GET", "/api/health"), (200, {"status": "ok"}))
        self.assertEqual(call("GET", "/api/inventory")[0], 401)
        self.assertEqual(call("POST", "/api/session", body={"email": "viewer@north.example", "password": "wrong"})[0], 401)
        status, body = call("GET", "/api/me", self.north); self.assertEqual(status, 200); self.assertEqual(body["tenant"], "north")
        status, body = call("GET", "/api/inventory", self.north); self.assertEqual(status, 200); self.assertEqual([x["on_hand"] for x in body["items"]], [100, 60, 20])
        self.assertEqual(call("GET", "/api/inventory", self.south)[1]["items"][0]["on_hand"], 100)
        south_order_status, south_order = self.post("/api/orders", {"client_ref": "south-only", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, self.south)
        self.assertEqual(south_order_status, 201)
        self.assertEqual(call("GET", "/api/orders/" + south_order["id"], self.north)[0], 404)
        self.assertEqual(self.post("/api/orders", {"client_ref": "viewer-denied", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, self.viewer)[0], 403)
        self.assertEqual(call("POST", "/api/orders", self.north, {"client_ref": "no-key", "lines": [{"sku": "SAMPLE", "quantity": 1}]})[0], 400)

    def test_validation_zero_price_and_idempotency(self):
        self.assertEqual(self.post("/api/orders", {"client_ref": "bad", "lines": [{"sku": "SAMPLE", "quantity": 0}]})[0], 400)
        payload = {"client_ref": "zero-sample", "lines": [{"sku": "SAMPLE", "quantity": 2}], "total_cents": 999999}
        first = self.post("/api/orders", payload, key="create-zero")
        replay = self.post("/api/orders", payload, key="create-zero")
        self.assertEqual(first[0], 201); self.assertEqual(replay, first); self.assertEqual(first[1]["total_cents"], 0)
        self.assertEqual(self.post("/api/orders", {"client_ref": "other", "lines": [{"sku": "SAMPLE", "quantity": 2}]}, key="create-zero")[0], 409)
        self.assertEqual(self.post("/api/orders", {"client_ref": "zero-sample", "lines": [{"sku": "SAMPLE", "quantity": 1}]})[0], 409)

    def test_atomic_reservation_concurrency_and_stale(self):
        bad = self.post("/api/orders", {"client_ref": "atomic-fail", "lines": [{"sku": "BOLT", "quantity": 99}, {"sku": "CABLE", "quantity": 100}]})[1]
        before = call("GET", "/api/inventory", self.north)[1]
        self.assertEqual(self.post(f"/api/orders/{bad['id']}/reserve", {"expected_version": 1})[0], 409)
        after = call("GET", "/api/inventory", self.north)[1]; self.assertEqual(before, after)
        a = self.post("/api/orders", {"client_ref": "race-a", "lines": [{"sku": "BOLT", "quantity": 60}]})[1]
        b = self.post("/api/orders", {"client_ref": "race-b", "lines": [{"sku": "BOLT", "quantity": 60}]})[1]
        results = []
        def reserve(order): results.append(self.post(f"/api/orders/{order['id']}/reserve", {"expected_version": 1})[0])
        t1, t2 = threading.Thread(target=reserve, args=(a,)), threading.Thread(target=reserve, args=(b,)); t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(self.post(f"/api/orders/{a['id']}/reserve", {"expected_version": 1})[0], 409)

    def test_workflow_stock_returns_audit_and_pagination(self):
        order = self.post("/api/orders", {"client_ref": "round-trip", "lines": [{"sku": "CABLE", "quantity": 2}, {"sku": "SAMPLE", "quantity": 2}]})[1]
        status, order = self.post(f"/api/orders/{order['id']}/reserve", {"expected_version": 1}); self.assertEqual(status, 200)
        status, order = self.post(f"/api/orders/{order['id']}/ship", {"expected_version": 2}); self.assertEqual(status, 200); self.assertEqual(order["status"], "shipped")
        inv = call("GET", "/api/inventory", self.north)[1]["items"]; cable = next(x for x in inv if x["sku"] == "CABLE"); self.assertEqual((cable["on_hand"], cable["reserved"], cable["available"]), (58, 0, 58))
        status, order = self.post(f"/api/orders/{order['id']}/returns", {"expected_version": 3, "lines": [{"sku": "CABLE", "quantity": 1}]}); self.assertEqual(status, 200); self.assertEqual(order["status"], "shipped")
        status, order = self.post(f"/api/orders/{order['id']}/returns", {"expected_version": 4, "lines": [{"sku": "CABLE", "quantity": 1}, {"sku": "SAMPLE", "quantity": 2}]}); self.assertEqual(status, 200); self.assertEqual(order["status"], "returned")
        self.assertEqual(self.post(f"/api/orders/{order['id']}/returns", {"expected_version": 5, "lines": [{"sku": "CABLE", "quantity": 1}]} )[0], 409)
        bolt = next(x for x in call("GET", "/api/inventory", self.north)[1]["items"] if x["sku"] == "BOLT")
        self.assertEqual(self.post("/api/stock/adjustments", {"sku": "BOLT", "delta": 5, "expected_version": bolt["version"], "reason": "cycle count"}, self.admin)[0], 200)
        self.assertEqual(self.post("/api/stock/adjustments", {"sku": "BOLT", "delta": 5, "expected_version": bolt["version"], "reason": "stale"}, self.admin)[0], 409)
        audit = call("GET", "/api/audit?limit=2", self.north)[1]; self.assertEqual(len(audit["items"]), 2); self.assertIsNotNone(audit["next_cursor"])
        audit2 = call("GET", "/api/audit?limit=100&cursor=" + audit["next_cursor"], self.north)[1]; self.assertTrue(audit2["items"])
        self.assertEqual(call("GET", "/api/orders/does-not-exist", self.south)[0], 404)

    def test_durable_restart(self):
        before = call("GET", "/api/inventory", self.north)[1]
        self.proc.terminate(); self.proc.wait(timeout=5)
        env = os.environ.copy(); env.update(PORT=str(PORT), DATA_DIR=DATA, SEED_DEMO="1")
        self.__class__.proc = subprocess.Popen([os.path.join(ROOT, "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                if call("GET", "/api/health")[0] == 200: break
            except Exception: time.sleep(.05)
        after = call("GET", "/api/inventory", self.north)[1]
        self.assertEqual(before, after)
        self.assertEqual(call("GET", "/api/me", self.north)[0], 200)

if __name__ == "__main__": unittest.main(verbosity=2)
