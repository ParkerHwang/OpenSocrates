#!/usr/bin/env python3
"""DepotFlow: a small, durable multi-tenant fulfillment service."""
import base64
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
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
DB_PATH = DATA_DIR / "depotflow.sqlite3"
PORT = int(os.environ.get("PORT", "8000"))
SEED_DEMO = os.environ.get("SEED_DEMO") == "1"
PASSWORD = "DepotDemo!2026"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS tenants (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
  tenant_id TEXT NOT NULL REFERENCES tenants(id), password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory (
  tenant_id TEXT NOT NULL REFERENCES tenants(id), sku TEXT NOT NULL,
  name TEXT NOT NULL, on_hand INTEGER NOT NULL CHECK(on_hand >= 0),
  reserved INTEGER NOT NULL CHECK(reserved >= 0), price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
  version INTEGER NOT NULL CHECK(version >= 1), PRIMARY KEY(tenant_id, sku)
);
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), client_ref TEXT NOT NULL,
  status TEXT NOT NULL, version INTEGER NOT NULL CHECK(version >= 1), total_cents INTEGER NOT NULL,
  created_at TEXT NOT NULL, UNIQUE(tenant_id, client_ref)
);
CREATE TABLE IF NOT EXISTS order_lines (
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE, sku TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity > 0), unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
  returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(returned_quantity >= 0), PRIMARY KEY(order_id, sku)
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  action TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
  tenant_id TEXT NOT NULL REFERENCES tenants(id), idem_key TEXT NOT NULL, method TEXT NOT NULL,
  path TEXT NOT NULL, payload_hash TEXT NOT NULL, status INTEGER NOT NULL, body_json TEXT NOT NULL,
  created_at TEXT NOT NULL, PRIMARY KEY(tenant_id, idem_key)
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS orders_tenant_created ON orders(tenant_id, created_at, id);
CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant_id, id);
"""

class HttpError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message

def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")

def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)

def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def connect():
    db = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    return db

def seed_if_empty(db):
    if not SEED_DEMO or db.execute("SELECT 1 FROM tenants LIMIT 1").fetchone():
        return
    stock = [("BOLT", "Steel bolt kit", 100, 1250), ("CABLE", "Cable assembly", 60, 2499), ("SAMPLE", "Sample pack", 20, 0)]
    db.execute("BEGIN IMMEDIATE")
    try:
        for tenant in ("north", "south"):
            db.execute("INSERT INTO tenants(id) VALUES (?)", (tenant,))
            for role in ("admin", "operator", "viewer"):
                email = f"{role}@{tenant}.example"
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), email, role, tenant, password_hash(PASSWORD)))
            for sku, name, on_hand, price in stock:
                db.execute("INSERT INTO inventory VALUES (?, ?, ?, ?, 0, ?, 1)", (tenant, sku, name, on_hand, price))
        db.commit()
    except Exception:
        db.rollback()
        raise

def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = connect()
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    seed_if_empty(db)
    db.close()

def error_body(code, message):
    return {"error": {"code": code, "message": message}}

def encode_cursor(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")

def decode_cursor(value, expected_len):
    if not value or not isinstance(value, str):
        raise HttpError(400, "invalid_cursor", "Cursor is invalid")
    try:
        padded = value + "=" * (-len(value) % 4)
        parsed = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if not isinstance(parsed, list) or len(parsed) != expected_len:
            raise ValueError
        return parsed
    except Exception:
        raise HttpError(400, "invalid_cursor", "Cursor is invalid")

def limit_param(params):
    raw = params.get("limit", ["20"])[0]
    if not re.fullmatch(r"[0-9]+", raw or "") or not 1 <= int(raw) <= 100:
        raise HttpError(400, "invalid_limit", "limit must be an integer from 1 to 100")
    return int(raw)

def parse_json_bytes(raw):
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HttpError(400, "invalid_json", "Request body must be valid JSON")
    if not isinstance(value, dict):
        raise HttpError(400, "invalid_payload", "Request body must be a JSON object")
    return value

def require_str(value, name, nonempty=True):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise HttpError(400, "invalid_payload", f"{name} must be a non-empty string")
    return value.strip() if nonempty else value

def require_positive(value, name="quantity"):
    if not integer(value) or value <= 0:
        raise HttpError(400, "invalid_quantity", f"{name} must be a positive integer")
    return value

def require_version(payload):
    value = payload.get("expected_version")
    if not integer(value) or value < 1:
        raise HttpError(400, "invalid_version", "expected_version must be a positive integer")
    return value

def payload_fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

class App(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status, body):
        data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, name, content_type):
        path = ROOT / "static" / name
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                return self.send_json(200, {"status": "ok"})
            if parsed.path == "/" or parsed.path == "/index.html":
                return self.send_file("index.html", "text/html; charset=utf-8")
            if parsed.path == "/app.js":
                return self.send_file("app.js", "text/javascript; charset=utf-8")
            if parsed.path == "/styles.css":
                return self.send_file("styles.css", "text/css; charset=utf-8")
            user = self.auth()
            db = connect()
            try:
                result = self.get_api(db, parsed.path, parse_qs(parsed.query, keep_blank_values=True), user)
            finally:
                db.close()
            return self.send_json(200, result)
        except HttpError as exc:
            return self.send_json(exc.status, error_body(exc.code, exc.message))
        except Exception as exc:
            print(f"GET failure: {exc}", flush=True)
            return self.send_json(500, error_body("internal_error", "An unexpected server error occurred"))

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise HttpError(400, "payload_too_large", "Request body is too large")
            payload = parse_json_bytes(self.rfile.read(length))
            if parsed.path == "/api/session":
                return self.session(payload)
            user = self.auth()
            self.authorize_mutation(parsed.path, user)
            key = self.headers.get("Idempotency-Key", "").strip()
            if not key:
                raise HttpError(400, "missing_idempotency_key", "Idempotency-Key is required")
            db = connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                replay = self.check_idempotency(db, user, key, parsed.path, payload)
                if replay:
                    db.commit()
                    return self.send_json(*replay)
                status, result = self.mutate(db, parsed.path, payload, user)
                self.save_idempotency(db, user, key, parsed.path, payload, status, result)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
            return self.send_json(status, result)
        except HttpError as exc:
            return self.send_json(exc.status, error_body(exc.code, exc.message))
        except sqlite3.IntegrityError as exc:
            return self.send_json(409, error_body("conflict", "The requested change conflicts with existing data"))
        except Exception as exc:
            print(f"POST failure: {exc}", flush=True)
            return self.send_json(500, error_body("internal_error", "An unexpected server error occurred"))

    def session(self, payload):
        email = payload.get("email")
        password = payload.get("password")
        if not isinstance(email, str) or not email.strip() or not isinstance(password, str):
            raise HttpError(401, "invalid_credentials", "Email or password is incorrect")
        email = email.strip()
        db = connect()
        try:
            row = db.execute("SELECT id,email,role,tenant_id FROM users WHERE email=? AND password_hash=?", (email, password_hash(password))).fetchone()
            if not row:
                raise HttpError(401, "invalid_credentials", "Email or password is incorrect")
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], now()))
        finally:
            db.close()
        return self.send_json(200, {"token": token, "user": self.user_json(row)})

    def user_json(self, row):
        return {"email": row["email"], "role": row["role"], "tenant": row["tenant_id"]}

    def auth(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            raise HttpError(401, "unauthorized", "A valid bearer token is required")
        token_hash = hashlib.sha256(header[7:].strip().encode()).hexdigest()
        db = connect()
        try:
            row = db.execute("SELECT u.id,u.email,u.role,u.tenant_id FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (token_hash,)).fetchone()
        finally:
            db.close()
        if not row:
            raise HttpError(401, "unauthorized", "A valid bearer token is required")
        return row

    def authorize_mutation(self, path, user):
        if user["role"] == "viewer":
            raise HttpError(403, "forbidden", "Viewer accounts cannot mutate data")
        if path == "/api/stock/adjustments" and user["role"] != "admin":
            raise HttpError(403, "forbidden", "Only admins can adjust stock")

    def check_idempotency(self, db, user, key, path, payload):
        row = db.execute("SELECT method,path,payload_hash,status,body_json FROM idempotency WHERE tenant_id=? AND idem_key=?", (user["tenant_id"], key)).fetchone()
        if not row:
            return None
        if row["method"] != "POST" or row["path"] != path or row["payload_hash"] != payload_fingerprint(payload):
            raise HttpError(409, "idempotency_conflict", "Idempotency-Key was already used with a different request")
        return row["status"], json.loads(row["body_json"])

    def save_idempotency(self, db, user, key, path, payload, status, result):
        db.execute("INSERT INTO idempotency VALUES (?, ?, 'POST', ?, ?, ?, ?, ?)", (user["tenant_id"], key, path, payload_fingerprint(payload), status, json.dumps(result, separators=(",", ":"), ensure_ascii=False), now()))

    def get_api(self, db, path, params, user):
        tenant = user["tenant_id"]
        if path == "/api/me":
            return self.user_json(user)
        if path == "/api/inventory":
            return {"items": [self.inventory_json(r) for r in db.execute("SELECT * FROM inventory WHERE tenant_id=? ORDER BY sku", (tenant,))]}
        if path == "/api/dashboard":
            counts = {r["status"]: r["count"] for r in db.execute("SELECT status,COUNT(*) count FROM orders WHERE tenant_id=? GROUP BY status", (tenant,))}
            inv = db.execute("SELECT COALESCE(SUM(on_hand),0) units,COALESCE(SUM(reserved),0) reserved FROM inventory WHERE tenant_id=?", (tenant,)).fetchone()
            return {"orders_by_status": counts, "inventory_units": inv["units"], "reserved_units": inv["reserved"]}
        if path == "/api/audit":
            limit = limit_param(params)
            cursor = params.get("cursor", [None])[0]
            after = 0
            if cursor is not None:
                values = decode_cursor(cursor, 1)
                if not integer(values[0]) or values[0] < 0:
                    raise HttpError(400, "invalid_cursor", "Cursor is invalid")
                after = values[0]
            rows = db.execute("SELECT id,action,entity_id,actor,created_at FROM audit WHERE tenant_id=? AND id>? ORDER BY id LIMIT ?", (tenant, after, limit + 1)).fetchall()
            items = [dict(r) for r in rows[:limit]]
            return {"items": items, "next_cursor": encode_cursor([items[-1]["id"]]) if len(rows) > limit else None}
        if path == "/api/orders":
            limit = limit_param(params)
            status = params.get("status", [None])[0]
            if status is not None and status not in {"draft", "reserved", "shipped", "cancelled", "returned"}:
                raise HttpError(400, "invalid_status", "status filter is invalid")
            q = params.get("q", [None])[0]
            if q is not None and not isinstance(q, str):
                raise HttpError(400, "invalid_query", "q must be text")
            cursor = params.get("cursor", [None])[0]
            after_created, after_id = "", ""
            if cursor is not None:
                values = decode_cursor(cursor, 2)
                if not all(isinstance(v, str) and v for v in values):
                    raise HttpError(400, "invalid_cursor", "Cursor is invalid")
                after_created, after_id = values
            clauses = ["tenant_id=?", "(created_at>? OR (created_at=? AND id>?))"]
            args = [tenant, after_created, after_created, after_id]
            if status:
                clauses.append("status=?"); args.append(status)
            if q is not None:
                clauses.append("LOWER(client_ref) LIKE ?"); args.append("%" + q.lower() + "%")
            sql = "SELECT * FROM orders WHERE " + " AND ".join(clauses) + " ORDER BY created_at,id LIMIT ?"
            args.append(limit + 1)
            rows = db.execute(sql, args).fetchall()
            items = [self.order_json(db, r) for r in rows[:limit]]
            return {"items": items, "next_cursor": encode_cursor([rows[limit-1]["created_at"], rows[limit-1]["id"]]) if len(rows) > limit else None}
        match = re.fullmatch(r"/api/orders/([^/]+)", path)
        if match:
            row = db.execute("SELECT * FROM orders WHERE id=? AND tenant_id=?", (match.group(1), tenant)).fetchone()
            if not row:
                raise HttpError(404, "not_found", "Order not found")
            return self.order_json(db, row)
        raise HttpError(404, "not_found", "Route not found")

    def inventory_json(self, row):
        result = {"sku": row["sku"], "name": row["name"], "on_hand": row["on_hand"], "reserved": row["reserved"], "available": row["on_hand"] - row["reserved"], "price_cents": row["price_cents"], "version": row["version"]}
        if result["available"] < 0:
            raise RuntimeError("inventory invariant violated")
        return result

    def order_json(self, db, row):
        lines = db.execute("SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid", (row["id"],)).fetchall()
        return {"id": row["id"], "client_ref": row["client_ref"], "status": row["status"], "version": row["version"], "total_cents": row["total_cents"], "lines": [dict(x) for x in lines]}

    def mutate(self, db, path, payload, user):
        if path == "/api/stock/adjustments":
            return self.stock_adjust(db, payload, user)
        if path == "/api/orders":
            return self.create_order(db, payload, user)
        match = re.fullmatch(r"/api/orders/([^/]+)/(reserve|ship|cancel|returns)", path)
        if match:
            if match.group(2) == "returns":
                return self.return_order(db, match.group(1), payload, user)
            return self.transition(db, match.group(1), match.group(2), payload, user)
        raise HttpError(404, "not_found", "Route not found")

    def stock_adjust(self, db, payload, user):
        sku = require_str(payload.get("sku"), "sku")
        delta = payload.get("delta")
        if not integer(delta) or delta == 0:
            raise HttpError(400, "invalid_delta", "delta must be a nonzero integer")
        expected = require_version(payload)
        reason = require_str(payload.get("reason"), "reason")
        row = db.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant_id"], sku)).fetchone()
        if not row:
            raise HttpError(400, "unknown_sku", "SKU does not exist")
        if row["version"] != expected:
            raise HttpError(409, "stale_version", "Inventory has changed; refresh and retry")
        if row["on_hand"] + delta < row["reserved"]:
            raise HttpError(409, "insufficient_stock", "Adjustment would reduce stock below reserved units")
        db.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant_id=? AND sku=?", (delta, user["tenant_id"], sku))
        updated = db.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant_id"], sku)).fetchone()
        self.audit(db, user, "stock_adjusted", sku)
        return 200, self.inventory_json(updated)

    def normalized_lines(self, db, tenant, payload):
        lines = payload.get("lines")
        if not isinstance(lines, list) or not lines:
            raise HttpError(400, "invalid_lines", "lines must be a non-empty array")
        seen = set(); normalized = []
        for line in lines:
            if not isinstance(line, dict):
                raise HttpError(400, "invalid_lines", "Each line must be an object")
            sku = require_str(line.get("sku"), "sku")
            if sku in seen:
                raise HttpError(400, "duplicate_sku", "Each SKU may appear only once")
            qty = require_positive(line.get("quantity"))
            row = db.execute("SELECT sku,price_cents FROM inventory WHERE tenant_id=? AND sku=?", (tenant, sku)).fetchone()
            if not row:
                raise HttpError(400, "unknown_sku", "SKU does not exist")
            seen.add(sku)
            normalized.append((sku, qty, row["price_cents"]))
        return normalized

    def create_order(self, db, payload, user):
        client_ref = require_str(payload.get("client_ref"), "client_ref")
        lines = self.normalized_lines(db, user["tenant_id"], payload)
        if db.execute("SELECT 1 FROM orders WHERE tenant_id=? AND client_ref=?", (user["tenant_id"], client_ref)).fetchone():
            raise HttpError(409, "duplicate_client_ref", "client_ref is already in use")
        order_id = str(uuid.uuid4())
        total = sum(qty * price for _, qty, price in lines)
        created = now()
        db.execute("INSERT INTO orders VALUES (?, ?, ?, 'draft', 1, ?, ?)", (order_id, user["tenant_id"], client_ref, total, created))
        for sku, qty, price in lines:
            db.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?, 0)", (order_id, sku, qty, price))
        self.audit(db, user, "order_created", order_id)
        return 201, self.order_json(db, db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())

    def load_order(self, db, order_id, user):
        row = db.execute("SELECT * FROM orders WHERE id=? AND tenant_id=?", (order_id, user["tenant_id"])).fetchone()
        if not row:
            raise HttpError(404, "not_found", "Order not found")
        return row

    def transition(self, db, order_id, action, payload, user):
        order = self.load_order(db, order_id, user)
        expected = require_version(payload)
        if order["version"] != expected:
            raise HttpError(409, "stale_version", "Order has changed; refresh and retry")
        lines = db.execute("SELECT * FROM order_lines WHERE order_id=?", (order_id,)).fetchall()
        if action == "reserve":
            if order["status"] != "draft":
                raise HttpError(409, "invalid_transition", "Only draft orders can be reserved")
            for line in lines:
                stock = db.execute("SELECT * FROM inventory WHERE tenant_id=? AND sku=?", (user["tenant_id"], line["sku"])).fetchone()
                if stock["on_hand"] - stock["reserved"] < line["quantity"]:
                    raise HttpError(409, "insufficient_stock", f"Insufficient available stock for {line['sku']}")
            for line in lines:
                db.execute("UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant_id=? AND sku=?", (line["quantity"], user["tenant_id"], line["sku"]))
            next_status = "reserved"
        elif action == "ship":
            if order["status"] != "reserved":
                raise HttpError(409, "invalid_transition", "Only reserved orders can be shipped")
            for line in lines:
                changed = db.execute("UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=? AND on_hand>=? AND reserved>=?", (line["quantity"], line["quantity"], user["tenant_id"], line["sku"], line["quantity"], line["quantity"])).rowcount
                if changed != 1:
                    raise HttpError(409, "insufficient_stock", "Stock changed before shipping")
            next_status = "shipped"
        else:
            if order["status"] not in ("draft", "reserved"):
                raise HttpError(409, "invalid_transition", "Only draft or reserved orders can be cancelled")
            if order["status"] == "reserved":
                for line in lines:
                    changed = db.execute("UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant_id=? AND sku=? AND reserved>=?", (line["quantity"], user["tenant_id"], line["sku"], line["quantity"])).rowcount
                    if changed != 1:
                        raise HttpError(409, "conflict", "Reserved stock changed before cancellation")
            next_status = "cancelled"
        db.execute("UPDATE orders SET status=?,version=version+1 WHERE id=?", (next_status, order_id))
        self.audit(db, user, {"reserve": "order_reserved", "ship": "order_shipped", "cancel": "order_cancelled"}[action], order_id)
        return 200, self.order_json(db, db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())

    def return_order(self, db, order_id, payload, user):
        order = self.load_order(db, order_id, user)
        expected = require_version(payload)
        if order["version"] != expected:
            raise HttpError(409, "stale_version", "Order has changed; refresh and retry")
        if order["status"] != "shipped":
            raise HttpError(409, "invalid_transition", "Only shipped orders can receive returns")
        raw_lines = payload.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raise HttpError(400, "invalid_lines", "lines must be a non-empty array")
        originals = {r["sku"]: r for r in db.execute("SELECT * FROM order_lines WHERE order_id=?", (order_id,))}
        seen = set(); returns = []
        for line in raw_lines:
            if not isinstance(line, dict):
                raise HttpError(400, "invalid_lines", "Each line must be an object")
            sku = require_str(line.get("sku"), "sku")
            qty = require_positive(line.get("quantity"))
            if sku in seen or sku not in originals:
                raise HttpError(400, "invalid_return_line", "Return SKU must be unique and belong to the order")
            if originals[sku]["returned_quantity"] + qty > originals[sku]["quantity"]:
                raise HttpError(409, "return_exceeds_shipped", f"Return exceeds shipped quantity for {sku}")
            seen.add(sku); returns.append((sku, qty))
        for sku, qty in returns:
            db.execute("UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?", (qty, order_id, sku))
            db.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant_id=? AND sku=?", (qty, user["tenant_id"], sku))
        after = db.execute("SELECT quantity,returned_quantity FROM order_lines WHERE order_id=?", (order_id,)).fetchall()
        next_status = "returned" if all(r["quantity"] == r["returned_quantity"] for r in after) else "shipped"
        db.execute("UPDATE orders SET status=?,version=version+1 WHERE id=?", (next_status, order_id))
        self.audit(db, user, "order_returned", order_id)
        return 200, self.order_json(db, db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())

    def audit(self, db, user, action, entity_id):
        db.execute("INSERT INTO audit(tenant_id,action,entity_id,actor,created_at) VALUES (?, ?, ?, ?, ?)", (user["tenant_id"], action, entity_id, user["email"], now()))

def main():
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), App)
    print(f"DepotFlow listening on http://127.0.0.1:{PORT} (data: {DB_PATH})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
