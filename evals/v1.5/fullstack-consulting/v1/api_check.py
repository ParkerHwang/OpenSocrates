"""Language-neutral public HTTP contract checks. No candidate implementation edits."""

from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class Probe:
    def __init__(self, url, output):
        self.url = url.rstrip("/")
        self.output = output
        self.lock = threading.Lock()
        self.groups = []
        self.tokens = {}
        self.keep = {}

    def req(self, method, path, body=None, who="admin", key=None, token=None):
        headers = {"Content-Type": "application/json"}
        if who is not None:
            headers["Authorization"] = "Bearer " + (token or self.tokens.get(who, ""))
        if key is not None:
            headers["Idempotency-Key"] = key
        request = urllib.request.Request(
            self.url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        begin = time.monotonic()
        try:
            with urllib.request.urlopen(request) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as e:
            status = e.code
            raw = e.read()
        try:
            value = json.loads(raw)
        except ValueError:
            value = {"non_json_body": raw.decode("utf-8", "replace")[:3000]}
        with self.lock:
            with (self.output / "api-requests.jsonl").open("a") as f:
                f.write(
                    json.dumps(
                        {
                            "method": method,
                            "path": path,
                            "body": body,
                            "who": who,
                            "key": key,
                            "status": status,
                            "response": value,
                            "wall_seconds": time.monotonic() - begin,
                        }
                    )
                    + "\n"
                )
        return status, value

    def ok(self, method, path, body=None, who="admin", key=None):
        code, value = self.req(method, path, body, who, key)
        assert 200 <= code < 300, (code, value)
        return value

    def group(self, name, fn, critical=False):
        try:
            detail = fn()
            passed = detail is not False
        except Exception as e:
            detail = repr(e)
            passed = False
        self.groups.append({"name": name, "pass": passed, "critical": critical, "details": detail})

    def create(self, lines=None, ref=None, key=None, who="admin"):
        return self.ok(
            "POST",
            "/api/orders",
            {
                "client_ref": ref or "CHECK-" + uuid.uuid4().hex[:12],
                "lines": lines or [{"sku": "BOLT", "quantity": 2}],
            },
            who,
            key or uuid.uuid4().hex,
        )

    def move(self, order, action, lines=None, who="admin", key=None):
        body = {"expected_version": order["version"]}
        if lines is not None:
            body["lines"] = lines
        return self.ok(
            "POST", f"/api/orders/{order['id']}/{action}", body, who, key or uuid.uuid4().hex
        )

    def stock(self, who="admin"):
        return {x["sku"]: x for x in self.ok("GET", "/api/inventory", who=who)["items"]}

    def audit(self, who="admin"):
        items = []
        cursor = None
        while True:
            data = self.ok(
                "GET",
                "/api/audit?limit=100"
                + ("&cursor=" + urllib.parse.quote(cursor) if cursor else ""),
                who=who,
            )
            items += data["items"]
            next_ = data["next_cursor"]
            if next_ is None:
                return items
            assert next_ != cursor, "nonadvancing cursor"
            cursor = next_

    def login(self):
        for alias, role, tenant in [
            ("admin", "admin", "north"),
            ("operator", "operator", "north"),
            ("viewer", "viewer", "north"),
            ("south", "admin", "south"),
        ]:
            data = self.ok(
                "POST",
                "/api/session",
                {"email": f"{role}@{tenant}.example", "password": "DepotDemo!2026"},
                who=None,
            )
            assert data["user"] == dict(email=f"{role}@{tenant}.example", role=role, tenant=tenant)
            self.tokens[alias] = data["token"]

    def run(self):
        self.output.mkdir(parents=True, exist_ok=True)
        self.group("health", lambda: self.ok("GET", "/api/health", who=None)["status"] == "ok")
        self.group("login_and_identity", self.login, True)

        def authorization():
            assert self.req("GET", "/api/inventory", who=None)[0] == 401
            assert self.req("GET", "/api/inventory", token="invalid")[0] == 401
            assert (
                self.req(
                    "POST",
                    "/api/session",
                    {"email": "admin@north.example", "password": "bad"},
                    who=None,
                )[0]
                == 401
            )
            assert (
                self.req(
                    "POST",
                    "/api/orders",
                    {"client_ref": "FORBIDDEN", "lines": [{"sku": "BOLT", "quantity": 1}]},
                    "viewer",
                    "v1",
                )[0]
                == 403
            )
            assert self.ok("GET", "/api/me", who="operator")["role"] == "operator"

        self.group("authentication_and_role", authorization, True)

        def seed():
            a = self.stock()
            b = self.stock("south")
            assert [
                (s, a[s]["on_hand"], a[s]["available"], a[s]["reserved"], a[s]["price_cents"])
                for s in ("BOLT", "CABLE", "SAMPLE")
            ] == [("BOLT", 100, 100, 0, 1250), ("CABLE", 60, 60, 0, 2499), ("SAMPLE", 20, 20, 0, 0)]
            assert all(a[s]["on_hand"] == b[s]["on_hand"] for s in a)

        self.group("seed_stock", seed)

        def validation():
            cases = [
                [],
                [{"sku": "BOLT", "quantity": True}],
                [{"sku": "BOLT", "quantity": 1.5}],
                [{"sku": "BOLT", "quantity": 0}],
                [{"sku": "NOPE", "quantity": 1}],
                [{"sku": "BOLT", "quantity": 1}, {"sku": "BOLT", "quantity": 2}],
            ]
            for i, lines in enumerate(cases):
                code, body = self.req(
                    "POST",
                    "/api/orders",
                    {"client_ref": f"INVALID-{i}", "lines": lines},
                    key=f"invalid-{i}",
                )
                assert code == 400 and isinstance(body.get("error", {}).get("message"), str), (
                    i,
                    code,
                    body,
                )

        self.group("input_validation", validation, True)

        def free_order():
            o = self.create([{"sku": "SAMPLE", "quantity": 1}])
            assert o["total_cents"] == 0 and o["status"] == "draft"

        self.group("nonempty_zero_price_order", free_order)

        def server_price():
            o = self.create([{"sku": "BOLT", "quantity": 2, "unit_price_cents": 1}])
            assert o["total_cents"] == 2500 and o["lines"][0]["unit_price_cents"] == 1250

        self.group("server_price_authority", server_price)

        def tenant():
            o = self.create()
            assert self.req("GET", "/api/orders/" + str(o["id"]), who="south")[0] == 404
            assert (
                self.req(
                    "POST",
                    "/api/orders/" + str(o["id"]) + "/reserve",
                    {"expected_version": o["version"]},
                    "south",
                    "cross",
                )[0]
                == 404
            )

        self.group("tenant_isolation", tenant, True)

        def operator_stock():
            v = self.stock()["BOLT"]["version"]
            assert (
                self.req(
                    "POST",
                    "/api/stock/adjustments",
                    {"sku": "BOLT", "delta": 1, "expected_version": v, "reason": "role"},
                    "operator",
                    "opstock",
                )[0]
                == 403
            )
            self.create(who="operator")

        self.group("operator_permissions", operator_stock)

        def replay():
            body = {"client_ref": "REPLAY", "lines": [{"sku": "BOLT", "quantity": 1}]}
            first = self.req("POST", "/api/orders", body, key="replay-create")
            assert first[0] in (200, 201)
            before = len(self.audit())
            second = self.req("POST", "/api/orders", body, key="replay-create")
            assert first == second and len(self.audit()) == before
            assert (
                self.req(
                    "POST", "/api/orders", {**body, "client_ref": "CHANGED"}, key="replay-create"
                )[0]
                == 409
            )
            assert (
                self.req(
                    "POST",
                    f"/api/orders/{first[1]['id']}/reserve",
                    {"expected_version": 1},
                    key="replay-create",
                )[0]
                == 409
            )
            self.keep["replay"] = {"body": body, "response": first}

        self.group("idempotency_replay_and_conflict", replay, True)

        def failed_key():
            body = {"client_ref": "RECOVER-KEY", "lines": []}
            assert self.req("POST", "/api/orders", body, key="recover-key")[0] == 400
            body["lines"] = [{"sku": "BOLT", "quantity": 1}]
            assert self.req("POST", "/api/orders", body, key="recover-key")[0] in (200, 201)

        self.group("failed_request_does_not_consume_key", failed_key)

        def key_required():
            assert (
                self.req(
                    "POST",
                    "/api/orders",
                    {"client_ref": "NOKEY", "lines": [{"sku": "BOLT", "quantity": 1}]},
                )[0]
                == 400
            )

        self.group("idempotency_key_required", key_required)

        def reference_unique():
            self.create(ref="UNIQUE")
            assert (
                self.req(
                    "POST",
                    "/api/orders",
                    {"client_ref": "UNIQUE", "lines": [{"sku": "BOLT", "quantity": 3}]},
                    key="different-key",
                )[0]
                == 409
            )

        self.group("client_reference_unique", reference_unique)

        def cancel():
            o = self.create()
            before = self.stock()
            o = self.move(o, "reserve")
            assert o["status"] == "reserved" and o["version"] == 2
            s = self.stock()
            assert (
                s["BOLT"]["reserved"] == before["BOLT"]["reserved"] + 2
                and s["BOLT"]["on_hand"] == before["BOLT"]["on_hand"]
            )
            o = self.move(o, "cancel")
            s = self.stock()
            assert (
                o["status"] == "cancelled"
                and o["version"] == 3
                and s["BOLT"]["reserved"] == before["BOLT"]["reserved"]
            )

        self.group("reserve_cancel_stock", cancel, True)

        def atomic():
            o = self.create([{"sku": "BOLT", "quantity": 2}, {"sku": "CABLE", "quantity": 999}])
            before = self.stock()
            audit = len(self.audit())
            assert (
                self.req(
                    "POST",
                    f"/api/orders/{o['id']}/reserve",
                    {"expected_version": o["version"]},
                    key="atomic",
                )[0]
                == 409
            )
            assert (
                before == self.stock()
                and len(self.audit()) == audit
                and self.ok("GET", f"/api/orders/{o['id']}")["status"] == "draft"
            )

        self.group("multiline_atomic_failure", atomic, True)

        def stale():
            o = self.create()
            updated = self.move(o, "reserve")
            before = self.stock()
            n = len(self.audit())
            assert (
                self.req(
                    "POST",
                    f"/api/orders/{o['id']}/ship",
                    {"expected_version": o["version"]},
                    key="stale",
                )[0]
                == 409
            )
            assert self.stock() == before and len(self.audit()) == n
            self.move(updated, "cancel")

        self.group("stale_version_no_effect", stale, True)

        def returns():
            o = self.create([{"sku": "BOLT", "quantity": 3}, {"sku": "CABLE", "quantity": 2}])
            before = self.stock()
            o = self.move(self.move(o, "reserve"), "ship")
            stock = self.stock()
            assert (
                stock["BOLT"]["on_hand"] == before["BOLT"]["on_hand"] - 3
                and stock["BOLT"]["reserved"] == before["BOLT"]["reserved"]
            )
            assert o["status"] == "shipped"
            o = self.move(o, "returns", [{"sku": "BOLT", "quantity": 1}])
            assert o["status"] == "shipped"
            assert self.stock()["BOLT"]["on_hand"] == before["BOLT"]["on_hand"] - 2
            old = self.stock()
            assert (
                self.req(
                    "POST",
                    f"/api/orders/{o['id']}/returns",
                    {"expected_version": o["version"], "lines": [{"sku": "BOLT", "quantity": 3}]},
                    key="excess-return",
                )[0]
                == 409
            )
            assert old == self.stock()
            o = self.move(
                o, "returns", [{"sku": "BOLT", "quantity": 2}, {"sku": "CABLE", "quantity": 2}]
            )
            assert o["status"] == "returned"
            assert self.stock()["BOLT"]["on_hand"] == before["BOLT"]["on_hand"]
            assert (
                self.req(
                    "POST",
                    f"/api/orders/{o['id']}/cancel",
                    {"expected_version": o["version"]},
                    key="invalid-cancel",
                )[0]
                == 409
            )

        self.group("ship_partial_full_return", returns, True)

        def bad_return():
            o = self.move(self.move(self.create(), "reserve"), "ship")
            stock = self.stock()
            for q in (True, 1.5, 0):
                assert (
                    self.req(
                        "POST",
                        f"/api/orders/{o['id']}/returns",
                        {
                            "expected_version": o["version"],
                            "lines": [{"sku": "BOLT", "quantity": q}],
                        },
                        key="badreturn" + str(q),
                    )[0]
                    == 400
                )
            assert stock == self.stock()

        self.group("return_quantity_validation", bad_return)

        def stock_floor():
            o = self.move(self.create(), "reserve")
            s = self.stock()["BOLT"]
            n = len(self.audit())
            code, _ = self.req(
                "POST",
                "/api/stock/adjustments",
                {
                    "sku": "BOLT",
                    "delta": -(s["on_hand"] - s["reserved"] + 1),
                    "expected_version": s["version"],
                    "reason": "floor",
                },
                key="floor",
            )
            assert code == 409 and self.stock()["BOLT"] == s and len(self.audit()) == n
            self.move(o, "cancel")

        self.group("stock_adjustment_respects_reservations", stock_floor, True)

        def race():
            s = self.stock("south")["BOLT"]
            self.ok(
                "POST",
                "/api/stock/adjustments",
                {
                    "sku": "BOLT",
                    "delta": 10 - s["on_hand"],
                    "expected_version": s["version"],
                    "reason": "race fixture",
                },
                "south",
                "race-stock",
            )
            orders = [self.create([{"sku": "BOLT", "quantity": 1}], who="south") for _ in range(20)]

            def reserve(o):
                return self.req(
                    "POST",
                    f"/api/orders/{o['id']}/reserve",
                    {"expected_version": o["version"]},
                    "south",
                    "race-" + str(o["id"]),
                )[0]

            with ThreadPoolExecutor(max_workers=20) as pool:
                codes = list(pool.map(reserve, orders))
            assert sum(200 <= c < 300 for c in codes) == 10 and codes.count(409) == 10, codes
            s = self.stock("south")["BOLT"]
            assert (s["on_hand"], s["reserved"], s["available"]) == (10, 10, 0)

        self.group("concurrent_reservations_no_oversell", race, True)

        def duplicate_race():
            body = {"client_ref": "CONCURRENT-REPLAY", "lines": [{"sku": "BOLT", "quantity": 1}]}
            before = len(self.audit())
            with ThreadPoolExecutor(max_workers=12) as pool:
                results = list(
                    pool.map(
                        lambda _: self.req("POST", "/api/orders", body, key="simultaneous"),
                        range(12),
                    )
                )
            assert all(r == results[0] for r in results) and results[0][0] in (200, 201)
            assert len(self.audit()) == before + 1

        self.group("concurrent_idempotent_create", duplicate_race, True)

        def pagination():
            for i in range(5):
                self.create(ref=f"PAGE-{i}")
            cursor = None
            ids = []
            for _ in range(4):
                result = self.ok(
                    "GET",
                    "/api/orders?q=page-&limit=2"
                    + ("&cursor=" + urllib.parse.quote(cursor) if cursor else ""),
                )
                ids += [o["id"] for o in result["items"]]
                cursor = result["next_cursor"]
                if cursor is None:
                    break
            assert len(ids) == len(set(ids)) == 5
            assert self.ok("GET", "/api/orders?q=NOTHING-MATCHES")["items"] == []
            assert self.req("GET", "/api/orders?limit=0")[0] == 400
            assert self.req("GET", "/api/orders?status=nonsense")[0] == 400
            assert self.req("GET", "/api/orders?cursor=not-a-real-cursor")[0] == 400

        self.group("filter_and_cursor_pagination", pagination)

        def audit():
            before = self.audit()
            o = self.create()
            after = self.audit()
            assert len(after) == len(before) + 1
            event = after[-1]
            assert all(k in event for k in ("id", "action", "entity_id", "actor", "created_at"))
            assert str(event["entity_id"]) == str(o["id"])
            self.keep["audit"] = len(after)

        self.group("audit_single_effect", audit, True)

        def dashboard():
            d = self.ok("GET", "/api/dashboard")
            s = self.stock()
            assert d["inventory_units"] == sum(x["on_hand"] for x in s.values())
            assert d["reserved_units"] == sum(x["reserved"] for x in s.values())
            all_ = self.ok("GET", "/api/orders?limit=100")
            assert all_["next_cursor"] is None
            counts = Counter(o["status"] for o in all_["items"])
            assert all(d["orders_by_status"].get(k, 0) == v for k, v in counts.items())

        self.group("dashboard_consistency", dashboard)
        try:
            self.keep["stock"] = self.stock()
            self.keep["order_count"] = sum(
                self.ok("GET", "/api/dashboard")["orders_by_status"].values()
            )
        except Exception as e:
            self.keep["persistence_prerequisite_error"] = repr(e)
        return {
            "groups": self.groups,
            "passed": sum(x["pass"] for x in self.groups),
            "total": len(self.groups),
            "critical_pass": all(g["pass"] for g in self.groups if g["critical"]),
            "persistence_expectation": self.keep,
        }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("output", type=Path)
    a = p.parse_args()
    print(json.dumps(Probe(a.url, a.output).run(), indent=2))
