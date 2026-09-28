#!/usr/bin/env python3
"""DepotFlow local HTTP service. All mutations run inside SQLite write transactions."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('DATA_DIR', str(ROOT / 'data')))
DB = DATA_DIR / 'depotflow.sqlite3'
MAX_INT = 2**31 - 1


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def bad(message):
    raise APIError(400, 'bad_request', message)


def conflict(message):
    raise APIError(409, 'conflict', message)


def integer(value, name, *, minimum=0, maximum=MAX_INT):
    if type(value) is not int or not minimum <= value <= maximum:
        bad(f'{name} must be an integer from {minimum} to {maximum}')
    return value


def obj(value):
    if not isinstance(value, dict):
        bad('JSON body must be an object')
    return value


def nonempty(value, name, max_length=200):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        bad(f'{name} must be nonempty text (up to {max_length} characters)')
    return value.strip()


def reject_json_constant(value):
    raise ValueError(f'Invalid JSON constant: {value}')


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 180000)
    return salt.hex() + ':' + digest.hex()


def password_ok(password, stored):
    salt, digest = stored.split(':')
    trial = password_hash(password, bytes.fromhex(salt)).split(':')[1]
    return hmac.compare_digest(trial, digest)


def connect():
    con = sqlite3.connect(DB, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=15000')
    return con


def initialize():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, tenant TEXT NOT NULL REFERENCES tenants(id), email TEXT UNIQUE NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS inventory(tenant TEXT NOT NULL REFERENCES tenants(id), sku TEXT NOT NULL, name TEXT NOT NULL, on_hand INTEGER NOT NULL CHECK(on_hand>=0), reserved INTEGER NOT NULL CHECK(reserved>=0 AND reserved<=on_hand), price_cents INTEGER NOT NULL CHECK(price_cents>=0), version INTEGER NOT NULL CHECK(version>=1), PRIMARY KEY(tenant,sku));
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL REFERENCES tenants(id), client_ref TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL, total_cents INTEGER NOT NULL, UNIQUE(tenant,client_ref));
        CREATE INDEX IF NOT EXISTS orders_tenant_id ON orders(tenant,id);
        CREATE TABLE IF NOT EXISTS order_lines(order_id INTEGER NOT NULL REFERENCES orders(id), sku TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price_cents INTEGER NOT NULL, returned_quantity INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(order_id,sku));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL REFERENCES tenants(id), action TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant,id);
        CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL REFERENCES tenants(id), key TEXT NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL, payload TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(tenant,key));
        ''')
        if os.environ.get('SEED_DEMO') == '1' and con.execute('SELECT COUNT(*) FROM tenants').fetchone()[0] == 0:
            con.execute('BEGIN IMMEDIATE')
            try:
                for tenant in ('north', 'south'):
                    con.execute('INSERT INTO tenants VALUES (?)', (tenant,))
                    for role in ('admin', 'operator', 'viewer'):
                        con.execute('INSERT INTO users(tenant,email,role,password_hash) VALUES (?,?,?,?)',
                                    (tenant, f'{role}@{tenant}.example', role, password_hash('DepotDemo!2026')))
                    for sku, name, stock, price in (('BOLT','Steel bolt kit',100,1250),('CABLE','Cable assembly',60,2499),('SAMPLE','Sample pack',20,0)):
                        con.execute('INSERT INTO inventory VALUES (?,?,?,?,?,?,?)', (tenant,sku,name,stock,0,price,1))
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise


def inventory_item(row):
    return {k: row[k] for k in ('sku','name','on_hand','reserved','price_cents','version')} | {'available': row['on_hand']-row['reserved']}


def order(con, tenant, order_id):
    row = con.execute('SELECT * FROM orders WHERE id=? AND tenant=?', (order_id,tenant)).fetchone()
    if row is None:
        raise APIError(404, 'not_found', 'Order not found')
    lines = con.execute('SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid', (order_id,)).fetchall()
    return {'id':row['id'],'client_ref':row['client_ref'],'status':row['status'],'version':row['version'],
            'total_cents':row['total_cents'],'lines':[dict(line) for line in lines]}


def audit(con, user, action, entity_id):
    con.execute('INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES (?,?,?,?,?)',
                (user['tenant'],action,str(entity_id),user['email'],datetime.now(timezone.utc).isoformat()))


def lines_payload(value, *, name='lines'):
    if not isinstance(value, list) or not value:
        bad(f'{name} must be a nonempty array')
    result, seen = [], set()
    for line in value:
        if not isinstance(line, dict) or not isinstance(line.get('sku'), str) or not line['sku']:
            bad('Each line needs a SKU')
        sku = line['sku']
        if sku in seen:
            bad('Duplicate SKU lines are not allowed')
        seen.add(sku)
        result.append((sku, integer(line.get('quantity'), 'quantity', minimum=1)))
    return result


def apply_mutation(con, user, path, body):
    tenant = user['tenant']
    if path == '/api/stock/adjustments':
        sku = nonempty(body.get('sku'), 'sku', 80)
        delta = integer(body.get('delta'), 'delta', minimum=-MAX_INT)
        if delta == 0: bad('delta must be nonzero')
        expected = integer(body.get('expected_version'), 'expected_version', minimum=1)
        nonempty(body.get('reason'), 'reason', 500)
        row = con.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?', (tenant,sku)).fetchone()
        if row is None: bad('Unknown SKU')
        if row['version'] != expected: conflict('Inventory changed; refresh and retry')
        new_stock = row['on_hand'] + delta
        if new_stock < row['reserved']: conflict('Adjustment would reduce stock below reserved units')
        if new_stock > MAX_INT: bad('Resulting stock is too large')
        con.execute('UPDATE inventory SET on_hand=?,version=version+1 WHERE tenant=? AND sku=?', (new_stock,tenant,sku))
        audit(con,user,'stock.adjusted',sku)
        return inventory_item(con.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?', (tenant,sku)).fetchone())
    if path == '/api/orders':
        ref = nonempty(body.get('client_ref'), 'client_ref', 200)
        lines = lines_payload(body.get('lines'))
        if con.execute('SELECT 1 FROM orders WHERE tenant=? AND client_ref=?', (tenant,ref)).fetchone():
            conflict('Client reference already exists')
        priced, total = [], 0
        for sku, qty in lines:
            item = con.execute('SELECT price_cents FROM inventory WHERE tenant=? AND sku=?', (tenant,sku)).fetchone()
            if item is None: bad(f'Unknown SKU: {sku}')
            total += qty * item['price_cents']
            priced.append((sku,qty,item['price_cents']))
        if total > 2**63-1: bad('Order total is too large')
        cur = con.execute('INSERT INTO orders(tenant,client_ref,status,version,total_cents) VALUES (?,?,?,?,?)', (tenant,ref,'draft',1,total))
        for sku,qty,price in priced:
            con.execute('INSERT INTO order_lines(order_id,sku,quantity,unit_price_cents) VALUES (?,?,?,?)', (cur.lastrowid,sku,qty,price))
        audit(con,user,'order.created',cur.lastrowid)
        return order(con,tenant,cur.lastrowid)
    match = re.fullmatch(r'/api/orders/(\d+)/(reserve|ship|cancel|returns)',path)
    if not match:
        raise APIError(404,'not_found','Route not found')
    order_id, action = int(match[1]), match[2]
    current = order(con,tenant,order_id)
    expected = integer(body.get('expected_version'), 'expected_version', minimum=1)
    if expected != current['version']: conflict('Order changed; refresh and retry')
    status = current['status']
    if action == 'reserve' and status != 'draft': conflict('Only draft orders can be reserved')
    if action == 'ship' and status != 'reserved': conflict('Only reserved orders can be shipped')
    if action == 'cancel' and status not in ('draft','reserved'): conflict('This order cannot be cancelled')
    if action == 'returns' and status != 'shipped': conflict('Only shipped orders can be returned')
    if action == 'returns':
        requested = lines_payload(body.get('lines'))
        existing = {line['sku']:line for line in current['lines']}
        for sku,qty in requested:
            if sku not in existing: bad(f'SKU is not in this order: {sku}')
            if qty + existing[sku]['returned_quantity'] > existing[sku]['quantity']:
                conflict('Returned quantity exceeds shipped quantity')
            item = con.execute('SELECT on_hand FROM inventory WHERE tenant=? AND sku=?', (tenant,sku)).fetchone()
            if item['on_hand'] + qty > MAX_INT: conflict('Return would exceed inventory capacity')
        for sku,qty in requested:
            con.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?', (qty,tenant,sku))
            con.execute('UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?', (qty,order_id,sku))
        all_returned = con.execute('SELECT COUNT(*) FROM order_lines WHERE order_id=? AND returned_quantity<quantity', (order_id,)).fetchone()[0] == 0
        new_status = 'returned' if all_returned else 'shipped'
    else:
        new_status = {'reserve':'reserved','ship':'shipped','cancel':'cancelled'}[action]
        if action == 'reserve':
            for line in current['lines']:
                item = con.execute('SELECT on_hand,reserved FROM inventory WHERE tenant=? AND sku=?', (tenant,line['sku'])).fetchone()
                if item['on_hand']-item['reserved'] < line['quantity']:
                    conflict(f'Insufficient available stock for {line["sku"]}')
            for line in current['lines']:
                con.execute('UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?', (line['quantity'],tenant,line['sku']))
        if action == 'ship':
            for line in current['lines']:
                con.execute('UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',
                            (line['quantity'],line['quantity'],tenant,line['sku']))
        if action == 'cancel' and status == 'reserved':
            for line in current['lines']:
                con.execute('UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?', (line['quantity'],tenant,line['sku']))
    con.execute('UPDATE orders SET status=?,version=version+1 WHERE id=?', (new_status,order_id))
    audit(con,user,'order.' + ('returned' if action == 'returns' else action),order_id)
    return order(con,tenant,order_id)


def encode_cursor(value):
    return base64.urlsafe_b64encode(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).decode().rstrip('=')


def decode_cursor(raw):
    try:
        value = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw)%4)))
        if not isinstance(value,dict) or type(value.get('after')) is not int or type(value.get('max')) is not int or value['after'] < 0 or value['max'] < value['after']:
            raise ValueError()
        return value
    except Exception:
        bad('Invalid cursor')


def query_one(params, key, default=None):
    vals = params.get(key)
    if vals is None: return default
    if len(vals) != 1: bad(f'Invalid {key} parameter')
    return vals[0]


def list_page(con, tenant, path, params):
    allowed = {'limit','cursor'} | ({'status','q'} if path == '/api/orders' else set())
    if set(params)-allowed: bad('Unknown query parameter')
    limit_raw = query_one(params,'limit','20')
    if not re.fullmatch(r'\d+',limit_raw): bad('Invalid limit')
    limit = integer(int(limit_raw),'limit',minimum=1,maximum=100)
    status = query_one(params,'status') if path == '/api/orders' else None
    q = query_one(params,'q','') if path == '/api/orders' else None
    if status is not None and status not in ('draft','reserved','shipped','returned','cancelled'): bad('Invalid status')
    if q is not None and len(q) > 200: bad('Search is too long')
    table = 'orders' if path == '/api/orders' else 'audit'
    raw_cursor = query_one(params,'cursor')
    max_id = con.execute(f'SELECT COALESCE(MAX(id),0) FROM {table} WHERE tenant=?',(tenant,)).fetchone()[0]
    after = 0
    if raw_cursor is not None:
        cursor = decode_cursor(raw_cursor)
        if cursor.get('kind') != table or cursor.get('status') != status or cursor.get('q') != q or cursor['max'] > max_id:
            bad('Cursor does not match this query')
        after, max_id = cursor['after'], cursor['max']
    sql = f'SELECT id FROM {table} WHERE tenant=? AND id>? AND id<=?'
    args = [tenant,after,max_id]
    if table == 'orders':
        if status:
            sql += ' AND status=?'; args.append(status)
        if q:
            sql += ' AND instr(lower(client_ref),lower(?))>0'; args.append(q)
    rows = con.execute(sql+' ORDER BY id LIMIT ?',(*args,limit+1)).fetchall()
    ids = [r['id'] for r in rows[:limit]]
    items = [order(con,tenant,id_) for id_ in ids] if table == 'orders' else [dict(con.execute('SELECT id,action,entity_id,actor,created_at FROM audit WHERE id=?',(id_,)).fetchone()) for id_ in ids]
    next_cursor = encode_cursor({'kind':table,'after':ids[-1],'max':max_id,'status':status,'q':q}) if len(rows)>limit else None
    return {'items':items,'next_cursor':next_cursor}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def send_json(self, status, value):
        data = json.dumps(value,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)

    def read_body(self):
        try:
            size = int(self.headers.get('Content-Length','0'))
            if size < 1 or size > 1024*1024: bad('JSON body is required and must be under 1 MiB')
            return obj(json.loads(self.rfile.read(size),parse_constant=reject_json_constant))
        except (ValueError,UnicodeDecodeError,json.JSONDecodeError):
            bad('Invalid JSON body')

    def do_GET(self): self.dispatch()
    def do_POST(self): self.dispatch()

    def dispatch(self):
        try:
            parsed = urlsplit(self.path)
            path = parsed.path.rstrip('/') or '/'
            fingerprint_path = parsed.path
            if self.command == 'GET' and path == '/api/health':
                return self.send_json(200,{'status':'ok'})
            if self.command == 'GET' and path in ('/','/app.js','/style.css'):
                filename = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path]
                content = (ROOT / 'web' / filename).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type',{'index.html':'text/html; charset=utf-8','app.js':'application/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[filename])
                self.send_header('Content-Length',str(len(content)))
                self.end_headers(); self.wfile.write(content); return
            if not path.startswith('/api/'):
                raise APIError(404,'not_found','Route not found')
            if self.command == 'POST' and path == '/api/session':
                body = self.read_body()
                email, password = body.get('email'), body.get('password')
                with connect() as con:
                    row = con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone() if isinstance(email,str) else None
                    if row is None or not isinstance(password,str) or not password_ok(password,row['password_hash']):
                        raise APIError(401,'unauthorized','Invalid email or password')
                    token = secrets.token_urlsafe(32)
                    con.execute('INSERT INTO sessions VALUES (?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id']))
                    user = {k:row[k] for k in ('email','role','tenant')}
                return self.send_json(200,{'token':token,'user':user})
            auth = self.headers.get('Authorization','')
            if not auth.startswith('Bearer ') or not auth[7:]:
                raise APIError(401,'unauthorized','Sign in is required')
            with connect() as con:
                userrow = con.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token_hash=?',
                                      (hashlib.sha256(auth[7:].encode()).hexdigest(),)).fetchone()
                if userrow is None: raise APIError(401,'unauthorized','Invalid session')
                user = {k:userrow[k] for k in ('email','role','tenant')}
                if self.command == 'GET':
                    params = parse_qs(parsed.query,keep_blank_values=True)
                    if path == '/api/me': return self.send_json(200,user)
                    if path == '/api/inventory':
                        rows = con.execute('SELECT * FROM inventory WHERE tenant=? ORDER BY sku',(user['tenant'],)).fetchall()
                        return self.send_json(200,{'items':[inventory_item(r) for r in rows]})
                    if path == '/api/dashboard':
                        counts = {r['status']:r['n'] for r in con.execute('SELECT status,COUNT(*) n FROM orders WHERE tenant=? GROUP BY status',(user['tenant'],))}
                        units = con.execute('SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0) FROM inventory WHERE tenant=?',(user['tenant'],)).fetchone()
                        return self.send_json(200,{'orders_by_status':counts,'inventory_units':units[0],'reserved_units':units[1]})
                    if path in ('/api/orders','/api/audit'):
                        return self.send_json(200,list_page(con,user['tenant'],path,params))
                    match = re.fullmatch(r'/api/orders/(\d+)',path)
                    if match: return self.send_json(200,order(con,user['tenant'],int(match[1])))
                if self.command == 'POST':
                    if user['role'] == 'viewer': raise APIError(403,'forbidden','Viewer access is read-only')
                    if path == '/api/stock/adjustments' and user['role'] != 'admin':
                        raise APIError(403,'forbidden','Only admins can adjust stock')
                    if path != '/api/stock/adjustments' and path != '/api/orders' and not re.fullmatch(r'/api/orders/\d+/(reserve|ship|cancel|returns)',path):
                        raise APIError(404,'not_found','Route not found')
                    key = self.headers.get('Idempotency-Key','')
                    if not key.strip() or len(key)>200: bad('A nonempty Idempotency-Key is required')
                    body = self.read_body()
                    canonical = json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False)
                    con.execute('BEGIN IMMEDIATE')
                    try:
                        previous = con.execute('SELECT * FROM idempotency WHERE tenant=? AND key=?',(user['tenant'],key)).fetchone()
                        if previous:
                            if previous['method'] != self.command or previous['path'] != fingerprint_path or previous['payload'] != canonical:
                                conflict('Idempotency key was used for a different request')
                            result, status = json.loads(previous['body']), previous['status']
                        else:
                            result, status = apply_mutation(con,user,path,body), 200 if path == '/api/stock/adjustments' or path.endswith(('/reserve','/ship','/cancel','/returns')) else 201
                            con.execute('INSERT INTO idempotency VALUES (?,?,?,?,?,?,?)',
                                        (user['tenant'],key,self.command,fingerprint_path,canonical,status,json.dumps(result,separators=(',',':'))))
                        con.execute('COMMIT')
                    except Exception:
                        con.execute('ROLLBACK'); raise
                    return self.send_json(status,result)
            raise APIError(404,'not_found','Route not found')
        except APIError as exc:
            self.send_json(exc.status,{'error':{'code':exc.code,'message':exc.message}})
        except (sqlite3.Error,OverflowError) as exc:
            print('Database error:',repr(exc),file=sys.stderr)
            self.send_json(500,{'error':{'code':'internal_error','message':'Database operation failed'}})

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(),fmt % args),file=sys.stderr)


if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT','8000'))
    print(f'DepotFlow listening on http://127.0.0.1:{port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
