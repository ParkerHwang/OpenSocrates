from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import threading
import unittest
from urllib.parse import urlencode

from tests.support import RunningApp, key


class APITest(unittest.TestCase):
    def setUp(self):
        self.app = RunningApp()
        self.addCleanup(self.app.close)
        self.admin = self.app.login()
        self.operator = self.app.login('operator')
        self.viewer = self.app.login('viewer')
        self.south = self.app.login(tenant='south')

    def get(self, path, token=None, expected=200):
        status, result = self.app.request('GET', path, token=token or self.admin)
        self.assertEqual(status, expected, result)
        return result

    def post(self, path, data, token=None, expected=200, idem=None):
        status, result = self.app.request('POST', path, data, token=token or self.admin, key=idem or key())
        self.assertEqual(status, expected, result)
        if status >= 400:
            self.assertIsInstance(result['error']['message'], str)
            self.assertTrue(result['error']['code'])
        return result

    def create(self, ref='ORDER-1', lines=None, **options):
        return self.post('/api/orders', {'client_ref': ref, 'lines': lines if lines is not None else [{'sku': 'BOLT', 'quantity': 5}]}, expected=201, **options)

    def action(self, order, action, expected=200, **data):
        return self.post(f'/api/orders/{order["id"]}/{action}', {'expected_version': order['version'], **data}, expected=expected)

    def stock(self, token=None):
        return {item['sku']: item for item in self.get('/api/inventory', token)['items']}

    def snapshot(self):
        # Compare the entire persisted business state, including retry records.
        with sqlite3.connect(self.app.db_path) as db:
            return {table: db.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
                    for table in ('inventory','orders','order_lines','audit','order_states','idempotency')}

    def test_health_auth_and_all_demo_accounts(self):
        self.assertEqual(self.app.request('GET', '/api/health'), (200, {'status': 'ok'}))
        for tenant in ('north','south'):
            for role in ('admin','operator','viewer'):
                token = self.app.login(role, tenant)
                self.assertEqual(self.get('/api/me', token), {'email': f'{role}@{tenant}.example', 'role': role, 'tenant': tenant})
        for token in (None, 'fake-token'):
            self.assertEqual(self.app.request('GET', '/api/inventory', token=token)[0], 401)
        for credentials in ({'email': 'missing@example.com','password':'x'}, {'email':'admin@north.example','password':'wrong'}, {}):
            self.assertEqual(self.app.request('POST', '/api/session', credentials)[0], 401)
        self.assertIn('DepotFlow', self.app.request('GET', '/')[1])

    def test_seed_inventory_is_independent_and_integer(self):
        north, south = self.stock(), self.stock(self.south)
        self.assertEqual(north, south)
        for sku, qty, price in [('BOLT',100,1250),('CABLE',60,2499),('SAMPLE',20,0)]:
            item = north[sku]
            self.assertEqual((item['on_hand'],item['reserved'],item['available'],item['price_cents'],item['version']), (qty,0,qty,price,1))
            self.assertTrue(all(type(item[f]) is int for f in ('on_hand','reserved','available','price_cents','version')))

    def test_roles_isolation_and_untrusted_overrides(self):
        payload = {'client_ref':'PRIVATE','lines':[{'sku':'BOLT','quantity':2,'unit_price_cents':1}],
                   'tenant':'south','role':'admin','total_cents':0,'status':'shipped','version':99}
        order = self.post('/api/orders', payload, token=self.operator, expected=201)
        self.assertEqual((order['total_cents'],order['status'],order['version']), (2500,'draft',1))
        self.get(f'/api/orders/{order["id"]}', self.south, 404)
        for action in ('reserve','ship','cancel','returns'):
            self.post(f'/api/orders/{order["id"]}/{action}', {'expected_version':1,'lines':[{'sku':'BOLT','quantity':1}]}, token=self.south, expected=404)
            self.post(f'/api/orders/{order["id"]}/{action}', {'expected_version':1}, token=self.viewer, expected=403)
        self.post('/api/orders', payload, token=self.viewer, expected=403)
        self.post('/api/stock/adjustments', {'sku':'BOLT','delta':1,'expected_version':1,'reason':'receipt'}, token=self.operator, expected=403)
        self.post('/api/stock/adjustments', {}, token=self.viewer, expected=403)
        self.assertEqual(self.get('/api/orders', self.south)['items'], [])
        self.assertEqual(self.get('/api/audit', self.south)['items'], [])
        self.assertEqual(self.get('/api/dashboard', self.south)['inventory_units'], 180)
        status, me = self.app.request('GET','/api/me',token=self.viewer,headers={'X-Tenant':'south','X-Role':'admin'})
        self.assertEqual((status,me['tenant'],me['role']), (200,'north','viewer'))
        self.create('PRIVATE', token=self.south)  # Tenant-local uniqueness.

    def test_full_lifecycle_partial_and_complete_returns(self):
        order = self.create(lines=[{'sku':'BOLT','quantity':4},{'sku':'CABLE','quantity':3}])
        self.assertEqual(order['total_cents'], 4*1250+3*2499)
        order = self.action(order, 'reserve')
        self.assertEqual((order['status'],order['version']), ('reserved',2))
        before_ship = self.stock()
        self.assertEqual(before_ship['BOLT']['available'],96)
        order = self.action(order, 'ship')
        self.assertEqual((order['status'],order['version']), ('shipped',3))
        after_ship = self.stock()
        for sku in ('BOLT','CABLE'):
            self.assertEqual(before_ship[sku]['available'], after_ship[sku]['available'])
            self.assertEqual(after_ship[sku]['reserved'],0)
        order = self.action(order, 'returns', lines=[{'sku':'BOLT','quantity':1}])
        self.assertEqual((order['status'],order['version'],order['lines'][0]['returned_quantity']), ('shipped',4,1))
        self.assertEqual(self.stock()['BOLT']['on_hand'],97)
        order = self.action(order, 'returns', lines=[{'sku':'BOLT','quantity':3},{'sku':'CABLE','quantity':3}])
        self.assertEqual((order['status'],order['version']), ('returned',5))
        final = self.snapshot()
        self.action(order, 'returns', expected=409, lines=[{'sku':'BOLT','quantity':1}])
        self.action(order, 'cancel', expected=409)
        self.assertEqual(final,self.snapshot())
        self.assertEqual(self.stock()['BOLT']['on_hand'],100)
        self.assertEqual(self.get('/api/dashboard')['orders_by_status']['returned'],1)
        audit = self.get('/api/audit')['items']
        self.assertEqual([e['action'] for e in audit], ['order.created','order.reserved','order.shipped','order.returned','order.returned'])
        self.assertEqual(len({e['id'] for e in audit}),5)
        self.assertTrue(all(e['actor']=='admin@north.example' for e in audit))
        self.assertEqual(audit[1]['details']['stock'][0]['after']['reserved'],4)

    def test_zero_price_nonempty_order(self):
        order = self.create(lines=[{'sku':'SAMPLE','quantity':3}])
        self.assertEqual(order['total_cents'],0)
        self.assertEqual(order['lines'][0]['unit_price_cents'],0)
        order = self.action(order,'reserve')
        order = self.action(order,'ship')
        self.assertEqual(order['status'],'shipped')
        self.assertEqual(self.stock()['SAMPLE']['on_hand'],17)

    def test_create_validation_no_effects(self):
        before = self.snapshot()
        bad_lines = [[], None, {}, [False], [{'sku':'UNKNOWN','quantity':1}],
                     [{'sku':'BOLT','quantity':1},{'sku':'BOLT','quantity':2}]]
        for quantity in (True,False,0,-1,1.5,1.0,'2',None,10**100):
            bad_lines.append([{'sku':'BOLT','quantity':quantity}])
        for rows in bad_lines:
            self.post('/api/orders', {'client_ref':'INVALID','lines':rows}, expected=400)
        for ref in ('','   ',True,123,None,'a'*161):
            self.post('/api/orders', {'client_ref':ref,'lines':[{'sku':'BOLT','quantity':1}]}, expected=400)
        self.assertEqual(before,self.snapshot())

    def test_reference_conflict_and_catalog_snapshot(self):
        order = self.create()
        before = self.snapshot()
        self.post('/api/orders', {'client_ref':'ORDER-1','lines':[{'sku':'BOLT','quantity':6}]}, expected=409)
        self.assertEqual(before,self.snapshot())
        with sqlite3.connect(self.app.db_path) as db:
            db.execute("UPDATE inventory SET price_cents=999 WHERE tenant='north' AND sku='BOLT'")
        old = self.get(f'/api/orders/{order["id"]}')
        self.assertEqual(old['lines'][0]['unit_price_cents'],1250)
        self.assertEqual(self.create('NEW')['lines'][0]['unit_price_cents'],999)

    def test_adjustment_validation_and_reserved_floor(self):
        order = self.action(self.create(lines=[{'sku':'BOLT','quantity':90}]), 'reserve')
        before = self.snapshot()
        self.post('/api/stock/adjustments', {'sku':'BOLT','delta':-11,'expected_version':2,'reason':'count'}, expected=409)
        for change in ({'delta':0},{'delta':True},{'delta':1.1},{'expected_version':True},{'reason':' '},{'sku':'NOPE'}):
            self.post('/api/stock/adjustments', {'sku':'BOLT','delta':1,'expected_version':2,'reason':'count',**change}, expected=400)
        self.post('/api/stock/adjustments', {'sku':'BOLT','delta':1,'expected_version':1,'reason':'count'}, expected=409)
        self.assertEqual(before,self.snapshot())
        item = self.post('/api/stock/adjustments', {'sku':'BOLT','delta':-10,'expected_version':2,'reason':'count correction'})
        self.assertEqual((item['on_hand'],item['reserved'],item['available'],item['version']),(90,90,0,3))
        item = self.post('/api/stock/adjustments', {'sku':'BOLT','delta':12,'expected_version':3,'reason':'receipt'})
        self.assertEqual(item['on_hand'],102)
        self.assertEqual(self.stock(self.south)['BOLT']['on_hand'],100)
        self.assertEqual(self.get('/api/audit')['items'][-1]['details']['reason'],'receipt')

    def test_atomic_multiline_reservation_failure_and_retry(self):
        order = self.create(lines=[{'sku':'BOLT','quantity':1},{'sku':'CABLE','quantity':61}])
        before = self.snapshot(); idem = key()
        path = f'/api/orders/{order["id"]}/reserve'
        self.post(path, {'expected_version':1}, idem=idem, expected=409)
        self.assertEqual(before,self.snapshot())
        self.post('/api/stock/adjustments', {'sku':'CABLE','delta':1,'expected_version':1,'reason':'receipt'})
        self.post(path, {'expected_version':1}, idem=idem)
        self.assertEqual(self.stock()['CABLE']['available'],0)

    def test_cancel_draft_and_reserved(self):
        draft = self.create('DRAFT')
        initial = self.stock()
        cancelled = self.action(draft,'cancel')
        self.assertEqual(self.stock(),initial)
        self.assertEqual((cancelled['status'],cancelled['version']),('cancelled',2))
        reserved = self.action(self.create('RESERVED'),'reserve')
        self.assertEqual(self.stock()['BOLT']['reserved'],5)
        self.action(reserved,'cancel')
        self.assertEqual(self.stock()['BOLT']['reserved'],0)
        self.assertEqual(self.stock()['BOLT']['on_hand'],100)

    def test_invalid_transitions_and_stale_versions_are_atomic(self):
        order = self.create()
        before = self.snapshot()
        self.action(order,'ship',expected=409)
        self.action(order,'returns',expected=409,lines=[{'sku':'BOLT','quantity':1}])
        for value in (True,False,1.0,1.2,0,None,'1'):
            self.action(order,'reserve',expected=400,expected_version=value)
        self.assertEqual(before,self.snapshot())
        reserved = self.action(order,'reserve'); before = self.snapshot()
        self.action(order,'ship',expected=409)
        self.action(reserved,'reserve',expected=409)
        self.assertEqual(before,self.snapshot())
        shipped = self.action(reserved,'ship'); before = self.snapshot()
        self.action(shipped,'cancel',expected=409)
        self.action(shipped,'ship',expected=409)
        self.assertEqual(before,self.snapshot())

    def test_invalid_and_excess_multiline_returns_are_atomic(self):
        order = self.action(self.action(self.create(lines=[{'sku':'BOLT','quantity':2},{'sku':'CABLE','quantity':2}]),'reserve'),'ship')
        before = self.snapshot()
        for rows in ([], [{'sku':'SAMPLE','quantity':1}], [{'sku':'BOLT','quantity':True}],
                     [{'sku':'BOLT','quantity':0}], [{'sku':'BOLT','quantity':1.5}],
                     [{'sku':'BOLT','quantity':1},{'sku':'BOLT','quantity':1}]):
            self.action(order,'returns',expected=400,lines=rows)
        self.action(order,'returns',expected=409,lines=[{'sku':'BOLT','quantity':1},{'sku':'CABLE','quantity':3}])
        self.assertEqual(before,self.snapshot())
        order = self.action(order,'returns',lines=[{'sku':'BOLT','quantity':1}]); before = self.snapshot()
        self.action(order,'returns',expected=409,lines=[{'sku':'BOLT','quantity':2}])
        self.assertEqual(before,self.snapshot())

    def test_idempotency_replay_conflict_authorization_and_failed_keys(self):
        payload = {'client_ref':'RETRY','lines':[{'sku':'BOLT','quantity':2}]}; idem = key()
        self.assertEqual(self.app.request('POST','/api/orders',payload,token=self.admin)[0],400)
        self.assertEqual(self.app.request('POST','/api/orders',payload,token=self.admin,key='  ')[0],400)
        order = self.post('/api/orders', payload, expected=201, idem=idem); before = self.snapshot()
        replay = self.post('/api/orders', dict(reversed(list(payload.items()))), expected=201, idem=idem)
        self.assertEqual(replay,order)
        self.post('/api/orders', {**payload,'extra':'changed'}, expected=409, idem=idem)
        self.post('/api/stock/adjustments', payload, expected=409, idem=idem)
        self.post('/api/orders', payload, token=self.viewer, expected=403, idem=idem)
        self.assertEqual(self.app.request('POST','/api/orders',payload,key=idem)[0],401)
        self.assertEqual(before,self.snapshot())
        self.post('/api/orders', payload, token=self.south, expected=201, idem=idem)
        retry = key()
        self.post('/api/orders', {'client_ref':'FIX','lines':[]}, expected=400, idem=retry)
        self.post('/api/orders', {'client_ref':'FIX','lines':[{'sku':'SAMPLE','quantity':1}]}, expected=201, idem=retry)

    def test_transition_and_adjustment_replay_original_body(self):
        order = self.create(); idem = key(); path = f'/api/orders/{order["id"]}/reserve'
        reserved = self.post(path, {'expected_version':1}, idem=idem)
        shipped = self.action(reserved, 'ship'); before = self.snapshot()
        self.assertEqual(self.post(path, {'expected_version':1}, idem=idem),reserved)
        self.assertEqual(before,self.snapshot())
        payload = {'sku':'BOLT','delta':4,'expected_version':3,'reason':'count'}; idem = key()
        result = self.post('/api/stock/adjustments',payload,idem=idem); before=self.snapshot()
        self.assertEqual(self.post('/api/stock/adjustments',payload,idem=idem),result)
        self.post('/api/stock/adjustments',payload,token=self.operator,expected=403,idem=idem)
        self.assertEqual(before,self.snapshot())

    def parallel(self, count, callback):
        barrier = threading.Barrier(count)
        def worker(i):
            barrier.wait(timeout=10)
            return callback(i)
        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(worker,range(count)))

    def test_concurrent_identical_create_and_adjustment_commit_once(self):
        idem = key(); payload = {'client_ref':'SIMULTANEOUS','lines':[{'sku':'BOLT','quantity':1}]}
        results = self.parallel(16, lambda _: self.app.request('POST','/api/orders',payload,token=self.admin,key=idem))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(results[0][0],201)
        self.assertEqual(len(self.get('/api/audit')['items']),1)
        idem = key(); payload = {'sku':'BOLT','delta':2,'expected_version':1,'reason':'receipt'}
        results = self.parallel(16, lambda _: self.app.request('POST','/api/stock/adjustments',payload,token=self.admin,key=idem))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(results[0][0],200)
        self.assertEqual(self.stock()['BOLT']['on_hand'],102)
        self.assertEqual(len(self.get('/api/audit')['items']),2)

    def test_concurrent_reservations_never_oversell(self):
        orders = [self.create(f'RACE-{i}',lines=[{'sku':'BOLT','quantity':60},{'sku':'CABLE','quantity':30}]) for i in range(2)]
        results = self.parallel(2, lambda i: self.app.request('POST',f'/api/orders/{orders[i]["id"]}/reserve',
                                 {'expected_version':1},token=self.admin,key=key()))
        self.assertEqual(sorted(r[0] for r in results),[200,409])
        stock = self.stock()
        self.assertEqual((stock['BOLT']['reserved'],stock['CABLE']['reserved']),(60,30))
        self.assertEqual(len(self.get('/api/audit')['items']),3)
        states = [self.get(f'/api/orders/{o["id"]}') for o in orders]
        self.assertEqual(sorted((o['status'],o['version']) for o in states),[('draft',1),('reserved',2)])

    def test_concurrent_conflicting_payloads_and_versions(self):
        idem = key()
        results = self.parallel(8, lambda i: self.app.request('POST','/api/orders',
            {'client_ref':f'KEY-{i}','lines':[{'sku':'SAMPLE','quantity':1}]},token=self.admin,key=idem))
        self.assertEqual([r[0] for r in results].count(201),1)
        self.assertEqual([r[0] for r in results].count(409),7)
        order = self.create()
        results = self.parallel(8, lambda _: self.app.request('POST',f'/api/orders/{order["id"]}/reserve',
            {'expected_version':1},token=self.admin,key=key()))
        self.assertEqual([r[0] for r in results].count(200),1)
        self.assertEqual([r[0] for r in results].count(409),7)
        self.assertEqual(self.stock()['BOLT']['reserved'],5)

    def test_concurrent_identical_transitions_and_returns_commit_once(self):
        order=self.create()
        for action, version in [('reserve',1),('ship',2),('returns',3)]:
            idem=key(); payload={'expected_version':version}
            if action=='returns': payload['lines']=[{'sku':'BOLT','quantity':5}]
            results=self.parallel(12,lambda _: self.app.request('POST',f'/api/orders/{order["id"]}/{action}',
                                 payload,token=self.admin,key=idem))
            self.assertTrue(all(result==results[0] for result in results))
            self.assertEqual(results[0][0],200)
            self.assertEqual(results[0][1]['version'],version+1)
        self.assertEqual(self.stock()['BOLT']['on_hand'],100)
        self.assertEqual(self.stock()['BOLT']['reserved'],0)
        self.assertEqual(len(self.get('/api/audit')['items']),4)

    def test_database_failure_rolls_back_stock_order_audit_and_retry_record(self):
        order=self.create(); before=self.snapshot(); idem=key()
        # Inject a storage-layer failure after inventory/order writes but before commit.
        with sqlite3.connect(self.app.db_path) as db:
            db.execute("CREATE TRIGGER injected_failure BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        self.post(f'/api/orders/{order["id"]}/reserve',{'expected_version':1},expected=500,idem=idem)
        self.assertEqual(before,self.snapshot())
        with sqlite3.connect(self.app.db_path) as db:
            db.execute('DROP TRIGGER injected_failure')
        self.post(f'/api/orders/{order["id"]}/reserve',{'expected_version':1},idem=idem)
        self.assertEqual(self.stock()['BOLT']['reserved'],5)

    def test_order_pagination_stable_under_inserts_and_status_changes(self):
        orders = [self.create(f'Match-{i}') for i in range(7)]
        self.create('Unrelated')
        query = {'limit':2,'status':'draft','q':'mAtCH-'}
        page = self.get('/api/orders?'+urlencode(query)); collected = page['items'][:]
        self.create('Match-new')
        self.action(orders[4], 'cancel')
        while page['next_cursor']:
            page = self.get('/api/orders?'+urlencode({**query,'cursor':page['next_cursor']}))
            collected += page['items']
        self.assertEqual([o['id'] for o in collected],[o['id'] for o in orders])
        self.assertEqual(collected[4]['status'],'cancelled')  # Original membership, current detail.
        self.assertEqual(self.get('/api/orders?q=NOT-FOUND')['items'],[])

    def test_unicode_and_literal_substring_search(self):
        self.create('Straße_100%')
        self.create('Other')
        for q in ('STRASSE','_100%','%'):
            self.assertEqual(len(self.get('/api/orders?'+urlencode({'q':q}))['items']),1)
        self.assertEqual(self.get('/api/orders?q=%27%20OR%201%3D1--')['items'],[])

    def test_invalid_filters_cursors_and_cross_tenant_cursor(self):
        for i in range(3): self.create(str(i))
        for query in ('limit=0','limit=101','limit=true','limit=1.5','limit=','limit=-1','status=unknown','status=',
                      'cursor=','cursor=junk','limit=1&limit=2','unexpected=1','q='+'x'*161):
            self.get('/api/orders?'+query,expected=400)
        page = self.get('/api/orders?limit=1'); cursor = page['next_cursor']
        self.get('/api/orders?'+urlencode({'cursor':cursor}),self.south,400)
        self.get('/api/orders?'+urlencode({'cursor':cursor,'q':'changed'}),expected=400)
        self.get('/api/audit?'+urlencode({'cursor':cursor}),expected=400)
        self.get('/api/orders?'+urlencode({'cursor':cursor[:-1]+'z'}),expected=400)
        self.get('/api/audit?limit=101',expected=400)
        self.get('/api/audit?status=draft',expected=400)

    def test_audit_pagination_dashboard_and_actor(self):
        for i in range(5): self.create(f'AUDIT-{i}',token=self.operator)
        page = self.get('/api/audit?limit=2'); events = page['items'][:]
        self.create('LATER')
        while page['next_cursor']:
            page = self.get('/api/audit?'+urlencode({'limit':2,'cursor':page['next_cursor']})); events += page['items']
        self.assertEqual(len(events),5)
        self.assertTrue(all(e['actor']=='operator@north.example' for e in events))
        self.assertEqual([e['id'] for e in events],sorted(set(e['id'] for e in events)))
        dashboard = self.get('/api/dashboard')
        self.assertEqual(dashboard['orders_by_status']['draft'],6)
        self.assertEqual((dashboard['inventory_units'],dashboard['reserved_units']),(180,0))

    def test_malformed_json_and_invalid_methods(self):
        before=self.snapshot()
        for raw in ('[]','null','true','{','{"client_ref":"a","client_ref":"b"}',
                    '{"x":NaN}','{"x":Infinity}','{"x":1e999}','{"x":"\\ud800"}'):
            status, body = self.app.request('POST','/api/orders',token=self.admin,key=key(),raw=raw)
            self.assertEqual(status,400,body)
        self.assertEqual(self.app.request('POST','/api/orders',{},token=self.admin,key=key(),headers={'Content-Type':'text/plain'})[0],400)
        self.assertEqual(self.app.request('POST','/api/orders?ignored=1',{},token=self.admin,key=key())[0],400)
        self.assertEqual(self.app.request('PUT','/api/orders',{},token=self.admin,key=key())[0],405)
        self.get('/api/missing',expected=404)
        self.assertEqual(before,self.snapshot())

    def test_restart_preserves_stock_sessions_audit_cursors_and_replays(self):
        payload={'client_ref':'DURABLE','lines':[{'sku':'BOLT','quantity':10}]}; idem=key()
        original = self.post('/api/orders',payload,expected=201,idem=idem)
        shipped = self.action(self.action(original,'reserve'),'ship')
        order = self.action(shipped,'returns',lines=[{'sku':'BOLT','quantity':3}])
        self.create('NEXT')
        cursor = self.get('/api/orders?limit=1')['next_cursor']
        before = self.snapshot()
        self.app.restart(hard=True)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.stock()['BOLT']['on_hand'],93)
        self.assertEqual(self.get(f'/api/orders/{order["id"]}'),order)
        self.assertEqual(self.post('/api/orders',payload,expected=201,idem=idem),original)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.get('/api/orders?'+urlencode({'cursor':cursor}))['items'][0]['client_ref'],'NEXT')
        with sqlite3.connect(self.app.db_path) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])


class EmptyStoreTest(unittest.TestCase):
    def test_seed_disabled_and_then_only_once(self):
        app=RunningApp(seed=False)
        self.addCleanup(app.close)
        self.assertEqual(app.request('GET','/api/health')[0],200)
        self.assertEqual(app.request('POST','/api/session',{'email':'admin@north.example','password':'DepotDemo!2026'})[0],401)
        app.seed=True; app.restart()
        token=app.login()
        payload={'sku':'SAMPLE','delta':-20,'expected_version':1,'reason':'empty shelf'}
        self.assertEqual(app.request('POST','/api/stock/adjustments',payload,token=token,key=key())[0],200)
        app.restart()
        items=app.request('GET','/api/inventory',token=token)[1]['items']
        self.assertEqual(next(i for i in items if i['sku']=='SAMPLE')['on_hand'],0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
