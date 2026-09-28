'use strict';

const $app = document.getElementById('app');
const state = {
  token: sessionStorage.getItem('depotflow-token'), user: null, view: 'inventory', busy: false,
  notice: null, inventory: [], dashboard: null, orders: null, audit: null, detail: null,
  showNew: false, showAdjust: false, ref: '', lines: [{sku: 'BOLT', quantity: '1'}], returns: {},
  adjustment: {sku: 'BOLT', delta: '', reason: '', version: null},
  filters: {q: '', status: ''}, draftFilters: {q: '', status: ''},
  orderCursors: [null], auditCursors: [null], uncertain: null,
  loginEmail: '', loginPassword: '', loading: false,
};
const money = value => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(value / 100);
const count = value => new Intl.NumberFormat('en-US').format(value);
const writable = () => state.user && state.user.role !== 'viewer';
const currentCursor = key => state[key][state[key].length - 1];

// Every piece of server/user text becomes a text node; no HTML interpolation.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'class') node.className = value;
    else if (key === 'value') node.value = value;
    else if (key === 'checked' || key === 'disabled') node[key] = value;
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child !== null && child !== undefined && child !== false)
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
const button = (text, testid, action, cls = 'primary', attrs = {}) =>
  el('button', {type: 'button', class: cls, 'data-testid': testid, onclick: action, ...attrs}, text);
const badge = status => el('span', {class: `badge badge-${status}`}, status);
const brand = () => el('div', {class: 'brand'}, el('span', {class: 'brand-mark', 'aria-hidden': 'true'}, '▤'), 'DepotFlow');
function field(label, control, hint) {
  return el('div', {class: 'field'}, el('label', {for: control.id}, label), control, hint && el('small', {}, hint));
}
function input(id, value, oninput, attrs = {}) {
  return el('input', {id, value, oninput: event => oninput(event.target.value), ...attrs});
}
function select(id, value, choices, onChange, attrs = {}) {
  const node = el('select', {id, onchange: event => onChange(event.target.value), ...attrs},
    choices.map(([v, label]) => el('option', {value: v}, label)));
  node.value = value;
  return node;
}
const skuChoices = () => state.inventory.map(item => [item.sku, `${item.sku} · ${item.name}`]);
function notice() {
  if (!state.notice) return null;
  return el('div', {class: `notice ${state.notice.kind}`, role: state.notice.kind === 'error' ? 'alert' : 'status'},
    state.notice.message,
    state.uncertain && button('Retry original request', 'retry-mutation', () => executeMutation(state.uncertain), 'secondary', {disabled: state.busy}),
    state.notice.retryRead && button('Refresh data', 'retry-read', refresh, 'secondary', {disabled: state.busy}));
}

class RequestError extends Error {
  constructor(status, code, message) { super(message); this.status = status; this.code = code; }
}
async function api(path, {method = 'GET', body, key} = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const headers = {};
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (key) headers['Idempotency-Key'] = key;
    const response = await fetch(path, {method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal});
    const data = await response.json();
    if (!response.ok) throw new RequestError(response.status, data.error?.code, data.error?.message || 'Request failed.');
    return data;
  } finally { clearTimeout(timeout); }
}
function handleError(error) {
  if (error.status === 401 && state.user) {
    logout();
    state.notice = {kind: 'error', message: 'Your session expired. Sign in again.'};
  } else {
    state.notice = {kind: 'error', message: error.message || 'Unable to reach the local server.'};
  }
}
function ordersPath() {
  const params = new URLSearchParams({limit: '10'});
  if (state.filters.status) params.set('status', state.filters.status);
  if (state.filters.q) params.set('q', state.filters.q);
  if (currentCursor('orderCursors')) params.set('cursor', currentCursor('orderCursors'));
  return `/api/orders?${params}`;
}
function auditPath() {
  const params = new URLSearchParams({limit: '15'});
  if (currentCursor('auditCursors')) params.set('cursor', currentCursor('auditCursors'));
  return `/api/audit?${params}`;
}
async function loadData() {
  const [inventory, dashboard, orders, audit] = await Promise.all([
    api('/api/inventory'), api('/api/dashboard'), api(ordersPath()), api(auditPath()),
  ]);
  state.inventory = inventory.items; state.dashboard = dashboard; state.orders = orders; state.audit = audit;
}
async function refresh() {
  if (state.busy) return;
  state.busy = true; render();
  try {
    await loadData();
    if (state.detail) state.detail = await api(`/api/orders/${state.detail.id}`);
    if (state.showAdjust) state.adjustment.version = state.inventory.find(item => item.sku === state.adjustment.sku)?.version;
    state.notice = {kind: 'info', message: 'Latest data loaded. Any form entries have been kept.'};
  } catch (error) { handleError(error); state.notice.retryRead = true; }
  finally { state.busy = false; render(); }
}
async function executeMutation(intent) {
  if (state.busy) return;
  state.busy = true; state.notice = {kind: 'info', message: 'Saving changes…'}; render();
  let result;
  try {
    sessionStorage.setItem('depotflow-pending', JSON.stringify(intent));
    result = await api(intent.path, {method: 'POST', body: intent.body, key: intent.key});
  } catch (error) {
    if (!error.status || error.status >= 500) {
      state.uncertain = intent;
      state.notice = {kind: 'error', message: 'The server did not confirm the result. Your request is kept. Retry the original request safely before making another change.'};
    } else {
      state.uncertain = null;
      sessionStorage.removeItem('depotflow-pending');
      handleError(error);
      if (error.code === 'stale_version') {
        try {
          await loadData();
          if (state.detail) state.detail = await api(`/api/orders/${state.detail.id}`);
          state.adjustment.version = state.inventory.find(item => item.sku === state.adjustment.sku)?.version;
          state.notice.message += ' Latest values are now shown; your input has been kept.';
        } catch (_) { state.notice.message += ' Use Refresh to load the latest version.'; }
      }
    }
    state.busy = false; render(); return;
  }
  state.uncertain = null;
  sessionStorage.removeItem('depotflow-pending');
  if (intent.kind !== 'adjust') state.view = 'orders';
  if (intent.kind === 'create') {
    state.detail = result; state.showNew = false; state.ref = ''; state.lines = [{sku: 'BOLT', quantity: '1'}]; state.returns = {};
  } else if (intent.kind === 'adjust') {
    state.showAdjust = false; state.adjustment = {sku: 'BOLT', delta: '', reason: '', version: null};
  } else { state.detail = result; state.returns = {}; }
  state.orderCursors = [null]; state.auditCursors = [null];
  state.notice = {kind: 'success', message: intent.message};
  try {
    await loadData();
    if (state.detail) state.detail = await api(`/api/orders/${state.detail.id}`);
  }
  catch (_) { state.notice = {kind: 'error', message: `${intent.message} The change is saved, but some views could not refresh.`, retryRead: true}; }
  state.busy = false; render();
  document.querySelector('[data-testid="order-detail"]')?.focus({preventScroll: true});
}
function mutate(path, body, kind, message) {
  if (state.busy || state.uncertain) return;
  executeMutation({path, body, kind, message, key: crypto.randomUUID()});
}
function logout() {
  sessionStorage.removeItem('depotflow-token');
  sessionStorage.removeItem('depotflow-pending');
  state.token = null; state.user = null; state.detail = null; state.notice = null; state.uncertain = null;
  state.inventory = []; state.dashboard = null; state.orders = null; state.audit = null;
  state.showNew = false; state.showAdjust = false; state.ref = ''; state.lines = [{sku: 'BOLT', quantity: '1'}];
  state.adjustment = {sku: 'BOLT', delta: '', reason: '', version: null};
  state.returns = {}; state.filters = {q: '', status: ''}; state.draftFilters = {q: '', status: ''};
  state.orderCursors = [null]; state.auditCursors = [null]; state.loginPassword = ''; state.view = 'inventory'; render();
}
async function signIn(event) {
  event.preventDefault(); if (state.busy) return;
  state.busy = true; state.notice = {kind: 'info', message: 'Signing in…'}; render();
  try {
    const result = await api('/api/session', {method: 'POST', body: {email: state.loginEmail, password: state.loginPassword}});
    state.token = result.token; state.user = result.user; state.loginPassword = '';
    sessionStorage.setItem('depotflow-token', result.token);
    await loadData(); state.notice = null;
  } catch (error) { handleError(error); if (state.user) state.notice.retryRead = true; }
  finally { state.busy = false; render(); }
}
function loginView() {
  return el('div', {class: 'login-shell'},
    el('section', {class: 'login-story'}, brand(),
      el('div', {}, el('div', {class: 'eyebrow'}, 'THE FULFILLMENT WORKSPACE'),
        el('h1', {}, 'A clear path from shelf to shipment.'),
        el('p', {}, 'Orders, stock, and every step in between. Keep your warehouse moving with one shared source of truth.'),
        el('div', {class: 'flow-diagram', 'aria-hidden': 'true'}, el('span', {class: 'flow-step'}, '01  Receive'), '→', el('span', {class: 'flow-step'}, '02  Reserve'), '→', el('span', {class: 'flow-step'}, '03  Ship'))),
      el('div', {class: 'login-footer'}, 'DepotFlow / Local operations, connected.')),
    el('main', {class: 'login-main'}, el('div', {class: 'login-card'},
      el('div', {class: 'eyebrow'}, 'WELCOME BACK'), el('h1', {}, 'Sign in to your depot'),
      el('p', {class: 'muted'}, 'Your workspace is linked to your account.'), notice(),
      el('form', {onsubmit: signIn}, el('fieldset', {disabled: state.busy},
        field('Email address', input('email', state.loginEmail, v => state.loginEmail = v, {type: 'email', autocomplete: 'username', required: true, 'data-testid': 'login-email', placeholder: 'operator@north.example'})),
        field('Password', input('password', state.loginPassword, v => state.loginPassword = v, {type: 'password', autocomplete: 'current-password', required: true, 'data-testid': 'login-password'})),
        el('button', {type: 'submit', class: 'primary', 'data-testid': 'login-submit'}, state.busy ? 'Signing in…' : 'Open workspace →'))),
      el('div', {class: 'demo-note'}, el('strong', {}, 'Local demo accounts'), el('br'), 'Use admin, operator, or viewer at ', el('code', {}, 'north.example'), ' or ', el('code', {}, 'south.example'), '.', el('br'), 'Password: ', el('code', {}, 'DepotDemo!2026')))));
}
function heading(title, subtitle, action) {
  return el('div', {class: 'page-heading'}, el('div', {}, el('div', {class: 'eyebrow'}, 'WAREHOUSE OPERATIONS'), el('h1', {}, title), el('p', {}, subtitle)), action);
}
function metric(label, value, note) {
  return el('div', {class: 'metric'}, el('div', {class: 'metric-label'}, label), el('div', {class: 'metric-value'}, count(value)), el('div', {class: 'metric-note'}, note));
}
function table(headers, rows, testid) {
  return el('div', {class: 'table-scroll'}, el('table', {'data-testid': testid},
    el('thead', {}, el('tr', {}, headers.map(h => el('th', {scope: 'col'}, h)))), el('tbody', {}, rows)));
}
function adjustmentForm() {
  const draft = state.adjustment;
  return el('section', {class: 'panel'}, el('div', {class: 'panel-header'}, el('h2', {}, 'Adjust stock'),
    button('Close', 'close-adjustment', () => {state.showAdjust = false; render();}, 'text-button', {disabled: state.busy})),
    el('form', {class: 'panel-body', onsubmit: event => {
      event.preventDefault(); mutate('/api/stock/adjustments', {sku: draft.sku, delta: Number(draft.delta), expected_version: draft.version, reason: draft.reason}, 'adjust', 'Stock adjustment saved.');
    }}, el('fieldset', {disabled: state.busy || !!state.uncertain},
      el('div', {class: 'form-grid'},
        field('Product', select('adjust-sku', draft.sku, skuChoices(), value => {draft.sku = value; draft.version = state.inventory.find(i => i.sku === value).version;}, {'data-testid': 'adjust-sku'})),
        field('Quantity change', input('adjust-delta', draft.delta, value => draft.delta = value, {type: 'number', step: '1', min: '-1000000000', max: '1000000000', required: true, 'data-testid': 'adjust-delta'}), 'Positive to receive stock, negative to remove stock.')),
      field('Reason', input('adjust-reason', draft.reason, value => draft.reason = value, {required: true, maxlength: '1000', 'data-testid': 'adjust-reason', placeholder: 'e.g. Supplier delivery or cycle count correction'})),
      el('button', {type: 'submit', class: 'primary', 'data-testid': 'submit-adjustment'}, 'Save adjustment'))));
}
function inventoryView() {
  const d = state.dashboard;
  return el('div', {}, heading('Inventory overview', 'Know what’s on the shelf, committed, and ready to go.',
    state.user.role === 'admin' && button('+ Adjust stock', 'adjust-stock', () => {
      state.showAdjust = !state.showAdjust; state.adjustment.version = state.inventory.find(i => i.sku === state.adjustment.sku)?.version; render();
    }, 'primary', {disabled: state.busy || !!state.uncertain})),
    d && el('div', {class: 'metrics'}, metric('On hand', d.inventory_units, 'Total physical units'),
      metric('Reserved', d.reserved_units, 'Committed to open orders'), metric('Available', d.inventory_units - d.reserved_units, 'Ready for a new order'),
      metric('Awaiting shipment', d.orders_by_status.reserved || 0, 'Reserved orders')),
    state.showAdjust && adjustmentForm(),
    el('section', {class: 'panel'}, el('div', {class: 'panel-header'}, el('h2', {}, 'Stock catalog'), el('span', {class: 'muted'}, `${state.inventory.length} products`)),
      table(['Product', 'On hand', 'Reserved', 'Available', 'Unit price', 'Version'], state.inventory.map(item => el('tr', {},
        el('td', {}, el('div', {class: 'product'}, el('span', {class: 'sku'}, item.sku), el('small', {}, item.name))),
        el('td', {class: 'numeric'}, count(item.on_hand)), el('td', {class: 'numeric'}, count(item.reserved)),
        el('td', {class: 'numeric stock-number'}, count(item.available)), el('td', {class: 'numeric'}, money(item.price_cents)),
        el('td', {class: 'numeric muted'}, item.version))), 'inventory-table'),
      !state.inventory.length && el('div', {class: 'empty'}, 'No products in this workspace.')),
    el('div', {class: 'hint'}, el('span', {'aria-hidden': 'true'}, '↳'), el('span', {}, el('strong', {}, 'From shelf to shipment. '), 'Reserving commits available stock. Shipping removes those units from the shelf. Returns put them back into available stock.')),
    d && el('section', {class: 'panel status-panel'}, el('div', {class: 'panel-header'}, el('h2', {}, 'Order activity')),
      el('div', {class: 'panel-body actions'}, Object.entries(d.orders_by_status).map(([status, n]) => el('span', {}, badge(status), ` ${n} `)))));
}
function newOrderForm() {
  const total = state.lines.reduce((sum, line) => sum + (state.inventory.find(i => i.sku === line.sku)?.price_cents || 0) * (Number(line.quantity) || 0), 0);
  return el('section', {class: 'panel'}, el('div', {class: 'panel-header'}, el('h2', {}, 'Create an order'),
    button('Close', 'close-new-order', () => {state.showNew = false; render();}, 'text-button', {disabled: state.busy})),
    el('form', {class: 'panel-body', onsubmit: event => {
      event.preventDefault(); mutate('/api/orders', {client_ref: state.ref, lines: state.lines.map(line => ({sku: line.sku, quantity: Number(line.quantity)}))}, 'create', 'Order created. Reserve stock when it is ready to fulfill.');
    }}, el('fieldset', {disabled: state.busy || !!state.uncertain},
      field('Client reference', input('client-ref', state.ref, value => state.ref = value, {required: true, maxlength: '200', 'data-testid': 'order-client-ref', placeholder: 'e.g. WEB-1042'}), 'A unique reference for this workspace.'),
      state.lines.map((line, index) => el('div', {class: 'line-row'},
        field(`Product · line ${index + 1}`, select(`line-sku-${index}`, line.sku, skuChoices(), value => {line.sku = value; render();}, {'data-testid': 'line-sku'})),
        field('Quantity', input(`line-qty-${index}`, line.quantity, value => {
          line.quantity = value;
          const totalNode = document.getElementById('create-total');
          if (totalNode) totalNode.textContent = money(state.lines.reduce((sum, l) => sum + (state.inventory.find(i => i.sku === l.sku)?.price_cents || 0) * (Number(l.quantity) || 0), 0));
        }, {type: 'number', min: '1', max: '1000000000', step: '1', required: true, 'data-testid': 'line-quantity'})),
        state.lines.length > 1 && button('Remove line', null, () => {state.lines.splice(index, 1); render();}, 'text-button', {'aria-label': `Remove line ${index + 1}`}))),
      button('+ Add line', 'add-line', () => {
        state.lines.push({sku: state.inventory.find(item => !state.lines.some(line => line.sku === item.sku))?.sku || 'BOLT', quantity: '1'}); render();
      }, 'secondary', {disabled: state.lines.length >= 100}),
      el('p', {class: 'detail-total'}, 'Order total ', el('span', {id: 'create-total'}, money(total))),
      el('div', {class: 'form-actions'}, el('span', {class: 'muted'}, 'Stock is committed when reserved.'),
        el('button', {type: 'submit', class: 'primary', 'data-testid': 'submit-order'}, 'Create order')))));
}
async function openOrder(id) {
  if (state.busy) return;
  state.busy = true; state.notice = {kind: 'info', message: 'Loading order…'}; render();
  try { state.detail = await api(`/api/orders/${id}`); state.returns = {}; state.notice = null; }
  catch (error) { handleError(error); }
  state.busy = false; render();
  document.querySelector('[data-testid="order-detail"]')?.focus();
}
async function changePage(kind, cursor, back = false) {
  if (state.busy) return;
  const key = kind === 'orders' ? 'orderCursors' : 'auditCursors';
  const old = [...state[key]];
  if (back) state[key].pop(); else state[key].push(cursor);
  state.busy = true; render();
  try { state[kind] = await api(kind === 'orders' ? ordersPath() : auditPath()); }
  catch (error) { state[key] = old; handleError(error); }
  state.busy = false; render();
}
function pagination(kind, data) {
  const cursors = state[kind === 'orders' ? 'orderCursors' : 'auditCursors'];
  return el('div', {class: 'pagination'}, `Page ${cursors.length} · oldest first`, el('div', {class: 'actions'},
    button('Previous', `${kind}-previous`, () => changePage(kind, null, true), 'secondary', {disabled: state.busy || cursors.length <= 1}),
    button('Next', `${kind}-next`, () => changePage(kind, data.next_cursor), 'secondary', {disabled: state.busy || !data.next_cursor})));
}
function detailView() {
  const detail = state.detail;
  const transitionAction = (action, message) => mutate(`/api/orders/${detail.id}/${action}`, {expected_version: detail.version}, action, message);
  const locked = state.busy || !!state.uncertain;
  return el('section', {class: 'panel', 'data-testid': 'order-detail', tabindex: '-1', 'aria-label': 'Order detail'},
    el('div', {class: 'panel-header'}, el('div', {}, el('h2', {class: 'detail-title'}, detail.client_ref),
      el('div', {class: 'detail-meta'}, badge(detail.status), `Version ${detail.version}`)),
      button('Close', 'close-detail', () => {state.detail = null; render();}, 'text-button', {disabled: state.busy})),
    table(['SKU', 'Ordered', 'Unit price', 'Returned'], detail.lines.map(line => el('tr', {}, el('td', {class: 'sku'}, line.sku),
      el('td', {class: 'numeric'}, line.quantity), el('td', {class: 'numeric'}, money(line.unit_price_cents)), el('td', {class: 'numeric'}, line.returned_quantity)))),
    el('div', {class: 'detail-total'}, 'Order total ', money(detail.total_cents)),
    writable() && ['draft', 'reserved'].includes(detail.status) && el('div', {class: 'detail-actions'}, el('div', {class: 'actions'},
      detail.status === 'draft' && button('Reserve stock', 'reserve-order', () => transitionAction('reserve', 'Stock reserved. This order is ready to ship.'), 'primary', {disabled: locked}),
      detail.status === 'reserved' && button('Ship order', 'ship-order', () => transitionAction('ship', 'Order shipped. Stock and history are up to date.'), 'primary', {disabled: locked})),
      button('Cancel order', 'cancel-order', () => transitionAction('cancel', 'Order cancelled. Any reserved stock has been released.'), 'danger', {disabled: locked})),
    writable() && detail.status === 'shipped' && el('form', {class: 'return-form', onsubmit: event => {
      event.preventDefault(); const lines = detail.lines.map(line => ({sku: line.sku, quantity: Number(state.returns[line.sku] || 0)})).filter(line => line.quantity !== 0);
      if (!lines.length) {state.notice = {kind: 'error', message: 'Enter at least one quantity to return.'}; render(); return;}
      mutate(`/api/orders/${detail.id}/returns`, {expected_version: detail.version, lines}, 'returns', 'Return received. Inventory and order history have been updated.');
    }}, el('h3', {}, 'Receive a return'), el('p', {class: 'muted'}, 'Enter only the units arriving back at the warehouse.'),
      el('fieldset', {disabled: locked}, el('div', {class: 'return-lines'}, detail.lines.map(line =>
        field(`${line.sku} · ${line.quantity - line.returned_quantity} returnable`, input(`return-${line.sku}`, state.returns[line.sku] || '0', value => state.returns[line.sku] = value,
          {type: 'number', min: '0', max: String(line.quantity - line.returned_quantity), step: '1', 'data-testid': 'return-quantity', disabled: line.quantity === line.returned_quantity})))),
        el('button', {type: 'submit', class: 'primary', 'data-testid': 'submit-return'}, 'Receive return'))),
    ['returned', 'cancelled'].includes(detail.status) && el('div', {class: 'panel-body muted'}, detail.status === 'returned' ? 'All shipped units have been returned to inventory.' : 'This order is closed. No stock remains reserved.'),
    !writable() && el('div', {class: 'panel-body muted'}, 'Viewer access · You can inspect this order and its history.'));
}
function ordersView() {
  const data = state.orders;
  return el('div', {}, heading('Orders', 'From the first line item to the final delivery.', writable() && button('+ New order', 'new-order', () => {state.showNew = true; render(); document.getElementById('client-ref')?.focus();}, 'primary', {disabled: state.busy || !!state.uncertain})),
    state.showNew && newOrderForm(), el('div', {class: `order-layout ${state.detail ? 'with-detail' : ''}`},
      el('section', {class: 'panel'}, el('div', {class: 'panel-header'}, el('h2', {}, 'Order register'), el('span', {class: 'muted'}, 'Oldest first')),
        el('form', {class: 'filters', onsubmit: async event => {
          event.preventDefault(); if (state.busy) return;
          state.filters = {...state.draftFilters}; state.orderCursors = [null]; state.busy = true; render();
          try {state.orders = await api(ordersPath());} catch (error) {handleError(error);}
          state.busy = false; render();
        }}, field('Search reference', input('order-search', state.draftFilters.q, value => state.draftFilters.q = value, {type: 'search', maxlength: '200', placeholder: 'Search client reference…', 'data-testid': 'order-search'})),
          field('Status', select('status-filter', state.draftFilters.status, [['', 'All statuses'], ...['draft', 'reserved', 'shipped', 'cancelled', 'returned'].map(s => [s, s])], value => state.draftFilters.status = value, {'data-testid': 'order-status'})),
          el('button', {type: 'submit', class: 'secondary', disabled: state.busy, 'data-testid': 'apply-filters'}, 'Apply')),
        data?.items.length ? table(['Reference', 'Status', 'Total'], data.items.map(item => el('tr', {},
          el('td', {}, button(item.client_ref, 'open-order', () => openOrder(item.id), 'text-button', {disabled: state.busy})),
          el('td', {}, badge(item.status)), el('td', {class: 'numeric'}, money(item.total_cents))))) :
          el('div', {class: 'empty'}, el('strong', {}, 'No orders here yet'), 'Create an order or try a different search.'),
        data && pagination('orders', data)), state.detail && detailView()));
}
function auditView() {
  const data = state.audit;
  return el('div', {}, heading('Activity history', 'A committed record of every inventory and order change.'),
    el('section', {class: 'panel'}, el('div', {class: 'panel-header'}, el('h2', {}, 'Workspace audit trail'), el('span', {class: 'muted'}, 'Oldest first')),
      table(['Event', 'Entity', 'Actor', 'Time', 'Details'], (data?.items || []).map(item => el('tr', {},
        el('td', {}, badge(item.action.replace('.', ' '))),
        el('td', {class: 'audit-id', title: item.entity_id}, item.action.startsWith('order.') ? button(item.entity_id.slice(0, 8), null, () => {state.view = 'orders'; openOrder(item.entity_id);}, 'text-button', {disabled: state.busy, 'aria-label': `Open order ${item.entity_id}`}) : item.entity_id),
        el('td', {}, item.actor), el('td', {}, new Date(item.created_at).toLocaleString()),
        el('td', {class: 'audit-details'}, item.details.reason || item.details.client_ref || (item.details.lines ? item.details.lines.map(line => `${line.sku} × ${line.quantity}`).join(', ') : 'Order status updated')))), 'audit-table'),
      !data?.items.length && el('div', {class: 'empty'}, el('strong', {}, 'Your history starts here'), 'Completed stock and order changes will appear in this view.'),
      data && pagination('audit', data)));
}
function shell() {
  return el('div', {class: 'shell'},
    el('aside', {class: 'sidebar'}, brand(), el('div', {class: 'workspace-tag'}, el('div', {class: 'eyebrow'}, 'CURRENT WORKSPACE'), el('strong', {}, `${state.user.tenant} depot`)),
      el('nav', {class: 'navigation', 'aria-label': 'Main navigation'}, [['inventory', 'Inventory', '▦'], ['orders', 'Orders', '▤'], ['audit', 'Activity', '◷']].map(([view, title, icon]) =>
        button([el('span', {class: 'nav-icon', 'aria-hidden': 'true'}, icon), title], `nav-${view}`, () => {state.view = view; render();}, `nav-button ${state.view === view ? 'active' : ''}`, {'aria-current': state.view === view ? 'page' : null, disabled: state.busy}))),
      el('div', {class: 'sidebar-bottom'}, el('div', {class: 'email'}, state.user.email), el('div', {class: 'role'}, `${state.user.role} access`), button('Sign out', 'logout', logout, 'logout', {disabled: state.busy || !!state.uncertain}))),
    el('main', {class: 'main', 'aria-busy': String(state.busy)},
      el('div', {class: 'topbar'}, el('span', {}, `${state.user.tenant.toUpperCase()} / ${state.user.role === 'viewer' ? 'VIEW ONLY' : 'FULFILLMENT'}`),
        el('div', {class: 'live'}, state.busy ? 'Updating…' : el('span', {class: 'dot', 'aria-hidden': 'true'}),
          button('Refresh', 'refresh', refresh, 'text-button', {disabled: state.busy}))),
      notice(), state.view === 'inventory' ? inventoryView() : state.view === 'orders' ? ordersView() : auditView()));
}
function render() { $app.replaceChildren(state.user ? shell() : loginView()); }
async function start() {
  render();
  if (!state.token) return;
  state.busy = true; state.notice = {kind: 'info', message: 'Restoring your workspace…'}; render();
  try {
    state.user = await api('/api/me'); await loadData(); state.notice = null;
    const pending = sessionStorage.getItem('depotflow-pending');
    if (pending) {
      state.uncertain = JSON.parse(pending);
      state.notice = {kind: 'error', message: 'A previous request has an unconfirmed result. Retry the original request safely before making another change.'};
    }
  }
  catch (error) {handleError(error); if (state.user) state.notice.retryRead = true; else {state.token = null; sessionStorage.removeItem('depotflow-token');}}
  state.busy = false; render();
}
start();
