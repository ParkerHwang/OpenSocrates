import concurrent.futures, json, os, socket, subprocess, tempfile, time, unittest, urllib.error, urllib.request, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class DepotApiTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.port=self.free_port(); self.base=f'http://127.0.0.1:{self.port}'; self.start(seed=True)
        self.north=self.login('admin@north.example'); self.south=self.login('admin@south.example'); self.operator=self.login('operator@north.example'); self.viewer=self.login('viewer@north.example')
    def tearDown(self):
        self.stop(); self.temp.cleanup()
    @staticmethod
    def free_port():
        sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close(); return port
    def start(self,seed=False):
        env={**os.environ,'DATA_DIR':self.temp.name,'PORT':str(self.port),'SEED_DEMO':'1' if seed else '0'}
        self.proc=subprocess.Popen([str(ROOT/'run.sh')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                if self.call('GET','/api/health')[0]==200: return
            except Exception: pass
            time.sleep(.05)
        raise AssertionError('server did not start: '+self.proc.stderr.read().decode())
    def stop(self):
        self.proc.terminate()
        try: self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait()
        error=self.proc.stderr.read().decode()
        if error: print(error)
        self.proc.stderr.close()
    def call(self,method,path,body=None,token=None,key=None):
        headers={}
        if token: headers['Authorization']='Bearer '+token
        if body is not None:
            headers['Content-Type']='application/json'; headers['Idempotency-Key']=key or str(uuid.uuid4())
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
        try: response=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as error: response=error
        with response: return response.status,json.load(response)
    def login(self,email):
        status,body=self.call('POST','/api/session',{'email':email,'password':'DepotDemo!2026'})
        self.assertEqual(status,200); return body['token']
    def request(self,method,path,body=None,token=None,key=None,expected=200):
        status,result=self.call(method,path,body,token or self.north,key)
        self.assertEqual(status,expected,(path,result)); return result
    def inventory(self,token=None): return {i['sku']:i for i in self.request('GET','/api/inventory',token=token)['items']}
    def audit(self,token=None): return self.request('GET','/api/audit?limit=100',token=token)['items']
    def test_workflow_returns_replay_and_restart(self):
        self.assertEqual(self.inventory()['BOLT']['available'],100)
        order=self.request('POST','/api/orders',{'client_ref':'workflow','lines':[{'sku':'BOLT','quantity':3},{'sku':'SAMPLE','quantity':2}],'total_cents':1,'tenant':'south'},key='create-workflow',expected=201)
        self.assertEqual(order['total_cents'],3750); self.assertEqual(order['version'],1)
        self.assertEqual(self.request('POST','/api/orders',{'tenant':'south','total_cents':1,'lines':[{'quantity':3,'sku':'BOLT'},{'quantity':2,'sku':'SAMPLE'}],'client_ref':'workflow'},key='create-workflow',expected=201),order)
        self.assertEqual(len(self.audit()),1)
        reserved=self.request('POST',f"/api/orders/{order['id']}/reserve",{'expected_version':1},key='reserve-workflow')
        self.assertEqual(reserved['version'],2); self.assertEqual(self.inventory()['BOLT']['reserved'],3)
        self.request('POST',f"/api/orders/{order['id']}/reserve",{'expected_version':1},expected=409)
        shipped=self.request('POST',f"/api/orders/{order['id']}/ship",{'expected_version':2})
        self.assertEqual(shipped['status'],'shipped'); self.assertEqual(self.inventory()['BOLT']['available'],97)
        self.request('POST',f"/api/orders/{order['id']}/returns",{'expected_version':3,'lines':[{'sku':'BOLT','quantity':1}]})
        self.assertEqual(self.inventory()['BOLT']['on_hand'],98)
        complete=self.request('POST',f"/api/orders/{order['id']}/returns",{'expected_version':4,'lines':[{'sku':'BOLT','quantity':2},{'sku':'SAMPLE','quantity':2}]})
        self.assertEqual(complete['status'],'returned'); self.assertEqual(complete['version'],5)
        self.assertEqual(len(self.audit()),5)
        self.assertEqual(self.request('GET','/api/dashboard')['orders_by_status']['returned'],1)
        self.stop(); self.start(seed=True)
        self.assertEqual(self.request('GET',f"/api/orders/{order['id']}"),complete)
        self.assertEqual(self.request('POST',f"/api/orders/{order['id']}/reserve",{'expected_version':1},key='reserve-workflow'),reserved)
        self.assertEqual(len(self.audit()),5); self.assertEqual(self.inventory()['BOLT']['on_hand'],100)
    def test_roles_validation_atomicity_and_isolation(self):
        self.request('GET','/api/inventory',token=self.viewer)
        self.request('POST','/api/orders',{'client_ref':'blocked','lines':[{'sku':'BOLT','quantity':1}]},token=self.viewer,expected=403)
        self.request('POST','/api/stock/adjustments',{'sku':'BOLT','delta':1,'expected_version':1,'reason':'test'},token=self.operator,expected=403)
        self.assertEqual(self.call('GET','/api/me')[0],401)
        self.assertEqual(self.call('POST','/api/session',{'email':'admin@north.example','password':'bad'})[0],401)
        self.request('POST','/api/orders',{'client_ref':'bad','lines':[{'sku':'BOLT','quantity':True}]},expected=400)
        self.request('POST','/api/orders',{'client_ref':'bad','lines':[{'sku':'UNKNOWN','quantity':1}]},expected=400)
        self.request('POST','/api/orders',{'client_ref':'bad','lines':[{'sku':'BOLT','quantity':1},{'sku':'BOLT','quantity':1}]},expected=400)
        zero=self.request('POST','/api/orders',{'client_ref':'zero','lines':[{'sku':'SAMPLE','quantity':1}]},expected=201)
        self.assertEqual(zero['total_cents'],0)
        self.request('POST','/api/orders',{'client_ref':'zero','lines':[{'sku':'SAMPLE','quantity':2}]},expected=409)
        self.request('POST','/api/orders',{'client_ref':'zero','lines':[{'sku':'SAMPLE','quantity':1}]},key='conflicting-key',expected=409)
        self.request('POST','/api/orders',{'client_ref':'other','lines':[{'sku':'SAMPLE','quantity':1}]},key='conflicting-key',expected=201)
        south=self.request('POST','/api/orders',{'client_ref':'zero','lines':[{'sku':'BOLT','quantity':1}]},token=self.south,expected=201)
        self.request('GET',f"/api/orders/{south['id']}",expected=404)
        self.request('POST',f"/api/orders/{south['id']}/reserve",{'expected_version':1},expected=404)
        self.assertEqual(self.inventory(self.south)['BOLT']['on_hand'],100)
        before=self.inventory(); events=len(self.audit())
        failing=self.request('POST','/api/orders',{'client_ref':'too-many','lines':[{'sku':'BOLT','quantity':1},{'sku':'CABLE','quantity':61}]},expected=201)
        events+=1
        self.request('POST',f"/api/orders/{failing['id']}/reserve",{'expected_version':1},expected=409)
        self.assertEqual(self.inventory(),before); self.assertEqual(len(self.audit()),events)
        adjusted=self.request('POST','/api/stock/adjustments',{'sku':'BOLT','delta':-2,'expected_version':1,'reason':'count'})
        self.assertEqual(adjusted['on_hand'],98)
        self.request('POST','/api/stock/adjustments',{'sku':'BOLT','delta':1,'expected_version':1,'reason':'stale'},expected=409)
        req=urllib.request.Request(self.base+'/api/orders',data=b'{"client_ref":"missing-key","lines":[{"sku":"BOLT","quantity":1}]}',headers={'Authorization':'Bearer '+self.north,'Content-Type':'application/json'},method='POST')
        with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(req)
        self.assertEqual(error.exception.code,400)
        self.request('GET','/api/orders?cursor=',expected=400)
        self.request('POST','/api/orders',{'client_ref':'boolean','lines':[{'sku':'BOLT','quantity':True}]},expected=400)
        self.request('POST','/api/orders',{'client_ref':'huge','lines':[{'sku':'BOLT','quantity':2**70}]},expected=400)
        self.request('POST','/api/stock/adjustments',{'sku':'BOLT','delta':True,'expected_version':2,'reason':'bad'},expected=400)
    def test_cancel_reserved_and_reject_overreturn(self):
        order=self.request('POST','/api/orders',{'client_ref':'cancel-me','lines':[{'sku':'CABLE','quantity':4}]},expected=201)
        self.request('POST',f"/api/orders/{order['id']}/reserve",{'expected_version':1})
        self.assertEqual(self.inventory()['CABLE']['reserved'],4)
        before=self.inventory(); events=len(self.audit())
        self.request('POST','/api/stock/adjustments',{'sku':'CABLE','delta':-57,'expected_version':2,'reason':'below reserved'},expected=409)
        self.assertEqual(self.inventory(),before); self.assertEqual(len(self.audit()),events)
        cancelled=self.request('POST',f"/api/orders/{order['id']}/cancel",{'expected_version':2})
        self.assertEqual(cancelled['status'],'cancelled'); self.assertEqual(self.inventory()['CABLE']['reserved'],0)
        self.request('POST',f"/api/orders/{order['id']}/ship",{'expected_version':3},expected=409)
        shipped=self.request('POST','/api/orders',{'client_ref':'return-limit','lines':[{'sku':'CABLE','quantity':2}]},expected=201)
        self.request('POST',f"/api/orders/{shipped['id']}/reserve",{'expected_version':1})
        self.request('POST',f"/api/orders/{shipped['id']}/ship",{'expected_version':2})
        before=self.inventory(); events=len(self.audit())
        self.request('POST',f"/api/orders/{shipped['id']}/returns",{'expected_version':3,'lines':[{'sku':'CABLE','quantity':3}]},expected=409)
        self.assertEqual(self.inventory(),before); self.assertEqual(len(self.audit()),events)
        self.assertEqual(self.inventory(),before)
    def test_concurrency_pagination_and_key_scope(self):
        orders=[self.request('POST','/api/orders',{'client_ref':f'race-{i}','lines':[{'sku':'BOLT','quantity':60}]},expected=201) for i in range(2)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda o:self.call('POST',f"/api/orders/{o['id']}/reserve",{'expected_version':1},self.north),orders))
        self.assertEqual(sorted(s for s,_ in results),[200,409]); self.assertEqual(self.inventory()['BOLT']['reserved'],60)
        self.assertEqual(sum(e['action']=='order_reserved' for e in self.audit()),1)
        before=len(self.audit())
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(lambda _:self.call('POST','/api/orders',{'client_ref':'same-key','lines':[{'sku':'SAMPLE','quantity':1}]},self.north,'shared'),range(5)))
        self.assertEqual([s for s,_ in results],[201]*5); self.assertEqual(len({r['id'] for _,r in results}),1); self.assertEqual(len(self.audit()),before+1)
        self.request('POST','/api/orders',{'client_ref':'different','lines':[{'sku':'SAMPLE','quantity':1}]},key='shared',expected=409)
        self.request('POST','/api/orders',{'client_ref':'south-key','lines':[{'sku':'SAMPLE','quantity':1}]},token=self.south,key='shared',expected=201)
        first=self.request('GET','/api/orders?limit=1&q=race'); self.assertEqual(len(first['items']),1)
        self.request('POST','/api/orders',{'client_ref':'race-later','lines':[{'sku':'SAMPLE','quantity':1}]},expected=201)
        second=self.request('GET','/api/orders?limit=1&q=race&cursor='+first['next_cursor']); self.assertEqual(len(second['items']),1)
        self.assertNotEqual(first['items'][0]['id'],second['items'][0]['id'])
        self.assertIsNone(second['next_cursor'])
        self.request('POST','/api/orders',{'client_ref':'Éclair','lines':[{'sku':'SAMPLE','quantity':1}]},expected=201)
        self.assertEqual(len(self.request('GET','/api/orders?q=%C3%A9CLAIR')['items']),1)
        self.request('GET','/api/orders?limit=1&q=wrong&cursor='+first['next_cursor'],expected=400)
        self.request('GET','/api/orders?status=invalid',expected=400)
        self.request('GET','/api/orders?limit=101',expected=400)
        self.request('GET','/api/audit?cursor=garbage',expected=400)
if __name__=='__main__': unittest.main()
