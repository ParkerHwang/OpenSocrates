(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const state = {
    token: localStorage.getItem('depotflow_token') || '', user: null, view: 'inventory',
    inventory: [], dashboard: null, orders: [], orderCursor: null, selectedOrder: null,
    audit: [], auditCursor: null, notice: null, orderQuery: '', orderStatus: '',
    showOrderForm: false, draftClientRef: '', draftLines: [{ sku: 'BOLT', quantity: '1' }], busy: false, viewLoadId: 0,
  };

  function node(tag, attrs = {}, ...children) {
    const item = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (key === 'className') item.className = value;
      else if (key === 'text') item.textContent = value;
      else if (key === 'dataset') Object.entries(value).forEach(([name, data]) => item.dataset[name] = data);
      else if (key.startsWith('on') && typeof value === 'function') item.addEventListener(key.slice(2).toLowerCase(), value);
      else if (typeof value === 'boolean') { if (value) item.setAttribute(key, ''); }
      else if (value !== undefined && value !== null) item.setAttribute(key, String(value));
    });
    children.flat(Infinity).forEach(child => {
      if (child === undefined || child === null || child === false) return;
      item.append(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return item;
  }

  function button(label, attrs = {}) {
    return node('button', { type: 'button', className: 'button', ...attrs }, label);
  }

  function formatMoney(cents) {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(cents / 100);
  }

  function api(path, options = {}) {
    const headers = { Accept: 'application/json', ...(options.headers || {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    return fetch(path, { ...options, headers }).then(async response => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const issue = new Error(data?.error?.message || `Request failed (${response.status}).`);
        issue.status = response.status;
        issue.code = data?.error?.code || 'request_failed';
        throw issue;
      }
      return data;
    });
  }

  function setNotice(message, error = false) {
    state.notice = message ? { message, error } : null;
  }

  function showWorkspace() {
    $('#login-screen').hidden = true;
    $('#workspace').hidden = false;
    $('#account-label').textContent = `${state.user.email} · ${state.user.tenant} · ${state.user.role}`;
  }

  function showLogin() {
    state.token = '';
    state.user = null;
    state.view = 'inventory';
    state.inventory = [];
    state.dashboard = null;
    state.orders = [];
    state.selectedOrder = null;
    state.audit = [];
    state.orderQuery = '';
    state.orderStatus = '';
    state.showOrderForm = false;
    state.draftClientRef = '';
    state.draftLines = [{ sku: 'BOLT', quantity: '1' }];
    state.notice = null;
    state.viewLoadId += 1;
    localStorage.removeItem('depotflow_token');
    $('#workspace').hidden = true;
    $('#login-screen').hidden = false;
  }

  async function loadInventory() {
    const [inventory, dashboard] = await Promise.all([api('/api/inventory'), api('/api/dashboard')]);
    state.inventory = inventory.items;
    state.dashboard = dashboard;
  }

  async function loadOrders(reset = true) {
    if (reset) {
      state.orders = [];
      state.orderCursor = null;
    }
    const params = new URLSearchParams({ limit: '20' });
    if (state.orderQuery) params.set('q', state.orderQuery);
    if (state.orderStatus) params.set('status', state.orderStatus);
    if (!reset && state.orderCursor) params.set('cursor', state.orderCursor);
    const result = await api(`/api/orders?${params.toString()}`);
    state.orders = reset ? result.items : state.orders.concat(result.items);
    state.orderCursor = result.next_cursor;
  }

  async function loadAudit(reset = true) {
    if (reset) {
      state.audit = [];
      state.auditCursor = null;
    }
    const params = new URLSearchParams({ limit: '30' });
    if (!reset && state.auditCursor) params.set('cursor', state.auditCursor);
    const result = await api(`/api/audit?${params.toString()}`);
    state.audit = reset ? result.items : state.audit.concat(result.items);
    state.auditCursor = result.next_cursor;
  }

  async function refreshView() {
    const requestedView = state.view;
    try {
      if (requestedView === 'inventory') await loadInventory();
      if (requestedView === 'orders') {
        await Promise.all([loadInventory(), loadOrders()]);
        if (state.selectedOrder) state.selectedOrder = await api(`/api/orders/${encodeURIComponent(state.selectedOrder.id)}`);
      }
      if (requestedView === 'audit') await loadAudit();
      if (state.view !== requestedView) return;
      render();
    } catch (error) {
      setNotice(error.message, true);
      render();
    }
  }

  function appendNotice(container) {
    if (!state.notice) return;
    container.append(node('div', { className: `toast${state.notice.error ? ' error' : ''}`, role: 'status', 'aria-live': 'polite', text: state.notice.message }));
  }

  function pageHeading(title, description, action = null) {
    const left = node('div', {}, node('p', { className: 'eyebrow tight', text: 'DEPOTFLOW WORKSPACE' }), node('h1', { text: title }), node('p', { text: description }));
    const heading = node('div', { className: 'page-heading' }, left);
    if (action) heading.append(action);
    return heading;
  }

  function card(title, content, attrs = {}) {
    const box = node('section', { className: `panel card ${attrs.className || ''}` });
    const header = node('div', { className: 'card-heading' }, node('h2', { text: title }));
    if (attrs.action) header.append(attrs.action);
    box.append(header, content);
    return box;
  }

  function statCard(label, value, note = '') {
    return node('article', { className: 'panel stat-card' }, node('div', { className: 'stat-label', text: label }), node('div', { className: 'stat-value', text: value }), node('div', { className: 'stat-note', text: note }));
  }

  function table(headers, rows, testid, className = '') {
    const tableEl = node('table', { className: `data-table ${className}`, 'data-testid': testid });
    tableEl.append(node('thead', {}, node('tr', {}, headers.map(label => node('th', { scope: 'col', text: label })))));
    const body = node('tbody');
    rows.forEach(row => body.append(row));
    tableEl.append(body);
    return tableEl;
  }

  function renderInventory() {
    const root = $('#view');
    root.replaceChildren();
    appendNotice(root);
    root.append(pageHeading('Inventory', 'A live view of available stock and committed orders.'));
    const d = state.dashboard || { inventory_units: 0, reserved_units: 0, orders_by_status: {} };
    const available = state.inventory.reduce((sum, item) => sum + item.available, 0);
    const orderTotal = Object.values(d.orders_by_status).reduce((sum, n) => sum + n, 0);
    const draftCount = d.orders_by_status.draft || 0;
    root.append(node('div', { className: 'stats-grid' },
      statCard('Units on hand', d.inventory_units.toLocaleString(), `${state.inventory.length} catalog items`),
      statCard('Reserved units', d.reserved_units.toLocaleString(), 'Committed to open orders'),
      statCard('Available units', available.toLocaleString(), 'Ready to reserve'),
      statCard('Active orders', orderTotal.toLocaleString(), `${draftCount} awaiting reservation`),
    ));

    const stockRows = state.inventory.map(item => node('tr', {},
      node('td', { className: 'sku', text: item.sku }), node('td', { text: item.name }),
      node('td', { className: 'stock-value', text: item.on_hand.toLocaleString() }),
      node('td', { className: 'stock-value', text: item.reserved.toLocaleString() }),
      node('td', { className: `stock-value ${item.available < 5 ? 'low-stock' : ''}`, text: item.available.toLocaleString() }),
      node('td', { className: 'stock-value', text: formatMoney(item.price_cents) }),
    ));
    const inventoryTable = table(['SKU', 'Product', 'On hand', 'Reserved', 'Available', 'Unit price'], stockRows, 'inventory-table');
    const tableWrap = node('div', { className: 'table-wrap' }, inventoryTable);
    const stockCard = card('Stock by product', tableWrap, { action: button('Refresh', { className: 'button small', dataset: { action: 'refresh' } }) });
    const info = node('div', { className: 'panel card' }, node('div', { className: 'card-heading' }, node('h2', { text: 'Stock health' })),
      node('p', { className: 'muted', text: 'Reservations reduce availability immediately. Shipment reduces on-hand and reserved units together, so available stock stays steady through dispatch.' }),
      node('p', { className: 'subtle', text: 'Catalog prices are snapshotted when an order is created.' }));
    root.append(node('div', { className: 'content-grid' }, stockCard, info));

    if (state.user.role === 'admin') {
      const form = node('form', { id: 'adjustment-form', className: 'order-form' }, node('h3', { text: 'Adjust stock' }));
      const skuLabel = node('label', { className: 'field-label', for: 'adjust-sku', text: 'Product' });
      const skuSelect = node('select', { id: 'adjust-sku', className: 'control', name: 'sku' }, state.inventory.map(item => node('option', { value: item.sku, text: `${item.sku} · ${item.name}` })));
      const deltaLabel = node('label', { className: 'field-label', for: 'adjust-delta', text: 'Signed quantity change' });
      const delta = node('input', { id: 'adjust-delta', className: 'control', name: 'delta', type: 'number', step: '1', required: '', placeholder: 'e.g. 12 or -3' });
      const reasonLabel = node('label', { className: 'field-label', for: 'adjust-reason', text: 'Reason' });
      const reason = node('input', { id: 'adjust-reason', className: 'control', name: 'reason', required: '', maxlength: '500', placeholder: 'Receiving, count correction…' });
      form.append(skuLabel, skuSelect, deltaLabel, delta, reasonLabel, reason, node('div', { className: 'form-actions' }, node('button', { className: 'button primary', type: 'submit', text: 'Save adjustment' })));
      root.append(node('div', { className: 'panel card', style: 'margin-top:18px' }, form));
    }
  }

  function statusBadge(status) {
    return node('span', { className: `badge ${status}`, text: status });
  }

  function orderRow(order) {
    return node('tr', { dataset: { orderId: order.id } },
      node('td', {}, node('button', { className: 'order-ref-button', type: 'button', dataset: { action: 'select-order', orderId: order.id }, text: order.client_ref })),
      node('td', {}, statusBadge(order.status)), node('td', { text: formatMoney(order.total_cents) }),
      node('td', { className: 'stock-value', text: String(order.lines.length) }),
    );
  }

  function makeLineRow(line, index) {
    const wrap = node('div', { className: 'line-row' });
    const selectId = `line-sku-${index}`;
    const select = node('select', { id: selectId, className: 'control', 'data-testid': 'line-sku', 'aria-label': `Product for line ${index + 1}`, dataset: { lineIndex: index } },
      state.inventory.map(item => node('option', { value: item.sku, selected: item.sku === line.sku, text: `${item.sku} · ${item.name}` })));
    const quantity = node('input', { className: 'control', type: 'number', min: '1', step: '1', required: '', value: line.quantity, 'data-testid': 'line-quantity', 'aria-label': `Quantity for line ${index + 1}`, dataset: { lineIndex: index } });
    const remove = node('button', { className: 'icon-button', type: 'button', 'aria-label': `Remove line ${index + 1}`, title: 'Remove line', dataset: { action: 'remove-line', lineIndex: index }, text: '×' });
    wrap.append(select, quantity, remove);
    return wrap;
  }

  function orderForm() {
    const form = node('form', { id: 'order-form', className: 'order-form' });
    form.append(node('h3', { text: 'Create an order' }));
    const ref = node('input', { id: 'order-client-ref', className: 'control', name: 'client_ref', maxlength: '160', required: '', placeholder: 'e.g. PO-2048', value: state.draftClientRef, 'data-testid': 'order-client-ref' });
    form.append(node('label', { className: 'field-label', for: 'order-client-ref', text: 'Client reference' }), ref);
    form.append(node('div', { id: 'line-list', className: 'line-list' }, state.draftLines.map(makeLineRow)));
    form.append(node('div', { className: 'form-actions' },
      button('Add line', { className: 'button small', dataset: { action: 'add-line' }, 'data-testid': 'add-line' }),
      node('button', { className: 'button primary', type: 'submit', text: 'Create draft', 'data-testid': 'submit-order' }),
    ));
    return form;
  }

  function detailPanel() {
    const panel = node('section', { className: 'panel card detail-panel', 'data-testid': 'order-detail' });
    panel.append(node('div', { className: 'card-heading' }, node('h2', { text: 'Order detail' }), button('Refresh', { className: 'button small', dataset: { action: 'refresh-order' } })));
    const order = state.selectedOrder;
    if (!order) {
      panel.append(node('div', { className: 'detail-empty', text: 'Select an order to review its lines and available actions.' }));
      return panel;
    }
    panel.append(node('div', { className: 'detail-title-row' }, node('h3', { className: 'detail-ref', text: order.client_ref }), statusBadge(order.status)));
    panel.append(node('p', { className: 'detail-meta', text: `Order ${order.id} · Version ${order.version} · Total ${formatMoney(order.total_cents)}` }));
    const lineRows = order.lines.map(line => node('tr', {}, node('td', { className: 'sku', text: line.sku }), node('td', { className: 'stock-value', text: String(line.quantity) }), node('td', { className: 'stock-value', text: formatMoney(line.unit_price_cents) }), node('td', { className: 'stock-value', text: String(line.returned_quantity) })));
    panel.append(node('div', { className: 'table-wrap' }, table(['SKU', 'Qty', 'Unit price', 'Returned'], lineRows, 'order-lines-table', 'detail-table')));
    if (state.user.role !== 'viewer') {
      const actions = node('div', { className: 'action-row' });
      if (order.status === 'draft') actions.append(button('Reserve stock', { className: 'button primary', dataset: { action: 'transition', transition: 'reserve' }, 'data-testid': 'reserve-order' }));
      if (order.status === 'reserved') actions.append(button('Ship order', { className: 'button primary', dataset: { action: 'transition', transition: 'ship' }, 'data-testid': 'ship-order' }));
      if (['draft', 'reserved'].includes(order.status)) actions.append(button('Cancel order', { className: 'button danger', dataset: { action: 'transition', transition: 'cancel' }, 'data-testid': 'cancel-order' }));
      if (order.status === 'shipped') {
        const returnForm = node('form', { id: 'return-form', className: 'return-form' }, node('h3', { text: 'Record a return' }));
        order.lines.forEach(line => {
          const remaining = line.quantity - line.returned_quantity;
          const label = node('label', { className: 'return-line' }, node('span', { text: `${line.sku} · ${remaining} remaining` }), node('input', { className: 'control', type: 'number', min: '0', max: String(remaining), step: '1', value: '0', disabled: remaining === 0, 'aria-label': `Return quantity for ${line.sku}`, 'data-testid': 'return-quantity', dataset: { sku: line.sku, maximum: remaining } }));
          returnForm.append(label);
        });
        returnForm.append(node('button', { className: 'button primary small', type: 'submit', text: 'Submit return', 'data-testid': 'submit-return' }));
        actions.append(returnForm);
      }
      if (actions.childNodes.length) panel.append(actions);
    }
    return panel;
  }

  function renderOrders() {
    const root = $('#view');
    root.replaceChildren();
    appendNotice(root);
    const newButton = state.user.role === 'viewer' ? null : button(state.showOrderForm ? 'Close form' : 'New order', { className: 'button primary', dataset: { action: 'toggle-order-form' }, 'data-testid': 'new-order' });
    root.append(pageHeading('Orders', 'Create, reserve, ship, and return customer orders.', newButton));
    const filter = node('div', { className: 'filter-row' });
    const search = node('input', { className: 'search-control', type: 'search', placeholder: 'Search client reference', 'aria-label': 'Search orders', value: state.orderQuery, dataset: { action: 'search-orders' } });
    const status = node('select', { className: 'control select-control', 'aria-label': 'Filter by order status', dataset: { action: 'filter-status' } },
      [['', 'All statuses'], ...Array.from(['draft', 'reserved', 'shipped', 'returned', 'cancelled'], key => [key, key])].map(([value, label]) => node('option', { value, selected: value === state.orderStatus, text: label })));
    filter.append(search, status);
    const rows = state.orders.map(orderRow);
    const orderTable = rows.length ? table(['Client reference', 'Status', 'Total', 'Lines'], rows, 'orders-table', 'orders-table') : node('div', { className: 'empty', text: 'No orders match this view yet.' });
    const listBox = node('section', { className: 'panel card' }, node('div', { className: 'card-heading' }, node('h2', { text: 'Order queue' }), button('Refresh', { className: 'button small', dataset: { action: 'refresh-orders' } })), filter, node('div', { className: 'table-wrap' }, orderTable));
    if (state.orderCursor) listBox.append(button('Load more orders', { className: 'button small', dataset: { action: 'load-more-orders' } }));
    if (state.showOrderForm && state.user.role !== 'viewer') listBox.append(orderForm());
    root.append(node('div', { className: 'orders-layout' }, listBox, detailPanel()));
  }

  function renderAudit() {
    const root = $('#view');
    root.replaceChildren();
    appendNotice(root);
    root.append(pageHeading('Audit history', 'A tenant-scoped record of committed stock and order changes.'));
    const rows = state.audit.map(event => node('tr', {}, node('td', { className: 'stock-value', text: `#${event.id}` }), node('td', { className: 'audit-action', text: event.action }), node('td', { className: 'stock-value', text: event.entity_id }), node('td', { className: 'audit-actor', text: event.actor }), node('td', { text: new Date(event.created_at).toLocaleString() })));
    const contents = rows.length ? table(['Event', 'Action', 'Entity', 'Actor', 'Time'], rows, 'audit-table') : node('div', { className: 'empty', 'data-testid': 'audit-table', text: 'No committed changes yet.' });
    const box = node('section', { className: 'panel audit-card' }, node('div', { className: 'card-heading' }, node('h2', { text: 'Committed events' }), button('Refresh', { className: 'button small', dataset: { action: 'refresh-audit' } })), node('div', { className: 'table-wrap' }, contents));
    if (state.auditCursor) box.append(button('Load more events', { className: 'button small', dataset: { action: 'load-more-audit' } }));
    root.append(box);
  }

  function render() {
    document.querySelectorAll('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.view === state.view));
    if (!state.user) return;
    if (state.view === 'orders') renderOrders();
    else if (state.view === 'audit') renderAudit();
    else renderInventory();
  }

  async function loadInitialView() {
    const requestedView = state.view;
    const requestId = ++state.viewLoadId;
    renderLoading();
    try {
      if (requestedView === 'inventory') await loadInventory();
      if (requestedView === 'orders') await Promise.all([loadInventory(), loadOrders()]);
      if (requestedView === 'audit') await loadAudit();
      if (state.view !== requestedView || state.viewLoadId !== requestId) return;
      render();
    } catch (error) {
      if (state.view !== requestedView || state.viewLoadId !== requestId) return;
      setNotice(error.message, true);
      render();
    }
  }

  function renderLoading() {
    document.querySelectorAll('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.view === state.view));
    const title = state.view === 'orders' ? 'Orders' : state.view === 'audit' ? 'Audit history' : 'Inventory';
    const root = $('#view');
    root.replaceChildren(pageHeading(title, 'Loading the latest committed workspace data.'), node('div', { className: 'panel card empty', role: 'status', 'aria-live': 'polite', text: 'Loading…' }));
  }

  function idempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  async function mutate(path, payload, buttonEl) {
    if (state.busy) return;
    state.busy = true;
    const originalLabel = buttonEl?.textContent;
    if (buttonEl) buttonEl.disabled = true;
    if (buttonEl) buttonEl.textContent = 'Saving…';
    try {
      const result = await api(path, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey() }, body: JSON.stringify(payload) });
      if (path === '/api/orders') {
        state.selectedOrder = result;
        state.showOrderForm = false;
        state.draftClientRef = '';
        state.draftLines = [{ sku: state.inventory[0]?.sku || 'BOLT', quantity: '1' }];
        state.orderQuery = '';
        state.orderStatus = '';
      } else if (/\/api\/orders\/[^/]+\//.test(path)) {
        state.selectedOrder = result;
      }
      setNotice('Change saved. Inventory and history are up to date.');
      await Promise.all([loadInventory(), loadOrders(), loadAudit()]);
      if (state.selectedOrder) state.selectedOrder = await api(`/api/orders/${encodeURIComponent(state.selectedOrder.id)}`);
      render();
    } catch (error) {
      // Keep the current DOM and form values so stale-version or validation errors cannot erase user input.
      setNotice(`${error.message}${error.code === 'stale_version' ? ' Your inputs are still here; refresh the order when ready.' : ''}`, true);
      const previous = $('#view .toast');
      if (previous) previous.remove();
      const root = $('#view');
      if (root) root.prepend(node('div', { className: 'toast error', role: 'status', 'aria-live': 'polite', text: state.notice.message }));
      if (buttonEl) {
        buttonEl.disabled = false;
        buttonEl.textContent = originalLabel;
      }
    } finally {
      state.busy = false;
    }
  }

  function rememberLines() {
    const ref = $('#order-client-ref');
    if (ref) state.draftClientRef = ref.value;
    const selects = Array.from(document.querySelectorAll('[data-testid="line-sku"]'));
    const quantities = Array.from(document.querySelectorAll('[data-testid="line-quantity"]'));
    state.draftLines = selects.map((select, index) => ({ sku: select.value, quantity: quantities[index]?.value || '1' }));
  }

  $('#login-form').addEventListener('submit', async event => {
    event.preventDefault();
    const buttonEl = $('[data-testid="login-submit"]');
    const message = $('#login-message');
    buttonEl.disabled = true;
    message.textContent = 'Signing in…';
    message.classList.remove('success');
    try {
      const form = new FormData(event.currentTarget);
      const result = await api('/api/session', { method: 'POST', body: JSON.stringify({ email: form.get('email'), password: form.get('password') }) });
      state.token = result.token;
      state.user = result.user;
      localStorage.setItem('depotflow_token', state.token);
      setNotice(null);
      showWorkspace();
      await loadInitialView();
    } catch (error) {
      message.textContent = error.message;
    } finally {
      buttonEl.disabled = false;
    }
  });

  $('#logout').addEventListener('click', showLogin);
  document.querySelectorAll('.nav-link').forEach(link => link.addEventListener('click', async () => {
    state.view = link.dataset.view;
    setNotice(null);
    await loadInitialView();
  }));

  $('#view').addEventListener('click', async event => {
    const target = event.target.closest('[data-action]');
    if (!target) return;
    const action = target.dataset.action;
    if (action === 'refresh') { setNotice(null); await refreshView(); }
    if (action === 'refresh-orders') { setNotice(null); await Promise.all([loadOrders(), state.selectedOrder && api(`/api/orders/${encodeURIComponent(state.selectedOrder.id)}`).then(order => state.selectedOrder = order)]); render(); }
    if (action === 'refresh-audit') { setNotice(null); await loadAudit(); render(); }
    if (action === 'refresh-order' && state.selectedOrder) { state.selectedOrder = await api(`/api/orders/${encodeURIComponent(state.selectedOrder.id)}`); setNotice(null); render(); }
    if (action === 'select-order') { state.selectedOrder = await api(`/api/orders/${encodeURIComponent(target.dataset.orderId)}`); setNotice(null); render(); }
    if (action === 'toggle-order-form') { state.showOrderForm = !state.showOrderForm; if (state.showOrderForm && !state.draftLines.length) state.draftLines = [{ sku: state.inventory[0]?.sku || 'BOLT', quantity: '1' }]; render(); }
    if (action === 'add-line') { rememberLines(); state.draftLines.push({ sku: state.inventory[0]?.sku || 'BOLT', quantity: '1' }); render(); }
    if (action === 'remove-line') { rememberLines(); if (state.draftLines.length > 1) state.draftLines.splice(Number(target.dataset.lineIndex), 1); render(); }
    if (action === 'load-more-orders') { await loadOrders(false); render(); }
    if (action === 'load-more-audit') { await loadAudit(false); render(); }
    if (action === 'transition' && state.selectedOrder) {
      const transition = target.dataset.transition;
      await mutate(`/api/orders/${encodeURIComponent(state.selectedOrder.id)}/${transition}`, { expected_version: state.selectedOrder.version }, target);
    }
  });

  $('#view').addEventListener('input', event => {
    if (event.target.matches('[data-action="search-orders"]')) {
      state.orderQuery = event.target.value;
      const selectionStart = event.target.selectionStart;
      const selectionEnd = event.target.selectionEnd;
      clearTimeout(window.depotSearchTimer);
      window.depotSearchTimer = setTimeout(async () => {
        await loadOrders();
        if (state.view !== 'orders') return;
        render();
        const search = $('#view [data-action="search-orders"]');
        if (search) {
          search.focus();
          if (selectionStart !== null && selectionEnd !== null) search.setSelectionRange(selectionStart, selectionEnd);
        }
      }, 220);
    }
    if (event.target.matches('[data-testid="line-sku"], [data-testid="line-quantity"]')) rememberLines();
    if (event.target.matches('#order-client-ref')) state.draftClientRef = event.target.value;
  });

  $('#view').addEventListener('change', async event => {
    if (event.target.matches('[data-action="filter-status"]')) {
      state.orderStatus = event.target.value;
      await loadOrders();
      render();
    }
    if (event.target.matches('[data-testid="line-sku"], [data-testid="line-quantity"]')) rememberLines();
  });

  $('#view').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.target;
    const submitter = event.submitter;
    if (form.id === 'order-form') {
      rememberLines();
      const clientRef = form.elements.client_ref.value.trim();
      const lines = state.draftLines.map(line => ({ sku: line.sku, quantity: Number(line.quantity) }));
      if (lines.some(line => !Number.isInteger(line.quantity) || line.quantity < 1)) {
        setNotice('Each line quantity must be a positive whole number.', true);
        const previous = $('#view .toast');
        if (previous) previous.remove();
        $('#view').prepend(node('div', { className: 'toast error', role: 'status', text: state.notice.message }));
        return;
      }
      await mutate('/api/orders', { client_ref: clientRef, lines }, submitter);
    }
    if (form.id === 'return-form' && state.selectedOrder) {
      const lines = Array.from(form.querySelectorAll('[data-testid="return-quantity"]'))
        .map(input => ({ sku: input.dataset.sku, quantity: Number(input.value) }))
        .filter(line => line.quantity > 0);
      if (!lines.length) {
        setNotice('Enter at least one positive return quantity.', true);
        const previous = $('#view .toast');
        if (previous) previous.remove();
        $('#view').prepend(node('div', { className: 'toast error', role: 'status', text: state.notice.message }));
        return;
      }
      await mutate(`/api/orders/${encodeURIComponent(state.selectedOrder.id)}/returns`, { expected_version: state.selectedOrder.version, lines }, submitter);
    }
    if (form.id === 'adjustment-form') {
      const sku = form.elements.sku.value;
      const item = state.inventory.find(candidate => candidate.sku === sku);
      await mutate('/api/stock/adjustments', { sku, delta: Number(form.elements.delta.value), expected_version: item.version, reason: form.elements.reason.value.trim() }, submitter);
    }
  });

  async function resumeSession() {
    if (!state.token) return;
    try {
      state.user = await api('/api/me');
      showWorkspace();
      await loadInitialView();
    } catch (_) {
      showLogin();
    }
  }

  resumeSession();
})();
