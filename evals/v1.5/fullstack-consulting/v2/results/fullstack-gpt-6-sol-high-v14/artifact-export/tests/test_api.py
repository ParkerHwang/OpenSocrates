import concurrent.futures
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "DepotDemo!2026"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class DepotApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT)
        cls.port = free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.start()

    @classmethod
    def start(cls):
        env = os.environ.copy()
        env.update({"PORT": str(cls.port), "DATA_DIR": cls.temp.name, "SEED_DEMO": "1"})
        cls.process = subprocess.Popen([str(ROOT / "run.sh")], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                with urllib.request.urlopen(cls.base + "/api/health", timeout=0.2) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.05)
        raise AssertionError("server did not start")

    @classmethod
    def stop(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.process.stderr.close()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.temp.cleanup()

    def request(self, method, path, token=None, body=None, key=None):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
            if key is not None:
                headers["Idempotency-Key"] = key
        request = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def login(self, email):
        status, data = self.request("POST", "/api/session", body={"email": email, "password": PASSWORD})
        self.assertEqual(status, 200)
        return data["token"]

    def test_workflow_and_integrity(self):
        north = self.login("operator@north.example")
        south = self.login("operator@south.example")
        admin = self.login("admin@north.example")
        viewer = self.login("viewer@north.example")
        self.assertEqual(self.request("GET", "/api/me")[0], 401)
        self.assertEqual(self.request("GET", "/api/me", "bad")[0], 401)
        self.assertEqual(self.request("POST", "/api/session", body={"email": "operator@north.example", "password": "bad"})[0], 401)
        self.assertEqual(self.request("GET", "/api/me", north)[1], {"email": "operator@north.example", "tenant": "north", "role": "operator"})
        self.assertEqual(self.request("GET", "/api/inventory", north)[1]["items"][0]["on_hand"], 100)
        self.assertEqual(self.request("GET", "/api/inventory", south)[1]["items"][0]["on_hand"], 100)

        create = {"client_ref": "alpha", "lines": [{"sku": "BOLT", "quantity": 3}, {"sku": "CABLE", "quantity": 2}], "tenant": "south", "role": "admin", "total_cents": 1}
        status, order = self.request("POST", "/api/orders", north, create, "create-alpha")
        self.assertEqual(status, 201)
        self.assertEqual(order["total_cents"], 3 * 1250 + 2 * 2499)
        self.assertEqual(order["version"], 1)
        self.assertEqual(self.request("GET", f"/api/orders/{order['id']}", south)[0], 404)
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/reserve", south, {"expected_version": 1}, "other-tenant")[0], 404)
        self.assertEqual(self.request("POST", "/api/orders", viewer, create, "viewer-write")[0], 403)
        self.assertEqual(self.request("POST", "/api/stock/adjustments", north, {"sku": "BOLT", "delta": 1, "expected_version": 1, "reason": "test"}, "operator-write")[0], 403)
        self.assertEqual(self.request("POST", "/api/orders", north, create)[0], 400)
        self.assertEqual(self.request("POST", "/api/orders", north, create, "create-alpha"), (201, order))
        self.assertEqual(self.request("POST", "/api/orders", north, {**create, "client_ref": "changed"}, "create-alpha")[0], 409)
        self.assertEqual(self.request("POST", "/api/orders", north, {**create, "lines": [{"sku": "BOLT", "quantity": 1}]}, "new-key")[0], 409)

        for index, lines in enumerate([[], [{"sku": "BOLT", "quantity": 0}], [{"sku": "BOLT", "quantity": True}], [{"sku": "BOLT", "quantity": 1.5}], [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 2}], [{"sku": "UNKNOWN", "quantity": 1}]]):
            self.assertEqual(self.request("POST", "/api/orders", north, {"client_ref": f"invalid-{index}", "lines": lines}, f"invalid-{index}")[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?status=broken", north)[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?limit=0", north)[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?cursor=garbage", north)[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?q=no-such-order", north)[1]["items"], [])

        status, reserved = self.request("POST", f"/api/orders/{order['id']}/reserve", north, {"expected_version": 1}, "reserve-alpha")
        self.assertEqual((status, reserved["status"], reserved["version"]), (200, "reserved", 2))
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/reserve", north, {"expected_version": 1}, "reserve-alpha"), (200, reserved))
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/ship", north, {"expected_version": 1}, "stale")[0], 409)
        stock = {x["sku"]: x for x in self.request("GET", "/api/inventory", north)[1]["items"]}
        self.assertEqual((stock["BOLT"]["on_hand"], stock["BOLT"]["reserved"], stock["BOLT"]["available"]), (100, 3, 97))
        self.assertEqual(self.request("POST", "/api/stock/adjustments", admin, {"sku": "BOLT", "delta": -98, "expected_version": 2, "reason": "too much"}, "bad-adjust")[0], 409)
        status, adjusted = self.request("POST", "/api/stock/adjustments", admin, {"sku": "BOLT", "delta": 5, "expected_version": 2, "reason": "counted"}, "bad-adjust")
        self.assertEqual((status, adjusted["on_hand"], adjusted["version"]), (200, 105, 3))
        self.assertEqual(self.request("POST", "/api/stock/adjustments", admin, {"sku": "BOLT", "delta": 5, "expected_version": 2, "reason": "counted"}, "bad-adjust"), (200, adjusted))
        self.assertEqual(self.request("POST", "/api/stock/adjustments", admin, {"sku": "BOLT", "delta": 1, "expected_version": 2, "reason": "stale"}, "stale-stock")[0], 409)
        status, shipped = self.request("POST", f"/api/orders/{order['id']}/ship", north, {"expected_version": 2}, "ship-alpha")
        self.assertEqual((status, shipped["status"], shipped["version"]), (200, "shipped", 3))
        stock = {x["sku"]: x for x in self.request("GET", "/api/inventory", north)[1]["items"]}
        self.assertEqual((stock["BOLT"]["on_hand"], stock["BOLT"]["reserved"], stock["BOLT"]["available"]), (102, 0, 102))
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/cancel", north, {"expected_version": 3}, "cancel-shipped")[0], 409)
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/returns", north, {"expected_version": 3, "lines": [{"sku": "CABLE", "quantity": 3}]}, "too-many")[0], 409)
        status, partial = self.request("POST", f"/api/orders/{order['id']}/returns", north, {"expected_version": 3, "lines": [{"sku": "BOLT", "quantity": 1}]}, "partial")
        self.assertEqual((status, partial["status"], partial["version"], partial["lines"][0]["returned_quantity"]), (200, "shipped", 4, 1))
        status, complete = self.request("POST", f"/api/orders/{order['id']}/returns", north, {"expected_version": 4, "lines": [{"sku": "BOLT", "quantity": 2}, {"sku": "CABLE", "quantity": 2}]}, "complete")
        self.assertEqual((status, complete["status"], complete["version"]), (200, "returned", 5))
        self.assertEqual(self.request("POST", f"/api/orders/{order['id']}/returns", north, {"expected_version": 5, "lines": [{"sku": "BOLT", "quantity": 1}]}, "late-return")[0], 409)

        status, free = self.request("POST", "/api/orders", north, {"client_ref": "free", "lines": [{"sku": "SAMPLE", "quantity": 1}]}, "free")
        self.assertEqual((status, free["total_cents"]), (201, 0))
        status, cancelled = self.request("POST", f"/api/orders/{free['id']}/cancel", north, {"expected_version": 1}, "cancel-free")
        self.assertEqual((status, cancelled["status"]), (200, "cancelled"))
        self.assertEqual(self.request("GET", "/api/dashboard", north)[1]["orders_by_status"], {"cancelled": 1, "returned": 1})
        self.assertEqual(len(self.request("GET", "/api/audit", north)[1]["items"]), 8)
        self.assertEqual(self.request("GET", "/api/audit", south)[1]["items"], [])

        first_page = self.request("GET", "/api/orders?limit=1", north)[1]
        late = self.request("POST", "/api/orders", north, {"client_ref": "late", "lines": [{"sku": "BOLT", "quantity": 1}]}, "late-create")[1]
        second_page = self.request("GET", "/api/orders?limit=1&cursor=" + first_page["next_cursor"], north)[1]
        self.assertEqual([first_page["items"][0]["id"], second_page["items"][0]["id"]], [order["id"], free["id"]])
        self.assertIsNone(second_page["next_cursor"])
        self.assertNotIn(late["id"], [first_page["items"][0]["id"], second_page["items"][0]["id"]])
        self.assertEqual(self.request("GET", "/api/orders?status=draft&limit=1&cursor=" + first_page["next_cursor"], north)[0], 400)
        self.assertEqual(len(self.request("GET", "/api/audit?limit=1", north)[1]["items"]), 1)

        # Two independent drafts contend for the same remaining SAMPLE units.
        ids = []
        for n in ("race-a", "race-b"):
            ids.append(self.request("POST", "/api/orders", south, {"client_ref": n, "lines": [{"sku": "SAMPLE", "quantity": 15}]}, n)[1]["id"])
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pair: self.request("POST", f"/api/orders/{pair[0]}/reserve", south, {"expected_version": 1}, pair[1]), zip(ids, ("race-reserve-a", "race-reserve-b"))))
        self.assertEqual(sorted(result[0] for result in results), [200, 409])
        self.assertEqual(next(x for x in self.request("GET", "/api/inventory", south)[1]["items"] if x["sku"] == "SAMPLE")["reserved"], 15)
        # Two exact retries of one create must have one order and one event.
        retry_body = {"client_ref": "same-concurrent", "lines": [{"sku": "BOLT", "quantity": 1}]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            retries = list(pool.map(lambda _: self.request("POST", "/api/orders", south, retry_body, "same-create"), range(2)))
        self.assertEqual(retries[0], retries[1])
        self.assertEqual(retries[0][0], 201)
        self.assertEqual(len(self.request("GET", "/api/orders?q=same-concurrent", south)[1]["items"]), 1)
        draft_page = self.request("GET", "/api/orders?status=draft&limit=1", south)[1]
        self.assertIsNotNone(draft_page["next_cursor"])
        self.assertEqual(self.request("POST", f"/api/orders/{retries[0][1]['id']}/cancel", south, {"expected_version": 1}, "cancel-after-snapshot")[0], 200)
        frozen_page = self.request("GET", "/api/orders?status=draft&limit=1&cursor=" + draft_page["next_cursor"], south)[1]
        self.assertEqual(frozen_page["items"][0]["id"], retries[0][1]["id"])
        self.assertEqual(frozen_page["items"][0]["status"], "cancelled")
        self.assertEqual(len(self.request("GET", "/api/audit", south)[1]["items"]), 5)

        # Multi-line reserve fails atomically and does not consume the retry key.
        failing = self.request("POST", "/api/orders", south, {"client_ref": "atomic", "lines": [{"sku": "BOLT", "quantity": 1}, {"sku": "SAMPLE", "quantity": 10}]}, "atomic-create")[1]
        before = self.request("GET", "/api/inventory", south)[1]
        events_before = len(self.request("GET", "/api/audit", south)[1]["items"])
        self.assertEqual(self.request("POST", f"/api/orders/{failing['id']}/reserve", south, {"expected_version": 1}, "atomic-reserve")[0], 409)
        self.assertEqual(self.request("GET", "/api/inventory", south)[1], before)
        self.assertEqual(self.request("GET", f"/api/orders/{failing['id']}", south)[1]["version"], 1)
        self.assertEqual(len(self.request("GET", "/api/audit", south)[1]["items"]), events_before)
        self.assertEqual(self.request("POST", f"/api/orders/{failing['id']}/reserve", south, {"expected_version": 1}, "atomic-reserve")[0], 409)

        # A fresh process sees the same data and replays the original successful body.
        self.stop()
        self.start()
        self.assertEqual(self.request("GET", f"/api/orders/{order['id']}", north)[1], complete)
        self.assertEqual(self.request("POST", "/api/orders", north, create, "create-alpha"), (201, order))
        self.assertEqual(self.request("POST", "/api/orders", south, retry_body, "same-create"), retries[0])
        self.assertEqual(next(x for x in self.request("GET", "/api/inventory", north)[1]["items"] if x["sku"] == "BOLT")["on_hand"], 105)
        self.assertEqual(len(self.request("GET", "/api/audit", north)[1]["items"]), 9)


if __name__ == "__main__":
    unittest.main()
