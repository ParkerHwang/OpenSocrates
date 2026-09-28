"""Tenant-scoped domain operations. Callers supply a trusted authenticated user."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from datetime import datetime, timezone

from .db import password_hash

STATUSES = ('draft', 'reserved', 'shipped', 'cancelled', 'returned')
MAX_INT = 9_007_199_254_740_991


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def fail(status, code, message):
    raise APIError(status, code, message)


def string(value, name, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        fail(400, 'invalid_payload', f'{name} must be nonempty text of at most {maximum} characters.')
    return value


def integer(value, name, minimum=1, maximum=MAX_INT):
    if type(value) is not int or not minimum <= value <= maximum:
        fail(400, 'invalid_payload', f'{name} must be an integer from {minimum} to {maximum}.')
    return value


def lines_payload(data):
    lines = data.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        fail(400, 'invalid_payload', 'lines must contain between 1 and 100 items.')
    seen = set()
    for line in lines:
        if not isinstance(line, dict):
            fail(400, 'invalid_payload', 'Each line must be an object.')
        sku = string(line.get('sku'), 'sku')
        integer(line.get('quantity'), 'quantity')
        if sku in seen:
            fail(400, 'duplicate_sku', f'{sku} appears more than once.')
        seen.add(sku)
    return lines


def inventory_item(row):
    return {k: row[k] for k in ('sku', 'name', 'on_hand', 'reserved', 'price_cents', 'version')} | {
        'available': row['on_hand'] - row['reserved']}


def get_stock(db, tenant, sku):
    row = db.execute('SELECT * FROM inventory WHERE tenant=? AND sku=?', (tenant, sku)).fetchone()
    if row is None:
        fail(400, 'unknown_sku', f'Unknown SKU: {sku}.')
    return row


def get_order(db, tenant, order_id):
    row = db.execute('SELECT * FROM orders WHERE tenant=? AND id=?', (tenant, order_id)).fetchone()
    if row is None:
        fail(404, 'not_found', 'Order not found.')
    result = {k: row[k] for k in ('id', 'client_ref', 'status', 'version', 'total_cents')}
    result['lines'] = [dict(line) for line in db.execute(
        'SELECT sku,quantity,unit_price_cents,returned_quantity FROM order_lines '
        'WHERE tenant=? AND order_id=? ORDER BY position', (tenant, order_id))]
    return result


def version_matches(actual, expected):
    integer(expected, 'expected_version')
    if actual != expected:
        fail(409, 'stale_version', 'This record changed. Refresh its version, review your input, then retry.')


def event(db, user, action, entity_id, details):
    inserted = db.execute('INSERT INTO audit(tenant,action,entity_id,actor,created_at,details) VALUES (?,?,?,?,?,?)',
               (user['tenant'], action, entity_id, user['email'],
                datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                json.dumps(details, sort_keys=True, separators=(',', ':'))))
    if action.startswith('order.'):
        db.execute('INSERT INTO order_status_history VALUES (?,?,?,?)',
                   (user['tenant'], entity_id, inserted.lastrowid, details.get('to', 'draft')))


def login(db, data):
    email, password = data.get('email'), data.get('password')
    if not isinstance(email, str) or not isinstance(password, str) or len(password) > 1024:
        fail(401, 'bad_credentials', 'Email or password is incorrect.')
    row = db.execute('SELECT * FROM users WHERE email=?', (email.strip().lower(),)).fetchone()
    candidate = password_hash(password, row['salt'] if row else '00' * 16)
    if row is None or not hmac.compare_digest(candidate, row['password_hash']):
        fail(401, 'bad_credentials', 'Email or password is incorrect.')
    token = secrets.token_urlsafe(32)
    db.execute('BEGIN IMMEDIATE')
    db.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
    db.execute('INSERT INTO sessions VALUES (?,?,?)',
               (hashlib.sha256(token.encode()).hexdigest(), row['email'], int(time.time()) + 43_200))
    db.commit()
    return {'token': token, 'user': {k: row[k] for k in ('email', 'role', 'tenant')}}


def authenticate(db, authorization):
    if not authorization or not authorization.startswith('Bearer '):
        fail(401, 'unauthenticated', 'Sign in to continue.')
    token = authorization[7:]
    row = db.execute('SELECT u.email,u.role,u.tenant FROM sessions s JOIN users u ON u.email=s.email '
                     'WHERE s.token_hash=? AND s.expires_at>?',
                     (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
    if row is None:
        fail(401, 'unauthenticated', 'Session is invalid or expired. Sign in again.')
    return dict(row)


def authorize(user, path):
    if user['role'] == 'viewer':
        fail(403, 'forbidden', 'Viewers can inspect records but cannot make changes.')
    if path == '/api/stock/adjustments' and user['role'] != 'admin':
        fail(403, 'forbidden', 'Only an admin can adjust stock.')


def mutation(db, user, path, key, data):
    # Authorize before looking up retries, so stored results cannot bypass role checks.
    authorize(user, path)
    string(key, 'Idempotency-Key', 200)
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    fingerprint = hashlib.sha256(('POST\n' + path + '\n' + canonical).encode()).hexdigest()
    db.execute('BEGIN IMMEDIATE')
    cached = db.execute('SELECT * FROM idempotency WHERE tenant=? AND key=?', (user['tenant'], key)).fetchone()
    if cached:
        if cached['fingerprint'] != fingerprint:
            fail(409, 'idempotency_conflict', 'This Idempotency-Key was already used for a different request.')
        db.commit()
        return cached['status'], cached['body']
    if path == '/api/stock/adjustments':
        status, result = 200, adjust_stock(db, user, data)
    elif path == '/api/orders':
        status, result = 201, create_order(db, user, data)
    else:
        match = re.fullmatch(r'/api/orders/([^/]+)/(reserve|ship|cancel|returns)', path)
        if not match:
            fail(404, 'not_found', 'Route not found.')
        status, result = 200, transition(db, user, *match.groups(), data)
    body = json.dumps(result, separators=(',', ':'), ensure_ascii=True)
    db.execute('INSERT INTO idempotency VALUES (?,?,?,?,?)', (user['tenant'], key, fingerprint, status, body))
    db.commit()
    return status, body


def adjust_stock(db, user, data):
    tenant = user['tenant']
    sku = string(data.get('sku'), 'sku')
    delta = integer(data.get('delta'), 'delta', -MAX_INT)
    if delta == 0:
        fail(400, 'invalid_payload', 'delta must be nonzero.')
    reason = string(data.get('reason'), 'reason', 1000)
    stock = get_stock(db, tenant, sku)
    version_matches(stock['version'], data.get('expected_version'))
    new_stock = stock['on_hand'] + delta
    if new_stock < stock['reserved']:
        fail(409, 'insufficient_stock', 'Adjustment would reduce on-hand stock below reserved units.')
    if new_stock > MAX_INT:
        fail(400, 'invalid_payload', 'Resulting stock exceeds the supported integer range.')
    db.execute('UPDATE inventory SET on_hand=?,version=version+1 WHERE tenant=? AND sku=?', (new_stock, tenant, sku))
    event(db, user, 'stock.adjusted', sku, {'delta': delta, 'reason': reason, 'before': stock['on_hand'], 'after': new_stock})
    return inventory_item(get_stock(db, tenant, sku))


def create_order(db, user, data):
    tenant = user['tenant']
    ref = string(data.get('client_ref'), 'client_ref')
    lines = lines_payload(data)
    priced, total = [], 0
    for line in lines:
        stock = get_stock(db, tenant, line['sku'])
        priced.append((line['sku'], line['quantity'], stock['price_cents']))
        total += line['quantity'] * stock['price_cents']
    if total > MAX_INT:
        fail(400, 'invalid_payload', 'Order total exceeds the supported integer range.')
    if db.execute('SELECT 1 FROM orders WHERE tenant=? AND client_ref=?', (tenant, ref)).fetchone():
        fail(409, 'duplicate_reference', 'An order already uses this client reference.')
    order_id = uuid.uuid4().hex
    db.execute('INSERT INTO orders(id,tenant,client_ref,status,total_cents) VALUES (?,?,?,\'draft\',?)',
               (order_id, tenant, ref, total))
    db.executemany('INSERT INTO order_lines(tenant,order_id,position,sku,quantity,unit_price_cents) VALUES (?,?,?,?,?,?)',
                   [(tenant, order_id, i, sku, quantity, price) for i, (sku, quantity, price) in enumerate(priced)])
    event(db, user, 'order.created', order_id, {'client_ref': ref, 'lines': priced})
    return get_order(db, tenant, order_id)


def transition(db, user, order_id, action, data):
    tenant = user['tenant']
    order = get_order(db, tenant, order_id)
    version_matches(order['version'], data.get('expected_version'))
    returns = lines_payload(data) if action == 'returns' else None
    allowed = {'reserve': ('draft',), 'ship': ('reserved',), 'cancel': ('draft', 'reserved'), 'returns': ('shipped',)}
    if order['status'] not in allowed[action]:
        fail(409, 'invalid_transition', f"Cannot {action} an order with status {order['status']}.")
    next_status = {'reserve': 'reserved', 'ship': 'shipped', 'cancel': 'cancelled', 'returns': 'shipped'}[action]
    if action == 'returns':
        by_sku = {line['sku']: line for line in order['lines']}
        for line in returns:
            original = by_sku.get(line['sku'])
            if original is None:
                fail(400, 'unknown_sku', f"{line['sku']} does not belong to this order.")
            if original['returned_quantity'] + line['quantity'] > original['quantity']:
                fail(409, 'excess_return', f"Return exceeds shipped quantity for {line['sku']}.")
            stock = get_stock(db, tenant, line['sku'])
            if stock['on_hand'] + line['quantity'] > MAX_INT:
                fail(409, 'stock_limit', 'Returned stock exceeds the supported integer range.')
            db.execute('UPDATE order_lines SET returned_quantity=returned_quantity+? WHERE tenant=? AND order_id=? AND sku=?',
                       (line['quantity'], tenant, order_id, line['sku']))
            db.execute('UPDATE inventory SET on_hand=on_hand+?,version=version+1 WHERE tenant=? AND sku=?',
                       (line['quantity'], tenant, line['sku']))
        remaining = db.execute('SELECT SUM(quantity-returned_quantity) FROM order_lines WHERE tenant=? AND order_id=?',
                               (tenant, order_id)).fetchone()[0]
        if remaining == 0:
            next_status = 'returned'
    else:
        for line in order['lines']:
            quantity, sku = line['quantity'], line['sku']
            stock = get_stock(db, tenant, sku)
            if action == 'reserve':
                if stock['on_hand'] - stock['reserved'] < quantity:
                    fail(409, 'insufficient_stock', f'Not enough available stock for {sku}.')
                db.execute('UPDATE inventory SET reserved=reserved+?,version=version+1 WHERE tenant=? AND sku=?',
                           (quantity, tenant, sku))
            elif action == 'ship':
                db.execute('UPDATE inventory SET reserved=reserved-?,on_hand=on_hand-?,version=version+1 WHERE tenant=? AND sku=?',
                           (quantity, quantity, tenant, sku))
            elif order['status'] == 'reserved':
                db.execute('UPDATE inventory SET reserved=reserved-?,version=version+1 WHERE tenant=? AND sku=?',
                           (quantity, tenant, sku))
    db.execute('UPDATE orders SET status=?,version=version+1 WHERE tenant=? AND id=?', (next_status, tenant, order_id))
    event(db, user, {'reserve': 'order.reserved', 'ship': 'order.shipped', 'cancel': 'order.cancelled', 'returns': 'order.returned'}[action],
          order_id, {'from': order['status'], 'to': next_status, 'version': order['version'] + 1, 'lines': returns or order['lines']})
    return get_order(db, tenant, order_id)


def cursor_encode(secret, data):
    raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode()
    signature = hmac.new(bytes.fromhex(secret), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature + raw).decode().rstrip('=')


def cursor_decode(secret, cursor):
    try:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,2048}', cursor):
            raise ValueError()
        raw = base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4))
        signature, payload = raw[:32], raw[32:]
        if not hmac.compare_digest(signature, hmac.new(bytes.fromhex(secret), payload, hashlib.sha256).digest()):
            raise ValueError()
        return json.loads(payload)
    except (ValueError, TypeError):
        fail(400, 'invalid_cursor', 'Cursor is invalid. Start again from the first page.')


def paginate(db, tenant, kind, query):
    allowed = {'limit', 'cursor', 'status', 'q'} if kind == 'orders' else {'limit', 'cursor'}
    if set(query) - allowed or any(len(values) != 1 for values in query.values()):
        fail(400, 'invalid_filter', 'Unknown or repeated query parameters.')
    params = {k: v[0] for k, v in query.items()}
    limit_raw = params.get('limit', '20')
    if not re.fullmatch(r'[0-9]{1,3}', limit_raw) or not 1 <= int(limit_raw) <= 100:
        fail(400, 'invalid_filter', 'limit must be an integer from 1 to 100.')
    limit = int(limit_raw)
    status, search = params.get('status'), params.get('q', '')
    if status is not None and status not in STATUSES or len(search) > 200:
        fail(400, 'invalid_filter', 'Invalid status or search longer than 200 characters.')
    binding = {'tenant': tenant, 'kind': kind, 'status': status, 'q': search.casefold()}
    secret = db.execute('SELECT value FROM meta WHERE key=\'cursor_secret\'').fetchone()[0]
    column = 'seq' if kind == 'orders' else 'id'
    after = 0
    high = db.execute(f'SELECT COALESCE(MAX({column}),0) FROM {kind} WHERE tenant=?', (tenant,)).fetchone()[0]
    at = db.execute('SELECT COALESCE(MAX(id),0) FROM audit WHERE tenant=?', (tenant,)).fetchone()[0]
    if 'cursor' in params:
        decoded = cursor_decode(secret, params['cursor'])
        if not isinstance(decoded, dict) or any(decoded.get(k) != v for k, v in binding.items()):
            fail(400, 'invalid_cursor', 'Cursor does not match this tenant, list, or filter.')
        after, high = decoded.get('after'), decoded.get('high')
        at = decoded.get('at')
        if type(after) is not int or type(high) is not int or type(at) is not int or not 0 <= after <= high or at < 0:
            fail(400, 'invalid_cursor', 'Invalid cursor position.')
    sql = f'SELECT * FROM {kind} WHERE tenant=? AND {column}>? AND {column}<=?'
    args = [tenant, after, high]
    if kind == 'orders':
        if status:
            # Freeze membership as of the first page, even if matching orders transition.
            sql += (' AND (SELECT h.status FROM order_status_history h WHERE h.tenant=orders.tenant '
                    'AND h.order_id=orders.id AND h.audit_id<=? ORDER BY h.audit_id DESC LIMIT 1)=?')
            args.extend((at, status))
        if search:
            sql += ' AND instr(casefold(client_ref),?)>0'
            args.append(search.casefold())
    rows = db.execute(sql + f' ORDER BY {column} LIMIT ?', (*args, limit + 1)).fetchall()
    page = rows[:limit]
    items = [get_order(db, tenant, row['id']) if kind == 'orders' else
             {k: row[k] for k in ('id', 'action', 'entity_id', 'actor', 'created_at')} | {'details': json.loads(row['details'])} for row in page]
    cursor = cursor_encode(secret, binding | {'after': page[-1][column], 'high': high, 'at': at}) if len(rows) > limit else None
    return {'items': items, 'next_cursor': cursor}


def read(db, user, path, query):
    tenant = user['tenant']
    if path == '/api/me':
        return user
    if path == '/api/inventory':
        return {'items': [inventory_item(row) for row in db.execute('SELECT * FROM inventory WHERE tenant=? ORDER BY sku', (tenant,))]}
    if path == '/api/dashboard':
        counts = dict.fromkeys(STATUSES, 0)
        counts.update({row['status']: row['n'] for row in db.execute('SELECT status,COUNT(*) n FROM orders WHERE tenant=? GROUP BY status', (tenant,))})
        stock = db.execute('SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0) FROM inventory WHERE tenant=?', (tenant,)).fetchone()
        return {'orders_by_status': counts, 'inventory_units': stock[0], 'reserved_units': stock[1]}
    if path in ('/api/orders', '/api/audit'):
        return paginate(db, tenant, path[5:], query)
    match = re.fullmatch(r'/api/orders/([^/]+)', path)
    if match:
        return get_order(db, tenant, match[1])
    fail(404, 'not_found', 'Route not found.')
