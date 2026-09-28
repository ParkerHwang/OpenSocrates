#!/usr/bin/env python3
"""DepotFlow: a small, dependency-free fulfillment service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
DB_PATH = DATA_DIR / "depotflow.sqlite3"
PORT = int(os.environ.get("PORT", "8080"))
SEED_DEMO = os.environ.get("SEED_DEMO") == "1"
PASSWORD = "DepotDemo!2026"

TOKENS: dict[str, dict[str, str]] = {}
TOKENS_LOCK = threading.Lock()


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def json_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8")


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return salt.hex() + ":" + digest.hex()


def password_matches(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def require_dict(value: object) -> dict:
    if not isinstance(value, dict):
        raise AppError(400, "invalid_payload", "JSON body must be an object")
    return value


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def require_int(value: object, name: str, positive: bool = False) -> int:
    if not is_int(value) or (positive and value <= 0):
        qualifier = "positive integer" if positive else "integer"
        raise AppError(400, "invalid_payload", f"{name} must be a {qualifier}")
    return int(value)


def require_nonempty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(400, "invalid_payload", f"{name} must be a non-empty string")
    return value.strip()


def encode_cursor(value: object) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> object:
    try:
        padded = value + "=" * (-len(value) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, UnicodeError, json.JSONDecodeError):
        raise AppError(400, "invalid_cursor", "cursor is invalid")


class Store:
    def __init__(self, path: Path):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def initialize(self) -> None:
        conn = self.connect()
        try:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin','operator','viewer')),
                    tenant TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    tenant TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    on_hand INTEGER NOT NULL CHECK (on_hand >= 0),
                    reserved INTEGER NOT NULL CHECK (reserved >= 0),
                    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
                    version INTEGER NOT NULL CHECK (version >= 1),
                    PRIMARY KEY (tenant, sku)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    tenant TEXT NOT NULL,
                    client_ref TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('draft','reserved','shipped','cancelled','returned')),
                    version INTEGER NOT NULL CHECK (version >= 1),
                    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
                    created_at TEXT NOT NULL,
                    UNIQUE (tenant, client_ref)
                );
                CREATE TABLE IF NOT EXISTS order_lines (
                    tenant TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    line_no INTEGER NOT NULL,
                    sku TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
                    returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK (returned_quantity >= 0),
                    PRIMARY KEY (tenant, order_id, line_no),
                    UNIQUE (tenant, order_id, sku),
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    tenant TEXT NOT NULL,
                    idem_key TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant, idem_key)
                );
                CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant, id);
                CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant, seq);
                """
            )
            if SEED_DEMO and all(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0 for table in ("users", "inventory", "orders", "audit", "idempotency")):
                seed(conn)
        finally:
            conn.close()


def seed(conn: sqlite3.Connection) -> None:
    catalog = [
        ("BOLT", "Steel bolt kit", 100, 1250),
        ("CABLE", "Cable assembly", 60, 2499),
        ("SAMPLE", "Sample pack", 20, 0),
    ]
    for tenant in ("north", "south"):
        for role in ("admin", "operator", "viewer"):
            email = f"{role}@{tenant}.example"
            conn.execute(
                "INSERT INTO users(email,password_hash,role,tenant) VALUES (?,?,?,?)",
                (email, password_hash(PASSWORD), role, tenant),
            )
        for sku, name, on_hand, price in catalog:
            conn.execute(
                "INSERT INTO inventory(tenant,sku,name,on_hand,reserved,price_cents,version) VALUES (?,?,?,?,?,?,1)",
                (tenant, sku, name, on_hand, 0, price),
            )


STORE = Store(DB_PATH)


def public_user(row: sqlite3.Row | dict) -> dict[str, str]:
    return {"email": row["email"], "role": row["role"], "tenant": row["tenant"]}


def inventory_item(row: sqlite3.Row) -> dict:
    return {
        "sku": row["sku"],
        "name": row["name"],
        "on_hand": int(row["on_hand"]),
        "reserved": int(row["reserved"]),
        "available": int(row["on_hand"] - row["reserved"]),
        "price_cents": int(row["price_cents"]),
        "version": int(row["version"]),
    }


def order_json(conn: sqlite3.Connection, tenant: str, order_id: str) -> dict:
    row = conn.execute(
        "SELECT id,client_ref,status,version,total_cents FROM orders WHERE tenant=? AND id=?",
        (tenant, order_id),
    ).fetchone()
    if row is None:
        raise AppError(404, "not_found", "order not found")
    lines = conn.execute(
        "SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE tenant=? AND order_id=? ORDER BY line_no",
        (tenant, order_id),
    ).fetchall()
    return {
        "id": row["id"],
        "client_ref": row["client_ref"],
        "status": row["status"],
        "version": int(row["version"]),
        "total_cents": int(row["total_cents"]),
        "lines": [
            {
                "sku": line["sku"],
                "quantity": int(line["quantity"]),
                "unit_price_cents": int(line["unit_price_cents"]),
                "returned_quantity": int(line["returned_quantity"]),
            }
            for line in lines
        ],
    }


def add_audit(conn: sqlite3.Connection, tenant: str, action: str, entity_id: str, actor: str) -> None:
    conn.execute(
        "INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES (?,?,?,?,?)",
        (tenant, action, entity_id, actor, now_iso()),
    )


def check_expected(actual: int, body: dict) -> None:
    expected = require_int(body.get("expected_version"), "expected_version")
    if expected != actual:
        raise AppError(409, "stale_version", "expected_version does not match the current version")


def parse_order_lines(body: dict) -> list[tuple[str, int]]:
    lines = body.get("lines")
    if not isinstance(lines, list) or not lines:
        raise AppError(400, "invalid_payload", "lines must be a non-empty array")
    result: list[tuple[str, int]] = []
    seen: set[str] = set()
    for line in lines:
        if not isinstance(line, dict):
            raise AppError(400, "invalid_payload", "each line must be an object")
        sku = require_nonempty_string(line.get("sku"), "line.sku")
        quantity = require_int(line.get("quantity"), "line.quantity", positive=True)
        if sku in seen:
            raise AppError(400, "invalid_payload", "duplicate SKU lines are not allowed")
        seen.add(sku)
        result.append((sku, quantity))
    return result


def perform_mutation(
    user: dict[str, str], method: str, path: str, idem_key: str, body: dict, callback
) -> tuple[int, object]:
    if not idem_key.strip():
        raise AppError(400, "missing_idempotency_key", "Idempotency-Key is required for mutations")
    payload_hash = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    conn = STORE.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute(
            "SELECT method,path,payload_hash,status_code,response_json FROM idempotency WHERE tenant=? AND idem_key=?",
            (user["tenant"], idem_key),
        ).fetchone()
        if previous:
            if (
                previous["method"] != method
                or previous["path"] != path
                or previous["payload_hash"] != payload_hash
            ):
                raise AppError(409, "idempotency_conflict", "Idempotency-Key was already used with different request data")
            conn.rollback()
            return int(previous["status_code"]), json.loads(previous["response_json"])
        status, result = callback(conn)
        conn.execute(
            "INSERT INTO idempotency(tenant,idem_key,method,path,payload_hash,status_code,response_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (user["tenant"], idem_key, method, path, payload_hash, status, json.dumps(result, separators=(",", ":")), now_iso()),
        )
        conn.commit()
        return status, result
    except AppError:
        conn.rollback()
        raise
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if "orders.tenant, orders.client_ref" in str(exc) or "UNIQUE constraint failed: orders.tenant, orders.client_ref" in str(exc):
            raise AppError(409, "duplicate_client_ref", "client_ref is already used by this tenant")
        raise
    finally:
        conn.close()


def get_inventory(conn: sqlite3.Connection, tenant: str) -> list[dict]:
    return [inventory_item(row) for row in conn.execute("SELECT * FROM inventory WHERE tenant=? ORDER BY sku", (tenant,)).fetchall()]


def mutation_order_create(conn: sqlite3.Connection, user: dict, body: dict) -> tuple[int, object]:
    client_ref = require_nonempty_string(body.get("client_ref"), "client_ref")
    lines = parse_order_lines(body)
    catalog: list[tuple[str, int, int]] = []
    for sku, quantity in lines:
        row = conn.execute("SELECT price_cents FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], sku)).fetchone()
        if row is None:
            raise AppError(400, "unknown_sku", f"unknown SKU: {sku}")
        catalog.append((sku, quantity, int(row["price_cents"])))
    try:
        order_id = str(uuid.uuid4())
        total = sum(quantity * price for _, quantity, price in catalog)
        conn.execute(
            "INSERT INTO orders(id,tenant,client_ref,status,version,total_cents,created_at) VALUES (?,?,?,?,?,?,?)",
            (order_id, user["tenant"], client_ref, "draft", 1, total, now_iso()),
        )
        for line_no, (sku, quantity, price) in enumerate(catalog, 1):
            conn.execute(
                "INSERT INTO order_lines(tenant,order_id,line_no,sku,quantity,unit_price_cents,returned_quantity) VALUES (?,?,?,?,?,?,0)",
                (user["tenant"], order_id, line_no, sku, quantity, price),
            )
    except sqlite3.IntegrityError as exc:
        if "client_ref" in str(exc):
            raise AppError(409, "duplicate_client_ref", "client_ref is already used by this tenant")
        raise
    add_audit(conn, user["tenant"], "order_created", order_id, user["email"])
    return 201, order_json(conn, user["tenant"], order_id)


def mutation_stock_adjust(conn: sqlite3.Connection, user: dict, body: dict) -> tuple[int, object]:
    sku = require_nonempty_string(body.get("sku"), "sku")
    delta = require_int(body.get("delta"), "delta")
    expected = require_int(body.get("expected_version"), "expected_version")
    reason = require_nonempty_string(body.get("reason"), "reason")
    if delta == 0:
        raise AppError(400, "invalid_payload", "delta must be nonzero")
    row = conn.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], sku)).fetchone()
    if row is None:
        raise AppError(400, "unknown_sku", f"unknown SKU: {sku}")
    if expected != row["version"]:
        raise AppError(409, "stale_version", "expected_version does not match the current inventory version")
    if row["on_hand"] + delta < row["reserved"]:
        raise AppError(409, "insufficient_stock", "adjustment would reduce on-hand below reserved stock")
    conn.execute(
        "UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?",
        (delta, user["tenant"], sku),
    )
    updated = conn.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], sku)).fetchone()
    add_audit(conn, user["tenant"], "stock_adjusted", sku, user["email"])
    return 200, inventory_item(updated)


def mutation_transition(conn: sqlite3.Connection, user: dict, order_id: str, action: str, body: dict) -> tuple[int, object]:
    row = conn.execute("SELECT * FROM orders WHERE tenant=? AND id=?", (user["tenant"], order_id)).fetchone()
    if row is None:
        raise AppError(404, "not_found", "order not found")
    check_expected(int(row["version"]), body)
    status = row["status"]
    lines = conn.execute("SELECT * FROM order_lines WHERE tenant=? AND order_id=? ORDER BY line_no", (user["tenant"], order_id)).fetchall()
    if action == "reserve":
        if status != "draft":
            raise AppError(409, "invalid_transition", "only draft orders can be reserved")
        for line in lines:
            stock = conn.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], line["sku"])).fetchone()
            if stock is None or stock["on_hand"] - stock["reserved"] < line["quantity"]:
                raise AppError(409, "insufficient_stock", f"insufficient available stock for {line['sku']}")
        for line in lines:
            conn.execute("UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?", (line["quantity"], user["tenant"], line["sku"]))
        new_status = "reserved"
    elif action == "ship":
        if status != "reserved":
            raise AppError(409, "invalid_transition", "only reserved orders can be shipped")
        for line in lines:
            conn.execute(
                "UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?",
                (line["quantity"], line["quantity"], user["tenant"], line["sku"]),
            )
        new_status = "shipped"
    elif action == "cancel":
        if status not in ("draft", "reserved"):
            raise AppError(409, "invalid_transition", "only draft or reserved orders can be cancelled")
        if status == "reserved":
            for line in lines:
                conn.execute("UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?", (line["quantity"], user["tenant"], line["sku"]))
        new_status = "cancelled"
    else:
        raise AppError(400, "invalid_route", "unknown order transition")
    conn.execute("UPDATE orders SET status=?,version=version+1 WHERE tenant=? AND id=?", (new_status, user["tenant"], order_id))
    add_audit(conn, user["tenant"], f"order_{action}", order_id, user["email"])
    return 200, order_json(conn, user["tenant"], order_id)


def mutation_return(conn: sqlite3.Connection, user: dict, order_id: str, body: dict) -> tuple[int, object]:
    row = conn.execute("SELECT * FROM orders WHERE tenant=? AND id=?", (user["tenant"], order_id)).fetchone()
    if row is None:
        raise AppError(404, "not_found", "order not found")
    check_expected(int(row["version"]), body)
    if row["status"] != "shipped":
        raise AppError(409, "invalid_transition", "only shipped orders can receive returns")
    requested = parse_order_lines(body)
    by_sku = {line["sku"]: line for line in conn.execute("SELECT * FROM order_lines WHERE tenant=? AND order_id=?", (user["tenant"], order_id)).fetchall()}
    for sku, quantity in requested:
        line = by_sku.get(sku)
        if line is None:
            raise AppError(400, "invalid_payload", f"{sku} is not on this order")
        if line["returned_quantity"] + quantity > line["quantity"]:
            raise AppError(409, "return_exceeds_shipped", f"return exceeds shipped quantity for {sku}")
    for sku, quantity in requested:
        conn.execute("UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE tenant=? AND order_id=? AND sku=?", (quantity, user["tenant"], order_id, sku))
        conn.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?", (quantity, user["tenant"], sku))
    remaining = conn.execute("SELECT COUNT(*) FROM order_lines WHERE tenant=? AND order_id=? AND returned_quantity < quantity", (user["tenant"], order_id)).fetchone()[0]
    new_status = "returned" if remaining == 0 else "shipped"
    conn.execute("UPDATE orders SET status=?,version=version+1 WHERE tenant=? AND id=?", (new_status, user["tenant"], order_id))
    add_audit(conn, user["tenant"], "order_returned", order_id, user["email"])
    return 200, order_json(conn, user["tenant"], order_id)


class Handler(BaseHTTPRequestHandler):
    server_version = "DepotFlow/1.0"

    def log_message(self, fmt: str, *args) -> None:
        return

    def send_json(self, status: int, value: object) -> None:
        payload = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def fail(self, error: AppError) -> None:
        self.send_json(error.status, {"error": {"code": error.code, "message": error.message}})

    def parse_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise AppError(400, "invalid_payload", "invalid Content-Length")
        if length > 1_000_000:
            raise AppError(400, "invalid_payload", "request body is too large")
        try:
            raw = self.rfile.read(length).decode("utf-8")
            value = json.loads(raw) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AppError(400, "invalid_payload", "body must contain valid JSON")
        return require_dict(value)

    def authenticated(self) -> dict[str, str]:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            raise AppError(401, "unauthorized", "Bearer token is required")
        token = header[7:].strip()
        with TOKENS_LOCK:
            user = TOKENS.get(token)
        if user is None:
            raise AppError(401, "unauthorized", "token is invalid or expired")
        return user

    def require_mutator(self, user: dict[str, str]) -> None:
        if user["role"] == "viewer":
            raise AppError(403, "forbidden", "viewer accounts cannot mutate data")

    def route(self, method: str, user: dict[str, str] | None, path: str, query: dict[str, list[str]], body: dict | None) -> tuple[int, object]:
        if method == "GET" and path == "/api/health":
            return 200, {"status": "ok"}
        if method == "POST" and path == "/api/session":
            if body is None:
                raise AppError(400, "invalid_payload", "body is required")
            email = require_nonempty_string(body.get("email"), "email").lower()
            password = body.get("password")
            if not isinstance(password, str):
                raise AppError(401, "unauthorized", "invalid credentials")
            conn = STORE.connect()
            try:
                row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            finally:
                conn.close()
            if row is None or not password_matches(password, row["password_hash"]):
                raise AppError(401, "unauthorized", "invalid credentials")
            token = secrets.token_urlsafe(32)
            identity = public_user(row)
            with TOKENS_LOCK:
                TOKENS[token] = identity
            return 200, {"token": token, "user": identity}
        if user is None:
            raise AppError(401, "unauthorized", "authentication is required")
        if method == "GET" and path == "/api/me":
            return 200, user
        conn = STORE.connect()
        try:
            if method == "GET" and path == "/api/inventory":
                return 200, {"items": get_inventory(conn, user["tenant"])}
            if method == "GET" and path == "/api/dashboard":
                counts = {s: 0 for s in ("draft", "reserved", "shipped", "cancelled", "returned")}
                for row in conn.execute("SELECT status,COUNT(*) AS count FROM orders WHERE tenant=? GROUP BY status", (user["tenant"],)):
                    counts[row["status"]] = int(row["count"])
                stock = conn.execute("SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0) FROM inventory WHERE tenant=?", (user["tenant"],)).fetchone()
                return 200, {"orders_by_status": counts, "inventory_units": int(stock[0]), "reserved_units": int(stock[1])}
            if method == "GET" and path == "/api/orders":
                return self.list_orders(conn, user, query)
            if method == "GET" and path.startswith("/api/orders/"):
                order_id = path.split("/")[3] if len(path.split("/")) == 4 else ""
                return 200, order_json(conn, user["tenant"], order_id)
            if method == "GET" and path == "/api/audit":
                return self.list_audit(conn, user, query)
        finally:
            conn.close()

        if method != "POST":
            raise AppError(404, "not_found", "route not found")
        self.require_mutator(user)
        if body is None:
            raise AppError(400, "invalid_payload", "body is required")
        idem_key = self.headers.get("Idempotency-Key", "")
        if path == "/api/stock/adjustments":
            if user["role"] != "admin":
                raise AppError(403, "forbidden", "only admins can adjust stock")
            return perform_mutation(user, method, path, idem_key, body, lambda c: mutation_stock_adjust(c, user, body))
        if path == "/api/orders":
            return perform_mutation(user, method, path, idem_key, body, lambda c: mutation_order_create(c, user, body))
        pieces = path.split("/")
        if len(pieces) == 5 and pieces[:3] == ["", "api", "orders"]:
            order_id, action = pieces[3], pieces[4]
            if action in ("reserve", "ship", "cancel"):
                return perform_mutation(user, method, path, idem_key, body, lambda c: mutation_transition(c, user, order_id, action, body))
            if action == "returns":
                return perform_mutation(user, method, path, idem_key, body, lambda c: mutation_return(c, user, order_id, body))
        raise AppError(404, "not_found", "route not found")

    def list_orders(self, conn: sqlite3.Connection, user: dict, query: dict[str, list[str]]) -> tuple[int, object]:
        status = query.get("status", [None])[0]
        q = query.get("q", [None])[0]
        limit_text = query.get("limit", ["20"])[0]
        if status is not None and status not in ("draft", "reserved", "shipped", "cancelled", "returned"):
            raise AppError(400, "invalid_filter", "status filter is invalid")
        try:
            limit = int(limit_text)
        except ValueError:
            raise AppError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        if not 1 <= limit <= 100 or str(limit) != limit_text:
            raise AppError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        cursor = query.get("cursor", [None])[0]
        after = 0
        if cursor:
            decoded = decode_cursor(cursor)
            if not isinstance(decoded, dict) or not is_int(decoded.get("seq")) or decoded.get("status") != status or decoded.get("q") != q:
                raise AppError(400, "invalid_cursor", "cursor does not match this query")
            after = decoded["seq"]
        clauses = ["tenant=?", "seq>?"]
        args: list[object] = [user["tenant"], after]
        if status:
            clauses.append("status=?")
            args.append(status)
        if q is not None:
            clauses.append("LOWER(client_ref) LIKE ?")
            args.append("%" + q.lower() + "%")
        rows = conn.execute(
            f"SELECT seq,id FROM orders WHERE {' AND '.join(clauses)} ORDER BY seq LIMIT ?",
            (*args, limit + 1),
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [order_json(conn, user["tenant"], row["id"]) for row in rows]
        next_cursor = encode_cursor({"seq": rows[-1]["seq"], "status": status, "q": q}) if has_more and rows else None
        return 200, {"items": items, "next_cursor": next_cursor}

    def list_audit(self, conn: sqlite3.Connection, user: dict, query: dict[str, list[str]]) -> tuple[int, object]:
        limit_text = query.get("limit", ["20"])[0]
        try:
            limit = int(limit_text)
        except ValueError:
            raise AppError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        if not 1 <= limit <= 100 or str(limit) != limit_text:
            raise AppError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        cursor = query.get("cursor", [None])[0]
        after = 0
        if cursor:
            decoded = decode_cursor(cursor)
            if not is_int(decoded) or decoded < 0:
                raise AppError(400, "invalid_cursor", "cursor is invalid")
            after = decoded
        rows = conn.execute(
            "SELECT id,action,entity_id,actor,created_at FROM audit WHERE tenant=? AND id>? ORDER BY id LIMIT ?",
            (user["tenant"], after, limit + 1),
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [{"id": int(row["id"]), "action": row["action"], "entity_id": row["entity_id"], "actor": row["actor"], "created_at": row["created_at"]} for row in rows]
        return 200, {"items": items, "next_cursor": encode_cursor(rows[-1]["id"]) if has_more and rows else None}

    def dispatch(self, method: str) -> None:
        split = urlsplit(self.path)
        path = split.path.rstrip("/") or "/"
        query = parse_qs(split.query, keep_blank_values=True)
        if method == "GET" and not path.startswith("/api"):
            self.serve_static(path)
            return
        if method == "POST":
            body = self.parse_body()
        else:
            body = None
        try:
            if method == "GET" and path == "/api/health":
                status, result = self.route(method, None, path, query, body)
            elif method == "POST" and path == "/api/session":
                status, result = self.route(method, None, path, query, body)
            else:
                user = self.authenticated()
                status, result = self.route(method, user, path, query, body)
            self.send_json(status, result)
        except AppError as error:
            self.fail(error)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            self.fail(AppError(500, "internal_error", "an unexpected server error occurred"))

    def serve_static(self, path: str) -> None:
        names = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
        filename = names.get(path)
        if filename is None:
            self.send_error(404)
            return
        file_path = ROOT / filename
        try:
            payload = file_path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        content_type = "text/html; charset=utf-8" if filename.endswith(".html") else "text/javascript; charset=utf-8" if filename.endswith(".js") else "text/css; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"DepotFlow listening on http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
