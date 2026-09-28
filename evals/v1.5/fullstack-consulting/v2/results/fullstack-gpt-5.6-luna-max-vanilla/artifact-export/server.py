#!/usr/bin/env python3
"""DepotFlow: a small, dependency-free multi-tenant fulfillment service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
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
STATIC_ROOT = ROOT / "static"
PASSWORD = "DepotDemo!2026"
STATUSES = ("draft", "reserved", "shipped", "cancelled", "returned")
ROLES = ("admin", "operator", "viewer")
SQLITE_INT_MIN = -(2**63)
SQLITE_INT_MAX = 2**63 - 1


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def bad_request(code: str, message: str) -> AppError:
    return AppError(400, code, message)


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and SQLITE_INT_MIN <= value <= SQLITE_INT_MAX


def required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not is_int(value):
        raise bad_request("invalid_payload", f"{key} must be an integer")
    return value


def required_nonempty_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise bad_request("invalid_payload", f"{key} must be a non-empty string")
    return value.strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def password_digest(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256$120000${salt.hex()}${digest.hex()}"


def make_password(password: str) -> str:
    return password_digest(password, secrets.token_bytes(16))


def check_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        ).hex()
        return hmac.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def encode_cursor(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise bad_request("invalid_cursor", "cursor is invalid")
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        result = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        raise bad_request("invalid_cursor", "cursor is invalid")
    if not isinstance(result, dict):
        raise bad_request("invalid_cursor", "cursor is invalid")
    return result


class Store:
    def __init__(self, data_dir: str, seed_demo: bool):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "depotflow.sqlite3"
        self.initialize(seed_demo)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self, seed_demo: bool) -> None:
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    email TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'operator', 'viewer')),
                    password_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    on_hand INTEGER NOT NULL CHECK(on_hand >= 0),
                    reserved INTEGER NOT NULL CHECK(reserved >= 0),
                    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                    version INTEGER NOT NULL CHECK(version >= 1),
                    PRIMARY KEY (tenant_id, sku)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    created_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    client_ref TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('draft', 'reserved', 'shipped', 'cancelled', 'returned')),
                    version INTEGER NOT NULL CHECK(version >= 1),
                    total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
                    created_at TEXT NOT NULL,
                    UNIQUE (tenant_id, client_ref)
                );
                CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant_id, created_seq);
                CREATE TABLE IF NOT EXISTS order_lines (
                    tenant_id TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    line_index INTEGER NOT NULL,
                    sku TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
                    returned_quantity INTEGER NOT NULL CHECK(returned_quantity >= 0),
                    PRIMARY KEY (tenant_id, order_id, sku),
                    UNIQUE (tenant_id, order_id, line_index)
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
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    key TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, key)
                );
                """
            )
            if seed_demo and conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0] == 0:
                self.seed(conn)
        finally:
            conn.close()

    def seed(self, conn: sqlite3.Connection) -> None:
        catalog = (
            ("BOLT", "Steel bolt kit", 100, 1250),
            ("CABLE", "Cable assembly", 60, 2499),
            ("SAMPLE", "Sample pack", 20, 0),
        )
        conn.execute("BEGIN IMMEDIATE")
        try:
            for tenant in ("north", "south"):
                conn.execute("INSERT INTO tenants(id) VALUES (?)", (tenant,))
                for role in ROLES:
                    email = f"{role}@{tenant}.example"
                    conn.execute(
                        "INSERT INTO users(id, tenant_id, email, role, password_hash) VALUES (?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, tenant, email, role, make_password(PASSWORD)),
                    )
                for sku, name, on_hand, price_cents in catalog:
                    conn.execute(
                        "INSERT INTO inventory(tenant_id, sku, name, on_hand, reserved, price_cents, version) VALUES (?, ?, ?, ?, 0, ?, 1)",
                        (tenant, sku, name, on_hand, price_cents),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, str]:
    return {"email": row["email"], "role": row["role"], "tenant": row["tenant_id"]}


def inventory_item(row: sqlite3.Row) -> dict[str, int | str]:
    return {
        "sku": row["sku"],
        "name": row["name"],
        "on_hand": int(row["on_hand"]),
        "reserved": int(row["reserved"]),
        "available": int(row["on_hand"] - row["reserved"]),
        "price_cents": int(row["price_cents"]),
        "version": int(row["version"]),
    }


def fetch_order(conn: sqlite3.Connection, tenant: str, order_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM orders WHERE tenant_id=? AND id=?", (tenant, order_id)
    ).fetchone()
    if row is None:
        raise AppError(404, "not_found", "order not found")
    return row


def order_json(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    lines = conn.execute(
        "SELECT sku, quantity, unit_price_cents, returned_quantity FROM order_lines "
        "WHERE tenant_id=? AND order_id=? ORDER BY line_index",
        (row["tenant_id"], row["id"]),
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


def audit_event(
    conn: sqlite3.Connection, tenant: str, action: str, entity_id: str, actor: str
) -> None:
    conn.execute(
        "INSERT INTO audit(tenant_id, action, entity_id, actor, created_at) VALUES (?, ?, ?, ?, ?)",
        (tenant, action, entity_id, actor, utc_now()),
    )


def parse_query(raw_path: str, allowed: set[str]) -> dict[str, str]:
    parsed = urlsplit(raw_path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) - allowed or any(len(values) != 1 for values in query.values()):
        raise bad_request("invalid_filter", "query filters are invalid")
    return {key: values[0] for key, values in query.items()}


def parse_limit(params: dict[str, str]) -> int:
    if "limit" not in params:
        return 20
    raw = params["limit"]
    if not re.fullmatch(r"[0-9]+", raw):
        raise bad_request("invalid_filter", "limit must be an integer from 1 to 100")
    limit = int(raw)
    if limit < 1 or limit > 100:
        raise bad_request("invalid_filter", "limit must be an integer from 1 to 100")
    return limit


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep normal API use quiet; explicit errors are still returned as JSON.
        return

    @property
    def store(self) -> Store:
        return self.server.store  # type: ignore[attr-defined]

    def send_json(self, status: int, body: Any) -> None:
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, error: AppError) -> None:
        # A rejected POST may have an unread body (for example, a missing
        # idempotency key). Close that HTTP/1.1 connection so those bytes cannot
        # be parsed as the next request on a reused socket.
        self.close_connection = True
        self.send_json(error.status, {"error": {"code": error.code, "message": error.message}})

    def send_bytes(self, status: int, content_type: str, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_payload(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise bad_request("invalid_payload", "JSON request body is required")
        try:
            length = int(raw_length)
        except ValueError:
            raise bad_request("invalid_payload", "invalid content length")
        if length < 0 or length > 1_048_576:
            raise bad_request("invalid_payload", "request body is too large")
        try:
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise bad_request("invalid_payload", "body must be valid JSON")
        if not isinstance(payload, dict):
            raise bad_request("invalid_payload", "body must be a JSON object")
        return payload

    def authenticated_user(self) -> dict[str, str]:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            raise AppError(401, "unauthorized", "a valid bearer token is required")
        token = header[7:].strip()
        conn = self.store.connect()
        try:
            row = conn.execute(
                "SELECT user_id, tenant_id, email, role FROM sessions WHERE token=?", (token,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise AppError(401, "unauthorized", "a valid bearer token is required")
        return {"user_id": row["user_id"], "tenant_id": row["tenant_id"], "email": row["email"], "role": row["role"]}

    def require_role(self, user: dict[str, str], roles: set[str]) -> None:
        if user["role"] not in roles:
            raise AppError(403, "forbidden", "your role cannot perform this mutation")

    def mutation(
        self,
        allowed_roles: set[str],
        callback: Callable[[sqlite3.Connection, dict[str, str], dict[str, Any]], tuple[int, Any]],
    ) -> None:
        user = self.authenticated_user()
        self.require_role(user, allowed_roles)
        key = self.headers.get("Idempotency-Key")
        if key is None or not key.strip():
            raise bad_request("missing_idempotency_key", "Idempotency-Key is required")
        key = key.strip()
        payload = self.read_payload()
        payload_hash = hash_payload(payload)
        path = urlsplit(self.path).path
        conn = self.store.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT method, path, payload_hash, status_code, response_json FROM idempotency "
                "WHERE tenant_id=? AND key=?",
                (user["tenant_id"], key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["method"] != self.command
                    or existing["path"] != path
                    or existing["payload_hash"] != payload_hash
                ):
                    raise conflict(
                        "idempotency_conflict",
                        "Idempotency-Key was already used with a different request",
                    )
                replay_status = int(existing["status_code"])
                replay_body = json.loads(existing["response_json"])
                conn.commit()
                self.send_json(replay_status, replay_body)
                return
            status, body = callback(conn, user, payload)
            response_json = canonical_json(body)
            conn.execute(
                "INSERT INTO idempotency(tenant_id, key, method, path, payload_hash, status_code, response_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user["tenant_id"],
                    key,
                    self.command,
                    path,
                    payload_hash,
                    status,
                    response_json,
                    utc_now(),
                ),
            )
            conn.commit()
            self.send_json(status, body)
        except AppError:
            conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            if "orders.tenant_id, orders.client_ref" in str(exc) or "orders.tenant_id, client_ref" in str(exc):
                raise conflict("duplicate_client_ref", "client_ref is already used")
            raise
        finally:
            conn.close()

    def do_GET(self) -> None:
        try:
            path = urlsplit(self.path).path
            if path == "/api/health":
                self.send_json(200, {"status": "ok"})
            elif path == "/api/me":
                user = self.authenticated_user()
                self.send_json(200, {"email": user["email"], "role": user["role"], "tenant": user["tenant_id"]})
            elif path == "/api/inventory":
                self.handle_inventory()
            elif path == "/api/dashboard":
                self.handle_dashboard()
            elif path == "/api/orders":
                self.handle_orders()
            elif path.startswith("/api/orders/") and "/" not in path[len("/api/orders/") :]:
                self.handle_order_detail(unquote(path[len("/api/orders/") :]))
            elif path == "/api/audit":
                self.handle_audit()
            elif path == "/" or path.startswith("/static/"):
                self.handle_static(path)
            else:
                raise AppError(404, "not_found", "route not found")
        except AppError as error:
            self.send_error_json(error)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            self.send_error_json(AppError(500, "internal_error", "internal server error"))

    def do_POST(self) -> None:
        try:
            path = urlsplit(self.path).path
            if path == "/api/session":
                self.handle_session()
            elif path == "/api/stock/adjustments":
                self.mutation({"admin"}, self.mutate_stock_adjustment)
            elif path == "/api/orders":
                self.mutation({"admin", "operator"}, self.mutate_create_order)
            else:
                match = re.fullmatch(r"/api/orders/([^/]+)/(reserve|ship|cancel|returns)", path)
                if match:
                    action = match.group(2)
                    callback = {
                        "reserve": self.mutate_reserve,
                        "ship": self.mutate_ship,
                        "cancel": self.mutate_cancel,
                        "returns": self.mutate_return,
                    }[action]
                    self.mutation({"admin", "operator"}, lambda conn, user, payload: callback(conn, user, unquote(match.group(1)), payload))
                else:
                    raise AppError(404, "not_found", "route not found")
        except AppError as error:
            self.send_error_json(error)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            self.send_error_json(AppError(500, "internal_error", "internal server error"))

    def handle_session(self) -> None:
        payload = self.read_payload()
        email = payload.get("email")
        password = payload.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            raise bad_request("invalid_payload", "email and password are required")
        email = email.strip().lower()
        conn = self.store.connect()
        try:
            row = conn.execute(
                "SELECT id, tenant_id, email, role, password_hash FROM users WHERE email=?", (email,)
            ).fetchone()
            if row is None or not check_password(password, row["password_hash"]):
                raise AppError(401, "invalid_credentials", "email or password is incorrect")
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO sessions(token, user_id, tenant_id, email, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (token, row["id"], row["tenant_id"], row["email"], row["role"], utc_now()),
            )
            conn.commit()
            self.send_json(200, {"token": token, "user": public_user(row)})
        finally:
            conn.close()

    def handle_inventory(self) -> None:
        user = self.authenticated_user()
        conn = self.store.connect()
        try:
            rows = conn.execute(
                "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory "
                "WHERE tenant_id=? ORDER BY sku",
                (user["tenant_id"],),
            ).fetchall()
            self.send_json(200, {"items": [inventory_item(row) for row in rows]})
        finally:
            conn.close()

    def handle_dashboard(self) -> None:
        user = self.authenticated_user()
        conn = self.store.connect()
        try:
            counts = {status: 0 for status in STATUSES}
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM orders WHERE tenant_id=? GROUP BY status",
                (user["tenant_id"],),
            ).fetchall():
                counts[row["status"]] = int(row["count"])
            totals = conn.execute(
                "SELECT COALESCE(SUM(on_hand), 0) AS on_hand, COALESCE(SUM(reserved), 0) AS reserved "
                "FROM inventory WHERE tenant_id=?",
                (user["tenant_id"],),
            ).fetchone()
            self.send_json(
                200,
                {
                    "orders_by_status": counts,
                    "inventory_units": int(totals["on_hand"]),
                    "reserved_units": int(totals["reserved"]),
                },
            )
        finally:
            conn.close()

    def handle_orders(self) -> None:
        user = self.authenticated_user()
        params = parse_query(self.path, {"status", "q", "limit", "cursor"})
        status = params.get("status")
        if status is not None and status not in STATUSES:
            raise bad_request("invalid_filter", "status filter is invalid")
        query = params.get("q", "")
        limit = parse_limit(params)
        after_seq = 0
        if "cursor" in params:
            cursor = decode_cursor(params["cursor"])
            if (
                cursor.get("v") != 1
                or cursor.get("tenant") != user["tenant_id"]
                or not is_int(cursor.get("seq"))
                or cursor["seq"] < 1
                or cursor.get("status") != status
                or cursor.get("q") != query
            ):
                raise bad_request("invalid_cursor", "cursor does not match these filters")
            after_seq = cursor["seq"]
        conn = self.store.connect()
        try:
            sql = "SELECT * FROM orders WHERE tenant_id=? AND created_seq>?"
            args: list[Any] = [user["tenant_id"], after_seq]
            if status is not None:
                sql += " AND status=?"
                args.append(status)
            sql += " ORDER BY created_seq ASC"
            rows = conn.execute(sql, args).fetchall()
            matching: list[sqlite3.Row] = []
            folded_query = query.casefold()
            for row in rows:
                if folded_query and folded_query not in row["client_ref"].casefold():
                    continue
                matching.append(row)
                if len(matching) > limit:
                    break
            has_more = len(matching) > limit
            shown = matching[:limit]
            body: dict[str, Any] = {
                "items": [order_json(conn, row) for row in shown],
                "next_cursor": None,
            }
            if has_more:
                body["next_cursor"] = encode_cursor(
                    {"v": 1, "tenant": user["tenant_id"], "seq": int(shown[-1]["created_seq"]), "status": status, "q": query}
                )
            self.send_json(200, body)
        finally:
            conn.close()

    def handle_order_detail(self, order_id: str) -> None:
        user = self.authenticated_user()
        conn = self.store.connect()
        try:
            row = fetch_order(conn, user["tenant_id"], order_id)
            self.send_json(200, order_json(conn, row))
        finally:
            conn.close()

    def handle_audit(self) -> None:
        user = self.authenticated_user()
        params = parse_query(self.path, {"limit", "cursor"})
        limit = parse_limit(params)
        after_id = 0
        if "cursor" in params:
            cursor = decode_cursor(params["cursor"])
            if cursor.get("v") != 1 or cursor.get("tenant") != user["tenant_id"] or not is_int(cursor.get("id")) or cursor["id"] < 1:
                raise bad_request("invalid_cursor", "cursor is invalid")
            after_id = cursor["id"]
        conn = self.store.connect()
        try:
            rows = conn.execute(
                "SELECT id, action, entity_id, actor, created_at FROM audit "
                "WHERE tenant_id=? AND id>? ORDER BY id ASC LIMIT ?",
                (user["tenant_id"], after_id, limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            shown = rows[:limit]
            body: dict[str, Any] = {
                "items": [
                    {
                        "id": int(row["id"]),
                        "action": row["action"],
                        "entity_id": row["entity_id"],
                        "actor": row["actor"],
                        "created_at": row["created_at"],
                    }
                    for row in shown
                ],
                "next_cursor": None,
            }
            if has_more:
                body["next_cursor"] = encode_cursor({"v": 1, "tenant": user["tenant_id"], "id": int(shown[-1]["id"])})
            self.send_json(200, body)
        finally:
            conn.close()

    def handle_static(self, path: str) -> None:
        relative = "index.html" if path == "/" else path.removeprefix("/static/")
        allowed = {"index.html", "app.js", "styles.css"}
        if relative not in allowed:
            raise AppError(404, "not_found", "asset not found")
        file_path = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT.resolve() not in file_path.parents:
            raise AppError(404, "not_found", "asset not found")
        try:
            data = file_path.read_bytes()
        except OSError:
            raise AppError(404, "not_found", "asset not found")
        content_type = {
            "index.html": "text/html; charset=utf-8",
            "app.js": "text/javascript; charset=utf-8",
            "styles.css": "text/css; charset=utf-8",
        }[relative]
        self.send_bytes(200, content_type, data)

    def mutate_stock_adjustment(
        self, conn: sqlite3.Connection, user: dict[str, str], payload: dict[str, Any]
    ) -> tuple[int, Any]:
        sku = required_nonempty_string(payload, "sku")
        delta = required_int(payload, "delta")
        expected_version = required_int(payload, "expected_version")
        reason = required_nonempty_string(payload, "reason")
        if delta == 0:
            raise bad_request("invalid_payload", "delta must be nonzero")
        row = conn.execute(
            "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory WHERE tenant_id=? AND sku=?",
            (user["tenant_id"], sku),
        ).fetchone()
        if row is None:
            raise bad_request("unknown_sku", "sku does not exist")
        if row["version"] != expected_version:
            raise conflict("stale_version", "inventory version is stale")
        new_on_hand = row["on_hand"] + delta
        if new_on_hand > SQLITE_INT_MAX:
            raise bad_request("invalid_payload", "adjustment is too large")
        if new_on_hand < row["reserved"]:
            raise conflict("insufficient_stock", "adjustment would reduce stock below reserved units")
        conn.execute(
            "UPDATE inventory SET on_hand=?, version=version+1 WHERE tenant_id=? AND sku=?",
            (new_on_hand, user["tenant_id"], sku),
        )
        audit_event(conn, user["tenant_id"], "stock.adjusted", sku, user["email"])
        updated = conn.execute(
            "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory WHERE tenant_id=? AND sku=?",
            (user["tenant_id"], sku),
        ).fetchone()
        return 200, inventory_item(updated)

    def parse_order_lines(
        self, conn: sqlite3.Connection, tenant: str, raw_lines: Any
    ) -> tuple[list[dict[str, Any]], int]:
        if not isinstance(raw_lines, list) or not raw_lines:
            raise bad_request("invalid_payload", "lines must be a non-empty array")
        seen: set[str] = set()
        lines: list[dict[str, Any]] = []
        total = 0
        for index, raw_line in enumerate(raw_lines):
            if not isinstance(raw_line, dict):
                raise bad_request("invalid_payload", "each line must be an object")
            sku = raw_line.get("sku")
            quantity = raw_line.get("quantity")
            if not isinstance(sku, str) or not sku.strip():
                raise bad_request("invalid_payload", "line sku must be a non-empty string")
            sku = sku.strip()
            if not is_int(quantity) or quantity <= 0:
                raise bad_request("invalid_payload", "line quantity must be a positive integer")
            if sku in seen:
                raise bad_request("invalid_payload", "duplicate sku lines are not allowed")
            seen.add(sku)
            inventory = conn.execute(
                "SELECT sku, name, on_hand, reserved, price_cents, version FROM inventory WHERE tenant_id=? AND sku=?",
                (tenant, sku),
            ).fetchone()
            if inventory is None:
                raise bad_request("unknown_sku", f"sku {sku} does not exist")
            total += int(quantity) * int(inventory["price_cents"])
            if total > SQLITE_INT_MAX:
                raise bad_request("invalid_payload", "order total is too large")
            lines.append(
                {
                    "index": index,
                    "sku": sku,
                    "quantity": int(quantity),
                    "unit_price_cents": int(inventory["price_cents"]),
                }
            )
        return lines, total

    def mutate_create_order(
        self, conn: sqlite3.Connection, user: dict[str, str], payload: dict[str, Any]
    ) -> tuple[int, Any]:
        client_ref = required_nonempty_string(payload, "client_ref")
        lines, total = self.parse_order_lines(conn, user["tenant_id"], payload.get("lines"))
        existing = conn.execute(
            "SELECT id FROM orders WHERE tenant_id=? AND client_ref=?",
            (user["tenant_id"], client_ref),
        ).fetchone()
        if existing is not None:
            raise conflict("duplicate_client_ref", "client_ref is already used")
        order_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO orders(id, tenant_id, client_ref, status, version, total_cents, created_at) "
            "VALUES (?, ?, ?, 'draft', 1, ?, ?)",
            (order_id, user["tenant_id"], client_ref, total, utc_now()),
        )
        for line in lines:
            conn.execute(
                "INSERT INTO order_lines(tenant_id, order_id, line_index, sku, quantity, unit_price_cents, returned_quantity) "
                "VALUES (?, ?, ?, ?, ?, ?, 0)",
                (
                    user["tenant_id"],
                    order_id,
                    line["index"],
                    line["sku"],
                    line["quantity"],
                    line["unit_price_cents"],
                ),
            )
        audit_event(conn, user["tenant_id"], "order.created", order_id, user["email"])
        row = fetch_order(conn, user["tenant_id"], order_id)
        return 201, order_json(conn, row)

    def expected_order(self, payload: dict[str, Any]) -> int:
        return required_int(payload, "expected_version")

    def transition_order(
        self,
        conn: sqlite3.Connection,
        user: dict[str, str],
        order_id: str,
        payload: dict[str, Any],
        from_status: str,
        to_status: str,
        action: str,
        stock_action: str | None = None,
    ) -> tuple[int, Any]:
        expected = self.expected_order(payload)
        row = fetch_order(conn, user["tenant_id"], order_id)
        if row["version"] != expected:
            raise conflict("stale_version", "order version is stale")
        if row["status"] != from_status:
            raise conflict("invalid_transition", f"cannot {action.split('.')[-1]} an order in {row['status']} state")
        lines = conn.execute(
            "SELECT sku, quantity FROM order_lines WHERE tenant_id=? AND order_id=? ORDER BY line_index",
            (user["tenant_id"], order_id),
        ).fetchall()
        if stock_action == "reserve":
            for line in lines:
                inventory = conn.execute(
                    "SELECT on_hand, reserved FROM inventory WHERE tenant_id=? AND sku=?",
                    (user["tenant_id"], line["sku"]),
                ).fetchone()
                if inventory is None or inventory["on_hand"] - inventory["reserved"] < line["quantity"]:
                    raise conflict("insufficient_stock", f"insufficient available stock for {line['sku']}")
            for line in lines:
                conn.execute(
                    "UPDATE inventory SET reserved=reserved+?, version=version+1 WHERE tenant_id=? AND sku=?",
                    (line["quantity"], user["tenant_id"], line["sku"]),
                )
        elif stock_action == "ship":
            for line in lines:
                inventory = conn.execute(
                    "SELECT on_hand, reserved FROM inventory WHERE tenant_id=? AND sku=?",
                    (user["tenant_id"], line["sku"]),
                ).fetchone()
                if inventory is None or inventory["reserved"] < line["quantity"] or inventory["on_hand"] < line["quantity"]:
                    raise conflict("insufficient_stock", f"reserved stock is unavailable for {line['sku']}")
            for line in lines:
                conn.execute(
                    "UPDATE inventory SET on_hand=on_hand-?, reserved=reserved-?, version=version+1 "
                    "WHERE tenant_id=? AND sku=?",
                    (line["quantity"], line["quantity"], user["tenant_id"], line["sku"]),
                )
        elif stock_action == "release":
            for line in lines:
                conn.execute(
                    "UPDATE inventory SET reserved=reserved-?, version=version+1 "
                    "WHERE tenant_id=? AND sku=? AND reserved>=?",
                    (line["quantity"], user["tenant_id"], line["sku"], line["quantity"]),
                )
                if conn.execute("SELECT changes()").fetchone()[0] != 1:
                    raise conflict("insufficient_stock", f"reserved stock is unavailable for {line['sku']}")
        conn.execute(
            "UPDATE orders SET status=?, version=version+1 WHERE tenant_id=? AND id=?",
            (to_status, user["tenant_id"], order_id),
        )
        audit_event(conn, user["tenant_id"], action, order_id, user["email"])
        updated = fetch_order(conn, user["tenant_id"], order_id)
        return 200, order_json(conn, updated)

    def mutate_reserve(
        self, conn: sqlite3.Connection, user: dict[str, str], order_id: str, payload: dict[str, Any]
    ) -> tuple[int, Any]:
        return self.transition_order(conn, user, order_id, payload, "draft", "reserved", "order.reserved", "reserve")

    def mutate_ship(
        self, conn: sqlite3.Connection, user: dict[str, str], order_id: str, payload: dict[str, Any]
    ) -> tuple[int, Any]:
        return self.transition_order(conn, user, order_id, payload, "reserved", "shipped", "order.shipped", "ship")

    def mutate_cancel(
        self, conn: sqlite3.Connection, user: dict[str, str], order_id: str, payload: dict[str, Any]
    ) -> tuple[int, Any]:
        expected = self.expected_order(payload)
        row = fetch_order(conn, user["tenant_id"], order_id)
        if row["version"] != expected:
            raise conflict("stale_version", "order version is stale")
        if row["status"] not in ("draft", "reserved"):
            raise conflict("invalid_transition", f"cannot cancel an order in {row['status']} state")
        stock_action = "release" if row["status"] == "reserved" else None
        return self.transition_order(conn, user, order_id, payload, row["status"], "cancelled", "order.cancelled", stock_action)

    def mutate_return(
        self, conn: sqlite3.Connection, user: dict[str, str], order_id: str, payload: dict[str, Any]
    ) -> tuple[int, Any]:
        expected = self.expected_order(payload)
        row = fetch_order(conn, user["tenant_id"], order_id)
        if row["version"] != expected:
            raise conflict("stale_version", "order version is stale")
        if row["status"] != "shipped":
            raise conflict("invalid_transition", f"cannot return an order in {row['status']} state")
        raw_lines = payload.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raise bad_request("invalid_payload", "lines must be a non-empty array")
        order_lines = {
            line["sku"]: line
            for line in conn.execute(
                "SELECT sku, quantity, returned_quantity FROM order_lines WHERE tenant_id=? AND order_id=?",
                (user["tenant_id"], order_id),
            ).fetchall()
        }
        seen: set[str] = set()
        requested: list[tuple[str, int]] = []
        for raw_line in raw_lines:
            if not isinstance(raw_line, dict):
                raise bad_request("invalid_payload", "each return line must be an object")
            sku = raw_line.get("sku")
            quantity = raw_line.get("quantity")
            if not isinstance(sku, str) or not sku.strip() or not is_int(quantity) or quantity <= 0:
                raise bad_request("invalid_payload", "return sku and quantity are invalid")
            sku = sku.strip()
            if sku in seen:
                raise bad_request("invalid_payload", "duplicate return sku lines are not allowed")
            seen.add(sku)
            line = order_lines.get(sku)
            if line is None:
                raise bad_request("invalid_payload", f"sku {sku} is not on this order")
            if quantity > line["quantity"] - line["returned_quantity"]:
                raise conflict("return_exceeds_shipped", f"return exceeds shipped quantity for {sku}")
            requested.append((sku, int(quantity)))
        for sku, quantity in requested:
            conn.execute(
                "UPDATE inventory SET on_hand=on_hand+?, version=version+1 WHERE tenant_id=? AND sku=?",
                (quantity, user["tenant_id"], sku),
            )
            conn.execute(
                "UPDATE order_lines SET returned_quantity=returned_quantity+? "
                "WHERE tenant_id=? AND order_id=? AND sku=?",
                (quantity, user["tenant_id"], order_id, sku),
            )
        remaining = conn.execute(
            "SELECT COUNT(*) AS count FROM order_lines WHERE tenant_id=? AND order_id=? AND returned_quantity < quantity",
            (user["tenant_id"], order_id),
        ).fetchone()["count"]
        new_status = "returned" if remaining == 0 else "shipped"
        conn.execute(
            "UPDATE orders SET status=?, version=version+1 WHERE tenant_id=? AND id=?",
            (new_status, user["tenant_id"], order_id),
        )
        audit_event(conn, user["tenant_id"], "order.returned", order_id, user["email"])
        updated = fetch_order(conn, user["tenant_id"], order_id)
        return 200, order_json(conn, updated)


class DepotServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], store: Store):
        self.store = store
        super().__init__(address, Handler)


def main() -> None:
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError:
        print("PORT must be an integer", file=sys.stderr)
        raise SystemExit(2)
    data_dir = os.environ.get("DATA_DIR", str(ROOT / "data"))
    seed_demo = os.environ.get("SEED_DEMO") == "1"
    store = Store(data_dir, seed_demo)
    server = DepotServer(("127.0.0.1", port), store)
    print(f"DepotFlow listening on http://127.0.0.1:{port} (data: {store.data_dir})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
