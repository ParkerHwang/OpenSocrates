import concurrent.futures
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class DepotFlowRoutes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.port = free_port()
        self.base = f'http://127.0.0.1:{self.port}'
        self.seq = 0
        self.start()
        self.north_admin = self.login('admin@north.example')
        self.north_operator = self.login('operator@north.example')
        self.north_viewer = self.login('viewer@north.example')
        self.south_admin = self.login('admin@south.example')

    def tearDown(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.temp.cleanup()

    def start(self):
        env = os.environ.copy()
        env.update(PORT=str(self.port), DATA_DIR=self.temp.name, SEED_DEMO='1')
        self.process = subprocess.Popen([str(ROOT/'run.sh')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if self.call('GET','/api/health')[0] == 200: return
            except Exception: pass
            time.sleep(.05)
        self.fail('server did not start')

    def call(self, method, path, body=None, token=None, key=None, headers=None):
        hdr = dict(headers or {})
        if token: hdr['Authorization'] = 'Bearer ' + token
        if body is not None:
            hdr['Content-Type'] = 'application/json'
            if key is None:
                self.seq += 1
                key = f'test-{self.seq}'
            if key is not False: hdr['Idempotency-Key'] = key
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base+path,data=data,headers=hdr,method=method)
        try:
            with urlopen(req,timeout=20) as response:
                return response.status,json.load(response)
        except HTTPError as exc:
            return exc.code,json.load(exc)

    def login(self,email):
        status, data = self.call('POST','/api/session',{'email':email,'password':'DepotDemo!2026'})
        self.assertEqual(status,200)
        return data['token']

    def post(self,path,body,token=None,key=None):
        return self.call('POST',path,body,token or self.north_operator,key)

    def inventory(self,token=None):
        return {i['sku']:i for i in self.call('GET','/api/inventory',token=token or self.north_operator)[1]['items']}

    def test_workflow_atomicity_roles_replay_restart(self):
        self.assertEqual(self.call('GET','/api/me')[0],401)
        self.assertEqual(self.call('GET','/api/me',token='wrong')[0],401)
        self.assertEqual(self.call('POST','/api/session',{'email':'admin@north.example','password':'wrong'})[0],401)
        self.assertEqual(self.call('GET','/api/me',token=self.north_viewer)[1]['role'],'viewer')
        self.assertEqual(self.post('/api/orders',{'client_ref':'forbidden','lines':[{'sku':'BOLT','quantity':1}]},self.north_viewer)[0],403)
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'BOLT','delta':1,'expected_version':1,'reason':'test'})[0],403)
        self.assertEqual(self.post('/api/orders',{'client_ref':'missing','lines':[{'sku':'BOLT','quantity':1}]},key=False)[0],400)
        self.assertEqual(self.call('GET','/api/audit',token=self.north_operator)[1]['items'],[])
        self.assertEqual(self.inventory()['BOLT']['on_hand'],100)

        status, item = self.post('/api/stock/adjustments',{'sku':'BOLT','delta':5,'expected_version':1,'reason':'counted'},self.north_admin,key='adjust')
        self.assertEqual((status,item['on_hand'],item['version']),(200,105,2))
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'BOLT','delta':5,'expected_version':1,'reason':'counted'},self.north_admin,key='adjust'),(status,item))
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'BOLT','delta':6,'expected_version':1,'reason':'counted'},self.north_admin,key='adjust')[0],409)
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'BOLT','delta':1.5,'expected_version':2,'reason':'bad'},self.north_admin)[0],400)
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'BOLT','delta':True,'expected_version':2,'reason':'bad'},self.north_admin)[0],400)

        payload={'client_ref':'sample-free','lines':[{'sku':'SAMPLE','quantity':2,'unit_price_cents':999}], 'tenant':'south','total_cents':999}
        status, sample = self.post('/api/orders',payload,key='create-sample')
        self.assertEqual((status,sample['total_cents'],sample['version'],sample['status']),(201,0,1,'draft'))
        self.assertEqual(self.post('/api/orders',payload,key='create-sample'),(status,sample))
        self.assertEqual(self.post('/api/orders',payload,key='other-key')[0],409)
        self.assertEqual(self.call('GET',f'/api/orders/{sample["id"]}',token=self.south_admin)[0],404)
        self.assertEqual(self.call('GET','/api/orders',token=self.south_admin)[1]['items'],[])
        self.assertEqual(self.inventory(self.south_admin)['BOLT']['on_hand'],100)
        self.assertEqual(self.post('/api/orders',{'client_ref':'bad','lines':[{'sku':'BOLT','quantity':1},{'sku':'BOLT','quantity':2}]})[0],400)
        self.assertEqual(self.post('/api/orders',{'client_ref':'bad','lines':[{'sku':'NOPE','quantity':1}]})[0],400)
        self.assertEqual(self.post('/api/orders',{'client_ref':'bad','lines':[]})[0],400)
        self.assertEqual(self.post('/api/orders',{'client_ref':'bad','lines':[{'sku':'BOLT','quantity':False}]})[0],400)

        status, multi = self.post('/api/orders',{'client_ref':'multi','lines':[{'sku':'BOLT','quantity':10},{'sku':'CABLE','quantity':61}]})
        self.assertEqual(status,201)
        before = self.inventory()
        audit_before = len(self.call('GET','/api/audit',token=self.north_operator)[1]['items'])
        self.assertEqual(self.post(f'/api/orders/{multi["id"]}/reserve',{'expected_version':1})[0],409)
        self.assertEqual(self.inventory(),before)
        self.assertEqual(len(self.call('GET','/api/audit',token=self.north_operator)[1]['items']),audit_before)

        status, reserved = self.post(f'/api/orders/{sample["id"]}/reserve',{'expected_version':1},key='reserve-sample')
        self.assertEqual((status,reserved['status'],reserved['version']),(200,'reserved',2))
        self.assertEqual(self.inventory()['SAMPLE']['reserved'],2)
        self.assertEqual(self.post(f'/api/orders/{sample["id"]}/reserve',{'expected_version':1},key='reserve-sample'),(status,reserved))
        self.assertEqual(self.post(f'/api/orders/{sample["id"]}/ship',{'expected_version':1})[0],409)
        status, shipped = self.post(f'/api/orders/{sample["id"]}/ship',{'expected_version':2})
        self.assertEqual((status,shipped['status'],shipped['version']),(200,'shipped',3))
        self.assertEqual(self.inventory()['SAMPLE']['on_hand'],18)
        self.assertEqual(self.inventory()['SAMPLE']['reserved'],0)
        self.assertEqual(self.post(f'/api/orders/{sample["id"]}/cancel',{'expected_version':3})[0],409)
        self.assertEqual(self.post(f'/api/orders/{sample["id"]}/returns',{'expected_version':3,'lines':[{'sku':'SAMPLE','quantity':3}]})[0],409)
        status, partial = self.post(f'/api/orders/{sample["id"]}/returns',{'expected_version':3,'lines':[{'sku':'SAMPLE','quantity':1}]})
        self.assertEqual((status,partial['status'],partial['version'],partial['lines'][0]['returned_quantity']),(200,'shipped',4,1))
        status, full = self.post(f'/api/orders/{sample["id"]}/returns',{'expected_version':4,'lines':[{'sku':'SAMPLE','quantity':1}]})
        self.assertEqual((status,full['status'],full['version']),(200,'returned',5))
        self.assertEqual(self.inventory()['SAMPLE']['on_hand'],20)
        self.assertEqual(self.post(f'/api/orders/{sample["id"]}/returns',{'expected_version':5,'lines':[{'sku':'SAMPLE','quantity':1}]})[0],409)
        self.assertEqual(self.call('GET','/api/dashboard',token=self.north_operator)[1]['orders_by_status']['returned'],1)

        self.process.terminate(); self.process.wait(timeout=5); self.start()
        self.assertEqual(self.inventory()['BOLT']['on_hand'],105)
        self.assertEqual(self.inventory()['SAMPLE']['on_hand'],20)
        self.assertEqual(self.post('/api/orders',payload,key='create-sample'),(201,sample))
        self.assertEqual(self.call('GET',f'/api/orders/{sample["id"]}',token=self.north_operator)[1],full)
        actions = [a['action'] for a in self.call('GET','/api/audit',token=self.north_operator)[1]['items']]
        self.assertEqual(actions.count('order.created'),2)
        self.assertEqual(actions.count('stock.adjusted'),1)
        self.assertEqual(actions.count('order.reserve'),1)
        self.assertEqual(actions.count('order.ship'),1)
        self.assertEqual(actions.count('order.returned'),2)

    def test_concurrency_and_pagination(self):
        orders=[]
        for i in range(5):
            status,o=self.post('/api/orders',{'client_ref':f'race-{i}','lines':[{'sku':'BOLT','quantity':30}]})
            self.assertEqual(status,201); orders.append(o)
        def reserve(o):
            return self.post(f'/api/orders/{o["id"]}/reserve',{'expected_version':1},key=f'race-key-{o["id"]}')
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(reserve,orders))
        self.assertEqual(sum(status==200 for status,_ in results),3)
        self.assertEqual(sum(status==409 for status,_ in results),2)
        self.assertEqual(self.inventory()['BOLT']['reserved'],90)
        self.assertEqual(self.call('GET','/api/dashboard',token=self.north_operator)[1]['reserved_units'],90)
        target=next(o for o,(status,_) in zip(orders,results) if status==200)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            same=list(pool.map(lambda _:self.post(f'/api/orders/{target["id"]}/cancel',{'expected_version':2},key='same-cancel'),range(2)))
        self.assertEqual(same[0],same[1])
        self.assertEqual(same[0][0],200)
        self.assertEqual(self.inventory()['BOLT']['reserved'],60)
        self.assertEqual(self.call('GET',f'/api/orders/{target["id"]}',token=self.north_operator)[1]['version'],3)
        refs=[]; cursor=None
        while True:
            path='/api/orders?status=reserved&q=RACE&limit=1'+('&cursor='+cursor if cursor else '')
            status,page=self.call('GET',path,token=self.north_operator)
            self.assertEqual(status,200)
            refs += [o['client_ref'] for o in page['items']]
            cursor=page['next_cursor']
            if not cursor: break
        self.assertEqual(len(refs),2)
        self.assertEqual(len(set(refs)),2)
        self.assertEqual(self.call('GET','/api/orders?limit=0',token=self.north_operator)[0],400)
        self.assertEqual(self.call('GET','/api/orders?status=unknown',token=self.north_operator)[0],400)
        self.assertEqual(self.call('GET','/api/orders?cursor=nope',token=self.north_operator)[0],400)
        self.assertEqual(self.call('GET','/api/audit?limit=101',token=self.north_operator)[0],400)

    def test_failed_key_release_and_cursor_snapshot(self):
        _, first = self.post('/api/orders',{'client_ref':'page-1','lines':[{'sku':'CABLE','quantity':50}]})
        _, second = self.post('/api/orders',{'client_ref':'page-2','lines':[{'sku':'CABLE','quantity':20}]})
        status, page = self.call('GET','/api/orders?limit=1',token=self.north_operator)
        self.assertEqual(status,200)
        self.assertEqual([o['id'] for o in page['items']],[first['id']])
        cursor=page['next_cursor']
        self.assertIsNotNone(cursor)
        self.post('/api/orders',{'client_ref':'page-3','lines':[{'sku':'SAMPLE','quantity':1}]})
        status, next_page=self.call('GET','/api/orders?limit=1&cursor='+cursor,token=self.north_operator)
        self.assertEqual(status,200)
        self.assertEqual([o['id'] for o in next_page['items']],[second['id']])
        self.assertIsNone(next_page['next_cursor'])
        self.assertEqual(self.call('GET','/api/orders?status=draft&limit=1&cursor='+cursor,token=self.north_operator)[0],400)

        _, reserved=self.post(f'/api/orders/{first["id"]}/reserve',{'expected_version':1})
        self.assertEqual(reserved['status'],'reserved')
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'CABLE','delta':-11,'expected_version':2,'reason':'too low'},self.north_admin)[0],409)
        self.assertEqual(self.post('/api/stock/adjustments',{'sku':'CABLE','delta':-11,'expected_version':1,'reason':'too low'},self.north_admin)[0],409)
        self.assertEqual(self.inventory()['CABLE']['on_hand'],60)
        failed_key='failed-reserve'
        self.assertEqual(self.post(f'/api/orders/{second["id"]}/reserve',{'expected_version':1},key=failed_key)[0],409)
        _,cancelled=self.post(f'/api/orders/{first["id"]}/cancel',{'expected_version':2})
        self.assertEqual(cancelled['status'],'cancelled')
        self.assertEqual(self.inventory()['CABLE']['reserved'],0)
        status,reserved=self.post(f'/api/orders/{second["id"]}/reserve',{'expected_version':1},key=failed_key)
        self.assertEqual((status,reserved['status']),(200,'reserved'))
        self.assertEqual(self.inventory()['CABLE']['reserved'],20)
        self.assertEqual(self.post('/api/orders',{'client_ref':'different','lines':[{'sku':'SAMPLE','quantity':1}]},key=failed_key)[0],409)
        # The same key is independent in the other tenant.
        self.assertEqual(self.post('/api/orders',{'client_ref':'south-key','lines':[{'sku':'SAMPLE','quantity':1}]},self.south_admin,key=failed_key)[0],201)
        audit=self.call('GET','/api/audit?limit=2',token=self.north_operator)[1]
        self.assertEqual(len(audit['items']),2)
        self.assertIsNotNone(audit['next_cursor'])
        next_audit=self.call('GET','/api/audit?limit=2&cursor='+audit['next_cursor'],token=self.north_operator)[1]
        self.assertFalse(set(a['id'] for a in audit['items']) & set(a['id'] for a in next_audit['items']))

    def test_identical_concurrent_create_is_one_operation(self):
        body={'client_ref':'parallel-create','lines':[{'sku':'BOLT','quantity':1}]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:self.post('/api/orders',body,key='parallel-create-key'),range(2)))
        self.assertEqual(responses[0],responses[1])
        self.assertEqual(responses[0][0],201)
        listed=self.call('GET','/api/orders',token=self.north_operator)[1]['items']
        self.assertEqual(len(listed),1)
        self.assertEqual(listed[0]['id'],responses[0][1]['id'])
        events=self.call('GET','/api/audit',token=self.north_operator)[1]['items']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['action'],'order.created')


if __name__ == '__main__': unittest.main()
