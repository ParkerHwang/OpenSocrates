#!/usr/bin/env python3
"""DepotFlow: local, tenant-isolated fulfillment server."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data"))).resolve()
DB_PATH = DATA_DIR / "depotflow.sqlite3"
STATUSES = {"draft", "reserved", "shipped", "returned", "cancelled"}
MAX_SQL_INT = 2**63 - 1
SKU_SEED = [("BOLT", "Steel bolt kit", 100, 1250), ("CABLE", "Cable assembly", 60, 2499), ("SAMPLE", "Sample pack", 20, 0)]


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def fail(status, code, message):
    raise ApiError(status, code, message)


def db():
    con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    con.create_function("casefold", 1, lambda value: value.casefold(), deterministic=True)
    return con


def initialize():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS tenants (id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS users (
          email TEXT PRIMARY KEY, tenant TEXT NOT NULL REFERENCES tenants(id),
          role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
          salt BLOB NOT NULL, password_hash BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, email TEXT NOT NULL REFERENCES users(email),
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inventory (
          tenant TEXT NOT NULL REFERENCES tenants(id), sku TEXT NOT NULL,
          name TEXT NOT NULL, on_hand INTEGER NOT NULL CHECK(on_hand>=0),
          reserved INTEGER NOT NULL CHECK(reserved>=0 AND reserved<=on_hand),
          price_cents INTEGER NOT NULL CHECK(price_cents>=0),
          version INTEGER NOT NULL CHECK(version>=1), PRIMARY KEY(tenant,sku));
        CREATE TABLE IF NOT EXISTS orders (
          id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL REFERENCES tenants(id),
          client_ref TEXT NOT NULL, status TEXT NOT NULL,
          version INTEGER NOT NULL CHECK(version>=1), total_cents INTEGER NOT NULL,
          created_at TEXT NOT NULL, UNIQUE(tenant,client_ref));
        CREATE INDEX IF NOT EXISTS orders_tenant_id ON orders(tenant,id);
        CREATE TABLE IF NOT EXISTS order_lines (
          order_id INTEGER NOT NULL REFERENCES orders(id), sku TEXT NOT NULL,
          quantity INTEGER NOT NULL CHECK(quantity>0),
          unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0),
          returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(returned_quantity>=0 AND returned_quantity<=quantity),
          PRIMARY KEY(order_id,sku));
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL REFERENCES tenants(id),
          action TEXT NOT NULL, entity_id TEXT NOT NULL,
          actor TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant,id);
        CREATE TABLE IF NOT EXISTS idempotency (
          tenant TEXT NOT NULL REFERENCES tenants(id), key TEXT NOT NULL,
          fingerprint TEXT NOT NULL, status INTEGER NOT NULL,
          response TEXT NOT NULL, PRIMARY KEY(tenant,key));
        CREATE TABLE IF NOT EXISTS order_snapshots (
          id TEXT PRIMARY KEY, tenant TEXT NOT NULL REFERENCES tenants(id),
          filters TEXT NOT NULL, order_ids TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        con.execute("INSERT OR IGNORE INTO meta VALUES ('cursor_secret',?)", (secrets.token_hex(32),))
        if os.environ.get("SEED_DEMO") == "1" and con.execute("SELECT COUNT(*) FROM tenants").fetchone()[0] == 0:
            con.execute("BEGIN IMMEDIATE")
            try:
                for tenant in ("north", "south"):
                    con.execute("INSERT INTO tenants VALUES (?)", (tenant,))
                    for role in ("admin", "operator", "viewer"):
                        email = f"{role}@{tenant}.example"
                        salt = secrets.token_bytes(16)
                        digest = hashlib.pbkdf2_hmac("sha256", b"DepotDemo!2026", salt, 200000)
                        con.execute("INSERT INTO users VALUES (?,?,?,?,?)", (email, tenant, role, salt, digest))
                    for sku, name, qty, price in SKU_SEED:
                        con.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,1)", (tenant, sku, name, qty, 0, price))
                con.commit()
            except Exception:
                con.rollback()
                raise


def integer(value, name, minimum=None, maximum=None):
    if type(value) is not int or value < -MAX_SQL_INT or value > MAX_SQL_INT or (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        fail(400, "invalid_payload", f"{name} must be an integer" + (f" from {minimum} to {maximum}" if minimum is not None and maximum is not None else ""))
    return value


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        fail(400, "invalid_payload", f"{name} must be a nonempty string")
    return value.strip()


def object_payload(value):
    if not isinstance(value, dict):
        fail(400, "invalid_payload", "JSON body must be an object")
    return value


def lines_payload(value):
    if not isinstance(value, list) or not value:
        fail(400, "invalid_payload", "lines must be a nonempty array")
    found = set()
    result = []
    for line in value:
        if not isinstance(line, dict):
            fail(400, "invalid_payload", "each line must be an object")
        sku = nonempty(line.get("sku"), "sku")
        qty = integer(line.get("quantity"), "quantity", 1)
        if sku in found:
            fail(400, "invalid_payload", f"duplicate SKU: {sku}")
        found.add(sku)
        result.append((sku, qty))
    return result


def inventory_item(row):
    return {"sku": row["sku"], "name": row["name"], "on_hand": row["on_hand"],
            "reserved": row["reserved"], "available": row["on_hand"] - row["reserved"],
            "price_cents": row["price_cents"], "version": row["version"]}


def order_object(con, row):
    lines = con.execute("SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid", (row["id"],)).fetchall()
    return {"id": row["id"], "client_ref": row["client_ref"], "status": row["status"],
            "version": row["version"], "total_cents": row["total_cents"],
            "lines": [dict(line) for line in lines]}


def audit(con, tenant, action, entity_id, actor):
    con.execute("INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES (?,?,?,?,?)",
                (tenant, action, str(entity_id), actor, datetime.now(timezone.utc).isoformat()))


def create_order(con, tenant, actor, body):
    ref = nonempty(body.get("client_ref"), "client_ref")
    if len(ref) > 200:
        fail(400, "invalid_payload", "client_ref is too long")
    lines = lines_payload(body.get("lines"))
    if con.execute("SELECT 1 FROM orders WHERE tenant=? AND client_ref=?", (tenant, ref)).fetchone():
        fail(409, "client_ref_conflict", "client_ref already exists")
    prices = {}
    for sku, qty in lines:
        row = con.execute("SELECT price_cents FROM inventory WHERE tenant=? AND sku=?", (tenant, sku)).fetchone()
        if not row:
            fail(400, "unknown_sku", f"Unknown SKU: {sku}")
        prices[sku] = row["price_cents"]
    total = sum(qty * prices[sku] for sku, qty in lines)
    if total > MAX_SQL_INT:
        fail(400, "invalid_payload", "Order total is too large")
    cur = con.execute("INSERT INTO orders(tenant,client_ref,status,version,total_cents,created_at) VALUES (?,?,'draft',1,?,?)",
                      (tenant, ref, total, datetime.now(timezone.utc).isoformat()))
    order_id = cur.lastrowid
    for sku, qty in lines:
        con.execute("INSERT INTO order_lines(order_id,sku,quantity,unit_price_cents) VALUES (?,?,?,?)",
                    (order_id, sku, qty, prices[sku]))
    audit(con, tenant, "order_created", order_id, actor)
    return order_object(con, con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())


def adjust_stock(con, tenant, actor, body):
    sku = nonempty(body.get("sku"), "sku")
    delta = integer(body.get("delta"), "delta")
    if delta == 0:
        fail(400, "invalid_payload", "delta must be nonzero")
    expected = integer(body.get("expected_version"), "expected_version", 1)
    nonempty(body.get("reason"), "reason")
    row = con.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?", (tenant, sku)).fetchone()
    if not row:
        fail(400, "unknown_sku", f"Unknown SKU: {sku}")
    if row["version"] != expected:
        fail(409, "stale_version", "Inventory changed; refresh and try again")
    if row["on_hand"] + delta < row["reserved"]:
        fail(409, "insufficient_stock", "Adjustment would reduce stock below reserved units")
    if row["on_hand"] + delta > MAX_SQL_INT:
        fail(400, "invalid_payload", "Adjusted stock is too large")
    con.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?", (delta, tenant, sku))
    audit(con, tenant, "stock_adjusted", sku, actor)
    return inventory_item(con.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?", (tenant, sku)).fetchone())


def transition(con, tenant, actor, order_id, action, body):
    expected = integer(body.get("expected_version"), "expected_version", 1)
    row = con.execute("SELECT * FROM orders WHERE tenant=? AND id=?", (tenant, order_id)).fetchone()
    if not row:
        fail(404, "not_found", "Order not found")
    if row["version"] != expected:
        fail(409, "stale_version", "Order changed; refresh and try again")
    status = row["status"]
    lines = con.execute("SELECT * FROM order_lines WHERE order_id=? ORDER BY rowid", (order_id,)).fetchall()
    if action == "reserve":
        if status != "draft":
            fail(409, "invalid_transition", "Only a draft can be reserved")
        for line in lines:
            stock = con.execute("SELECT on_hand,reserved FROM inventory WHERE tenant=? AND sku=?", (tenant, line["sku"])).fetchone()
            if stock["on_hand"] - stock["reserved"] < line["quantity"]:
                fail(409, "insufficient_stock", f"Insufficient available stock for {line['sku']}")
        for line in lines:
            con.execute("UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?", (line["quantity"], tenant, line["sku"]))
        new_status = "reserved"
    elif action == "ship":
        if status != "reserved":
            fail(409, "invalid_transition", "Only a reserved order can be shipped")
        for line in lines:
            con.execute("UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?",
                        (line["quantity"], line["quantity"], tenant, line["sku"]))
        new_status = "shipped"
    elif action == "cancel":
        if status not in ("draft", "reserved"):
            fail(409, "invalid_transition", "Only a draft or reserved order can be cancelled")
        if status == "reserved":
            for line in lines:
                con.execute("UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?", (line["quantity"], tenant, line["sku"]))
        new_status = "cancelled"
    elif action == "returns":
        if status != "shipped":
            fail(409, "invalid_transition", "Only a shipped order can accept returns")
        requested = lines_payload(body.get("lines"))
        owned = {line["sku"]: line for line in lines}
        for sku, qty in requested:
            if sku not in owned:
                fail(400, "invalid_payload", f"SKU is not in this order: {sku}")
            if qty + owned[sku]["returned_quantity"] > owned[sku]["quantity"]:
                fail(409, "return_exceeds_shipped", f"Return exceeds shipped quantity for {sku}")
            stock = con.execute("SELECT on_hand FROM inventory WHERE tenant=? AND sku=?", (tenant, sku)).fetchone()
            if stock["on_hand"] + qty > MAX_SQL_INT:
                fail(409, "stock_capacity", f"Stock quantity limit reached for {sku}")
        for sku, qty in requested:
            con.execute("UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?", (qty, order_id, sku))
            con.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?", (qty, tenant, sku))
        all_lines = con.execute("SELECT quantity,returned_quantity FROM order_lines WHERE order_id=?", (order_id,)).fetchall()
        new_status = "returned" if all(line["quantity"] == line["returned_quantity"] for line in all_lines) else "shipped"
    else:
        fail(404, "not_found", "Endpoint not found")
    con.execute("UPDATE orders SET status=?,version=version+1 WHERE id=?", (new_status, order_id))
    audit(con, tenant, {"reserve": "order_reserved", "ship": "order_shipped", "cancel": "order_cancelled", "returns": "order_returned"}[action], order_id, actor)
    return order_object(con, con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())


def cursor_secret(con):
    return bytes.fromhex(con.execute("SELECT value FROM meta WHERE key='cursor_secret'").fetchone()[0])


def make_cursor(con, kind, after, maximum, filters):
    raw = json.dumps({"kind": kind, "after": after, "max": maximum, "filters": filters}, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(cursor_secret(con), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + sig).decode().rstrip("=")


def read_cursor(con, token, kind, filters):
    try:
        packed = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        raw, sig = packed[:-32], packed[-32:]
        if not hmac.compare_digest(sig, hmac.new(cursor_secret(con), raw, hashlib.sha256).digest()):
            raise ValueError()
        data = json.loads(raw)
        if data["kind"] != kind or data["filters"] != filters or type(data["after"]) is not int or type(data["max"]) is not int or data["after"] < 0 or data["max"] < data["after"]:
            raise ValueError()
        return data["after"], data["max"]
    except Exception:
        fail(400, "invalid_cursor", "Invalid cursor for these filters")


def make_order_cursor(con, snapshot_id, offset, filters):
    raw = json.dumps({"kind": "orders", "snapshot": snapshot_id, "offset": offset, "filters": filters}, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(cursor_secret(con), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + sig).decode().rstrip("=")


def read_order_cursor(con, token, tenant, filters):
    try:
        packed = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        raw, sig = packed[:-32], packed[-32:]
        if not hmac.compare_digest(sig, hmac.new(cursor_secret(con), raw, hashlib.sha256).digest()):
            raise ValueError()
        data = json.loads(raw)
        if data["kind"] != "orders" or data["filters"] != filters or type(data["offset"]) is not int or data["offset"] < 1 or not isinstance(data["snapshot"], str):
            raise ValueError()
        row = con.execute("SELECT order_ids FROM order_snapshots WHERE id=? AND tenant=? AND filters=?", (data["snapshot"], tenant, json.dumps(filters, sort_keys=True))).fetchone()
        if not row:
            raise ValueError()
        ids = json.loads(row["order_ids"])
        if data["offset"] >= len(ids):
            raise ValueError()
        return data["snapshot"], data["offset"], ids
    except Exception:
        fail(400, "invalid_cursor", "Invalid cursor for these filters")


def param(query, name, default=None):
    values = query.get(name)
    if values is None:
        return default
    if len(values) != 1:
        fail(400, "invalid_filter", f"Invalid {name}")
    return values[0]


def page_limit(query):
    value = param(query, "limit", "20")
    if len(value) > 3 or not re.fullmatch(r"[0-9]+", value or ""):
        fail(400, "invalid_filter", "limit must be from 1 to 100")
    return integer(int(value), "limit", 1, 100)


def list_orders(con, tenant, query):
    if set(query) - {"status", "q", "limit", "cursor"}:
        fail(400, "invalid_filter", "Unknown order filter")
    status = param(query, "status", "")
    q = param(query, "q", "")
    if status and status not in STATUSES:
        fail(400, "invalid_filter", "Invalid order status")
    if len(q) > 200:
        fail(400, "invalid_filter", "Search is too long")
    limit = page_limit(query)
    filters = {"status": status, "q": q.casefold()}
    token = param(query, "cursor")
    if "cursor" in query and not token:
        fail(400, "invalid_cursor", "Invalid cursor for these filters")
    if token:
        snapshot_id, offset, ids = read_order_cursor(con, token, tenant, filters)
    else:
        sql = "SELECT id FROM orders WHERE tenant=?"
        args = [tenant]
        if status:
            sql += " AND status=?"
            args.append(status)
        if q:
            sql += " AND instr(casefold(client_ref),?)>0"
            args.append(q.casefold())
        ids = [row["id"] for row in con.execute(sql + " ORDER BY id", args)]
        snapshot_id, offset = None, 0
        if len(ids) > limit:
            snapshot_id = secrets.token_hex(16)
            con.execute("INSERT INTO order_snapshots VALUES (?,?,?,?,?)", (snapshot_id, tenant, json.dumps(filters, sort_keys=True), json.dumps(ids), datetime.now(timezone.utc).isoformat()))
    page_ids = ids[offset:offset + limit]
    rows = [con.execute("SELECT * FROM orders WHERE tenant=? AND id=?", (tenant, order_id)).fetchone() for order_id in page_ids]
    next_offset = offset + len(page_ids)
    return {"items": [order_object(con, row) for row in rows],
            "next_cursor": make_order_cursor(con, snapshot_id, next_offset, filters) if next_offset < len(ids) else None}


def list_audit(con, tenant, query):
    if set(query) - {"limit", "cursor"}:
        fail(400, "invalid_filter", "Unknown audit filter")
    limit = page_limit(query)
    token = param(query, "cursor")
    if "cursor" in query and not token:
        fail(400, "invalid_cursor", "Invalid cursor")
    after, maximum = read_cursor(con, token, "audit", {}) if token else (0, con.execute("SELECT COALESCE(MAX(id),0) FROM audit WHERE tenant=?", (tenant,)).fetchone()[0])
    rows = con.execute("SELECT id,action,entity_id,actor,created_at FROM audit WHERE tenant=? AND id>? AND id<=? ORDER BY id LIMIT ?",
                       (tenant, after, maximum, limit + 1)).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {"items": [dict(row) for row in rows],
            "next_cursor": make_cursor(con, "audit", rows[-1]["id"], maximum, {}) if has_more else None}


class Handler(BaseHTTPRequestHandler):
    server_version = "DepotFlow/1.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def send_json(self, status, value):
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        if not self.headers.get("Content-Type", "").split(";")[0].strip() == "application/json":
            fail(400, "invalid_payload", "Content-Type must be application/json")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 1024 * 1024:
                raise ValueError()
            return object_payload(json.loads(self.rfile.read(size)))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            fail(400, "invalid_payload", "Invalid JSON body")

    def auth(self, con):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:]:
            fail(401, "unauthorized", "Sign in to continue")
        digest = hashlib.sha256(header[7:].encode()).hexdigest()
        row = con.execute("SELECT users.email,users.tenant,users.role FROM sessions JOIN users ON sessions.email=users.email WHERE sessions.token_hash=?", (digest,)).fetchone()
        if not row:
            fail(401, "unauthorized", "Session is invalid")
        return dict(row)

    def route(self):
        parts = urlsplit(self.path)
        path = parts.path
        query = parse_qs(parts.query, keep_blank_values=True)
        if self.command == "GET" and path == "/api/health":
            return self.send_json(200, {"status": "ok"})
        if self.command == "GET" and path in ("/", "/index.html", "/app.js", "/style.css"):
            name = "index.html" if path in ("/", "/index.html") else path[1:]
            raw = (ROOT / "static" / name).read_bytes()
            kind = "text/html" if name.endswith("html") else "text/css" if name.endswith("css") else "text/javascript"
            self.send_response(200)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            return self.wfile.write(raw)
        if self.command == "POST" and path == "/api/session":
            body = self.body()
            email, password = body.get("email"), body.get("password")
            if not isinstance(email, str) or not isinstance(password, str):
                fail(401, "bad_credentials", "Email or password is incorrect")
            with db() as con:
                row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if not row or not hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", password.encode(), row["salt"], 200000), row["password_hash"]):
                    fail(401, "bad_credentials", "Email or password is incorrect")
                token = secrets.token_urlsafe(32)
                con.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), email, datetime.now(timezone.utc).isoformat()))
                return self.send_json(200, {"token": token, "user": {"email": email, "role": row["role"], "tenant": row["tenant"]}})
        if not path.startswith("/api/"):
            fail(404, "not_found", "Endpoint not found")
        with db() as con:
            user = self.auth(con)
            tenant, actor = user["tenant"], user["email"]
            if self.command == "GET":
                if path == "/api/me":
                    result = user
                elif path == "/api/inventory":
                    result = {"items": [inventory_item(row) for row in con.execute("SELECT * FROM inventory WHERE tenant=? ORDER BY sku", (tenant,))]}
                elif path == "/api/orders":
                    result = list_orders(con, tenant, query)
                elif re.fullmatch(r"/api/orders/[0-9]{1,19}", path):
                    row = con.execute("SELECT * FROM orders WHERE tenant=? AND id=?", (tenant, int(path.rsplit("/", 1)[1]))).fetchone()
                    if not row:
                        fail(404, "not_found", "Order not found")
                    result = order_object(con, row)
                elif path == "/api/audit":
                    result = list_audit(con, tenant, query)
                elif path == "/api/dashboard":
                    counts = {row["status"]: row["n"] for row in con.execute("SELECT status,COUNT(*) n FROM orders WHERE tenant=? GROUP BY status", (tenant,))}
                    totals = con.execute("SELECT COALESCE(SUM(on_hand),0) stock,COALESCE(SUM(reserved),0) reserved FROM inventory WHERE tenant=?", (tenant,)).fetchone()
                    result = {"orders_by_status": counts, "inventory_units": totals["stock"], "reserved_units": totals["reserved"]}
                else:
                    fail(404, "not_found", "Endpoint not found")
                return self.send_json(200, result)
            if self.command != "POST":
                fail(404, "not_found", "Endpoint not found")
            match = re.fullmatch(r"/api/orders/([0-9]{1,19})/(reserve|ship|cancel|returns)", path)
            if path == "/api/stock/adjustments":
                if user["role"] != "admin":
                    fail(403, "forbidden", "Admin role required")
            elif path == "/api/orders" or match:
                if user["role"] == "viewer":
                    fail(403, "forbidden", "Viewer cannot change orders")
            else:
                fail(404, "not_found", "Endpoint not found")
            key = self.headers.get("Idempotency-Key", "")
            if not key.strip() or len(key) > 200:
                fail(400, "missing_idempotency_key", "Provide a nonempty Idempotency-Key (up to 200 characters)")
            body = self.body()
            fingerprint = hashlib.sha256(json.dumps([self.command, path, body], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            con.execute("BEGIN IMMEDIATE")
            try:
                saved = con.execute("SELECT fingerprint,status,response FROM idempotency WHERE tenant=? AND key=?", (tenant, key)).fetchone()
                if saved:
                    if saved["fingerprint"] != fingerprint:
                        fail(409, "idempotency_conflict", "Idempotency-Key was used for a different request")
                    result, status = json.loads(saved["response"]), saved["status"]
                else:
                    if path == "/api/stock/adjustments":
                        result, status = adjust_stock(con, tenant, actor, body), 200
                    elif path == "/api/orders":
                        result, status = create_order(con, tenant, actor, body), 201
                    else:
                        result, status = transition(con, tenant, actor, int(match.group(1)), match.group(2), body), 200
                    con.execute("INSERT INTO idempotency VALUES (?,?,?,?,?)", (tenant, key, fingerprint, status, json.dumps(result, separators=(",", ":"))))
                con.commit()
            except Exception:
                con.rollback()
                raise
            return self.send_json(status, result)

    def do_GET(self):
        self.handle_route()

    def do_POST(self):
        self.handle_route()

    def handle_route(self):
        try:
            self.route()
        except ApiError as error:
            self.send_json(error.status, {"error": {"code": error.code, "message": error.message}})
        except Exception:
            self.send_json(500, {"error": {"code": "internal_error", "message": "An internal error occurred"}})
            raise


class DepotHTTPServer(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


if __name__ == "__main__":
    initialize()
    port = int(os.environ.get("PORT", "8000"))
    print(f"DepotFlow listening on http://127.0.0.1:{port}", flush=True)
    DepotHTTPServer(("127.0.0.1", port), Handler).serve_forever()
