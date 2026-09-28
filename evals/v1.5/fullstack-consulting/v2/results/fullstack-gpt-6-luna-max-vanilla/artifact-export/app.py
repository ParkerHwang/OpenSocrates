#!/usr/bin/env python3
"""DepotFlow: a small, self-contained multi-tenant fulfillment service."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data"))).expanduser()
DB_PATH = DATA_DIR / "depotflow.sqlite3"
PASSWORD = "DepotDemo!2026"
ROLES = {"admin", "operator", "viewer"}
STATUSES = {"draft", "reserved", "shipped", "cancelled", "returned"}
CATALOG = [
    ("BOLT", "Steel bolt kit", 100, 1250),
    ("CABLE", "Cable assembly", 60, 2499),
    ("SAMPLE", "Sample pack", 20, 0),
]
MAX_DB_INTEGER = 9_223_372_036_854_775_807


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def fail(status: int, code: str, message: str):
    raise ApiError(status, code, message)


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
    salt BLOB NOT NULL,
    password_hash BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    on_hand INTEGER NOT NULL CHECK(typeof(on_hand) = 'integer' AND on_hand >= 0),
    reserved INTEGER NOT NULL CHECK(typeof(reserved) = 'integer' AND reserved >= 0 AND reserved <= on_hand),
    price_cents INTEGER NOT NULL CHECK(typeof(price_cents) = 'integer' AND price_cents >= 0),
    version INTEGER NOT NULL CHECK(typeof(version) = 'integer' AND version >= 1),
    PRIMARY KEY(tenant_id, sku)
);
CREATE TABLE IF NOT EXISTS orders (
    order_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    client_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','reserved','shipped','cancelled','returned')),
    version INTEGER NOT NULL CHECK(typeof(version) = 'integer' AND version >= 1),
    total_cents INTEGER NOT NULL CHECK(typeof(total_cents) = 'integer' AND total_cents >= 0),
    created_at TEXT NOT NULL,
    UNIQUE(tenant_id, client_ref)
);
CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant_id, order_seq);
CREATE TABLE IF NOT EXISTS order_lines (
    tenant_id TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(typeof(quantity) = 'integer' AND quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK(typeof(unit_price_cents) = 'integer' AND unit_price_cents >= 0),
    returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(typeof(returned_quantity) = 'integer' AND returned_quantity >= 0 AND returned_quantity <= quantity),
    PRIMARY KEY(tenant_id, order_id, sku)
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    action TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant_id, id);
CREATE TABLE IF NOT EXISTS idempotency (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    key TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, key)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.create_function("casefold", 1, lambda value: value.casefold() if value is not None else "")
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 160_000)


def initialize() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(SCHEMA)
        if os.environ.get("SEED_DEMO") == "1" and con.execute("SELECT COUNT(*) FROM tenants").fetchone()[0] == 0:
            con.execute("BEGIN IMMEDIATE")
            try:
                for tenant in ("north", "south"):
                    con.execute("INSERT INTO tenants(id) VALUES(?)", (tenant,))
                    for role in ("admin", "operator", "viewer"):
                        email = f"{role}@{tenant}.example"
                        salt = secrets.token_bytes(16)
                        con.execute(
                            "INSERT INTO users(tenant_id,email,role,salt,password_hash) VALUES(?,?,?,?,?)",
                            (tenant, email, role, salt, password_digest(PASSWORD, salt)),
                        )
                    for sku, name, quantity, price in CATALOG:
                        con.execute(
                            "INSERT INTO inventory(tenant_id,sku,name,on_hand,reserved,price_cents,version) VALUES(?,?,?,?,?,?,1)",
                            (tenant, sku, name, quantity, 0, price),
                        )
                con.commit()
            except Exception:
                con.rollback()
                raise
    finally:
        con.close()


def require_object(value):
    if not isinstance(value, dict):
        fail(400, "invalid_payload", "Request body must be a JSON object.")
    return value


def integer(value, field: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or (minimum is not None and value < minimum):
        suffix = f" at least {minimum}" if minimum is not None else ""
        fail(400, "invalid_payload", f"{field} must be an integer{suffix}.")
    if value < -MAX_DB_INTEGER or value > MAX_DB_INTEGER:
        fail(400, "invalid_payload", f"{field} is outside the supported integer range.")
    return value


def nonempty_string(value, field: str, max_length: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        fail(400, "invalid_payload", f"{field} must be a nonempty string of at most {max_length} characters.")
    return value.strip()


def inventory_item(row: sqlite3.Row) -> dict:
    return {
        "sku": row["sku"], "name": row["name"], "on_hand": row["on_hand"],
        "reserved": row["reserved"], "available": row["on_hand"] - row["reserved"],
        "price_cents": row["price_cents"], "version": row["version"],
    }


def get_order(con: sqlite3.Connection, tenant: str, order_id: str) -> dict:
    row = con.execute("SELECT * FROM orders WHERE tenant_id=? AND id=?", (tenant, order_id)).fetchone()
    if row is None:
        fail(404, "not_found", "Order not found.")
    lines = con.execute(
        "SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE tenant_id=? AND order_id=? ORDER BY rowid",
        (tenant, order_id),
    ).fetchall()
    return {
        "id": row["id"], "client_ref": row["client_ref"], "status": row["status"],
        "version": row["version"], "total_cents": row["total_cents"],
        "lines": [dict(line) for line in lines],
    }


def add_audit(con: sqlite3.Connection, tenant: str, action: str, entity_id: str, actor: str) -> None:
    con.execute(
        "INSERT INTO audit(tenant_id,action,entity_id,actor,created_at) VALUES(?,?,?,?,?)",
        (tenant, action, entity_id, actor, now_iso()),
    )


def require_expected(body: dict) -> int:
    if "expected_version" not in body:
        fail(400, "invalid_payload", "expected_version is required.")
    return integer(body["expected_version"], "expected_version", 1)


def check_version(actual: int, expected: int) -> None:
    if actual != expected:
        fail(409, "stale_version", "The record changed. Refresh it and try again.")
    if actual == MAX_DB_INTEGER:
        fail(409, "version_exhausted", "The record version can no longer be incremented.")


def check_incrementable_inventory(version: int) -> None:
    if version >= MAX_DB_INTEGER:
        fail(409, "version_exhausted", "An inventory version can no longer be incremented.")


def validate_lines(raw, con: sqlite3.Connection, tenant: str) -> list[tuple[str, int, int]]:
    if not isinstance(raw, list) or not raw:
        fail(400, "invalid_payload", "lines must be a nonempty array.")
    seen = set()
    lines = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            fail(400, "invalid_payload", f"lines[{index}] must be an object.")
        sku = nonempty_string(item.get("sku"), f"lines[{index}].sku", 64)
        qty = integer(item.get("quantity"), f"lines[{index}].quantity", 1)
        if sku in seen:
            fail(400, "invalid_payload", f"Duplicate SKU {sku} in lines.")
        seen.add(sku)
        row = con.execute("SELECT price_cents FROM inventory WHERE tenant_id=? AND sku=?", (tenant, sku)).fetchone()
        if row is None:
            fail(400, "unknown_sku", f"Unknown SKU {sku}.")
        lines.append((sku, qty, row["price_cents"]))
    return lines


class DepotHandler(BaseHTTPRequestHandler):
    server_version = "DepotFlow/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        # Keep local runs quiet; errors are returned as structured JSON.
        return

    def send_json(self, status: int, data: dict):
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, name: str, content_type: str):
        raw = (ROOT / "static" / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(raw)

    def authenticate(self, con: sqlite3.Connection):
        auth = self.headers.get("Authorization", "")
        match = re.fullmatch(r"Bearer\s+(\S+)", auth, re.IGNORECASE)
        if not match:
            fail(401, "unauthorized", "A valid Bearer token is required.")
        row = con.execute(
            "SELECT u.id,u.email,u.role,u.tenant_id FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
            (match.group(1),),
        ).fetchone()
        if row is None:
            fail(401, "unauthorized", "A valid Bearer token is required.")
        return row

    def read_body(self):
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            fail(400, "invalid_payload", "Content-Length is required.")
        try:
            length = int(raw_length)
            if length < 0 or length > 1_000_000:
                raise ValueError()
            raw = self.rfile.read(length)
            value = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            fail(400, "invalid_json", "Request body must contain valid JSON.")
        return require_object(value)

    def query(self):
        parsed = parse_qs(urlsplit(self.path).query, keep_blank_values=True, strict_parsing=False)
        return {key: values[-1] for key, values in parsed.items()}

    def dispatch(self):
        path = urlsplit(self.path).path
        if self.command == "GET" and path == "/":
            return self.send_file("index.html", "text/html; charset=utf-8")
        if self.command == "GET" and path == "/app.js":
            return self.send_file("app.js", "text/javascript; charset=utf-8")
        if self.command == "GET" and path == "/styles.css":
            return self.send_file("styles.css", "text/css; charset=utf-8")

        if self.command == "GET" and path == "/api/health":
            return self.send_json(200, {"status": "ok"})

        con = connect()
        try:
            # Authentication happens before replay and before protected route handling.
            if self.command == "POST" and path == "/api/session":
                body = self.read_body()
                return self.create_session(con, body)
            user = self.authenticate(con)
            tenant, actor, role = user["tenant_id"], user["email"], user["role"]

            if self.command == "GET":
                query = self.query()
                if path == "/api/me":
                    return self.send_json(200, {"email": actor, "role": role, "tenant": tenant})
                if path == "/api/inventory":
                    rows = con.execute("SELECT * FROM inventory WHERE tenant_id=? ORDER BY sku", (tenant,)).fetchall()
                    return self.send_json(200, {"items": [inventory_item(row) for row in rows]})
                if path == "/api/dashboard":
                    counts = {status: 0 for status in STATUSES}
                    for row in con.execute("SELECT status,COUNT(*) n FROM orders WHERE tenant_id=? GROUP BY status", (tenant,)):
                        counts[row["status"]] = row["n"]
                    stock_rows = con.execute("SELECT on_hand,reserved FROM inventory WHERE tenant_id=?", (tenant,)).fetchall()
                    return self.send_json(200, {"orders_by_status": counts, "inventory_units": sum(row["on_hand"] for row in stock_rows), "reserved_units": sum(row["reserved"] for row in stock_rows)})
                if path == "/api/orders":
                    return self.list_orders(con, tenant, query)
                match = re.fullmatch(r"/api/orders/([^/]+)", path)
                if match:
                    return self.send_json(200, get_order(con, tenant, match.group(1)))
                if path == "/api/audit":
                    return self.list_audit(con, tenant, query)
                fail(404, "not_found", "Route not found.")

            if self.command != "POST":
                fail(405, "method_not_allowed", "This method is not supported.")

            admin_only = path == "/api/stock/adjustments"
            if role == "viewer" or (admin_only and role != "admin"):
                fail(403, "forbidden", "Your role cannot perform this change.")
            body = self.read_body()
            if path != "/api/session":
                return self.mutate(con, tenant, actor, role, path, body)
            fail(404, "not_found", "Route not found.")
        finally:
            con.close()

    def create_session(self, con: sqlite3.Connection, body: dict):
        email = nonempty_string(body.get("email"), "email", 254).lower()
        password = body.get("password")
        if not isinstance(password, str):
            fail(400, "invalid_payload", "password must be a string.")
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row is None or not secrets.compare_digest(password_digest(password, row["salt"]), row["password_hash"]):
            fail(401, "bad_credentials", "Email or password is incorrect.")
        token = secrets.token_urlsafe(32)
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (token, row["id"], now_iso()))
        con.commit()
        return self.send_json(200, {"token": token, "user": {"email": row["email"], "role": row["role"], "tenant": row["tenant_id"]}})

    def cursor_limit(self, query: dict) -> tuple[int, int | None]:
        raw_limit = query.get("limit", "20")
        if not re.fullmatch(r"[0-9]+", raw_limit):
            fail(400, "invalid_query", "limit must be an integer from 1 to 100.")
        limit = int(raw_limit)
        if not 1 <= limit <= 100:
            fail(400, "invalid_query", "limit must be an integer from 1 to 100.")
        cursor = None
        if "cursor" in query:
            raw_cursor = query["cursor"]
            if not re.fullmatch(r"[0-9]+", raw_cursor):
                fail(400, "invalid_cursor", "cursor must be a nonnegative integer.")
            cursor = int(raw_cursor)
        return limit, cursor

    def list_orders(self, con, tenant, query):
        limit, cursor = self.cursor_limit(query)
        status = query.get("status")
        if status is not None and status not in STATUSES:
            fail(400, "invalid_query", "status is not a valid order status.")
        q = query.get("q", "")
        if len(q) > 200:
            fail(400, "invalid_query", "q must be at most 200 characters.")
        params = [tenant]
        where = "tenant_id=?"
        if status is not None:
            where += " AND status=?"
            params.append(status)
        if cursor is not None:
            max_seq = con.execute("SELECT COALESCE(MAX(order_seq),0) FROM orders WHERE tenant_id=?", (tenant,)).fetchone()[0]
            if cursor > max_seq:
                fail(400, "invalid_cursor", "cursor is not valid for this tenant.")
            where += " AND order_seq>?"
            params.append(cursor)
        if q:
            where += " AND instr(casefold(client_ref),?)>0"
            params.append(q.casefold())
        page = con.execute(f"SELECT * FROM orders WHERE {where} ORDER BY order_seq ASC LIMIT ?", (*params, limit + 1)).fetchall()
        has_more = len(page) > limit
        page = page[:limit]
        items = [get_order(con, tenant, row["id"]) for row in page]
        next_cursor = str(page[-1]["order_seq"]) if has_more and page else None
        return self.send_json(200, {"items": items, "next_cursor": next_cursor})

    def list_audit(self, con, tenant, query):
        limit, cursor = self.cursor_limit(query)
        params = [tenant]
        where = "tenant_id=?"
        if cursor is not None:
            max_id = con.execute("SELECT COALESCE(MAX(id),0) FROM audit").fetchone()[0]
            if cursor > max_id:
                fail(400, "invalid_cursor", "cursor is not valid.")
            where += " AND id>?"
            params.append(cursor)
        rows = con.execute(f"SELECT * FROM audit WHERE {where} ORDER BY id ASC LIMIT ?", (*params, limit + 1)).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [{"id": row["id"], "action": row["action"], "entity_id": row["entity_id"], "actor": row["actor"], "created_at": row["created_at"]} for row in rows]
        return self.send_json(200, {"items": items, "next_cursor": str(rows[-1]["id"]) if has_more and rows else None})

    def mutate(self, con, tenant, actor, role, path, body):
        key = self.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 200:
            fail(400, "idempotency_key_required", "A nonempty Idempotency-Key of at most 200 characters is required.")
        method = self.command
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        con.execute("BEGIN IMMEDIATE")
        try:
            previous = con.execute("SELECT * FROM idempotency WHERE tenant_id=? AND key=?", (tenant, key)).fetchone()
            if previous is not None:
                if previous["method"] != method or previous["path"] != path or previous["payload_hash"] != digest:
                    fail(409, "idempotency_conflict", "This idempotency key was already used for a different request.")
                con.commit()
                return self.send_json(previous["response_status"], json.loads(previous["response_json"]))

            status, result = self.perform_mutation(con, tenant, actor, role, path, body)
            con.execute(
                "INSERT INTO idempotency(tenant_id,key,method,path,payload_hash,response_status,response_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (tenant, key, method, path, digest, status, json.dumps(result, separators=(",", ":"), ensure_ascii=False), now_iso()),
            )
            con.commit()
            return self.send_json(status, result)
        except Exception:
            if con.in_transaction:
                con.rollback()
            raise

    def perform_mutation(self, con, tenant, actor, role, path, body):
        if path == "/api/orders":
            client_ref = nonempty_string(body.get("client_ref"), "client_ref", 160)
            lines = validate_lines(body.get("lines"), con, tenant)
            total = sum(qty * price for _, qty, price in lines)
            if total > MAX_DB_INTEGER:
                fail(400, "invalid_payload", "Order total exceeds the supported integer range.")
            if con.execute("SELECT 1 FROM orders WHERE tenant_id=? AND client_ref=?", (tenant, client_ref)).fetchone():
                fail(409, "duplicate_client_ref", "client_ref is already in use for this tenant.")
            order_id = str(uuid.uuid4())
            con.execute(
                "INSERT INTO orders(id,tenant_id,client_ref,status,version,total_cents,created_at) VALUES(?,?,?,'draft',1,?,?)",
                (order_id, tenant, client_ref, total, now_iso()),
            )
            for sku, qty, price in lines:
                con.execute("INSERT INTO order_lines(tenant_id,order_id,sku,quantity,unit_price_cents) VALUES(?,?,?,?,?)", (tenant, order_id, sku, qty, price))
            add_audit(con, tenant, "order.created", order_id, actor)
            return 201, get_order(con, tenant, order_id)

        if path == "/api/stock/adjustments":
            if role != "admin":
                fail(403, "forbidden", "Only admins can adjust stock.")
            sku = nonempty_string(body.get("sku"), "sku", 64)
            delta = integer(body.get("delta"), "delta")
            if delta == 0:
                fail(400, "invalid_payload", "delta must not be zero.")
            expected = require_expected(body)
            reason = nonempty_string(body.get("reason"), "reason", 500)
            row = con.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (tenant, sku)).fetchone()
            if row is None:
                fail(400, "unknown_sku", f"Unknown SKU {sku}.")
            check_version(row["version"], expected)
            if row["on_hand"] + delta < row["reserved"]:
                fail(409, "insufficient_stock", "Adjustment would reduce on-hand below reserved stock.")
            if row["on_hand"] + delta > MAX_DB_INTEGER:
                fail(400, "invalid_payload", "Adjustment exceeds the supported stock range.")
            con.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant_id=? AND sku=?", (delta, tenant, sku))
            add_audit(con, tenant, f"stock.adjusted ({reason})", sku, actor)
            item = con.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (tenant, sku)).fetchone()
            return 200, inventory_item(item)

        match = re.fullmatch(r"/api/orders/([^/]+)/(reserve|ship|cancel|returns)", path)
        if not match:
            fail(404, "not_found", "Route not found.")
        order_id, action = match.groups()
        order = con.execute("SELECT * FROM orders WHERE tenant_id=? AND id=?", (tenant, order_id)).fetchone()
        if order is None:
            fail(404, "not_found", "Order not found.")
        expected = require_expected(body)
        check_version(order["version"], expected)
        lines = con.execute("SELECT * FROM order_lines WHERE tenant_id=? AND order_id=? ORDER BY rowid", (tenant, order_id)).fetchall()

        if action == "reserve":
            if order["status"] != "draft":
                fail(409, "invalid_transition", "Only draft orders can be reserved.")
            # Validate every line before changing any stock; the surrounding IMMEDIATE transaction serializes reservations.
            stock = []
            for line in lines:
                row = con.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (tenant, line["sku"])).fetchone()
                if row is None:
                    fail(409, "insufficient_stock", f"Inventory is unavailable for {line['sku']}.")
                check_incrementable_inventory(row["version"])
                if row["on_hand"] - row["reserved"] < line["quantity"]:
                    fail(409, "insufficient_stock", f"Insufficient available stock for {line['sku']}.")
                stock.append((row, line["quantity"]))
            for row, qty in stock:
                con.execute("UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant_id=? AND sku=?", (qty, tenant, row["sku"]))
            new_status = "reserved"
        elif action == "ship":
            if order["status"] != "reserved":
                fail(409, "invalid_transition", "Only reserved orders can be shipped.")
            for line in lines:
                row = con.execute("SELECT on_hand,reserved,version FROM inventory WHERE tenant_id=? AND sku=?", (tenant, line["sku"])).fetchone()
                if row is None or row["on_hand"] < line["quantity"] or row["reserved"] < line["quantity"]:
                    fail(409, "insufficient_stock", f"Reserved stock is unavailable for {line['sku']}.")
                check_incrementable_inventory(row["version"])
            for line in lines:
                con.execute("UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=?", (line["quantity"], line["quantity"], tenant, line["sku"]))
            new_status = "shipped"
        elif action == "cancel":
            if order["status"] not in ("draft", "reserved"):
                fail(409, "invalid_transition", "Only draft or reserved orders can be cancelled.")
            if order["status"] == "reserved":
                for line in lines:
                    row = con.execute("SELECT reserved,version FROM inventory WHERE tenant_id=? AND sku=?", (tenant, line["sku"])).fetchone()
                    if row is None or row["reserved"] < line["quantity"]:
                        fail(409, "invalid_state", f"Reserved stock is unavailable for {line['sku']}.")
                    check_incrementable_inventory(row["version"])
                for line in lines:
                    con.execute("UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=?", (line["quantity"], tenant, line["sku"]))
            new_status = "cancelled"
        else:
            if order["status"] != "shipped":
                fail(409, "invalid_transition", "Only shipped orders can be returned.")
            raw_lines = body.get("lines")
            if not isinstance(raw_lines, list) or not raw_lines:
                fail(400, "invalid_payload", "lines must be a nonempty array.")
            shipped = {line["sku"]: line for line in lines}
            seen = set()
            requested = []
            for index, raw in enumerate(raw_lines):
                if not isinstance(raw, dict):
                    fail(400, "invalid_payload", f"lines[{index}] must be an object.")
                sku = nonempty_string(raw.get("sku"), f"lines[{index}].sku", 64)
                qty = integer(raw.get("quantity"), f"lines[{index}].quantity", 1)
                if sku in seen:
                    fail(400, "invalid_payload", f"Duplicate SKU {sku} in returns.")
                seen.add(sku)
                if sku not in shipped:
                    fail(400, "invalid_payload", f"SKU {sku} is not part of this order.")
                line = shipped[sku]
                if line["returned_quantity"] + qty > line["quantity"]:
                    fail(409, "return_limit", f"Return quantity exceeds shipped quantity for {sku}.")
                requested.append((sku, qty, line["returned_quantity"] + qty, line["quantity"]))
            for sku, qty, returned, _ in requested:
                stock_row = con.execute("SELECT on_hand,version FROM inventory WHERE tenant_id=? AND sku=?", (tenant, sku)).fetchone()
                if stock_row is None:
                    fail(409, "invalid_state", f"Inventory is unavailable for {sku}.")
                check_incrementable_inventory(stock_row["version"])
                if stock_row["on_hand"] + qty > MAX_DB_INTEGER:
                    fail(409, "stock_range_exceeded", f"Returning {sku} would exceed the supported stock range.")
            for sku, qty, returned, _ in requested:
                con.execute("UPDATE order_lines SET returned_quantity=? WHERE tenant_id=? AND order_id=? AND sku=?", (returned, tenant, order_id, sku))
                con.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant_id=? AND sku=?", (qty, tenant, sku))
            updated = {sku: returned for sku, _, returned, _ in requested}
            complete = all(updated.get(line["sku"], line["returned_quantity"]) == line["quantity"] for line in lines)
            new_status = "returned" if complete else "shipped"

        con.execute("UPDATE orders SET status=?,version=version+1 WHERE tenant_id=? AND id=?", (new_status, tenant, order_id))
        add_audit(con, tenant, f"order.{action}", order_id, actor)
        return 200, get_order(con, tenant, order_id)

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_PUT(self):
        self.handle_request()

    def do_PATCH(self):
        self.handle_request()

    def do_DELETE(self):
        self.handle_request()

    def handle_request(self):
        try:
            self.dispatch()
        except ApiError as err:
            self.send_json(err.status, {"error": {"code": err.code, "message": err.message}})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            # Avoid leaking database paths or implementation details to clients.
            self.send_json(500, {"error": {"code": "internal_error", "message": "The request could not be completed."}})


class DepotHTTPServer(ThreadingHTTPServer):
    # A wider accept queue prevents short bursts from being refused while worker threads start.
    request_queue_size = 256
    daemon_threads = True


def main():
    initialize()
    port = int(os.environ.get("PORT", "8000"))
    server = DepotHTTPServer(("127.0.0.1", port), DepotHandler)
    print(f"DepotFlow listening on http://127.0.0.1:{port} (data: {DB_PATH})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
