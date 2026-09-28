'use strict';

// All client text is inserted with textContent; no user data is parsed as HTML.
const h = (tag, props = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key in node && !key.startsWith('aria-') && !key.startsWith('data-')) node[key] = value;
    else node.setAttribute(key, value);
  }
  children.flat(Infinity).forEach(child => {
    if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  });
  return node;
};
const test = id => ({'data-testid': id});
const money = cents => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(cents / 100);
const number = value => new Intl.NumberFormat('en-US').format(value);
const state = {token: sessionStorage.getItem('depotflow-token'), user: null, view: 'inventory', epoch: 0,
  busy: false, filters: {q: '', status: ''}, retries: new Map()};
let main, notice, navButtons = [];
const root = document.getElementById('app');
const button = (text, props = {}) => h('button', {type: 'button', ...props}, text);
const badge = status => h('span', {class: `status ${status}`}, status);
const label = (text, input, props = {}) => h('label', props, text, input);
const brand = () => h('div', {class: 'brand'}, h('img', {src: '/favicon.svg', alt: ''}), h('div', {}, 'DepotFlow', h('small', {}, 'Fulfillment workspace')));
const writable = () => state.user.role !== 'viewer';

class RequestError extends Error {
  constructor(message, code, status) {super(message); this.code = code; this.status = status;}
}
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {...options, headers: {'Content-Type': 'application/json',
      ...(state.token ? {Authorization: `Bearer ${state.token}`} : {}), ...options.headers}});
  } catch (_) {throw new RequestError('Connection interrupted. Retry the same operation to safely recover its result.', 'network', 0);}
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/session') {
      logout();
      loginNotice('Your session expired. Sign in again.');
    }
    throw new RequestError(data.error?.message || 'The request failed.', data.error?.code, response.status);
  }
  return data;
}
function message(target, text = '', kind = 'error') {
  target.className = `message ${kind}`;
  target.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  target.textContent = text;
}
function notify(text, kind = 'success') {message(notice, text, kind);}
function logout() {
  state.token = null; state.user = null; state.epoch++; state.retries.clear();
  sessionStorage.removeItem('depotflow-token');
  renderLogin();
}
function loginNotice(text) {message(document.getElementById('login-notice'), text);}

function renderLogin() {
  const email = h('input', {...test('login-email'), type: 'email', name: 'email', autocomplete: 'username', required: true, placeholder: 'operator@north.example'});
  const password = h('input', {...test('login-password'), type: 'password', name: 'password', autocomplete: 'current-password', required: true, placeholder: 'Enter your password'});
  const submit = h('button', {...test('login-submit'), class: 'primary', type: 'submit'}, 'Sign in to workspace');
  const error = h('div', {id: 'login-notice', 'aria-live': 'polite'});
  const fieldset = h('fieldset', {}, label('Email address', email), label('Password', password), submit);
  const form = h('form', {class: 'login-form', onSubmit: async event => {
    event.preventDefault(); if (fieldset.disabled) return;
    fieldset.disabled = true; submit.textContent = 'Signing in…'; message(error);
    try {
      const result = await api('/api/session', {method: 'POST', body: JSON.stringify({email: email.value, password: password.value})});
      state.token = result.token; state.user = result.user;
      sessionStorage.setItem('depotflow-token', result.token); state.filters = {q: '', status: ''};
      renderShell(); await navigate('inventory');
    } catch (err) {message(error, err.message);}
    finally {fieldset.disabled = false; submit.textContent = 'Sign in to workspace';}
  }}, h('div', {class: 'eyebrow'}, 'Your warehouse, in order'), h('h1', {}, 'Welcome back'),
  h('p', {class: 'muted small'}, 'Sign in to keep fulfillment moving.'), error, fieldset,
  h('div', {class: 'demo-note'}, h('p', {}, h('strong', {}, 'Local demo accounts')),
    h('p', {}, 'Use ', h('code', {}, 'admin'), ', ', h('code', {}, 'operator'), ', or ', h('code', {}, 'viewer'),
      h('br'), 'at ', h('code', {}, '@north.example'), ' or ', h('code', {}, '@south.example'), '.'),
    h('p', {}, 'Password: ', h('code', {}, 'DepotDemo!2026'))),
  h('p', {class: 'login-fineprint'}, 'Separate organizations. One connected workflow.'));
  root.replaceChildren(h('div', {class: 'login-shell'},
    h('section', {class: 'login-story'}, brand(),
      h('div', {class: 'story-copy'}, h('div', {class: 'eyebrow'}, 'Ready for the next order'),
        h('h1', {}, 'A clear path from shelf to shipment.'),
        h('p', {}, 'Keep stock accurate, orders moving, and every change accounted for.')),
      h('div', {class: 'story-grid'}, ['Receive', 'Reserve', 'Deliver'].map((word, i) => h('div', {}, h('strong', {}, `0${i+1}`), h('span', {}, word))))),
    h('section', {class: 'login-area', 'aria-label': 'Sign in'}, form)));
}

function renderShell() {
  navButtons = ['inventory', 'orders', 'audit'].map((view, index) => button('', {
    ...test(`nav-${view}`), onClick: () => navigate(view)
  }));
  ['Inventory', 'Orders', 'Activity log'].forEach((text, i) => navButtons[i].append(h('span', {class: 'nav-num'}, `0${i+1}`), text));
  main = h('main', {id: 'main', class: 'main', tabIndex: -1});
  notice = h('div', {'aria-live': 'polite'});
  root.replaceChildren(h('div', {class: 'shell'},
    h('aside', {class: 'sidebar'}, brand(),
      h('div', {class: 'tenant-label'}, h('div', {class: 'eyebrow'}, 'Organization'), h('strong', {}, `${state.user.tenant} warehouse`)),
      h('nav', {'aria-label': 'Main navigation'}, navButtons),
      h('div', {class: 'sidebar-footer'}, h('div', {}, h('span', {}, state.user.email), h('br'), h('span', {class: 'role'}, state.user.role)),
        button('Sign out', {...test('logout'), onClick: logout}))),
    h('div', {class: 'workspace'}, h('header', {class: 'topbar'}, h('span', {}, 'WAREHOUSE OPERATIONS'),
      h('span', {class: 'live-dot'}, `${state.user.tenant.toUpperCase()} / LOCAL WORKSPACE`)), main)));
}
function pageHeading(title, subtitle, action) {
  return h('div', {class: 'page-heading'}, h('div', {}, h('div', {class: 'eyebrow'}, 'DepotFlow / Operations'), h('h1', {}, title), h('p', {class: 'muted small'}, subtitle)), action);
}
function setPage(...nodes) {main.replaceChildren(notice, ...nodes);}
async function navigate(view, options = {}) {
  if (state.busy || !state.user) return;
  state.view = view; const epoch = ++state.epoch;
  navButtons.forEach((b, i) => {const active = ['inventory', 'orders', 'audit'][i] === (view === 'detail' || view === 'new' ? 'orders' : view);
    b.classList.toggle('active', active); if (active) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');});
  if (!options.keepNotice) message(notice);
  setPage(h('div', {class: 'loading', role: 'status'}, 'Loading workspace…'));
  try {
    if (view === 'inventory') await renderInventory(epoch);
    if (view === 'orders') await renderOrders(epoch);
    if (view === 'new') await renderNewOrder(epoch);
    if (view === 'detail') await renderDetail(options.id, epoch, options.returnValues);
    if (view === 'audit') await renderAudit(epoch);
  } catch (err) {
    if (epoch !== state.epoch) return;
    setPage(pageHeading('Could not load this view', 'Your saved changes are safe.'), button('Try again', {onClick: () => navigate(view, options)}));
    notify(err.message, 'error');
  }
}
function lock(locked, container) {
  state.busy = locked;
  document.querySelectorAll('.sidebar button').forEach(b => b.disabled = locked);
  container.setAttribute('aria-busy', String(locked));
  container.querySelectorAll('button,input,select').forEach(control => {
    if (locked) {control.dataset.wasDisabled = String(control.disabled); control.disabled = true;}
    else {control.disabled = control.dataset.wasDisabled === 'true'; delete control.dataset.wasDisabled;}
  });
}
async function mutation(container, path, payload, onSuccess, localNotice = notice) {
  if (state.busy) return;
  const body = JSON.stringify(payload), signature = path + body;
  const key = state.retries.get(signature) || crypto.randomUUID(); state.retries.set(signature, key);
  lock(true, container); message(localNotice, 'Saving changes…', 'info');
  let result;
  try {result = await api(path, {method: 'POST', headers: {'Idempotency-Key': key}, body});}
  catch (err) {message(localNotice, err.message + (err.code === 'stale_version' ? ' Your entered values are still here.' : ''));}
  finally {lock(false, container);}
  if (result) {state.retries.delete(signature); await onSuccess(result);}
}

async function renderInventory(epoch) {
  const [inventory, dashboard] = await Promise.all([api('/api/inventory'), api('/api/dashboard')]);
  if (epoch !== state.epoch) return;
  const counts = dashboard.orders_by_status;
  const stats = h('div', {class: 'stats'},
    stat('On hand', number(dashboard.inventory_units), 'Units across your catalog'),
    stat('Reserved', number(dashboard.reserved_units), 'Committed to open orders'),
    stat('Ready to ship', number(counts.reserved || 0), 'Orders awaiting dispatch'),
    stat('Shipped', number(counts.shipped || 0), 'Including partial returns'));
  const table = h('table', {...test('inventory-table')},
    h('caption', {class: 'visually-hidden'}, 'Inventory quantities, prices, and versions'),
    h('thead', {}, h('tr', {}, ['Product', 'On hand', 'Reserved', 'Available', 'Unit price', 'Version'].map((name, i) => h('th', {scope: 'col', class: i ? 'numeric' : ''}, name)))),
    h('tbody', {}, inventory.items.map(item => h('tr', {},
      h('td', {}, h('span', {class: 'product-name'}, item.name), h('span', {class: 'sku'}, item.sku)),
      h('td', {class: 'numeric'}, number(item.on_hand)), h('td', {class: 'numeric'}, number(item.reserved)),
      h('td', {class: 'numeric'}, h('span', {class: 'stock-pill'}, number(item.available))),
      h('td', {class: 'numeric'}, money(item.price_cents)), h('td', {class: 'numeric muted'}, item.version)))));
  const panel = h('section', {class: 'card'}, h('div', {class: 'card-head'}, h('div', {}, h('h2', {}, 'Stock overview'), h('p', {class: 'muted small'}, 'Available stock excludes reserved units.')),
    h('span', {class: 'badge-count'}, `${inventory.items.length} SKUs`)), h('div', {class: 'table-wrap'}, table));
  setPage(pageHeading('Inventory', 'Know what is on the shelf, and what is already spoken for.', button('Refresh', {onClick: () => navigate('inventory')})), stats, panel);
  if (!inventory.items.length) panel.append(empty('No inventory yet', 'Seed a new local store to begin.'));
  if (state.user.role === 'admin') main.append(adjustmentForm(inventory.items));
  if (!writable()) main.append(h('p', {class: 'refresh-note'}, 'Viewer access · You can inspect inventory, orders, and activity.'));
}
function stat(name, value, note) {return h('div', {class: 'stat'}, h('div', {class: 'stat-label'}, name), h('div', {class: 'stat-value'}, value), h('div', {class: 'stat-note'}, note));}
function empty(title, text) {return h('div', {class: 'empty'}, h('strong', {}, title), text);}
function skuSelect(items, marker = 'line-sku') {
  return h('select', {...test(marker), required: true}, items.map(item => h('option', {value: item.sku}, `${item.sku} — ${item.name}`)));
}
function adjustmentForm(items) {
  const sku = skuSelect(items, 'adjustment-sku');
  const delta = h('input', {...test('adjustment-delta'), type: 'number', required: true, step: 1, min: -1000000000, max: 1000000000, placeholder: 'e.g. 12 or -3'});
  const reason = h('input', {...test('adjustment-reason'), required: true, maxLength: 1000, placeholder: 'What changed and why?'});
  let versions = Object.fromEntries(items.map(item => [item.sku, item.version]));
  const versionNote = h('p', {class: 'inline-note'});
  const updateNote = () => versionNote.textContent = `Using stock version ${versions[sku.value] ?? '—'}.`;
  sku.addEventListener('change', updateNote); updateNote();
  const localNotice = h('div', {'aria-live': 'polite'});
  const form = h('form', {onSubmit: event => {event.preventDefault();
    if (!Number.isSafeInteger(Number(delta.value)) || Number(delta.value) === 0) return message(localNotice, 'Enter a nonzero whole-number adjustment.');
    mutation(form, '/api/stock/adjustments', {sku: sku.value, delta: Number(delta.value), expected_version: versions[sku.value], reason: reason.value}, async () => {
      notify('Stock adjustment saved. Inventory and totals are up to date.'); await navigate('inventory', {keepNotice: true});
    }, localNotice);
  }}, h('div', {class: 'form-grid'}, label('Product', sku), label('Unit adjustment (+ / −)', delta), label('Reason', reason, {class: 'wide'})), versionNote, localNotice,
  h('div', {class: 'form-actions'}, button('Refresh stock versions', {onClick: async () => {
    try {const latest = await api('/api/inventory'); versions = Object.fromEntries(latest.items.map(item => [item.sku, item.version])); updateNote(); message(localNotice, 'Stock versions refreshed. Review your adjustment before saving.', 'info');}
    catch (err) {message(localNotice, err.message);}
  }}), h('button', {type: 'submit', class: 'primary', ...test('submit-adjustment')}, 'Save adjustment')));
  return h('details', {class: 'card stock-adjustment'}, h('summary', {}, 'Adjust stock'), h('div', {class: 'card-body'}, h('p', {class: 'muted small'}, 'Record a receipt or correction. A reason is saved in the activity log.'), form));
}

function orderQuery(cursor) {
  const params = new URLSearchParams({limit: '20'});
  if (state.filters.q) params.set('q', state.filters.q);
  if (state.filters.status) params.set('status', state.filters.status);
  if (cursor) params.set('cursor', cursor);
  return `/api/orders?${params}`;
}
async function renderOrders(epoch) {
  const data = await api(orderQuery()); if (epoch !== state.epoch) return;
  const search = h('input', {type: 'search', value: state.filters.q, placeholder: 'Search client reference', maxLength: 160, ...test('order-search')});
  const status = h('select', {...test('order-filter')}, h('option', {value: ''}, 'All statuses'), ['draft','reserved','shipped','cancelled','returned'].map(s => h('option', {value: s}, s[0].toUpperCase()+s.slice(1))));
  status.value = state.filters.status;
  const filters = h('form', {class: 'toolbar', onSubmit: event => {event.preventDefault(); state.filters = {q: search.value, status: status.value}; navigate('orders');}},
    label('Client reference', search, {class: 'search'}), label('Status', status), h('button', {type: 'submit'}, 'Apply filters'),
    button('Reset', {onClick: () => {state.filters = {q: '', status: ''}; navigate('orders');}}));
  const tbody = h('tbody');
  const table = h('table', {}, h('caption', {class: 'visually-hidden'}, 'Orders, oldest first'),
    h('thead', {}, h('tr', {}, ['Client reference','Status','Items','Total',''].map(text => h('th', {scope: 'col'}, text)))), tbody);
  const append = items => items.forEach(order => tbody.append(h('tr', {},
    h('td', {}, button(order.client_ref, {class: 'link order-ref', onClick: () => navigate('detail', {id: order.id})})),
    h('td', {}, badge(order.status)), h('td', {}, `${order.lines.reduce((n,l) => n+l.quantity,0)} units`), h('td', {}, money(order.total_cents)),
    h('td', {}, button('View →', {'aria-label': `View order ${order.client_ref}`, onClick: () => navigate('detail', {id: order.id})})))));
  append(data.items);
  const pager = pagination(data.next_cursor, async cursor => {const next = await api(orderQuery(cursor)); if (epoch === state.epoch) append(next.items); return next;});
  const panel = h('section', {class: 'card'}, filters, data.items.length ? h('div', {class: 'table-wrap'}, table) : empty('No orders found', 'Try another filter or create your first order.'), pager);
  setPage(pageHeading('Orders', 'From first request to final delivery. Oldest orders appear first.', writable() ? button('+ New order', {...test('new-order'), class: 'primary', onClick: () => navigate('new')}) : null), panel);
}
function pagination(cursor, load) {
  const note = h('span', {class: 'muted small'}, cursor ? 'More records available' : 'You’re up to date');
  const more = button('Load more', {disabled: !cursor, onClick: async () => {
    more.disabled = true; more.textContent = 'Loading…';
    try {const data = await load(cursor); cursor = data.next_cursor; note.textContent = cursor ? 'More records available' : 'All records loaded';}
    catch (err) {notify(err.message, 'error');}
    finally {more.disabled = !cursor; more.textContent = 'Load more';}
  }});
  return h('div', {class: 'pagination'}, note, more);
}

async function renderNewOrder(epoch) {
  if (!writable()) return navigate('orders');
  const inventory = await api('/api/inventory'); if (epoch !== state.epoch) return;
  const ref = h('input', {...test('order-client-ref'), required: true, maxLength: 160, placeholder: 'e.g. NORTH-1042', autocomplete: 'off'});
  const rows = h('div'); const total = h('strong'); const localNotice = h('div', {'aria-live': 'polite'});
  const recalculate = () => {
    const sum = [...rows.children].reduce((n,row) => n + (inventory.items.find(i => i.sku === row.querySelector('select').value)?.price_cents || 0) * Number(row.querySelector('input').value), 0);
    total.textContent = `Estimated total ${money(sum)}`;
  };
  function addRow() {
    const select = skuSelect(inventory.items), qty = h('input', {...test('line-quantity'), type: 'number', value: '1', required: true, step: 1, min: 1, max: 1000000000});
    const index = rows.children.length;
    if (index < inventory.items.length) select.value = inventory.items[index].sku;
    const row = h('div', {class: 'form-row'}, label('Product', select), label('Quantity', qty, {class: 'quantity'}),
      button('Remove', {'aria-label': 'Remove order line', onClick: () => {if (rows.children.length > 1) row.remove(); recalculate();}}));
    select.addEventListener('change', recalculate); qty.addEventListener('input', recalculate); rows.append(row); recalculate();
  }
  addRow();
  const form = h('form', {onSubmit: event => {event.preventDefault();
    const lines = [...rows.children].map(row => ({sku: row.querySelector('select').value, quantity: Number(row.querySelector('input').value)}));
    if (new Set(lines.map(l => l.sku)).size !== lines.length) return message(localNotice, 'Choose each product only once. Combine its quantity on one line.');
    mutation(form, '/api/orders', {client_ref: ref.value, lines}, async result => {
      notify(`Order ${result.client_ref} created. Reserve stock when you are ready.`); await navigate('detail', {id: result.id, keepNotice: true});
    }, localNotice);
  }}, h('section', {class: 'form-section'}, label('Client reference', ref), h('p', {class: 'inline-note'}, 'A unique reference for this organization.')),
    h('section', {class: 'form-section'}, h('h2', {}, 'Order lines'), h('p', {class: 'muted small'}, 'Prices come from your catalog. Stock is committed when you reserve the order.'), rows,
      button('+ Add line', {...test('add-line'), onClick: addRow})), localNotice,
    h('div', {class: 'form-actions'}, total, h('button', {type: 'submit', class: 'primary', ...test('submit-order')}, 'Create order')));
  setPage(button('← Back to orders', {class: 'link back', onClick: () => navigate('orders')}), pageHeading('New order', 'Build an order with one or more products.'), h('section', {class: 'card order-form'}, h('div', {class: 'card-body'}, form)));
}

async function renderDetail(id, epoch, returnValues = {}) {
  const order = await api(`/api/orders/${encodeURIComponent(id)}`); if (epoch !== state.epoch) return;
  const returnInputs = {};
  const canReturn = writable() && order.status === 'shipped';
  const detail = h('section', {...test('order-detail')});
  const localNotice = h('div', {'aria-live': 'polite'});
  const saveValues = () => Object.fromEntries(Object.entries(returnInputs).map(([sku, input]) => [sku, input.value]));
  const refresh = () => navigate('detail', {id, returnValues: saveValues(), keepNotice: true});
  const transition = action => mutation(detail, `/api/orders/${id}/${action}`, {expected_version: order.version}, async result => {
    notify(`Order ${result.client_ref} is now ${result.status}.`); await navigate('detail', {id, keepNotice: true});
  }, localNotice);
  const table = h('table', {}, h('caption', {class: 'visually-hidden'}, 'Order lines and returns'),
    h('thead', {}, h('tr', {}, ['SKU','Ordered','Unit price','Returned', ...(canReturn ? ['Return now'] : [])].map(name => h('th', {scope: 'col'}, name)))),
    h('tbody', {}, order.lines.map(line => {
      const remaining = line.quantity - line.returned_quantity;
      if (canReturn) returnInputs[line.sku] = h('input', {...test('return-quantity'), class: 'return-input', type: 'number', min: 0, max: remaining, step: 1,
        value: returnValues[line.sku] ?? '0', disabled: remaining === 0, 'aria-label': `Return quantity for ${line.sku}`});
      return h('tr', {}, h('td', {class: 'sku'}, line.sku), h('td', {}, line.quantity), h('td', {}, money(line.unit_price_cents)), h('td', {}, line.returned_quantity),
        canReturn ? h('td', {}, returnInputs[line.sku]) : null);
    })));
  const returnForm = h('form', {onSubmit: event => {event.preventDefault();
    const lines = Object.entries(returnInputs).filter(([,input]) => Number(input.value) > 0).map(([sku,input]) => ({sku,quantity: Number(input.value)}));
    if (!lines.length) return message(localNotice, 'Enter a return quantity of at least 1 for one product.');
    mutation(detail, `/api/orders/${id}/returns`, {expected_version: order.version, lines}, async result => {
      notify(result.status === 'returned' ? 'All items returned. Stock has been restored.' : 'Partial return recorded. Returned units are back in stock.');
      await navigate('detail', {id, keepNotice: true});
    }, localNotice);
  }}, h('div', {class: 'table-wrap'}, table));
  if (canReturn) returnForm.append(h('div', {class: 'return-actions'}, h('h3', {}, 'Receive a return'),
    h('p', {}, 'Enter units received for each product. Leave other quantities at zero.'), h('button', {type: 'submit', class: 'primary', ...test('submit-return')}, 'Record return')));
  const actions = h('div', {class: 'action-stack'});
  if (writable()) {
    if (order.status === 'draft') actions.append(button('Reserve stock', {...test('reserve-order'), class: 'primary', onClick: () => transition('reserve')}));
    if (order.status === 'reserved') actions.append(button('Ship order', {...test('ship-order'), class: 'primary', onClick: () => transition('ship')}));
    if (['draft','reserved'].includes(order.status)) actions.append(button('Cancel order', {...test('cancel-order'), class: 'danger', onClick: () => transition('cancel')}));
  }
  const descriptions = {draft: 'Reserve every line to commit stock to this order.', reserved: 'Stock is reserved. Confirm shipment when the order leaves the warehouse.',
    shipped: 'The order has shipped. Receive partial or complete returns below.', cancelled: 'This order is closed. Any reserved stock was released.', returned: 'All ordered units have been returned to stock.'};
  detail.append(pageHeading(order.client_ref, 'Order detail', button('Refresh order', {onClick: refresh})), localNotice,
    h('div', {class: 'detail-grid'}, h('section', {class: 'card'}, h('div', {class: 'card-head'}, h('h2', {}, 'Products'), h('span', {class: 'badge-count'}, `${order.lines.length} ${order.lines.length === 1 ? 'line' : 'lines'}`)), returnForm),
      h('aside', {class: 'card card-body'}, h('div', {class: 'eyebrow'}, 'Order summary'), badge(order.status),
        h('div', {class: 'detail-meta'}, h('p', {}, 'Version ', h('strong', {}, order.version))),
        h('p', {class: 'stat-value'}, money(order.total_cents)), h('p', {class: 'muted small'}, 'Original order total · Prices locked at creation'),
        h('p', {class: 'small'}, descriptions[order.status]), actions,
        h('p', {class: 'refresh-note mono'}, id))));
  detail.querySelector('h1').classList.add('order-ref');
  setPage(button('← Back to orders', {class: 'link back', onClick: () => navigate('orders')}), detail);
}

async function renderAudit(epoch) {
  const data = await api('/api/audit?limit=20'); if (epoch !== state.epoch) return;
  const tbody = h('tbody');
  const append = items => items.forEach(event => {
    const details = event.details || {}, stock = details.stock || [];
    const inspection = h('details', {class: 'audit-detail'}, h('summary', {}, 'Inspect change'),
      h('p', {class: 'mono'}, `Entity: ${event.entity_id}`), details.reason ? h('p', {}, `Reason: ${details.reason}`) : null,
      details.order ? h('p', {}, `Order version ${details.order.version} · ${details.order.status} · ${money(details.order.total_cents)}`) : null,
      stock.length ? h('ul', {}, stock.map(change => h('li', {}, h('strong', {}, change.sku),
        ` · On hand ${change.before.on_hand} → ${change.after.on_hand}; reserved ${change.before.reserved} → ${change.after.reserved}; stock version ${change.after.version}.`))) : h('p', {}, 'No stock quantity changed.'));
    tbody.append(h('tr', {}, h('td', {}, h('span', {class: 'audit-action'}, event.action.replaceAll('.', ' · ')),
      h('span', {class: 'audit-ref'}, details.client_ref || event.entity_id), inspection),
      h('td', {}, event.actor), h('td', {}, h('time', {dateTime: event.created_at}, new Date(event.created_at).toLocaleString())), h('td', {class: 'numeric muted'}, `#${event.id}`)));
  });
  append(data.items);
  const table = h('table', {...test('audit-table'), class: 'audit-table'}, h('caption', {class: 'visually-hidden'}, 'Tenant activity, oldest first'),
    h('thead', {}, h('tr', {}, ['Activity / reference','Performed by','Time','Event'].map(text => h('th', {scope: 'col'}, text)))), tbody);
  setPage(pageHeading('Activity log', 'A committed history of orders and inventory. Oldest events appear first.', button('Refresh', {onClick: () => navigate('audit')})),
    h('section', {class: 'card'}, h('div', {class: 'table-wrap'}, table), !data.items.length ? empty('No activity yet', 'Order and inventory changes will appear here.') : null,
      pagination(data.next_cursor, async cursor => {const next = await api(`/api/audit?limit=20&cursor=${encodeURIComponent(cursor)}`); if (epoch === state.epoch) append(next.items); return next;})));
}

(async () => {
  if (!state.token) return renderLogin();
  root.append(h('div', {class: 'loading', role: 'status'}, 'Opening your workspace…'));
  try {state.user = await api('/api/me'); renderShell(); await navigate('inventory');}
  catch (_) {renderLogin();}
})();
