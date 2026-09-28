#!/usr/bin/env python3
"""DepotFlow local fulfillment service. Python stdlib + SQLite."""
import hashlib, json, os, secrets, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DATA_DIR=os.environ.get('DATA_DIR',os.path.join(os.path.dirname(__file__),'data'))
os.makedirs(DATA_DIR,exist_ok=True)
DB=os.path.join(DATA_DIR,'depotflow.sqlite3')
CATALOG=[('BOLT','Steel bolt kit',100,1250),('CABLE','Cable assembly',60,2499),('SAMPLE','Sample pack',20,0)]

def db():
 c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row
 c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=30000');return c
def now():return datetime.now(timezone.utc).isoformat(timespec='milliseconds')
def init():
 c=db();c.executescript('''CREATE TABLE IF NOT EXISTS users(email TEXT PRIMARY KEY,tenant TEXT NOT NULL,role TEXT NOT NULL,password_hash TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS tokens(token_hash TEXT PRIMARY KEY,email TEXT NOT NULL REFERENCES users(email));
 CREATE TABLE IF NOT EXISTS inventory(tenant TEXT NOT NULL,sku TEXT NOT NULL,name TEXT NOT NULL,on_hand INTEGER NOT NULL,reserved INTEGER NOT NULL DEFAULT 0,price_cents INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(tenant,sku),CHECK(on_hand>=0 AND reserved>=0 AND reserved<=on_hand));
 CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,client_ref TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,total_cents INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(tenant,client_ref));
 CREATE TABLE IF NOT EXISTS order_lines(order_id INTEGER NOT NULL REFERENCES orders(id),sku TEXT NOT NULL,quantity INTEGER NOT NULL,unit_price_cents INTEGER NOT NULL,returned_quantity INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(order_id,sku));
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,action TEXT NOT NULL,entity_id TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,request_hash TEXT NOT NULL,status INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(tenant,key));''')
 empty=c.execute('SELECT (SELECT count(*) FROM users)+(SELECT count(*) FROM inventory)+(SELECT count(*) FROM orders)').fetchone()[0]==0
 if os.environ.get('SEED_DEMO')=='1' and empty:
  ph=hashlib.sha256(b'DepotDemo!2026').hexdigest();c.execute('BEGIN IMMEDIATE')
  for t in ('north','south'):
   for role in ('admin','operator','viewer'):c.execute('INSERT INTO users VALUES(?,?,?,?)',(f'{role}@{t}.example',t,role,ph))
   for sku,name,n,p in CATALOG:c.execute('INSERT INTO inventory(tenant,sku,name,on_hand,price_cents) VALUES(?,?,?,?,?)',(t,sku,name,n,p))
  c.commit()
 c.close()
class ApiError(Exception):
 def __init__(self,status,code,message):self.status=status;self.code=code;self.message=message
def fail(status,code,message):raise ApiError(status,code,message)
def integer(v):return isinstance(v,int) and not isinstance(v,bool)
def text(v,name):
 if not isinstance(v,str) or not v.strip():fail(400,'invalid_payload',f'{name} must be nonempty text')
 return v.strip()
def item(r):return {'sku':r['sku'],'name':r['name'],'on_hand':r['on_hand'],'reserved':r['reserved'],'available':r['on_hand']-r['reserved'],'price_cents':r['price_cents'],'version':r['version']}
def get_order(c,oid,tenant):
 r=c.execute('SELECT * FROM orders WHERE tenant=? AND id=?',(tenant,oid)).fetchone()
 if not r:return None
 lines=c.execute('SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines WHERE order_id=? ORDER BY rowid',(oid,)).fetchall()
 return {'id':r['id'],'client_ref':r['client_ref'],'status':r['status'],'version':r['version'],'total_cents':r['total_cents'],'lines':[dict(x) for x in lines]}
class Handler(BaseHTTPRequestHandler):
 server_version='DepotFlow/1.0'
 def log_message(self,*args):pass
 def send_json(self,status,data):
  b=json.dumps(data,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def readbody(self):
  try:
   d=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
   if not isinstance(d,dict):fail(400,'invalid_json','Expected a JSON object')
   return d
  except ApiError:raise
  except Exception:fail(400,'invalid_json','Request body must be valid JSON')
 def user(self):
  h=self.headers.get('Authorization','');token=h[7:] if h.startswith('Bearer ') else ''
  if not token:fail(401,'unauthorized','A valid bearer token is required')
  c=db();r=c.execute('SELECT u.email,u.tenant,u.role FROM tokens t JOIN users u ON u.email=t.email WHERE t.token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone();c.close()
  if not r:fail(401,'unauthorized','A valid bearer token is required')
  return dict(r)
 def do_GET(self):
  p=urlparse(self.path).path
  if p in ('/','/index.html'):
   try:b=open(os.path.join(os.path.dirname(__file__),'index.html'),'rb').read()
   except OSError:b=b'UI not installed'
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if p=='/api/health':return self.send_json(200,{'status':'ok'})
  try:
   u=self.user();c=db();q=parse_qs(urlparse(self.path).query,keep_blank_values=True);t=u['tenant']
   if p=='/api/me':out=u
   elif p=='/api/inventory':out={'items':[item(r) for r in c.execute('SELECT * FROM inventory WHERE tenant=? ORDER BY sku',(t,))]}
   elif p=='/api/dashboard':
    counts={r['status']:r['n'] for r in c.execute('SELECT status,count(*) n FROM orders WHERE tenant=? GROUP BY status',(t,))};r=c.execute('SELECT coalesce(sum(on_hand),0) n,coalesce(sum(reserved),0) r FROM inventory WHERE tenant=?',(t,)).fetchone();out={'orders_by_status':counts,'inventory_units':r['n'],'reserved_units':r['r']}
   elif p=='/api/orders':
    ls=q.get('limit',['20'])[0]
    if not ls.isdigit() or not 1<=int(ls)<=100:fail(400,'invalid_filter','limit must be from 1 to 100')
    status=q.get('status',[''])[0]
    if status not in ('','draft','reserved','shipped','cancelled','returned'):fail(400,'invalid_filter','Unknown order status')
    cursor=q.get('cursor',[''])[0]
    if cursor:
     if not cursor.isdigit() or int(cursor)<1:fail(400,'invalid_cursor','Invalid cursor')
     cursor=int(cursor)
    else:cursor=0
    query=q.get('q',[''])[0];sql='SELECT id FROM orders WHERE tenant=?';args=[t]
    if status:sql+=' AND status=?';args.append(status)
    if query:sql+=' AND instr(lower(client_ref),lower(?))>0';args.append(query)
    ids=[r['id'] for r in c.execute(sql+' AND id>? ORDER BY id LIMIT ?',args+[cursor,int(ls)+1])];more=len(ids)>int(ls);ids=ids[:int(ls)]
    out={'items':[get_order(c,i,t) for i in ids],'next_cursor':str(ids[-1]) if more else None}
   elif p=='/api/audit':
    ls=q.get('limit',['20'])[0];cur=q.get('cursor',['0'])[0]
    if not ls.isdigit() or not 1<=int(ls)<=100:fail(400,'invalid_filter','limit must be from 1 to 100')
    if not cur.isdigit():fail(400,'invalid_cursor','Invalid cursor')
    rows=c.execute('SELECT * FROM audit WHERE tenant=? AND id>? ORDER BY id LIMIT ?',(t,int(cur),int(ls)+1)).fetchall();more=len(rows)>int(ls);rows=rows[:int(ls)]
    out={'items':[{'id':r['id'],'action':r['action'],'entity_id':r['entity_id'],'actor':r['actor'],'created_at':r['created_at']} for r in rows],'next_cursor':str(rows[-1]['id']) if more else None}
   elif p.startswith('/api/orders/') and p.count('/')==3:
    try:oid=int(p.rsplit('/',1)[1])
    except ValueError:fail(404,'not_found','Order not found')
    out=get_order(c,oid,t)
    if out is None:fail(404,'not_found','Order not found')
   else:fail(404,'not_found','Route not found')
   c.close();self.send_json(200,out)
  except ApiError as e:self.send_json(e.status,{'error':{'code':e.code,'message':e.message}})
  except Exception:self.send_json(500,{'error':{'code':'internal_error','message':'Internal server error'}})
 def do_POST(self):
  c=None
  try:
   d=self.readbody();p=urlparse(self.path).path
   if p=='/api/session':
    email=text(d.get('email'),'email').lower();pw=d.get('password')
    if not isinstance(pw,str):fail(401,'bad_credentials','Email or password is incorrect')
    c=db();r=c.execute('SELECT * FROM users WHERE email=? AND password_hash=?',(email,hashlib.sha256(pw.encode()).hexdigest())).fetchone()
    if not r:c.close();fail(401,'bad_credentials','Email or password is incorrect')
    token=secrets.token_urlsafe(32);c.execute('INSERT INTO tokens VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),email));c.close();return self.send_json(200,{'token':token,'user':{'email':email,'role':r['role'],'tenant':r['tenant']}})
   u=self.user()
   if u['role']=='viewer':fail(403,'forbidden','Viewer accounts cannot make changes')
   key=self.headers.get('Idempotency-Key','')
   if not key.strip():fail(400,'idempotency_required','Idempotency-Key is required')
   if len(key)>200:fail(400,'invalid_idempotency_key','Idempotency-Key is too long')
   if p=='/api/stock/adjustments' and u['role']!='admin':fail(403,'forbidden','Administrator role required')
   fingerprint=hashlib.sha256((self.command+'\n'+p+'\n'+json.dumps(d,sort_keys=True,separators=(',',':'))).encode()).hexdigest()
   c=db();c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM idempotency WHERE tenant=? AND key=?',(u['tenant'],key)).fetchone()
   if old:
    if old['request_hash']!=fingerprint:c.rollback();c.close();fail(409,'idempotency_conflict','Key was already used for a different request')
    c.commit();c.close();return self.send_json(old['status'],json.loads(old['body']))
   status,out=self.mutate(c,u,p,d);c.execute('INSERT INTO idempotency VALUES(?,?,?,?,?)',(u['tenant'],key,fingerprint,status,json.dumps(out,separators=(',',':'))));c.commit();c.close();self.send_json(status,out)
  except ApiError as e:
   if c is not None:
    try:c.rollback();c.close()
    except Exception:pass
   self.send_json(e.status,{'error':{'code':e.code,'message':e.message}})
  except sqlite3.IntegrityError:
   if c is not None:
    try:c.rollback();c.close()
    except Exception:pass
   self.send_json(409,{'error':{'code':'conflict','message':'A conflicting resource already exists'}})
  except Exception:
   if c is not None:
    try:c.rollback();c.close()
    except Exception:pass
   self.send_json(500,{'error':{'code':'internal_error','message':'Internal server error'}})
 def mutate(self,c,u,p,d):
  t=u['tenant'];actor=u['email']
  def audit(action,eid):c.execute('INSERT INTO audit(tenant,action,entity_id,actor,created_at) VALUES(?,?,?,?,?)',(t,action,str(eid),actor,now()))
  if p=='/api/stock/adjustments':
   sku=text(d.get('sku'),'sku').upper();delta=d.get('delta');ev=d.get('expected_version');text(d.get('reason'),'reason')
   if not integer(delta) or delta==0 or not integer(ev):fail(400,'invalid_payload','delta must be a nonzero integer and expected_version an integer')
   r=c.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?',(t,sku)).fetchone()
   if not r:fail(400,'unknown_sku','Unknown SKU')
   if ev!=r['version']:fail(409,'stale_version','Inventory version is stale')
   if r['on_hand']+delta<r['reserved']:fail(409,'insufficient_stock','Adjustment would reduce stock below reserved quantity')
   c.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?',(delta,t,sku));audit('stock.adjusted',sku)
   return 200,item(c.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?',(t,sku)).fetchone())
  if p=='/api/orders':
   ref=text(d.get('client_ref'),'client_ref');lines=d.get('lines')
   if not isinstance(lines,list) or not lines:fail(400,'invalid_lines','At least one line is required')
   seen=set();values=[];total=0
   for l in lines:
    if not isinstance(l,dict):fail(400,'invalid_lines','Each line must be an object')
    sku=text(l.get('sku'),'sku').upper();qty=l.get('quantity')
    if not integer(qty) or qty<=0:fail(400,'invalid_quantity','Quantity must be a positive integer')
    if sku in seen:fail(400,'duplicate_sku','Duplicate SKU lines are invalid')
    seen.add(sku);r=c.execute('SELECT price_cents FROM inventory WHERE tenant=? AND sku=?',(t,sku)).fetchone()
    if not r:fail(400,'unknown_sku','Unknown SKU')
    total+=r['price_cents']*qty;values.append((sku,qty,r['price_cents']))
   try:c.execute("INSERT INTO orders(tenant,client_ref,status,version,total_cents,created_at) VALUES(?,?, 'draft',1,?,?)",(t,ref,total,now()))
   except sqlite3.IntegrityError:fail(409,'client_ref_conflict','Client reference already exists')
   oid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   for sku,qty,price in values:c.execute('INSERT INTO order_lines(order_id,sku,quantity,unit_price_cents) VALUES(?,?,?,?)',(oid,sku,qty,price))
   audit('order.created',oid);return 201,get_order(c,oid,t)
  a=p.split('/')
  if len(a)!=5 or a[:2]!=['','api'] or a[2]!='orders' or not a[3].isdigit():fail(404,'not_found','Route not found')
  oid=int(a[3]);action=a[4];order=get_order(c,oid,t)
  if not order:fail(404,'not_found','Order not found')
  ev=d.get('expected_version')
  if not integer(ev):fail(400,'invalid_payload','expected_version must be an integer')
  if ev!=order['version']:fail(409,'stale_version','Order version is stale')
  if action=='reserve':
   if order['status']!='draft':fail(409,'invalid_transition','Only draft orders can be reserved')
   for l in order['lines']:
    r=c.execute('SELECT on_hand,reserved FROM inventory WHERE tenant=? AND sku=?',(t,l['sku'])).fetchone()
    if r['on_hand']-r['reserved']<l['quantity']:fail(409,'insufficient_stock',f"Insufficient available stock for {l['sku']}")
   for l in order['lines']:c.execute('UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?',(l['quantity'],t,l['sku']))
   new='reserved'
  elif action=='ship':
   if order['status']!='reserved':fail(409,'invalid_transition','Only reserved orders can be shipped')
   for l in order['lines']:c.execute('UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',(l['quantity'],l['quantity'],t,l['sku']))
   new='shipped'
  elif action=='cancel':
   if order['status'] not in ('draft','reserved'):fail(409,'invalid_transition','Only draft or reserved orders can be cancelled')
   if order['status']=='reserved':
    for l in order['lines']:c.execute('UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',(l['quantity'],t,l['sku']))
   new='cancelled'
  elif action=='returns':
   if order['status']!='shipped':fail(409,'invalid_transition','Only shipped orders can be returned')
   lines=d.get('lines')
   if not isinstance(lines,list) or not lines:fail(400,'invalid_lines','At least one return line is required')
   existing={l['sku']:l for l in order['lines']};seen=set()
   for l in lines:
    if not isinstance(l,dict):fail(400,'invalid_lines','Each line must be an object')
    sku=text(l.get('sku'),'sku').upper();qty=l.get('quantity')
    if not integer(qty) or qty<=0:fail(400,'invalid_quantity','Quantity must be a positive integer')
    if sku in seen:fail(400,'duplicate_sku','Duplicate return lines are invalid')
    seen.add(sku)
    if sku not in existing:fail(400,'invalid_return_sku','SKU is not part of this order')
    if qty>existing[sku]['quantity']-existing[sku]['returned_quantity']:fail(409,'return_exceeds_shipped','Return quantity exceeds unreturned shipped quantity')
   for l in lines:
    sku=l['sku'].upper();qty=l['quantity'];c.execute('UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE order_id=? AND sku=?',(qty,oid,sku));c.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?',(qty,t,sku))
   remain=c.execute('SELECT sum(quantity-returned_quantity) FROM order_lines WHERE order_id=?',(oid,)).fetchone()[0];new='returned' if remain==0 else 'shipped'
  else:fail(404,'not_found','Route not found')
  c.execute('UPDATE orders SET status=?,version=version+1 WHERE id=?',(new,oid));audit('order.'+action,oid);return 200,get_order(c,oid,t)

def main():
 init();port=int(os.environ.get('PORT','8000'));s=ThreadingHTTPServer(('127.0.0.1',port),Handler);print(f'DepotFlow listening at 127.0.0.1:{port}; database {DB}',flush=True);s.serve_forever()
if __name__=='__main__':main()
