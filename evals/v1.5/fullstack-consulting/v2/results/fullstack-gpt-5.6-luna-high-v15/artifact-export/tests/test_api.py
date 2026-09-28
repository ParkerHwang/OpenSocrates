#!/usr/bin/env python3
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close(); return port


class DepotFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tempfile.mkdtemp(prefix="depotflow-test-")
        cls.port = free_port()
        env = os.environ.copy(); env.update(DATA_DIR=cls.data, PORT=str(cls.port), SEED_DEMO="1")
        cls.proc = subprocess.Popen([os.path.join(ROOT, "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(80):
            try:
                if cls.raw("GET", "/api/health")[0] == 200: break
            except Exception: time.sleep(.05)
        else: raise RuntimeError("server did not start")
        cls.north = cls.login("admin@north.example")
        cls.south = cls.login("admin@south.example")
        cls.viewer = cls.login("viewer@north.example")
        cls.operator = cls.login("operator@north.example")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.wait(timeout=5); shutil.rmtree(cls.data, ignore_errors=True)

    @classmethod
    def raw(cls, method, path, body=None, token=None, key=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (cls.port, path), method=method)
        if body is not None:
            req.data = json.dumps(body).encode(); req.add_header("Content-Type", "application/json")
        if token: req.add_header("Authorization", "Bearer " + token)
        if key: req.add_header("Idempotency-Key", key)
        try:
            with urllib.request.urlopen(req, timeout=10) as response: return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error: return error.code, json.loads(error.read())

    @classmethod
    def login(cls, email):
        status, data = cls.raw("POST", "/api/session", {"email": email, "password": "DepotDemo!2026"})
        assert status == 200, data
        return data["token"]

    def get(self, path, token=None): return self.raw("GET", path, token=token or self.north)
    def post(self, path, body, token=None, key=None): return self.raw("POST", path, body, token or self.north, key)

    def test_health_auth_and_tenant_isolation(self):
        self.assertEqual(self.raw("GET", "/api/health"), (200, {"status": "ok"}))
        self.assertEqual(self.raw("GET", "/api/inventory")[0], 401)
        self.assertEqual(self.get("/api/inventory")[0], 200)
        status, data = self.post("/api/orders", {"client_ref": "north-secret", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, key="iso-order")
        self.assertEqual(status, 201)
        self.assertEqual(self.get("/api/orders/" + data["id"], self.south)[0], 404)

    def test_viewer_and_validation(self):
        status, data = self.post("/api/orders", {"client_ref": "viewer-no", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, self.viewer, "viewer-key")
        self.assertEqual(status, 403); self.assertEqual(data["error"]["code"], "forbidden")
        self.assertEqual(self.post("/api/orders", {"client_ref": "bad", "lines": []}, key="bad-key")[0], 400)
        self.assertEqual(self.post("/api/orders", {"client_ref": "bad2", "lines": [{"sku": "NOPE", "quantity": 1}]}, key="bad2-key")[0], 400)
        self.assertEqual(self.post("/api/orders", {"client_ref": "bad3", "lines": [{"sku": "SAMPLE", "quantity": True}]}, key="bad3-key")[0], 400)
        status, _ = self.post("/api/orders", {"client_ref": "missing-key", "lines": [{"sku": "SAMPLE", "quantity": 1}]})
        self.assertEqual(status, 400)

    def test_order_idempotency_and_zero_price(self):
        body = {"client_ref": "sample-free", "lines": [{"sku": "SAMPLE", "quantity": 2}]}
        before_audit = len(self.get("/api/audit")[1]["items"])
        status, first = self.post("/api/orders", body, key="same-order")
        self.assertEqual(status, 201); self.assertEqual(first["total_cents"], 0); self.assertEqual(first["lines"][0]["unit_price_cents"], 0)
        self.__class__.replay_body = body
        self.__class__.replay_order = first
        status, replay = self.post("/api/orders", body, key="same-order")
        self.assertEqual((status, replay), (201, first))
        status, conflict = self.post("/api/orders", {"client_ref": "different", "lines": body["lines"]}, key="same-order")
        self.assertEqual(status, 409); self.assertEqual(conflict["error"]["code"], "idempotency_conflict")
        self.assertEqual(len(self.get("/api/audit")[1]["items"]), before_audit + 1)

    def test_atomic_reserve_and_concurrent_reservation(self):
        before = self.get("/api/inventory")[1]["items"]
        status, failed = self.post("/api/orders", {"client_ref": "atomic-fail", "lines": [{"sku": "BOLT", "quantity": 1000}, {"sku": "CABLE", "quantity": 1}]}, key="atomic-create")
        self.assertEqual(status, 201)
        status, _ = self.post("/api/orders/%s/reserve" % failed["id"], {"expected_version": 1}, key="atomic-reserve")
        self.assertEqual(status, 409)
        self.assertEqual(self.get("/api/inventory")[1]["items"], before)
        orders = []
        for n in range(2):
            status, order = self.post("/api/orders", {"client_ref": "race-%d" % n, "lines": [{"sku": "BOLT", "quantity": 60}]}, key="race-create-%d" % n)
            self.assertEqual(status, 201); orders.append(order)
        def reserve(order): return self.post("/api/orders/%s/reserve" % order["id"], {"expected_version": 1}, key="race-reserve-" + order["id"])[0]
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(reserve, orders))
        self.assertEqual(sorted(outcomes), [200, 409])

    def test_transitions_returns_stale_and_audit(self):
        status, order = self.post("/api/orders", {"client_ref": "return-flow", "lines": [{"sku": "BOLT", "quantity": 2}, {"sku": "CABLE", "quantity": 1}]}, key="return-create")
        self.assertEqual(status, 201)
        oid = order["id"]
        self.assertEqual(self.post(f"/api/orders/{oid}/reserve", {"expected_version": 99}, key="stale-reserve")[0], 409)
        self.assertEqual(self.post(f"/api/orders/{oid}/reserve", {"expected_version": 1}, key="return-reserve")[0], 200)
        self.assertEqual(self.post(f"/api/orders/{oid}/ship", {"expected_version": 2}, key="return-ship")[0], 200)
        status, partial = self.post(f"/api/orders/{oid}/returns", {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}, key="return-partial")
        self.assertEqual(status, 200); self.assertEqual(partial["status"], "shipped")
        status, complete = self.post(f"/api/orders/{oid}/returns", {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "CABLE", "quantity": 1}]}, key="return-full")
        self.assertEqual(status, 200); self.assertEqual(complete["status"], "returned")
        self.assertEqual(self.post(f"/api/orders/{oid}/returns", {"expected_version": 5, "lines": [{"sku": "BOLT", "quantity": 1}]}, key="return-again")[0], 409)
        status, _ = self.post("/api/stock/adjustments", {"sku": "SAMPLE", "delta": 1, "expected_version": 1, "reason": "cycle count"}, key="stock-one")
        self.assertEqual(status, 200)
        self.assertEqual(self.post("/api/stock/adjustments", {"sku": "SAMPLE", "delta": 1, "expected_version": 1, "reason": "stale"}, key="stock-stale")[0], 409)

    def test_pagination_and_restart_durability(self):
        sample_before = next(i for i in self.get("/api/inventory")[1]["items"] if i["sku"] == "SAMPLE")
        status, data = self.get("/api/orders?limit=1")
        self.assertEqual(status, 200)
        if data["next_cursor"]:
            status2, data2 = self.get("/api/orders?limit=100&cursor=" + data["next_cursor"])
            self.assertEqual(status2, 200)
            self.assertTrue({x["id"] for x in data["items"]}.isdisjoint({x["id"] for x in data2["items"]}))
        self.assertEqual(self.get("/api/orders?limit=0")[0], 400)
        self.proc.terminate(); self.proc.wait(timeout=5)
        env = os.environ.copy(); env.update(DATA_DIR=self.data, PORT=str(self.port), SEED_DEMO="1")
        self.__class__.proc = subprocess.Popen([os.path.join(ROOT, "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(80):
            try:
                if self.raw("GET", "/api/health")[0] == 200: break
            except Exception: time.sleep(.05)
        self.assertGreater(len(self.get("/api/orders")[1]["items"]), 0)
        status, replay = self.post("/api/orders", self.replay_body, key="same-order")
        self.assertEqual((status, replay), (201, self.replay_order))
        sample = next(i for i in self.get("/api/inventory")[1]["items"] if i["sku"] == "SAMPLE")
        self.assertEqual(sample, sample_before)


if __name__ == "__main__": unittest.main(verbosity=2)
