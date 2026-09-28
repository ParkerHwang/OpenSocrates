(() => {
  'use strict';

  const byId = (id) => document.getElementById(id);
  const loginScreen = byId('login-screen');
  const appShell = byId('app-shell');
  const pageContent = byId('page-content');
  const notice = byId('notice');
  const state = {
    token: localStorage.getItem('depotflow-token') || '',
    user: null,
    tab: 'inventory',
    inventory: [],
    dashboard: null,
    orders: [],
    orderCursor: null,
    orderQuery: '',
    orderStatus: '',
    selectedOrder: null,
    newOrderOpen: false,
    draftLines: [{ sku: 'BOLT', quantity: '1' }],
    audit: [],
    auditCursor: null,
    mutationKeys: new Map(),
    noticeTimer: null,
  };

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  }

  function labeledField(labelText, control, className = 'field') {
    const wrapper = node('div', className);
    const label = node('label', '', labelText);
    label.htmlFor = control.id;
    wrapper.append(label, control);
    return wrapper;
  }

  function makeButton(text, className = 'button secondary', testId, type = 'button') {
    const btn = node('button', className, text);
    btn.type = type;
    if (testId) btn.dataset.testid = testId;
    return btn;
  }

  function statusBadge(status) {
    return node('span', `badge ${status}`, status);
  }

  function money(cents) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
  }

  function setNotice(message, kind = 'info', timeout = 6000) {
    window.clearTimeout(state.noticeTimer);
    if (!message) {
      notice.hidden = true;
      notice.textContent = '';
      return;
    }
    notice.className = `notice ${kind}`;
    notice.textContent = message;
    notice.hidden = false;
    if (timeout > 0) state.noticeTimer = window.setTimeout(() => { notice.hidden = true; }, timeout);
  }

  async function api(path, options = {}) {
    const headers = { Accept: 'application/json' };
    if (state.token && !options.noAuth) headers.Authorization = `Bearer ${state.token}`;
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (options.key) headers['Idempotency-Key'] = options.key;
    let response;
    try {
      response = await fetch(path, {
        method: options.method || 'GET',
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
    } catch (error) {
      throw new Error('Could not reach DepotFlow. Check that the local server is running and retry.');
    }
    let value;
    try { value = await response.json(); } catch (_) { value = {}; }
    if (!response.ok) {
      const detail = value && value.error ? value.error : {};
      const error = new Error(detail.message || `Request failed (${response.status}).`);
      error.status = response.status;
      error.code = detail.code || 'request_failed';
      throw error;
    }
    return value;
  }

  function stableStringify(value) {
    if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
    if (value && typeof value === 'object') {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`;
    }
    return JSON.stringify(value);
  }

  function mutationKey(method, path, body) {
    const fingerprint = `${method}\n${path}\n${stableStringify(body)}`;
    if (!state.mutationKeys.has(fingerprint)) state.mutationKeys.set(fingerprint, crypto.randomUUID());
    return [fingerprint, state.mutationKeys.get(fingerprint)];
  }

  async function mutate(method, path, body) {
    const [fingerprint, key] = mutationKey(method, path, body);
    try {
      const value = await api(path, { method, body, key });
      state.mutationKeys.delete(fingerprint);
      return value;
    } catch (error) {
      // Retain the key so a retry of this exact request safely replays success
      // if the response was lost after the server committed.
      throw error;
    }
  }

  function showLogin(message = '') {
    loginScreen.hidden = false;
    appShell.hidden = true;
    byId('login-message').textContent = message;
  }

  function setProfile() {
    const first = state.user.tenant.charAt(0).toUpperCase();
    byId('sidebar-tenant').textContent = first + state.user.tenant.slice(1);
    byId('profile-email').textContent = state.user.email;
    byId('profile-role').textContent = state.user.role[0].toUpperCase() + state.user.role.slice(1);
    byId('avatar').textContent = first;
    byId('role-pill').textContent = state.user.role.toUpperCase();
  }

  async function enterWorkspace() {
    loginScreen.hidden = true;
    appShell.hidden = false;
    setProfile();
    setNotice('Signed in. Your warehouse data is ready.', 'success');
    await navigate('inventory');
  }

  byId('login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const submit = byId('login-submit');
    const fields = new FormData(event.currentTarget);
    const email = String(fields.get('email') || '').trim();
    const password = String(fields.get('password') || '');
    submit.disabled = true;
    submit.textContent = 'Signing in…';
    byId('login-message').textContent = '';
    try {
      const result = await api('/api/session', { method: 'POST', body: { email, password }, noAuth: true });
      state.token = result.token;
      state.user = result.user;
      localStorage.setItem('depotflow-token', state.token);
      await enterWorkspace();
    } catch (error) {
      byId('login-message').textContent = error.message;
    } finally {
      submit.disabled = false;
      submit.innerHTML = 'Sign in <span aria-hidden="true">→</span>';
    }
  });

  byId('logout').addEventListener('click', () => {
    localStorage.removeItem('depotflow-token');
    state.token = '';
    state.user = null;
    state.inventory = [];
    state.orders = [];
    state.audit = [];
    state.selectedOrder = null;
    state.newOrderOpen = false;
    setNotice('');
    byId('login-form').reset();
    showLogin('You have signed out.');
  });

  document.querySelectorAll('[data-tab]').forEach((button) => {
    button.addEventListener('click', () => navigate(button.dataset.tab));
  });

  async function navigate(tab) {
    state.tab = tab;
    document.querySelectorAll('[data-tab]').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab));
    byId('breadcrumb-current').textContent = tab === 'audit' ? 'Audit trail' : tab[0].toUpperCase() + tab.slice(1);
    pageContent.replaceChildren(node('div', 'panel empty-state', 'Loading workspace data…'));
    try {
      if (tab === 'inventory') {
        await refreshInventory();
        renderInventory();
      } else if (tab === 'orders') {
        await loadOrders(true);
        renderOrdersPage();
      } else {
        await loadAudit(true);
        renderAuditPage();
      }
    } catch (error) {
      pageContent.replaceChildren(emptyState('Could not load this view', error.message, '↻'));
      setNotice(error.message, 'error', 0);
    }
  }

  async function refreshInventory() {
    const [inventory, dashboard] = await Promise.all([api('/api/inventory'), api('/api/dashboard')]);
    state.inventory = inventory.items;
    state.dashboard = dashboard;
  }

  function emptyState(title, description, icon = '▦') {
    const box = node('div', 'empty-state');
    box.append(node('span', 'empty-icon', icon), node('strong', '', title), node('span', '', description));
    return box;
  }

  function metric(label, value, sub, accent) {
    const card = node('div', 'metric-card');
    card.append(node('span', 'metric-label', label), node('span', 'metric-accent', accent), node('div', 'metric-value', value), node('div', 'metric-sub', sub));
    return card;
  }

  function renderInventory() {
    pageContent.replaceChildren();
    const heading = node('div', 'page-heading');
    const title = node('div');
    title.append(node('p', 'section-kicker', 'WAREHOUSE OVERVIEW'), node('h1', '', 'Inventory'), node('p', '', 'Stock position and fulfillment activity for your warehouse.'));
    heading.append(title);
    pageContent.append(heading);

    const dashboard = state.dashboard || { orders_by_status: {}, inventory_units: 0, reserved_units: 0 };
    const ordersByStatus = dashboard.orders_by_status || {};
    const totalOrders = Object.values(ordersByStatus).reduce((sum, count) => sum + count, 0);
    const availableUnits = state.inventory.reduce((sum, item) => sum + item.available, 0);
    const reservedOrders = ordersByStatus.reserved || 0;
    const grid = node('section', 'summary-grid');
    grid.setAttribute('aria-label', 'Warehouse summary');
    grid.append(
      metric('ON-HAND UNITS', dashboard.inventory_units.toLocaleString(), 'Across all active SKUs', '▦'),
      metric('AVAILABLE', availableUnits.toLocaleString(), 'Ready to allocate', '↗'),
      metric('RESERVED UNITS', dashboard.reserved_units.toLocaleString(), `${reservedOrders} orders being prepared`, '◷'),
      metric('OPEN ORDERS', String((ordersByStatus.draft || 0) + reservedOrders), `${totalOrders} total orders recorded`, '▤'),
    );
    pageContent.append(grid);

    const stockPanel = node('section', 'panel');
    const stockHead = node('div', 'panel-heading');
    const stockTitle = node('div');
    stockTitle.append(node('h2', '', 'Stock by SKU'), node('p', '', 'Available stock is calculated from on-hand minus reserved.'));
    stockHead.append(stockTitle, node('span', 'badge', `${state.inventory.length} SKUS`));
    const wrap = node('div', 'table-wrap');
    const table = node('table');
    table.dataset.testid = 'inventory-table';
    table.setAttribute('aria-label', 'Inventory by SKU');
    const thead = node('thead');
    const tr = node('tr');
    ['SKU', 'PRODUCT', 'ON HAND', 'RESERVED', 'AVAILABLE', 'UNIT PRICE', 'VERSION'].forEach((text) => tr.append(node('th', '', text)));
    thead.append(tr);
    const tbody = node('tbody');
    state.inventory.forEach((item) => {
      const row = node('tr');
      row.append(node('td', '', ''));
      row.lastChild.append(node('span', 'sku-cell', item.sku));
      row.append(node('td', '', item.name));
      row.append(node('td', 'stock-value', item.on_hand.toLocaleString()));
      row.append(node('td', 'stock-value', item.reserved.toLocaleString()));
      row.append(node('td', `stock-value ${item.available < 10 ? 'stock-low' : 'stock-ok'}`, item.available.toLocaleString()));
      row.append(node('td', '', money(item.price_cents)));
      row.append(node('td', 'audit-id', `v${item.version}`));
      tbody.append(row);
    });
    table.append(thead, tbody);
    wrap.append(table);
    stockPanel.append(stockHead, wrap);
    if (state.user.role !== 'viewer' && state.user.role === 'admin') {
      stockPanel.append(buildAdjustmentForm());
    }
    pageContent.append(stockPanel);

    const lower = node('div', 'dashboard-bottom');
    const flow = node('section', 'panel');
    const flowHead = node('div', 'panel-heading');
    flowHead.append(node('div'));
    flowHead.firstChild.append(node('h2', '', 'Order flow'), node('p', '', 'Current order status across the warehouse.'));
    flow.append(flowHead);
    const breakdown = node('div', 'status-breakdown');
    const maxCount = Math.max(1, ...Object.values(ordersByStatus));
    ['draft', 'reserved', 'shipped', 'returned', 'cancelled'].forEach((status) => {
      const row = node('div', 'status-row');
      row.append(node('span', '', status[0].toUpperCase() + status.slice(1)));
      const track = node('span', 'status-track');
      const fill = node('span', 'status-fill');
      fill.style.width = `${((ordersByStatus[status] || 0) / maxCount) * 100}%`;
      track.append(fill);
      row.append(track, node('span', 'status-count', String(ordersByStatus[status] || 0)));
      breakdown.append(row);
    });
    flow.append(breakdown);
    const auditCard = node('section', 'panel');
    const auditHead = node('div', 'panel-heading');
    auditHead.append(node('div'));
    auditHead.firstChild.append(node('h2', '', 'Trace every movement'), node('p', '', 'Successful changes appear in a tenant-scoped audit log.'));
    auditCard.append(auditHead, makeButton('Open audit trail →', 'button secondary', null));
    auditCard.lastChild.addEventListener('click', () => navigate('audit'));
    lower.append(flow, auditCard);
    pageContent.append(lower);
  }

  function buildAdjustmentForm() {
    const panel = node('section', 'panel');
    const heading = node('div', 'panel-heading');
    heading.append(node('div'));
    heading.firstChild.append(node('h2', '', 'Adjust stock'), node('p', '', 'Admin adjustments require the latest inventory version and a reason.'));
    const form = node('form', 'filters');
    const skuSelect = node('select');
    skuSelect.id = 'adjust-sku';
    skuSelect.className = 'filter-control';
    state.inventory.forEach((item) => {
      const option = node('option', '', item.sku);
      option.value = item.sku;
      skuSelect.append(option);
    });
    const delta = node('input');
    delta.id = 'adjust-delta'; delta.type = 'number'; delta.step = '1'; delta.required = true; delta.placeholder = 'e.g. 12'; delta.className = 'filter-control';
    const reason = node('input');
    reason.id = 'adjust-reason'; reason.type = 'text'; reason.required = true; reason.placeholder = 'Reason for adjustment'; reason.className = 'filter-control';
    form.append(labeledField('SKU', skuSelect), labeledField('Signed quantity', delta), labeledField('Reason', reason, 'field search-field'));
    const submit = makeButton('Save adjustment', 'button primary', null, 'submit');
    form.append(submit);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const item = state.inventory.find((value) => value.sku === skuSelect.value);
      const body = { sku: skuSelect.value, delta: Number(delta.value), expected_version: item.version, reason: reason.value.trim() };
      submit.disabled = true;
      try {
        await mutate('POST', '/api/stock/adjustments', body);
        await refreshInventory();
        renderInventory();
        setNotice(`Stock updated for ${body.sku}.`, 'success');
      } catch (error) {
        setNotice(`${error.message}${error.code ? ` (${error.code})` : ''}`, 'error', 0);
        submit.disabled = false;
      }
    });
    panel.append(heading, form);
    return panel;
  }

  function buildOrderQuery(cursor = null) {
    const params = new URLSearchParams();
    params.set('limit', '20');
    if (state.orderStatus) params.set('status', state.orderStatus);
    if (state.orderQuery.trim()) params.set('q', state.orderQuery.trim());
    if (cursor) params.set('cursor', cursor);
    return `/api/orders?${params.toString()}`;
  }

  async function loadOrders(reset) {
    if (reset) {
      state.orders = [];
      state.orderCursor = null;
    }
    const page = await api(buildOrderQuery(reset ? null : state.orderCursor));
    state.orders = reset ? page.items : state.orders.concat(page.items);
    state.orderCursor = page.next_cursor;
    if (state.selectedOrder && !state.orders.some((order) => order.id === state.selectedOrder.id)) {
      // A filtered result can hide the selected item without changing it.
    }
    byId('order-nav-count').textContent = state.orders.length ? String(state.orders.length) : '';
  }

  function renderOrdersPage() {
    pageContent.replaceChildren();
    const heading = node('div', 'page-heading');
    const title = node('div');
    title.append(node('p', 'section-kicker', 'PICK, PACK, SHIP'), node('h1', '', 'Orders'), node('p', '', 'Create orders, reserve available stock, and record returns.'));
    heading.append(title);
    if (state.user.role !== 'viewer') {
      const create = makeButton(state.newOrderOpen ? 'Close order form' : '+ New order', 'button primary', 'new-order');
      create.addEventListener('click', () => {
        state.newOrderOpen = !state.newOrderOpen;
        if (state.newOrderOpen && !state.draftLines.length) state.draftLines = [{ sku: state.inventory[0]?.sku || 'BOLT', quantity: '1' }];
        renderOrdersPage();
      });
      heading.append(create);
    }
    pageContent.append(heading);
    if (state.user.role === 'viewer') pageContent.append(node('div', 'role-viewer-note', 'Read-only access · order creation and fulfillment actions are disabled for viewers.'));
    if (state.newOrderOpen && state.user.role !== 'viewer') pageContent.append(buildNewOrderForm());

    const filterPanel = node('section', 'panel');
    const toolbar = node('div', 'toolbar');
    const filters = node('form', 'filters');
    const search = node('input');
    search.type = 'search'; search.id = 'order-search'; search.value = state.orderQuery; search.placeholder = 'Search client reference'; search.className = 'filter-control';
    const searchField = labeledField('CLIENT REFERENCE', search, 'field search-field');
    searchField.querySelector('label').htmlFor = 'order-search';
    const status = node('select');
    status.id = 'order-status'; status.className = 'filter-control';
    [['', 'All statuses'], ['draft', 'Draft'], ['reserved', 'Reserved'], ['shipped', 'Shipped'], ['returned', 'Returned'], ['cancelled', 'Cancelled']].forEach(([value, label]) => {
      const option = node('option', '', label); option.value = value; option.selected = state.orderStatus === value; status.append(option);
    });
    const statusField = labeledField('STATUS', status);
    statusField.querySelector('label').htmlFor = 'order-status';
    const apply = makeButton('Apply filters', 'button secondary small', null, 'submit');
    filters.append(searchField, statusField, apply);
    filters.addEventListener('submit', async (event) => {
      event.preventDefault();
      state.orderQuery = search.value;
      state.orderStatus = status.value;
      await safeOrdersReload();
    });
    toolbar.append(filters, node('span', 'toolbar-note', `${state.orders.length} shown`));
    filterPanel.append(toolbar);
    const layout = node('div', 'order-layout');
    const listPanel = node('section', 'panel');
    const listHead = node('div', 'panel-heading');
    listHead.append(node('h2', '', 'Order queue'));
    listPanel.append(listHead);
    const list = node('div', 'order-list');
    if (!state.orders.length) {
      list.append(emptyState('No orders found', state.orderQuery || state.orderStatus ? 'Try changing your search or status filter.' : 'Orders created by this tenant will appear here.', '▤'));
    } else {
      state.orders.forEach((order) => {
        const row = node('button', `order-row ${state.selectedOrder?.id === order.id ? 'selected' : ''}`);
        row.type = 'button';
        row.append(node('span', 'order-ref', order.client_ref));
        const meta = node('span', 'order-row-meta');
        meta.append(node('span', '', `${order.lines.length} line${order.lines.length === 1 ? '' : 's'} · ${money(order.total_cents)}`), statusBadge(order.status));
        row.append(meta);
        row.addEventListener('click', async () => {
          try {
            state.selectedOrder = await api(`/api/orders/${encodeURIComponent(order.id)}`);
            renderOrdersPage();
          } catch (error) { setNotice(error.message, 'error', 0); }
        });
        list.append(row);
      });
    }
    listPanel.append(list);
    if (state.orderCursor) {
      const more = makeButton('Load more orders', 'button secondary small load-more');
      more.addEventListener('click', async () => {
        more.disabled = true;
        try { await loadOrders(false); renderOrdersPage(); } catch (error) { setNotice(error.message, 'error', 0); more.disabled = false; }
      });
      listPanel.append(more);
    }
    const detailPanel = node('section', 'panel');
    if (state.selectedOrder) renderOrderDetail(detailPanel, state.selectedOrder);
    else detailPanel.append(emptyState('Select an order', 'Choose an order from the queue to inspect its lines and fulfillment history.', '⌕'));
    layout.append(listPanel, detailPanel);
    filterPanel.append(layout);
    pageContent.append(filterPanel);
  }

  async function safeOrdersReload() {
    try { await loadOrders(true); renderOrdersPage(); }
    catch (error) { setNotice(error.message, 'error', 0); }
  }

  function buildNewOrderForm() {
    const panel = node('section', 'panel');
    const heading = node('div', 'panel-heading');
    heading.append(node('div'));
    heading.firstChild.append(node('h2', '', 'Create an order'), node('p', '', 'Prices come from the warehouse catalog and are saved with the order.'));
    const form = node('form');
    const ref = node('input'); ref.type = 'text'; ref.id = 'new-client-ref'; ref.dataset.testid = 'order-client-ref'; ref.required = true; ref.maxLength = 120; ref.placeholder = 'e.g. WEB-1042';
    const refField = labeledField('CLIENT REFERENCE', ref);
    refField.querySelector('label').htmlFor = 'new-client-ref';
    form.append(refField);
    const linesTitle = node('div', 'panel-heading');
    linesTitle.style.marginTop = '16px';
    linesTitle.append(node('h2', '', 'Order lines'));
    const add = makeButton('+ Add line', 'button secondary small', 'add-line');
    linesTitle.append(add);
    form.append(linesTitle);
    const editor = node('div', 'line-editor');
    const renderLines = () => {
      editor.replaceChildren();
      state.draftLines.forEach((line, index) => {
        const row = node('div', 'line-row');
        const sku = node('select'); sku.id = `line-sku-${index}`; sku.dataset.testid = 'line-sku';
        state.inventory.forEach((item) => {
          const option = node('option', '', `${item.sku} · ${item.name} · ${money(item.price_cents)}`);
          option.value = item.sku; option.selected = item.sku === line.sku; sku.append(option);
        });
        const qty = node('input'); qty.type = 'number'; qty.min = '1'; qty.step = '1'; qty.required = true; qty.value = line.quantity; qty.id = `line-quantity-${index}`; qty.dataset.testid = 'line-quantity';
        const skuField = labeledField('SKU', sku); skuField.querySelector('label').htmlFor = sku.id;
        const qtyField = labeledField('QUANTITY', qty); qtyField.querySelector('label').htmlFor = qty.id;
        sku.addEventListener('change', () => { state.draftLines[index].sku = sku.value; updateEstimate(); });
        qty.addEventListener('input', () => { state.draftLines[index].quantity = qty.value; updateEstimate(); });
        row.append(skuField, qtyField);
        if (state.draftLines.length > 1) {
          const remove = makeButton('×', 'remove-line'); remove.setAttribute('aria-label', `Remove line ${index + 1}`);
          remove.addEventListener('click', () => { state.draftLines.splice(index, 1); renderLines(); updateEstimate(); });
          row.append(remove);
        } else {
          row.append(node('span'));
        }
        editor.append(row);
      });
    };
    const estimate = node('div', 'order-summary');
    const updateEstimate = () => {
      let total = 0;
      state.draftLines.forEach((line) => {
        const item = state.inventory.find((candidate) => candidate.sku === line.sku);
        const quantity = Number(line.quantity);
        if (item && Number.isSafeInteger(quantity) && quantity > 0) total += item.price_cents * quantity;
      });
      estimate.replaceChildren(node('span', '', 'Estimated order total'), node('strong', '', money(total)));
    };
    add.addEventListener('click', () => {
      if (state.draftLines.length >= 10) { setNotice('Orders can contain up to 10 lines in this form.', 'info'); return; }
      const used = new Set(state.draftLines.map((line) => line.sku));
      const nextSku = state.inventory.find((item) => !used.has(item.sku))?.sku || state.inventory[0]?.sku || 'BOLT';
      state.draftLines.push({ sku: nextSku, quantity: '1' });
      renderLines(); updateEstimate();
    });
    renderLines(); updateEstimate();
    form.append(editor, estimate);
    const footer = node('div', 'actions-row');
    const submit = makeButton('Create order', 'button primary', 'submit-order', 'submit');
    const cancel = makeButton('Cancel', 'button secondary');
    cancel.addEventListener('click', () => { state.newOrderOpen = false; renderOrdersPage(); });
    footer.append(submit, cancel);
    form.append(footer);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const lines = state.draftLines.map((line) => ({ sku: line.sku, quantity: Number(line.quantity) }));
      const duplicate = new Set(lines.map((line) => line.sku)).size !== lines.length;
      if (duplicate) { setNotice('Choose a different SKU on each line.', 'error', 0); return; }
      const body = { client_ref: ref.value.trim(), lines };
      submit.disabled = true;
      try {
        const order = await mutate('POST', '/api/orders', body);
        state.selectedOrder = order;
        state.newOrderOpen = false;
        state.draftLines = [{ sku: 'BOLT', quantity: '1' }];
        await Promise.all([refreshInventory(), loadOrders(true)]);
        renderOrdersPage();
        setNotice(`Order ${order.client_ref} was created.`, 'success');
      } catch (error) {
        setNotice(`${error.message}${error.code ? ` (${error.code})` : ''}`, 'error', 0);
        submit.disabled = false;
      }
    });
    panel.append(heading, form);
    return panel;
  }

  function renderOrderDetail(panel, order) {
    panel.dataset.testid = 'order-detail';
    const head = node('div', 'detail-title');
    const label = node('div');
    label.append(node('p', 'section-kicker', 'ORDER DETAIL'), node('h2', '', order.client_ref), node('span', 'detail-ref-label', order.id));
    head.append(label, statusBadge(order.status));
    panel.append(head);
    const meta = node('div', 'detail-meta');
    [['STATUS', order.status], ['VERSION', `v${order.version}`], ['LINES', String(order.lines.length)]].forEach(([labelText, value]) => {
      const cell = node('div'); cell.append(node('span', '', labelText), node('strong', '', value)); meta.append(cell);
    });
    panel.append(meta);
    const tableWrap = node('div', 'table-wrap');
    const table = node('table', 'detail-line-table');
    const thead = node('thead'); const header = node('tr');
    ['SKU', 'QTY', 'PRICE', 'RETURNED', 'LINE TOTAL'].forEach((value) => header.append(node('th', '', value)));
    thead.append(header);
    const tbody = node('tbody');
    order.lines.forEach((line) => {
      const tr = node('tr');
      tr.append(node('td', 'audit-id', line.sku), node('td', '', String(line.quantity)), node('td', '', money(line.unit_price_cents)), node('td', '', String(line.returned_quantity)), node('td', '', money(line.unit_price_cents * line.quantity)));
      tbody.append(tr);
    });
    table.append(thead, tbody); tableWrap.append(table); panel.append(tableWrap);
    const total = node('div', 'detail-total'); total.append(node('span', '', 'ORDER TOTAL'), node('strong', '', money(order.total_cents))); panel.append(total);
    if (state.user.role !== 'viewer') {
      const actions = node('div', 'actions-row');
      if (order.status === 'draft') {
        const reserve = makeButton('Reserve stock', 'button primary', 'reserve-order');
        reserve.addEventListener('click', () => transition('reserve', reserve)); actions.append(reserve);
        const cancel = makeButton('Cancel order', 'button danger', 'cancel-order');
        cancel.addEventListener('click', () => transition('cancel', cancel)); actions.append(cancel);
      } else if (order.status === 'reserved') {
        const ship = makeButton('Ship order', 'button primary', 'ship-order');
        ship.addEventListener('click', () => transition('ship', ship)); actions.append(ship);
        const cancel = makeButton('Cancel order', 'button danger', 'cancel-order');
        cancel.addEventListener('click', () => transition('cancel', cancel)); actions.append(cancel);
      }
      if (actions.childElementCount) panel.append(actions);
      if (order.status === 'shipped') panel.append(buildReturnForm(order));
    }
  }

  async function transition(action, button) {
    const order = state.selectedOrder;
    button.disabled = true;
    try {
      const updated = await mutate('POST', `/api/orders/${encodeURIComponent(order.id)}/${action}`, { expected_version: order.version });
      await afterOrderMutation(updated, `${updated.client_ref} is now ${updated.status}.`);
    } catch (error) {
      setNotice(`${error.message}${error.code ? ` (${error.code})` : ''}`, 'error', 0);
      button.disabled = false;
    }
  }

  function buildReturnForm(order) {
    const box = node('section', 'return-box');
    box.append(node('h3', '', 'Record a return'), node('p', '', 'Enter the number of shipped units received back. A partial return keeps this order shipped.'));
    const form = node('form');
    const fields = node('div', 'return-fields');
    order.lines.forEach((line, index) => {
      const field = node('label', 'return-field');
      const remaining = line.quantity - line.returned_quantity;
      field.append(node('span', '', `${line.sku} · ${remaining} remaining`));
      const input = node('input'); input.type = 'number'; input.min = '0'; input.max = String(remaining); input.step = '1'; input.value = '0'; input.id = `return-quantity-${index}`; input.dataset.testid = 'return-quantity'; input.dataset.sku = line.sku; input.disabled = remaining === 0;
      field.append(input); fields.append(field);
    });
    const actions = node('div', 'return-actions');
    const submit = makeButton('Submit return', 'button secondary', 'submit-return', 'submit');
    actions.append(submit);
    form.append(fields, actions);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const lines = Array.from(fields.querySelectorAll('input')).map((input) => ({ sku: input.dataset.sku, quantity: Number(input.value) })).filter((line) => line.quantity > 0);
      if (!lines.length || lines.some((line) => !Number.isSafeInteger(line.quantity))) {
        setNotice('Enter a positive whole number for at least one return line.', 'error', 0); return;
      }
      submit.disabled = true;
      try {
        const updated = await mutate('POST', `/api/orders/${encodeURIComponent(order.id)}/returns`, { expected_version: order.version, lines });
        await afterOrderMutation(updated, updated.status === 'returned' ? `${updated.client_ref} is fully returned.` : `Return recorded for ${updated.client_ref}.`);
      } catch (error) {
        setNotice(`${error.message}${error.code ? ` (${error.code})` : ''}`, 'error', 0);
        submit.disabled = false;
      }
    });
    box.append(form);
    return box;
  }

  async function afterOrderMutation(order, message) {
    state.selectedOrder = order;
    await Promise.all([refreshInventory(), loadOrders(true)]);
    renderOrdersPage();
    setNotice(message, 'success');
  }

  async function loadAudit(reset) {
    if (reset) { state.audit = []; state.auditCursor = null; }
    const params = new URLSearchParams({ limit: '30' });
    if (!reset && state.auditCursor) params.set('cursor', state.auditCursor);
    const page = await api(`/api/audit?${params.toString()}`);
    state.audit = reset ? page.items : state.audit.concat(page.items);
    state.auditCursor = page.next_cursor;
  }

  function renderAuditPage() {
    pageContent.replaceChildren();
    const heading = node('div', 'page-heading');
    const title = node('div');
    title.append(node('p', 'section-kicker', 'CHANGE HISTORY'), node('h1', '', 'Audit trail'), node('p', '', 'A tenant-scoped record of committed stock and order changes.'));
    heading.append(title);
    pageContent.append(heading);
    const panel = node('section', 'panel');
    const panelHead = node('div', 'panel-heading');
    panelHead.append(node('div'));
    panelHead.firstChild.append(node('h2', '', 'Activity log'), node('p', '', `${state.audit.length} event${state.audit.length === 1 ? '' : 's'} loaded · oldest first`));
    panelHead.append(node('span', 'badge', 'TENANT ONLY'));
    const tableWrap = node('div', 'table-wrap');
    const table = node('table'); table.dataset.testid = 'audit-table'; table.setAttribute('aria-label', 'Audit events');
    const thead = node('thead'); const row = node('tr');
    ['EVENT', 'ENTITY', 'ACTOR', 'RECORDED AT'].forEach((label) => row.append(node('th', '', label)));
    thead.append(row);
    const tbody = node('tbody');
    state.audit.forEach((entry) => {
      const tr = node('tr');
      tr.append(node('td', 'audit-action', entry.action), node('td', 'audit-id', entry.entity_id), node('td', '', entry.actor), node('td', 'audit-time', new Date(entry.created_at).toLocaleString()));
      tbody.append(tr);
    });
    table.append(thead, tbody); tableWrap.append(table);
    panel.append(panelHead, tableWrap);
    if (!state.audit.length) panel.append(emptyState('No activity yet', 'Successful stock adjustments, order creation, and order transitions will appear here.', '◷'));
    if (state.auditCursor) {
      const more = makeButton('Load older activity', 'button secondary small load-more');
      more.addEventListener('click', async () => {
        more.disabled = true;
        try { await loadAudit(false); renderAuditPage(); }
        catch (error) { setNotice(error.message, 'error', 0); more.disabled = false; }
      });
      panel.append(more);
    }
    pageContent.append(panel);
  }

  async function boot() {
    if (!state.token) { showLogin(); return; }
    try {
      state.user = await api('/api/me');
      await enterWorkspace();
    } catch (_) {
      localStorage.removeItem('depotflow-token');
      state.token = '';
      state.user = null;
      showLogin('Your session expired. Sign in again.');
    }
  }

  boot();
})();
