#!/usr/bin/env python3
"""DepotFlow: a small, dependency-free multi-tenant fulfillment service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
PASSWORD = "DepotDemo!2026"
DEFAULT_PORT = 8000
DEFAULT_DATA_DIR = ROOT / "data"


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error(status: int, code: str, message: str) -> APIError:
    return APIError(status, code, message)


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def require_int(value: Any, field: str, *, minimum: int | None = None) -> int:
    if not is_int(value) or (minimum is not None and value < minimum):
        suffix = f" >= {minimum}" if minimum is not None else ""
        raise error(400, "invalid_payload", f"{field} must be an integer{suffix}")
    return value


def require_object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise error(400, "invalid_payload", "JSON body must be an object")
    return payload


def require_nonempty_string(value: Any, field: str, *, max_length: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error(400, "invalid_payload", f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise error(400, "invalid_payload", f"{field} is too long")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    rounds = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds_text, salt_text, digest_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        salt = bytes.fromhex(salt_text)
        expected = bytes.fromhex(digest_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return hmac.compare_digest(actual, expected)


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

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    on_hand INTEGER NOT NULL CHECK (on_hand >= 0),
    reserved INTEGER NOT NULL CHECK (reserved >= 0 AND reserved <= on_hand),
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    version INTEGER NOT NULL CHECK (version >= 1),
    PRIMARY KEY (tenant_id, sku)
);

CREATE TABLE IF NOT EXISTS orders (
    order_no INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    client_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'reserved', 'shipped', 'cancelled', 'returned')),
    version INTEGER NOT NULL CHECK (version >= 1),
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, client_ref)
);

CREATE TABLE IF NOT EXISTS order_lines (
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK (returned_quantity >= 0 AND returned_quantity <= quantity),
    PRIMARY KEY (order_id, sku),
    UNIQUE (order_id, line_no)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    action TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    key TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    response_body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, key)
);

CREATE INDEX IF NOT EXISTS orders_tenant_order_no ON orders(tenant_id, order_no);
CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit_events(tenant_id, id);
CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
"""


CATALOG = (
    ("BOLT", "Steel bolt kit", 100, 1250),
    ("CABLE", "Cable assembly", 60, 2499),
    ("SAMPLE", "Sample pack", 20, 0),
)


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def initialize_database(db_path: Path, seed_demo: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect_db(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        try:
            has_tenants = conn.execute("SELECT 1 FROM tenants LIMIT 1").fetchone() is not None
            if seed_demo and not has_tenants:
                seed_demo_data(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()


def seed_demo_data(conn: sqlite3.Connection) -> None:
    for tenant in ("north", "south"):
        conn.execute("INSERT INTO tenants(id, name) VALUES (?, ?)", (tenant, tenant.title() + " Warehouse"))
        for role in ("admin", "operator", "viewer"):
            email = f"{role}@{tenant}.example"
            conn.execute(
                "INSERT INTO users(tenant_id, email, role, password_hash) VALUES (?, ?, ?, ?)",
                (tenant, email, role, hash_password(PASSWORD)),
            )
        for sku, name, on_hand, price_cents in CATALOG:
            conn.execute(
                """INSERT INTO inventory(tenant_id, sku, name, on_hand, reserved, price_cents, version)
                   VALUES (?, ?, ?, ?, 0, ?, 1)""",
                (tenant, sku, name, on_hand, price_cents),
            )


def encode_cursor(kind: str, position: int, filter_key: str = "") -> str:
    raw = canonical_json({"kind": kind, "position": position, "filter": filter_key}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str, expected_kind: str, expected_filter: str = "") -> int:
    if not isinstance(value, str) or not value:
        raise error(400, "invalid_cursor", "cursor is invalid")
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        data = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise error(400, "invalid_cursor", "cursor is invalid")
    if (
        not isinstance(data, dict)
        or data.get("kind") != expected_kind
        or data.get("filter", "") != expected_filter
        or not is_int(data.get("position"))
        or data["position"] < 0
    ):
        raise error(400, "invalid_cursor", "cursor is invalid")
    return data["position"]


def order_filter_key(status: str | None, query: str) -> str:
    return canonical_json({"status": status or "", "q": query.lower()})


def inventory_dict(row: sqlite3.Row) -> dict[str, Any]:
    on_hand = int(row["on_hand"])
    reserved = int(row["reserved"])
    return {
        "sku": row["sku"],
        "name": row["name"],
        "on_hand": on_hand,
        "reserved": reserved,
        "available": on_hand - reserved,
        "price_cents": int(row["price_cents"]),
        "version": int(row["version"]),
    }


def order_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    lines = conn.execute(
        """SELECT sku, quantity, unit_price_cents, returned_quantity
           FROM order_lines WHERE order_id = ? ORDER BY line_no""",
        (row["id"],),
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


def get_order(conn: sqlite3.Connection, tenant_id: str, order_id: str) -> sqlite3.Row:
    row = conn.execute(
        """SELECT order_no, id, client_ref, status, version, total_cents, created_at
           FROM orders WHERE tenant_id = ? AND id = ?""",
        (tenant_id, order_id),
    ).fetchone()
    if row is None:
        raise error(404, "order_not_found", "order not found")
    return row


def add_audit(conn: sqlite3.Connection, tenant_id: str, action: str, entity_id: str, actor: str) -> None:
    conn.execute(
        """INSERT INTO audit_events(tenant_id, action, entity_id, actor, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (tenant_id, action, entity_id, actor, utc_now()),
    )


def expected_version(payload: dict[str, Any]) -> int:
    if "expected_version" not in payload:
        raise error(400, "invalid_payload", "expected_version is required")
    return require_int(payload["expected_version"], "expected_version", minimum=1)


def validate_order_lines(payload: dict[str, Any]) -> list[tuple[str, int]]:
    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        raise error(400, "invalid_payload", "lines must be a non-empty array")
    output: list[tuple[str, int]] = []
    seen: set[str] = set()
    for line in lines:
        if not isinstance(line, dict):
            raise error(400, "invalid_payload", "each line must be an object")
        sku = require_nonempty_string(line.get("sku"), "sku", max_length=100)
        quantity = require_int(line.get("quantity"), "quantity", minimum=1)
        if sku in seen:
            raise error(400, "duplicate_sku", "duplicate SKU lines are not allowed")
        seen.add(sku)
        output.append((sku, quantity))
    return output


def validate_returns(payload: dict[str, Any]) -> list[tuple[str, int]]:
    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        raise error(400, "invalid_payload", "lines must be a non-empty array")
    output: list[tuple[str, int]] = []
    seen: set[str] = set()
    for line in lines:
        if not isinstance(line, dict):
            raise error(400, "invalid_payload", "each line must be an object")
        sku = require_nonempty_string(line.get("sku"), "sku", max_length=100)
        quantity = require_int(line.get("quantity"), "quantity", minimum=1)
        if sku in seen:
            raise error(400, "duplicate_sku", "duplicate SKU lines are not allowed")
        seen.add(sku)
        output.append((sku, quantity))
    return output


class DepotFlowHandler(BaseHTTPRequestHandler):
    server_version = "DepotFlow/1.0"

    @property
    def app_server(self) -> "DepotFlowServer":
        return self.server  # type: ignore[return-value]

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the default useful access log, but avoid exposing authorization headers.
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def send_json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, exc: APIError) -> None:
        self.send_json(exc.status, {"error": {"code": exc.code, "message": exc.message}})

    def parse_body(self) -> Any:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError:
            raise error(400, "invalid_payload", "Content-Length is invalid")
        if length > 1_000_000:
            raise error(400, "invalid_payload", "request body is too large")
        raw = self.rfile.read(length)
        if not raw:
            raise error(400, "invalid_payload", "JSON body is required")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise error(400, "invalid_payload", "request body must contain valid JSON")

    def authenticate(self) -> dict[str, Any]:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            raise error(401, "unauthorized", "a valid bearer token is required")
        token_hash = hashlib.sha256(header[7:].strip().encode()).hexdigest()
        conn = connect_db(self.app_server.db_path)
        try:
            row = conn.execute(
                """SELECT u.id, u.email, u.role, u.tenant_id
                   FROM sessions s JOIN users u ON u.id = s.user_id
                   WHERE s.token_hash = ?""",
                (token_hash,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise error(401, "unauthorized", "a valid bearer token is required")
        return {"id": int(row["id"]), "email": row["email"], "role": row["role"], "tenant": row["tenant_id"]}

    def require_mutation_access(self, user: dict[str, Any], path: str) -> None:
        if user["role"] == "viewer":
            raise error(403, "forbidden", "viewer users cannot mutate data")
        if path == "/api/stock/adjustments" and user["role"] != "admin":
            raise error(403, "forbidden", "only admins can adjust stock")

    def idempotent_mutation(
        self,
        user: dict[str, Any],
        key: str,
        path: str,
        payload: Any,
        callback: Callable[[sqlite3.Connection], tuple[int, dict[str, Any]]],
    ) -> tuple[int, dict[str, Any]]:
        conn = connect_db(self.app_server.db_path)
        request_hash = payload_hash(payload)
        try:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute(
                """SELECT method, path, payload_hash, status_code, response_body
                   FROM idempotency_keys WHERE tenant_id = ? AND key = ?""",
                (user["tenant"], key),
            ).fetchone()
            if previous is not None:
                if (
                    previous["method"] != "POST"
                    or previous["path"] != path
                    or previous["payload_hash"] != request_hash
                ):
                    conn.rollback()
                    raise error(409, "idempotency_conflict", "Idempotency-Key was already used for another request")
                response = json.loads(previous["response_body"])
                conn.rollback()
                return int(previous["status_code"]), response

            status, response = callback(conn)
            response_body = canonical_json(response)
            conn.execute(
                """INSERT INTO idempotency_keys
                   (tenant_id, key, method, path, payload_hash, status_code, response_body, created_at)
                   VALUES (?, ?, 'POST', ?, ?, ?, ?, ?)""",
                (user["tenant"], key, path, request_hash, status, response_body, utc_now()),
            )
            conn.commit()
            return status, response
        except APIError:
            if conn.in_transaction:
                conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            if conn.in_transaction:
                conn.rollback()
            if "orders.tenant_id, orders.client_ref" in str(exc) or "UNIQUE constraint failed: orders.tenant_id, orders.client_ref" in str(exc):
                raise error(409, "client_ref_conflict", "client_ref is already used by this tenant")
            raise
        finally:
            conn.close()

    def mutation_key(self) -> str:
        key = self.headers.get("Idempotency-Key")
        if key is None or not key.strip():
            raise error(400, "idempotency_key_required", "Idempotency-Key is required for mutations")
        key = key.strip()
        if len(key) > 200:
            raise error(400, "invalid_idempotency_key", "Idempotency-Key is too long")
        return key

    def do_GET(self) -> None:  # noqa: N802
        try:
            self.dispatch_get()
        except APIError as exc:
            self.send_error_json(exc)
        except BrokenPipeError:
            pass
        except Exception:
            self.send_error_json(error(500, "internal_error", "internal server error"))

    def do_POST(self) -> None:  # noqa: N802
        try:
            self.dispatch_post()
        except APIError as exc:
            self.send_error_json(exc)
        except BrokenPipeError:
            pass
        except Exception:
            self.send_error_json(error(500, "internal_error", "internal server error"))

    def dispatch_get(self) -> None:
        split = urlsplit(self.path)
        path = split.path
        if path == "/api/health":
            self.send_json(200, {"status": "ok"})
            return
        if not path.startswith("/api/"):
            self.serve_static(path)
            return

        user = self.authenticate()
        if path == "/api/me":
            self.send_json(200, {"email": user["email"], "role": user["role"], "tenant": user["tenant"]})
        elif path == "/api/inventory":
            self.send_json(200, self.read_inventory(user))
        elif path == "/api/dashboard":
            self.send_json(200, self.read_dashboard(user))
        elif path == "/api/orders":
            self.send_json(200, self.read_orders(user, split.query))
        elif path.startswith("/api/orders/") and "/" not in path[len("/api/orders/") :]:
            order_id = unquote(path[len("/api/orders/") :])
            conn = connect_db(self.app_server.db_path)
            try:
                row = get_order(conn, user["tenant"], order_id)
                body = order_dict(conn, row)
            finally:
                conn.close()
            self.send_json(200, body)
        elif path == "/api/audit":
            self.send_json(200, self.read_audit(user, split.query))
        else:
            raise error(404, "not_found", "route not found")

    def dispatch_post(self) -> None:
        split = urlsplit(self.path)
        path = split.path
        if path == "/api/session":
            self.handle_session(require_object(self.parse_body()))
            return
        if not path.startswith("/api/"):
            raise error(404, "not_found", "route not found")

        user = self.authenticate()
        self.require_mutation_access(user, path)
        payload = require_object(self.parse_body())
        key = self.mutation_key()

        if path == "/api/stock/adjustments":
            status, body = self.idempotent_mutation(user, key, path, payload, lambda conn: self.create_adjustment(conn, user, payload))
        elif path == "/api/orders":
            status, body = self.idempotent_mutation(user, key, path, payload, lambda conn: self.create_order(conn, user, payload))
        else:
            marker = "/api/orders/"
            if not path.startswith(marker):
                raise error(404, "not_found", "route not found")
            remainder = path[len(marker) :]
            parts = remainder.split("/")
            if len(parts) != 2 or not parts[0] or parts[1] not in {"reserve", "ship", "cancel", "returns"}:
                raise error(404, "not_found", "route not found")
            order_id = unquote(parts[0])
            action = parts[1]
            callback = lambda conn: self.transition_order(conn, user, order_id, action, payload)
            status, body = self.idempotent_mutation(user, key, path, payload, callback)
        self.send_json(status, body)

    def handle_session(self, payload: dict[str, Any]) -> None:
        email = require_nonempty_string(payload.get("email"), "email", max_length=320).lower()
        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise error(401, "invalid_credentials", "email or password is incorrect")
        conn = connect_db(self.app_server.db_path)
        try:
            row = conn.execute(
                "SELECT id, email, role, tenant_id, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if row is None or not verify_password(password, row["password_hash"]):
                raise error(401, "invalid_credentials", "email or password is incorrect")
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO sessions(token_hash, user_id, created_at) VALUES (?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), row["id"], utc_now()),
            )
            conn.commit()
        finally:
            conn.close()
        self.send_json(
            200,
            {
                "token": token,
                "user": {"email": row["email"], "role": row["role"], "tenant": row["tenant_id"]},
            },
        )

    def read_inventory(self, user: dict[str, Any]) -> dict[str, Any]:
        conn = connect_db(self.app_server.db_path)
        try:
            rows = conn.execute(
                "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory WHERE tenant_id = ? ORDER BY sku",
                (user["tenant"],),
            ).fetchall()
            return {"items": [inventory_dict(row) for row in rows]}
        finally:
            conn.close()

    def read_dashboard(self, user: dict[str, Any]) -> dict[str, Any]:
        conn = connect_db(self.app_server.db_path)
        try:
            counts = {status: 0 for status in ("draft", "reserved", "shipped", "cancelled", "returned")}
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM orders WHERE tenant_id = ? GROUP BY status",
                (user["tenant"],),
            ):
                counts[row["status"]] = int(row["count"])
            row = conn.execute(
                "SELECT COALESCE(SUM(on_hand), 0) AS on_hand, COALESCE(SUM(reserved), 0) AS reserved FROM inventory WHERE tenant_id = ?",
                (user["tenant"],),
            ).fetchone()
            return {"orders_by_status": counts, "inventory_units": int(row["on_hand"]), "reserved_units": int(row["reserved"])}
        finally:
            conn.close()

    def query_params(self, query: str, allowed: set[str]) -> dict[str, str]:
        parsed = parse_qs(query, keep_blank_values=True)
        if any(key not in allowed for key in parsed):
            raise error(400, "invalid_filter", "unknown query filter")
        values: dict[str, str] = {}
        for key, entries in parsed.items():
            if len(entries) != 1:
                raise error(400, "invalid_filter", f"{key} must appear once")
            values[key] = entries[0]
        return values

    def read_orders(self, user: dict[str, Any], query: str) -> dict[str, Any]:
        params = self.query_params(query, {"status", "q", "limit", "cursor"})
        status_filter = params.get("status")
        if status_filter is not None and status_filter not in {"draft", "reserved", "shipped", "cancelled", "returned"}:
            raise error(400, "invalid_filter", "status filter is invalid")
        search = params.get("q", "")
        if len(search) > 200:
            raise error(400, "invalid_filter", "q filter is too long")
        if "limit" in params:
            try:
                limit = int(params["limit"])
            except ValueError:
                raise error(400, "invalid_filter", "limit must be an integer from 1 to 100")
            if limit < 1 or limit > 100:
                raise error(400, "invalid_filter", "limit must be an integer from 1 to 100")
        else:
            limit = 20
        filter_key = order_filter_key(status_filter, search)
        position = decode_cursor(params["cursor"], "orders", filter_key) if "cursor" in params else 0
        clauses = ["tenant_id = ?", "order_no > ?"]
        args: list[Any] = [user["tenant"], position]
        if status_filter:
            clauses.append("status = ?")
            args.append(status_filter)
        if search:
            clauses.append("LOWER(client_ref) LIKE ?")
            args.append(f"%{search.lower()}%")
        conn = connect_db(self.app_server.db_path)
        try:
            rows = conn.execute(
                f"""SELECT order_no, id, client_ref, status, version, total_cents, created_at
                    FROM orders WHERE {' AND '.join(clauses)} ORDER BY order_no LIMIT ?""",
                (*args, limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            items = [order_dict(conn, row) for row in rows]
            next_cursor = encode_cursor("orders", int(rows[-1]["order_no"]), filter_key) if has_more and rows else None
            return {"items": items, "next_cursor": next_cursor}
        finally:
            conn.close()

    def read_audit(self, user: dict[str, Any], query: str) -> dict[str, Any]:
        params = self.query_params(query, {"limit", "cursor"})
        if "limit" in params:
            try:
                limit = int(params["limit"])
            except ValueError:
                raise error(400, "invalid_filter", "limit must be an integer from 1 to 100")
            if limit < 1 or limit > 100:
                raise error(400, "invalid_filter", "limit must be an integer from 1 to 100")
        else:
            limit = 20
        position = decode_cursor(params["cursor"], "audit") if "cursor" in params else 0
        conn = connect_db(self.app_server.db_path)
        try:
            rows = conn.execute(
                """SELECT id, action, entity_id, actor, created_at FROM audit_events
                   WHERE tenant_id = ? AND id > ? ORDER BY id LIMIT ?""",
                (user["tenant"], position, limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            items = [
                {
                    "id": int(row["id"]),
                    "action": row["action"],
                    "entity_id": row["entity_id"],
                    "actor": row["actor"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
            next_cursor = encode_cursor("audit", int(rows[-1]["id"])) if has_more and rows else None
            return {"items": items, "next_cursor": next_cursor}
        finally:
            conn.close()

    def create_adjustment(
        self, conn: sqlite3.Connection, user: dict[str, Any], payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        sku = require_nonempty_string(payload.get("sku"), "sku", max_length=100)
        delta = payload.get("delta")
        if not is_int(delta) or delta == 0:
            raise error(400, "invalid_payload", "delta must be a nonzero integer")
        expected = require_int(payload.get("expected_version"), "expected_version", minimum=1)
        reason = require_nonempty_string(payload.get("reason"), "reason", max_length=500)
        row = conn.execute(
            "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory WHERE tenant_id = ? AND sku = ?",
            (user["tenant"], sku),
        ).fetchone()
        if row is None:
            raise error(400, "unknown_sku", "SKU does not exist")
        if int(row["version"]) != expected:
            raise error(409, "stale_version", "inventory version is stale")
        new_on_hand = int(row["on_hand"]) + delta
        if new_on_hand < int(row["reserved"]):
            raise error(409, "insufficient_stock", "adjustment would reduce on-hand below reserved stock")
        conn.execute(
            "UPDATE inventory SET on_hand = ?, version = version + 1 WHERE tenant_id = ? AND sku = ?",
            (new_on_hand, user["tenant"], sku),
        )
        updated = conn.execute(
            "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory WHERE tenant_id = ? AND sku = ?",
            (user["tenant"], sku),
        ).fetchone()
        add_audit(conn, user["tenant"], "stock.adjusted", sku, user["email"])
        return 200, inventory_dict(updated)

    def create_order(
        self, conn: sqlite3.Connection, user: dict[str, Any], payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        client_ref = require_nonempty_string(payload.get("client_ref"), "client_ref", max_length=200)
        lines = validate_order_lines(payload)
        if conn.execute(
            "SELECT 1 FROM orders WHERE tenant_id = ? AND client_ref = ?",
            (user["tenant"], client_ref),
        ).fetchone():
            raise error(409, "client_ref_conflict", "client_ref is already used by this tenant")
        prices: list[tuple[str, int, int]] = []
        total = 0
        for sku, quantity in lines:
            row = conn.execute(
                "SELECT price_cents FROM inventory WHERE tenant_id = ? AND sku = ?",
                (user["tenant"], sku),
            ).fetchone()
            if row is None:
                raise error(400, "unknown_sku", "SKU does not exist")
            unit_price = int(row["price_cents"])
            prices.append((sku, quantity, unit_price))
            total += quantity * unit_price
        order_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO orders(id, tenant_id, client_ref, status, version, total_cents, created_at)
               VALUES (?, ?, ?, 'draft', 1, ?, ?)""",
            (order_id, user["tenant"], client_ref, total, utc_now()),
        )
        for line_no, (sku, quantity, unit_price) in enumerate(prices, start=1):
            conn.execute(
                """INSERT INTO order_lines(order_id, line_no, sku, quantity, unit_price_cents, returned_quantity)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (order_id, line_no, sku, quantity, unit_price),
            )
        row = get_order(conn, user["tenant"], order_id)
        body = order_dict(conn, row)
        add_audit(conn, user["tenant"], "order.created", order_id, user["email"])
        return 201, body

    def transition_order(
        self,
        conn: sqlite3.Connection,
        user: dict[str, Any],
        order_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        expected = expected_version(payload)
        row = get_order(conn, user["tenant"], order_id)
        if int(row["version"]) != expected:
            raise error(409, "stale_version", "order version is stale")

        if action == "reserve":
            body = self.reserve_order(conn, user, row)
            audit_action = "order.reserved"
        elif action == "ship":
            body = self.ship_order(conn, user, row)
            audit_action = "order.shipped"
        elif action == "cancel":
            body = self.cancel_order(conn, user, row)
            audit_action = "order.cancelled"
        else:
            body = self.return_order(conn, user, row, payload)
            audit_action = "order.returned"
        add_audit(conn, user["tenant"], audit_action, order_id, user["email"])
        return 200, body

    def line_rows(self, conn: sqlite3.Connection, order_id: str) -> list[sqlite3.Row]:
        return conn.execute(
            "SELECT line_no, sku, quantity, unit_price_cents, returned_quantity FROM order_lines WHERE order_id = ? ORDER BY line_no",
            (order_id,),
        ).fetchall()

    def reserve_order(self, conn: sqlite3.Connection, user: dict[str, Any], row: sqlite3.Row) -> dict[str, Any]:
        if row["status"] != "draft":
            raise error(409, "invalid_transition", "only draft orders can be reserved")
        lines = self.line_rows(conn, row["id"])
        inventory_rows: list[tuple[sqlite3.Row, int]] = []
        for line in lines:
            inv = conn.execute(
                "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory WHERE tenant_id = ? AND sku = ?",
                (user["tenant"], line["sku"]),
            ).fetchone()
            if inv is None or int(inv["on_hand"]) - int(inv["reserved"]) < int(line["quantity"]):
                raise error(409, "insufficient_stock", f"insufficient available stock for {line['sku']}")
            inventory_rows.append((inv, int(line["quantity"])))
        for inv, quantity in inventory_rows:
            conn.execute(
                "UPDATE inventory SET reserved = reserved + ?, version = version + 1 WHERE tenant_id = ? AND sku = ?",
                (quantity, user["tenant"], inv["sku"]),
            )
        conn.execute("UPDATE orders SET status = 'reserved', version = version + 1 WHERE id = ?", (row["id"],))
        return order_dict(conn, get_order(conn, user["tenant"], row["id"]))

    def ship_order(self, conn: sqlite3.Connection, user: dict[str, Any], row: sqlite3.Row) -> dict[str, Any]:
        if row["status"] != "reserved":
            raise error(409, "invalid_transition", "only reserved orders can be shipped")
        lines = self.line_rows(conn, row["id"])
        for line in lines:
            inv = conn.execute(
                "SELECT on_hand, reserved FROM inventory WHERE tenant_id = ? AND sku = ?",
                (user["tenant"], line["sku"]),
            ).fetchone()
            quantity = int(line["quantity"])
            if inv is None or int(inv["reserved"]) < quantity or int(inv["on_hand"]) < quantity:
                raise error(409, "insufficient_stock", f"reserved stock is unavailable for {line['sku']}")
        for line in lines:
            quantity = int(line["quantity"])
            conn.execute(
                """UPDATE inventory SET on_hand = on_hand - ?, reserved = reserved - ?, version = version + 1
                   WHERE tenant_id = ? AND sku = ?""",
                (quantity, quantity, user["tenant"], line["sku"]),
            )
        conn.execute("UPDATE orders SET status = 'shipped', version = version + 1 WHERE id = ?", (row["id"],))
        return order_dict(conn, get_order(conn, user["tenant"], row["id"]))

    def cancel_order(self, conn: sqlite3.Connection, user: dict[str, Any], row: sqlite3.Row) -> dict[str, Any]:
        if row["status"] not in {"draft", "reserved"}:
            raise error(409, "invalid_transition", "only draft or reserved orders can be cancelled")
        if row["status"] == "reserved":
            for line in self.line_rows(conn, row["id"]):
                inv = conn.execute(
                    "SELECT reserved FROM inventory WHERE tenant_id = ? AND sku = ?",
                    (user["tenant"], line["sku"]),
                ).fetchone()
                if inv is None or int(inv["reserved"]) < int(line["quantity"]):
                    raise error(409, "insufficient_stock", f"reserved stock is unavailable for {line['sku']}")
            for line in self.line_rows(conn, row["id"]):
                conn.execute(
                    "UPDATE inventory SET reserved = reserved - ?, version = version + 1 WHERE tenant_id = ? AND sku = ?",
                    (int(line["quantity"]), user["tenant"], line["sku"]),
                )
        conn.execute("UPDATE orders SET status = 'cancelled', version = version + 1 WHERE id = ?", (row["id"],))
        return order_dict(conn, get_order(conn, user["tenant"], row["id"]))

    def return_order(
        self, conn: sqlite3.Connection, user: dict[str, Any], row: sqlite3.Row, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if row["status"] != "shipped":
            raise error(409, "invalid_transition", "only shipped orders can receive returns")
        requested = validate_returns(payload)
        line_by_sku = {line["sku"]: line for line in self.line_rows(conn, row["id"])}
        for sku, quantity in requested:
            line = line_by_sku.get(sku)
            if line is None:
                raise error(400, "invalid_return_sku", "return SKU does not belong to the order")
            if int(line["returned_quantity"]) + quantity > int(line["quantity"]):
                raise error(409, "return_exceeds_shipped", f"return quantity exceeds shipped quantity for {sku}")
        for sku, quantity in requested:
            conn.execute(
                """UPDATE order_lines SET returned_quantity = returned_quantity + ?
                   WHERE order_id = ? AND sku = ?""",
                (quantity, row["id"], sku),
            )
            conn.execute(
                "UPDATE inventory SET on_hand = on_hand + ?, version = version + 1 WHERE tenant_id = ? AND sku = ?",
                (quantity, user["tenant"], sku),
            )
        remaining = conn.execute(
            "SELECT COUNT(*) AS count FROM order_lines WHERE order_id = ? AND returned_quantity < quantity",
            (row["id"],),
        ).fetchone()["count"]
        new_status = "shipped" if int(remaining) else "returned"
        conn.execute("UPDATE orders SET status = ?, version = version + 1 WHERE id = ?", (new_status, row["id"]))
        return order_dict(conn, get_order(conn, user["tenant"], row["id"]))

    def serve_static(self, path: str) -> None:
        if path == "/":
            relative = "index.html"
        elif path.startswith("/static/"):
            relative = path[len("/static/") :]
        else:
            raise error(404, "not_found", "route not found")
        if not relative or "/" in relative or "\\" in relative or relative in {".", ".."}:
            raise error(404, "not_found", "asset not found")
        file_path = STATIC_DIR / relative
        if not file_path.is_file():
            raise error(404, "not_found", "asset not found")
        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)


class DepotFlowServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], db_path: Path):
        self.db_path = db_path
        super().__init__(address, DepotFlowHandler)


def main() -> None:
    try:
        port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    except ValueError:
        print("PORT must be an integer", file=sys.stderr)
        raise SystemExit(2)
    if port < 1 or port > 65535:
        print("PORT must be between 1 and 65535", file=sys.stderr)
        raise SystemExit(2)
    data_dir = Path(os.environ.get("DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser().resolve()
    db_path = data_dir / "depotflow.sqlite3"
    initialize_database(db_path, os.environ.get("SEED_DEMO") == "1")
    server = DepotFlowServer(("127.0.0.1", port), db_path)
    print(f"DepotFlow listening on http://127.0.0.1:{port} using {db_path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
