import concurrent.futures
import json
import sqlite3
import threading
import unittest
from urllib.parse import urlencode

from .support import RunningServer, new_key


class APITests(unittest.TestCase):
    def setUp(self):
        self.server = RunningServer()
        self.addCleanup(self.server.close)
        self.operator = self.server.login()
        self.admin = self.server.login('admin')
        self.viewer = self.server.login('viewer')
        self.south = self.server.login('operator', 'south')

    def get(self, path, token=None, status=200):
        result, body = self.server.request('GET', path, token=token or self.operator)
        self.assertEqual(result, status, body)
        return body

    def post(self, path, payload, token=None, key=None, status=200):
        result, body = self.server.request('POST', path, payload, token or self.operator, key if key is not None else new_key())
        self.assertEqual(result, status, body)
        if status >= 400:
            self.assertIn('code', body['error'])
            self.assertTrue(body['error']['message'])
        return body

    def create(self, ref='order-1', lines=None, **kwargs):
        return self.post('/api/orders', {'client_ref': ref, 'lines': lines if lines is not None else [{'sku': 'BOLT', 'quantity': 3}]}, status=201, **kwargs)

    def transition(self, order, action, status=200, **kwargs):
        return self.post(f'/api/orders/{order["id"]}/{action}', {'expected_version': order['version'], **kwargs}, status=status)

    def inventory(self, token=None):
        return {row['sku']: row for row in self.get('/api/inventory', token)['items']}

    def snapshot(self):
        with sqlite3.connect(self.server.directory / 'depotflow.sqlite3') as conn:
            return {table: conn.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
                    for table in ('inventory', 'orders', 'order_lines', 'audit', 'idempotency')}

    def audit(self):
        return self.get('/api/audit?limit=100')['items']

    def test_health_login_seed_and_identity(self):
        self.assertEqual(self.server.request('GET', '/api/health'), (200, {'status': 'ok'}))
        for tenant in ('north', 'south'):
            for role in ('admin', 'operator', 'viewer'):
                token = self.server.login(role, tenant)
                self.assertEqual(self.get('/api/me', token), {'email': f'{role}@{tenant}.example', 'tenant': tenant, 'role': role})
        for token in (None, 'invalid'):
            for path in ('/api/me', '/api/inventory', '/api/orders', '/api/audit', '/api/dashboard'):
                self.assertEqual(self.server.request('GET', path, token=token)[0], 401)
        for payload in ({'email': 'operator@north.example', 'password': 'wrong'}, {'email': 'nobody@example.com', 'password': 'wrong'}, {}):
            self.assertEqual(self.server.request('POST', '/api/session', payload)[0], 401)
        self.assertEqual(self.inventory(), self.inventory(self.south))
        expected = {'BOLT': (100, 1250), 'CABLE': (60, 2499), 'SAMPLE': (20, 0)}
        for sku, item in self.inventory().items():
            self.assertEqual((item['on_hand'], item['price_cents']), expected[sku])
            self.assertEqual(item['reserved'], 0)
            self.assertEqual(item['available'], item['on_hand'])
            self.assertEqual(item['version'], 1)
            for name in ('on_hand', 'reserved', 'available', 'price_cents', 'version'):
                self.assertIs(type(item[name]), int)

    def test_fulfillment_partial_and_full_returns(self):
        created = self.create(lines=[{'sku': 'BOLT', 'quantity': 3}, {'sku': 'CABLE', 'quantity': 2}])
        self.assertEqual((created['status'], created['version'], created['total_cents']), ('draft', 1, 8748))
        reserved = self.transition(created, 'reserve')
        inv = self.inventory()
        self.assertEqual((inv['BOLT']['on_hand'], inv['BOLT']['reserved'], inv['BOLT']['available']), (100, 3, 97))
        shipped = self.transition(reserved, 'ship')
        inv = self.inventory()
        self.assertEqual((inv['BOLT']['on_hand'], inv['BOLT']['reserved'], inv['BOLT']['available']), (97, 0, 97))
        partial = self.transition(shipped, 'returns', lines=[{'sku': 'BOLT', 'quantity': 1}])
        self.assertEqual((partial['status'], partial['version']), ('shipped', 4))
        self.assertEqual(partial['lines'][0]['returned_quantity'], 1)
        before = self.snapshot()
        self.transition(partial, 'returns', status=409, lines=[{'sku': 'BOLT', 'quantity': 3}])
        self.assertEqual(before, self.snapshot())
        complete = self.transition(partial, 'returns', lines=[{'sku': 'BOLT', 'quantity': 2}, {'sku': 'CABLE', 'quantity': 2}])
        self.assertEqual((complete['status'], complete['version']), ('returned', 5))
        self.transition(complete, 'returns', status=409, lines=[{'sku': 'BOLT', 'quantity': 1}])
        self.assertEqual(self.inventory()['BOLT']['on_hand'], 100)
        self.assertEqual(self.inventory()['CABLE']['on_hand'], 60)
        self.assertEqual(len(self.audit()), 5)
        dashboard = self.get('/api/dashboard')
        self.assertEqual(dashboard['orders_by_status']['returned'], 1)
        self.assertEqual((dashboard['inventory_units'], dashboard['reserved_units']), (180, 0))

    def test_zero_price_order_and_untrusted_fields(self):
        data = self.post('/api/orders', {'client_ref': 'free', 'tenant': 'south', 'role': 'admin', 'total_cents': 500,
            'status': 'shipped', 'version': 99, 'lines': [{'sku': 'SAMPLE', 'quantity': 2, 'unit_price_cents': 50}]}, status=201)
        self.assertEqual((data['total_cents'], data['status'], data['version']), (0, 'draft', 1))
        self.assertEqual(data['lines'][0]['unit_price_cents'], 0)
        shipped = self.transition(self.transition(data, 'reserve'), 'ship')
        self.assertEqual(shipped['total_cents'], 0)
        self.get(f'/api/orders/{data["id"]}', token=self.south, status=404)
        self.assertEqual(self.inventory(self.south)['SAMPLE']['on_hand'], 20)

    def test_tenant_and_role_boundaries_including_replay(self):
        key = new_key()
        order = self.create(key=key)
        before = self.snapshot()
        paths = ['/api/orders', '/api/stock/adjustments'] + [f'/api/orders/{order["id"]}/{a}' for a in ('reserve', 'ship', 'cancel', 'returns')]
        for path in paths:
            self.post(path, {'client_ref': 'order-1', 'lines': [{'sku': 'BOLT', 'quantity': 3}], 'expected_version': 1}, token=self.viewer, key=key, status=403)
        self.post('/api/stock/adjustments', {'sku': 'BOLT', 'delta': 1, 'expected_version': 1, 'reason': 'test'}, status=403)
        for action in ('reserve', 'ship', 'cancel', 'returns'):
            self.post(f'/api/orders/{order["id"]}/{action}', {'expected_version': 1, 'lines': [{'sku': 'BOLT', 'quantity': 1}]}, token=self.south, status=404)
        self.get(f'/api/orders/{order["id"]}', token=self.south, status=404)
        status, identity = self.server.request('GET', '/api/me', token=self.viewer, headers={'X-Tenant': 'south', 'X-Role': 'admin'})
        self.assertEqual(status, 200)
        self.assertEqual(identity['role'], 'viewer')
        self.assertEqual(identity['tenant'], 'north')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.get('/api/orders', self.south)['items'], [])
        self.assertEqual(self.get('/api/audit', self.south)['items'], [])
        self.create(token=self.south, key=key)  # Tenant-local references AND keys.

    def test_order_validation_has_no_effect(self):
        cases = [None, [], [{'sku': 'MISSING', 'quantity': 1}], [{'sku': 'BOLT', 'quantity': 1}, {'sku': 'BOLT', 'quantity': 2}]]
        cases += [[{'sku': 'BOLT', 'quantity': v}] for v in (True, False, 1.0, 1.5, 0, -1, '2', None, 10**20)]
        cases += [[{}], ['BOLT'], [{'sku': True, 'quantity': 1}], [{'sku': '', 'quantity': 1}], [{}] * 101]
        before = self.snapshot()
        for lines in cases:
            with self.subTest(lines=lines):
                self.post('/api/orders', {'client_ref': 'bad', 'lines': lines}, status=400)
                self.assertEqual(before, self.snapshot())
        for ref in ('', '  ', True, 42, 'a' * 201):
            self.post('/api/orders', {'client_ref': ref, 'lines': [{'sku': 'BOLT', 'quantity': 1}]}, status=400)
        self.assertEqual(before, self.snapshot())

    def test_reference_uniqueness(self):
        self.create()
        before = self.snapshot()
        self.post('/api/orders', {'client_ref': 'order-1', 'lines': [{'sku': 'CABLE', 'quantity': 1}]}, status=409)
        self.assertEqual(before, self.snapshot())
        self.create(token=self.south)

    def test_stock_adjustments_version_and_reserved_floor(self):
        item = self.post('/api/stock/adjustments', {'sku': 'BOLT', 'delta': 10, 'expected_version': 1, 'reason': 'delivery'}, token=self.admin)
        self.assertEqual((item['on_hand'], item['version']), (110, 2))
        reserved = self.transition(self.create(lines=[{'sku': 'BOLT', 'quantity': 100}]), 'reserve')
        self.assertEqual(reserved['status'], 'reserved')
        before = self.snapshot()
        self.post('/api/stock/adjustments', {'sku': 'BOLT', 'delta': -11, 'expected_version': 3, 'reason': 'count'}, token=self.admin, status=409)
        self.post('/api/stock/adjustments', {'sku': 'BOLT', 'delta': 1, 'expected_version': 2, 'reason': 'stale'}, token=self.admin, status=409)
        self.assertEqual(before, self.snapshot())
        item = self.post('/api/stock/adjustments', {'sku': 'BOLT', 'delta': -10, 'expected_version': 3, 'reason': 'cycle count'}, token=self.admin)
        self.assertEqual((item['on_hand'], item['reserved'], item['available'], item['version']), (100, 100, 0, 4))
        self.assertEqual(self.audit()[-1]['details']['reason'], 'cycle count')

    def test_adjustment_validation(self):
        before = self.snapshot()
        valid = {'sku': 'BOLT', 'delta': 1, 'expected_version': 1, 'reason': 'test'}
        for field, values in {'delta': [0, True, 1.5, '1', None], 'expected_version': [True, 1.0, 0, -1, '1'], 'reason': ['', ' ', None, 1], 'sku': ['UNKNOWN', None]}.items():
            for value in values:
                self.post('/api/stock/adjustments', {**valid, field: value}, token=self.admin, status=400)
        self.assertEqual(before, self.snapshot())

    def test_atomic_multiline_reservation_failure_and_key_reuse(self):
        order = self.create(lines=[{'sku': 'BOLT', 'quantity': 5}, {'sku': 'CABLE', 'quantity': 61}])
        path = f'/api/orders/{order["id"]}/reserve'
        key = new_key()
        before = self.snapshot()
        self.post(path, {'expected_version': 1}, key=key, status=409)
        self.assertEqual(before, self.snapshot())
        self.post('/api/stock/adjustments', {'sku': 'CABLE', 'delta': 1, 'expected_version': 1, 'reason': 'restock'}, token=self.admin)
        self.post(path, {'expected_version': 1}, key=key)
        self.assertEqual(self.inventory()['BOLT']['reserved'], 5)

    def test_cancel_draft_reserved_and_invalid_transitions(self):
        draft = self.create()
        self.transition(draft, 'ship', status=409)
        self.transition(draft, 'returns', status=409, lines=[{'sku': 'BOLT', 'quantity': 1}])
        cancelled = self.transition(draft, 'cancel')
        self.assertEqual(cancelled['version'], 2)
        self.transition(cancelled, 'reserve', status=409)
        self.transition(cancelled, 'cancel', status=409)
        reserved = self.transition(self.create('order-2'), 'reserve')
        self.transition(reserved, 'reserve', status=409)
        self.transition(reserved, 'cancel')
        self.assertEqual(self.inventory()['BOLT']['reserved'], 0)
        shipped = self.transition(self.transition(self.create('order-3'), 'reserve'), 'ship')
        self.transition(shipped, 'cancel', status=409)
        self.transition(shipped, 'ship', status=409)

    def test_stale_versions_and_transition_validation(self):
        draft = self.create()
        reserved = self.transition(draft, 'reserve')
        before = self.snapshot()
        for action in ('ship', 'cancel', 'reserve'):
            self.transition(draft, action, status=409)
        for version in (True, False, 0, -1, 1.0, '2', None):
            self.post(f'/api/orders/{draft["id"]}/ship', {'expected_version': version}, status=400)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(reserved['version'], 2)

    def test_return_validation_and_atomic_failure(self):
        shipped = self.transition(self.transition(self.create(lines=[{'sku': 'BOLT', 'quantity': 2}, {'sku': 'CABLE', 'quantity': 1}]), 'reserve'), 'ship')
        before = self.snapshot()
        for lines in ([], [{'sku': 'SAMPLE', 'quantity': 1}], [{'sku': 'BOLT', 'quantity': 1}, {'sku': 'BOLT', 'quantity': 1}], [{'sku': 'BOLT', 'quantity': True}], [{'sku': 'BOLT', 'quantity': 1.5}], [{'sku': 'BOLT', 'quantity': 0}]):
            self.transition(shipped, 'returns', status=400, lines=lines)
        self.transition(shipped, 'returns', status=409, lines=[{'sku': 'BOLT', 'quantity': 1}, {'sku': 'CABLE', 'quantity': 2}])
        self.assertEqual(before, self.snapshot())

    def test_missing_keys_and_json_validation(self):
        before = self.snapshot()
        payload = {'client_ref': 'bad', 'lines': [{'sku': 'BOLT', 'quantity': 1}]}
        for key in (None, '', '   '):
            self.assertEqual(self.server.request('POST', '/api/orders', payload, self.operator, key)[0], 400)
        for token in (None, 'invalid'):
            self.assertEqual(self.server.request('POST', '/api/orders', payload, token, new_key())[0], 401)
            self.assertEqual(self.server.request('POST', '/api/orders', token=token, key=new_key(), raw=b'{')[0], 401)
        self.assertEqual(self.server.request('POST', '/api/orders', token=self.viewer, key=new_key(), raw=b'{')[0], 403)
        for raw in (b'[]', b'null', b'{', b'{"client_ref":"a","client_ref":"b"}', b'{"quantity":NaN}', b'{"client_ref":"\\ud800"}'):
            self.assertEqual(self.server.request('POST', '/api/orders', token=self.operator, key=new_key(), raw=raw)[0], 400)
        self.assertEqual(self.server.request('POST', '/api/orders', token=self.operator, key=new_key(), raw=b'x' * 65537)[0], 413)
        self.assertEqual(before, self.snapshot())

    def test_idempotency_success_canonical_payload_and_conflicts(self):
        key = new_key()
        order = self.create(key=key)
        before = self.snapshot()
        payload = {'lines': [{'quantity': 3, 'sku': 'BOLT'}], 'client_ref': 'order-1'}
        replay = self.post('/api/orders', payload, key=key, status=201)
        self.assertEqual(order, replay)
        self.post('/api/orders', {**payload, 'client_ref': 'changed'}, key=key, status=409)
        self.post(f'/api/orders/{order["id"]}/reserve', {'expected_version': 1}, key=key, status=409)
        self.assertEqual(before, self.snapshot())
        reserve_key = new_key()
        path = f'/api/orders/{order["id"]}/reserve'
        reserved = self.post(path, {'expected_version': 1}, key=reserve_key)
        self.transition(reserved, 'ship')
        before = self.snapshot()
        self.assertEqual(reserved, self.post(path, {'expected_version': 1}, key=reserve_key))
        self.assertEqual(before, self.snapshot())

    def test_idempotent_stock_replay_and_authorization(self):
        payload = {'sku': 'BOLT', 'delta': 1, 'expected_version': 1, 'reason': 'restock'}
        key = new_key()
        first = self.post('/api/stock/adjustments', payload, token=self.admin, key=key)
        self.assertEqual(first, self.post('/api/stock/adjustments', payload, token=self.admin, key=key))
        self.post('/api/stock/adjustments', payload, key=key, status=403)
        self.post('/api/stock/adjustments', payload, token=self.viewer, key=key, status=403)
        self.assertEqual(len(self.audit()), 1)

    def race(self, operations):
        barrier = threading.Barrier(len(operations))
        def run(op):
            barrier.wait(timeout=10)
            return op()
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def test_concurrent_reservations_never_oversell(self):
        orders = [self.create(f'race-{i}', [{'sku': 'BOLT', 'quantity': 70}, {'sku': 'CABLE', 'quantity': 20}]) for i in range(2)]
        operations = [lambda o=o: self.server.request('POST', f'/api/orders/{o["id"]}/reserve', {'expected_version': 1}, self.operator, new_key()) for o in orders]
        results = self.race(operations)
        self.assertEqual(sorted(r[0] for r in results), [200, 409])
        inv = self.inventory()
        self.assertEqual((inv['BOLT']['reserved'], inv['CABLE']['reserved']), (70, 20))
        self.assertEqual(len(self.audit()), 3)
        self.assertEqual(sorted(self.get(f'/api/orders/{o["id"]}')['version'] for o in orders), [1, 2])

    def test_concurrent_identical_create_and_transition(self):
        key = new_key()
        payload = {'client_ref': 'once', 'lines': [{'sku': 'BOLT', 'quantity': 2}]}
        results = self.race([lambda: self.server.request('POST', '/api/orders', payload, self.operator, key)] * 12)
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(results[0][0], 201)
        order = results[0][1]
        key = new_key()
        results = self.race([lambda: self.server.request('POST', f'/api/orders/{order["id"]}/reserve', {'expected_version': 1}, self.operator, key)] * 12)
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(results[0][0], 200)
        self.assertEqual(self.inventory()['BOLT']['reserved'], 2)
        self.assertEqual(len(self.audit()), 2)

    def test_concurrent_returns_with_distinct_keys(self):
        shipped = self.transition(self.transition(self.create(), 'reserve'), 'ship')
        payload = {'expected_version': 3, 'lines': [{'sku': 'BOLT', 'quantity': 2}]}
        results = self.race([lambda: self.server.request('POST', f'/api/orders/{shipped["id"]}/returns', payload, self.operator, new_key())] * 2)
        self.assertEqual(sorted(r[0] for r in results), [200, 409])
        self.assertEqual(self.inventory()['BOLT']['on_hand'], 99)
        self.assertEqual(len(self.audit()), 4)

    def test_filters_and_pagination_preserve_membership(self):
        orders = [self.create(f'Web-{i:02}') for i in range(7)]
        self.create('other')
        first = self.get('/api/orders?status=draft&q=wEB-&limit=2')
        seen = [item['id'] for item in first['items']]
        cursor = first['next_cursor']
        self.assertIsInstance(cursor, str)
        self.create('Web-new')  # New matches must not enter the in-progress traversal.
        self.transition(orders[3], 'cancel')  # A pre-existing match must not disappear.
        self.transition(orders[0], 'cancel')  # Removing earlier matches must not shift offsets.
        while cursor:
            page = self.get('/api/orders?' + urlencode({'status': 'draft', 'q': 'WEB-', 'limit': 2, 'cursor': cursor}))
            seen += [item['id'] for item in page['items']]
            cursor = page['next_cursor']
        self.assertEqual(seen, [item['id'] for item in orders])
        self.assertEqual(self.get('/api/orders?q=missing')['items'], [])
        self.assertEqual(len(self.get('/api/orders?status=cancelled')['items']), 2)
        self.get('/api/orders?' + urlencode({'cursor': first['next_cursor']}), status=400)
        self.get('/api/orders?' + urlencode({'status': 'draft', 'q': 'WEB-', 'cursor': first['next_cursor']}), token=self.south, status=400)
        self.get('/api/audit?' + urlencode({'cursor': first['next_cursor']}), status=400)

    def test_unicode_literal_search_and_default_limit(self):
        for i in range(22):
            self.create(f'Straße_100%_{i}')
        self.assertEqual(len(self.get('/api/orders')['items']), 20)
        self.assertIsInstance(self.get('/api/orders')['next_cursor'], str)
        self.assertEqual(len(self.get('/api/orders?' + urlencode({'q': 'STRASSE_100%', 'limit': 100}))['items']), 22)
        self.assertEqual(self.get('/api/orders?q=100X')['items'], [])

    def test_invalid_filters_and_cursors(self):
        for suffix in ('limit=0', 'limit=101', 'limit=true', 'limit=1.0', 'limit=-1', 'limit=',
                       'limit=1&limit=2', 'cursor=', 'cursor=garbage', 'unknown=x'):
            for path in ('/api/orders?', '/api/audit?'):
                self.get(path + suffix, status=400)
        for suffix in ('status=unknown', 'status=', 'status=draft&status=shipped', 'q=a&q=b', 'q=' + 'a' * 201):
            self.get('/api/orders?' + suffix, status=400)
        self.create('first')
        self.create('second')
        cursor = self.get('/api/orders?limit=1')['next_cursor']
        self.get('/api/orders?' + urlencode({'cursor': cursor[:-1] + ('a' if cursor[-1] != 'a' else 'b')}), status=400)

    def test_audit_pagination_and_actor_integrity(self):
        for i in range(5):
            self.create(f'audit-{i}')
        before = self.audit()
        page = self.get('/api/audit?limit=2')
        seen = page['items']
        self.create('new-event')
        while page['next_cursor']:
            page = self.get('/api/audit?' + urlencode({'limit': 2, 'cursor': page['next_cursor']}))
            seen += page['items']
        self.assertEqual(seen, before)
        for item in seen:
            self.assertEqual(item['actor'], 'operator@north.example')
            self.assertEqual(item['action'], 'order.created')
            self.assertTrue(item['created_at'].endswith('+00:00'))

    def test_database_failure_rolls_back_stock_order_audit_and_key(self):
        order = self.create()
        before = self.snapshot()
        with sqlite3.connect(self.server.directory / 'depotflow.sqlite3') as conn:
            conn.execute("CREATE TRIGGER reject_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'injected audit failure'); END")
        key = new_key()
        path = f'/api/orders/{order["id"]}/reserve'
        self.post(path, {'expected_version': 1}, key=key, status=500)
        self.assertEqual(before, self.snapshot())
        with sqlite3.connect(self.server.directory / 'depotflow.sqlite3') as conn:
            conn.execute('DROP TRIGGER reject_audit')
        self.post(path, {'expected_version': 1}, key=key)
        self.assertEqual(self.inventory()['BOLT']['reserved'], 3)
        self.assertEqual(len(self.audit()), 2)

    def test_restart_durability_sessions_replays_cursors_and_no_reseed(self):
        key = new_key()
        order = self.create(key=key)
        shipped = self.transition(self.transition(order, 'reserve'), 'ship')
        self.create('second')
        cursor = self.get('/api/orders?limit=1')['next_cursor']
        stock_key = new_key()
        payload = {'sku': 'CABLE', 'delta': 9, 'expected_version': 1, 'reason': 'durable delivery'}
        item = self.post('/api/stock/adjustments', payload, token=self.admin, key=stock_key)
        before = self.snapshot()
        dashboard = self.get('/api/dashboard')
        self.server.restart(kill=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(dashboard, self.get('/api/dashboard'))
        self.assertEqual(shipped, self.get(f'/api/orders/{order["id"]}'))
        self.assertEqual(self.inventory()['BOLT']['on_hand'], 97)
        self.assertEqual(item, self.post('/api/stock/adjustments', payload, token=self.admin, key=stock_key))
        self.assertEqual(order, self.create(key=key))
        self.assertEqual(self.get('/api/orders?' + urlencode({'limit': 1, 'cursor': cursor}))['items'][0]['client_ref'], 'second')
        self.assertEqual(before, self.snapshot())
        self.transition(shipped, 'returns', lines=[{'sku': 'BOLT', 'quantity': 3}])

    def test_database_constraints_and_dashboard_match(self):
        self.transition(self.create('reserved'), 'reserve')
        self.transition(self.transition(self.create('shipped'), 'reserve'), 'ship')
        self.transition(self.create('cancelled'), 'cancel')
        self.create('draft')
        inv = self.inventory()
        dashboard = self.get('/api/dashboard')
        self.assertEqual(dashboard['inventory_units'], sum(i['on_hand'] for i in inv.values()))
        self.assertEqual(dashboard['reserved_units'], sum(i['reserved'] for i in inv.values()))
        self.assertEqual(dashboard['orders_by_status'], {'draft': 1, 'reserved': 1, 'shipped': 1, 'cancelled': 1, 'returned': 0})
        with sqlite3.connect(self.server.directory / 'depotflow.sqlite3') as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE inventory SET on_hand=0 WHERE tenant='north' AND sku='BOLT'")


class EmptyStoreTests(unittest.TestCase):
    def test_seed_disabled_then_enabled_only_on_empty_store(self):
        server = RunningServer(seed=False)
        self.addCleanup(server.close)
        self.assertEqual(server.request('GET', '/api/health')[0], 200)
        self.assertEqual(server.request('POST', '/api/session', {'email': 'admin@north.example', 'password': 'DepotDemo!2026'})[0], 401)
        server.seed = True
        server.restart()
        token = server.login('admin')
        self.assertEqual(server.request('GET', '/api/inventory', token=token)[1]['items'][0]['on_hand'], 100)


if __name__ == '__main__':
    unittest.main()
