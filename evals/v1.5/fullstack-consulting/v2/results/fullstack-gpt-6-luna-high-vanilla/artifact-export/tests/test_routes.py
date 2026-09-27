import concurrent.futures, json, os, socket, subprocess, tempfile, time, unittest, urllib.error, urllib.request

ROOT=os.path.dirname(os.path.dirname(__file__))
class App(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();s=socket.socket();s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1];s.close()
  env=os.environ.copy();env.update(PORT=str(cls.port),DATA_DIR=cls.tmp.name,SEED_DEMO='1')
  cls.proc=subprocess.Popen(['./run.sh'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cls.base=f'http://127.0.0.1:{cls.port}'
  for _ in range(100):
   try:cls.call('GET','/api/health');break
   except Exception:time.sleep(.05)
  cls.admin=cls.login('admin@north.example');cls.op=cls.login('operator@north.example');cls.viewer=cls.login('viewer@north.example');cls.south=cls.login('admin@south.example')
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=5);cls.tmp.cleanup()
 @classmethod
 def call(cls,method,path,data=None,token=None,key=None,status=None):
  h={};
  if token:h['Authorization']='Bearer '+token
  if key:h['Idempotency-Key']=key
  raw=None if data is None else json.dumps(data).encode()
  if raw is not None:h['Content-Type']='application/json'
  req=urllib.request.Request(cls.base+path,data=raw,headers=h,method=method)
  try:r=urllib.request.urlopen(req,timeout=10);sc=r.status;body=json.loads(r.read())
  except urllib.error.HTTPError as e:sc=e.code;body=json.loads(e.read())
  if status is not None:assert sc==status,(sc,body)
  return sc,body
 @classmethod
 def login(cls,email):return cls.call('POST','/api/session',{'email':email,'password':'DepotDemo!2026'})[1]['token']
 def mutate(self,path,data,token=None,key=None,status=None):return self.call('POST',path,data,token or self.op,key or 'k-'+str(time.time_ns()),status)
 def test_auth_roles_and_tenant_scope(self):
  self.call('GET','/api/health',status=200)
  self.call('GET','/api/me',status=401)
  self.call('POST','/api/session',{'email':'operator@north.example','password':'bad'},status=401)
  self.call('GET','/api/inventory',token=self.south,status=200)
  self.call('POST','/api/orders',{'client_ref':'viewer-denied','lines':[{'sku':'BOLT','quantity':1}]},token=self.viewer,key='viewer-key',status=403)
  oid=self.mutate('/api/orders',{'client_ref':'tenant-secret','lines':[{'sku':'BOLT','quantity':1}]})[1]['id']
  self.call('GET',f'/api/orders/{oid}',token=self.south,status=404)
  self.call('GET','/api/audit',token=self.south,status=200)
 def test_admin_adjustment_and_cancellation(self):
  before=len(self.call('GET','/api/audit?limit=100',token=self.op)[1]['items'])
  adjusted=self.call('POST','/api/stock/adjustments',{'sku':'BOLT','delta':5,'expected_version':1,'reason':'receiving'},token=self.admin,key='adjust-once',status=200)[1]
  replay=self.call('POST','/api/stock/adjustments',{'sku':'BOLT','delta':5,'expected_version':1,'reason':'receiving'},token=self.admin,key='adjust-once',status=200)[1]
  self.assertEqual(adjusted,replay);self.assertEqual(adjusted['on_hand'],105)
  self.call('POST','/api/stock/adjustments',{'sku':'BOLT','delta':-200,'expected_version':2,'reason':'bad reduction'},token=self.admin,key='adjust-fail',status=409)
  order=self.mutate('/api/orders',{'client_ref':'cancel-draft','lines':[{'sku':'BOLT','quantity':2}]})[1]
  cancelled=self.call('POST',f"/api/orders/{order['id']}/cancel",{'expected_version':1},token=self.op,key='cancel-draft',status=200)[1];self.assertEqual(cancelled['status'],'cancelled')
  order=self.mutate('/api/orders',{'client_ref':'cancel-reserved','lines':[{'sku':'BOLT','quantity':2}]})[1]
  self.call('POST',f"/api/orders/{order['id']}/reserve",{'expected_version':1},token=self.op,key='cancel-reserve',status=200)
  self.call('POST',f"/api/orders/{order['id']}/cancel",{'expected_version':2},token=self.op,key='cancel-reserved',status=200)
  self.assertEqual(len(self.call('GET','/api/audit?limit=100',token=self.op)[1]['items']),before+6)
 def test_validation_zero_price_and_idempotency(self):
  self.mutate('/api/orders',{'client_ref':'zero-sample','lines':[{'sku':'SAMPLE','quantity':3}]},key='zero',status=201)
  status,order=self.call('POST','/api/orders',{'client_ref':'zero-sample-replay','lines':[{'sku':'SAMPLE','quantity':3}]},token=self.op,key='create-replay',status=201)
  replay=self.call('POST','/api/orders',{'client_ref':'zero-sample-replay','lines':[{'sku':'SAMPLE','quantity':3}]},token=self.op,key='create-replay',status=201)[1]
  self.assertEqual(order,replay);self.assertEqual(order['total_cents'],0)
  self.mutate('/api/orders',{'client_ref':'badqty','lines':[{'sku':'BOLT','quantity':True}]},status=400)
  self.mutate('/api/orders',{'client_ref':'badsku','lines':[{'sku':'WAT','quantity':1}]},status=400)
  self.mutate('/api/orders',{'client_ref':'baddup','lines':[{'sku':'BOLT','quantity':1},{'sku':'BOLT','quantity':1}]},status=400)
  self.mutate('/api/orders',{'client_ref':'zero-sample','lines':[{'sku':'SAMPLE','quantity':1}]},status=409)
  self.call('POST','/api/orders',{'client_ref':'key-change','lines':[{'sku':'BOLT','quantity':1}]},token=self.op,key='reused',status=201)
  self.call('POST','/api/orders',{'client_ref':'key-change2','lines':[{'sku':'BOLT','quantity':1}]},token=self.op,key='reused',status=409)
  self.call('POST','/api/orders',{'client_ref':'no-key','lines':[{'sku':'BOLT','quantity':1}]},token=self.op,status=400)
 def test_concurrent_identical_create_is_one_effect(self):
  before=len(self.call('GET','/api/audit?limit=100',token=self.op)[1]['items']);payload={'client_ref':'concurrent-replay','lines':[{'sku':'SAMPLE','quantity':2}]}
  def create(_):return self.call('POST','/api/orders',payload,token=self.op,key='concurrent-create',status=201)[1]
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:orders=list(pool.map(create,range(8)))
  self.assertTrue(all(o==orders[0] for o in orders));self.assertEqual(len(self.call('GET','/api/audit?limit=100',token=self.op)[1]['items']),before+1)
 def test_order_cursor_search_and_empty(self):
  for suffix in ('a','b','c'):self.mutate('/api/orders',{'client_ref':'page-'+suffix,'lines':[{'sku':'SAMPLE','quantity':1}]})
  _,first=self.call('GET','/api/orders?q=PAGE-&limit=2',token=self.op,status=200);self.assertEqual(len(first['items']),2);self.assertIsNotNone(first['next_cursor'])
  _,second=self.call('GET','/api/orders?q=page-&limit=2&cursor='+first['next_cursor'],token=self.op,status=200)
  self.assertEqual(len(second['items']),1);self.assertGreater(second['items'][0]['id'],first['items'][-1]['id'])
  _,empty=self.call('GET','/api/orders?q=no-such-ref',token=self.op,status=200);self.assertEqual(empty['items'],[])
  self.call('GET','/api/orders?limit=0',token=self.op,status=400);self.call('GET','/api/orders?cursor=bad',token=self.op,status=400)
 def test_atomic_reserve_race_and_stale(self):
  # Each competing order reserves all 55 CABLE units; exactly one may win.
  ids=[]
  for ref in ('race-a','race-b'):
   ids.append(self.mutate('/api/orders',{'client_ref':ref,'lines':[{'sku':'CABLE','quantity':55}]})[1]['id'])
  def reserve(i):return self.call('POST',f'/api/orders/{i}/reserve',{'expected_version':1},token=self.op,key='race-'+str(i))[0]
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(reserve,ids))
  self.assertEqual(sorted(codes),[200,409]);inv=self.call('GET','/api/inventory',token=self.op)[1]['items'];cable=next(i for i in inv if i['sku']=='CABLE');self.assertEqual(cable['reserved'],55);self.assertGreaterEqual(cable['available'],0)
  winner=ids[codes.index(200)]
  self.call('POST',f'/api/orders/{winner}/reserve',{'expected_version':1},token=self.op,key='race-'+str(winner),status=200)
  self.call('POST',f'/api/orders/{winner}/ship',{'expected_version':1},token=self.op,key='stale',status=409)
  self.call('POST','/api/stock/adjustments',{'sku':'BOLT','delta':-1,'expected_version':99,'reason':'stale'},token=self.admin,key='stale-stock',status=409)
  self.mutate('/api/stock/adjustments',{'sku':'BOLT','delta':-1,'expected_version':1,'reason':'operator denied'},token=self.op,status=403)
 def test_multi_line_atomic_returns_and_restart_durability(self):
  before=self.call('GET','/api/inventory',token=self.op)[1]['items'];bolt=next(x for x in before if x['sku']=='BOLT');cable=next(x for x in before if x['sku']=='CABLE')
  oid=self.mutate('/api/orders',{'client_ref':'atomic-return','lines':[{'sku':'BOLT','quantity':2},{'sku':'CABLE','quantity':100}]})[1]['id']
  self.call('POST',f'/api/orders/{oid}/reserve',{'expected_version':1},token=self.op,key='atomic-fail',status=409)
  after=self.call('GET','/api/inventory',token=self.op)[1]['items'];self.assertEqual(before,after)
  # Small feasible order: transitions and partial then complete return.
  oid=self.mutate('/api/orders',{'client_ref':'return-flow','lines':[{'sku':'BOLT','quantity':2},{'sku':'SAMPLE','quantity':1}]})[1]['id']
  r=self.call('POST',f'/api/orders/{oid}/reserve',{'expected_version':1},token=self.op,key='rf-reserve')[1]
  r=self.call('POST',f'/api/orders/{oid}/ship',{'expected_version':2},token=self.op,key='rf-ship')[1]
  r=self.call('POST',f'/api/orders/{oid}/returns',{'expected_version':3,'lines':[{'sku':'BOLT','quantity':1}]},token=self.op,key='rf-part')[1];self.assertEqual(r['status'],'shipped');self.assertEqual(r['version'],4)
  r=self.call('POST',f'/api/orders/{oid}/returns',{'expected_version':4,'lines':[{'sku':'BOLT','quantity':1},{'sku':'SAMPLE','quantity':1}]},token=self.op,key='rf-full')[1];self.assertEqual(r['status'],'returned')
  events=self.call('GET','/api/audit?limit=100',token=self.op)[1]['items'];n=len(events)
  self.proc.terminate();self.proc.wait(timeout=5)
  env=os.environ.copy();env.update(PORT=str(self.port),DATA_DIR=self.tmp.name,SEED_DEMO='1');self.__class__.proc=subprocess.Popen(['./run.sh'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(100):
   try:self.call('GET','/api/health');break
   except Exception:time.sleep(.05)
  durable=self.call('GET',f'/api/orders/{oid}',token=self.op)[1];self.assertEqual(durable['status'],'returned')
  self.assertEqual(len(self.call('GET','/api/audit?limit=100',token=self.op)[1]['items']),n)
  # Successful idempotency body also survives restart.
  replay=self.call('POST',f'/api/orders/{oid}/returns',{'expected_version':4,'lines':[{'sku':'BOLT','quantity':1},{'sku':'SAMPLE','quantity':1}]},token=self.op,key='rf-full',status=200)[1];self.assertEqual(replay,durable)

if __name__=='__main__':unittest.main()
