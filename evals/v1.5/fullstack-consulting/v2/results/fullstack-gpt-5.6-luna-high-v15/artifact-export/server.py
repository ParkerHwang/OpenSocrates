#!/usr/bin/env python3
import base64
import hashlib
import json
import os
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
STATIC_DIR = ROOT / "static"
PASSWORD = "DepotDemo!2026"
TENANTS = ("north", "south")
CATALOG = (
    ("BOLT", "Steel bolt kit", 100, 1250),
    ("CABLE", "Cable assembly", 60, 2499),
    ("SAMPLE", "Sample pack", 20, 0),
)
ROLES = {"admin", "operator", "viewer"}
STATUSES = {"draft", "reserved", "shipped", "cancelled", "returned"}
DB_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def require_int(value, name, minimum=None):
    if not is_int(value) or (minimum is not None and value < minimum):
        raise ApiError(400, "invalid_payload", f"{name} must be an integer" if minimum is None else f"{name} must be an integer >= {minimum}")
    return value


def password_hash(password):
    return hashlib.sha256(("depotflow:" + password).encode()).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def cursor_encode(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def cursor_decode(value):
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if not isinstance(decoded, list) or len(decoded) != 1 or not is_int(decoded[0]) or decoded[0] < 0:
            raise ValueError
        return decoded[0]
    except Exception:
        raise ApiError(400, "invalid_cursor", "cursor is invalid")


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    conn = connect()
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tenant TEXT NOT NULL,
          email TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
          password_hash TEXT NOT NULL,
          UNIQUE(tenant, email)
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inventory (
          tenant TEXT NOT NULL,
          sku TEXT NOT NULL,
          name TEXT NOT NULL,
          on_hand INTEGER NOT NULL CHECK(on_hand >= 0),
          reserved INTEGER NOT NULL CHECK(reserved >= 0 AND reserved <= on_hand),
          price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
          version INTEGER NOT NULL CHECK(version >= 1),
          PRIMARY KEY(tenant, sku)
        );
        CREATE TABLE IF NOT EXISTS orders (
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          id TEXT NOT NULL UNIQUE,
          tenant TEXT NOT NULL,
          client_ref TEXT NOT NULL,
          status TEXT NOT NULL,
          version INTEGER NOT NULL CHECK(version >= 1),
          total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
          created_at TEXT NOT NULL,
          UNIQUE(tenant, client_ref)
        );
        CREATE TABLE IF NOT EXISTS order_lines (
          order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
          sku TEXT NOT NULL,
          quantity INTEGER NOT NULL CHECK(quantity > 0),
          unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
          returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(returned_quantity >= 0),
          PRIMARY KEY(order_id, sku)
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
          status INTEGER NOT NULL,
          response_body TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(tenant, idem_key)
        );
        CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant, seq);
        CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant, id);
        """
    )
    conn.close()


def seed_if_empty():
    if os.environ.get("SEED_DEMO") != "1":
        return
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if sum(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("users", "sessions", "inventory", "orders", "order_lines", "audit", "idempotency")) == 0:
            for tenant in TENANTS:
                for role in ("admin", "operator", "viewer"):
                    conn.execute("INSERT INTO users(tenant,email,role,password_hash) VALUES(?,?,?,?)", (tenant, f"{role}@{tenant}.example", role, password_hash(PASSWORD)))
                for sku, name, on_hand, price in CATALOG:
                    conn.execute("INSERT INTO inventory(tenant,sku,name,on_hand,reserved,price_cents,version) VALUES(?,?,?,?,?,?,1)", (tenant, sku, name, on_hand, 0, price))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def public_user(row):
    return {"email": row["email"], "role": row["role"], "tenant": row["tenant"]}


def inventory_item(row):
    return {"sku": row["sku"], "name": row["name"], "on_hand": row["on_hand"], "reserved": row["reserved"], "available": row["on_hand"] - row["reserved"], "price_cents": row["price_cents"], "version": row["version"]}


def order_json(conn, order_id):
    order = conn.execute("SELECT id,client_ref,status,version,total_cents FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        return None
    lines = conn.execute("SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid", (order_id,)).fetchall()
    return {"id": order["id"], "client_ref": order["client_ref"], "status": order["status"], "version": order["version"], "total_cents": order["total_cents"], "lines": [{"sku": r["sku"], "quantity": r["quantity"], "unit_price_cents": r["unit_price_cents"], "returned_quantity": r["returned_quantity"]} for r in lines]}


def add_audit(conn, tenant, action, entity_id, actor):
    conn.execute("INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES(?,?,?,?,?)", (tenant, action, entity_id, actor, now()))


def parse_json(handler):
    length = handler.headers.get("Content-Length")
    if length is None:
        raise ApiError(400, "invalid_json", "request body is required")
    try:
        raw = handler.rfile.read(int(length))
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ApiError(400, "invalid_json", "request body must be valid JSON")
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_payload", "request body must be an object")
    return value


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status, body):
        encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, error):
        self.send_json(error.status, {"error": {"code": error.code, "message": error.message}})

    def do_GET(self):
        try:
            self.handle_get()
        except ApiError as e:
            self.send_error_json(e)
        except Exception:
            self.send_error_json(ApiError(500, "internal_error", "internal server error"))

    def do_POST(self):
        try:
            self.handle_post()
        except ApiError as e:
            self.send_error_json(e)
        except sqlite3.IntegrityError as e:
            self.send_error_json(ApiError(409, "conflict", "request conflicts with existing data"))
        except Exception:
            self.send_error_json(ApiError(500, "internal_error", "internal server error"))

    def authenticate(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            raise ApiError(401, "unauthorized", "a valid bearer token is required")
        conn = connect()
        row = conn.execute("SELECT u.id,u.email,u.role,u.tenant FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (header[7:].strip(),)).fetchone()
        conn.close()
        if not row:
            raise ApiError(401, "unauthorized", "a valid bearer token is required")
        return dict(row)

    def require_mutation_access(self, user, admin=False):
        if user["role"] == "viewer":
            raise ApiError(403, "forbidden", "viewer users cannot mutate data")
        if admin and user["role"] != "admin":
            raise ApiError(403, "forbidden", "administrator role required")

    def mutation_context(self, user, body):
        key = self.headers.get("Idempotency-Key", "").strip()
        if not key:
            raise ApiError(400, "missing_idempotency_key", "Idempotency-Key is required")
        if len(key) > 200:
            raise ApiError(400, "invalid_idempotency_key", "Idempotency-Key is too long")
        path = urlparse(self.path).path
        digest = hashlib.sha256(json_bytes(body)).hexdigest()
        conn = connect()
        conn.execute("BEGIN IMMEDIATE")
        prior = conn.execute("SELECT method,path,payload_hash,status,response_body FROM idempotency WHERE tenant=? AND idem_key=?", (user["tenant"], key)).fetchone()
        if prior:
            if prior["method"] != self.command or prior["path"] != path or prior["payload_hash"] != digest:
                conn.rollback(); conn.close()
                raise ApiError(409, "idempotency_conflict", "Idempotency-Key was already used with a different request")
            result = (prior["status"], json.loads(prior["response_body"]))
            conn.rollback(); conn.close()
            return None, result
        return conn, (key, digest, path)

    def finish_mutation(self, conn, user, key_info, status, body):
        key, digest, path = key_info
        conn.execute("INSERT INTO idempotency(tenant,idem_key,method,path,payload_hash,status,response_body,created_at) VALUES(?,?,?,?,?,?,?,?)", (user["tenant"], key, self.command, path, digest, status, json.dumps(body, separators=(",", ":"), ensure_ascii=False), now()))
        conn.commit()
        conn.close()
        self.send_json(status, body)

    def handle_get(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json(200, {"status": "ok"}); return
        if path == "/" or path == "/index.html":
            self.serve_static("index.html", "text/html; charset=utf-8"); return
        if path.startswith("/static/"):
            filename = path.removeprefix("/static/")
            if filename not in {"app.js", "style.css"}:
                raise ApiError(404, "not_found", "not found")
            mime = "application/javascript; charset=utf-8" if filename.endswith(".js") else "text/css; charset=utf-8"
            self.serve_static(filename, mime); return
        user = self.authenticate()
        conn = connect()
        try:
            if path == "/api/me":
                self.send_json(200, {"email": user["email"], "role": user["role"], "tenant": user["tenant"]}); return
            if path == "/api/inventory":
                rows = conn.execute("SELECT sku,name,on_hand,reserved,price_cents,version FROM inventory WHERE tenant=? ORDER BY sku", (user["tenant"],)).fetchall()
                self.send_json(200, {"items": [inventory_item(r) for r in rows]}); return
            if path == "/api/dashboard":
                counts = {s: 0 for s in STATUSES}
                for r in conn.execute("SELECT status,COUNT(*) AS n FROM orders WHERE tenant=? GROUP BY status", (user["tenant"],)):
                    counts[r["status"]] = r["n"]
                stock = conn.execute("SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0) FROM inventory WHERE tenant=?", (user["tenant"],)).fetchone()
                self.send_json(200, {"orders_by_status": counts, "inventory_units": stock[0], "reserved_units": stock[1]}); return
            if path == "/api/orders":
                self.list_orders(conn, user); return
            if path.startswith("/api/orders/") and path.count("/") == 3:
                order_id = path.split("/")[3]
                row = conn.execute("SELECT id FROM orders WHERE tenant=? AND id=?", (user["tenant"], order_id)).fetchone()
                if not row: raise ApiError(404, "not_found", "order not found")
                self.send_json(200, order_json(conn, order_id)); return
            if path == "/api/audit":
                self.list_audit(conn, user); return
            raise ApiError(404, "not_found", "not found")
        finally:
            conn.close()

    def serve_static(self, filename, mime):
        file = STATIC_DIR / filename
        if not file.exists(): raise ApiError(404, "not_found", "not found")
        data = file.read_bytes()
        self.send_response(200); self.send_header("Content-Type", mime); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def list_orders(self, conn, user):
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        status = query.get("status", [None])[0]
        q = query.get("q", [None])[0]
        limit_raw = query.get("limit", ["20"])[0]
        if status is not None and status not in STATUSES: raise ApiError(400, "invalid_filter", "status is invalid")
        if q is not None and not isinstance(q, str): raise ApiError(400, "invalid_filter", "q is invalid")
        try: limit = int(limit_raw)
        except Exception: raise ApiError(400, "invalid_filter", "limit must be an integer")
        if str(limit) != limit_raw or limit < 1 or limit > 100: raise ApiError(400, "invalid_filter", "limit must be between 1 and 100")
        cursor = query.get("cursor", [None])[0]
        after = cursor_decode(cursor) if cursor is not None else None
        clauses = ["tenant=?"]; args = [user["tenant"]]
        if status: clauses.append("status=?"); args.append(status)
        if q is not None: clauses.append("LOWER(client_ref) LIKE ?"); args.append("%" + q.lower() + "%")
        if after is not None: clauses.append("seq > ?"); args.append(after)
        sql = "SELECT seq,id FROM orders WHERE " + " AND ".join(clauses) + " ORDER BY seq LIMIT ?"
        args.append(limit + 1)
        rows = conn.execute(sql, args).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        items = [order_json(conn, r["id"]) for r in rows]
        self.send_json(200, {"items": items, "next_cursor": cursor_encode([rows[-1]["seq"]]) if more and rows else None})

    def list_audit(self, conn, user):
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        limit_raw = query.get("limit", ["20"])[0]
        try: limit = int(limit_raw)
        except Exception: raise ApiError(400, "invalid_filter", "limit must be an integer")
        if str(limit) != limit_raw or limit < 1 or limit > 100: raise ApiError(400, "invalid_filter", "limit must be between 1 and 100")
        cursor = query.get("cursor", [None])[0]
        after = cursor_decode(cursor) if cursor is not None else None
        sql = "SELECT id,action,entity_id,actor,created_at FROM audit WHERE tenant=?"; args = [user["tenant"]]
        if after is not None: sql += " AND id > ?"; args.append(after)
        sql += " ORDER BY id LIMIT ?"; args.append(limit + 1)
        rows = conn.execute(sql, args).fetchall(); more = len(rows) > limit; rows = rows[:limit]
        items = [{"id": r["id"], "action": r["action"], "entity_id": r["entity_id"], "actor": r["actor"], "created_at": r["created_at"]} for r in rows]
        self.send_json(200, {"items": items, "next_cursor": cursor_encode([rows[-1]["id"]]) if more and rows else None})

    def handle_post(self):
        path = urlparse(self.path).path
        if path == "/api/session":
            body = parse_json(self); self.create_session(body); return
        user = self.authenticate()
        body = parse_json(self)
        if path == "/api/stock/adjustments": self.require_mutation_access(user, admin=True)
        else: self.require_mutation_access(user)
        conn, info = self.mutation_context(user, body)
        if conn is None:
            self.send_json(info[0], info[1]); return
        try:
            if path == "/api/stock/adjustments": status, result = self.stock_adjust(conn, user, body)
            elif path == "/api/orders": status, result = self.create_order(conn, user, body)
            else:
                parts = path.split("/")
                if len(parts) != 5 or parts[1:3] != ["api", "orders"]: raise ApiError(404, "not_found", "not found")
                order_id, action = parts[3], parts[4]
                if action not in {"reserve", "ship", "cancel", "returns"}: raise ApiError(404, "not_found", "not found")
                status, result = self.transition(conn, user, order_id, action, body)
            self.finish_mutation(conn, user, info, status, result)
        except Exception:
            conn.rollback(); conn.close(); raise

    def create_session(self, body):
        if set(body) != {"email", "password"} or not isinstance(body["email"], str) or not isinstance(body["password"], str):
            raise ApiError(400, "invalid_payload", "email and password are required")
        conn = connect(); row = conn.execute("SELECT id,email,role,tenant,password_hash FROM users WHERE email=?", (body["email"].strip().lower(),)).fetchone()
        if not row or not secrets.compare_digest(row["password_hash"], password_hash(body["password"])):
            conn.close(); raise ApiError(401, "invalid_credentials", "email or password is incorrect")
        token = secrets.token_urlsafe(32); conn.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (token, row["id"], now())); conn.close()
        self.send_json(200, {"token": token, "user": public_user(row)})

    def stock_adjust(self, conn, user, body):
        if set(body) != {"sku", "delta", "expected_version", "reason"} or not isinstance(body.get("sku"), str) or not isinstance(body.get("reason"), str) or not body["reason"].strip():
            raise ApiError(400, "invalid_payload", "sku, delta, expected_version and nonempty reason are required")
        delta = require_int(body["delta"], "delta"); expected = require_int(body["expected_version"], "expected_version", 1)
        if delta == 0: raise ApiError(400, "invalid_payload", "delta must be nonzero")
        row = conn.execute("SELECT sku,name,on_hand,reserved,price_cents,version FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], body["sku"])).fetchone()
        if not row: raise ApiError(400, "unknown_sku", "sku is not in the catalog")
        if row["version"] != expected: raise ApiError(409, "stale_version", "inventory version is stale")
        if row["on_hand"] + delta < row["reserved"]: raise ApiError(409, "insufficient_stock", "adjustment would reduce stock below reserved units")
        conn.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?", (delta, user["tenant"], body["sku"]))
        updated = conn.execute("SELECT sku,name,on_hand,reserved,price_cents,version FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], body["sku"])).fetchone()
        add_audit(conn, user["tenant"], "stock.adjustment", body["sku"], user["email"])
        return 200, inventory_item(updated)

    def create_order(self, conn, user, body):
        if set(body) != {"client_ref", "lines"} or not isinstance(body.get("client_ref"), str) or not body["client_ref"].strip() or not isinstance(body.get("lines"), list) or not body["lines"]:
            raise ApiError(400, "invalid_payload", "client_ref and a nonempty lines array are required")
        client_ref = body["client_ref"].strip()
        seen = set(); lines = []; total = 0
        for line in body["lines"]:
            if not isinstance(line, dict) or set(line) != {"sku", "quantity"} or not isinstance(line.get("sku"), str): raise ApiError(400, "invalid_payload", "each line requires sku and quantity")
            sku = line["sku"]
            qty = require_int(line.get("quantity"), "quantity", 1)
            if sku in seen: raise ApiError(400, "duplicate_sku", "duplicate sku lines are not allowed")
            seen.add(sku); inv = conn.execute("SELECT sku,price_cents FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], sku)).fetchone()
            if not inv: raise ApiError(400, "unknown_sku", "sku is not in the catalog")
            lines.append((sku, qty, inv["price_cents"])); total += qty * inv["price_cents"]
        order_id = str(uuid.uuid4()); created = now()
        try:
            conn.execute("INSERT INTO orders(id,tenant,client_ref,status,version,total_cents,created_at) VALUES(?,?,?,?,?,?,?)", (order_id, user["tenant"], client_ref, "draft", 1, total, created))
        except sqlite3.IntegrityError:
            raise ApiError(409, "duplicate_client_ref", "client_ref is already used")
        for sku, qty, price in lines:
            conn.execute("INSERT INTO order_lines(order_id,sku,quantity,unit_price_cents) VALUES(?,?,?,?)", (order_id, sku, qty, price))
        add_audit(conn, user["tenant"], "order.created", order_id, user["email"])
        return 201, order_json(conn, order_id)

    def transition(self, conn, user, order_id, action, body):
        row = conn.execute("SELECT id,tenant,status,version FROM orders WHERE tenant=? AND id=?", (user["tenant"], order_id)).fetchone()
        if not row: raise ApiError(404, "not_found", "order not found")
        expected = require_int(body.get("expected_version"), "expected_version", 1)
        if row["version"] != expected: raise ApiError(409, "stale_version", "order version is stale")
        lines = conn.execute("SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid", (order_id,)).fetchall()
        if action == "returns": return self.returns(conn, user, row, lines, body)
        if set(body) != {"expected_version"}: raise ApiError(400, "invalid_payload", "expected_version is required")
        target = {"reserve": "reserved", "ship": "shipped", "cancel": "cancelled"}[action]
        allowed = {"reserve": {"draft"}, "ship": {"reserved"}, "cancel": {"draft", "reserved"}}[action]
        if row["status"] not in allowed: raise ApiError(409, "invalid_transition", f"cannot {action} an order in {row['status']} status")
        if action == "reserve":
            for line in lines:
                inv = conn.execute("SELECT on_hand,reserved FROM inventory WHERE tenant=? AND sku=?", (user["tenant"], line["sku"])).fetchone()
                if inv["on_hand"] - inv["reserved"] < line["quantity"]: raise ApiError(409, "insufficient_stock", f"insufficient available stock for {line['sku']}")
            for line in lines: conn.execute("UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?", (line["quantity"], user["tenant"], line["sku"]))
        elif action == "ship":
            for line in lines: conn.execute("UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?", (line["quantity"], line["quantity"], user["tenant"], line["sku"]))
        elif action == "cancel" and row["status"] == "reserved":
            for line in lines: conn.execute("UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?", (line["quantity"], user["tenant"], line["sku"]))
        conn.execute("UPDATE orders SET status=?,version=version+1 WHERE id=?", (target, order_id))
        add_audit(conn, user["tenant"], "order." + action, order_id, user["email"])
        return 200, order_json(conn, order_id)

    def returns(self, conn, user, row, lines, body):
        if set(body) != {"expected_version", "lines"} or not isinstance(body["lines"], list) or not body["lines"]: raise ApiError(400, "invalid_payload", "returns requires a nonempty lines array")
        if row["status"] != "shipped": raise ApiError(409, "invalid_transition", "only shipped orders can receive returns")
        seen = set(); requested = []
        by_sku = {r["sku"]: r for r in lines}
        for line in body["lines"]:
            if not isinstance(line, dict) or set(line) != {"sku", "quantity"} or not isinstance(line.get("sku"), str): raise ApiError(400, "invalid_payload", "each return line requires sku and quantity")
            if line["sku"] in seen: raise ApiError(400, "duplicate_sku", "duplicate return sku lines are not allowed")
            seen.add(line["sku"]); qty = require_int(line.get("quantity"), "quantity", 1)
            if line["sku"] not in by_sku: raise ApiError(400, "invalid_payload", "return sku is not on the order")
            item = by_sku[line["sku"]]
            if item["returned_quantity"] + qty > item["quantity"]: raise ApiError(409, "return_exceeds_shipped", "return quantity exceeds shipped quantity")
            requested.append((line["sku"], qty, item))
        for sku, qty, item in requested:
            conn.execute("UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?", (qty, row["id"], sku))
            conn.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?", (qty, user["tenant"], sku))
        requested_by_sku = {sku: qty for sku, qty, _ in requested}
        complete = all(item["returned_quantity"] + requested_by_sku[item["sku"]] == item["quantity"] for item in lines if item["sku"] in requested_by_sku) and all(item["returned_quantity"] == item["quantity"] for item in lines if item["sku"] not in requested_by_sku)
        if complete: conn.execute("UPDATE orders SET status='returned',version=version+1 WHERE id=?", (row["id"],))
        else: conn.execute("UPDATE orders SET version=version+1 WHERE id=?", (row["id"],))
        add_audit(conn, user["tenant"], "order.returns", row["id"], user["email"])
        return 200, order_json(conn, row["id"])


def main():
    init_db(); seed_if_empty()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"DepotFlow listening on http://127.0.0.1:{port} (data: {DB_PATH})", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()
