import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

from tests.support import App, new_key


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.app = App().start()
        self.addCleanup(self.app.close)
        self.operator = self.app.login()
        self.admin = self.app.login('admin')

    def get(self, path, token=None, expected=200):
        status, body = self.app.request('GET', '/api' + path, token=token or self.operator)
        self.assertEqual(status, expected, body)
        return body

    def post(self, path, data, token=None, expected=200, key=None):
        status, body = self.app.request('POST', '/api' + path, data, token or self.operator, key or new_key())
        self.assertEqual(status, expected, body)
        if expected >= 400:
            self.assertIsInstance(body['error']['code'], str)
            self.assertTrue(body['error']['message'])
        return body

    def create(self, ref=None, lines=None, **kwargs):
        return self.post('/orders', {'client_ref': ref or new_key(), 'lines': lines if lines is not None else [{'sku': 'BOLT', 'quantity': 2}]}, expected=201, **kwargs)

    def transition(self, order, action, **kwargs):
        return self.post(f"/orders/{order['id']}/{action}", {'expected_version': order['version']}, **kwargs)

    def stock(self, sku='BOLT', token=None):
        return next(item for item in self.get('/inventory', token)['items'] if item['sku'] == sku)

    def snapshot(self):
        with sqlite3.connect(self.app.data / 'depotflow.sqlite3') as db:
            return {table: db.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall() for table in ('inventory', 'orders', 'order_lines', 'audit', 'idempotency', 'order_status_history')}

    def test_health_authentication_and_roles(self):
        self.assertEqual(self.app.request('GET', '/api/health'), (200, {'status': 'ok'}))
        for token in (None, 'wrong'):
            self.assertEqual(self.app.request('GET', '/api/inventory', token=token)[0], 401)
        for data in ({'email': 'operator@north.example', 'password': 'wrong'}, {'email': 'absent', 'password': 'wrong'}, {'email': True, 'password': 2}):
            self.assertEqual(self.app.request('POST', '/api/session', data)[0], 401)
        self.assertEqual(self.get('/me'), {'email': 'operator@north.example', 'role': 'operator', 'tenant': 'north'})
        viewer = self.app.login('viewer')
        order = self.create(key='same-key')
        before = self.snapshot()
        self.post('/orders', {'client_ref': order['client_ref'], 'lines': [{'sku': 'BOLT', 'quantity': 2}]}, viewer, expected=403, key='same-key')
        for path in ('reserve', 'ship', 'cancel', 'returns'):
            self.post(f"/orders/{order['id']}/{path}", {'expected_version': 1}, viewer, expected=403)
        adjust = {'sku': 'BOLT', 'delta': 1, 'expected_version': 1, 'reason': 'Count'}
        self.post('/stock/adjustments', adjust, self.operator, expected=403)
        self.post('/stock/adjustments', adjust, viewer, expected=403)
        self.assertEqual(before, self.snapshot())
        for path in ('/inventory', '/dashboard', '/orders', '/audit'):
            self.get(path, viewer)

    def test_tenant_isolation_and_untrusted_fields(self):
        south = self.app.login('admin', 'south')
        north_order = self.post('/orders', {'client_ref': 'SAME', 'tenant': 'south', 'role': 'admin', 'total_cents': 1,
            'lines': [{'sku': 'BOLT', 'quantity': 2, 'unit_price_cents': 1}]}, expected=201, key='tenant-key')
        south_order = self.create('SAME', token=south, key='tenant-key')
        self.assertNotEqual(north_order['id'], south_order['id'])
        self.assertEqual(north_order['total_cents'], 2500)
        self.get('/orders/' + north_order['id'], south, expected=404)
        for action in ('reserve', 'ship', 'cancel', 'returns'):
            self.post(f"/orders/{north_order['id']}/{action}", {'expected_version': 1, 'lines': [{'sku': 'BOLT', 'quantity': 1}]}, south, expected=404)
        _, me = self.app.request('GET', '/api/me', token=self.operator, headers={'X-Tenant': 'south', 'X-Role': 'admin'})
        self.assertEqual(me['tenant'], 'north')
        self.transition(north_order, 'reserve')
        self.assertEqual(self.stock(token=south)['reserved'], 0)
        self.assertEqual(len(self.get('/orders', south)['items']), 1)
        self.assertEqual(len(self.get('/audit', south)['items']), 1)
        self.assertEqual(self.get('/dashboard', south)['reserved_units'], 0)

    def test_order_lifecycle_returns_and_dashboard(self):
        order = self.create(lines=[{'sku': 'BOLT', 'quantity': 4}, {'sku': 'CABLE', 'quantity': 3}])
        self.assertEqual((order['status'], order['version'], order['total_cents']), ('draft', 1, 12497))
        order = self.transition(order, 'reserve')
        self.assertEqual((order['status'], order['version']), ('reserved', 2))
        self.assertEqual((self.stock()['on_hand'], self.stock()['reserved'], self.stock()['available']), (100, 4, 96))
        order = self.transition(order, 'ship')
        self.assertEqual((self.stock()['on_hand'], self.stock()['reserved'], self.stock()['available']), (96, 0, 96))
        self.transition(order, 'cancel', expected=409)
        order = self.post(f"/orders/{order['id']}/returns", {'expected_version': 3, 'lines': [{'sku': 'BOLT', 'quantity': 2}]})
        self.assertEqual((order['status'], order['version'], order['lines'][0]['returned_quantity']), ('shipped', 4, 2))
        self.assertEqual(self.stock()['on_hand'], 98)
        before = self.snapshot()
        self.post(f"/orders/{order['id']}/returns", {'expected_version': 4, 'lines': [{'sku': 'CABLE', 'quantity': 1}, {'sku': 'BOLT', 'quantity': 3}]}, expected=409)
        self.assertEqual(before, self.snapshot())
        order = self.post(f"/orders/{order['id']}/returns", {'expected_version': 4, 'lines': [{'sku': 'BOLT', 'quantity': 2}, {'sku': 'CABLE', 'quantity': 3}]})
        self.assertEqual((order['status'], order['version']), ('returned', 5))
        self.assertEqual(self.stock()['on_hand'], 100)
        self.post(f"/orders/{order['id']}/returns", {'expected_version': 5, 'lines': [{'sku': 'BOLT', 'quantity': 1}]}, expected=409)
        dashboard = self.get('/dashboard')
        self.assertEqual(dashboard['inventory_units'], 180)
        self.assertEqual(dashboard['reserved_units'], 0)
        self.assertEqual(dashboard['orders_by_status']['returned'], 1)
        self.assertEqual([event['action'] for event in self.get('/audit')['items']], ['order.created', 'order.reserved', 'order.shipped', 'order.returned', 'order.returned'])

    def test_zero_price_and_cancel_release(self):
        order = self.create(lines=[{'sku': 'SAMPLE', 'quantity': 2}])
        self.assertEqual(order['total_cents'], 0)
        order = self.transition(order, 'reserve')
        self.assertEqual(self.stock('SAMPLE')['reserved'], 2)
        order = self.transition(order, 'cancel')
        self.assertEqual((order['status'], order['version']), ('cancelled', 3))
        self.assertEqual(self.stock('SAMPLE')['reserved'], 0)
        self.transition(order, 'reserve', expected=409)
        draft = self.create()
        before = self.get('/inventory')
        self.transition(draft, 'cancel')
        self.assertEqual(before, self.get('/inventory'))

    def test_atomic_multiline_reserve_and_stale_versions(self):
        order = self.create(lines=[{'sku': 'BOLT', 'quantity': 3}, {'sku': 'CABLE', 'quantity': 61}])
        before = self.snapshot()
        self.transition(order, 'reserve', expected=409)
        self.assertEqual(before, self.snapshot())
        self.post('/stock/adjustments', {'sku': 'CABLE', 'delta': 1, 'expected_version': 1, 'reason': 'Received'}, self.admin)
        reserved = self.transition(order, 'reserve')
        before = self.snapshot()
        self.post(f"/orders/{order['id']}/ship", {'expected_version': 1}, expected=409)
        self.post('/stock/adjustments', {'sku': 'BOLT', 'delta': 1, 'expected_version': 1, 'reason': 'Stale'}, self.admin, expected=409)
        self.post('/stock/adjustments', {'sku': 'BOLT', 'delta': -98, 'expected_version': 2, 'reason': 'Below reservation'}, self.admin, expected=409)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(reserved['version'], 2)

    def test_validation_is_strict_and_side_effect_free(self):
        invalid = [True, False, 1.5, 1.0, 0, -1, '2', None, [], {}, 9007199254740992]
        before = self.snapshot()
        for quantity in invalid:
            self.post('/orders', {'client_ref': 'bad', 'lines': [{'sku': 'BOLT', 'quantity': quantity}]}, expected=400)
        for lines in ([], [{'sku': 'NOPE', 'quantity': 1}], [{'sku': 'BOLT', 'quantity': 1}, {'sku': 'BOLT', 'quantity': 2}], ['BOLT'], None):
            self.post('/orders', {'client_ref': 'bad', 'lines': lines}, expected=400)
        for ref in ('', '  ', None, True, 'x' * 201):
            self.post('/orders', {'client_ref': ref, 'lines': [{'sku': 'BOLT', 'quantity': 1}]}, expected=400)
        for delta in (0, True, 1.5, 1.0, None, '2'):
            self.post('/stock/adjustments', {'sku': 'BOLT', 'delta': delta, 'expected_version': 1, 'reason': 'Invalid'}, self.admin, expected=400)
        for reason in ('', ' ', False):
            self.post('/stock/adjustments', {'sku': 'BOLT', 'delta': 1, 'expected_version': 1, 'reason': reason}, self.admin, expected=400)
        self.assertEqual(before, self.snapshot())
        order = self.create()
        for version in (True, False, 1.0, 0, None, '1'):
            self.post(f"/orders/{order['id']}/reserve", {'expected_version': version}, expected=400)
        for raw in ('[]', 'null', '{bad', '{"client_ref":"x","client_ref":"y"}', '{"v":NaN}', '{"v":1e999}', '{"v":"\\ud800"}'):
            self.assertEqual(self.app.request('POST', '/api/orders', token=self.operator, key=new_key(), raw=raw)[0], 400)

    def test_returns_validation_atomicity(self):
        order = self.transition(self.transition(self.create(), 'reserve'), 'ship')
        before = self.snapshot()
        for lines in ([], [{'sku': 'CABLE', 'quantity': 1}], [{'sku': 'BOLT', 'quantity': 1}, {'sku': 'BOLT', 'quantity': 1}], [{'sku': 'BOLT', 'quantity': True}], [{'sku': 'BOLT', 'quantity': -1}]):
            self.post(f"/orders/{order['id']}/returns", {'expected_version': 3, 'lines': lines}, expected=400)
        self.assertEqual(before, self.snapshot())

    def test_idempotency_replay_conflicts_failures_and_authorization(self):
        payload = {'client_ref': 'retry', 'lines': [{'sku': 'BOLT', 'quantity': 2}]}
        self.assertEqual(self.app.request('POST', '/api/orders', payload, self.operator)[0], 400)
        self.assertEqual(self.app.request('POST', '/api/orders', payload, self.operator, '   ')[0], 400)
        order = self.post('/orders', payload, expected=201, key='create')
        before = self.snapshot()
        self.assertEqual(order, self.post('/orders', dict(reversed(list(payload.items()))), expected=201, key='create'))
        self.post('/orders', payload | {'client_ref': 'other'}, expected=409, key='create')
        self.post('/orders', payload, expected=409)
        self.post(f"/orders/{order['id']}/reserve", {'expected_version': 1}, expected=409, key='create')
        self.assertEqual(before, self.snapshot())
        self.post(f"/orders/{order['id']}/ship", {'expected_version': 1}, expected=409, key='failed')
        self.transition(order, 'reserve')
        shipped = self.post(f"/orders/{order['id']}/ship", {'expected_version': 2}, key='failed')
        before = self.snapshot()
        self.assertEqual(shipped, self.post(f"/orders/{order['id']}/ship", {'expected_version': 2}, key='failed'))
        self.assertEqual(before, self.snapshot())
        adjust = {'sku': 'BOLT', 'delta': 3, 'expected_version': 3, 'reason': 'Retry receipt'}
        adjusted = self.post('/stock/adjustments', adjust, self.admin, key='adjust')
        self.assertEqual(adjusted, self.post('/stock/adjustments', adjust, self.admin, key='adjust'))
        self.post('/stock/adjustments', adjust, self.operator, expected=403, key='adjust')

    def test_concurrent_reservations_do_not_oversell(self):
        orders = [self.create(lines=[{'sku': 'BOLT', 'quantity': 60}]) for _ in range(8)]
        def reserve(order):
            return self.app.request('POST', f"/api/orders/{order['id']}/reserve", {'expected_version': 1}, self.operator, new_key())
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, orders))
        self.assertEqual(sorted(status for status, _ in results), [200] + [409] * 7)
        self.assertEqual((self.stock()['on_hand'], self.stock()['reserved'], self.stock()['available']), (100, 60, 40))
        self.assertEqual(len(self.get('/audit')['items']), 9)

    def test_concurrent_identical_creates_adjustments_and_transitions(self):
        def concurrently(path, payload, token, key, status):
            with ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(lambda _: self.app.request('POST', '/api' + path, payload, token, key), range(24)))
            self.assertTrue(all(result == results[0] for result in results))
            self.assertEqual(results[0][0], status)
            return results[0][1]
        order = concurrently('/orders', {'client_ref': 'parallel', 'lines': [{'sku': 'BOLT', 'quantity': 2}]}, self.operator, 'parallel-create', 201)
        concurrently(f"/orders/{order['id']}/reserve", {'expected_version': 1}, self.operator, 'parallel-reserve', 200)
        concurrently('/stock/adjustments', {'sku': 'BOLT', 'delta': 5, 'expected_version': 2, 'reason': 'Delivery'}, self.admin, 'parallel-adjust', 200)
        self.assertEqual((self.stock()['on_hand'], self.stock()['reserved'], self.stock()['version']), (105, 2, 3))
        self.assertEqual(len(self.get('/audit')['items']), 3)

    def test_pagination_filters_cursor_isolation_and_new_inserts(self):
        created = [self.create(f"{'Match' if i % 2 == 0 else 'other'}-{i}") for i in range(9)]
        first = self.get('/orders?q=mAtCh&status=draft&limit=2')
        # Page membership remains fixed even when a not-yet-seen match transitions.
        self.transition(created[4], 'cancel')
        self.create('Match-new')
        items = first['items']; cursor = first['next_cursor']
        while cursor:
            page = self.get('/orders?' + urlencode({'q': 'mAtCh', 'status': 'draft', 'limit': 2, 'cursor': cursor}))
            items += page['items']; cursor = page['next_cursor']
        self.assertEqual([o['id'] for o in items], [o['id'] for o in created[::2]])
        self.assertEqual(self.get('/orders?q=missing')['items'], [])
        self.assertIsNone(self.get('/orders?q=missing')['next_cursor'])
        for query in ('status=bad', 'status=', 'limit=0', 'limit=101', 'limit=1.5', 'limit=true', 'limit=', 'limit=2&limit=3', 'cursor=bad', 'cursor=', 'unknown=1'):
            self.get('/orders?' + query, expected=400)
        cursor = first['next_cursor']
        self.get('/orders?' + urlencode({'cursor': cursor}), expected=400)
        south = self.app.login('operator', 'south')
        self.get('/orders?' + urlencode({'cursor': cursor, 'q': 'match', 'status': 'draft'}), south, expected=400)
        self.get('/audit?' + urlencode({'cursor': cursor}), expected=400)
        audit, cursor = [], None
        while True:
            page = self.get('/audit?' + urlencode({'limit': 3} | ({'cursor': cursor} if cursor else {})))
            audit += page['items']; cursor = page['next_cursor']
            if cursor is None:
                break
        self.assertEqual(len(audit), 11)
        self.assertEqual([e['id'] for e in audit], sorted(set(e['id'] for e in audit)))
        self.assertTrue(all(e['actor'] == 'operator@north.example' for e in audit))

    def test_durable_restart_replay_cursor_and_no_reseed(self):
        payload = {'client_ref': 'durable', 'lines': [{'sku': 'BOLT', 'quantity': 4}]}
        original = self.post('/orders', payload, expected=201, key='durable-create')
        shipped = self.transition(self.transition(original, 'reserve'), 'ship')
        self.create('another')
        cursor = self.get('/orders?limit=1')['next_cursor']
        before = self.snapshot()
        self.app.stop(); self.app.start(seed=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.stock()['on_hand'], 96)
        self.assertEqual(shipped, self.get('/orders/' + original['id']))
        self.assertEqual(original, self.post('/orders', payload, expected=201, key='durable-create'))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(len(self.get('/orders?' + urlencode({'cursor': cursor}))['items']), 1)
        with sqlite3.connect(self.app.data / 'depotflow.sqlite3') as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_stock_adjustment_audit_details_and_safe_reduction(self):
        updated = self.post('/stock/adjustments', {'sku': 'BOLT', 'delta': -100, 'expected_version': 1, 'reason': 'Cycle count'}, self.admin)
        self.assertEqual((updated['on_hand'], updated['available'], updated['version']), (0, 0, 2))
        before = self.snapshot()
        self.post('/stock/adjustments', {'sku': 'BOLT', 'delta': -1, 'expected_version': 2, 'reason': 'Invalid'}, self.admin, expected=409)
        self.assertEqual(before, self.snapshot())
        event = self.get('/audit')['items'][0]
        self.assertEqual(event['details']['reason'], 'Cycle count')
        self.assertEqual(event['actor'], 'admin@north.example')
        for item in self.get('/inventory')['items']:
            for key in ('on_hand', 'reserved', 'available', 'price_cents', 'version'):
                self.assertIs(type(item[key]), int)

    def test_crash_restart_keeps_acknowledged_stock_and_retry(self):
        payload = {'sku': 'CABLE', 'delta': 7, 'expected_version': 1, 'reason': 'Before crash'}
        original = self.post('/stock/adjustments', payload, self.admin, key='crash-retry')
        before = self.snapshot()
        self.app.process.kill()
        self.app.process.wait(timeout=10)
        self.app.start(seed=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(original, self.post('/stock/adjustments', payload, self.admin, key='crash-retry'))
        self.assertEqual(before, self.snapshot())

    def test_same_version_concurrent_adjustment_has_one_winner(self):
        payload = {'sku': 'BOLT', 'delta': 1, 'expected_version': 1, 'reason': 'Concurrent adjustment'}
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.app.request('POST', '/api/stock/adjustments', payload, self.admin, new_key()), range(8)))
        self.assertEqual(sorted(status for status, _ in results), [200] + [409] * 7)
        self.assertEqual((self.stock()['on_hand'], self.stock()['version']), (101, 2))
        self.assertEqual(len(self.get('/audit')['items']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
