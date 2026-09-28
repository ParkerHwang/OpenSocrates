#!/usr/bin/env python3
"""DepotFlow: dependency-free local fulfillment service."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data"))).resolve()
DB_PATH = DATA_DIR / "depotflow.sqlite3"
PORT = int(os.environ.get("PORT", "8000"))
SEED = os.environ.get("SEED_DEMO") == "1"
SKU_DATA = [("BOLT", "Steel bolt kit", 100, 1250), ("CABLE", "Cable assembly", 60, 2499), ("SAMPLE", "Sample pack", 20, 0)]
PASSWORD = "DepotDemo!2026"
INIT_LOCK = threading.Lock()
MAX_INT = 2**63 - 1


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def connect():
    c = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    return salt.hex(), hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 160000).hex()


def initialize():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with INIT_LOCK:
        c = connect()
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, tenant TEXT NOT NULL, role TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inventory(tenant TEXT NOT NULL, sku TEXT NOT NULL, name TEXT NOT NULL, on_hand INTEGER NOT NULL CHECK(on_hand>=0), reserved INTEGER NOT NULL CHECK(reserved>=0 AND reserved<=on_hand), price_cents INTEGER NOT NULL CHECK(price_cents>=0), version INTEGER NOT NULL CHECK(version>0), PRIMARY KEY(tenant,sku));
        CREATE TABLE IF NOT EXISTS orders(sort_id INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, tenant TEXT NOT NULL, client_ref TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL, total_cents INTEGER NOT NULL, created_at TEXT NOT NULL, UNIQUE(tenant,client_ref));
        CREATE TABLE IF NOT EXISTS order_lines(order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE, sku TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price_cents INTEGER NOT NULL, returned_quantity INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(order_id,sku));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, action TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(tenant,key));
        CREATE INDEX IF NOT EXISTS idx_orders_tenant_sort ON orders(tenant,sort_id);
        CREATE INDEX IF NOT EXISTS idx_audit_tenant_id ON audit(tenant,id);
        """)
        if SEED:
            c.execute("BEGIN IMMEDIATE")
            try:
                populated = c.execute("SELECT (SELECT COUNT(*) FROM users)+(SELECT COUNT(*) FROM inventory)+(SELECT COUNT(*) FROM orders)+(SELECT COUNT(*) FROM audit)+(SELECT COUNT(*) FROM idempotency)").fetchone()[0]
                if populated == 0:
                    for tenant in ("north", "south"):
                        for role in ("admin", "operator", "viewer"):
                            email = f"{role}@{tenant}.example"
                            salt, digest = password_hash(PASSWORD)
                            c.execute("INSERT INTO users(email,tenant,role,salt,password_hash) VALUES(?,?,?,?,?)", (email, tenant, role, salt, digest))
                        c.executemany("INSERT INTO inventory(tenant,sku,name,on_hand,reserved,price_cents,version) VALUES(?,?,?, ?,0,?,1)", [(tenant, *x) for x in SKU_DATA])
                c.commit()
            except Exception:
                c.rollback(); raise
        c.close()


def integer(v):
    return isinstance(v, int) and not isinstance(v, bool)


def require_int(v, name, minimum=None):
    if not integer(v) or abs(v) > MAX_INT or (minimum is not None and v < minimum):
        raise ApiError(400, "invalid_payload", f"{name} must be an integer" + (f" >= {minimum}" if minimum is not None else ""))
    return v


def require_object(value):
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_payload", "Request body must be a JSON object")
    return value


def require_text(v, name):
    if not isinstance(v, str) or not v.strip():
        raise ApiError(400, "invalid_payload", f"{name} must be nonempty text")
    return v.strip()


def item_row(r):
    return {"sku": r["sku"], "name": r["name"], "on_hand": r["on_hand"], "reserved": r["reserved"], "available": r["on_hand"] - r["reserved"], "price_cents": r["price_cents"], "version": r["version"]}


def order_obj(c, order):
    if not order: return None
    lines = c.execute("SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid", (order["id"],)).fetchall()
    return {"id": order["id"], "client_ref": order["client_ref"], "status": order["status"], "version": order["version"], "total_cents": order["total_cents"], "lines": [dict(x) for x in lines]}


def cursor_encode(kind, n, scope=""):
    return base64.urlsafe_b64encode(f"{kind}:{n}:{scope}".encode()).decode().rstrip("=")


def cursor_decode(token, kind, c, tenant, scope=""):
    try:
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]+", token): raise ValueError()
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        if base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=") != token: raise ValueError()
        prefix, number, cursor_scope = raw.split(":", 2)
        n = int(number)
        if prefix != kind or n <= 0 or str(n) != number or cursor_scope != scope: raise ValueError()
        table, col = ("orders", "sort_id") if kind == "orders" else ("audit", "id")
        if not c.execute(f"SELECT 1 FROM {table} WHERE tenant=? AND {col}=?", (tenant, n)).fetchone(): raise ValueError()
        return n
    except Exception:
        raise ApiError(400, "invalid_cursor", "Cursor is invalid for this tenant or collection")


class DepotHTTPServer(ThreadingHTTPServer):
    request_queue_size = 256


class Handler(BaseHTTPRequestHandler):
    server_version = "DepotFlow/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1": super().log_message(fmt, *args)

    def send_json(self, status, body, headers=None):
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(data)

    def read_body(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n < 0 or n > 1_000_000: raise ValueError()
            raw = self.rfile.read(n)
            return require_object(json.loads(raw or b"{}"))
        except ApiError: raise
        except Exception: raise ApiError(400, "invalid_json", "Request body must be valid JSON")

    def user(self, c):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:]: raise ApiError(401, "unauthorized", "A valid bearer token is required")
        digest = hashlib.sha256(header[7:].encode()).hexdigest()
        r = c.execute("SELECT u.email,u.tenant,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (digest,)).fetchone()
        if not r: raise ApiError(401, "unauthorized", "A valid bearer token is required")
        return dict(r)

    def require_operator(self, u, admin=False):
        if u["role"] == "viewer": raise ApiError(403, "forbidden", "Viewer accounts cannot make changes")
        if admin and u["role"] != "admin": raise ApiError(403, "forbidden", "Administrator role required")

    def audit(self, c, u, action, entity):
        c.execute("INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES(?,?,?,?,?)", (u["tenant"], action, str(entity), u["email"], datetime.now(timezone.utc).isoformat()))

    def mutation(self, c, u, body, action):
        self.require_operator(u, admin=action == "stock.adjustment")
        key = self.headers.get("Idempotency-Key", "")
        if not key.strip(): raise ApiError(400, "idempotency_key_required", "Idempotency-Key header is required")
        fingerprint = hashlib.sha256(json.dumps([self.command, urlparse(self.path).path, body], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        old = c.execute("SELECT fingerprint,status,body FROM idempotency WHERE tenant=? AND key=?", (u["tenant"], key)).fetchone()
        if old:
            if old["fingerprint"] != fingerprint: raise ApiError(409, "idempotency_conflict", "Idempotency-Key was already used for a different request")
            return old["status"], json.loads(old["body"]), True
        return None

    def finish_mutation(self, c, u, key, status, body):
        # fingerprint was captured by mutation() and placed on the handler
        c.execute("INSERT INTO idempotency(tenant,key,fingerprint,status,body,created_at) VALUES(?,?,?,?,?,?)", (u["tenant"], key, self._fingerprint, status, json.dumps(body, separators=(",", ":")), datetime.now(timezone.utc).isoformat()))
        return status, body

    def do_GET(self): self.dispatch("GET")
    def do_POST(self): self.dispatch("POST")

    def dispatch(self, method):
        self.command = method
        path = urlparse(self.path).path
        c = connect()
        try:
            if path == "/api/health" and method == "GET": return self.send_json(200, {"status": "ok"})
            if not path.startswith("/api/"):
                if method == "GET": return self.serve_ui(path)
                raise ApiError(404, "not_found", "Route not found")
            if path == "/api/session" and method == "POST": return self.session(c)
            u = self.user(c)
            if path == "/api/me" and method == "GET": return self.send_json(200, u)
            if path == "/api/inventory" and method == "GET":
                rows = c.execute("SELECT * FROM inventory WHERE tenant=? ORDER BY sku", (u["tenant"],)).fetchall()
                return self.send_json(200, {"items": [item_row(x) for x in rows]})
            if path == "/api/dashboard" and method == "GET":
                counts = {r["status"]: r["n"] for r in c.execute("SELECT status,COUNT(*) n FROM orders WHERE tenant=? GROUP BY status", (u["tenant"],))}
                inv = c.execute("SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0) FROM inventory WHERE tenant=?", (u["tenant"],)).fetchone()
                return self.send_json(200, {"orders_by_status": counts, "inventory_units": inv[0], "reserved_units": inv[1]})
            if path == "/api/orders" and method == "GET": return self.list_orders(c, u)
            if path == "/api/audit" and method == "GET": return self.list_audit(c, u)
            match = re.fullmatch(r"/api/orders/([^/]+)", path)
            if match and method == "GET":
                o = c.execute("SELECT * FROM orders WHERE id=? AND tenant=?", (match.group(1), u["tenant"])).fetchone()
                if not o: raise ApiError(404, "not_found", "Order not found")
                return self.send_json(200, order_obj(c, o))
            if method == "POST":
                self.require_operator(u, admin=path == "/api/stock/adjustments")
                return self.post_mutation(c, u, path)
            raise ApiError(404, "not_found", "Route not found")
        except ApiError as e:
            self.send_json(e.status, {"error": {"code": e.code, "message": e.message}})
        except Exception:
            self.send_json(500, {"error": {"code": "internal_error", "message": "Unexpected server error"}})
        finally: c.close()

    def serve_ui(self, path):
        target = ROOT / "static" / ("index.html" if path == "/" else path.lstrip("/"))
        if not target.resolve().is_relative_to((ROOT / "static").resolve()) or not target.is_file():
            self.send_error(404); return
        data = target.read_bytes(); typ = "text/html" if target.suffix == ".html" else "text/css" if target.suffix == ".css" else "application/javascript"
        self.send_response(200); self.send_header("Content-Type", typ + "; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def session(self, c):
        body = self.read_body()
        email = body.get("email"); password = body.get("password")
        if not isinstance(email, str) or not isinstance(password, str): raise ApiError(400, "invalid_payload", "email and password are required")
        row = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not row or not hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(row["salt"]), 160000).hex(), row["password_hash"]):
            raise ApiError(401, "bad_credentials", "Email or password is incorrect")
        token = secrets.token_urlsafe(32)
        c.execute("INSERT INTO sessions(token_hash,user_id,created_at) VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], datetime.now(timezone.utc).isoformat()))
        user = {"email": row["email"], "role": row["role"], "tenant": row["tenant"]}
        self.send_json(200, {"token": token, "user": user})

    def list_orders(self, c, u):
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if set(qs) - {"status", "q", "limit", "cursor"} or any(len(v) != 1 for v in qs.values()): raise ApiError(400, "invalid_filter", "Invalid order filters")
        status = qs.get("status", [""])[0]; q = qs.get("q", [""])[0]
        if status and status not in {"draft", "reserved", "shipped", "cancelled", "returned"}: raise ApiError(400, "invalid_filter", "Unknown order status")
        try: limit = int(qs.get("limit", ["20"])[0])
        except ValueError: raise ApiError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        if not 1 <= limit <= 100 or str(limit) != qs.get("limit", [str(limit)])[0]: raise ApiError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        scope=json.dumps([status,q.casefold()],separators=(",",":"))
        after = cursor_decode(qs["cursor"][0], "orders", c, u["tenant"], scope) if "cursor" in qs else 0
        where, params = ["tenant=?", "sort_id>?"], [u["tenant"], after]
        if status: where.append("status=?"); params.append(status)
        rows = c.execute(f"SELECT * FROM orders WHERE {' AND '.join(where)} ORDER BY sort_id", params).fetchall()
        if q: rows = [r for r in rows if q.casefold() in r["client_ref"].casefold()]
        rows = rows[:limit+1]
        more = len(rows) > limit; rows = rows[:limit]
        return self.send_json(200, {"items": [order_obj(c, x) for x in rows], "next_cursor": cursor_encode("orders", rows[-1]["sort_id"], scope) if more else None})

    def list_audit(self, c, u):
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if set(qs) - {"limit", "cursor"} or any(len(v) != 1 for v in qs.values()): raise ApiError(400, "invalid_filter", "Invalid audit filters")
        try: limit = int(qs.get("limit", ["20"])[0])
        except ValueError: raise ApiError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        if not 1 <= limit <= 100 or str(limit) != qs.get("limit", [str(limit)])[0]: raise ApiError(400, "invalid_filter", "limit must be an integer from 1 to 100")
        after = cursor_decode(qs["cursor"][0], "audit", c, u["tenant"]) if "cursor" in qs else 0
        rows = c.execute("SELECT * FROM audit WHERE tenant=? AND id>? ORDER BY id LIMIT ?", (u["tenant"], after, limit+1)).fetchall()
        more = len(rows)>limit; rows=rows[:limit]
        return self.send_json(200, {"items": [{"id": r["id"], "action": r["action"], "entity_id": r["entity_id"], "actor": r["actor"], "created_at": r["created_at"]} for r in rows], "next_cursor": cursor_encode("audit", rows[-1]["id"]) if more else None})

    def post_mutation(self, c, u, path):
        body = self.read_body()
        key = self.headers.get("Idempotency-Key", "")
        c.execute("BEGIN IMMEDIATE")
        try:
            action = "stock.adjustment" if path == "/api/stock/adjustments" else "order.create" if path == "/api/orders" else "order.transition"
            previous = self.mutation(c, u, body, action)
            self._fingerprint = hashlib.sha256(json.dumps([self.command, path, body], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            if previous:
                c.commit(); return self.send_json(previous[0], previous[1])
            if path == "/api/stock/adjustments": status, result = self.adjust_stock(c, u, body)
            elif path == "/api/orders": status, result = self.create_order(c, u, body)
            else:
                m = re.fullmatch(r"/api/orders/([^/]+)/(reserve|ship|cancel|returns)", path)
                if not m: raise ApiError(404, "not_found", "Route not found")
                status, result = self.transition(c, u, m.group(1), m.group(2), body)
            self.finish_mutation(c, u, key, status, result); c.commit(); return self.send_json(status, result)
        except Exception:
            c.rollback(); raise

    def adjust_stock(self, c, u, b):
        delta = require_int(b.get("delta"), "delta")
        if delta == 0: raise ApiError(400, "invalid_payload", "delta must be nonzero")
        sku = require_text(b.get("sku"), "sku"); reason = require_text(b.get("reason"), "reason"); expected = require_int(b.get("expected_version"), "expected_version", 1)
        r = c.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?", (u["tenant"], sku)).fetchone()
        if not r: raise ApiError(400, "unknown_sku", "Unknown SKU")
        if expected != r["version"]: raise ApiError(409, "stale_version", "Inventory version is stale")
        if r["on_hand"] + delta > MAX_INT: raise ApiError(400,"invalid_payload","Adjusted stock is too large")
        if r["on_hand"] + delta < r["reserved"]: raise ApiError(409, "insufficient_stock", "Adjustment cannot reduce stock below reserved units")
        c.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?", (delta,u["tenant"],sku))
        self.audit(c,u,"stock.adjusted",sku)
        return 200, item_row(c.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?",(u["tenant"],sku)).fetchone())

    def parse_lines(self, c, tenant, raw):
        if not isinstance(raw, list) or not raw: raise ApiError(400, "invalid_payload", "lines must be a nonempty array")
        parsed=[]; seen=set()
        for x in raw:
            if not isinstance(x,dict): raise ApiError(400,"invalid_payload","Each line must be an object")
            sku=require_text(x.get("sku"),"sku"); qty=require_int(x.get("quantity"),"quantity",1)
            if sku in seen: raise ApiError(400,"duplicate_sku","SKU lines may not repeat")
            seen.add(sku); inv=c.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?",(tenant,sku)).fetchone()
            if not inv: raise ApiError(400,"unknown_sku",f"Unknown SKU: {sku}")
            parsed.append((sku,qty,inv["price_cents"]))
        return parsed

    def create_order(self,c,u,b):
        self.require_operator(u)
        ref=require_text(b.get("client_ref"),"client_ref")
        lines=self.parse_lines(c,u["tenant"],b.get("lines")); total=sum(q*p for _,q,p in lines); oid=str(uuid.uuid4())
        if total > MAX_INT: raise ApiError(400,"invalid_payload","Order total is too large")
        try:
            c.execute("INSERT INTO orders(id,tenant,client_ref,status,version,total_cents,created_at) VALUES(?,?,?,'draft',1,?,?)",(oid,u["tenant"],ref,total,datetime.now(timezone.utc).isoformat()))
        except sqlite3.IntegrityError: raise ApiError(409,"client_ref_conflict","client_ref is already in use")
        c.executemany("INSERT INTO order_lines(order_id,sku,quantity,unit_price_cents) VALUES(?,?,?,?)",[(oid,s,q,p) for s,q,p in lines])
        self.audit(c,u,"order.created",oid)
        return 201,order_obj(c,c.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone())

    def transition(self,c,u,oid,kind,b):
        self.require_operator(u)
        o=c.execute("SELECT * FROM orders WHERE id=? AND tenant=?",(oid,u["tenant"])).fetchone()
        if not o: raise ApiError(404,"not_found","Order not found")
        expected=require_int(b.get("expected_version"),"expected_version",1)
        if expected!=o["version"]: raise ApiError(409,"stale_version","Order version is stale")
        lines=c.execute("SELECT * FROM order_lines WHERE order_id=? ORDER BY rowid",(oid,)).fetchall()
        new_status=o["status"]
        if kind=="reserve":
            if o["status"]!="draft": raise ApiError(409,"invalid_transition","Only draft orders can be reserved")
            # Validate all stock before any update, within the same immediate transaction.
            for ln in lines:
                inv=c.execute("SELECT * FROM inventory WHERE tenant=? AND sku=?",(u["tenant"],ln["sku"])).fetchone()
                if inv["on_hand"]-inv["reserved"] < ln["quantity"]: raise ApiError(409,"insufficient_stock",f"Insufficient available stock for {ln['sku']}")
            for ln in lines: c.execute("UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?",(ln["quantity"],u["tenant"],ln["sku"]))
            new_status="reserved"
        elif kind=="ship":
            if o["status"]!="reserved": raise ApiError(409,"invalid_transition","Only reserved orders can ship")
            for ln in lines: c.execute("UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?",(ln["quantity"],ln["quantity"],u["tenant"],ln["sku"]))
            new_status="shipped"
        elif kind=="cancel":
            if o["status"] not in ("draft","reserved"): raise ApiError(409,"invalid_transition","Only draft or reserved orders can be cancelled")
            if o["status"]=="reserved":
                for ln in lines: c.execute("UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?",(ln["quantity"],u["tenant"],ln["sku"]))
            new_status="cancelled"
        elif kind=="returns":
            if o["status"]!="shipped": raise ApiError(409,"invalid_transition","Only shipped orders can be returned")
            ret=b.get("lines")
            if not isinstance(ret,list) or not ret: raise ApiError(400,"invalid_payload","lines must be a nonempty array")
            bysku={x["sku"]:x for x in lines}; seen=set(); parsed=[]
            for x in ret:
                if not isinstance(x,dict): raise ApiError(400,"invalid_payload","Each return line must be an object")
                sku=require_text(x.get("sku"),"sku"); qty=require_int(x.get("quantity"),"quantity",1)
                if sku in seen: raise ApiError(400,"duplicate_sku","SKU lines may not repeat")
                if sku not in bysku: raise ApiError(400,"invalid_return_line","SKU is not on this order")
                if bysku[sku]["returned_quantity"]+qty>bysku[sku]["quantity"]: raise ApiError(409,"return_exceeds_shipped","Return quantity exceeds shipped quantity")
                seen.add(sku);parsed.append((sku,qty))
            for sku,qty in parsed:
                inv=c.execute("SELECT on_hand FROM inventory WHERE tenant=? AND sku=?",(u["tenant"],sku)).fetchone()
                if inv["on_hand"]+qty>MAX_INT: raise ApiError(409,"stock_capacity","Returned stock exceeds supported inventory capacity")
                c.execute("UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?",(qty,oid,sku))
                c.execute("UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?",(qty,u["tenant"],sku))
            done=c.execute("SELECT COUNT(*) FROM order_lines WHERE order_id=? AND returned_quantity<quantity",(oid,)).fetchone()[0]==0
            new_status="returned" if done else "shipped"
        else: raise ApiError(404,"not_found","Route not found")
        c.execute("UPDATE orders SET status=?,version=version+1 WHERE id=?",(new_status,oid))
        event={"reserve":"order.reserved","ship":"order.shipped","cancel":"order.cancelled","returns":"order.returned"}[kind]
        self.audit(c,u,event,oid)
        return 200,order_obj(c,c.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone())


def main():
    initialize()
    server=DepotHTTPServer(("127.0.0.1",PORT),Handler)
    print(f"DepotFlow listening on http://127.0.0.1:{PORT} (data: {DB_PATH})",flush=True)
    server.serve_forever()


if __name__=="__main__": main()
