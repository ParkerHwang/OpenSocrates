#!/usr/bin/env python3
"""DepotFlow: a local, single-process-friendly multi-tenant fulfillment app."""

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
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data"))).expanduser()
DB_PATH = DATA_DIR / "depotflow.sqlite3"
MAX_INT64 = (1 << 63) - 1
MIN_INT64 = -(1 << 63)
ROLES = {"admin", "operator", "viewer"}
STATUSES = {"draft", "reserved", "shipped", "cancelled", "returned"}
CATALOG = (
    ("BOLT", "Steel bolt kit", 100, 1250),
    ("CABLE", "Cable assembly", 60, 2499),
    ("SAMPLE", "Sample pack", 20, 0),
)
DB_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def fail(status: int, code: str, message: str) -> None:
    raise ApiError(status, code, message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 30000")
    return db


@contextmanager
def read_db():
    db = connect()
    try:
        db.execute("BEGIN")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def open_db():
    db = connect()
    try:
        yield db
    finally:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
    password_salt BLOB NOT NULL,
    password_hash BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL REFERENCES users(email),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    on_hand INTEGER NOT NULL CHECK(on_hand >= 0),
    reserved INTEGER NOT NULL CHECK(reserved >= 0 AND reserved <= on_hand),
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    version INTEGER NOT NULL CHECK(version >= 1),
    PRIMARY KEY(tenant_id, sku)
);
CREATE TABLE IF NOT EXISTS orders (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    client_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','reserved','shipped','cancelled','returned')),
    version INTEGER NOT NULL CHECK(version >= 1),
    total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
    created_at TEXT NOT NULL,
    UNIQUE(tenant_id, client_ref)
);
CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant_id, seq);
CREATE TABLE IF NOT EXISTS order_lines (
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
    returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(returned_quantity >= 0 AND returned_quantity <= quantity),
    PRIMARY KEY(order_id, sku)
);
CREATE TABLE IF NOT EXISTS audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    action TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_tenant_seq ON audit_events(tenant_id, seq);
CREATE TABLE IF NOT EXISTS idempotency (
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    key TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    request_json TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, key)
);
"""


def password_record(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    salt = salt or secrets.token_bytes(16)
    return salt, hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180_000)


def initialize() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        db = connect()
        try:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(SCHEMA)
            if os.environ.get("SEED_DEMO") == "1":
                db.execute("BEGIN IMMEDIATE")
                try:
                    existing = db.execute("SELECT 1 FROM tenants LIMIT 1").fetchone()
                    if existing is None:
                        demo_password = "DepotDemo!2026"
                        for tenant in ("north", "south"):
                            db.execute("INSERT INTO tenants(id) VALUES (?)", (tenant,))
                            for role in ("admin", "operator", "viewer"):
                                email = f"{role}@{tenant}.example"
                                salt, password_hash = password_record(demo_password)
                                db.execute(
                                    "INSERT INTO users(email,tenant_id,role,password_salt,password_hash) VALUES (?,?,?,?,?)",
                                    (email, tenant, role, salt, password_hash),
                                )
                            for sku, name, on_hand, price in CATALOG:
                                db.execute(
                                    "INSERT INTO inventory(tenant_id,sku,name,on_hand,reserved,price_cents,version) VALUES (?,?,?, ?,0,?,1)",
                                    (tenant, sku, name, on_hand, price),
                                )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
        finally:
            db.close()


def user_public(row: sqlite3.Row) -> dict[str, str]:
    return {"email": row["email"], "role": row["role"], "tenant": row["tenant_id"]}


def inventory_item(row: sqlite3.Row) -> dict[str, Any]:
    on_hand, reserved = int(row["on_hand"]), int(row["reserved"])
    return {
        "sku": row["sku"],
        "name": row["name"],
        "on_hand": on_hand,
        "reserved": reserved,
        "available": on_hand - reserved,
        "price_cents": int(row["price_cents"]),
        "version": int(row["version"]),
    }


def order_object(db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    lines = db.execute(
        "SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid",
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


def add_audit(db: sqlite3.Connection, tenant: str, action: str, entity_id: str, actor: str) -> None:
    db.execute(
        "INSERT INTO audit_events(id,tenant_id,action,entity_id,actor,created_at) VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), tenant, action, entity_id, actor, utc_now()),
    )


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None:
        fail(400, "invalid_json", "A JSON request body is required.")
    try:
        length = int(raw_length)
    except ValueError:
        fail(400, "invalid_json", "Content-Length must be an integer.")
    if length < 0 or length > 1_000_000:
        fail(400, "invalid_json", "Request body must be at most 1 MB.")
    try:
        raw = handler.rfile.read(length)
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail(400, "invalid_json", "Request body must be valid JSON.")
    if not isinstance(body, dict):
        fail(400, "invalid_payload", "Request body must be a JSON object.")
    return body


def require_string(value: Any, field: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        fail(400, "invalid_payload", f"{field} must be a nonempty string.")
    return value


def require_int(value: Any, field: str, *, minimum: int | None = None, maximum: int = MAX_INT64) -> int:
    if type(value) is not int or value < MIN_INT64 or value > maximum or (minimum is not None and value < minimum):
        expectation = f"an integer >= {minimum}" if minimum is not None else "an integer"
        fail(400, "invalid_payload", f"{field} must be {expectation} within the supported range.")
    return value


def read_user(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    authorization = handler.headers.get("Authorization", "")
    match = re.fullmatch(r"Bearer\s+(\S+)", authorization)
    if not match:
        fail(401, "unauthorized", "A valid bearer token is required.")
    token_hash = hashlib.sha256(match.group(1).encode("utf-8")).hexdigest()
    with read_db() as db:
        row = db.execute(
            "SELECT u.email,u.tenant_id,u.role FROM sessions s JOIN users u ON u.email=s.email WHERE s.token_hash=?",
            (token_hash,),
        ).fetchone()
    if row is None:
        fail(401, "unauthorized", "A valid bearer token is required.")
    return user_public(row)


def require_role(user: dict[str, str], allowed: set[str]) -> None:
    if user["role"] not in allowed:
        fail(403, "forbidden", "Your role cannot perform this action.")


def query_one(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if values is None:
        return None
    if len(values) != 1:
        fail(400, "invalid_query", f"{key} must be provided at most once.")
    return values[0]


def parse_limit(query: dict[str, list[str]], default: int) -> int:
    raw = query_one(query, "limit")
    if raw is None:
        return default
    if len(raw) > 3 or not re.fullmatch(r"[0-9]+", raw):
        fail(400, "invalid_query", "limit must be an integer from 1 to 100.")
    limit = int(raw)
    if not 1 <= limit <= 100:
        fail(400, "invalid_query", "limit must be an integer from 1 to 100.")
    return limit


def encode_cursor(seq: int) -> str:
    return base64.urlsafe_b64encode(str(seq).encode("ascii")).decode("ascii").rstrip("=")


def decode_cursor(raw: str | None) -> int:
    if raw is None:
        return 0
    if not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        fail(400, "invalid_cursor", "cursor is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("ascii")
        if not re.fullmatch(r"[1-9][0-9]*", decoded):
            raise ValueError()
        return int(decoded)
    except (ValueError, UnicodeDecodeError):
        fail(400, "invalid_cursor", "cursor is invalid.")


def mutation_key(handler: BaseHTTPRequestHandler) -> str:
    key = handler.headers.get("Idempotency-Key", "")
    if not key.strip():
        fail(400, "idempotency_key_required", "A nonempty Idempotency-Key header is required.")
    if len(key) > 200:
        fail(400, "invalid_idempotency_key", "Idempotency-Key must be at most 200 characters.")
    return key


def run_mutation(
    handler: BaseHTTPRequestHandler,
    user: dict[str, str],
    body: dict[str, Any],
    action: Callable[[sqlite3.Connection], tuple[int, Any]],
) -> tuple[int, Any]:
    key = mutation_key(handler)
    method = handler.command.upper()
    path = urlsplit(handler.path).path
    request_json = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with open_db() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            previous = db.execute(
                "SELECT method,path,request_json,status_code,response_json FROM idempotency WHERE tenant_id=? AND key=?",
                (user["tenant"], key),
            ).fetchone()
            if previous is not None:
                if (previous["method"], previous["path"], previous["request_json"]) != (method, path, request_json):
                    fail(409, "idempotency_conflict", "This idempotency key was already used for a different request.")
                result = (int(previous["status_code"]), json.loads(previous["response_json"]))
                db.commit()
                return result
            status, response = action(db)
            response_json = json.dumps(response, separators=(",", ":"), ensure_ascii=False)
            db.execute(
                "INSERT INTO idempotency(tenant_id,key,method,path,request_json,status_code,response_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (user["tenant"], key, method, path, request_json, status, response_json, utc_now()),
            )
            db.commit()
            return status, response
        except Exception:
            db.rollback()
            raise


def require_order(db: sqlite3.Connection, tenant: str, order_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM orders WHERE tenant_id=? AND id=?", (tenant, order_id)).fetchone()
    if row is None:
        fail(404, "not_found", "Order not found.")
    return row


def expected_order_version(body: dict[str, Any], order: sqlite3.Row) -> int:
    expected = require_int(body.get("expected_version"), "expected_version", minimum=1)
    if expected != int(order["version"]):
        fail(409, "stale_version", "This order changed. Refresh it and try again.")
    return expected


class DepotHandler(BaseHTTPRequestHandler):
    server_version = "DepotFlow/1.0"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the local server quiet; errors are returned as structured JSON.
        return

    def send_json(self, status: int, body: Any) -> None:
        data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, error: ApiError) -> None:
        self.send_json(error.status, {"error": {"code": error.code, "message": error.message}})

    def do_GET(self) -> None:
        try:
            self.handle_get()
        except ApiError as error:
            self.send_error_json(error)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": {"code": "internal_error", "message": "The request could not be completed."}})

    def do_POST(self) -> None:
        try:
            self.handle_post()
        except ApiError as error:
            self.send_error_json(error)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": {"code": "internal_error", "message": "The request could not be completed."}})

    def do_PUT(self) -> None:
        self.send_json(405, {"error": {"code": "method_not_allowed", "message": "Method not allowed."}})

    def do_DELETE(self) -> None:
        self.send_json(405, {"error": {"code": "method_not_allowed", "message": "Method not allowed."}})

    def do_PATCH(self) -> None:
        self.send_json(405, {"error": {"code": "method_not_allowed", "message": "Method not allowed."}})

    def do_OPTIONS(self) -> None:
        self.send_json(405, {"error": {"code": "method_not_allowed", "message": "Method not allowed."}})

    def handle_get(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/" or path in ("/app.js", "/styles.css"):
            self.serve_static(path)
            return
        if path == "/api/health":
            self.send_json(200, {"status": "ok"})
            return
        user = read_user(self)
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=False)
        if path == "/api/me":
            self.send_json(200, user)
        elif path == "/api/inventory":
            with read_db() as db:
                rows = db.execute(
                    "SELECT sku,name,on_hand,reserved,price_cents,version FROM inventory WHERE tenant_id=? ORDER BY sku",
                    (user["tenant"],),
                ).fetchall()
            self.send_json(200, {"items": [inventory_item(row) for row in rows]})
        elif path == "/api/dashboard":
            with read_db() as db:
                statuses = db.execute(
                    "SELECT status,COUNT(*) AS n FROM orders WHERE tenant_id=? GROUP BY status",
                    (user["tenant"],),
                ).fetchall()
                inventory = db.execute(
                    "SELECT on_hand,reserved FROM inventory WHERE tenant_id=?",
                    (user["tenant"],),
                ).fetchall()
            counts = {status: 0 for status in STATUSES}
            counts.update({row["status"]: int(row["n"]) for row in statuses})
            self.send_json(200, {
                "orders_by_status": counts,
                "inventory_units": sum(int(row["on_hand"]) for row in inventory),
                "reserved_units": sum(int(row["reserved"]) for row in inventory),
            })
        elif path == "/api/orders":
            self.list_orders(user, query)
        elif path.startswith("/api/orders/") and "/" not in path[len("/api/orders/"):]:
            order_id = path[len("/api/orders/"):]
            with read_db() as db:
                order = require_order(db, user["tenant"], order_id)
                result = order_object(db, order)
            self.send_json(200, result)
        elif path == "/api/audit":
            self.list_audit(user, query)
        else:
            fail(404, "not_found", "Route not found.")

    def serve_static(self, path: str) -> None:
        files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8")}
        filename, content_type = files[path]
        try:
            content = (ROOT / "static" / filename).read_bytes()
        except OSError:
            fail(500, "static_unavailable", "The user interface is unavailable.")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def list_orders(self, user: dict[str, str], query: dict[str, list[str]]) -> None:
        unknown = set(query) - {"status", "q", "limit", "cursor"}
        if unknown:
            fail(400, "invalid_query", f"Unsupported order filter: {sorted(unknown)[0]}.")
        raw_status = query_one(query, "status")
        if raw_status is not None and raw_status not in STATUSES:
            fail(400, "invalid_query", "status is not a supported order status.")
        q = query_one(query, "q")
        if q is None:
            q = ""
        if len(q) > 300:
            fail(400, "invalid_query", "q must be at most 300 characters.")
        limit = parse_limit(query, 20)
        cursor = decode_cursor(query_one(query, "cursor"))
        clauses = ["tenant_id=?", "seq>?"]
        params: list[Any] = [user["tenant"], cursor]
        if raw_status is not None:
            clauses.append("status=?")
            params.append(raw_status)
        with read_db() as db:
            highest = db.execute("SELECT COALESCE(MAX(seq),0) FROM orders WHERE tenant_id=?", (user["tenant"],)).fetchone()[0]
            if cursor > int(highest):
                fail(400, "invalid_cursor", "cursor does not belong to an existing order position.")
            rows = db.execute(
                f"SELECT * FROM orders WHERE {' AND '.join(clauses)} ORDER BY seq",
                params,
            ).fetchall()
            if q:
                folded = q.casefold()
                rows = [row for row in rows if folded in row["client_ref"].casefold()]
            has_more = len(rows) > limit
            page = rows[:limit]
            items = [order_object(db, row) for row in page]
        next_cursor = encode_cursor(int(page[-1]["seq"])) if has_more and page else None
        self.send_json(200, {"items": items, "next_cursor": next_cursor})

    def list_audit(self, user: dict[str, str], query: dict[str, list[str]]) -> None:
        unknown = set(query) - {"limit", "cursor"}
        if unknown:
            fail(400, "invalid_query", f"Unsupported audit filter: {sorted(unknown)[0]}.")
        limit = parse_limit(query, 20)
        cursor = decode_cursor(query_one(query, "cursor"))
        with read_db() as db:
            highest = db.execute("SELECT COALESCE(MAX(seq),0) FROM audit_events WHERE tenant_id=?", (user["tenant"],)).fetchone()[0]
            if cursor > int(highest):
                fail(400, "invalid_cursor", "cursor does not belong to an existing audit position.")
            rows = db.execute(
                "SELECT seq,id,action,entity_id,actor,created_at FROM audit_events WHERE tenant_id=? AND seq>? ORDER BY seq LIMIT ?",
                (user["tenant"], cursor, limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            page = rows[:limit]
        items = [{"id": row["id"], "action": row["action"], "entity_id": row["entity_id"], "actor": row["actor"], "created_at": row["created_at"]} for row in page]
        next_cursor = encode_cursor(int(page[-1]["seq"])) if has_more and page else None
        self.send_json(200, {"items": items, "next_cursor": next_cursor})

    def handle_post(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/api/session":
            self.login()
            return
        user = read_user(self)
        if path == "/api/stock/adjustments":
            require_role(user, {"admin"})
            body = parse_json_body(self)
            status, result = run_mutation(self, user, body, lambda db: self.adjust_stock(db, user, body))
            self.send_json(status, result)
            return
        if path == "/api/orders":
            require_role(user, {"admin", "operator"})
            body = parse_json_body(self)
            status, result = run_mutation(self, user, body, lambda db: self.create_order(db, user, body))
            self.send_json(status, result)
            return
        match = re.fullmatch(r"/api/orders/([^/]+)/(reserve|ship|cancel|returns)", path)
        if match:
            require_role(user, {"admin", "operator"})
            body = parse_json_body(self)
            order_id, operation = match.groups()
            status, result = run_mutation(self, user, body, lambda db: self.transition_order(db, user, order_id, operation, body))
            self.send_json(status, result)
            return
        fail(404, "not_found", "Route not found.")

    def login(self) -> None:
        body = parse_json_body(self)
        email = require_string(body.get("email"), "email")
        password = require_string(body.get("password"), "password")
        with read_db() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row is None:
            fail(401, "invalid_credentials", "Email or password is incorrect.")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), row["password_salt"], 180_000)
        if not hmac.compare_digest(candidate, row["password_hash"]):
            fail(401, "invalid_credentials", "Email or password is incorrect.")
        token = secrets.token_urlsafe(32)
        with open_db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO sessions(token_hash,email,created_at) VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), email, utc_now()))
            db.commit()
        self.send_json(200, {"token": token, "user": user_public(row)})

    def adjust_stock(self, db: sqlite3.Connection, user: dict[str, str], body: dict[str, Any]) -> tuple[int, Any]:
        sku = require_string(body.get("sku"), "sku")
        delta = require_int(body.get("delta"), "delta")
        if delta == 0:
            fail(400, "invalid_payload", "delta must not be zero.")
        expected = require_int(body.get("expected_version"), "expected_version", minimum=1)
        reason = require_string(body.get("reason"), "reason")
        row = db.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant"], sku)).fetchone()
        if row is None:
            fail(400, "unknown_sku", "SKU does not exist.")
        if expected != int(row["version"]):
            fail(409, "stale_version", "Inventory changed. Refresh it and try again.")
        new_on_hand = int(row["on_hand"]) + delta
        if new_on_hand < int(row["reserved"]):
            fail(409, "insufficient_stock", "Adjustment cannot reduce stock below reserved units.")
        if new_on_hand < 0 or new_on_hand > MAX_INT64:
            fail(409, "insufficient_stock", "Adjustment would put stock outside the supported range.")
        db.execute("UPDATE inventory SET on_hand=?,version=version+1 WHERE tenant_id=? AND sku=?", (new_on_hand, user["tenant"], sku))
        updated = db.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant"], sku)).fetchone()
        add_audit(db, user["tenant"], "stock.adjusted", sku, user["email"])
        return 200, inventory_item(updated)

    def create_order(self, db: sqlite3.Connection, user: dict[str, str], body: dict[str, Any]) -> tuple[int, Any]:
        client_ref = require_string(body.get("client_ref"), "client_ref")
        lines = body.get("lines")
        if not isinstance(lines, list) or not lines:
            fail(400, "invalid_payload", "lines must be a nonempty array.")
        normalized: list[tuple[str, int, int]] = []
        seen: set[str] = set()
        total = 0
        for index, line in enumerate(lines):
            if not isinstance(line, dict):
                fail(400, "invalid_payload", f"lines[{index}] must be an object.")
            sku = require_string(line.get("sku"), f"lines[{index}].sku")
            quantity = require_int(line.get("quantity"), f"lines[{index}].quantity", minimum=1)
            if sku in seen:
                fail(400, "duplicate_sku", "An order cannot contain the same SKU more than once.")
            seen.add(sku)
            inventory = db.execute("SELECT price_cents FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant"], sku)).fetchone()
            if inventory is None:
                fail(400, "unknown_sku", f"Unknown SKU: {sku}.")
            unit_price = int(inventory["price_cents"])
            line_total = quantity * unit_price
            if line_total > MAX_INT64 or total + line_total > MAX_INT64:
                fail(400, "invalid_payload", "Order total exceeds the supported integer range.")
            total += line_total
            normalized.append((sku, quantity, unit_price))
        if db.execute("SELECT 1 FROM orders WHERE tenant_id=? AND client_ref=?", (user["tenant"], client_ref)).fetchone():
            fail(409, "duplicate_client_ref", "client_ref is already used in this tenant.")
        order_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO orders(id,tenant_id,client_ref,status,version,total_cents,created_at) VALUES (?,?,?,'draft',1,?,?)",
            (order_id, user["tenant"], client_ref, total, utc_now()),
        )
        for sku, quantity, unit_price in normalized:
            db.execute("INSERT INTO order_lines(order_id,sku,quantity,unit_price_cents,returned_quantity) VALUES (?,?,?, ?,0)", (order_id, sku, quantity, unit_price))
        row = require_order(db, user["tenant"], order_id)
        result = order_object(db, row)
        add_audit(db, user["tenant"], "order.created", order_id, user["email"])
        return 201, result

    def transition_order(self, db: sqlite3.Connection, user: dict[str, str], order_id: str, operation: str, body: dict[str, Any]) -> tuple[int, Any]:
        order = require_order(db, user["tenant"], order_id)
        expected_order_version(body, order)
        lines = db.execute("SELECT * FROM order_lines WHERE order_id=? ORDER BY rowid", (order_id,)).fetchall()
        by_sku = {line["sku"]: line for line in lines}
        status = order["status"]

        if operation == "reserve":
            if status != "draft":
                fail(409, "invalid_transition", "Only draft orders can be reserved.")
            inventory_rows: dict[str, sqlite3.Row] = {}
            for line in lines:
                item = db.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant"], line["sku"])).fetchone()
                inventory_rows[line["sku"]] = item
                if int(item["on_hand"]) - int(item["reserved"]) < int(line["quantity"]):
                    fail(409, "insufficient_stock", f"Insufficient available stock for {line['sku']}.")
            for line in lines:
                item = inventory_rows[line["sku"]]
                db.execute(
                    "UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant_id=? AND sku=?",
                    (int(line["quantity"]), user["tenant"], line["sku"]),
                )
            new_status, action = "reserved", "order.reserved"
        elif operation == "ship":
            if status != "reserved":
                fail(409, "invalid_transition", "Only reserved orders can be shipped.")
            for line in lines:
                item = db.execute("SELECT on_hand,reserved FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant"], line["sku"])).fetchone()
                if item is None or int(item["reserved"]) < int(line["quantity"]) or int(item["on_hand"]) < int(line["quantity"]):
                    fail(409, "insufficient_stock", f"Reserved stock is unavailable for {line['sku']}.")
            for line in lines:
                quantity = int(line["quantity"])
                db.execute(
                    "UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=?",
                    (quantity, quantity, user["tenant"], line["sku"]),
                )
            new_status, action = "shipped", "order.shipped"
        elif operation == "cancel":
            if status not in {"draft", "reserved"}:
                fail(409, "invalid_transition", "Only draft or reserved orders can be cancelled.")
            if status == "reserved":
                for line in lines:
                    item = db.execute("SELECT reserved FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant"], line["sku"])).fetchone()
                    if item is None or int(item["reserved"]) < int(line["quantity"]):
                        fail(409, "invalid_inventory", "Reserved inventory no longer matches this order.")
                for line in lines:
                    db.execute(
                        "UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=?",
                        (int(line["quantity"]), user["tenant"], line["sku"]),
                    )
            new_status, action = "cancelled", "order.cancelled"
        else:  # returns
            if status != "shipped":
                fail(409, "invalid_transition", "Only shipped orders can receive returns.")
            return_lines = body.get("lines")
            if not isinstance(return_lines, list) or not return_lines:
                fail(400, "invalid_payload", "lines must be a nonempty array.")
            normalized_returns: list[tuple[str, int]] = []
            seen: set[str] = set()
            for index, line in enumerate(return_lines):
                if not isinstance(line, dict):
                    fail(400, "invalid_payload", f"lines[{index}] must be an object.")
                sku = require_string(line.get("sku"), f"lines[{index}].sku")
                quantity = require_int(line.get("quantity"), f"lines[{index}].quantity", minimum=1)
                if sku in seen:
                    fail(400, "duplicate_sku", "A return cannot contain the same SKU more than once.")
                seen.add(sku)
                order_line = by_sku.get(sku)
                if order_line is None:
                    fail(400, "invalid_return", f"SKU {sku} is not on this order.")
                if int(order_line["returned_quantity"]) + quantity > int(order_line["quantity"]):
                    fail(409, "return_exceeds_shipped", f"Return quantity exceeds shipped units for {sku}.")
                normalized_returns.append((sku, quantity))
            for sku, quantity in normalized_returns:
                item = db.execute("SELECT on_hand FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant"], sku)).fetchone()
                if item is None or int(item["on_hand"]) > MAX_INT64 - quantity:
                    fail(409, "inventory_limit", f"Returning {sku} would exceed the supported inventory range.")
                db.execute(
                    "UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?",
                    (quantity, order_id, sku),
                )
                db.execute(
                    "UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant_id=? AND sku=?",
                    (quantity, user["tenant"], sku),
                )
            all_returned = all(
                int(line["returned_quantity"]) + next((q for sku, q in normalized_returns if sku == line["sku"]), 0) == int(line["quantity"])
                for line in lines
            )
            new_status = "returned" if all_returned else "shipped"
            action = "order.returned" if new_status == "returned" else "order.returned_partial"

        db.execute("UPDATE orders SET status=?,version=version+1 WHERE tenant_id=? AND id=?", (new_status, user["tenant"], order_id))
        updated = require_order(db, user["tenant"], order_id)
        result = order_object(db, updated)
        add_audit(db, user["tenant"], action, order_id, user["email"])
        return 200, result


def main() -> None:
    initialize()
    raw_port = os.environ.get("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise SystemExit("PORT must be an integer between 1 and 65535") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be an integer between 1 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), DepotHandler)
    server.daemon_threads = True
    print(f"DepotFlow listening on http://127.0.0.1:{port} (data: {DB_PATH})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
