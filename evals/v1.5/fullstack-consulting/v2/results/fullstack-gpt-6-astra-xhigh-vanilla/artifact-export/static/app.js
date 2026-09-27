'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const state = {token: sessionStorage.getItem('depot-token'), user: null, page: 'inventory', inventory: [], dashboard: null,
  orders: [], orderCursor: null, filters: {q: '', status: ''}, detail: null, composing: false, audit: [], auditCursor: null, busy: false, epoch: 0};
let intents;
try { intents = JSON.parse(sessionStorage.getItem('depot-intents') || '{}'); } catch { intents = {}; }
const money = cents => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(cents / 100);
const number = n => new Intl.NumberFormat('en-US').format(n);
const writable = () => state.user?.role !== 'viewer';

// All variable text is inserted as text nodes; user input is never interpreted as markup.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (key === 'class') node.className = value;
    else if (key === 'value') node.value = value;
    else if (value !== false && value != null) node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) if (child != null) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}
const button = (text, attrs = {}) => el('button', {type: 'button', ...attrs}, text);
const badge = status => el('span', {class: `pill ${status}`}, status);
function field(label, input, className = '') { return el('div', {class: className}, el('label', {for: input.id}, label), input); }
function showNotice(message, error = false, refresh = false) {
  const box = $('#notice'); box.hidden = false; box.className = error ? 'error' : '';
  box.replaceChildren(document.createTextNode(message));
  if (refresh) box.append(button('Refresh record · keep input', {onclick: refreshPreservingInput}));
}
function clearNotice() { $('#notice').hidden = true; }
function handleError(error) { showNotice(error.message, true, error.code === 'stale_version'); }

async function api(path, options = {}) {
  const headers = {...options.headers};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  let response;
  try { response = await fetch(`/api${path}`, {...options, headers, body: options.body === undefined ? undefined : JSON.stringify(options.body)}); }
  catch { throw new Error('Cannot reach DepotFlow. Your input is saved on this page. Retry the same action when connected.'); }
  let data;
  try { data = await response.json(); } catch { throw new Error('The server returned an unreadable response. Retry the same action.'); }
  if (!response.ok) {
    const error = new Error(data.error?.message || `Request failed (${response.status}).`);
    error.code = data.error?.code; error.status = response.status;
    if (response.status === 401 && path !== '/session') {
      showLogin('Your session expired. Sign in again.');
    }
    throw error;
  }
  return data;
}

async function mutate(path, payload) {
  const signature = `${state.user.tenant}:${path}:${JSON.stringify(payload)}`;
  const key = intents[signature] || crypto.randomUUID();
  intents[signature] = key; sessionStorage.setItem('depot-intents', JSON.stringify(intents));
  const result = await api(path, {method: 'POST', body: payload, headers: {'Idempotency-Key': key}});
  delete intents[signature]; sessionStorage.setItem('depot-intents', JSON.stringify(intents));
  return result;
}

async function pending(form, task) {
  if (state.busy) return;
  state.busy = true; clearNotice(); form?.setAttribute('aria-busy', 'true');
  const controls = [...document.querySelectorAll('button, input, select')];
  const previouslyDisabled = controls.map(node => node.disabled);
  controls.forEach(node => { node.disabled = true; });
  const status = el('p', {class: 'help', role: 'status'}, 'Saving changes…');
  form?.append(status);
  try { await task(); } catch (error) { handleError(error); }
  finally { controls.forEach((node, i) => { node.disabled = previouslyDisabled[i]; }); status.remove(); form?.removeAttribute('aria-busy'); state.busy = false; }
}

async function loadOverview() {
  const [inventory, dashboard] = await Promise.all([api('/inventory'), api('/dashboard')]);
  state.inventory = inventory.items; state.dashboard = dashboard;
}

function heading(eyebrow, title, description, action) {
  return el('div', {class: 'page-head'}, el('div', {}, el('p', {class: 'eyebrow'}, eyebrow), el('h1', {}, title), el('p', {class: 'muted'}, description)), action);
}
function panel(title, body, extra) {
  return el('section', {class: 'panel'}, el('div', {class: 'panel-head'}, el('h2', {}, title), extra), body);
}
function table(headers, rows, testid) {
  rows.forEach(row => [...row.children].forEach((cell, index) => cell.dataset.label = headers[index]));
  return el('div', {class: 'table-scroll', tabindex: '0', role: 'region', 'aria-label': 'Data table; scroll to see additional columns'}, el('table', {'data-testid': testid},
    el('thead', {}, el('tr', {}, headers.map(text => el('th', {scope: 'col'}, text)))), el('tbody', {}, rows)));
}
function stats() {
  const data = state.dashboard;
  const values = [['On hand', data.inventory_units, 'Units across your catalog'], ['Reserved', data.reserved_units, 'Committed to open orders'],
    ['Ready to ship', data.orders_by_status.reserved || 0, 'Orders with stock reserved'], ['Shipped', data.orders_by_status.shipped || 0, 'Includes partial returns']];
  return el('div', {class: 'stats'}, values.map(([name, value, sub]) => el('div', {class: 'stat'}, el('div', {class: 'stat-label'}, name), el('div', {class: 'stat-value'}, number(value)), el('div', {class: 'stat-sub'}, sub))));
}

function renderInventory() {
  const root = $('#page-content'); root.replaceChildren(heading('STOCK CONTROL', 'Inventory & overview', 'Live stock, reserved units, and the next orders to move.', button('Refresh', {onclick: () => navigate('inventory')})), stats());
  const rows = state.inventory.map(item => el('tr', {},
    el('td', {}, el('span', {class: 'sku'}, item.sku), el('span', {class: 'name-sub'}, item.name)),
    el('td', {class: 'num'}, number(item.on_hand)), el('td', {class: 'num'}, number(item.reserved)),
    el('td', {class: 'num available'}, number(item.available)), el('td', {class: 'num'}, money(item.price_cents)), el('td', {class: 'num'}, item.version)));
  root.append(panel('Stock ledger', table(['Item', 'On hand', 'Reserved', 'Available', 'Unit price', 'Version'], rows, 'inventory-table'), el('span', {class: 'pill'}, `${rows.length} SKUs`)));
  if (state.user.role === 'admin') root.append(adjustmentForm());
  else root.append(el('p', {class: 'help'}, state.user.role === 'viewer' ? 'Viewer access · You can inspect inventory, orders, and activity.' : 'Stock adjustments are available to your organization’s admin.'));
}

function skuSelect(id, testid, selected) {
  const select = el('select', {id, 'data-testid': testid, required: true}, state.inventory.map(item => el('option', {value: item.sku}, `${item.sku} · ${item.name}`)));
  if (selected) select.value = selected; return select;
}
function adjustmentForm(saved = {}) {
  const sku = skuSelect('adjust-sku', 'adjust-sku', saved.sku);
  const delta = el('input', {id: 'adjust-delta', type: 'number', step: '1', required: true, value: saved.delta || '', placeholder: 'e.g. 12 or -3'});
  const reason = el('input', {id: 'adjust-reason', required: true, maxlength: '1000', value: saved.reason || '', placeholder: 'Delivery received, cycle count…'});
  const versionNote = el('p', {class: 'help'});
  const updateNote = () => { versionNote.textContent = `Using stock version ${state.inventory.find(item => item.sku === sku.value).version}. Changes are checked before saving.`; };
  sku.addEventListener('change', updateNote); updateNote();
  const form = el('form', {id: 'adjustment-form', class: 'panel-body'}, el('div', {class: 'form-grid'}, field('SKU', sku), field('Change in units (+ / −)', delta), field('Reason', reason)), versionNote,
    el('div', {class: 'form-actions'}, el('button', {type: 'submit', class: 'primary'}, 'Adjust stock')));
  form.addEventListener('submit', event => {
    event.preventDefault();
    const payload = {sku: sku.value, delta: Number(delta.value), reason: reason.value, expected_version: state.inventory.find(item => item.sku === sku.value).version};
    pending(form, async () => { await mutate('/stock/adjustments', payload); await loadOverview(); renderInventory(); showNotice(`Stock adjusted for ${payload.sku}. Activity recorded.`); });
  });
  return panel('Adjust stock', form, el('span', {class: 'pill'}, 'Admin'));
}

function orderQuery(cursor) {
  const query = new URLSearchParams({limit: '20'});
  if (state.filters.status) query.set('status', state.filters.status);
  if (state.filters.q) query.set('q', state.filters.q);
  if (cursor) query.set('cursor', cursor);
  return `/orders?${query}`;
}
async function loadOrders(append = false) {
  const data = await api(orderQuery(append ? state.orderCursor : null));
  state.orders = append ? state.orders.concat(data.items) : data.items; state.orderCursor = data.next_cursor;
}
function renderOrders() {
  const root = $('#page-content');
  root.replaceChildren(heading('FULFILLMENT', 'Orders', 'Take each order from draft to delivery, and back when needed.',
    writable() ? button('+ New order', {'data-testid': 'new-order', class: 'primary', onclick: () => { state.composing = true; state.detail = null; renderOrders(); $('#order-client-ref').focus(); }}) : el('span', {class: 'pill'}, 'View only')));
  if (state.composing && writable()) root.append(orderForm());
  if (state.detail) root.append(orderDetail());
  const search = el('input', {id: 'order-search', type: 'search', maxlength: 200, value: state.filters.q, placeholder: 'Search client reference'});
  const status = el('select', {id: 'order-status'}, el('option', {value: ''}, 'All statuses'), ['draft', 'reserved', 'shipped', 'cancelled', 'returned'].map(s => el('option', {value: s}, s[0].toUpperCase() + s.slice(1))));
  status.value = state.filters.status;
  const form = el('form', {class: 'filter-bar'}, field('Client reference', search, 'search'), field('Status', status), el('button', {type: 'submit'}, 'Apply filters'));
  form.addEventListener('submit', event => { event.preventDefault(); pending(form, async () => { state.filters = {q: search.value, status: status.value}; await loadOrders(); renderOrders(); }); });
  const content = el('div', {}, form);
  if (!state.orders.length) content.append(el('div', {class: 'empty'}, el('strong', {}, 'No orders to display'), 'Create an order or change your filters.'));
  else content.append(table(['Reference', 'Status', 'Items', 'Total', ''], state.orders.map(order => el('tr', {},
    el('td', {class: 'order-ref'}, button(order.client_ref, {class: 'text-button', onclick: () => openOrder(order.id)})), el('td', {}, badge(order.status)),
    el('td', {}, number(order.lines.reduce((sum, line) => sum + line.quantity, 0))), el('td', {}, money(order.total_cents)),
    el('td', {}, button('View', {class: 'small', 'aria-label': `View ${order.client_ref}`, onclick: () => openOrder(order.id)}))))));
  if (state.orderCursor) content.append(el('div', {class: 'list-footer'}, button('Load more orders', {onclick: event => pending(event.currentTarget.parentElement, async () => { await loadOrders(true); renderOrders(); })})));
  root.append(panel('Order register', content, el('span', {class: 'muted'}, `${state.orders.length} shown · oldest first`)));
}

function orderForm() {
  const ref = el('input', {id: 'order-client-ref', 'data-testid': 'order-client-ref', required: true, maxlength: 200, placeholder: 'e.g. NORTH-1042'});
  const rows = el('div', {id: 'order-lines'}); let lineId = 0;
  function addLine() {
    const index = lineId++;
    const existing = [...rows.querySelectorAll('select')].map(node => node.value);
    const selected = state.inventory.find(item => !existing.includes(item.sku))?.sku;
    const sku = skuSelect(`line-sku-${index}`, 'line-sku', selected);
    const quantity = el('input', {id: `line-quantity-${index}`, 'data-testid': 'line-quantity', type: 'number', min: '1', step: '1', required: true, value: '1'});
    const row = el('div', {class: 'line-row'}, field('Item / SKU', sku), field('Quantity', quantity), button('Remove', {class: 'remove quiet', 'aria-label': `Remove line ${index + 1}`, onclick: () => { if (rows.children.length > 1) { row.remove(); updateTotal(); } else showNotice('Keep at least one order line.', true); }}));
    rows.append(row); sku.addEventListener('change', updateTotal); quantity.addEventListener('input', updateTotal); updateTotal();
  }
  const total = el('p', {class: 'help'});
  function updateTotal() { let cents = 0; rows.querySelectorAll('.line-row').forEach(row => { cents += state.inventory.find(item => item.sku === $('select', row).value).price_cents * Number($('input', row).value); }); total.textContent = `Catalog total: ${money(cents)} · Prices are confirmed by the server.`; }
  const form = el('form', {class: 'panel-body', id: 'create-order-form'}, field('Client reference', ref), rows,
    el('div', {class: 'form-actions'}, button('+ Add line', {'data-testid': 'add-line', onclick: addLine})), total,
    el('div', {class: 'form-actions'}, el('button', {type: 'submit', class: 'primary', 'data-testid': 'submit-order'}, 'Create draft order'),
      button('Close', {onclick: () => { state.composing = false; renderOrders(); }})));
  addLine();
  form.addEventListener('submit', event => { event.preventDefault();
    const payload = {client_ref: ref.value, lines: [...rows.children].map(row => ({sku: $('select', row).value, quantity: Number($('input', row).value)}))};
    pending(form, async () => { state.detail = await mutate('/orders', payload); state.composing = false; await Promise.all([loadOrders(), loadOverview()]); renderOrders(); showNotice('Draft created. Reserve stock when the order is ready.'); $('[data-testid="order-detail"]').focus(); });
  });
  return panel('New order', form, el('span', {class: 'pill draft'}, 'Draft'));
}

async function openOrder(id) {
  if (state.busy) return;
  const root = $('#page-content');
  await pending(root, async () => { state.detail = await api(`/orders/${id}`); state.composing = false; renderOrders(); $('[data-testid="order-detail"]').focus(); });
}

function orderDetail(savedReturns = {}) {
  const order = state.detail;
  const canReturn = writable() && order.status === 'shipped';
  const form = el('form', {id: 'return-form'});
  const headers = ['Item', 'Ordered', 'Unit price', 'Returned'];
  if (canReturn) headers.push('Return now');
  const rows = order.lines.map(line => {
    const cells = [el('td', {}, el('span', {class: 'sku'}, line.sku)), el('td', {}, line.quantity), el('td', {}, money(line.unit_price_cents)), el('td', {}, `${line.returned_quantity} / ${line.quantity}`)];
    if (canReturn) {
      const remaining = line.quantity - line.returned_quantity;
      cells.push(el('td', {}, el('div', {class: 'return-field'}, el('label', {for: `return-${line.sku}`}, line.sku), el('input', {id: `return-${line.sku}`, 'data-testid': 'return-quantity', 'data-sku': line.sku, type: 'number', min: '0', max: remaining, step: '1', value: savedReturns[line.sku] ?? '0', disabled: remaining === 0}))));
    }
    return el('tr', {}, cells);
  });
  form.append(table(headers, rows));
  const actions = el('div', {class: 'detail-actions'});
  if (writable()) {
    if (order.status === 'draft') actions.append(button('Reserve stock', {'data-testid': 'reserve-order', class: 'primary', onclick: () => act('reserve')}));
    if (order.status === 'reserved') actions.append(button('Ship order', {'data-testid': 'ship-order', class: 'primary', onclick: () => act('ship')}));
    if (['draft', 'reserved'].includes(order.status)) actions.append(button('Cancel order', {'data-testid': 'cancel-order', class: 'danger', onclick: () => act('cancel')}));
    if (canReturn) actions.append(el('button', {type: 'submit', class: 'primary', 'data-testid': 'submit-return'}, 'Receive return'), el('p', {class: 'help'}, 'Enter units received for each item. Leave other lines at 0.'));
  }
  actions.append(button('Refresh order', {onclick: refreshPreservingInput}), button('Close detail', {onclick: () => { state.detail = null; renderOrders(); }}));
  form.append(actions);
  form.addEventListener('submit', event => { event.preventDefault();
    const lines = [...form.querySelectorAll('[data-testid="return-quantity"]')].map(input => ({sku: input.dataset.sku, quantity: Number(input.value)})).filter(line => line.quantity !== 0);
    if (!lines.length) { showNotice('Enter at least one positive return quantity.', true); return; }
    act('returns', lines);
  });
  async function act(action, lines) {
    const payload = {expected_version: order.version}; if (lines) payload.lines = lines;
    await pending(form, async () => { state.detail = await mutate(`/orders/${order.id}/${action}`, payload); await Promise.all([loadOrders(), loadOverview()]); renderOrders(); showNotice(`Order ${state.detail.client_ref}: ${action === 'returns' ? 'return received' : state.detail.status}. Inventory and activity are updated.`); });
  }
  return el('section', {class: 'panel', 'data-testid': 'order-detail', tabindex: '-1'},
    el('div', {class: 'panel-head'}, el('h2', {class: 'order-ref'}, order.client_ref), badge(order.status)),
    el('div', {class: 'panel-body'}, el('div', {class: 'order-detail-meta'}, el('span', {}, 'Total ', el('strong', {}, money(order.total_cents))), el('span', {}, 'Version ', el('strong', {}, order.version))), el('p', {class: 'help'}, `Order ID: ${order.id}`)), form);
}

async function refreshPreservingInput() {
  const savedReturns = Object.fromEntries([...document.querySelectorAll('[data-testid="return-quantity"]')].map(input => [input.dataset.sku, input.value]));
  const adjustment = $('#adjustment-form') ? {sku: $('#adjust-sku').value, delta: $('#adjust-delta').value, reason: $('#adjust-reason').value} : null;
  await pending($('#page-content'), async () => {
    await loadOverview();
    if (state.page === 'orders' && state.detail) {
      state.detail = await api(`/orders/${state.detail.id}`); await loadOrders(); renderOrders();
      $('[data-testid="order-detail"]').replaceWith(orderDetail(savedReturns));
    } else if (state.page === 'inventory') {
      renderInventory(); if (adjustment) $('#adjustment-form').closest('.panel').replaceWith(adjustmentForm(adjustment));
    }
    showNotice('Current record loaded. Your input was kept; review it before submitting again.');
  });
}

async function loadAudit(append = false) {
  const query = new URLSearchParams({limit: '20'}); if (append && state.auditCursor) query.set('cursor', state.auditCursor);
  const data = await api(`/audit?${query}`); state.audit = append ? state.audit.concat(data.items) : data.items; state.auditCursor = data.next_cursor;
}
function renderAudit() {
  const root = $('#page-content'); root.replaceChildren(heading('TRACEABILITY', 'Activity log', 'A committed record of every stock and order change.', button('Refresh', {onclick: () => navigate('audit')})));
  const body = el('div', {}, table(['Event', 'Entity', 'Actor', 'Recorded at'], state.audit.map(item => el('tr', {},
    el('td', {}, el('strong', {}, item.action), el('div', {class: 'help'}, `Event #${item.id}`), item.details ? el('details', {class: 'audit-details'}, el('summary', {}, 'Change details'), el('pre', {}, JSON.stringify(item.details, null, 2))) : null),
    el('td', {class: 'audit-entity'}, item.entity_id.length === 32 ? button(item.entity_id, {class: 'text-button audit-entity', onclick: async () => { await navigate('orders'); await openOrder(item.entity_id); }}) : item.entity_id),
    el('td', {}, item.actor), el('td', {}, el('time', {datetime: item.created_at}, new Date(item.created_at).toLocaleString())))), 'audit-table'));
  if (!state.audit.length) body.append(el('div', {class: 'empty'}, el('strong', {}, 'No activity yet'), 'Successful stock adjustments and order changes appear here.'));
  if (state.auditCursor) body.append(el('div', {class: 'list-footer'}, button('Load more activity', {onclick: event => pending(event.currentTarget.parentElement, async () => { await loadAudit(true); renderAudit(); })})));
  root.append(panel('Warehouse activity', body, el('span', {class: 'muted'}, 'Oldest first')));
}

async function navigate(page) {
  state.page = page; state.detail = null; state.composing = false; clearNotice();
  const epoch = ++state.epoch;
  document.querySelectorAll('[data-page]').forEach(node => { if (node.dataset.page === page) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current'); });
  $('#page-content').replaceChildren(el('div', {class: 'loading', role: 'status'}, 'Loading warehouse records…'));
  try {
    if (page === 'inventory') await loadOverview();
    else if (page === 'orders') await Promise.all([loadOrders(), loadOverview()]);
    else await loadAudit();
    if (epoch !== state.epoch || !state.user) return;
    ({inventory: renderInventory, orders: renderOrders, audit: renderAudit})[page]();
  } catch (error) { if (epoch !== state.epoch) return; $('#page-content').replaceChildren(el('div', {class: 'empty'}, 'Records could not be loaded.', button('Try again', {onclick: () => navigate(page)}))); handleError(error); }
}

function showLogin(message = '') {
  state.token = null; state.user = null; ++state.epoch; sessionStorage.removeItem('depot-token');
  $('#login-screen').hidden = false; $('#app').hidden = true; $('#login-error').textContent = message;
}
async function showApp(user) {
  state.user = user; $('#login-screen').hidden = true; $('#app').hidden = false;
  $('#account-label').replaceChildren(el('span', {class: 'account-label-tenant'}, `${user.tenant} warehouse`), document.createTextNode(` · ${user.role} · ${user.email}`));
  await navigate('inventory');
}
$('#login-form').addEventListener('submit', async event => {
  event.preventDefault(); const submit = $('[data-testid="login-submit"]'); if (submit.disabled) return;
  submit.disabled = true; submit.textContent = 'Signing in…'; $('#login-error').textContent = '';
  try { const data = await api('/session', {method: 'POST', body: {email: $('#login-email').value, password: $('#login-password').value}});
    state.token = data.token; sessionStorage.setItem('depot-token', data.token); $('#login-password').value = ''; await showApp(data.user);
  } catch (error) { $('#login-error').textContent = error.message; } finally { submit.disabled = false; submit.textContent = 'Sign in'; }
});
$('#logout').addEventListener('click', () => { intents = {}; sessionStorage.removeItem('depot-intents'); state.filters = {q: '', status: ''}; $('#page-content').replaceChildren(); showLogin(); $('#login-email').focus(); });
document.querySelectorAll('[data-page]').forEach(node => node.addEventListener('click', () => navigate(node.dataset.page)));
if (state.token) { api('/me').then(showApp).catch(() => showLogin('Sign in to open your workspace.')); }
