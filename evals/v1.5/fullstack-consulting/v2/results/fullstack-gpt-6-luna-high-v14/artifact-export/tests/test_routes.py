import concurrent.futures
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DepotRoutes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); self.port = s.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.start()
        self.tokens = {role: self.login(f"{role}@north.example")["token"] for role in ("admin", "operator", "viewer")}
        self.south = self.login("operator@south.example")["token"]

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def start(self):
        env = os.environ.copy(); env.update(PORT=str(self.port), DATA_DIR=self.temp.name, SEED_DEMO="1", QUIET="1")
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "server.py")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                if self.request("GET", "/api/health")[0] == 200: return
            except Exception: time.sleep(.05)
        raise RuntimeError("server did not start: " + str(self.proc.stderr.read()))

    def stop(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            self.proc.terminate(); self.proc.wait(timeout=5)
        if getattr(self, "proc", None):
            if self.proc.stdout: self.proc.stdout.close()
            if self.proc.stderr: self.proc.stderr.close()

    def request(self, method, path, body=None, token=None, key=None):
        headers = {}
        if body is not None: headers["Content-Type"] = "application/json"
        if token: headers["Authorization"] = "Bearer " + token
        if key is not None: headers["Idempotency-Key"] = key
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read())

    def login(self, email):
        code, data = self.request("POST", "/api/session", {"email": email, "password": "DepotDemo!2026"})
        self.assertEqual(code, 200)
        return data

    def post(self, path, body, token=None, key=None):
        return self.request("POST", path, body, token or self.tokens["operator"], key or f"test-{time.time_ns()}")

    def order(self, ref, lines):
        status, data = self.post("/api/orders", {"client_ref": ref, "lines": lines})
        self.assertEqual(status, 201, data)
        return data

    def test_tenant_roles_validation_and_zero_price(self):
        code, me = self.request("GET", "/api/me", token=self.tokens["admin"])
        self.assertEqual((code, me["tenant"], me["role"]), (200, "north", "admin"))
        self.assertEqual(self.request("GET", "/api/inventory", token=self.south)[1]["items"][0]["on_hand"], 100)
        o = self.order("free-sample", [{"sku": "SAMPLE", "quantity": 1, "unit_price_cents": 999999}])
        self.assertEqual((o["total_cents"], o["lines"][0]["unit_price_cents"]), (0, 0))
        self.assertEqual(self.request("GET", "/api/orders/" + o["id"], token=self.south)[0], 404)
        self.assertEqual(self.post("/api/orders", {"client_ref": "v", "lines": [{"sku":"BOLT","quantity":1}]}, self.tokens["viewer"])[0], 403)
        self.assertEqual(self.post("/api/stock/adjustments", {"sku":"BOLT","delta":1,"expected_version":1,"reason":"x"}, self.tokens["operator"])[0], 403)
        self.assertEqual(self.post("/api/stock/adjustments", {"sku":"BOLT","delta":1,"expected_version":1,"reason":"x"}, self.tokens["admin"])[0], 200)
        for lines in ([], [{"sku":"BOLT","quantity":True}], [{"sku":"BOLT","quantity":1.5}], [{"sku":"NOPE","quantity":1}], [{"sku":"BOLT","quantity":1},{"sku":"BOLT","quantity":2}]):
            self.assertEqual(self.post("/api/orders", {"client_ref": "bad-"+str(time.time_ns()), "lines": lines})[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?limit=0", token=self.tokens["admin"])[0], 400)
        self.assertEqual(self.request("GET", "/api/orders?cursor=bad", token=self.tokens["admin"])[0], 400)
        self.assertEqual(self.request("GET", "/api/orders", token=self.tokens["admin"])[0], 200)
        self.assertEqual(self.request("POST", "/api/orders", {"client_ref":"x","lines":[]}, token=self.tokens["viewer"])[0], 403)
        self.assertEqual(self.request("GET", "/api/inventory")[0], 401)
        self.assertEqual(self.request("POST","/api/session",{"email":"operator@north.example","password":"wrong"})[0],401)
        self.assertEqual(self.request("POST","/api/orders",{"client_ref":"missing-key","lines":[{"sku":"BOLT","quantity":1}]},token=self.tokens["operator"])[0],400)

    def test_atomic_reserve_concurrency_and_failed_attempt_audit(self):
        before = self.request("GET", "/api/inventory", token=self.tokens["admin"])[1]["items"]
        audit_before = len(self.request("GET", "/api/audit", token=self.tokens["admin"])[1]["items"])
        o = self.order("too-large", [{"sku":"BOLT","quantity":101},{"sku":"CABLE","quantity":1}])
        code, _ = self.post(f"/api/orders/{o['id']}/reserve", {"expected_version":1})
        self.assertEqual(code, 409)
        after = self.request("GET", "/api/inventory", token=self.tokens["admin"])[1]["items"]
        self.assertEqual([(x["reserved"],x["version"]) for x in before],[(x["reserved"],x["version"]) for x in after])
        self.assertEqual(len(self.request("GET", "/api/audit", token=self.tokens["admin"])[1]["items"]), audit_before+1) # order creation only
        first, second = [self.order(f"race-{i}", [{"sku":"BOLT","quantity":60}]) for i in range(2)]
        def reserve(o): return self.post(f"/api/orders/{o['id']}/reserve", {"expected_version":1})[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(reserve,[first,second]))
        self.assertEqual(sorted(outcomes), [200,409])
        item = next(x for x in self.request("GET", "/api/inventory", token=self.tokens["admin"])[1]["items"] if x["sku"]=="BOLT")
        self.assertEqual(item["reserved"],60)

    def test_transitions_returns_stale_and_audit(self):
        o=self.order("return-flow",[{"sku":"BOLT","quantity":2},{"sku":"SAMPLE","quantity":1}])
        self.assertEqual(self.post(f"/api/orders/{o['id']}/reserve",{"expected_version":99})[0],409)
        r=self.post(f"/api/orders/{o['id']}/reserve",{"expected_version":1});self.assertEqual((r[0],r[1]["status"],r[1]["version"]),(200,"reserved",2))
        self.assertEqual(self.post(f"/api/orders/{o['id']}/ship",{"expected_version":1})[0],409)
        r=self.post(f"/api/orders/{o['id']}/ship",{"expected_version":2});self.assertEqual((r[0],r[1]["status"],r[1]["version"]),(200,"shipped",3))
        r=self.post(f"/api/orders/{o['id']}/returns",{"expected_version":3,"lines":[{"sku":"BOLT","quantity":1}]});self.assertEqual((r[0],r[1]["status"],r[1]["version"]),(200,"shipped",4))
        r=self.post(f"/api/orders/{o['id']}/returns",{"expected_version":4,"lines":[{"sku":"BOLT","quantity":1},{"sku":"SAMPLE","quantity":1}]});self.assertEqual((r[0],r[1]["status"],r[1]["version"]),(200,"returned",5))
        self.assertEqual(self.post(f"/api/orders/{o['id']}/returns",{"expected_version":5,"lines":[{"sku":"BOLT","quantity":1}]})[0],409)
        audit=self.request("GET","/api/audit?limit=2",token=self.tokens["admin"])[1]
        self.assertEqual(len(audit["items"]),2); self.assertTrue(audit["next_cursor"])
        page2=self.request("GET","/api/audit?limit=2&cursor="+audit["next_cursor"],token=self.tokens["admin"])[1]
        self.assertFalse(set(x["id"] for x in audit["items"]) & set(x["id"] for x in page2["items"]))

    def test_cancel_releases_stock_and_adjustment_guards_versions(self):
        order=self.order("cancel-me",[{"sku":"BOLT","quantity":5}])
        self.assertEqual(self.post(f"/api/orders/{order['id']}/reserve",{"expected_version":1})[0],200)
        inv=next(x for x in self.request("GET","/api/inventory",token=self.tokens["admin"])[1]["items"] if x["sku"]=="BOLT")
        self.assertEqual(inv["reserved"],5)
        self.assertEqual(self.post("/api/stock/adjustments",{"sku":"BOLT","delta":-100,"expected_version":inv["version"],"reason":"count"},self.tokens["admin"])[0],409)
        self.assertEqual(self.post("/api/stock/adjustments",{"sku":"BOLT","delta":1,"expected_version":1,"reason":"count"},self.tokens["admin"])[0],409)
        cancelled=self.post(f"/api/orders/{order['id']}/cancel",{"expected_version":2})
        self.assertEqual((cancelled[0],cancelled[1]["status"],cancelled[1]["version"]),(200,"cancelled",3))
        after=next(x for x in self.request("GET","/api/inventory",token=self.tokens["admin"])[1]["items"] if x["sku"]=="BOLT")
        self.assertEqual(after["reserved"],0)

    def test_idempotency_replay_conflict_restart_and_durable_state(self):
        body={"client_ref":"retry-me","lines":[{"sku":"SAMPLE","quantity":1}]}
        status, created=self.post("/api/orders",body,key="persist-key")
        adjust=self.post("/api/stock/adjustments",{"sku":"BOLT","delta":7,"expected_version":1,"reason":"durability check"},self.tokens["admin"],"stock-persist-key")
        self.assertEqual(adjust[0],200)
        count=len(self.request("GET","/api/audit",token=self.tokens["admin"])[1]["items"])
        again=self.post("/api/orders",body,key="persist-key")
        self.assertEqual((again[0],again[1]),(status,created))
        changed=self.post("/api/orders",{**body,"client_ref":"changed"},key="persist-key")
        self.assertEqual(changed[0],409)
        self.stop();self.start()
        self.tokens={role:self.login(f"{role}@north.example")["token"] for role in ("admin","operator","viewer")}
        replay=self.post("/api/orders",body,key="persist-key")
        self.assertEqual(replay[1],created)
        self.assertEqual(len(self.request("GET","/api/audit",token=self.tokens["admin"])[1]["items"]),count)
        got=self.request("GET","/api/orders/"+created["id"],token=self.tokens["admin"])
        self.assertEqual(got[1],created)
        bolt=next(x for x in self.request("GET","/api/inventory",token=self.tokens["admin"])[1]["items"] if x["sku"]=="BOLT")
        self.assertEqual(bolt["on_hand"],107)
        db=Path(self.temp.name)/"depotflow.sqlite3"
        self.assertTrue(db.exists())

    def test_concurrent_identical_retry_single_effect_and_filter_bound_cursor(self):
        body={"client_ref":"same-retry","lines":[{"sku":"SAMPLE","quantity":1}]}
        def create(_): return self.post("/api/orders",body,key="concurrent-same")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(create,range(8)))
        self.assertEqual(len({json.dumps(x,sort_keys=True) for x in results}),1)
        self.assertEqual(sum(1 for x in self.request("GET","/api/audit",token=self.tokens["admin"])[1]["items"] if x["action"]=="order.created"),1)
        for ref in ("pagination-blue-1","pagination-blue-2","pagination-red-3"):
            self.order(ref,[{"sku":"SAMPLE","quantity":1}])
        page=self.request("GET","/api/orders?q=blue&limit=1",token=self.tokens["admin"])[1]
        self.assertEqual(len(page["items"]),1);self.assertIsNotNone(page["next_cursor"])
        self.assertEqual(self.request("GET","/api/orders?q=red&limit=1&cursor="+page["next_cursor"],token=self.tokens["admin"])[0],400)
        next_page=self.request("GET","/api/orders?q=blue&limit=1&cursor="+page["next_cursor"],token=self.tokens["admin"])[1]
        self.assertNotEqual(page["items"][0]["id"],next_page["items"][0]["id"])
        self.order("Straße-ref",[{"sku":"SAMPLE","quantity":1}])
        folded=self.request("GET","/api/orders?q=STRASSE&limit=100",token=self.tokens["admin"])[1]
        self.assertEqual([x["client_ref"] for x in folded["items"]], ["Straße-ref"])


if __name__ == "__main__": unittest.main(verbosity=2)
