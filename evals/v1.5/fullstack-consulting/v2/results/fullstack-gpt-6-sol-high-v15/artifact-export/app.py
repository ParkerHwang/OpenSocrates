import base64, hashlib, hmac, json, os, secrets, sqlite3, sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parent
DATA_DIR=Path(os.environ.get('DATA_DIR',str(ROOT/'data')))
DB=DATA_DIR/'depotflow.sqlite3'
STATUSES={'draft','reserved','shipped','cancelled','returned'}
MAX_INTEGER=2**63-1
class ApiError(Exception):
    def __init__(self,status,code,message): self.status,self.code,self.message=status,code,message
def bad(message): raise ApiError(400,'bad_request',message)
def conflict(message): raise ApiError(409,'conflict',message)
def is_int(value): return type(value) is int
def connect():
    db=sqlite3.connect(DB,timeout=20,isolation_level=None)
    db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA busy_timeout=20000')
    return db
def init_db():
    DATA_DIR.mkdir(parents=True,exist_ok=True); db=connect(); db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,tenant TEXT NOT NULL,email TEXT UNIQUE NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS inventory(tenant TEXT NOT NULL,sku TEXT NOT NULL,name TEXT NOT NULL,on_hand INTEGER NOT NULL CHECK(on_hand>=0),reserved INTEGER NOT NULL CHECK(reserved>=0 AND reserved<=on_hand),price_cents INTEGER NOT NULL CHECK(price_cents>=0),version INTEGER NOT NULL CHECK(version>=1),PRIMARY KEY(tenant,sku));
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,client_ref TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,total_cents INTEGER NOT NULL,UNIQUE(tenant,client_ref));
    CREATE TABLE IF NOT EXISTS order_lines(order_id INTEGER NOT NULL REFERENCES orders(id),sku TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>0),unit_price_cents INTEGER NOT NULL,returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(returned_quantity>=0 AND returned_quantity<=quantity),PRIMARY KEY(order_id,sku));
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,action TEXT NOT NULL,entity_id TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,method TEXT NOT NULL,path TEXT NOT NULL,payload_hash TEXT NOT NULL,status INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(tenant,key));
    CREATE INDEX IF NOT EXISTS idx_orders_tenant_id ON orders(tenant,id);
    CREATE INDEX IF NOT EXISTS idx_audit_tenant_id ON audit(tenant,id);
    ''')
    db.execute('BEGIN IMMEDIATE')
    try:
        if not db.execute("SELECT 1 FROM meta WHERE key='cursor_secret'").fetchone(): db.execute("INSERT INTO meta VALUES('cursor_secret',?)",(secrets.token_hex(32),))
        empty_store=not any(db.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone() for table in ('users','sessions','inventory','orders','order_lines','audit','idempotency'))
        if os.environ.get('SEED_DEMO')=='1' and empty_store:
            for tenant in ('north','south'):
                for role in ('admin','operator','viewer'):
                    salt=secrets.token_hex(16)
                    hashed=hashlib.pbkdf2_hmac('sha256',b'DepotDemo!2026',bytes.fromhex(salt),200000).hex()
                    db.execute('INSERT INTO users(tenant,email,role,salt,password_hash) VALUES(?,?,?,?,?)',(tenant,f'{role}@{tenant}.example',role,salt,hashed))
                for sku,name,qty,price in [('BOLT','Steel bolt kit',100,1250),('CABLE','Cable assembly',60,2499),('SAMPLE','Sample pack',20,0)]: db.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,1)',(tenant,sku,name,qty,0,price))
        db.commit()
    except Exception: db.rollback(); raise
    finally: db.close()
def public_user(row): return {k:row[k] for k in ('email','role','tenant')}
def auth(db,headers):
    value=headers.get('Authorization','')
    if not value.startswith('Bearer ') or not value[7:].strip(): raise ApiError(401,'unauthorized','A valid bearer token is required')
    row=db.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?',(hashlib.sha256(value[7:].encode()).hexdigest(),)).fetchone()
    if not row: raise ApiError(401,'unauthorized','A valid bearer token is required')
    return row
def inventory_item(row): return {**{k:row[k] for k in ('sku','name','on_hand','reserved','price_cents','version')},'available':row['on_hand']-row['reserved']}
def order(db,tenant,oid):
    row=db.execute('SELECT * FROM orders WHERE id=? AND tenant=?',(oid,tenant)).fetchone()
    if not row: raise ApiError(404,'not_found','Order not found')
    lines=db.execute('SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid',(oid,)).fetchall()
    return {'id':row['id'],'client_ref':row['client_ref'],'status':row['status'],'version':row['version'],'total_cents':row['total_cents'],'lines':[dict(x) for x in lines]}
def event(db,tenant,action,entity_id,actor): db.execute('INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES(?,?,?,?,?)',(tenant,action,str(entity_id),actor,datetime.now(timezone.utc).isoformat()))
def required_version(payload):
    v=payload.get('expected_version')
    if not is_int(v) or not 1<=v<=MAX_INTEGER: bad('expected_version must be a positive integer')
    return v
def lines_payload(payload):
    lines=payload.get('lines')
    if not isinstance(lines,list) or not lines: bad('lines must be a nonempty array')
    seen=set(); clean=[]
    for line in lines:
        if not isinstance(line,dict) or not isinstance(line.get('sku'),str) or not line['sku'] or not is_int(line.get('quantity')) or not 1<=line['quantity']<=MAX_INTEGER: bad('Each line needs a SKU and positive integer quantity')
        sku=line['sku']
        if sku in seen: bad('Duplicate SKU lines are not allowed')
        seen.add(sku); clean.append((sku,line['quantity']))
    return clean
def mutate(db,user,path,payload):
    tenant,actor=user['tenant'],user['email']
    if path=='/api/stock/adjustments':
        sku,delta,version,reason=(payload.get(k) for k in ('sku','delta','expected_version','reason'))
        if not isinstance(sku,str) or not sku or not is_int(delta) or delta==0 or abs(delta)>MAX_INTEGER or not is_int(version) or not 1<=version<=MAX_INTEGER or not isinstance(reason,str) or not reason.strip(): bad('sku, nonzero integer delta, positive expected_version and reason are required')
        row=db.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?',(tenant,sku)).fetchone()
        if not row: bad('Unknown SKU')
        if row['version']!=version: conflict('Inventory version is stale; refresh and retry')
        if row['on_hand']+delta<row['reserved']: conflict('Adjustment would reduce stock below reserved units')
        if row['on_hand']+delta>MAX_INTEGER or row['version']==MAX_INTEGER: conflict('Inventory limit reached')
        db.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?',(delta,tenant,sku))
        event(db,tenant,'stock_adjusted',sku,actor)
        return 200,inventory_item(db.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?',(tenant,sku)).fetchone())
    if path=='/api/orders':
        ref=payload.get('client_ref')
        if not isinstance(ref,str) or not ref.strip(): bad('client_ref must be nonempty')
        ref=ref.strip(); lines=lines_payload(payload)
        if db.execute('SELECT 1 FROM orders WHERE tenant=? AND client_ref=?',(tenant,ref)).fetchone(): conflict('Client reference already exists')
        prices={}
        for sku,qty in lines:
            row=db.execute('SELECT price_cents FROM inventory WHERE tenant=? AND sku=?',(tenant,sku)).fetchone()
            if not row: bad(f'Unknown SKU: {sku}')
            prices[sku]=row['price_cents']
        total=sum(qty*prices[sku] for sku,qty in lines)
        if total>MAX_INTEGER: bad('Order total is too large')
        cur=db.execute('INSERT INTO orders(tenant,client_ref,status,version,total_cents) VALUES(?, ?,"draft",1,?)',(tenant,ref,total))
        oid=cur.lastrowid
        for sku,qty in lines: db.execute('INSERT INTO order_lines(order_id,sku,quantity,unit_price_cents) VALUES(?,?,?,?)',(oid,sku,qty,prices[sku]))
        event(db,tenant,'order_created',oid,actor)
        return 201,order(db,tenant,oid)
    parts=path.split('/')
    if len(parts)!=5 or parts[:3]!=['','api','orders'] or parts[4] not in ('reserve','ship','cancel','returns') or not parts[3].isdigit(): raise ApiError(404,'not_found','Endpoint not found')
    oid=int(parts[3]); action=parts[4]; current=order(db,tenant,oid); version=required_version(payload)
    if current['version']!=version: conflict('Order version is stale; refresh and retry')
    if current['version']==MAX_INTEGER: conflict('Order version limit reached')
    status=current['status']
    if action=='reserve':
        if status!='draft': conflict('Only draft orders can be reserved')
        for line in current['lines']:
            row=db.execute('SELECT on_hand,reserved FROM inventory WHERE tenant=? AND sku=?',(tenant,line['sku'])).fetchone()
            if row['on_hand']-row['reserved']<line['quantity']: conflict(f'Insufficient available stock for {line["sku"]}')
        for line in current['lines']:
            row=db.execute('SELECT version FROM inventory WHERE tenant=? AND sku=?',(tenant,line['sku'])).fetchone()
            if row['version']==MAX_INTEGER: conflict('Inventory version limit reached')
        for line in current['lines']: db.execute('UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?',(line['quantity'],tenant,line['sku']))
        new_status='reserved'
    elif action=='ship':
        if status!='reserved': conflict('Only reserved orders can be shipped')
        for line in current['lines']:
            row=db.execute('SELECT version FROM inventory WHERE tenant=? AND sku=?',(tenant,line['sku'])).fetchone()
            if row['version']==MAX_INTEGER: conflict('Inventory version limit reached')
        for line in current['lines']: db.execute('UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',(line['quantity'],line['quantity'],tenant,line['sku']))
        new_status='shipped'
    elif action=='cancel':
        if status not in ('draft','reserved'): conflict('Only draft or reserved orders can be cancelled')
        if status=='reserved':
            for line in current['lines']:
                row=db.execute('SELECT version FROM inventory WHERE tenant=? AND sku=?',(tenant,line['sku'])).fetchone()
                if row['version']==MAX_INTEGER: conflict('Inventory version limit reached')
            for line in current['lines']: db.execute('UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',(line['quantity'],tenant,line['sku']))
        new_status='cancelled'
    else:
        if status!='shipped': conflict('Only shipped orders can be returned')
        returned=lines_payload(payload); by_sku={line['sku']:line for line in current['lines']}
        for sku,qty in returned:
            if sku not in by_sku: bad(f'SKU {sku} is not in this order')
            if by_sku[sku]['returned_quantity']+qty>by_sku[sku]['quantity']: conflict(f'Return quantity exceeds shipped quantity for {sku}')
            item=db.execute('SELECT on_hand,version FROM inventory WHERE tenant=? AND sku=?',(tenant,sku)).fetchone()
            if item['on_hand']+qty>MAX_INTEGER or item['version']==MAX_INTEGER: conflict('Inventory limit reached')
        for sku,qty in returned:
            db.execute('UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?',(qty,oid,sku))
            db.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?',(qty,tenant,sku))
        amounts={sku:line['returned_quantity'] for sku,line in by_sku.items()}
        for sku,qty in returned: amounts[sku]+=qty
        new_status='returned' if all(amounts[sku]==line['quantity'] for sku,line in by_sku.items()) else 'shipped'
    db.execute('UPDATE orders SET status=?,version=version+1 WHERE id=?',(new_status,oid))
    event(db,tenant,{'reserve':'order_reserved','ship':'order_shipped','cancel':'order_cancelled','returns':'order_returned'}[action],oid,actor)
    return 200,order(db,tenant,oid)
def cursor_secret(db): return bytes.fromhex(db.execute("SELECT value FROM meta WHERE key='cursor_secret'").fetchone()[0])
def encode_cursor(db,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode(); sig=hmac.new(cursor_secret(db),raw,hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw+sig).decode().rstrip('=')
def decode_cursor(db,token,kind,filters,tenant):
    try:
        data=base64.urlsafe_b64decode(token+'='*((-len(token))%4)); raw,sig=data[:-32],data[-32:]
        if not hmac.compare_digest(hmac.new(cursor_secret(db),raw,hashlib.sha256).digest(),sig): raise ValueError()
        value=json.loads(raw)
        if value.get('kind')!=kind or value.get('filters')!=filters or value.get('tenant')!=tenant or not is_int(value.get('last')) or not is_int(value.get('max')) or value['last']<0 or value['max']<value['last']: raise ValueError()
        return value
    except Exception: bad('Invalid cursor')
def param(qs,name,default=None):
    values=qs.get(name)
    if values is None: return default
    if len(values)!=1: bad(f'Invalid {name}')
    return values[0]
def limit_of(qs):
    value=param(qs,'limit','20')
    if not value.isdigit() or not 1<=int(value)<=100: bad('limit must be an integer from 1 to 100')
    return int(value)
def list_orders(db,tenant,qs):
    if set(qs)-{'status','q','limit','cursor'}: bad('Invalid order filter')
    status=param(qs,'status'); q=param(qs,'q',''); limit=limit_of(qs)
    if status is not None and status not in STATUSES: bad('Invalid status filter')
    filters={'status':status,'q':q}; cursor=param(qs,'cursor')
    if cursor is not None: c=decode_cursor(db,cursor,'orders',filters,tenant); last,maxid=c['last'],c['max']
    else: last=0; maxid=db.execute('SELECT COALESCE(MAX(id),0) FROM orders WHERE tenant=?',(tenant,)).fetchone()[0]
    sql='SELECT id,client_ref FROM orders WHERE tenant=? AND id>? AND id<=?'; args=[tenant,last,maxid]
    if status: sql+=' AND status=?'; args.append(status)
    sql+=' ORDER BY id'
    if not q: sql+=' LIMIT ?'; args.append(limit+1)
    rows=db.execute(sql,args).fetchall()
    if q: rows=[row for row in rows if q.casefold() in row['client_ref'].casefold()]
    selected=rows[:limit]; items=[order(db,tenant,row['id']) for row in selected]
    next_cursor=encode_cursor(db,{'kind':'orders','filters':filters,'tenant':tenant,'last':selected[-1]['id'],'max':maxid}) if len(rows)>limit else None
    return {'items':items,'next_cursor':next_cursor}
def list_audit(db,tenant,qs):
    if set(qs)-{'limit','cursor'}: bad('Invalid audit filter')
    limit=limit_of(qs); cursor=param(qs,'cursor')
    if cursor is not None: c=decode_cursor(db,cursor,'audit',{},tenant); last,maxid=c['last'],c['max']
    else: last=0; maxid=db.execute('SELECT COALESCE(MAX(id),0) FROM audit WHERE tenant=?',(tenant,)).fetchone()[0]
    rows=db.execute('SELECT id,action,entity_id,actor,created_at FROM audit WHERE tenant=? AND id>? AND id<=? ORDER BY id LIMIT ?',(tenant,last,maxid,limit+1)).fetchall(); selected=rows[:limit]
    next_cursor=encode_cursor(db,{'kind':'audit','filters':{},'tenant':tenant,'last':selected[-1]['id'],'max':maxid}) if len(rows)>limit else None
    return {'items':[dict(row) for row in selected],'next_cursor':next_cursor}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
    def send_json(self,status,body):
        data=json.dumps(body,separators=(',',':')).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
    def body(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>1000000: bad('Invalid request body size')
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict): bad('JSON body must be an object')
            return payload
        except (ValueError,UnicodeDecodeError): bad('Invalid JSON body')
    def handle_request(self):
        parsed=urlsplit(self.path); path=parsed.path
        if path=='/api/health' and self.command=='GET': return 200,{'status':'ok'}
        if not path.startswith('/api/'):
            if self.command!='GET': raise ApiError(404,'not_found','Endpoint not found')
            filename='index.html' if path=='/' else path.lstrip('/')
            if filename not in ('index.html','app.js','style.css'): raise ApiError(404,'not_found','Page not found')
            data=(ROOT/'static'/filename).read_bytes(); mime={'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[filename]
            self.send_response(200); self.send_header('Content-Type',mime+'; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return None
        db=connect()
        try:
            if path=='/api/session' and self.command=='POST':
                payload=self.body(); email=payload.get('email'); password=payload.get('password')
                if not isinstance(email,str) or not isinstance(password,str): raise ApiError(401,'unauthorized','Invalid credentials')
                row=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                if not row: raise ApiError(401,'unauthorized','Invalid credentials')
                hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(row['salt']),200000).hex()
                if not hmac.compare_digest(hashed,row['password_hash']): raise ApiError(401,'unauthorized','Invalid credentials')
                token=secrets.token_urlsafe(32); db.execute('INSERT INTO sessions VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id']))
                return 200,{'token':token,'user':public_user(row)}
            user=auth(db,self.headers); tenant=user['tenant']
            if self.command=='GET':
                db.execute('BEGIN')
                qs=parse_qs(parsed.query,keep_blank_values=True)
                if path=='/api/me': return 200,public_user(user)
                if path=='/api/inventory': return 200,{'items':[inventory_item(row) for row in db.execute('SELECT * FROM inventory WHERE tenant=? ORDER BY sku',(tenant,))]}
                if path=='/api/dashboard':
                    counts={row['status']:row['n'] for row in db.execute('SELECT status,COUNT(*) n FROM orders WHERE tenant=? GROUP BY status',(tenant,))}
                    totals=db.execute('SELECT COALESCE(SUM(on_hand),0) on_hand,COALESCE(SUM(reserved),0) reserved FROM inventory WHERE tenant=?',(tenant,)).fetchone()
                    return 200,{'orders_by_status':counts,'inventory_units':totals['on_hand'],'reserved_units':totals['reserved']}
                if path=='/api/orders': return 200,list_orders(db,tenant,qs)
                if path=='/api/audit': return 200,list_audit(db,tenant,qs)
                parts=path.split('/')
                if len(parts)==4 and parts[:3]==['','api','orders'] and parts[3].isdigit(): return 200,order(db,tenant,int(parts[3]))
                raise ApiError(404,'not_found','Endpoint not found')
            if self.command=='POST':
                parts=path.split('/'); adjust=path=='/api/stock/adjustments'; create=path=='/api/orders'
                transition=len(parts)==5 and parts[:3]==['','api','orders'] and parts[3].isdigit() and parts[4] in ('reserve','ship','cancel','returns')
                if not (adjust or create or transition): raise ApiError(404,'not_found','Endpoint not found')
                if user['role']=='viewer' or (adjust and user['role']!='admin'): raise ApiError(403,'forbidden','Your role cannot perform this action')
                key=self.headers.get('Idempotency-Key','')
                if not key.strip() or len(key)>200: bad('A nonempty Idempotency-Key is required')
                payload=self.body(); digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
                db.execute('BEGIN IMMEDIATE')
                try:
                    prior=db.execute('SELECT * FROM idempotency WHERE tenant=? AND key=?',(tenant,key)).fetchone()
                    if prior:
                        if prior['method']!=self.command or prior['path']!=path or prior['payload_hash']!=digest: conflict('Idempotency key was used for a different request')
                        result=prior['status'],json.loads(prior['body']); db.commit(); return result
                    status,body=mutate(db,user,path,payload)
                    db.execute('INSERT INTO idempotency VALUES(?,?,?,?,?,?,?)',(tenant,key,self.command,path,digest,status,json.dumps(body,separators=(',',':'))))
                    db.commit(); return status,body
                except Exception: db.rollback(); raise
            raise ApiError(404,'not_found','Endpoint not found')
        finally: db.close()
    def do_GET(self): self.dispatch()
    def do_POST(self): self.dispatch()
    def dispatch(self):
        try:
            result=self.handle_request()
            if result is not None: self.send_json(*result)
        except ApiError as exc: self.send_json(exc.status,{'error':{'code':exc.code,'message':exc.message}})
        except Exception as exc:
            print('Server error:',repr(exc),file=sys.stderr); self.send_json(500,{'error':{'code':'internal_error','message':'Internal server error'}})
if __name__=='__main__':
    init_db(); port=int(os.environ.get('PORT','8000')); print(f'DepotFlow at http://127.0.0.1:{port}',flush=True)
    try: ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
    except KeyboardInterrupt: pass
