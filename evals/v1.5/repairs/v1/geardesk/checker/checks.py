#!/usr/bin/env python3
"""Bounded public-adapter acceptance checks. All stores and catalog edits are synthetic."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

TIMEOUT = 12
REQUEST = dict(
    memberId="regular",
    start="2026-11-06",
    end="2026-11-09",
    lines=[dict(itemId="camera", quantity=1)],
)


def historical_equal(before, after):
    """Every retained historical field is mandatory; only documented zero default is additive."""
    if isinstance(before, dict):
        return (isinstance(after, dict) and all(k in after and historical_equal(v, after[k]) for k,v in before.items())
                and all(k in before or (k == "lateFeePerUnitDay" and type(v) is int and v == 0) for k,v in after.items()))
    if isinstance(before, list):
        return isinstance(after,list) and len(before)==len(after) and all(historical_equal(a,b) for a,b in zip(before,after))
    return type(before) is type(after) and before == after


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Harness:
    def __init__(self, project, root, stage):
        self.project, self.root, self.stage = project, root, stage
        self.data = root / "data"
        self.data.mkdir()
        self.catalog_path = root / "catalog.json"
        self.catalog = {
            "items": [
                dict(
                    id="camera",
                    name="Camera",
                    stock=3,
                    rate=1000 if stage == 1 else 1200,
                    deposit=5000,
                ),
                dict(id="tripod", name="Tripod", stock=5, rate=200, deposit=1000),
                dict(id="projector", name="Projector", stock=1, rate=0, deposit=2000),
            ],
            "members": [
                dict(id="regular", name="Regular", discountBps=0),
                dict(id="club", name="Club", discountBps=1000),
            ],
        }
        if stage >= 2:
            self.catalog["pricing"] = dict(weekendBps=15000, discountCap=300)
        if stage >= 3:
            self.catalog["pricing"]["lateFeePerUnitDay"] = 100
        self.write_catalog()
        self.receipts = []
        self.process = None
        self.key = 0

    def write_catalog(self):
        self.catalog_path.write_text(json.dumps(self.catalog))

    def start(self):
        argv = [
            "node",
            "server.mjs",
            "--data-dir",
            str(self.data),
            "--catalog",
            str(self.catalog_path),
            "--port",
            "0",
        ]
        self.stderr = (self.root / "server.stderr").open("w+")
        self.receipts.append(dict(adapter="server", argv=argv, phase="spawn"))
        self.process = subprocess.Popen(
            argv,
            cwd=self.project,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            text=True,
        )
        deadline = time.monotonic() + TIMEOUT
        pending = b""
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("Server exited before startup")
            if select.select([self.process.stdout], [], [], 0.1)[0]:
                pending += os.read(self.process.stdout.fileno(), 65536)
                if b"\n" not in pending:
                    continue
                startup = json.loads(pending.split(b"\n", 1)[0])
                self.port = startup["port"]
                require(
                    type(self.port) is int and 0 < self.port < 65536,
                    "invalid startup port",
                )
                self.receipts.append(dict(adapter="server", argv=argv, startup=startup))
                return
        raise TimeoutError("Server startup timed out")

    def close(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process.stdout.close()
        if hasattr(self, "stderr"):
            self.stderr.flush()
            self.stderr.seek(0)
            self.receipts.append(
                dict(
                    adapter="server",
                    phase="shutdown",
                    exitCode=self.process.returncode if self.process else None,
                    stderr=self.stderr.read(),
                )
            )
            self.stderr.close()

    def call(self, adapter, operation, body=None, data=None, catalog=None):
        if adapter == "cli":
            argv = [
                "node",
                "cli.mjs",
                "--data-dir",
                str(data or self.data),
                "--catalog",
                str(catalog or self.catalog_path),
                operation,
            ]
            proc = subprocess.run(
                argv,
                cwd=self.project,
                input=json.dumps(body or {}),
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
            receipt = dict(
                adapter="cli",
                argv=argv,
                request=body or {},
                exitCode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
            self.receipts.append(receipt)
            response = json.loads(proc.stdout)
            require(
                (proc.returncode == 0) == (response.get("ok") is True),
                "CLI exit and envelope disagree",
            )
        else:
            method = (
                "POST"
                if operation in ("quote", "availability", "command", "batch")
                else "GET"
            )
            url = f"http://127.0.0.1:{self.port}/api/{operation}"
            request = urllib.request.Request(
                url,
                data=json.dumps(body or {}).encode() if method == "POST" else None,
                headers={"Content-Type": "application/json"},
                method=method,
            )
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT) as result:
                    status, raw = result.status, result.read().decode()
            except urllib.error.HTTPError as result:
                status, raw = result.code, result.read().decode()
            self.receipts.append(
                dict(
                    adapter="http",
                    method=method,
                    url=url,
                    request=body or {},
                    status=status,
                    body=raw,
                )
            )
            response = json.loads(raw)
            require(
                (200 <= status < 300) == (response.get("ok") is True),
                "HTTP status and envelope disagree",
            )
            require(
                response.get("ok") is True or 400 <= status < 500,
                "business failure must be 4xx",
            )
        require(
            type(response.get("ok")) is bool and type(response.get("revision")) is int,
            "invalid response envelope",
        )
        if not response["ok"]:
            require(
                response.get("error", {}).get("code")
                in (
                    "VALIDATION",
                    "NOT_FOUND",
                    "CAPACITY",
                    "INVALID_TRANSITION",
                    "REVISION_CONFLICT",
                    "IDEMPOTENCY_CONFLICT",
                    "BUSY",
                ),
                "unknown error code",
            )
            require(
                isinstance(response["error"].get("message"), str),
                "missing error message",
            )
        return response

    def ok(self, adapter, operation, body=None, **kwargs):
        result = self.call(adapter, operation, body, **kwargs)
        require(result["ok"], f"{operation}: {result}")
        return result

    def revision(self):
        return self.ok("cli", "report")["revision"]

    def command(self, adapter, content, revision=None, key=None):
        self.key += 1
        return self.call(
            adapter,
            "command",
            dict(
                content,
                expectedRevision=self.revision() if revision is None else revision,
                idempotencyKey=key or f"check-{self.key}",
            ),
        )

    def good_command(self, adapter, content, **kwargs):
        result = self.command(adapter, content, **kwargs)
        require(result["ok"], str(result))
        return result

    def reject(self, adapter, operation, body, code="VALIDATION"):
        before = self.revision()
        result = self.call(adapter, operation, body)
        require(
            not result["ok"]
            and result["error"]["code"] in ((code,) if isinstance(code, str) else code),
            str(result),
        )
        require(self.revision() == before, "failed operation changed revision")

    def reserve(self, adapter, identity, **changes):
        return self.good_command(
            adapter, dict(REQUEST, type="reserve", id=identity, **changes)
        )

    def reservation(self, identity):
        rows = self.ok("http", "reservations")["data"]
        return next(r for r in rows if r["id"] == identity)


def exercise(h, check, legacy_store=None):
    def web_surface():
        base = f"http://127.0.0.1:{h.port}"
        with urllib.request.urlopen(base + "/", timeout=TIMEOUT) as response:
            require(
                response.status == 200 and "GearDesk" in response.read().decode(),
                "web console unavailable",
            )
        for suffix in ("/../package.json", "/%2e%2e/package.json"):
            try:
                with urllib.request.urlopen(base + suffix, timeout=TIMEOUT) as response:
                    raw = response.read().decode()
                    require(
                        '"geardesk-demo"' not in raw, "static path escapes web root"
                    )
            except urllib.error.HTTPError as response:
                require(400 <= response.code < 500, "unexpected traversal status")

    check("web console and static path confinement", web_surface)
    subtotal = 3000 if h.stage == 1 else 4800
    for adapter in ("cli", "http"):

        def quote(a=adapter):
            before = h.revision()
            q = h.ok(a, "quote", REQUEST)["data"]
            require(
                {
                    k: q[k]
                    for k in (
                        "rentalSubtotal",
                        "discount",
                        "rentalTotal",
                        "deposit",
                        "totalDue",
                    )
                }
                == dict(
                    rentalSubtotal=subtotal,
                    discount=0,
                    rentalTotal=subtotal,
                    deposit=5000,
                    totalDue=subtotal + 5000,
                ),
                "quote totals",
            )
            require(
                q["lines"][0]["quantity"] == 1 and h.revision() == before,
                "quote mutated or lost quantity",
            )

        check(f"{adapter}: quote arithmetic and read-only", quote)

        def discount(a=adapter):
            q = h.ok(a, "quote", dict(REQUEST, memberId="club"))["data"]
            require(
                q["discount"] == 300 and q["deposit"] == 5000,
                "aggregate discount / cap / deposit",
            )

        check(f"{adapter}: club aggregate discount", discount)

        def free(a=adapter):
            q = h.ok(
                a, "quote", dict(REQUEST, lines=[dict(itemId="projector", quantity=1)])
            )["data"]
            require(
                q["rentalSubtotal"] == 0 and q["totalDue"] == 2000, "free rate deposit"
            )

        check(f"{adapter}: zero-rate deposit", free)

        def invalid(a=adapter):
            variants = [
                dict(REQUEST, start="2026-02-30"),
                dict(REQUEST, end="2026-11-06"),
                dict(REQUEST, end="2026-12-09"),
                dict(REQUEST, lines=[]),
                dict(REQUEST, lines=[dict(itemId="camera", quantity=True)]),
                dict(REQUEST, lines=[dict(itemId="camera", quantity=1.5)]),
                dict(REQUEST, lines=[dict(itemId="camera", quantity=0)]),
                dict(REQUEST, lines=[dict(itemId="camera", quantity=-1)]),
                dict(REQUEST, lines=REQUEST["lines"] * 2),
                dict(REQUEST, memberId="unknown"),
                dict(REQUEST, lines=[dict(itemId="unknown", quantity=1)]),
            ]
            for body in variants:
                unknown = body.get("memberId") == "unknown" or any(
                    line.get("itemId") == "unknown" for line in body.get("lines", [])
                )
                h.reject(
                    a,
                    "quote",
                    body,
                    ("VALIDATION", "NOT_FOUND") if unknown else "VALIDATION",
                )

        check(f"{adapter}: invalid dates identities and quantities", invalid)

        def missing(a=adapter):
            h.reject(a, "command", dict(type="reserve", id="missing-fields", **REQUEST))

        check(f"{adapter}: required mutation controls", missing)

    def unsafe_money():
        saved = copy.deepcopy(h.catalog)
        try:
            h.catalog["items"][0]["rate"] = 9007199254740991
            h.write_catalog()
            for adapter in ("cli", "http"):
                h.reject(adapter, "quote", REQUEST)
        finally:
            h.catalog = saved
            h.write_catalog()

    check("unsafe aggregate money rejected by both adapters", unsafe_money)

    def half_up_discount():
        saved = copy.deepcopy(h.catalog)
        try:
            h.catalog["items"][1]["rate"] = 5
            h.write_catalog()
            request = dict(
                REQUEST,
                memberId="club",
                start="2026-11-06",
                end="2026-11-07",
                lines=[dict(itemId="tripod", quantity=1)],
            )
            for adapter in ("cli", "http"):
                quote = h.ok(adapter, "quote", request)["data"]
                require(
                    quote["rentalSubtotal"] == 5
                    and quote["discount"] == 1
                    and quote["totalDue"] == 1004,
                    "half-up discount",
                )
        finally:
            h.catalog = saved
            h.write_catalog()

    check("aggregate discount half-up rounding", half_up_discount)
    check(
        "catalog and public reads agree",
        lambda: require(
            all(
                h.ok("cli", op)["data"] == h.ok("http", op)["data"]
                for op in ("catalog", "reservations", "report")
            ),
            "adapter read mismatch",
        ),
    )

    def capacity():
        h.reserve(
            "cli",
            "capacity-a",
            end="2026-11-07",
            lines=[dict(itemId="camera", quantity=2)],
        )
        h.reserve(
            "http",
            "capacity-b",
            start="2026-11-07",
            lines=[dict(itemId="camera", quantity=2)],
        )
        for adapter in ("cli", "http"):
            h.ok(adapter, "quote", REQUEST)
            h.reject(
                adapter,
                "quote",
                dict(REQUEST, lines=[dict(itemId="camera", quantity=2)]),
                "CAPACITY",
            )
            rows = h.ok(
                adapter, "availability", dict(start="2026-11-06", end="2026-11-09")
            )["data"]
            require(
                next(r["available"] for r in rows if r["itemId"] == "camera") == 1,
                "daily minimum; disjoint occupants must not be summed",
            )
        h.good_command("http", dict(type="cancel", id="capacity-a"))
        h.good_command("cli", dict(type="cancel", id="capacity-b"))

    check("adjacent bookings and overlapping quote capacity", capacity)

    def replay():
        rev = h.revision()
        content = dict(REQUEST, type="reserve", id="replay")
        first = h.good_command("http", content, revision=rev, key="replay-key")
        again = h.command(
            "cli", dict(reversed(list(content.items()))), revision=0, key="replay-key"
        )
        require(
            again["ok"] and again["revision"] == first["revision"], "semantic replay"
        )
        conflict = h.command(
            "http", dict(content, id="other"), revision=0, key="replay-key"
        )
        require(
            not conflict["ok"] and conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT",
            "key conflict precedence",
        )
        stale = h.command("cli", dict(type="cancel", id="replay"), revision=rev)
        require(
            not stale["ok"] and stale["error"]["code"] == "REVISION_CONFLICT",
            "stale revision",
        )
        h.good_command("cli", dict(type="cancel", id="replay"))

    check("cross-adapter replay conflict and stale revision", replay)

    def parallel():
        rev = h.revision()
        with ThreadPoolExecutor(2) as pool:
            results = list(
                pool.map(
                    lambda a: h.command(
                        a,
                        dict(REQUEST, type="reserve", id="parallel-" + a),
                        revision=rev,
                        key="parallel-" + a,
                    ),
                    ("cli", "http"),
                )
            )
        require(sum(r["ok"] for r in results) == 1, "exactly one concurrent winner")
        require(
            next(r for r in results if not r["ok"])["error"]["code"]
            in ("REVISION_CONFLICT", "BUSY"),
            "concurrent loser",
        )
        require(h.revision() == rev + 1, "concurrent revision increment")
        h.good_command(
            "cli",
            dict(
                type="cancel", id="parallel-" + ("cli" if results[0]["ok"] else "http")
            ),
        )

    check("parallel CLI HTTP writer serialization", parallel)

    def lifecycle():
        h.reserve("cli", "lifecycle")
        for adapter, content, code in [
            ("http", dict(type="return", id="lifecycle"), "INVALID_TRANSITION"),
            ("cli", dict(type="checkout", id="no-such"), "NOT_FOUND"),
            ("http", dict(REQUEST, type="reserve", id="lifecycle"), "VALIDATION"),
        ]:
            result = h.command(adapter, content)
            require(not result["ok"] and result["error"]["code"] == code, str(result))
        h.good_command("http", dict(type="checkout", id="lifecycle"))
        result = h.command("cli", dict(type="cancel", id="lifecycle"))
        require(
            not result["ok"] and result["error"]["code"] == "INVALID_TRANSITION",
            "cancel checked out",
        )
        result = h.good_command("cli", dict(type="return", id="lifecycle"))
        require(
            result["data"]["refund"] == 5000
            and h.reservation("lifecycle")["status"] == "returned",
            "full return",
        )
        result = h.command("http", dict(type="return", id="lifecycle"))
        require(
            not result["ok"] and result["error"]["code"] == "INVALID_TRANSITION",
            "double return",
        )

    check("status transitions and frozen deposit refund", lifecycle)

    def frozen():
        h.reserve("http", "frozen")
        original = copy.deepcopy(h.reservation("frozen")["quote"])
        saved = copy.deepcopy(h.catalog)
        try:
            h.catalog["items"][0]["rate"] = 1700
            h.catalog["items"][0]["deposit"] = 7000
            h.write_catalog()
            for adapter in ("cli", "http"):
                quote = h.ok(adapter, "quote", REQUEST)["data"]
                require(
                    quote["deposit"] == 7000
                    and quote["rentalSubtotal"] == (5100 if h.stage == 1 else 6800),
                    "new catalog facts without server restart",
                )
            require(
                h.reservation("frozen")["quote"] == original, "historical quote changed"
            )
            h.good_command("cli", dict(type="checkout", id="frozen"))
            require(
                h.good_command("http", dict(type="return", id="frozen"))["data"][
                    "refund"
                ]
                == 5000,
                "historical deposit changed",
            )
        finally:
            h.catalog = saved
            h.write_catalog()

    check("current catalog and historical pricing freeze", frozen)

    def reports():
        rows = h.ok("cli", "reservations")["data"]
        report = h.ok("http", "report")["data"]
        require(report["reservationCount"] == len(rows), "reservation count")
        for status in ("reserved", "checked_out", "returned", "cancelled"):
            require(
                report["counts"][status] == sum(r["status"] == status for r in rows),
                "status counts",
            )
        require(
            report["rentalRevenue"]
            == sum(
                r["quote"]["rentalTotal"] for r in rows if r["status"] != "cancelled"
            ),
            "frozen revenue",
        )
        require(report["auditCount"] == h.revision(), "audit one per revision")

    check("public report revenue counts and audit", reports)

    def malformed():
        for raw in (
            json.dumps(dict(schemaVersion=99, revision=0)),
            "{broken-json",
            json.dumps(dict(schemaVersion=1, revision=True)),
        ):
            data = h.root / "bad-store"
            data.mkdir(exist_ok=True)
            (data / "store.json").write_text(raw)
            result = h.call(
                "cli",
                "command",
                dict(
                    REQUEST,
                    type="reserve",
                    id="bad",
                    expectedRevision=0,
                    idempotencyKey="bad",
                ),
                data=data,
            )
            require(
                not result["ok"] and (data / "store.json").read_text() == raw,
                "unsupported store overwritten",
            )

    check("unsupported store preserved", malformed)
    if h.stage >= 2:

        def maintenance():
            h.good_command(
                "cli",
                dict(
                    type="maintenance.add",
                    id="maint",
                    itemId="camera",
                    quantity=3,
                    start="2026-11-06",
                    end="2026-11-07",
                ),
            )
            for adapter in ("cli", "http"):
                require(
                    any(
                        r["id"] == "maint" for r in h.ok(adapter, "maintenance")["data"]
                    ),
                    "maintenance listing",
                )
                h.reject(adapter, "quote", REQUEST, "CAPACITY")
            h.reserve("http", "maint-adjacent", start="2026-11-07")
            result = h.command(
                "http",
                dict(
                    type="maintenance.add",
                    id="maint-overlap",
                    itemId="camera",
                    quantity=1,
                    start="2026-11-06",
                    end="2026-11-07",
                ),
            )
            require(
                not result["ok"] and result["error"]["code"] == "CAPACITY",
                "maintenance overlap",
            )
            require(
                h.ok("cli", "report")["data"]["maintenanceCount"] == 1,
                "maintenance count",
            )
            h.good_command("http", dict(type="maintenance.remove", id="maint"))
            result = h.command("cli", dict(type="maintenance.remove", id="maint"))
            require(
                not result["ok"] and result["error"]["code"] == "NOT_FOUND",
                "removed maintenance",
            )
            h.good_command("cli", dict(type="cancel", id="maint-adjacent"))

        check("maintenance capacity adjacency removal and report", maintenance)

        def rounding():
            saved = copy.deepcopy(h.catalog)
            try:
                h.catalog["items"][1]["rate"] = 201
                h.write_catalog()
                request = dict(
                    REQUEST,
                    start="2026-11-07",
                    end="2026-11-08",
                    lines=[dict(itemId="tripod", quantity=2)],
                )
                for adapter in ("cli", "http"):
                    require(
                        h.ok(adapter, "quote", request)["data"]["rentalSubtotal"]
                        == 604,
                        "per-unit half-up rounding",
                    )
            finally:
                h.catalog = saved
                h.write_catalog()

        check("weekend rounding before quantity multiplication", rounding)

        def optional_pricing():
            saved = copy.deepcopy(h.catalog)
            try:
                h.catalog.pop("pricing")
                h.write_catalog()
                for adapter in ("cli", "http"):
                    quote = h.ok(adapter, "quote", dict(REQUEST, memberId="club"))[
                        "data"
                    ]
                    require(
                        quote["rentalSubtotal"] == 3600 and quote["discount"] == 360,
                        "absent pricing defaults",
                    )
            finally:
                h.catalog = saved
                h.write_catalog()

        check("missing optional pricing has base rates and no cap", optional_pricing)

    if h.stage >= 3:

        def partial():
            h.reserve(
                "cli",
                "partial",
                lines=[
                    dict(itemId="camera", quantity=2),
                    dict(itemId="tripod", quantity=1),
                ],
            )
            h.good_command("http", dict(type="checkout", id="partial"))
            before = h.ok("cli", "report")["data"]
            result = h.good_command(
                "http",
                dict(
                    type="return.partial",
                    id="partial",
                    returnedOn="2026-11-10",
                    lines=[dict(itemId="camera", quantity=1)],
                ),
            )["data"]
            require(
                (result["refund"], result["lateFee"], result["returnedQuantity"])
                == (4900, 100, 1),
                "partial refund arithmetic",
            )
            require(
                h.reservation("partial")["status"] == "checked_out", "partial status"
            )
            report = h.ok("http", "report")["data"]
            require(
                report["depositHeld"] == before["depositHeld"] - 5000
                and report["refunded"] == before["refunded"] + 4900
                and report["lateFees"] == before["lateFees"] + 100,
                "partial report accounting",
            )
            require(
                next(
                    r["available"]
                    for r in h.ok(
                        "cli",
                        "availability",
                        dict(start="2026-11-06", end="2026-11-09"),
                    )["data"]
                    if r["itemId"] == "camera"
                )
                == 2,
                "partial capacity release",
            )
            for lines in (
                [dict(itemId="camera", quantity=2)],
                [dict(itemId="projector", quantity=1)],
                [dict(itemId="camera", quantity=1)] * 2,
            ):
                result = h.command(
                    "cli",
                    dict(
                        type="return.partial",
                        id="partial",
                        returnedOn="2026-11-10",
                        lines=lines,
                    ),
                )
                require(
                    not result["ok"] and result["error"]["code"] == "VALIDATION",
                    "invalid return lines",
                )
            result = h.good_command(
                "cli", dict(type="return", id="partial", returnedOn="2026-11-10")
            )["data"]
            require(
                (result["refund"], result["lateFee"], result["returnedQuantity"])
                == (5800, 200, 2),
                "remaining full return",
            )
            require(
                h.reservation("partial")["status"] == "returned",
                "completed partial return",
            )

        check("partial remaining returns validation capacity and accounting", partial)

        def return_dates():
            h.reserve("http", "return-dates")
            h.good_command("cli", dict(type="checkout", id="return-dates"))
            for adapter, date in (("cli", "2026-02-30"), ("http", "2026-11-05")):
                result = h.command(
                    adapter,
                    dict(
                        type="return.partial",
                        id="return-dates",
                        returnedOn=date,
                        lines=[dict(itemId="camera", quantity=1)],
                    ),
                )
                require(
                    not result["ok"] and result["error"]["code"] == "VALIDATION",
                    "invalid actual return date",
                )
            result = h.good_command(
                "http", dict(type="return", id="return-dates", returnedOn="2026-11-09")
            )["data"]
            require(
                result["refund"] == 5000 and result["lateFee"] == 0,
                "end date must have no fee",
            )

        check("return date validation and scheduled-end zero fee", return_dates)

        def absent_fee():
            saved = copy.deepcopy(h.catalog)
            try:
                h.catalog["pricing"].pop("lateFeePerUnitDay")
                h.write_catalog()
                h.reserve("cli", "absent-fee")
            finally:
                h.catalog = saved
                h.write_catalog()
            h.good_command("http", dict(type="checkout", id="absent-fee"))
            result = h.good_command(
                "cli", dict(type="return", id="absent-fee", returnedOn="2026-11-11")
            )["data"]
            require(
                result["refund"] == 5000 and result["lateFee"] == 0,
                "missing fee snapshot must remain zero",
            )

        check("missing fee rate snapshots zero for new reservation", absent_fee)

        def fee_freeze():
            h.reserve(
                "http", "fee-freeze", lines=[dict(itemId="projector", quantity=1)]
            )
            h.good_command("cli", dict(type="checkout", id="fee-freeze"))
            h.catalog["pricing"]["lateFeePerUnitDay"] = 999
            h.write_catalog()
            try:
                result = h.good_command(
                    "http",
                    dict(type="return", id="fee-freeze", returnedOn="2026-11-10"),
                )["data"]
                require(
                    result["lateFee"] == 100 and result["refund"] == 1900,
                    "fee snapshot",
                )
            finally:
                h.catalog["pricing"]["lateFeePerUnitDay"] = 100
                h.write_catalog()

        check("late-fee snapshot uses accepted catalog", fee_freeze)

        def capped_fee():
            h.reserve("cli", "fee-cap", lines=[dict(itemId="projector", quantity=1)])
            h.good_command("http", dict(type="checkout", id="fee-cap"))
            result = h.good_command(
                "cli", dict(type="return", id="fee-cap", returnedOn="2026-12-09")
            )["data"]
            require(
                result["lateFee"] == 2000 and result["refund"] == 0,
                "fee must cap at deposit",
            )

        check("late fee capped by returned deposits", capped_fee)

        def batch():
            rev = h.revision()
            raw = (h.data / "store.json").read_bytes()
            commands = [
                dict(REQUEST, type="reserve", id="rollback"),
                dict(type="checkout", id="unknown-batch"),
            ]
            for adapter in ("cli", "http"):
                result = h.call(
                    adapter,
                    "batch",
                    dict(
                        expectedRevision=rev,
                        idempotencyKey="rollback-" + adapter,
                        commands=commands,
                    ),
                )
                require(
                    not result["ok"] and (h.data / "store.json").read_bytes() == raw,
                    "batch rollback changed bytes",
                )
            commands = [
                dict(REQUEST, type="reserve", id="batch-good"),
                dict(type="checkout", id="batch-good"),
                dict(type="return", id="batch-good"),
            ]
            body = dict(
                expectedRevision=rev, idempotencyKey="batch-key", commands=commands
            )
            result = h.ok("http", "batch", body)
            require(
                result["revision"] == rev + 3 and len(result["data"]) == 3,
                "batch revisions and result array",
            )
            raw = (h.data / "store.json").read_bytes()
            require(
                h.ok("cli", "batch", dict(body, expectedRevision=0))["revision"]
                == rev + 3,
                "batch replay",
            )
            require(
                (h.data / "store.json").read_bytes() == raw,
                "batch replay rewrote store",
            )
            conflict = h.call(
                "cli",
                "batch",
                dict(body, commands=[dict(type="cancel", id="batch-good")]),
            )
            require(
                not conflict["ok"]
                and conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT",
                "batch key conflict",
            )
            for commands in ([], [dict(type="cancel", id="batch-good")] * 21):
                h.reject(
                    "http",
                    "batch",
                    dict(
                        expectedRevision=h.revision(),
                        idempotencyKey="size-" + str(len(commands)),
                        commands=commands,
                    ),
                )

        check("atomic batch rollback revisions replay conflict and limits", batch)

        def batch_identity():
            h.good_command(
                "cli", dict(REQUEST, type="reserve", id="separate-key"), key="batch-key"
            )
            h.good_command("http", dict(type="cancel", id="separate-key"))
            rev = h.revision()
            result = h.call(
                "cli",
                "batch",
                dict(
                    expectedRevision=rev - 1,
                    idempotencyKey="stale-batch",
                    commands=[dict(REQUEST, type="reserve", id="stale-batch")],
                ),
            )
            require(
                not result["ok"]
                and result["error"]["code"] == "REVISION_CONFLICT"
                and h.revision() == rev,
                "stale batch",
            )

        check("batch and individual key namespaces and stale revision", batch_identity)

        def migration():
            legacy = h.root / "legacy"
            legacy.mkdir()
            raw = Path(legacy_store).read_bytes()
            (legacy / "store.json").write_bytes(raw)
            source = json.loads(raw)
            require(
                source["schemaVersion"] == 1, "fixture must be genuine schemaVersion 1"
            )
            original = h.ok("cli", "reservations", data=legacy)["data"]
            report = h.ok("cli", "report", data=legacy)["data"]
            require(
                (legacy / "store.json").read_bytes() == raw,
                "read migrated persisted bytes",
            )
            identities = {r["id"]: r for r in original}
            require(
                identities["legacy-active"]["status"] == "checked_out"
                and identities["legacy-active"]["quote"]["rentalTotal"] == 4800,
                "legacy active fixture contract",
            )
            require(
                identities["legacy-returned"]["status"] == "returned"
                and identities["legacy-cancelled"]["status"] == "cancelled",
                "legacy completed fixture contract",
            )
            failed = h.call(
                "cli",
                "command",
                dict(
                    type="checkout",
                    id="missing-legacy",
                    expectedRevision=source["revision"],
                    idempotencyKey="legacy-fail",
                ),
                data=legacy,
            )
            require(
                not failed["ok"] and (legacy / "store.json").read_bytes() == raw,
                "failed legacy command rewrote bytes",
            )
            result = h.ok(
                "cli",
                "command",
                dict(
                    type="return",
                    id="legacy-active",
                    returnedOn="2026-11-11",
                    expectedRevision=source["revision"],
                    idempotencyKey="legacy-return",
                ),
                data=legacy,
            )
            require(
                result["data"]["refund"] == 5000 and result["data"]["lateFee"] == 0,
                "invented historical late fee",
            )
            require(
                json.loads((legacy / "store.json").read_text())["schemaVersion"] == 2,
                "successful migration version",
            )
            rows = {
                r["id"]: r for r in h.ok("cli", "reservations", data=legacy)["data"]
            }
            require(
                rows["legacy-active"]["status"] == "returned",
                "legacy active return status",
            )
            require(
                historical_equal(identities["legacy-active"]["quote"], rows["legacy-active"]["quote"]),
                "legacy frozen quote lost",
            )
            for identity in ("legacy-returned", "legacy-cancelled"):
                for field in ("id", "memberId", "start", "end", "status", "lines"):
                    require(
                        rows[identity][field] == identities[identity][field],
                        "legacy historical public record changed",
                    )
                for field in (
                    "rentalSubtotal",
                    "discount",
                    "rentalTotal",
                    "deposit",
                    "totalDue",
                ):
                    require(
                        rows[identity]["quote"][field]
                        == identities[identity]["quote"][field],
                        "legacy historical quote amounts changed",
                    )
            for identity in identities:
                require(historical_equal(identities[identity]["quote"], rows[identity]["quote"]), "historical quote/lines changed")
                for field in ("id", "memberId", "start", "end", "lines"):
                    require(rows[identity][field] == identities[identity][field], "historical identity/quantity changed")
            persisted = json.loads((legacy / "store.json").read_text())
            require(persisted["audit"][:len(source["audit"])] == source["audit"], "historical audit lost")
            after = h.ok("cli", "report", data=legacy)["data"]
            require(
                after["refunded"] == report["refunded"] + 5000
                and after["depositHeld"] == report["depositHeld"] - 5000
                and after["lateFees"] == 0,
                "legacy accounting migration",
            )
            require(
                after["auditCount"] == report["auditCount"] + 1
                and after["rentalRevenue"] == report["rentalRevenue"],
                "legacy audit/revenue preservation",
            )

        if legacy_store is not None and Path(legacy_store).is_file():
            check(
                "genuine version-1 historical fees preservation and migration",
                migration,
            )
        else:
            check(
                "genuine version-1 historical fees preservation and migration",
                lambda: (_ for _ in ()).throw(
                    Unassessable("Genuine prior-stage store fixture unavailable")
                ),
            )

    def final_accounting():
        for adapter in ("cli", "http"):
            report = h.ok(adapter, "report")["data"]
            require(
                report["depositHeld"] == 0,
                "all scenario active deposits must be released",
            )
            require(
                report["refunded"] == (37600 if h.stage >= 3 else 10000),
                "cumulative refunds",
            )
            require(
                report["auditCount"] == h.revision(),
                "final audit / revision consistency",
            )
            if h.stage >= 3:
                require(report["lateFees"] == 2400, "cumulative fees")
            if h.stage >= 2:
                require(report["maintenanceCount"] == 0, "removed maintenance count")
        require(
            json.loads((h.data / "store.json").read_text())["schemaVersion"]
            == (2 if h.stage >= 3 else 1),
            "write schema version",
        )

    check(
        "final cumulative deposit refund fee audit and schema accounting",
        final_accounting,
    )


class Unassessable(Exception):
    """Required historical evidence was unavailable, not an application verdict."""


def run_checks(
    project: Path, stage: int, output: Path, legacy_store: Path | None = None
):
    project, output = Path(project).resolve(), Path(output).resolve()
    if stage not in (1, 2, 3):
        raise ValueError("stage must be 1, 2 or 3")
    if output.exists():
        raise FileExistsError(f"Refusing existing output: {output}")
    checks = []

    def check(name, fn):
        start = time.monotonic()
        try:
            if name.startswith("final cumulative") and any(
                c["status"] != "pass" and c["group"] == "main" for c in checks
            ):
                raise Unassessable(
                    "Earlier scenario did not complete; the full cumulative fixture total was not reached"
                )
            fn()
            status = "pass"
            detail = None
        except Unassessable as exc:
            status = "unassessable"
            detail = str(exc)
        except AssertionError as exc:
            status = "fail"
            detail = str(exc)
        except Exception as exc:
            status = "error"
            detail = f"{type(exc).__name__}: {exc}"
        checks.append(
            dict(
                name=name,
                group="migration" if name.startswith("genuine version-1") else "main",
                status=status,
                detail=detail,
                durationSeconds=round(time.monotonic() - start, 3),
            )
        )

    with tempfile.TemporaryDirectory(prefix="geardesk-acceptance-") as folder:
        h = Harness(project, Path(folder), stage)
        try:
            check("server loopback startup", h.start)
            if checks[-1]["status"] == "pass":
                exercise(h, check, legacy_store)
            else:
                for operation, body in [
                    ("catalog", {}),
                    ("report", {}),
                    ("quote", REQUEST),
                ]:
                    check(
                        "independent CLI smoke after HTTP startup failure: "
                        + operation,
                        lambda op=operation, req=body: h.ok("cli", op, req),
                    )
                checks.append(
                    dict(
                        name="remaining HTTP and mixed adapter checks",
                        status="unassessable",
                        detail="Server startup unavailable; independent CLI smoke still attempted",
                    )
                )
        finally:
            h.close()
        summary = dict(
            stage=stage,
            project=str(project),
            counts={
                s: sum(c["status"] == s for c in checks)
                for s in ("pass", "fail", "error", "unassessable")
            },
            checks=checks,
            receipts=h.receipts,
            limitations=[
                "Genuine historical migration coverage requires the supplied prior-stage store fixture.",
                "Main scenarios share one dependency group; migration is isolated and cannot suppress main accounting.",
            ],
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(summary, stream, indent=2)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--legacy-store",
        type=Path,
        help="Genuine prior-stage schemaVersion 1 fixture; copied to owned temporary data",
    )
    args = parser.parse_args()
    summary = run_checks(args.project, args.stage, args.output, args.legacy_store)
    print(json.dumps(summary["counts"]))
    raise SystemExit(
        1 if summary["counts"]["fail"] or summary["counts"]["error"] else 0
    )
