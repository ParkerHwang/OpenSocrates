"""All API projections and mutation rules; callers own the transaction."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone

from .db import password_hash

STATUSES = ('draft', 'reserved', 'shipped', 'cancelled', 'returned')
MAX_UNITS = 1_000_000_000
MAX_INTEGER = 9_007_199_254_740_991


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def bad(message):
    raise APIError(400, 'invalid_request', message)


def conflict(code, message):
    raise APIError(409, code, message)


def integer(value, name, minimum=1, maximum=MAX_UNITS):
    if type(value) is not int or not minimum <= value <= maximum:
        bad(f'{name} must be an integer from {minimum} to {maximum}.')
    return value


def string(value, name, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        bad(f'{name} must be nonempty text, at most {maximum} characters.')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def user_shape(row):
    return {key: row[key] for key in ('email', 'role', 'tenant')}


def authenticate(conn, authorization):
    if not authorization.startswith('Bearer ') or len(authorization) > 512:
        raise APIError(401, 'unauthorized', 'Sign in to continue.')
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    row = conn.execute('SELECT u.* FROM sessions s JOIN users u ON u.email=s.email '
                       'WHERE s.token_hash=? AND s.expires_at>?', (digest, int(time.time()))).fetchone()
    if row is None:
        raise APIError(401, 'unauthorized', 'Your session is invalid or expired. Sign in again.')
    return user_shape(row)


def login(conn, payload):
    email = payload.get('email')
    password = payload.get('password')
    if not isinstance(email, str) or not isinstance(password, str) or len(password) > 1024:
        raise APIError(401, 'bad_credentials', 'Email or password is incorrect.')
    row = conn.execute('SELECT * FROM users WHERE email=?', (email.strip().lower(),)).fetchone()
    # Equal password work for known and unknown users.
    salt = row['salt'] if row else '00' * 16
    candidate = password_hash(password, salt)
    if row is None or not hmac.compare_digest(candidate, row['password_hash']):
        raise APIError(401, 'bad_credentials', 'Email or password is incorrect.')
    token = secrets.token_urlsafe(32)
    conn.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
    conn.execute('INSERT INTO sessions VALUES (?,?,?)',
                 (hashlib.sha256(token.encode()).hexdigest(), row['email'], int(time.time()) + 43200))
    return {'token': token, 'user': user_shape(row)}


def authorize(user, path):
    if user['role'] == 'viewer':
        raise APIError(403, 'forbidden', 'Viewers can inspect data but cannot make changes.')
    if path == '/api/stock/adjustments' and user['role'] != 'admin':
        raise APIError(403, 'forbidden', 'Only an administrator can adjust stock.')


def inventory_item(conn, tenant, sku):
    row = conn.execute('SELECT sku,name,on_hand,reserved,on_hand-reserved AS available,'
                       'price_cents,version FROM inventory WHERE tenant=? AND sku=?', (tenant, sku)).fetchone()
    if not row:
        bad(f'Unknown SKU: {sku}.')
    return dict(row)


def order(conn, tenant, oid):
    row = conn.execute('SELECT id,client_ref,status,version,total_cents FROM orders WHERE tenant=? AND id=?',
                       (tenant, oid)).fetchone()
    if row is None:
        raise APIError(404, 'not_found', 'Order not found.')
    result = dict(row)
    result['lines'] = [dict(line) for line in conn.execute(
        'SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines '
        'WHERE tenant=? AND order_id=? ORDER BY position', (tenant, oid))]
    return result


def event(conn, user, action, entity, details, status=None):
    conn.execute('INSERT INTO audit (tenant,action,entity_id,actor,created_at,status,details) VALUES (?,?,?,?,?,?,?)',
                 (user['tenant'], action, entity, user['email'],
                  datetime.now(timezone.utc).isoformat(timespec='milliseconds'), status, canonical(details)))


def check_version(payload, current):
    version = integer(payload.get('expected_version'), 'expected_version', maximum=MAX_INTEGER)
    if version != current:
        conflict('stale_version', f'This record changed (current version {current}). Refresh and review before trying again.')


def lines_from(payload):
    lines = payload.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        bad('lines must contain between 1 and 100 entries.')
    seen, result = set(), []
    for line in lines:
        if not isinstance(line, dict):
            bad('Each line must be an object with sku and quantity.')
        sku = string(line.get('sku'), 'sku', 80)
        qty = integer(line.get('quantity'), 'quantity')
        if sku in seen:
            bad(f'Duplicate SKU: {sku}. Combine its quantities into one line.')
        seen.add(sku)
        result.append((sku, qty))
    return result


def adjust(conn, user, payload):
    tenant = user['tenant']
    sku = string(payload.get('sku'), 'sku', 80)
    delta = integer(payload.get('delta'), 'delta', -MAX_UNITS, MAX_UNITS)
    if delta == 0:
        bad('delta must be nonzero.')
    reason = string(payload.get('reason'), 'reason', 1000)
    item = inventory_item(conn, tenant, sku)
    check_version(payload, item['version'])
    new_count = item['on_hand'] + delta
    if new_count < item['reserved']:
        conflict('stock_conflict', 'Adjustment would reduce on-hand stock below reserved units.')
    if new_count > MAX_UNITS:
        conflict('stock_conflict', 'Stock would exceed the supported inventory limit.')
    conn.execute('UPDATE inventory SET on_hand=?,version=version+1 WHERE tenant=? AND sku=?',
                 (new_count, tenant, sku))
    event(conn, user, 'stock.adjusted', sku, {'delta': delta, 'reason': reason, 'on_hand': new_count})
    return inventory_item(conn, tenant, sku)


def create_order(conn, user, payload):
    tenant = user['tenant']
    ref = string(payload.get('client_ref'), 'client_ref')
    lines = lines_from(payload)
    priced = [(sku, qty, inventory_item(conn, tenant, sku)['price_cents']) for sku, qty in lines]
    total = sum(qty * price for _, qty, price in priced)
    if total > MAX_INTEGER:
        bad('Order total exceeds the supported integer range.')
    oid = str(uuid.uuid4())
    try:
        conn.execute('INSERT INTO orders (id,tenant,client_ref,status,version,total_cents) VALUES (?,?,?,\'draft\',1,?)',
                     (oid, tenant, ref, total))
    except sqlite3.IntegrityError:
        conflict('reference_conflict', 'This client reference already belongs to an order. Choose a unique reference.')
    for position, (sku, qty, price) in enumerate(priced):
        conn.execute('INSERT INTO order_lines VALUES (?,?,?,?,?,?,0)', (tenant, oid, position, sku, qty, price))
    event(conn, user, 'order.created', oid, {'client_ref': ref}, 'draft')
    return order(conn, tenant, oid)


def transition(conn, user, oid, action, payload):
    tenant = user['tenant']
    current = order(conn, tenant, oid)
    check_version(payload, current['version'])
    requested = lines_from(payload) if action == 'returns' else None
    allowed = {'reserve': ('draft',), 'ship': ('reserved',), 'cancel': ('draft', 'reserved'), 'returns': ('shipped',)}
    if current['status'] not in allowed[action]:
        conflict('invalid_transition', f"Cannot {action} an order with status {current['status']}.")
    next_status = {'reserve': 'reserved', 'ship': 'shipped', 'cancel': 'cancelled', 'returns': 'shipped'}[action]
    changes = []
    if action == 'returns':
        original = {line['sku']: line for line in current['lines']}
        for sku, qty in requested:
            if sku not in original:
                bad(f'SKU {sku} does not belong to this order.')
            line = original[sku]
            if line['returned_quantity'] + qty > line['quantity']:
                conflict('return_exceeded', f'Return exceeds the remaining shipped quantity for {sku}.')
            changes.append((sku, qty, 0))
        # Validate every line before changing any; the surrounding transaction also rolls back failures.
        for sku, qty in requested:
            conn.execute('UPDATE order_lines SET returned_quantity=returned_quantity+? '
                         'WHERE tenant=? AND order_id=? AND sku=?', (qty, tenant, oid, sku))
        if all(line['returned_quantity'] + dict(requested).get(line['sku'], 0) == line['quantity']
               for line in current['lines']):
            next_status = 'returned'
    else:
        for line in current['lines']:
            sku, qty = line['sku'], line['quantity']
            if action == 'reserve':
                item = inventory_item(conn, tenant, sku)
                if item['available'] < qty:
                    conflict('insufficient_stock', f"Not enough available {sku}: requested {qty}, available {item['available']}.")
                changes.append((sku, 0, qty))
            elif action == 'ship':
                changes.append((sku, -qty, -qty))
            elif current['status'] == 'reserved':
                changes.append((sku, 0, -qty))
    for sku, on_hand_delta, reserved_delta in changes:
        item = inventory_item(conn, tenant, sku)
        if item['on_hand'] + on_hand_delta > MAX_UNITS:
            conflict('stock_conflict', f'Returned {sku} would exceed the inventory limit.')
        conn.execute('UPDATE inventory SET on_hand=on_hand+?,reserved=reserved+?,version=version+1 '
                     'WHERE tenant=? AND sku=?', (on_hand_delta, reserved_delta, tenant, sku))
    conn.execute('UPDATE orders SET status=?,version=version+1 WHERE tenant=? AND id=?', (next_status, tenant, oid))
    event(conn, user, 'order.' + {'reserve': 'reserved', 'ship': 'shipped', 'cancel': 'cancelled', 'returns': 'returned'}[action],
          oid, payload, next_status)
    return order(conn, tenant, oid)


def mutate(conn, user, path, payload, key):
    authorize(user, path)  # Never let a cached success bypass present authorization.
    string(key, 'Idempotency-Key', 200)
    fingerprint = hashlib.sha256(canonical(['POST', path, payload]).encode()).hexdigest()
    saved = conn.execute('SELECT * FROM idempotency WHERE tenant=? AND key=?', (user['tenant'], key)).fetchone()
    if saved:
        if saved['fingerprint'] != fingerprint:
            conflict('idempotency_conflict', 'This Idempotency-Key was already used for a different request.')
        return saved['status'], saved['body']
    status = 200
    if path == '/api/stock/adjustments':
        result = adjust(conn, user, payload)
    elif path == '/api/orders':
        status, result = 201, create_order(conn, user, payload)
    else:
        match = re.fullmatch(r'/api/orders/([^/]+)/(reserve|ship|cancel|returns)', path)
        if not match:
            raise APIError(404, 'not_found', 'API endpoint not found.')
        result = transition(conn, user, *match.groups(), payload)
    body = canonical(result)
    conn.execute('INSERT INTO idempotency VALUES (?,?,?,?,?)', (user['tenant'], key, fingerprint, status, body))
    return status, body


def cursor_secret(conn):
    return bytes.fromhex(conn.execute("SELECT value FROM metadata WHERE key='cursor_secret'").fetchone()[0])


def encode_cursor(conn, data):
    content = base64.urlsafe_b64encode(canonical(data).encode()).decode().rstrip('=')
    signature = hmac.new(cursor_secret(conn), content.encode(), hashlib.sha256).hexdigest()
    return content + '.' + signature


def decode_cursor(conn, token, context):
    try:
        if len(token) > 8192:
            raise ValueError()
        content, signature = token.split('.')
        expected = hmac.new(cursor_secret(conn), content.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        value = json.loads(base64.b64decode(content + '=' * (-len(content) % 4), altchars=b'-_', validate=True))
        if not isinstance(value, dict) or set(value) != set(context) | {'last', 'high', 'audit_high'}:
            raise ValueError()
        if any(value.get(k) != v for k, v in context.items()):
            raise ValueError()
        if any(type(value[k]) is not int or value[k] < 0 for k in ('last', 'high', 'audit_high')):
            raise ValueError()
        if value['last'] > value['high']:
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError, KeyError):
        bad('Invalid cursor. Use the next_cursor from the same tenant, view and filters.')


def page_query(query, allowed):
    if any(k not in allowed or len(v) != 1 for k, v in query.items()):
        bad('Unknown or repeated query parameter.')
    limit = query.get('limit', ['20'])[0]
    if not re.fullmatch(r'[0-9]{1,3}', limit) or not 1 <= int(limit) <= 100:
        bad('limit must be an integer from 1 to 100.')
    return int(limit)


def list_page(conn, tenant, kind, query):
    limit = page_query(query, {'limit', 'cursor', 'status', 'q'} if kind == 'orders' else {'limit', 'cursor'})
    status, q = query.get('status', [None])[0], query.get('q', [''])[0]
    if status is not None and status not in STATUSES:
        bad('status must be draft, reserved, shipped, cancelled or returned.')
    if len(q) > 200:
        bad('q must be at most 200 characters.')
    context = {'kind': kind, 'tenant': tenant, 'status': status, 'q': q.casefold()}
    if 'cursor' in query:
        cursor = decode_cursor(conn, query['cursor'][0], context)
    else:
        table, column = ('orders', 'seq') if kind == 'orders' else ('audit', 'id')
        high = conn.execute(f'SELECT COALESCE(MAX({column}),0) FROM {table} WHERE tenant=?', (tenant,)).fetchone()[0]
        audit_high = conn.execute('SELECT COALESCE(MAX(id),0) FROM audit WHERE tenant=?', (tenant,)).fetchone()[0]
        cursor = dict(context, last=0, high=high, audit_high=audit_high)
    if kind == 'orders':
        sql = 'SELECT o.id,o.seq FROM orders o WHERE o.tenant=? AND o.seq>? AND o.seq<=? AND instr(casefold(o.client_ref),?)>0'
        params = [tenant, cursor['last'], cursor['high'], q.casefold()]
        if status is not None:
            # Membership uses the first page's audit watermark even if status changes between pages.
            sql += ' AND (SELECT a.status FROM audit a WHERE a.tenant=o.tenant AND a.entity_id=o.id AND a.id<=? ORDER BY a.id DESC LIMIT 1)=?'
            params.extend((cursor['audit_high'], status))
        rows = conn.execute(sql + ' ORDER BY o.seq LIMIT ?', (*params, limit + 1)).fetchall()
        items = [order(conn, tenant, row['id']) for row in rows[:limit]]
        last = rows[min(limit, len(rows)) - 1]['seq'] if rows else 0
    else:
        rows = conn.execute('SELECT id,action,entity_id,actor,created_at,details FROM audit '
                            'WHERE tenant=? AND id>? AND id<=? ORDER BY id LIMIT ?',
                            (tenant, cursor['last'], cursor['high'], limit + 1)).fetchall()
        items = [{**dict(row), 'details': json.loads(row['details'])} for row in rows[:limit]]
        last = rows[min(limit, len(rows)) - 1]['id'] if rows else 0
    next_cursor = encode_cursor(conn, dict(cursor, last=last)) if len(rows) > limit else None
    return {'items': items, 'next_cursor': next_cursor}


def read(conn, user, path, query):
    tenant = user['tenant']
    if path == '/api/me':
        return user
    if path == '/api/inventory':
        return {'items': [inventory_item(conn, tenant, r['sku']) for r in conn.execute(
            'SELECT sku FROM inventory WHERE tenant=? ORDER BY sku', (tenant,))]}
    if path == '/api/dashboard':
        counts = dict.fromkeys(STATUSES, 0)
        counts.update({r['status']: r['n'] for r in conn.execute(
            'SELECT status,COUNT(*) AS n FROM orders WHERE tenant=? GROUP BY status', (tenant,))})
        totals = conn.execute('SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0) FROM inventory WHERE tenant=?', (tenant,)).fetchone()
        return {'orders_by_status': counts, 'inventory_units': totals[0], 'reserved_units': totals[1]}
    if path in ('/api/orders', '/api/audit'):
        return list_page(conn, tenant, path.rsplit('/', 1)[1], query)
    match = re.fullmatch(r'/api/orders/([^/]+)', path)
    if match:
        return order(conn, tenant, match[1])
    raise APIError(404, 'not_found', 'API endpoint not found.')
