/* DepotFlow's UI intentionally uses textContent and DOM APIs for user data. */
const state = { token: localStorage.getItem('depotflow-token'), user: null, view: 'inventory', inventory: [], orders: [], selected: null, dashboard: null, audit: [], busy: false, message: null, error: null };
const app = document.querySelector('#app');

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === 'className') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'htmlFor') node.htmlFor = value;
    else if (key.startsWith('data-')) node.setAttribute(key, value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
    else node[key] = value;
  }
  for (const child of children) node.append(child);
  return node;
}
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function button(label, props = {}) { return el('button', { type: 'button', text: label, ...props }); }
function showError(message) { state.error = message; state.message = null; render(); }
function showMessage(message) { state.message = message; state.error = null; render(); }
function money(cents) { return `$${(cents / 100).toFixed(2)}`; }
function apiError(data, status) { return data?.error?.message || `Request failed (${status})`; }
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body !== undefined) { headers['Content-Type'] = 'application/json'; headers['Idempotency-Key'] ||= crypto.randomUUID(); options.body = JSON.stringify(options.body); }
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && path !== '/api/session') { logout(false); throw new Error('Your session is no longer valid.'); }
  if (!response.ok) throw new Error(apiError(data, response.status));
  return data;
}
async function loadUser() { if (!state.token) return false; try { state.user = await api('/api/me'); return true; } catch { state.token = null; localStorage.removeItem('depotflow-token'); return false; } }
async function refreshDashboard() { state.dashboard = await api('/api/dashboard'); }
async function refreshInventory() { state.inventory = (await api('/api/inventory')).items; }
async function refreshOrders() { state.orders = (await api('/api/orders?limit=100')).items; }
async function refreshAudit() { state.audit = (await api('/api/audit?limit=100')).items; }
async function refreshAll() { await Promise.all([refreshDashboard(), refreshInventory(), refreshOrders(), refreshAudit()]); }

function loginView() {
  const form = el('form', { className: 'login-card form-stack', onsubmit: async e => { e.preventDefault(); if (state.busy) return; state.busy = true; render(); const email = form.querySelector('[data-testid="login-email"]').value; const password = form.querySelector('[data-testid="login-password"]').value; try { const data = await api('/api/session', { method: 'POST', body: { email, password } }); state.token = data.token; state.user = data.user; localStorage.setItem('depotflow-token', state.token); await refreshAll(); state.view = 'inventory'; state.error = null; } catch (error) { state.error = error.message; } finally { state.busy = false; render(); } } }, [
    el('div', { className: 'eyebrow', text: 'Warehouse operations' }), el('h1', { text: 'DepotFlow' }), el('p', { className: 'muted', text: 'Receive, reserve, ship, and reconcile orders with tenant-safe inventory.' }),
    state.error ? el('div', { className: 'error', role: 'alert', text: state.error }) : document.createTextNode(''),
    el('label', { htmlFor: 'login-email', text: 'Email' }, [el('input', { id: 'login-email', type: 'email', required: true, autocomplete: 'username', 'data-testid': 'login-email' })]),
    el('label', { htmlFor: 'login-password', text: 'Password' }, [el('input', { id: 'login-password', type: 'password', required: true, autocomplete: 'current-password', 'data-testid': 'login-password' })]),
    button(state.busy ? 'Signing in…' : 'Sign in', { type: 'submit', className: 'primary', disabled: state.busy, 'data-testid': 'login-submit' }),
    el('p', { className: 'muted small', text: 'Demo users use the synthetic password DepotDemo!2026.' })
  ]);
  return el('div', { className: 'login-wrap' }, [form]);
}
function header() {
  const out = button('Log out', { className: 'secondary', 'data-testid': 'logout', onclick: () => logout(true) });
  return el('header', { className: 'topbar' }, [el('div', {}, [el('div', { className: 'brand', text: 'DepotFlow' }), el('small', { text: 'Fulfillment control center' })]), el('div', { className: 'topbar-actions' }, [el('small', { text: `${state.user.email} · ${state.user.role} · ${state.user.tenant}` }), out])]);
}
function nav() {
  const items = [['inventory', 'Inventory', 'nav-inventory'], ['orders', 'Orders', 'nav-orders'], ['audit', 'Audit trail', 'nav-audit']];
  return el('nav', { className: 'nav', 'aria-label': 'Primary navigation' }, items.map(([view, label, testid]) => button(label, { className: state.view === view ? 'active' : '', 'data-testid': testid, onclick: () => { state.view = view; state.error = null; state.message = null; render(); } })));
}
function shell(content) { return el('div', { className: 'shell' }, [header(), nav(), el('main', {}, [state.error ? el('div', { className: 'error', role: 'alert', text: state.error }) : document.createTextNode(''), state.message ? el('div', { className: 'success', role: 'status', text: state.message }) : document.createTextNode(''), content])]); }
function metric(label, value) { return el('div', { className: 'card metric' }, [el('span', { className: 'muted small', text: label }), el('strong', { text: String(value) })]); }
function adjustmentCard() {
  const form = el('form', { className: 'card form-stack', onsubmit: async e => { e.preventDefault(); if (state.busy) return; const sku = form.querySelector('select').value; const item = state.inventory.find(entry => entry.sku === sku); state.busy = true; render(); try { await api('/api/stock/adjustments', { method: 'POST', body: { sku, delta: Number(form.querySelector('[name="delta"]').value), expected_version: item.version, reason: form.querySelector('[name="reason"]').value } }); await refreshAll(); showMessage(`Stock adjustment for ${sku} saved.`); } catch (error) { state.error = error.message; } finally { state.busy = false; render(); } } }, [el('h2', { text: 'Admin stock adjustment' }), el('div', { className: 'line-row' }, [el('label', { text: 'SKU' }, [el('select', {}, state.inventory.map(item => el('option', { value: item.sku, text: item.sku })))]), el('label', { text: 'Signed delta' }, [el('input', { name: 'delta', type: 'number', step: '1', required: true, placeholder: 'e.g. 5' })]), document.createTextNode('')]), el('label', { text: 'Reason' }, [el('input', { name: 'reason', required: true, placeholder: 'Cycle count correction' })]), button(state.busy ? 'Saving…' : 'Adjust stock', { type: 'submit', className: 'primary', disabled: state.busy })]);
  return form;
}
function inventoryView() {
  const dash = state.dashboard || { orders_by_status: {}, inventory_units: 0, reserved_units: 0 };
  const counts = dash.orders_by_status || {};
  const rows = state.inventory.map(item => el('tr', {}, [el('td', { text: item.sku }), el('td', { text: item.name }), el('td', { text: String(item.on_hand) }), el('td', { text: String(item.reserved) }), el('td', { text: String(item.available) }), el('td', { text: money(item.price_cents) }), el('td', { text: `v${item.version}` })]));
  const table = el('table', { 'data-testid': 'inventory-table' }, [el('thead', {}, [el('tr', {}, ['SKU', 'Name', 'On hand', 'Reserved', 'Available', 'Price', 'Version'].map(text => el('th', { scope: 'col', text })))]), el('tbody', {}, rows)]);
  return el('div', { className: 'grid' }, [el('div', { className: 'section-heading' }, [el('div', {}, [el('div', { className: 'eyebrow', text: 'Overview' }), el('h1', { text: 'Inventory & dashboard' })]), button('Refresh', { className: 'secondary', onclick: async () => { try { await refreshAll(); showMessage('Dashboard refreshed.'); } catch (e) { showError(e.message); } } })]), el('div', { className: 'grid metrics' }, [metric('Inventory units', dash.inventory_units), metric('Reserved units', dash.reserved_units), metric('Open orders', (counts.draft || 0) + (counts.reserved || 0)), metric('Shipped / returned', (counts.shipped || 0) + (counts.returned || 0))]), el('section', { className: 'card' }, [el('h2', { text: 'Stock position' }), state.inventory.length ? el('div', { className: 'table-wrap' }, [table]) : el('div', { className: 'empty', text: 'No inventory items found.' })]), state.user.role === 'admin' && state.inventory.length ? adjustmentCard() : document.createTextNode('')]);
}
function newOrderCard() {
  if (state.user.role === 'viewer') return el('div', { className: 'card notice', text: 'Viewer access is read-only. Ask an operator or admin to create or transition orders.' });
  const form = el('form', { className: 'card form-stack', 'data-testid': 'new-order', onsubmit: async e => { e.preventDefault(); if (state.busy) return; state.busy = true; render(); try { const lines = [...form.querySelectorAll('.line-row')].map(row => ({ sku: row.querySelector('[data-testid="line-sku"]').value, quantity: Number(row.querySelector('[data-testid="line-quantity"]').value) })); const data = await api('/api/orders', { method: 'POST', body: { client_ref: form.querySelector('[data-testid="order-client-ref"]').value, lines } }); state.selected = data; await refreshAll(); showMessage(`Order ${data.client_ref} created.`); } catch (error) { state.error = error.message; } finally { state.busy = false; render(); } } }, [el('h2', { text: 'New order' }), el('label', { htmlFor: 'order-client-ref', text: 'Client reference' }, [el('input', { id: 'order-client-ref', required: true, placeholder: 'e.g. PO-1042', 'data-testid': 'order-client-ref' })]), el('div', { id: 'line-editor' }), el('div', { className: 'button-row' }, [button('Add line', { type: 'button', className: 'secondary', 'data-testid': 'add-line', onclick: () => addLine(form) }), button(state.busy ? 'Creating…' : 'Create draft order', { type: 'submit', className: 'primary', disabled: state.busy, 'data-testid': 'submit-order' })])]);
  addLine(form);
  return form;
}
function addLine(form) { const editor = form.querySelector('#line-editor'); const row = el('div', { className: 'line-row' }, [el('label', { text: 'SKU' }, [el('select', { 'data-testid': 'line-sku', required: true }, state.inventory.map(item => el('option', { value: item.sku, text: `${item.sku} — ${item.name}` })))]), el('label', { text: 'Quantity' }, [el('input', { type: 'number', min: '1', step: '1', value: '1', required: true, 'data-testid': 'line-quantity' })]), button('Remove', { type: 'button', className: 'danger', onclick: () => { if (editor.children.length > 1) row.remove(); } })]); editor.append(row); }
function ordersView() {
  const filter = el('input', { type: 'search', placeholder: 'Search client reference', value: state.orderSearch || '', oninput: e => { state.orderSearch = e.target.value; renderOrdersTable(tableWrap, e.target.value); } });
  const tableWrap = el('div', { className: 'table-wrap' });
  renderOrdersTable(tableWrap, state.orderSearch || '');
  return el('div', { className: 'grid' }, [el('div', { className: 'section-heading' }, [el('div', {}, [el('div', { className: 'eyebrow', text: 'Workflow' }), el('h1', { text: 'Orders' })]), el('div', { className: 'button-row' }, [filter, button('Refresh', { className: 'secondary', onclick: async () => { try { await refreshAll(); render(); } catch (e) { showError(e.message); } } })])]), el('div', { className: 'two-col grid' }, [newOrderCard(), el('section', { className: 'card' }, [el('h2', { text: 'Order queue' }), tableWrap])]), state.selected ? orderDetail() : document.createTextNode('')]);
}
function renderOrdersTable(container, search) { clear(container); const items = state.orders.filter(order => order.client_ref.toLowerCase().includes(search.toLowerCase())); if (!items.length) { container.append(el('div', { className: 'empty', text: 'No matching orders.' })); return; } const table = el('table', {}, [el('thead', {}, [el('tr', {}, ['Reference', 'Status', 'Total', 'Version'].map(text => el('th', { scope: 'col', text })))]), el('tbody', {}, items.map(order => el('tr', {}, [el('td', {}, [button(order.client_ref, { className: 'order-link', onclick: () => { state.selected = order; state.error = null; render(); } })]), el('td', {}, [el('span', { className: `status ${order.status}`, text: order.status })]), el('td', { text: money(order.total_cents) }), el('td', { text: `v${order.version}` })])))]); container.append(table); }
function orderDetail() {
  const order = state.selected; if (!order) return document.createTextNode('');
  const canMutate = state.user.role !== 'viewer'; const action = async (name, body, label) => { if (state.busy) return; state.busy = true; render(); try { state.selected = await api(`/api/orders/${order.id}/${name}`, { method: 'POST', body }); await refreshAll(); showMessage(`${label} completed.`); } catch (e) { state.error = e.message; } finally { state.busy = false; render(); } };
  const actions = [];
  if (canMutate && order.status === 'draft') actions.push(button('Reserve stock', { className: 'primary', disabled: state.busy, 'data-testid': 'reserve-order', onclick: () => action('reserve', { expected_version: order.version }, 'Reservation') }));
  if (canMutate && order.status === 'reserved') actions.push(button('Ship order', { className: 'primary', disabled: state.busy, 'data-testid': 'ship-order', onclick: () => action('ship', { expected_version: order.version }, 'Shipment') }));
  if (canMutate && ['draft', 'reserved'].includes(order.status)) actions.push(button('Cancel order', { className: 'danger', disabled: state.busy, 'data-testid': 'cancel-order', onclick: () => action('cancel', { expected_version: order.version }, 'Cancellation') }));
  if (canMutate && order.status === 'shipped') { const returnForm = el('form', { className: 'form-stack', onsubmit: e => { e.preventDefault(); const lines = [...returnForm.querySelectorAll('[data-testid="return-quantity"]')].map(input => ({ sku: input.dataset.sku, quantity: Number(input.value) })).filter(line => line.quantity > 0); if (!lines.length) { showError('Enter at least one return quantity.'); return; } action('returns', { expected_version: order.version, lines }, 'Return'); } }, [el('h3', { text: 'Record return' })]); returnForm.append(...order.lines.map(line => el('label', { text: `${line.sku} (shipped ${line.quantity - line.returned_quantity}, returned ${line.returned_quantity})` }, [el('input', { type: 'number', min: '0', max: String(line.quantity - line.returned_quantity), value: '0', 'data-testid': 'return-quantity', 'data-sku': line.sku })]))); returnForm.append(button('Submit return', { type: 'submit', className: 'primary', disabled: state.busy, 'data-testid': 'submit-return' })); actions.push(returnForm); }
  const lineRows = order.lines.map(line => el('tr', {}, [el('td', { text: line.sku }), el('td', { text: String(line.quantity) }), el('td', { text: money(line.unit_price_cents) }), el('td', { text: String(line.returned_quantity) })]));
  return el('section', { className: 'card', 'data-testid': 'order-detail' }, [el('div', { className: 'section-heading' }, [el('div', {}, [el('div', { className: 'eyebrow', text: 'Order detail' }), el('h2', { text: order.client_ref }), el('span', { className: `status ${order.status}`, text: order.status })]), el('div', { className: 'button-row' }, actions)]), el('p', { className: 'muted small', text: `Order ID ${order.id} · version ${order.version} · total ${money(order.total_cents)}` }), el('div', { className: 'table-wrap' }, [el('table', {}, [el('thead', {}, [el('tr', {}, ['SKU', 'Quantity', 'Unit price', 'Returned'].map(text => el('th', { scope: 'col', text })))]), el('tbody', {}, lineRows)])])]);
}
function auditView() { const rows = state.audit.map(event => el('tr', {}, [el('td', { text: String(event.id) }), el('td', { text: event.action }), el('td', { text: event.entity_id }), el('td', { text: event.actor }), el('td', { text: event.created_at })])); return el('div', { className: 'grid' }, [el('div', { className: 'section-heading' }, [el('div', {}, [el('div', { className: 'eyebrow', text: 'Traceability' }), el('h1', { text: 'Audit trail' })]), button('Refresh', { className: 'secondary', onclick: async () => { try { await refreshAudit(); showMessage('Audit refreshed.'); } catch (e) { showError(e.message); } } })]), el('section', { className: 'card' }, [state.audit.length ? el('div', { className: 'table-wrap' }, [el('table', { 'data-testid': 'audit-table' }, [el('thead', {}, [el('tr', {}, ['ID', 'Action', 'Entity', 'Actor', 'Created'].map(text => el('th', { scope: 'col', text })))]), el('tbody', {}, rows)])]) : el('div', { className: 'empty', 'data-testid': 'audit-table', text: 'No audit events yet.' })])]); }
function logout(show) { state.token = null; state.user = null; state.selected = null; localStorage.removeItem('depotflow-token'); if (show) { state.message = 'Signed out.'; } render(); }
function render() { clear(app); if (!state.user) { app.append(loginView()); return; } const content = state.view === 'orders' ? ordersView() : state.view === 'audit' ? auditView() : inventoryView(); app.append(shell(content)); }

(async () => { if (await loadUser()) { try { await refreshAll(); } catch (e) { state.error = e.message; } } render(); })();
