#!/usr/bin/env python3
"""DepotFlow: a small, single-process multi-tenant fulfillment service."""

from __future__ import annotations

import base64
import hashlib
import hmac
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
from urllib.parse import parse_qs, unquote, urlsplit


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data"))).expanduser()
DB_PATH = DATA_DIR / "depotflow.sqlite3"
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))
PASSWORD = "DepotDemo!2026"
MAX_DB_INT = 2**63 - 1
PRODUCTS = (
    ("BOLT", "Steel bolt kit", 100, 1250),
    ("CABLE", "Cable assembly", 60, 2499),
    ("SAMPLE", "Sample pack", 20, 0),
)
ROLES = {"admin", "operator", "viewer"}
STATUSES = {"draft", "reserved", "shipped", "cancelled", "returned"}


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.create_function("casefold", 1, lambda value: value.casefold() if isinstance(value, str) else "")
    return conn


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return f"{salt.hex()}:{value.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, AttributeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000).hex()
    return hmac.compare_digest(actual, digest_hex)


def initialize() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inventory (
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                on_hand INTEGER NOT NULL CHECK(on_hand >= 0),
                reserved INTEGER NOT NULL CHECK(reserved >= 0 AND reserved <= on_hand),
                price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                version INTEGER NOT NULL CHECK(version >= 1),
                PRIMARY KEY(tenant_id, sku)
            );
            CREATE TABLE IF NOT EXISTS orders (
                order_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                client_ref TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('draft','reserved','shipped','cancelled','returned')),
                version INTEGER NOT NULL CHECK(version >= 1),
                total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
                created_at TEXT NOT NULL,
                UNIQUE(tenant_id, client_ref)
            );
            CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant_id, order_seq);
            CREATE TABLE IF NOT EXISTS order_lines (
                tenant_id INTEGER NOT NULL,
                order_id TEXT NOT NULL REFERENCES orders(id),
                line_no INTEGER NOT NULL,
                sku TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
                returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(returned_quantity >= 0 AND returned_quantity <= quantity),
                PRIMARY KEY(order_id, sku),
                UNIQUE(order_id, line_no),
                FOREIGN KEY(tenant_id, sku) REFERENCES inventory(tenant_id, sku)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                action TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit_events(tenant_id, id);
            CREATE TABLE IF NOT EXISTS idempotency (
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                key TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                status INTEGER NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(tenant_id, key)
            );
            """
        )
        if os.environ.get("SEED_DEMO") == "1":
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0] == 0:
                for tenant in ("north", "south"):
                    cur = conn.execute("INSERT INTO tenants(slug) VALUES (?)", (tenant,))
                    tenant_id = cur.lastrowid
                    for sku, name, on_hand, price in PRODUCTS:
                        conn.execute(
                            "INSERT INTO inventory(tenant_id,sku,name,on_hand,reserved,price_cents,version) VALUES(?,?,?,?,?,?,1)",
                            (tenant_id, sku, name, on_hand, 0, price),
                        )
                    for role in ("admin", "operator", "viewer"):
                        conn.execute(
                            "INSERT INTO users(tenant_id,email,role,password_hash) VALUES(?,?,?,?)",
                            (tenant_id, f"{role}@{tenant}.example", role, password_hash(PASSWORD)),
                        )
            conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def parse_json(body: bytes) -> dict:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise APIError(400, "invalid_json", "Request body must be valid JSON.")
    if not isinstance(value, dict):
        raise APIError(400, "invalid_payload", "Request body must be a JSON object.")
    return value


def require_int(value, field: str, minimum: int | None = None, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value > MAX_DB_INT or value < -MAX_DB_INT - 1:
        raise APIError(400, "invalid_payload", f"{field} must be an integer.")
    if minimum is not None and value < minimum:
        raise APIError(400, "invalid_payload", f"{field} must be at least {minimum}.")
    if not allow_zero and minimum is not None and minimum == 1 and value < 1:
        raise APIError(400, "invalid_payload", f"{field} must be a positive integer.")
    return value


def inventory_item(conn: sqlite3.Connection, tenant_id: int, sku: str) -> dict | None:
    row = conn.execute(
        "SELECT sku,name,on_hand,reserved,price_cents,version FROM inventory WHERE tenant_id=? AND sku=?",
        (tenant_id, sku),
    ).fetchone()
    if row is None:
        return None
    return {
        "sku": row["sku"], "name": row["name"], "on_hand": row["on_hand"],
        "reserved": row["reserved"], "available": row["on_hand"] - row["reserved"],
        "price_cents": row["price_cents"], "version": row["version"],
    }


def order_object(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    lines = conn.execute(
        "SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE tenant_id=? AND order_id=? ORDER BY line_no",
        (row["tenant_id"], row["id"]),
    ).fetchall()
    return {
        "id": row["id"], "client_ref": row["client_ref"], "status": row["status"],
        "version": row["version"], "total_cents": row["total_cents"],
        "lines": [{"sku": x["sku"], "quantity": x["quantity"], "unit_price_cents": x["unit_price_cents"], "returned_quantity": x["returned_quantity"]} for x in lines],
    }


def get_order(conn: sqlite3.Connection, tenant_id: int, order_id: str) -> tuple[sqlite3.Row, dict]:
    row = conn.execute("SELECT * FROM orders WHERE tenant_id=? AND id=?", (tenant_id, order_id)).fetchone()
    if row is None:
        raise APIError(404, "not_found", "Order was not found.")
    return row, order_object(conn, row)


def add_audit(conn: sqlite3.Connection, user: dict, action: str, entity_id: str) -> None:
    conn.execute(
        "INSERT INTO audit_events(tenant_id,action,entity_id,actor,created_at) VALUES(?,?,?,?,?)",
        (user["tenant_id"], action, entity_id, user["email"], now_iso()),
    )


def check_expected(payload: dict) -> int:
    if "expected_version" not in payload:
        raise APIError(400, "invalid_payload", "expected_version is required.")
    return require_int(payload["expected_version"], "expected_version", 1)


def validate_lines(payload) -> list[dict]:
    if not isinstance(payload, list) or not payload:
        raise APIError(400, "invalid_payload", "lines must be a nonempty array.")
    result = []
    seen = set()
    for line in payload:
        if not isinstance(line, dict):
            raise APIError(400, "invalid_payload", "Each line must be an object.")
        sku = line.get("sku")
        if not isinstance(sku, str) or not sku.strip():
            raise APIError(400, "invalid_payload", "Each line needs a nonempty sku.")
        sku = sku.strip()
        if sku in seen:
            raise APIError(400, "invalid_payload", f"SKU {sku} appears more than once.")
        seen.add(sku)
        if "quantity" not in line:
            raise APIError(400, "invalid_payload", "Each line needs a positive integer quantity.")
        quantity = require_int(line["quantity"], "quantity", 1)
        result.append({"sku": sku, "quantity": quantity})
    return result


def create_order(conn: sqlite3.Connection, user: dict, payload: dict) -> tuple[int, dict]:
    ref = payload.get("client_ref")
    if not isinstance(ref, str) or not ref.strip():
        raise APIError(400, "invalid_payload", "client_ref must be a nonempty string.")
    ref = ref.strip()
    lines = validate_lines(payload.get("lines"))
    inventory = {}
    total = 0
    for line in lines:
        item = conn.execute(
            "SELECT name,price_cents FROM inventory WHERE tenant_id=? AND sku=?",
            (user["tenant_id"], line["sku"]),
        ).fetchone()
        if item is None:
            raise APIError(400, "unknown_sku", f"Unknown SKU: {line['sku']}.")
        line["price"] = item["price_cents"]
        total += item["price_cents"] * line["quantity"]
        if total > MAX_DB_INT:
            raise APIError(400, "invalid_payload", "Order total exceeds the supported integer range.")
        inventory[line["sku"]] = item
    if conn.execute("SELECT 1 FROM orders WHERE tenant_id=? AND client_ref=?", (user["tenant_id"], ref)).fetchone():
        raise APIError(409, "client_ref_conflict", "client_ref is already used by this tenant.")
    order_id = "ord_" + uuid.uuid4().hex
    try:
        conn.execute(
            "INSERT INTO orders(id,tenant_id,client_ref,status,version,total_cents,created_at) VALUES(?,?,?,'draft',1,?,?)",
            (order_id, user["tenant_id"], ref, total, now_iso()),
        )
    except sqlite3.IntegrityError:
        raise APIError(409, "client_ref_conflict", "client_ref is already used by this tenant.")
    for line_no, line in enumerate(lines):
        conn.execute(
            "INSERT INTO order_lines(tenant_id,order_id,line_no,sku,quantity,unit_price_cents,returned_quantity) VALUES(?,?,?,?,?,?,0)",
            (user["tenant_id"], order_id, line_no, line["sku"], line["quantity"], line["price"]),
        )
    row = conn.execute("SELECT * FROM orders WHERE tenant_id=? AND id=?", (user["tenant_id"], order_id)).fetchone()
    result = order_object(conn, row)
    add_audit(conn, user, "order.created", order_id)
    return 201, result


def stock_adjustment(conn: sqlite3.Connection, user: dict, payload: dict) -> tuple[int, dict]:
    sku = payload.get("sku")
    if not isinstance(sku, str) or not sku.strip():
        raise APIError(400, "invalid_payload", "sku must be a nonempty string.")
    sku = sku.strip()
    if "delta" not in payload:
        raise APIError(400, "invalid_payload", "delta is required.")
    delta = require_int(payload["delta"], "delta")
    if delta == 0:
        raise APIError(400, "invalid_payload", "delta must be nonzero.")
    expected = check_expected(payload)
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise APIError(400, "invalid_payload", "reason must be a nonempty string.")
    row = conn.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant_id"], sku)).fetchone()
    if row is None:
        raise APIError(400, "unknown_sku", f"Unknown SKU: {sku}.")
    if row["version"] != expected:
        raise APIError(409, "stale_version", "Inventory changed; reload it and retry with the current version.")
    next_hand = row["on_hand"] + delta
    if next_hand < row["reserved"]:
        raise APIError(409, "insufficient_stock", "Adjustment cannot reduce on_hand below reserved stock.")
    if next_hand > MAX_DB_INT:
        raise APIError(400, "invalid_payload", "Adjusted stock exceeds the supported integer range.")
    conn.execute("UPDATE inventory SET on_hand=?,version=version+1 WHERE tenant_id=? AND sku=?", (next_hand, user["tenant_id"], sku))
    add_audit(conn, user, "stock.adjusted", sku)
    return 200, inventory_item(conn, user["tenant_id"], sku)


def transition_order(conn: sqlite3.Connection, user: dict, order_id: str, action: str, payload: dict) -> tuple[int, dict]:
    expected = check_expected(payload)
    order, _ = get_order(conn, user["tenant_id"], order_id)
    if order["version"] != expected:
        raise APIError(409, "stale_version", "Order changed; reload it and retry with the current version.")
    lines = conn.execute("SELECT * FROM order_lines WHERE tenant_id=? AND order_id=? ORDER BY line_no", (user["tenant_id"], order_id)).fetchall()

    if action == "reserve":
        if order["status"] != "draft":
            raise APIError(409, "invalid_transition", "Only draft orders can be reserved.")
        stock_rows = {}
        for line in lines:
            stock = conn.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant_id"], line["sku"])).fetchone()
            available = stock["on_hand"] - stock["reserved"]
            if available < line["quantity"]:
                raise APIError(409, "insufficient_stock", f"Insufficient available stock for {line['sku']}.")
            stock_rows[line["sku"]] = stock
        for line in lines:
            stock = stock_rows[line["sku"]]
            conn.execute(
                "UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant_id=? AND sku=?",
                (line["quantity"], user["tenant_id"], line["sku"]),
            )
        new_status, audit_action = "reserved", "order.reserved"
    elif action == "ship":
        if order["status"] != "reserved":
            raise APIError(409, "invalid_transition", "Only reserved orders can be shipped.")
        for line in lines:
            conn.execute(
                "UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=?",
                (line["quantity"], line["quantity"], user["tenant_id"], line["sku"]),
            )
        new_status, audit_action = "shipped", "order.shipped"
    elif action == "cancel":
        if order["status"] not in ("draft", "reserved"):
            raise APIError(409, "invalid_transition", "Only draft or reserved orders can be cancelled.")
        if order["status"] == "reserved":
            for line in lines:
                conn.execute(
                    "UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=?",
                    (line["quantity"], user["tenant_id"], line["sku"]),
                )
        new_status, audit_action = "cancelled", "order.cancelled"
    elif action == "returns":
        if order["status"] != "shipped":
            raise APIError(409, "invalid_transition", "Returns are accepted only for shipped orders with units remaining.")
        requested = validate_lines(payload.get("lines"))
        line_map = {line["sku"]: line for line in lines}
        for request in requested:
            original = line_map.get(request["sku"])
            if original is None:
                raise APIError(400, "invalid_payload", f"SKU {request['sku']} is not on this order.")
            if original["returned_quantity"] + request["quantity"] > original["quantity"]:
                raise APIError(409, "return_quantity_exceeded", f"Return quantity exceeds shipped quantity for {request['sku']}.")
            stock = conn.execute("SELECT on_hand FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant_id"], request["sku"])).fetchone()
            if stock["on_hand"] + request["quantity"] > MAX_DB_INT:
                raise APIError(409, "inventory_capacity_exceeded", f"Inventory capacity would be exceeded for {request['sku']}.")
        for request in requested:
            conn.execute(
                "UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE tenant_id=? AND order_id=? AND sku=?",
                (request["quantity"], user["tenant_id"], order_id, request["sku"]),
            )
            conn.execute(
                "UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant_id=? AND sku=?",
                (request["quantity"], user["tenant_id"], request["sku"]),
            )
        all_lines = conn.execute("SELECT quantity,returned_quantity FROM order_lines WHERE tenant_id=? AND order_id=?", (user["tenant_id"], order_id)).fetchall()
        new_status = "returned" if all(x["returned_quantity"] == x["quantity"] for x in all_lines) else "shipped"
        audit_action = "order.returned"
    else:
        raise APIError(404, "not_found", "Unknown order action.")

    conn.execute("UPDATE orders SET status=?,version=version+1 WHERE tenant_id=? AND id=?", (new_status, user["tenant_id"], order_id))
    add_audit(conn, user, audit_action, order_id)
    updated = conn.execute("SELECT * FROM orders WHERE tenant_id=? AND id=?", (user["tenant_id"], order_id)).fetchone()
    return 200, order_object(conn, updated)


def decode_cursor(cursor: str | None, tenant_id: int, kind: str) -> int:
    if cursor is None:
        return 0
    if not cursor or len(cursor) > 80:
        raise APIError(400, "invalid_cursor", "cursor is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
    except Exception:
        raise APIError(400, "invalid_cursor", "cursor is invalid.")
    match = re.fullmatch(r"([1-9][0-9]*)\.(orders|audit)\.([1-9][0-9]*)", decoded)
    if not match or int(match.group(1)) != tenant_id or match.group(2) != kind:
        raise APIError(400, "invalid_cursor", "cursor is invalid.")
    value = int(match.group(3))
    if value > MAX_DB_INT or base64.urlsafe_b64encode(decoded.encode()).decode().rstrip("=") != cursor:
        raise APIError(400, "invalid_cursor", "cursor is invalid.")
    return value


def encode_cursor(value: int, tenant_id: int, kind: str) -> str:
    content = f"{tenant_id}.{kind}.{value}"
    return base64.urlsafe_b64encode(content.encode()).decode().rstrip("=")


class Handler(BaseHTTPRequestHandler):
    server_version = "DepotFlow/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET_HTTP") != "1":
            super().log_message(fmt, *args)

    def send_json(self, status: int, value: dict) -> None:
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, error: APIError) -> None:
        self.send_json(error.status, error.body())

    def read_payload(self) -> dict:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            raise APIError(400, "invalid_payload", "Content-Length must be an integer.")
        if length < 0 or length > 1_048_576:
            raise APIError(400, "invalid_payload", "Request body is too large.")
        return parse_json(self.rfile.read(length))

    def auth_user(self) -> dict:
        header = self.headers.get("Authorization", "")
        match = re.fullmatch(r"Bearer\s+([^\s]+)", header, flags=re.IGNORECASE)
        if not match:
            raise APIError(401, "unauthorized", "A valid bearer token is required.")
        token_hash = hashlib.sha256(match.group(1).encode()).hexdigest()
        conn = connect()
        try:
            row = conn.execute(
                "SELECT u.id,u.email,u.role,u.tenant_id,t.slug FROM sessions s JOIN users u ON u.id=s.user_id JOIN tenants t ON t.id=u.tenant_id WHERE s.token_hash=?",
                (token_hash,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise APIError(401, "unauthorized", "A valid bearer token is required.")
        return {"id": row["id"], "email": row["email"], "role": row["role"], "tenant_id": row["tenant_id"], "tenant": row["slug"]}

    def do_GET(self):  # noqa: N802
        try:
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if path == "/" or path in ("/index.html", "/app.js", "/styles.css"):
                self.serve_static(path)
                return
            if path == "/api/health":
                self.send_json(200, {"status": "ok"})
                return
            user = self.auth_user()
            conn = connect()
            try:
                conn.execute("BEGIN")
                if path == "/api/me":
                    self.send_json(200, {"email": user["email"], "role": user["role"], "tenant": user["tenant"]})
                elif path == "/api/inventory":
                    rows = conn.execute("SELECT sku FROM inventory WHERE tenant_id=? ORDER BY sku", (user["tenant_id"],)).fetchall()
                    self.send_json(200, {"items": [inventory_item(conn, user["tenant_id"], row["sku"]) for row in rows]})
                elif path == "/api/dashboard":
                    counts = {status: 0 for status in sorted(STATUSES)}
                    for row in conn.execute("SELECT status,COUNT(*) AS n FROM orders WHERE tenant_id=? GROUP BY status", (user["tenant_id"],)):
                        counts[row["status"]] = row["n"]
                    row = conn.execute("SELECT COALESCE(SUM(on_hand),0) AS units,COALESCE(SUM(reserved),0) AS reserved FROM inventory WHERE tenant_id=?", (user["tenant_id"],)).fetchone()
                    self.send_json(200, {"orders_by_status": counts, "inventory_units": row["units"], "reserved_units": row["reserved"]})
                elif path == "/api/orders":
                    self.get_orders(conn, user, parsed.query)
                elif path.startswith("/api/orders/") and "/" not in path[len("/api/orders/"):]:
                    _, order = get_order(conn, user["tenant_id"], path.rsplit("/", 1)[1])
                    self.send_json(200, order)
                elif path == "/api/audit":
                    self.get_audit(conn, user, parsed.query)
                else:
                    raise APIError(404, "not_found", "Route was not found.")
                conn.commit()
            finally:
                conn.close()
        except APIError as exc:
            self.send_error_json(exc)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            self.send_error_json(APIError(500, "internal_error", "The server could not complete the request."))

    def get_orders(self, conn: sqlite3.Connection, user: dict, query: str) -> None:
        params = parse_qs(query, keep_blank_values=True)
        unknown = set(params) - {"status", "q", "limit", "cursor"}
        if unknown:
            raise APIError(400, "invalid_filter", f"Unknown order filter: {sorted(unknown)[0]}.")
        for name in ("status", "q", "limit", "cursor"):
            if len(params.get(name, [])) > 1:
                raise APIError(400, "invalid_filter", f"{name} may be supplied only once.")
        status = params.get("status", [None])[0]
        if status is not None and status not in STATUSES:
            raise APIError(400, "invalid_filter", "status is not a supported order status.")
        q = params.get("q", [""])[0]
        if len(q) > 200:
            raise APIError(400, "invalid_filter", "q must be at most 200 characters.")
        limit_text = params.get("limit", ["20"])[0]
        if not re.fullmatch(r"[0-9]+", limit_text):
            raise APIError(400, "invalid_filter", "limit must be an integer from 1 to 100.")
        limit = int(limit_text)
        if limit < 1 or limit > 100:
            raise APIError(400, "invalid_filter", "limit must be an integer from 1 to 100.")
        after = decode_cursor(params.get("cursor", [None])[0], user["tenant_id"], "orders")
        clauses = ["tenant_id=?", "order_seq>?"]
        values: list = [user["tenant_id"], after]
        if status is not None:
            clauses.append("status=?")
            values.append(status)
        if q:
            clauses.append("instr(casefold(client_ref),casefold(?))>0")
            values.append(q)
        rows = conn.execute(
            f"SELECT * FROM orders WHERE {' AND '.join(clauses)} ORDER BY order_seq LIMIT ?",
            (*values, limit + 1),
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [order_object(conn, row) for row in rows]
        next_cursor = encode_cursor(rows[-1]["order_seq"], user["tenant_id"], "orders") if has_more and rows else None
        self.send_json(200, {"items": items, "next_cursor": next_cursor})

    def get_audit(self, conn: sqlite3.Connection, user: dict, query: str) -> None:
        params = parse_qs(query, keep_blank_values=True)
        unknown = set(params) - {"limit", "cursor"}
        if unknown:
            raise APIError(400, "invalid_filter", f"Unknown audit filter: {sorted(unknown)[0]}.")
        for name in ("limit", "cursor"):
            if len(params.get(name, [])) > 1:
                raise APIError(400, "invalid_filter", f"{name} may be supplied only once.")
        limit_text = params.get("limit", ["20"])[0]
        if not re.fullmatch(r"[0-9]+", limit_text) or not 1 <= int(limit_text) <= 100:
            raise APIError(400, "invalid_filter", "limit must be an integer from 1 to 100.")
        limit = int(limit_text)
        after = decode_cursor(params.get("cursor", [None])[0], user["tenant_id"], "audit")
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE tenant_id=? AND id>? ORDER BY id LIMIT ?",
            (user["tenant_id"], after, limit + 1),
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [{"id": r["id"], "action": r["action"], "entity_id": r["entity_id"], "actor": r["actor"], "created_at": r["created_at"]} for r in rows]
        next_cursor = encode_cursor(rows[-1]["id"], user["tenant_id"], "audit") if has_more and rows else None
        self.send_json(200, {"items": items, "next_cursor": next_cursor})

    def do_POST(self):  # noqa: N802
        try:
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if path == "/api/session":
                self.login()
                return
            if path == "/api/health":
                raise APIError(405, "method_not_allowed", "Use GET for this route.")
            match = re.fullmatch(r"/api/orders/([^/]+)/(reserve|ship|cancel|returns)", path)
            valid = path == "/api/orders" or path == "/api/stock/adjustments" or match is not None
            if not valid:
                raise APIError(404, "not_found", "Route was not found.")
            user = self.auth_user()
            action = "create" if path == "/api/orders" else "adjust" if path == "/api/stock/adjustments" else match.group(2)
            if user["role"] == "viewer" or (action == "adjust" and user["role"] != "admin"):
                raise APIError(403, "forbidden", "Your role cannot perform this mutation.")
            key = self.headers.get("Idempotency-Key")
            if key is None or not key.strip() or len(key.strip()) > 200:
                raise APIError(400, "idempotency_key_required", "A nonempty Idempotency-Key of at most 200 characters is required.")
            key = key.strip()
            payload = self.read_payload()
            if action == "create":
                fn = create_order
            elif action == "adjust":
                fn = stock_adjustment
            else:
                order_id = match.group(1)
                fn = lambda conn, user, body: transition_order(conn, user, order_id, action, body)
            status, response, replayed = self.run_idempotent(user, key, self.command, path, payload, fn)
            self.send_json(status, response)
        except APIError as exc:
            self.send_error_json(exc)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            self.send_error_json(APIError(500, "internal_error", "The server could not complete the request."))

    def run_idempotent(self, user: dict, key: str, method: str, path: str, payload: dict, operation):
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(f"{method}\n{path}\n{canonical}".encode()).hexdigest()
        conn = connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT fingerprint,status,response_json FROM idempotency WHERE tenant_id=? AND key=?", (user["tenant_id"], key)).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise APIError(409, "idempotency_conflict", "This Idempotency-Key was already used with a different method, path, or payload.")
                status = existing["status"]
                response = json.loads(existing["response_json"])
                conn.commit()
                return status, response, True
            status, response = operation(conn, user, payload)
            encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
            conn.execute(
                "INSERT INTO idempotency(tenant_id,key,fingerprint,status,response_json,created_at) VALUES(?,?,?,?,?,?)",
                (user["tenant_id"], key, fingerprint, status, encoded, now_iso()),
            )
            conn.commit()
            return status, response, False
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def login(self):
        payload = self.read_payload()
        email = payload.get("email")
        password = payload.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            raise APIError(401, "invalid_credentials", "Email or password is incorrect.")
        conn = connect()
        try:
            row = conn.execute(
                "SELECT u.id,u.email,u.role,u.password_hash,t.slug FROM users u JOIN tenants t ON t.id=u.tenant_id WHERE lower(u.email)=lower(?)",
                (email.strip(),),
            ).fetchone()
            if row is None or not verify_password(password, row["password_hash"]):
                raise APIError(401, "invalid_credentials", "Email or password is incorrect.")
            token = secrets.token_urlsafe(32)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO sessions(token_hash,user_id,created_at) VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], now_iso()))
            conn.commit()
        finally:
            conn.close()
        self.send_json(200, {"token": token, "user": {"email": row["email"], "role": row["role"], "tenant": row["slug"]}})

    def serve_static(self, path: str):
        names = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
        file = ROOT / "static" / names[path]
        content_type = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}[file.suffix]
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):  # noqa: N802
        if self.path in ("/", "/index.html", "/app.js", "/styles.css"):
            parsed = urlsplit(self.path)
            file = ROOT / "static" / {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}[parsed.path]
            self.send_response(200)
            self.send_header("Content-Length", str(file.stat().st_size))
            self.end_headers()
        else:
            self.send_json(404, {"error": {"code": "not_found", "message": "Route was not found."}})


def main() -> None:
    initialize()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"DepotFlow listening on http://{HOST}:{PORT} (database: {DB_PATH})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
