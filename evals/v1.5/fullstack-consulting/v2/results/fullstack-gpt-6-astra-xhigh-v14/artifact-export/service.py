"""Tenant-scoped business operations, called inside one request transaction."""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid

from database import password_hash

MAX_UNITS = 1_000_000_000
MAX_INT = 9_007_199_254_740_991
STATUSES = ('draft', 'reserved', 'shipped', 'cancelled', 'returned')


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def invalid(message):
    raise APIError(400, 'invalid_payload', message)


def integer(value, name, minimum=1, maximum=MAX_UNITS):
    if type(value) is not int or not minimum <= value <= maximum:
        invalid(f'{name} must be an integer between {minimum} and {maximum}.')
    return value


def string(value, name, maximum=160):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        invalid(f'{name} must be nonempty text of at most {maximum} characters.')
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        invalid(f'{name} contains unsupported control characters.')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def user_dict(row):
    return {k: row[k] for k in ('email', 'role', 'tenant')}


def login(db, data):
    email, password = data.get('email'), data.get('password')
    if not isinstance(email, str) or not isinstance(password, str) or len(password) > 1024:
        raise APIError(401, 'bad_credentials', 'Email or password is incorrect.')
    row = db.execute('SELECT * FROM users WHERE email=?', (email.strip().lower(),)).fetchone()
    # Do comparable password work even for nonexistent users.
    candidate = password_hash(password, row['salt'] if row else '00' * 16)
    if not row or not hmac.compare_digest(candidate, row['password_hash']):
        raise APIError(401, 'bad_credentials', 'Email or password is incorrect.')
    token = secrets.token_urlsafe(32)
    db.execute('INSERT INTO sessions VALUES (?,?,?)',
               (hashlib.sha256(token.encode()).hexdigest(), row['email'], int(time.time()) + 86400))
    return {'token': token, 'user': user_dict(row)}


def authenticate(db, header):
    if not header or not header.startswith('Bearer ') or len(header) > 512:
        raise APIError(401, 'unauthorized', 'Sign in to continue.')
    digest = hashlib.sha256(header[7:].encode()).hexdigest()
    row = db.execute('SELECT u.* FROM users u JOIN sessions s ON s.email=u.email '
                     'WHERE s.token_hash=? AND s.expires_at>?', (digest, int(time.time()))).fetchone()
    if not row:
        raise APIError(401, 'unauthorized', 'Your session is invalid or expired. Sign in again.')
    return user_dict(row)


def inventory_item(db, tenant, sku):
    row = db.execute('SELECT sku,name,on_hand,reserved,on_hand-reserved AS available,price_cents,version '
                     'FROM inventory WHERE tenant=? AND sku=?', (tenant, sku)).fetchone()
    if not row:
        invalid(f'Unknown SKU: {sku}.')
    return dict(row)


def inventory(db, tenant):
    return {'items': [dict(r) for r in db.execute(
        'SELECT sku,name,on_hand,reserved,on_hand-reserved AS available,price_cents,version '
        'FROM inventory WHERE tenant=? ORDER BY sku', (tenant,))]}


def order(db, tenant, oid):
    row = db.execute('SELECT id,client_ref,status,version,total_cents FROM orders WHERE tenant=? AND id=?',
                     (tenant, oid)).fetchone()
    if not row:
        raise APIError(404, 'not_found', 'Order not found.')
    result = dict(row)
    result['lines'] = [dict(r) for r in db.execute(
        'SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines '
        'WHERE tenant=? AND order_id=? ORDER BY position', (tenant, oid))]
    return result


def lines(data):
    raw = data.get('lines')
    if not isinstance(raw, list) or not 1 <= len(raw) <= 100:
        invalid('lines must contain between 1 and 100 order lines.')
    parsed, seen = [], set()
    for line in raw:
        if not isinstance(line, dict):
            invalid('Each line must be an object.')
        sku = string(line.get('sku'), 'sku', 64)
        qty = integer(line.get('quantity'), 'quantity')
        if sku in seen:
            invalid(f'SKU {sku} appears more than once.')
        seen.add(sku)
        parsed.append((sku, qty))
    return parsed


def audit(db, user, action, entity_id, details, status=None):
    event = db.execute('INSERT INTO audit(tenant,action,entity_id,actor,created_at,details) VALUES (?,?,?,?,?,?)',
                      (user['tenant'], action, entity_id, user['email'],
                       datetime.now(timezone.utc).isoformat(timespec='milliseconds'), canonical(details)))
    if status:
        db.execute('INSERT INTO order_states VALUES (?,?,?,?)',
                   (user['tenant'], entity_id, event.lastrowid, status))


def check_version(current, data):
    expected = integer(data.get('expected_version'), 'expected_version', maximum=MAX_INT)
    if expected != current['version']:
        raise APIError(409, 'stale_version', 'This record changed. Refresh its version, review your input, and try again.')


def stock_change(db, tenant, sku, on_hand=0, reserved=0):
    before = inventory_item(db, tenant, sku)
    new_hand, new_reserved = before['on_hand'] + on_hand, before['reserved'] + reserved
    if new_hand < new_reserved or new_reserved < 0 or new_hand < 0:
        raise APIError(409, 'insufficient_stock', f'Insufficient available stock for {sku}.')
    if new_hand > MAX_UNITS:
        raise APIError(409, 'stock_limit', f'{sku} would exceed the stock limit of {MAX_UNITS}.')
    db.execute('UPDATE inventory SET on_hand=?,reserved=?,version=version+1 WHERE tenant=? AND sku=?',
               (new_hand, new_reserved, tenant, sku))
    return {'sku': sku, 'on_hand_delta': on_hand, 'reserved_delta': reserved,
            'before': before, 'after': inventory_item(db, tenant, sku)}


def adjust(db, user, data):
    sku = string(data.get('sku'), 'sku', 64)
    delta = integer(data.get('delta'), 'delta', -MAX_UNITS, MAX_UNITS)
    if delta == 0:
        invalid('delta must not be zero.')
    reason = string(data.get('reason'), 'reason', 1000)
    check_version(inventory_item(db, user['tenant'], sku), data)
    change = stock_change(db, user['tenant'], sku, on_hand=delta)
    audit(db, user, 'stock.adjusted', sku, {'reason': reason, 'stock': [change]})
    return 200, change['after']


def create_order(db, user, data):
    ref = string(data.get('client_ref'), 'client_ref')
    parsed = lines(data)
    tenant = user['tenant']
    catalog = [(sku, qty, inventory_item(db, tenant, sku)['price_cents']) for sku, qty in parsed]
    total = sum(qty * price for sku, qty, price in catalog)
    if total > MAX_INT:
        invalid('Order total exceeds the supported integer range.')
    if db.execute('SELECT 1 FROM orders WHERE tenant=? AND client_ref=?', (tenant, ref)).fetchone():
        raise APIError(409, 'duplicate_reference', 'An order already uses this client reference.')
    oid = str(uuid.uuid4())
    db.execute('INSERT INTO orders(id,tenant,client_ref,status,version,total_cents) VALUES (?,?,?,\'draft\',1,?)',
               (oid, tenant, ref, total))
    for position, (sku, qty, price) in enumerate(catalog):
        db.execute('INSERT INTO order_lines VALUES (?,?,?,?,?,?,0)', (tenant, oid, sku, position, qty, price))
    result = order(db, tenant, oid)
    audit(db, user, 'order.created', oid, {'client_ref': ref, 'order': result}, 'draft')
    return 201, result


def transition(db, user, oid, action, data):
    tenant = user['tenant']
    current = order(db, tenant, oid)
    check_version(current, data)
    parsed = lines(data) if action == 'returns' else None
    allowed = {'reserve': ('draft',), 'ship': ('reserved',),
               'cancel': ('draft', 'reserved'), 'returns': ('shipped',)}
    if current['status'] not in allowed[action]:
        raise APIError(409, 'invalid_transition', f'Cannot {action} an order with status {current["status"]}.')
    changes = []
    if action == 'returns':
        by_sku = {line['sku']: line for line in current['lines']}
        for sku, qty in parsed:
            if sku not in by_sku:
                invalid(f'SKU {sku} is not on this order.')
            line = by_sku[sku]
            if line['returned_quantity'] + qty > line['quantity']:
                raise APIError(409, 'excess_return', f'Return exceeds the remaining shipped quantity for {sku}.')
        for sku, qty in parsed:
            changes.append(stock_change(db, tenant, sku, on_hand=qty))
            db.execute('UPDATE order_lines SET returned_quantity=returned_quantity+? '
                       'WHERE tenant=? AND order_id=? AND sku=?', (qty, tenant, oid, sku))
        updated = order(db, tenant, oid)
        status = 'returned' if all(l['quantity'] == l['returned_quantity'] for l in updated['lines']) else 'shipped'
    else:
        status = {'reserve': 'reserved', 'ship': 'shipped', 'cancel': 'cancelled'}[action]
        for line in current['lines']:
            sku, qty = line['sku'], line['quantity']
            if action == 'reserve':
                changes.append(stock_change(db, tenant, sku, reserved=qty))
            elif action == 'ship':
                changes.append(stock_change(db, tenant, sku, on_hand=-qty, reserved=-qty))
            elif current['status'] == 'reserved':
                changes.append(stock_change(db, tenant, sku, reserved=-qty))
    db.execute('UPDATE orders SET status=?,version=version+1 WHERE tenant=? AND id=?', (status, tenant, oid))
    result = order(db, tenant, oid)
    audit(db, user, {'reserve': 'order.reserved', 'ship': 'order.shipped',
                    'cancel': 'order.cancelled', 'returns': 'order.returned'}[action], oid,
          {'client_ref': current['client_ref'], 'from_status': current['status'], 'order': result, 'stock': changes}, status)
    return 200, result


def authorize_mutation(user, path):
    if user['role'] == 'viewer':
        raise APIError(403, 'forbidden', 'Viewers can inspect records but cannot change them.')
    if path == '/api/stock/adjustments' and user['role'] != 'admin':
        raise APIError(403, 'forbidden', 'Only an administrator can adjust stock.')


def mutate(db, user, method, path, data, key):
    authorize_mutation(user, path)
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise APIError(400, 'idempotency_key_required', 'Supply a nonempty Idempotency-Key of at most 200 characters.')
    fingerprint = hashlib.sha256((method + '\n' + path + '\n' + canonical(data)).encode()).hexdigest()
    previous = db.execute('SELECT * FROM idempotency WHERE tenant=? AND key=?', (user['tenant'], key)).fetchone()
    if previous:
        if not hmac.compare_digest(previous['fingerprint'], fingerprint):
            raise APIError(409, 'idempotency_conflict', 'This Idempotency-Key was used for a different request.')
        return previous['status'], json.loads(previous['body'])
    if path == '/api/orders':
        status, body = create_order(db, user, data)
    elif path == '/api/stock/adjustments':
        status, body = adjust(db, user, data)
    else:
        match = re.fullmatch(r'/api/orders/([^/]+)/(reserve|ship|cancel|returns)', path)
        if not match:
            raise APIError(404, 'not_found', 'Route not found.')
        status, body = transition(db, user, *match.groups(), data)
    db.execute('INSERT INTO idempotency VALUES (?,?,?,?,?)',
               (user['tenant'], key, fingerprint, status, canonical(body)))
    return status, body


def cursor_encode(db, payload):
    encoded = base64.urlsafe_b64encode(canonical(payload).encode()).decode().rstrip('=')
    secret = db.execute("SELECT value FROM meta WHERE key='cursor_secret'").fetchone()[0]
    signature = hmac.new(bytes.fromhex(secret), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + '.' + signature


def cursor_decode(db, token):
    try:
        if len(token) > 4096:
            raise ValueError()
        encoded, signature = token.split('.')
        secret = db.execute("SELECT value FROM meta WHERE key='cursor_secret'").fetchone()[0]
        expected = hmac.new(bytes.fromhex(secret), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, TypeError, UnicodeError):
        raise APIError(400, 'invalid_cursor', 'This pagination cursor is invalid.') from None


def page_options(db, tenant, kind, query):
    allowed = {'limit', 'cursor'} | ({'status', 'q'} if kind == 'orders' else set())
    if set(query) - allowed or any(len(v) != 1 for v in query.values()):
        raise APIError(400, 'invalid_filter', 'Unknown or repeated query parameter.')
    limit_text = query.get('limit', ['20'])[0]
    if not re.fullmatch(r'[0-9]{1,3}', limit_text) or not 1 <= int(limit_text) <= 100:
        raise APIError(400, 'invalid_filter', 'limit must be an integer between 1 and 100.')
    status, q = query.get('status', [None])[0], query.get('q', [''])[0]
    if (status is not None and status not in STATUSES) or len(q) > 160:
        raise APIError(400, 'invalid_filter', 'Invalid order status or search text.')
    base = {'v': 1, 'tenant': tenant, 'kind': kind, 'status': status, 'q': q.casefold()}
    token = query.get('cursor', [None])[0]
    if token is not None:
        cursor = cursor_decode(db, token)
        if any(cursor.get(k) != v for k, v in base.items()) or set(cursor) != set(base) | {'after', 'bound', 'event'}:
            raise APIError(400, 'invalid_cursor', 'Cursor does not match this tenant, view, or filters.')
        for key in ('after', 'bound', 'event'):
            if type(cursor.get(key)) is not int or cursor[key] < 0:
                raise APIError(400, 'invalid_cursor', 'Invalid cursor position.')
        return int(limit_text), cursor
    table, seq = ('orders', 'seq') if kind == 'orders' else ('audit', 'id')
    bound = db.execute(f'SELECT COALESCE(MAX({seq}),0) FROM {table} WHERE tenant=?', (tenant,)).fetchone()[0]
    event = db.execute('SELECT COALESCE(MAX(id),0) FROM audit WHERE tenant=?', (tenant,)).fetchone()[0]
    return int(limit_text), dict(base, after=0, bound=bound, event=event)


def list_orders(db, tenant, query):
    limit, cursor = page_options(db, tenant, 'orders', query)
    sql = 'SELECT o.id,o.seq FROM orders o WHERE o.tenant=? AND o.seq>? AND o.seq<=? '
    args = [tenant, cursor['after'], cursor['bound']]
    if cursor['q']:
        sql += 'AND instr(casefold(o.client_ref),?)>0 '
        args.append(cursor['q'])
    if cursor['status']:
        # Membership is evaluated at the first page's event boundary. A later
        # status transition cannot drop an original match from subsequent pages.
        sql += ('AND (SELECT s.status FROM order_states s WHERE s.tenant=o.tenant '
                'AND s.order_id=o.id AND s.event_id<=? ORDER BY s.event_id DESC LIMIT 1)=? ')
        args.extend([cursor['event'], cursor['status']])
    rows = db.execute(sql + 'ORDER BY o.seq LIMIT ?', (*args, limit + 1)).fetchall()
    next_cursor = cursor_encode(db, dict(cursor, after=rows[limit-1]['seq'])) if len(rows) > limit else None
    return {'items': [order(db, tenant, row['id']) for row in rows[:limit]], 'next_cursor': next_cursor}


def list_audit(db, tenant, query):
    limit, cursor = page_options(db, tenant, 'audit', query)
    rows = db.execute('SELECT id,action,entity_id,actor,created_at,details FROM audit '
                      'WHERE tenant=? AND id>? AND id<=? ORDER BY id LIMIT ?',
                      (tenant, cursor['after'], cursor['bound'], limit + 1)).fetchall()
    next_cursor = cursor_encode(db, dict(cursor, after=rows[limit-1]['id'])) if len(rows) > limit else None
    items = []
    for row in rows[:limit]:
        item = dict(row)
        item['details'] = json.loads(item['details'])
        items.append(item)
    return {'items': items, 'next_cursor': next_cursor}


def read_route(db, user, path, query):
    tenant = user['tenant']
    if path == '/api/me':
        return user
    if path == '/api/inventory':
        return inventory(db, tenant)
    if path == '/api/dashboard':
        counts = {status: 0 for status in STATUSES}
        counts.update({r[0]: r[1] for r in db.execute('SELECT status,COUNT(*) FROM orders WHERE tenant=? GROUP BY status', (tenant,))})
        totals = db.execute('SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0) FROM inventory WHERE tenant=?', (tenant,)).fetchone()
        return {'orders_by_status': counts, 'inventory_units': totals[0], 'reserved_units': totals[1]}
    if path == '/api/orders':
        return list_orders(db, tenant, query)
    if path == '/api/audit':
        return list_audit(db, tenant, query)
    match = re.fullmatch(r'/api/orders/([^/]+)', path)
    if match:
        return order(db, tenant, match[1])
    raise APIError(404, 'not_found', 'Route not found.')
