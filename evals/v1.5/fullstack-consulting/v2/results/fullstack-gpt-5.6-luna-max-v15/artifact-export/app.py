#!/usr/bin/env python3
"""DepotFlow: a small, self-contained multi-tenant fulfillment service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(APP_ROOT / "data"))).expanduser()
DB_PATH = DATA_DIR / "depotflow.sqlite3"
PORT = int(os.environ.get("PORT", "8000"))
MAX_BODY_BYTES = 1_048_576
MAX_INT64 = 9_223_372_036_854_775_807
PASSWORD_ITERATIONS = 120_000
VALID_ROLES = {"admin", "operator", "viewer"}
VALID_STATUSES = {"draft", "reserved", "shipped", "cancelled", "returned"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{8,200}$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"{salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return hmac.compare_digest(actual, expected)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def parse_json_bytes(raw: bytes) -> Any:
    if not raw:
        raise ApiError(400, "invalid_json", "Request body must contain a JSON object")
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ApiError(400, "invalid_json", "Request body must be valid JSON")
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_payload", "Request body must be a JSON object")
    return value


def canonical_payload(payload: dict[str, Any]) -> tuple[str, str]:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def require_nonempty_string(payload: dict[str, Any], name: str, *, max_len: int = 200) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "invalid_payload", f"{name} must be a nonempty string")
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(400, "invalid_payload", f"{name} is too long")
    return value


def require_int(
    payload: dict[str, Any], name: str, *, minimum: int | None = None, maximum: int = MAX_INT64
) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(400, "invalid_payload", f"{name} must be an integer")
    if value > maximum or value < -MAX_INT64:
        raise ApiError(400, "invalid_payload", f"{name} is outside the supported range")
    if minimum is not None and value < minimum:
        raise ApiError(400, "invalid_payload", f"{name} must be at least {minimum}")
    return value


def require_expected_version(payload: dict[str, Any]) -> int:
    return require_int(payload, "expected_version", minimum=1)


def parse_lines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        raise ApiError(400, "invalid_payload", "lines must be a nonempty array")
    if len(lines) > 100:
        raise ApiError(400, "invalid_payload", "lines contains too many entries")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in lines:
        if not isinstance(line, dict):
            raise ApiError(400, "invalid_payload", "each line must be an object")
        sku = require_nonempty_string(line, "sku", max_len=50)
        if sku in seen:
            raise ApiError(400, "duplicate_sku", f"SKU {sku} appears more than once")
        seen.add(sku)
        quantity = require_int(line, "quantity", minimum=1)
        result.append({"sku": sku, "quantity": quantity})
    return result


def parse_positive_id(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise ApiError(404, "not_found", "Object not found")
    try:
        result = int(value)
    except ValueError:
        raise ApiError(404, "not_found", "Object not found")
    if result > MAX_INT64:
        raise ApiError(404, "not_found", "Object not found")
    return result


def encode_cursor(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(value: str) -> dict[str, Any]:
    if not value or len(value) > 500 or not re.fullmatch(r"[A-Za-z0-9_\-]+", value):
        raise ApiError(400, "invalid_cursor", "Cursor is invalid")
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(decoded.decode("utf-8"), parse_constant=reject_json_constant)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise ApiError(400, "invalid_cursor", "Cursor is invalid")
    if not isinstance(parsed, dict):
        raise ApiError(400, "invalid_cursor", "Cursor is invalid")
    return parsed


def cursor_id(cursor: dict[str, Any]) -> int:
    value = cursor.get("last_id")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > MAX_INT64:
        raise ApiError(400, "invalid_cursor", "Cursor is invalid")
    return value


def error_body(error: ApiError) -> dict[str, Any]:
    return {"error": {"code": error.code, "message": error.message}}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    on_hand INTEGER NOT NULL CHECK (on_hand >= 0),
    reserved INTEGER NOT NULL CHECK (reserved >= 0),
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    version INTEGER NOT NULL CHECK (version >= 1),
    PRIMARY KEY (tenant_id, sku),
    CHECK (on_hand >= reserved)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    client_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'reserved', 'shipped', 'cancelled', 'returned')),
    version INTEGER NOT NULL CHECK (version >= 1),
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, client_ref)
);

CREATE TABLE IF NOT EXISTS order_lines (
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    line_index INTEGER NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK (returned_quantity >= 0),
    PRIMARY KEY (order_id, sku),
    UNIQUE (order_id, line_index)
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    action TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    idem_key TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, idem_key)
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_tenant_id ON orders(tenant_id, id);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_id ON audit(tenant_id, id);
"""


def initialize_database(seed_demo: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.executescript(SCHEMA)
        tenant_count = conn.execute("SELECT COUNT(*) AS count FROM tenants").fetchone()["count"]
        if seed_demo and tenant_count == 0:
            conn.execute("BEGIN IMMEDIATE")
            try:
                catalog = [
                    ("BOLT", "Steel bolt kit", 100, 1250),
                    ("CABLE", "Cable assembly", 60, 2499),
                    ("SAMPLE", "Sample pack", 20, 0),
                ]
                for tenant in ("north", "south"):
                    conn.execute("INSERT INTO tenants(id, name) VALUES (?, ?)", (tenant, tenant.title()))
                    for role in ("admin", "operator", "viewer"):
                        email = f"{role}@{tenant}.example"
                        conn.execute(
                            "INSERT INTO users(tenant_id, email, role, password_hash) VALUES (?, ?, ?, ?)",
                            (tenant, email, role, password_hash("DepotDemo!2026")),
                        )
                    for sku, name, on_hand, price_cents in catalog:
                        conn.execute(
                            """
                            INSERT INTO inventory(tenant_id, sku, name, on_hand, reserved, price_cents, version)
                            VALUES (?, ?, ?, ?, 0, ?, 1)
                            """,
                            (tenant, sku, name, on_hand, price_cents),
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    finally:
        conn.close()


def user_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, str]:
    return {"email": row["email"], "role": row["role"], "tenant": row["tenant_id"]}


def inventory_item(row: sqlite3.Row | dict[str, Any]) -> dict[str, int | str]:
    return {
        "sku": row["sku"],
        "name": row["name"],
        "on_hand": int(row["on_hand"]),
        "reserved": int(row["reserved"]),
        "available": int(row["on_hand"] - row["reserved"]),
        "price_cents": int(row["price_cents"]),
        "version": int(row["version"]),
    }


def fetch_order(conn: sqlite3.Connection, tenant_id: str, order_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, client_ref, status, version, total_cents FROM orders WHERE tenant_id = ? AND id = ?",
        (tenant_id, order_id),
    ).fetchone()
    if row is None:
        return None
    lines = conn.execute(
        """
        SELECT sku, quantity, unit_price_cents, returned_quantity
        FROM order_lines WHERE order_id = ? ORDER BY line_index ASC
        """,
        (order_id,),
    ).fetchall()
    return {
        "id": int(row["id"]),
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


def audit_event(
    conn: sqlite3.Connection, tenant_id: str, action: str, entity_id: str, actor: str
) -> None:
    conn.execute(
        "INSERT INTO audit(tenant_id, action, entity_id, actor, created_at) VALUES (?, ?, ?, ?, ?)",
        (tenant_id, action, entity_id, actor, now_iso()),
    )


def get_order_or_404(conn: sqlite3.Connection, tenant_id: str, order_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM orders WHERE tenant_id = ? AND id = ?", (tenant_id, order_id)
    ).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "Order not found")
    return row


def get_inventory_or_400(conn: sqlite3.Connection, tenant_id: str, sku: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM inventory WHERE tenant_id = ? AND sku = ?", (tenant_id, sku)
    ).fetchone()
    if row is None:
        raise ApiError(400, "unknown_sku", f"Unknown SKU {sku}")
    return row


def create_order(
    conn: sqlite3.Connection, user: sqlite3.Row, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    client_ref = require_nonempty_string(payload, "client_ref")
    lines = parse_lines(payload)
    priced_lines: list[tuple[str, int, int]] = []
    total = 0
    for line in lines:
        inventory = get_inventory_or_400(conn, user["tenant_id"], line["sku"])
        line_total = line["quantity"] * int(inventory["price_cents"])
        if line_total > MAX_INT64 or total > MAX_INT64 - line_total:
            raise ApiError(400, "invalid_payload", "Order total is outside the supported range")
        total += line_total
        priced_lines.append((line["sku"], line["quantity"], int(inventory["price_cents"])))
    try:
        cursor = conn.execute(
            """
            INSERT INTO orders(tenant_id, client_ref, status, version, total_cents, created_at)
            VALUES (?, ?, 'draft', 1, ?, ?)
            """,
            (user["tenant_id"], client_ref, total, now_iso()),
        )
    except sqlite3.IntegrityError:
        raise ApiError(409, "client_ref_conflict", "client_ref is already used by this tenant")
    order_id = int(cursor.lastrowid)
    for index, (sku, quantity, unit_price) in enumerate(priced_lines):
        conn.execute(
            """
            INSERT INTO order_lines(order_id, line_index, sku, quantity, unit_price_cents, returned_quantity)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (order_id, index, sku, quantity, unit_price),
        )
    audit_event(conn, user["tenant_id"], "order_created", str(order_id), user["email"])
    result = fetch_order(conn, user["tenant_id"], order_id)
    assert result is not None
    return 201, result


def adjust_stock(
    conn: sqlite3.Connection, user: sqlite3.Row, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    sku = require_nonempty_string(payload, "sku", max_len=50)
    delta = require_int(payload, "delta")
    if delta == 0:
        raise ApiError(400, "invalid_payload", "delta must be nonzero")
    expected_version = require_expected_version(payload)
    reason = require_nonempty_string(payload, "reason", max_len=500)
    row = get_inventory_or_400(conn, user["tenant_id"], sku)
    if int(row["version"]) != expected_version:
        raise ApiError(409, "stale_version", "Inventory version is stale")
    new_on_hand = int(row["on_hand"]) + delta
    if new_on_hand < int(row["reserved"]):
        raise ApiError(409, "insufficient_stock", "Adjustment cannot reduce stock below reserved units")
    if new_on_hand > MAX_INT64:
        raise ApiError(400, "invalid_payload", "on_hand is outside the supported range")
    conn.execute(
        "UPDATE inventory SET on_hand = ?, version = version + 1 WHERE tenant_id = ? AND sku = ?",
        (new_on_hand, user["tenant_id"], sku),
    )
    audit_event(conn, user["tenant_id"], "stock_adjusted", sku, user["email"])
    updated = conn.execute(
        "SELECT * FROM inventory WHERE tenant_id = ? AND sku = ?", (user["tenant_id"], sku)
    ).fetchone()
    assert updated is not None
    return 200, inventory_item(updated)


def transition_order(
    conn: sqlite3.Connection, user: sqlite3.Row, order_id: int, action: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    expected_version = require_expected_version(payload)
    order = get_order_or_404(conn, user["tenant_id"], order_id)
    if int(order["version"]) != expected_version:
        raise ApiError(409, "stale_version", "Order version is stale")
    current_status = order["status"]
    lines = conn.execute(
        "SELECT sku, quantity, returned_quantity FROM order_lines WHERE order_id = ? ORDER BY line_index",
        (order_id,),
    ).fetchall()

    if action == "reserve":
        if current_status != "draft":
            raise ApiError(409, "invalid_transition", "Only draft orders can be reserved")
        for line in lines:
            stock = get_inventory_or_400(conn, user["tenant_id"], line["sku"])
            if int(stock["on_hand"]) - int(stock["reserved"]) < int(line["quantity"]):
                raise ApiError(409, "insufficient_stock", f"Insufficient available stock for {line['sku']}")
        for line in lines:
            conn.execute(
                """
                UPDATE inventory SET reserved = reserved + ?, version = version + 1
                WHERE tenant_id = ? AND sku = ?
                """,
                (int(line["quantity"]), user["tenant_id"], line["sku"]),
            )
        next_status = "reserved"
        audit_action = "order_reserved"
    elif action == "ship":
        if current_status != "reserved":
            raise ApiError(409, "invalid_transition", "Only reserved orders can be shipped")
        for line in lines:
            stock = get_inventory_or_400(conn, user["tenant_id"], line["sku"])
            if int(stock["reserved"]) < int(line["quantity"]):
                raise ApiError(409, "insufficient_stock", f"Reserved stock is unavailable for {line['sku']}")
        for line in lines:
            conn.execute(
                """
                UPDATE inventory
                SET on_hand = on_hand - ?, reserved = reserved - ?, version = version + 1
                WHERE tenant_id = ? AND sku = ?
                """,
                (int(line["quantity"]), int(line["quantity"]), user["tenant_id"], line["sku"]),
            )
        next_status = "shipped"
        audit_action = "order_shipped"
    elif action == "cancel":
        if current_status not in {"draft", "reserved"}:
            raise ApiError(409, "invalid_transition", "Only draft or reserved orders can be cancelled")
        if current_status == "reserved":
            for line in lines:
                stock = get_inventory_or_400(conn, user["tenant_id"], line["sku"])
                if int(stock["reserved"]) < int(line["quantity"]):
                    raise ApiError(409, "insufficient_stock", f"Reserved stock is unavailable for {line['sku']}")
            for line in lines:
                conn.execute(
                    """
                    UPDATE inventory SET reserved = reserved - ?, version = version + 1
                    WHERE tenant_id = ? AND sku = ?
                    """,
                    (int(line["quantity"]), user["tenant_id"], line["sku"]),
                )
        next_status = "cancelled"
        audit_action = "order_cancelled"
    else:
        raise ApiError(500, "internal_error", "Unsupported order transition")

    conn.execute(
        "UPDATE orders SET status = ?, version = version + 1 WHERE tenant_id = ? AND id = ?",
        (next_status, user["tenant_id"], order_id),
    )
    audit_event(conn, user["tenant_id"], audit_action, str(order_id), user["email"])
    result = fetch_order(conn, user["tenant_id"], order_id)
    assert result is not None
    return 200, result


def return_order(
    conn: sqlite3.Connection, user: sqlite3.Row, order_id: int, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    expected_version = require_expected_version(payload)
    return_lines = parse_lines(payload)
    order = get_order_or_404(conn, user["tenant_id"], order_id)
    if int(order["version"]) != expected_version:
        raise ApiError(409, "stale_version", "Order version is stale")
    if order["status"] == "returned":
        raise ApiError(409, "invalid_transition", "Order has already been completely returned")
    if order["status"] != "shipped":
        raise ApiError(409, "invalid_transition", "Only shipped orders can receive returns")
    stored_lines = {
        row["sku"]: row
        for row in conn.execute(
            "SELECT sku, quantity, returned_quantity FROM order_lines WHERE order_id = ?", (order_id,)
        ).fetchall()
    }
    for line in return_lines:
        stored = stored_lines.get(line["sku"])
        if stored is None:
            raise ApiError(400, "invalid_payload", f"SKU {line['sku']} is not on this order")
        remaining = int(stored["quantity"]) - int(stored["returned_quantity"])
        if line["quantity"] > remaining:
            raise ApiError(409, "return_exceeds_shipped", f"Return exceeds shipped quantity for {line['sku']}")
    for line in return_lines:
        conn.execute(
            """
            UPDATE inventory SET on_hand = on_hand + ?, version = version + 1
            WHERE tenant_id = ? AND sku = ?
            """,
            (line["quantity"], user["tenant_id"], line["sku"]),
        )
        conn.execute(
            """
            UPDATE order_lines SET returned_quantity = returned_quantity + ?
            WHERE order_id = ? AND sku = ?
            """,
            (line["quantity"], order_id, line["sku"]),
        )
    all_returned = True
    for sku, stored in stored_lines.items():
        returned = int(stored["returned_quantity"])
        returned += next((line["quantity"] for line in return_lines if line["sku"] == sku), 0)
        if returned != int(stored["quantity"]):
            all_returned = False
            break
    next_status = "returned" if all_returned else "shipped"
    conn.execute(
        "UPDATE orders SET status = ?, version = version + 1 WHERE tenant_id = ? AND id = ?",
        (next_status, user["tenant_id"], order_id),
    )
    audit_event(conn, user["tenant_id"], "order_returned", str(order_id), user["email"])
    result = fetch_order(conn, user["tenant_id"], order_id)
    assert result is not None
    return 200, result


Mutation = Callable[[sqlite3.Connection, sqlite3.Row, dict[str, Any]], tuple[int, dict[str, Any]]]


class DepotHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep normal request traffic quiet; startup and test failures remain visible.
        return

    def send_json(self, status: int, value: dict[str, Any]) -> None:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def send_bytes(self, status: int, raw: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_api_error(self, error: ApiError) -> None:
        self.send_json(error.status, error_body(error))

    def read_body_bytes(self) -> bytes:
        header = self.headers.get("Content-Length")
        if header is None:
            return b""
        try:
            length = int(header)
        except ValueError:
            raise ApiError(400, "invalid_request", "Content-Length is invalid")
        if length < 0 or length > MAX_BODY_BYTES:
            raise ApiError(413, "payload_too_large", "Request body is too large")
        return self.rfile.read(length)

    def authenticate(self, conn: sqlite3.Connection) -> sqlite3.Row:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError(401, "unauthorized", "A valid bearer token is required")
        token = header[7:].strip()
        if not TOKEN_RE.fullmatch(token):
            raise ApiError(401, "unauthorized", "A valid bearer token is required")
        row = conn.execute(
            """
            SELECT users.id, users.email, users.role, users.tenant_id
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
            """,
            (token_digest(token),),
        ).fetchone()
        if row is None:
            raise ApiError(401, "unauthorized", "A valid bearer token is required")
        return row

    def authorize(self, user: sqlite3.Row, roles: set[str]) -> None:
        if user["role"] not in roles:
            raise ApiError(403, "forbidden", "This role cannot mutate the requested resource")

    def run_mutation(
        self,
        conn: sqlite3.Connection,
        user: sqlite3.Row,
        raw: bytes,
        handler: Mutation,
        roles: set[str],
        path: str,
    ) -> None:
        # Authentication and role checks deliberately happen before idempotency replay.
        self.authorize(user, roles)
        key = self.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 200:
            raise ApiError(400, "idempotency_required", "A nonempty Idempotency-Key is required")
        payload = parse_json_bytes(raw)
        _, payload_hash = canonical_payload(payload)
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                """
                SELECT method, path, payload_hash, response_status, response_body
                FROM idempotency WHERE tenant_id = ? AND idem_key = ?
                """,
                (user["tenant_id"], key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["method"] == "POST"
                    and existing["path"] == path
                    and existing["payload_hash"] == payload_hash
                ):
                    response = json.loads(existing["response_body"])
                    conn.commit()
                    self.send_json(int(existing["response_status"]), response)
                    return
                raise ApiError(
                    409,
                    "idempotency_conflict",
                    "Idempotency-Key was already used with a different request",
                )
            status, response = handler(conn, user, payload)
            response_text = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
            conn.execute(
                """
                INSERT INTO idempotency
                (tenant_id, idem_key, method, path, payload_hash, response_status, response_body, created_at)
                VALUES (?, ?, 'POST', ?, ?, ?, ?, ?)
                """,
                (user["tenant_id"], key, path, payload_hash, status, response_text, now_iso()),
            )
            conn.commit()
            self.send_json(status, response)
        except Exception:
            conn.rollback()
            raise

    def handle_session(self, raw: bytes) -> None:
        payload = parse_json_bytes(raw)
        email = require_nonempty_string(payload, "email", max_len=254).lower()
        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise ApiError(400, "invalid_payload", "password must be a nonempty string")
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, email, role, tenant_id, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row is None or not password_matches(password, row["password_hash"]):
                raise ApiError(401, "unauthorized", "Email or password is incorrect")
            token = secrets.token_urlsafe(32)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO sessions(token_hash, user_id, created_at) VALUES (?, ?, ?)",
                (token_digest(token), row["id"], now_iso()),
            )
            conn.commit()
            self.send_json(200, {"token": token, "user": user_public(row)})
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def handle_get(self, path: str, query: dict[str, list[str]]) -> None:
        if path == "/api/health":
            self.send_json(200, {"status": "ok"})
            return
        if path in {"/", "/index.html", "/app.js", "/styles.css"}:
            self.serve_static(path)
            return
        if not path.startswith("/api/"):
            raise ApiError(404, "not_found", "Route not found")
        conn = get_connection()
        try:
            user = self.authenticate(conn)
            if path == "/api/me":
                self.send_json(200, user_public(user))
            elif path == "/api/inventory":
                rows = conn.execute(
                    "SELECT * FROM inventory WHERE tenant_id = ? ORDER BY sku", (user["tenant_id"],)
                ).fetchall()
                self.send_json(200, {"items": [inventory_item(row) for row in rows]})
            elif path == "/api/dashboard":
                counts = {
                    status: int(
                        conn.execute(
                            "SELECT COUNT(*) AS count FROM orders WHERE tenant_id = ? AND status = ?",
                            (user["tenant_id"], status),
                        ).fetchone()["count"]
                    )
                    for status in sorted(VALID_STATUSES)
                }
                totals = conn.execute(
                    "SELECT COALESCE(SUM(on_hand), 0) AS units, COALESCE(SUM(reserved), 0) AS reserved "
                    "FROM inventory WHERE tenant_id = ?",
                    (user["tenant_id"],),
                ).fetchone()
                self.send_json(
                    200,
                    {
                        "orders_by_status": counts,
                        "inventory_units": int(totals["units"]),
                        "reserved_units": int(totals["reserved"]),
                    },
                )
            elif path == "/api/orders":
                self.handle_order_list(conn, user, query)
            elif path.startswith("/api/orders/"):
                suffix = path[len("/api/orders/") :]
                if "/" in suffix or not suffix:
                    raise ApiError(404, "not_found", "Route not found")
                order_id = parse_positive_id(suffix)
                result = fetch_order(conn, user["tenant_id"], order_id)
                if result is None:
                    raise ApiError(404, "not_found", "Order not found")
                self.send_json(200, result)
            elif path == "/api/audit":
                self.handle_audit_list(conn, user, query)
            else:
                raise ApiError(404, "not_found", "Route not found")
        finally:
            conn.close()

    def query_single(self, query: dict[str, list[str]], name: str) -> str | None:
        values = query.get(name)
        if values is None:
            return None
        if len(values) != 1:
            raise ApiError(400, "invalid_filter", f"{name} may be supplied only once")
        return values[0]

    def parse_limit(self, query: dict[str, list[str]]) -> int:
        raw = self.query_single(query, "limit")
        if raw is None:
            return 20
        if not re.fullmatch(r"[0-9]+", raw):
            raise ApiError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        value = int(raw)
        if value < 1 or value > 100:
            raise ApiError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        return value

    def handle_order_list(
        self, conn: sqlite3.Connection, user: sqlite3.Row, query: dict[str, list[str]]
    ) -> None:
        status = self.query_single(query, "status")
        if status is not None and status not in VALID_STATUSES:
            raise ApiError(400, "invalid_filter", "status is invalid")
        q = self.query_single(query, "q")
        if q is not None and len(q) > 200:
            raise ApiError(400, "invalid_filter", "q is too long")
        limit = self.parse_limit(query)
        cursor_raw = self.query_single(query, "cursor")
        after = 0
        if cursor_raw is not None:
            decoded = decode_cursor(cursor_raw)
            after = cursor_id(decoded)
            if (
                set(decoded.keys()) != {"last_id", "status", "q"}
                or (decoded.get("status") is not None and decoded.get("status") not in VALID_STATUSES)
                or not isinstance(decoded.get("q"), str)
                or decoded.get("status") != status
                or decoded.get("q") != (q or "").casefold()
            ):
                raise ApiError(400, "invalid_cursor", "Cursor does not match the requested filters")
        sql = "SELECT id, client_ref, status, version, total_cents FROM orders WHERE tenant_id = ? AND id > ?"
        params: list[Any] = [user["tenant_id"], after]
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY id ASC"
        rows = conn.execute(sql, params).fetchall()
        selected: list[dict[str, Any]] = []
        q_norm = (q or "").casefold()
        for row in rows:
            if q_norm and q_norm not in row["client_ref"].casefold():
                continue
            order = fetch_order(conn, user["tenant_id"], int(row["id"]))
            assert order is not None
            selected.append(order)
            if len(selected) > limit:
                break
        has_more = len(selected) > limit
        if has_more:
            selected = selected[:limit]
            next_cursor = encode_cursor(
                {"last_id": selected[-1]["id"], "status": status, "q": q_norm}
            )
        else:
            next_cursor = None
        self.send_json(200, {"items": selected, "next_cursor": next_cursor})

    def handle_audit_list(
        self, conn: sqlite3.Connection, user: sqlite3.Row, query: dict[str, list[str]]
    ) -> None:
        limit = self.parse_limit(query)
        cursor_raw = self.query_single(query, "cursor")
        after = 0
        if cursor_raw is not None:
            decoded = decode_cursor(cursor_raw)
            after = cursor_id(decoded)
            if set(decoded.keys()) != {"last_id"}:
                raise ApiError(400, "invalid_cursor", "Cursor is invalid")
        rows = conn.execute(
            """
            SELECT id, action, entity_id, actor, created_at
            FROM audit WHERE tenant_id = ? AND id > ? ORDER BY id ASC LIMIT ?
            """,
            (user["tenant_id"], after, limit + 1),
        ).fetchall()
        has_more = len(rows) > limit
        items = [
            {
                "id": int(row["id"]),
                "action": row["action"],
                "entity_id": row["entity_id"],
                "actor": row["actor"],
                "created_at": row["created_at"],
            }
            for row in rows[:limit]
        ]
        next_cursor = encode_cursor({"last_id": items[-1]["id"]}) if has_more else None
        self.send_json(200, {"items": items, "next_cursor": next_cursor})

    def handle_post(self, path: str, raw: bytes) -> None:
        if path == "/api/session":
            self.handle_session(raw)
            return
        if not path.startswith("/api/"):
            raise ApiError(404, "not_found", "Route not found")
        conn = get_connection()
        try:
            user = self.authenticate(conn)
            if path == "/api/orders":
                self.run_mutation(conn, user, raw, create_order, {"admin", "operator"}, path)
            elif path == "/api/stock/adjustments":
                self.run_mutation(conn, user, raw, adjust_stock, {"admin"}, path)
            elif path.startswith("/api/orders/"):
                suffix = path[len("/api/orders/") :]
                pieces = suffix.split("/")
                if len(pieces) != 2 or pieces[1] not in {"reserve", "ship", "cancel", "returns"}:
                    raise ApiError(404, "not_found", "Route not found")
                order_id = parse_positive_id(pieces[0])
                action = pieces[1]
                if action == "returns":
                    handler: Mutation = lambda c, u, p: return_order(c, u, order_id, p)
                else:
                    handler = lambda c, u, p: transition_order(c, u, order_id, action, p)
                self.run_mutation(conn, user, raw, handler, {"admin", "operator"}, path)
            else:
                raise ApiError(404, "not_found", "Route not found")
        finally:
            conn.close()

    def serve_static(self, path: str) -> None:
        names = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
        filename = names.get(path)
        if filename is None:
            raise ApiError(404, "not_found", "File not found")
        file_path = APP_ROOT / "static" / filename
        try:
            raw = file_path.read_bytes()
        except OSError:
            raise ApiError(404, "not_found", "File not found")
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if filename.endswith(".js"):
            content_type = "text/javascript; charset=utf-8"
        elif filename.endswith(".css"):
            content_type = "text/css; charset=utf-8"
        elif filename.endswith(".html"):
            content_type = "text/html; charset=utf-8"
        self.send_bytes(200, raw, content_type)

    def dispatch(self, method: str) -> None:
        split = urlsplit(self.path)
        path = unquote(split.path)
        query = parse_qs(split.query, keep_blank_values=True)
        try:
            if method == "GET":
                self.handle_get(path, query)
            elif method == "POST":
                raw = self.read_body_bytes()
                self.handle_post(path, raw)
            else:
                raise ApiError(405, "method_not_allowed", "Method is not allowed")
        except ApiError as error:
            self.send_api_error(error)
        except sqlite3.OperationalError as error:
            print(f"database error: {error}", file=sys.stderr)
            self.send_api_error(ApiError(503, "storage_unavailable", "Storage is temporarily unavailable"))
        except Exception as error:
            print(f"unexpected error: {error}", file=sys.stderr)
            self.send_api_error(ApiError(500, "internal_error", "An unexpected server error occurred"))

    def do_GET(self) -> None:  # noqa: N802
        self.dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self.dispatch("POST")


class DepotHTTPServer(ThreadingHTTPServer):
    # The default socket backlog is five, which is unnecessarily small for the
    # local concurrent verification workload.
    request_queue_size = 128
    allow_reuse_address = True


def main() -> None:
    seed_demo = os.environ.get("SEED_DEMO", "0") == "1"
    initialize_database(seed_demo)
    server = DepotHTTPServer(("127.0.0.1", PORT), DepotHandler)
    print(f"DepotFlow listening on http://127.0.0.1:{PORT} using {DB_PATH}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
