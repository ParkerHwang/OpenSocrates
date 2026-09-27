#!/usr/bin/env python3
import hashlib, hmac, json, os, secrets, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE=os.path.dirname(os.path.abspath(__file__))
DATA_DIR=os.environ.get('DATA_DIR',os.path.join(BASE,'data'))
os.makedirs(DATA_DIR,exist_ok=True)
DB=os.path.join(DATA_DIR,'depotflow.sqlite3')
PASSWORD_ROUNDS=180000
MAX_SQL_INT=(1<<63)-1
MIN_SQL_INT=-(1<<63)

def connect():
    c=sqlite3.connect(DB,timeout=30,isolation_level=None); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=30000'); return c

def password_hash(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,PASSWORD_ROUNDS)
    return salt.hex()+':'+digest.hex()

def password_matches(password,stored):
    try: salt_hex,digest_hex=stored.split(':',1); salt=bytes.fromhex(salt_hex)
    except (ValueError,AttributeError): return False
    actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,PASSWORD_ROUNDS).hex()
    return hmac.compare_digest(digest_hex,actual)

def init():
    c=connect(); c.executescript('''
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS users(email TEXT PRIMARY KEY,tenant TEXT NOT NULL REFERENCES tenants(id),role TEXT NOT NULL,password_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,email TEXT NOT NULL REFERENCES users(email));
    CREATE TABLE IF NOT EXISTS inventory(tenant TEXT NOT NULL REFERENCES tenants(id),sku TEXT NOT NULL,name TEXT NOT NULL,on_hand INTEGER NOT NULL CHECK(on_hand>=0),reserved INTEGER NOT NULL CHECK(reserved>=0 AND reserved<=on_hand),price_cents INTEGER NOT NULL CHECK(price_cents>=0),version INTEGER NOT NULL CHECK(version>=1),PRIMARY KEY(tenant,sku));
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL REFERENCES tenants(id),client_ref TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,total_cents INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(tenant,client_ref));
    CREATE TABLE IF NOT EXISTS order_lines(order_id INTEGER NOT NULL REFERENCES orders(id),sku TEXT NOT NULL,quantity INTEGER NOT NULL,unit_price_cents INTEGER NOT NULL,returned_quantity INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(order_id,sku));
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,action TEXT NOT NULL,entity_id TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,method TEXT NOT NULL,path TEXT NOT NULL,payload TEXT NOT NULL,status INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(tenant,key));
    CREATE INDEX IF NOT EXISTS orders_tenant_id ON orders(tenant,id); CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant,id);
    ''')
    if os.environ.get('SEED_DEMO')=='1' and c.execute('SELECT COUNT(*) FROM tenants').fetchone()[0]==0:
        for tenant in ('north','south'):
            c.execute('INSERT INTO tenants VALUES(?)',(tenant,))
            for role in ('admin','operator','viewer'): c.execute('INSERT INTO users VALUES(?,?,?,?)',(f'{role}@{tenant}.example',tenant,role,password_hash('DepotDemo!2026')))
            for sku,name,qty,price in [('BOLT','Steel bolt kit',100,1250),('CABLE','Cable assembly',60,2499),('SAMPLE','Sample pack',20,0)]: c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,1)',(tenant,sku,name,qty,0,price))
    c.close()
init()

class ApiError(Exception):
    def __init__(self,status,code,message): self.status=status; self.code=code; self.message=message
def fail(status,code,msg): raise ApiError(status,code,msg)
def now(): return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
def is_int(v): return type(v) is int
def obj(v):
    if not isinstance(v,dict): fail(400,'bad_request','JSON object required')
    return v
def required_int(d,k,minimum=None,nonzero=False):
    v=d.get(k)
    if not is_int(v) or v>MAX_SQL_INT or v<MIN_SQL_INT or (minimum is not None and v<minimum) or (nonzero and v==0): fail(400,'bad_request',f'{k} must be a supported integer')
    return v
def nonempty_str(d,k):
    v=d.get(k)
    if not isinstance(v,str) or not v.strip(): fail(400,'bad_request',f'{k} must be a nonempty string')
    return v.strip()
def user_for(c,token):
    if not token: fail(401,'unauthorized','Bearer token required')
    r=c.execute('SELECT u.email,u.role,u.tenant FROM sessions s JOIN users u ON u.email=s.email WHERE s.token=?',(token,)).fetchone()
    if not r: fail(401,'unauthorized','Invalid or expired token')
    return dict(r)
def serialize_order(c,r):
    lines=c.execute('SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid',(r['id'],)).fetchall()
    return {'id':str(r['id']),'client_ref':r['client_ref'],'status':r['status'],'version':r['version'],'total_cents':r['total_cents'],'lines':[dict(x) for x in lines]}
def inv_dict(r):
    d=dict(r); d['available']=d['on_hand']-d['reserved']; return d
def audit(c,u,action,entity): c.execute('INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES(?,?,?,?,?)',(u['tenant'],action,str(entity),u['email'],now()))
def parse_lines(v):
    if not isinstance(v,list) or not v: fail(400,'bad_request','lines must be a nonempty array')
    seen=set(); out=[]
    for x in v:
        if not isinstance(x,dict): fail(400,'bad_request','Each line must be an object')
        sku=nonempty_str(x,'sku'); qty=required_int(x,'quantity',1)
        if sku in seen: fail(400,'bad_request','Duplicate SKU lines are invalid')
        seen.add(sku); out.append((sku,qty))
    return out
def mutate(c,u,method,path,key,payload,work):
    if not key: fail(400,'idempotency_required','Idempotency-Key header is required')
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    c.execute('BEGIN IMMEDIATE')
    try:
        old=c.execute('SELECT method,path,payload,status,body FROM idempotency WHERE tenant=? AND key=?',(u['tenant'],key)).fetchone()
        if old:
            if (old['method'],old['path'],old['payload'])!=(method,path,canonical): fail(409,'idempotency_conflict','Key already used for a different request')
            c.execute('COMMIT'); return old['status'],json.loads(old['body'])
        status,body=work(); encoded=json.dumps(body,separators=(',',':'),ensure_ascii=False)
        c.execute('INSERT INTO idempotency VALUES(?,?,?,?,?,?,?)',(u['tenant'],key,method,path,canonical,status,encoded)); c.execute('COMMIT'); return status,body
    except Exception:
        if c.in_transaction: c.execute('ROLLBACK')
        raise
def page(q):
    if any(len(q.get(k,[]))>1 for k in ('limit','cursor')): fail(400,'bad_request','Duplicate pagination parameters')
    s=q.get('limit',['20'])[0]
    try: n=int(s)
    except (ValueError,TypeError): fail(400,'bad_request','limit must be from 1 to 100')
    if str(n)!=s or not 1<=n<=100: fail(400,'bad_request','limit must be from 1 to 100')
    cur=q.get('cursor',[None])[0]
    if cur is None: return n,0
    try: cursor=int(cur)
    except (ValueError,TypeError): fail(400,'bad_request','Invalid cursor')
    if str(cursor)!=cur or not 0<=cursor<=MAX_SQL_INT: fail(400,'bad_request','Invalid cursor')
    return n,cursor

class Handler(BaseHTTPRequestHandler):
    server_version='DepotFlow/1.0'
    def log_message(self,*a): pass
    def send_json(self,s,d):
        b=json.dumps(d,separators=(',',':'),ensure_ascii=False).encode(); self.send_response(s); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
    def body(self):
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n>1000000: fail(413,'too_large','Request too large')
            return obj(json.loads(self.rfile.read(n) or b'{}'))
        except (ValueError,UnicodeDecodeError): fail(400,'bad_request','Malformed JSON')
    def static(self,path):
        if path=='/' : filename='index.html'; typ='text/html; charset=utf-8'
        elif path in ('/static/app.js','/static/style.css'):
            filename=path.rsplit('/',1)[1]; typ='text/javascript' if filename.endswith('.js') else 'text/css'
        else: return False
        b=open(os.path.join(BASE,'static',filename),'rb').read(); self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b); return True
    def route(self):
        p=urlparse(self.path); path=p.path; q=parse_qs(p.query,keep_blank_values=True)
        if self.command=='GET' and self.static(path): return
        c=connect()
        try:
            if path=='/api/health' and self.command=='GET': self.send_json(200,{'status':'ok'}); return
            if path=='/api/session' and self.command=='POST':
                d=self.body(); email=nonempty_str(d,'email').lower(); password=d.get('password'); r=c.execute('SELECT email,tenant,role,password_hash FROM users WHERE email=?',(email,)).fetchone()
                if not r or not isinstance(password,str) or not password_matches(password,r['password_hash']): fail(401,'bad_credentials','Email or password is incorrect')
                token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?)',(token,email)); self.send_json(200,{'token':token,'user':{'email':email,'role':r['role'],'tenant':r['tenant']}}); return
            auth=self.headers.get('Authorization',''); u=user_for(c,auth[7:] if auth.startswith('Bearer ') else None)
            if path=='/api/me' and self.command=='GET': self.send_json(200,u); return
            if path=='/api/inventory' and self.command=='GET':
                rows=c.execute('SELECT sku,name,on_hand,reserved,price_cents,version FROM inventory WHERE tenant=? ORDER BY sku',(u['tenant'],)).fetchall(); self.send_json(200,{'items':[inv_dict(r) for r in rows]}); return
            if path=='/api/dashboard' and self.command=='GET':
                counts={r['status']:r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM orders WHERE tenant=? GROUP BY status',(u['tenant'],))}; stock=c.execute('SELECT COALESCE(SUM(on_hand),0) units,COALESCE(SUM(reserved),0) reserved FROM inventory WHERE tenant=?',(u['tenant'],)).fetchone(); self.send_json(200,{'orders_by_status':counts,'inventory_units':stock['units'],'reserved_units':stock['reserved']}); return
            if path=='/api/orders' and self.command=='GET':
                limit,cur=page(q); status=q.get('status',[None])[0]; term=q.get('q',[''])[0]
                if status is not None and status not in ('draft','reserved','shipped','cancelled','returned'): fail(400,'bad_request','Invalid status filter')
                if len(q.get('status',[]))>1 or len(q.get('q',[]))>1: fail(400,'bad_request','Duplicate filters')
                sql='SELECT * FROM orders WHERE tenant=? AND id>?'; args=[u['tenant'],cur]
                if status: sql+=' AND status=?'; args.append(status)
                if term: sql+=' AND instr(lower(client_ref),lower(?))>0'; args.append(term)
                rows=c.execute(sql+' ORDER BY id LIMIT ?',args+[limit+1]).fetchall(); more=len(rows)>limit; rows=rows[:limit]
                self.send_json(200,{'items':[serialize_order(c,r) for r in rows],'next_cursor':str(rows[-1]['id']) if more and rows else None}); return
            if path=='/api/audit' and self.command=='GET':
                limit,cur=page(q); rows=c.execute('SELECT id,action,entity_id,actor,created_at FROM audit WHERE tenant=? AND id>? ORDER BY id LIMIT ?', (u['tenant'],cur,limit+1)).fetchall(); more=len(rows)>limit; rows=rows[:limit]
                self.send_json(200,{'items':[dict(r) for r in rows],'next_cursor':str(rows[-1]['id']) if more and rows else None}); return
            if path.startswith('/api/orders/') and self.command=='GET':
                oid=path.split('/')[3] if len(path.split('/'))>3 else ''
                if not oid.isdigit(): fail(404,'not_found','Order not found')
                r=c.execute('SELECT * FROM orders WHERE tenant=? AND id=?',(u['tenant'],int(oid))).fetchone()
                if not r: fail(404,'not_found','Order not found')
                self.send_json(200,serialize_order(c,r)); return
            if self.command=='POST':
                if u['role']=='viewer': fail(403,'forbidden','Viewer accounts cannot make changes')
                d=self.body(); key=self.headers.get('Idempotency-Key','').strip()
                if path=='/api/stock/adjustments':
                    if u['role']!='admin': fail(403,'forbidden','Only admins can adjust stock')
                    sku=nonempty_str(d,'sku'); delta=required_int(d,'delta',nonzero=True); ver=required_int(d,'expected_version',1); reason=nonempty_str(d,'reason')
                    def work():
                        r=c.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?',(u['tenant'],sku)).fetchone()
                        if not r: fail(400,'unknown_sku','Unknown SKU')
                        if r['version']!=ver: fail(409,'stale_version','Inventory version is stale')
                        if r['on_hand']+delta<r['reserved']: fail(409,'insufficient_stock','Adjustment falls below reserved quantity')
                        if r['on_hand']+delta>MAX_SQL_INT: fail(400,'bad_request','Adjusted stock exceeds supported integer range')
                        c.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?',(delta,u['tenant'],sku)); item=inv_dict(c.execute('SELECT sku,name,on_hand,reserved,price_cents,version FROM inventory WHERE tenant=? AND sku=?',(u['tenant'],sku)).fetchone()); audit(c,u,'stock.adjusted',sku); return 200,item
                    s,b=mutate(c,u,'POST',path,key,d,work); self.send_json(s,b); return
                if path=='/api/orders':
                    ref=nonempty_str(d,'client_ref'); lines=parse_lines(d.get('lines'))
                    def work():
                        catalog={r['sku']:r['price_cents'] for r in c.execute('SELECT sku,price_cents FROM inventory WHERE tenant=?',(u['tenant'],)).fetchall()}
                        if any(sku not in catalog for sku,_ in lines): fail(400,'unknown_sku','Unknown SKU')
                        total=sum(catalog[sku]*qty for sku,qty in lines)
                        if total>MAX_SQL_INT: fail(400,'bad_request','Order total exceeds supported integer range')
                        try: cur=c.execute('INSERT INTO orders(tenant,client_ref,status,version,total_cents,created_at) VALUES(?,?,\'draft\',1,?,?)',(u['tenant'],ref,total,now()))
                        except sqlite3.IntegrityError: fail(409,'duplicate_client_ref','Client reference already exists')
                        oid=cur.lastrowid
                        for sku,qty in lines: c.execute('INSERT INTO order_lines VALUES(?,?,?,?,0)',(oid,sku,qty,catalog[sku]))
                        r=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone(); audit(c,u,'order.created',oid); return 201,serialize_order(c,r)
                    s,b=mutate(c,u,'POST',path,key,d,work); self.send_json(s,b); return
                parts=path.split('/')
                if len(parts)==5 and parts[1:3]==['api','orders'] and parts[3].isdigit() and parts[4] in ('reserve','ship','cancel','returns'):
                    oid=int(parts[3]); act=parts[4]; ver=required_int(d,'expected_version',1); lines=parse_lines(d.get('lines')) if act=='returns' else None
                    def work():
                        r=c.execute('SELECT * FROM orders WHERE tenant=? AND id=?',(u['tenant'],oid)).fetchone()
                        if not r: fail(404,'not_found','Order not found')
                        if r['version']!=ver: fail(409,'stale_version','Order version is stale')
                        old=r['status']
                        if act=='reserve':
                            if old!='draft': fail(409,'invalid_transition','Only draft orders can be reserved')
                            ol=c.execute('SELECT * FROM order_lines WHERE order_id=?',(oid,)).fetchall()
                            for x in ol:
                                st=c.execute('SELECT on_hand,reserved FROM inventory WHERE tenant=? AND sku=?',(u['tenant'],x['sku'])).fetchone()
                                if st['on_hand']-st['reserved']<x['quantity']: fail(409,'insufficient_stock',f"Insufficient available stock for {x['sku']}")
                            for x in ol: c.execute('UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?',(x['quantity'],u['tenant'],x['sku']))
                            new='reserved'
                        elif act=='ship':
                            if old!='reserved': fail(409,'invalid_transition','Only reserved orders can ship')
                            for x in c.execute('SELECT * FROM order_lines WHERE order_id=?',(oid,)).fetchall(): c.execute('UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',(x['quantity'],x['quantity'],u['tenant'],x['sku']))
                            new='shipped'
                        elif act=='cancel':
                            if old not in ('draft','reserved'): fail(409,'invalid_transition','Only draft or reserved orders can cancel')
                            if old=='reserved':
                                for x in c.execute('SELECT * FROM order_lines WHERE order_id=?',(oid,)).fetchall(): c.execute('UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',(x['quantity'],u['tenant'],x['sku']))
                            new='cancelled'
                        else:
                            if old!='shipped': fail(409,'invalid_transition','Only shipped orders can be returned')
                            existing={x['sku']:x for x in c.execute('SELECT * FROM order_lines WHERE order_id=?',(oid,)).fetchall()}
                            for sku,qty in lines:
                                x=existing.get(sku)
                                if not x: fail(400,'bad_request','Return SKU is not on order')
                                if x['returned_quantity']+qty>x['quantity']: fail(409,'return_exceeds_shipped','Return exceeds shipped quantity')
                                current=c.execute('SELECT on_hand FROM inventory WHERE tenant=? AND sku=?',(u['tenant'],sku)).fetchone()
                                if current['on_hand']+qty>MAX_SQL_INT: fail(409,'stock_capacity','Returned stock exceeds supported inventory range')
                            for sku,qty in lines:
                                c.execute('UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?',(qty,oid,sku)); c.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?',(qty,u['tenant'],sku))
                            allx=c.execute('SELECT quantity,returned_quantity FROM order_lines WHERE order_id=?',(oid,)).fetchall(); new='returned' if all(x['quantity']==x['returned_quantity'] for x in allx) else 'shipped'
                        c.execute('UPDATE orders SET status=?,version=version+1 WHERE id=?',(new,oid)); updated=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone(); audit(c,u,'order.'+act,oid); return 200,serialize_order(c,updated)
                    s,b=mutate(c,u,'POST',path,key,d,work); self.send_json(s,b); return
            fail(404,'not_found','Route not found')
        finally: c.close()
    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def handle_request(self):
        try: self.route()
        except ApiError as e: self.send_json(e.status,{'error':{'code':e.code,'message':e.message}})
        except BrokenPipeError: pass
        except Exception as e:
            try: self.send_json(500,{'error':{'code':'internal_error','message':'Internal server error'}})
            except Exception: pass
            if os.environ.get('DEBUG'): print(type(e).__name__,str(e),flush=True)
class Server(ThreadingHTTPServer):
    request_queue_size=256
    daemon_threads=True
if __name__=='__main__': Server(('127.0.0.1',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
