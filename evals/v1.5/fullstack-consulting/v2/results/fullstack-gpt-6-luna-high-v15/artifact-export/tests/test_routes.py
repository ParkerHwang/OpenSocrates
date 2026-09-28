import json, os, socket, subprocess, tempfile, threading, time, unittest, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class DepotFlowRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT); self.port=self.free_port(); self.url=f'http://127.0.0.1:{self.port}'
        self.proc=None; self.start(seed=True)
        self.admin=self.login('admin@north.example'); self.op=self.login('operator@north.example'); self.viewer=self.login('viewer@north.example'); self.south=self.login('operator@south.example')
    def tearDown(self):
        self.stop(); self.tmp.cleanup()
    def free_port(self):
        s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p
    def start(self,seed=False):
        env=os.environ.copy(); env.update(PORT=str(self.port),DATA_DIR=self.tmp.name,SEED_DEMO='1' if seed else '0')
        self.proc=subprocess.Popen([str(ROOT/'run.sh')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                self.request('GET','/api/health'); return
            except Exception: time.sleep(.03)
        self.fail('server did not start')
    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate(); self.proc.wait(timeout=5)
    def request(self,method,path,body=None,token=None,key=None):
        headers={}
        if body is not None: headers['Content-Type']='application/json'
        if token: headers['Authorization']='Bearer '+token
        if key: headers['Idempotency-Key']=key
        data=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(self.url+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=10) as r: return r.status,json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code,json.loads(e.read())
    def login(self,email):
        s,d=self.request('POST','/api/session',{'email':email,'password':'DepotDemo!2026'}); self.assertEqual(s,200); return d['token']
    def post(self,path,body,token=None,key=None): return self.request('POST',path,body,token or self.op,key or 'k-'+str(time.time_ns()))
    def test_full_routes_isolation_atomicity_retry_restart(self):
        self.assertEqual(self.request('GET','/api/health'),(200,{'status':'ok'}))
        self.assertEqual(self.request('GET','/api/me')[0],401)
        self.assertEqual(self.request('POST','/api/stock/adjustments',{'sku':'BOLT','delta':1,'expected_version':1,'reason':'no key'},self.admin)[0],400)
        s,inv=self.request('GET','/api/inventory',token=self.op); self.assertEqual(s,200); self.assertEqual([(x['sku'],x['on_hand']) for x in inv['items']],[('BOLT',100),('CABLE',60),('SAMPLE',20)])
        self.assertEqual(self.request('GET','/api/inventory',token=self.south)[1]['items'][0]['on_hand'],100)
        s,order=self.post('/api/orders',{'client_ref':'ZeroSAMPLE','lines':[{'sku':'SAMPLE','quantity':2}]}); self.assertEqual(s,201); self.assertEqual(order['total_cents'],0)
        self.assertEqual(self.post('/api/orders',{'client_ref':'ZeroSAMPLE','lines':[{'sku':'SAMPLE','quantity':3}]})[0],409)
        for bad in ({'client_ref':'x','lines':[]},{'client_ref':'x','lines':[{'sku':'BOLT','quantity':True}]},{'client_ref':'x','lines':[{'sku':'BOLT','quantity':1.5}]},{'client_ref':'x','lines':[{'sku':'Z','quantity':1}]},{'client_ref':'x','lines':[{'sku':'BOLT','quantity':1},{'sku':'BOLT','quantity':1}]}): self.assertEqual(self.post('/api/orders',bad)[0],400)
        self.assertEqual(self.post('/api/orders',{'client_ref':'x','lines':[{'sku':'BOLT','quantity':1}]},self.viewer)[0],403)
        self.assertEqual(self.request('GET','/api/orders/'+order['id'],token=self.south)[0],404)
        # Multi-line reservation failure leaves every stock row and order untouched.
        _,too_big=self.post('/api/orders',{'client_ref':'atomic-fail','lines':[{'sku':'BOLT','quantity':1},{'sku':'CABLE','quantity':999}]})
        before=self.request('GET','/api/inventory',token=self.op)[1]['items']
        self.assertEqual(self.post('/api/orders/'+too_big['id']+'/reserve',{'expected_version':1})[0],409)
        self.assertEqual(self.request('GET','/api/inventory',token=self.op)[1]['items'],before)
        self.assertEqual(self.request('GET','/api/orders/'+too_big['id'],token=self.op)[1]['version'],1)
        # Concurrent reservations cannot oversell a final unit.
        _,adj=self.post('/api/stock/adjustments',{'sku':'BOLT','delta':-99,'expected_version':1,'reason':'concurrency fixture'},self.admin)
        ids=[]
        for n in range(2): ids.append(self.post('/api/orders',{'client_ref':f'race-{n}','lines':[{'sku':'BOLT','quantity':1}]})[1]['id'])
        def reserve(i): return self.post(f'/api/orders/{i}/reserve',{'expected_version':1})[0]
        with ThreadPoolExecutor(2) as ex: results=list(ex.map(reserve,ids))
        self.assertEqual(sorted(results),[200,409]); stock=self.request('GET','/api/inventory',token=self.op)[1]['items'][0]; self.assertEqual(stock['reserved'],1); self.assertGreaterEqual(stock['available'],0)
        winner=ids[results.index(200)]; self.assertEqual(self.post(f'/api/orders/{winner}/ship',{'expected_version':2})[0],200)
        shipped=self.request('GET',f'/api/orders/{winner}',token=self.op)[1]
        self.assertEqual(self.post(f"/api/orders/{winner}/returns",{'expected_version':shipped['version'],'lines':[{'sku':'BOLT','quantity':1}]})[0],200)
        returned=self.request('GET',f'/api/orders/{winner}',token=self.op)[1]; self.assertEqual(returned['status'],'returned')
        self.assertEqual(self.post(f"/api/orders/{winner}/returns",{'expected_version':returned['version'],'lines':[{'sku':'BOLT','quantity':1}]})[0],409)
        # Partial and full returns on a separate two-unit order.
        _,ret=self.post('/api/orders',{'client_ref':'partial-full','lines':[{'sku':'CABLE','quantity':2}]})
        self.assertEqual(self.post(f"/api/orders/{ret['id']}/reserve",{'expected_version':1})[0],200)
        self.assertEqual(self.post(f"/api/orders/{ret['id']}/ship",{'expected_version':2})[0],200)
        self.assertEqual(self.post(f"/api/orders/{ret['id']}/returns",{'expected_version':3,'lines':[{'sku':'CABLE','quantity':1}]})[1]['status'],'shipped')
        self.assertEqual(self.post(f"/api/orders/{ret['id']}/returns",{'expected_version':4,'lines':[{'sku':'CABLE','quantity':1}]})[1]['status'],'returned')
        # Replay returns exactly the first body once, across restart.
        req={'client_ref':'replay','lines':[{'sku':'SAMPLE','quantity':1}]}; s,first=self.post('/api/orders',req,key='replay-key'); self.assertEqual(s,201)
        self.assertEqual(self.post('/api/orders',req,key='replay-key'),(201,first))
        self.assertEqual(self.post('/api/orders',{'client_ref':'changed','lines':req['lines']},key='replay-key')[0],409)
        before_audit=self.request('GET','/api/audit?limit=100',token=self.op)[1]['items']; self.assertEqual(sum(1 for x in before_audit if x['action']=='order.created' and x['entity_id']==first['id']),1)
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'BOLT','delta':1,'expected_version':1,'reason':'cross endpoint'},self.admin,key='replay-key')[0],409)
        # Stale version and failed request do not create audit events.
        audit_count=len(before_audit)
        self.assertEqual(self.post('/api/orders/'+first['id']+'/cancel',{'expected_version':99})[0],409)
        self.assertEqual(len(self.request('GET','/api/audit?limit=100',token=self.op)[1]['items']),audit_count)
        self.stop(); self.start(seed=True)
        self.assertEqual(self.request('GET','/api/orders/'+first['id'],token=self.op)[1],first)
        self.assertEqual(self.post('/api/orders',req,key='replay-key'),(201,first))
        inv_after=self.request('GET','/api/inventory',token=self.op)[1]['items']; self.assertEqual(inv_after[0]['on_hand'],1)
        self.assertEqual(self.request('GET','/api/dashboard',token=self.op)[1]['orders_by_status']['returned'],2)
        self.assertEqual(self.request('GET','/api/audit?limit=100',token=self.south)[1]['items'],[])

if __name__=='__main__': unittest.main(verbosity=2)
