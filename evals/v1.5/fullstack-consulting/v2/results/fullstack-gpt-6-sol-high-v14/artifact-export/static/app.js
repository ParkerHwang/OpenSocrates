"use strict";

const app = document.querySelector("#app");
const state = {token: sessionStorage.getItem("depotflow_token"), user: null, view: "inventory", inventory: [], orders: [], orderCursor: null, audit: [], auditCursor: null, selected: null, busy: false, notice: null, filters: {status: "", q: ""}};
const money = cents => new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(cents / 100);

function node(tag, attrs = {}, content = "") {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "className") element.className = value;
    else if (key === "onClick") element.addEventListener("click", value);
    else if (key === "onSubmit") element.addEventListener("submit", value);
    else element.setAttribute(key, value);
  }
  if (content instanceof Node) element.append(content);
  else element.textContent = String(content);
  return element;
}

function message(text, type = "error") {
  state.notice = {text, type};
  const holder = document.querySelector("#notice");
  if (holder) renderNotice(holder);
}

function renderNotice(holder) {
  holder.replaceChildren();
  if (state.notice) holder.append(node("div", {className: state.notice.type, role: "status"}, state.notice.text));
}

async function api(path, options = {}) {
  const headers = {"Accept": "application/json"};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    headers["Idempotency-Key"] = options.key || crypto.randomUUID();
  }
  const response = await fetch(path, {method: options.method || "GET", headers, body: options.body === undefined ? undefined : JSON.stringify(options.body)});
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error?.message || `Request failed (${response.status})`);
    error.code = data.error?.code;
    error.status = response.status;
    if (response.status === 401 && path !== "/api/session") {
      state.token = null;
      state.user = null;
      sessionStorage.removeItem("depotflow_token");
      renderLogin();
    }
    throw error;
  }
  return data;
}

async function runMutation(task, onSuccess, retryScope) {
  if (state.busy) return;
  state.busy = true;
  const key = retryScope?.dataset.idempotencyKey || crypto.randomUUID();
  if (retryScope) retryScope.dataset.idempotencyKey = key;
  document.querySelectorAll("button").forEach(button => { if (button.dataset.mutation === "true") button.disabled = true; });
  state.notice = null;
  renderNotice(document.querySelector("#notice"));
  try {
    const result = await task(key);
    if (retryScope) delete retryScope.dataset.idempotencyKey;
    await onSuccess(result);
  } catch (error) {
    message(error.code === "stale_version" ? `${error.message} Your form is still here. Refresh the detail before retrying.` : error.message);
  } finally {
    state.busy = false;
    document.querySelectorAll("button[data-mutation='true']").forEach(button => button.disabled = false);
  }
}

function renderLogin() {
  app.innerHTML = `<div class="login-shell"><aside class="login-aside"><div class="brand"><span class="brand-mark">D</span>DepotFlow</div><div><h1>Keep every order moving.</h1><p>Inventory, fulfillment, returns and a clear history of every change, together in one workspace.</p></div><div class="muted">A local workspace for warehouse teams</div></aside><main class="login-panel"><form class="login-card" id="login-form"><div class="eyebrow">Welcome back</div><h2>Sign in</h2><p class="muted">Use your warehouse account to continue.</p><div class="field"><label for="email">Email</label><input id="email" data-testid="login-email" type="email" autocomplete="username" required></div><div class="field"><label for="password">Password</label><input id="password" data-testid="login-password" type="password" autocomplete="current-password" required></div><div id="login-error" aria-live="polite"></div><button class="primary full" data-testid="login-submit" type="submit">Sign in</button></form></main></div>`;
  document.querySelector("#login-form").addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector("button");
    button.disabled = true;
    button.textContent = "Signing in…";
    try {
      const data = await api("/api/session", {method: "POST", body: {email: document.querySelector("#email").value, password: document.querySelector("#password").value}});
      state.token = data.token;
      state.user = data.user;
      sessionStorage.setItem("depotflow_token", data.token);
      state.view = "inventory";
      state.notice = null;
      renderShell();
      await showView();
    } catch (error) {
      document.querySelector("#login-error").replaceChildren(node("div", {className: "error", role: "alert"}, error.message));
      button.disabled = false;
      button.textContent = "Sign in";
    }
  });
}

function renderShell() {
  app.innerHTML = `<div class="shell"><aside class="sidebar"><div class="brand"><span class="brand-mark">D</span>DepotFlow</div><nav class="nav" aria-label="Main navigation"><button type="button" data-view="inventory" data-testid="nav-inventory">▦ &nbsp; Inventory</button><button type="button" data-view="orders" data-testid="nav-orders">▤ &nbsp; Orders</button><button type="button" data-view="audit" data-testid="nav-audit">◷ &nbsp; Audit history</button></nav><div class="sidebar-bottom"><div><span class="role" id="role-label"></span><strong id="tenant-label"></strong><div id="email-label" class="hint"></div></div><button class="ghost" type="button" data-testid="logout">Log out ↗</button></div></aside><main class="main"><div class="topline"><span>Warehouse workspace</span><span id="top-tenant"></span></div><div id="notice" aria-live="polite"></div><div id="content"></div></main></div>`;
  document.querySelector("#role-label").textContent = state.user.role;
  document.querySelector("#tenant-label").textContent = state.user.tenant.toUpperCase() + " warehouse";
  document.querySelector("#email-label").textContent = state.user.email;
  document.querySelector("#top-tenant").textContent = state.user.tenant.toUpperCase() + " / " + state.user.role;
  document.querySelector("[data-testid='logout']").addEventListener("click", () => {
    sessionStorage.removeItem("depotflow_token");
    state.token = null;
    state.user = null;
    renderLogin();
  });
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", async () => {
    state.view = button.dataset.view;
    state.notice = null;
    await showView();
  }));
}

async function showView() {
  document.querySelectorAll("[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === state.view));
  const content = document.querySelector("#content");
  content.replaceChildren(node("div", {className: "spinner", role: "status"}, "Loading…"));
  try {
    if (state.view === "inventory") await showInventory();
    else if (state.view === "orders") await showOrders();
    else await showAudit();
  } catch (error) {
    message(error.message);
    content.replaceChildren(node("div", {className: "empty"}, "Could not load this view."));
  }
}

async function showInventory() {
  const [inventory, dashboard] = await Promise.all([api("/api/inventory"), api("/api/dashboard")]);
  state.inventory = inventory.items;
  const content = document.querySelector("#content");
  content.innerHTML = `<div class="page-header"><div><p class="eyebrow">Overview</p><h1 class="page-title">Inventory</h1><p class="page-lead">Stock on hand, reserved units and current order activity.</p></div></div><div class="metrics" id="metrics"></div><section class="card"><h2>Current stock</h2><div class="table-wrap"><table data-testid="inventory-table"><thead><tr><th scope="col">SKU</th><th scope="col">Item</th><th scope="col">On hand</th><th scope="col">Reserved</th><th scope="col">Available</th><th scope="col">Unit price</th><th scope="col">Version</th></tr></thead><tbody id="inventory-body"></tbody></table></div></section><div id="adjustments"></div>`;
  const metrics = document.querySelector("#metrics");
  const counts = Object.entries(dashboard.orders_by_status).map(([status, count]) => `${count} ${status}`).join(" · ") || "No orders yet";
  [["On hand", dashboard.inventory_units], ["Reserved", dashboard.reserved_units], ["Orders", counts]].forEach(([label, value]) => {
    const box = node("div", {className: "metric"});
    box.append(node("span", {}, label), node("strong", {}, value));
    metrics.append(box);
  });
  const body = document.querySelector("#inventory-body");
  if (!inventory.items.length) body.append(node("tr", {}, node("td", {colspan: "7"}, "No inventory yet.")));
  for (const item of inventory.items) {
    const row = node("tr");
    [item.sku, item.name, item.on_hand, item.reserved, item.available, money(item.price_cents), item.version].forEach((value, index) => row.append(node("td", {className: index === 0 ? "sku" : ""}, value)));
    body.append(row);
  }
  if (state.user.role === "admin") renderAdjustments(inventory.items);
  renderNotice(document.querySelector("#notice"));
}

function renderAdjustments(items) {
  const container = document.querySelector("#adjustments");
  const card = node("section", {className: "card"});
  card.append(node("h2", {}, "Adjust stock"), node("p", {className: "muted"}, "Record a signed quantity and a reason. Reductions cannot consume reserved units."));
  for (const item of items) {
    const form = node("form", {className: "adjust-form"});
    form.append(node("label", {className: "small-label"}, item.sku + " · v" + item.version));
    const delta = node("input", {type: "number", step: "1", required: "", placeholder: "Delta (+ or −)", "aria-label": `Quantity change for ${item.sku}`});
    const reason = node("input", {type: "text", required: "", placeholder: "Reason", "aria-label": `Reason for ${item.sku}`});
    const button = node("button", {type: "submit", className: "secondary", "data-mutation": "true"}, "Save adjustment");
    form.append(delta, reason, button);
    form.addEventListener("submit", event => {
      event.preventDefault();
      runMutation(key => api("/api/stock/adjustments", {method: "POST", key, body: {sku: item.sku, delta: Number(delta.value), expected_version: item.version, reason: reason.value}}), async () => {
        await showInventory();
        message(`${item.sku} stock adjusted.`, "success");
      }, form);
    });
    card.append(form);
  }
  container.append(card);
}

function orderQuery(cursor = null) {
  const params = new URLSearchParams({limit: "20"});
  if (state.filters.status) params.set("status", state.filters.status);
  if (state.filters.q) params.set("q", state.filters.q);
  if (cursor) params.set("cursor", cursor);
  return "/api/orders?" + params.toString();
}

async function showOrders() {
  const [orders, inventory] = await Promise.all([api(orderQuery()), api("/api/inventory")]);
  state.orders = orders.items;
  state.orderCursor = orders.next_cursor;
  state.inventory = inventory.items;
  const content = document.querySelector("#content");
  content.innerHTML = `<div class="page-header"><div><p class="eyebrow">Fulfillment</p><h1 class="page-title">Orders</h1><p class="page-lead">Create, reserve, ship and manage returns.</p></div><div id="create-action"></div></div><section class="card"><form id="order-filters" class="toolbar"><div class="field search"><label for="search-orders">Search reference</label><input id="search-orders" type="search" placeholder="Client reference"></div><div class="field status"><label for="status-filter">Status</label><select id="status-filter"><option value="">All statuses</option><option value="draft">Draft</option><option value="reserved">Reserved</option><option value="shipped">Shipped</option><option value="returned">Returned</option><option value="cancelled">Cancelled</option></select></div><button class="secondary" type="submit">Apply filters</button></form><div class="table-wrap"><table><thead><tr><th scope="col">Reference</th><th scope="col">Status</th><th scope="col">Lines</th><th scope="col">Total</th><th scope="col">Version</th><th scope="col"></th></tr></thead><tbody id="orders-body"></tbody></table></div><div class="pagination" id="orders-page"></div></section><div id="order-workspace"></div>`;
  document.querySelector("#search-orders").value = state.filters.q;
  document.querySelector("#status-filter").value = state.filters.status;
  document.querySelector("#order-filters").addEventListener("submit", async event => {
    event.preventDefault();
    state.filters = {q: document.querySelector("#search-orders").value, status: document.querySelector("#status-filter").value};
    state.selected = null;
    await showOrders();
  });
  if (state.user.role !== "viewer") {
    const button = node("button", {className: "primary", type: "button", "data-testid": "new-order", onClick: () => renderCreateForm()}, "+ New order");
    document.querySelector("#create-action").append(button);
  }
  renderOrderRows();
  if (state.selected) {
    try {
      const current = await api(`/api/orders/${state.selected}`);
      renderOrderDetail(current);
    } catch (error) { state.selected = null; }
  }
  renderNotice(document.querySelector("#notice"));
}

function renderOrderRows() {
  const body = document.querySelector("#orders-body");
  body.replaceChildren();
  if (!state.orders.length) body.append(node("tr", {}, node("td", {colspan: "6", className: "empty"}, "No orders match these filters.")));
  for (const order of state.orders) {
    const row = node("tr");
    const pill = node("span", {className: `pill ${order.status}`}, order.status);
    const link = node("button", {className: "table-link", type: "button", onClick: async () => {
      state.selected = order.id;
      const detail = await api(`/api/orders/${order.id}`);
      renderOrderDetail(detail);
    }}, "View details");
    row.append(node("td", {className: "sku"}, order.client_ref), node("td", {}, pill), node("td", {}, order.lines.length), node("td", {}, money(order.total_cents)), node("td", {}, order.version), node("td", {}, link));
    body.append(row);
  }
  const page = document.querySelector("#orders-page");
  page.replaceChildren();
  if (state.orderCursor) page.append(node("button", {className: "secondary", type: "button", onClick: async event => {
    event.currentTarget.disabled = true;
    try {
      const more = await api(orderQuery(state.orderCursor));
      state.orders.push(...more.items);
      state.orderCursor = more.next_cursor;
      renderOrderRows();
    } catch (error) { message(error.message); event.currentTarget.disabled = false; }
  }}, "Load more orders"));
}

function renderCreateForm() {
  const host = document.querySelector("#order-workspace");
  host.innerHTML = `<section class="card"><h2>Create order</h2><p class="muted">Choose catalog items and quantities. Prices are set by the warehouse catalog.</p><form id="create-order-form"><div class="field"><label for="client-ref">Client reference</label><input id="client-ref" data-testid="order-client-ref" maxlength="200" required></div><div id="create-lines"></div><div class="orders-footer"><button type="button" class="secondary" data-testid="add-line" id="add-line">+ Add line</button><button type="submit" class="primary" data-testid="submit-order" data-mutation="true">Create order</button></div></form></section>`;
  const lines = document.querySelector("#create-lines");
  const addLine = () => {
    const grid = node("div", {className: "line-grid"});
    const skuField = node("div", {className: "field"});
    const skuId = `sku-${crypto.randomUUID()}`;
    const sku = node("select", {id: skuId, "data-testid": "line-sku"});
    for (const item of state.inventory) sku.append(node("option", {value: item.sku}, `${item.sku} · ${item.name} (${money(item.price_cents)})`));
    skuField.append(node("label", {for: skuId}, "SKU"), sku);
    const qtyField = node("div", {className: "field"});
    const qtyId = `qty-${crypto.randomUUID()}`;
    const qty = node("input", {id: qtyId, "data-testid": "line-quantity", type: "number", min: "1", step: "1", value: "1", required: ""});
    qtyField.append(node("label", {for: qtyId}, "Quantity"), qty);
    const remove = node("button", {type: "button", className: "ghost", "aria-label": "Remove line", onClick: () => grid.remove()}, "Remove");
    grid.append(skuField, qtyField, remove);
    lines.append(grid);
  };
  addLine();
  document.querySelector("#add-line").addEventListener("click", addLine);
  document.querySelector("#create-order-form").addEventListener("submit", event => {
    event.preventDefault();
    const payload = {client_ref: document.querySelector("#client-ref").value, lines: [...lines.querySelectorAll(".line-grid")].map(row => ({sku: row.querySelector("select").value, quantity: Number(row.querySelector("input").value)}))};
    runMutation(key => api("/api/orders", {method: "POST", key, body: payload}), async result => {
      state.filters = {status: "", q: ""};
      state.selected = result.id;
      await showOrders();
      message(`Order ${result.client_ref} created.`, "success");
    }, event.currentTarget);
  });
  host.scrollIntoView({behavior: "smooth", block: "start"});
}

function renderOrderDetail(order) {
  const host = document.querySelector("#order-workspace");
  host.innerHTML = `<section class="card" data-testid="order-detail"><div class="page-header"><div><p class="eyebrow">Order detail</p><h2 id="detail-ref"></h2></div><span id="detail-status" class="pill"></span></div><div class="detail-grid"><div><span>Order ID</span><strong id="detail-id"></strong></div><div><span>Total</span><strong id="detail-total"></strong></div><div><span>Version</span><strong id="detail-version"></strong></div><div><span>Lines</span><strong id="detail-count"></strong></div></div><div class="table-wrap" style="margin-top:18px"><table><thead><tr><th scope="col">SKU</th><th scope="col">Quantity</th><th scope="col">Unit price</th><th scope="col">Returned</th></tr></thead><tbody id="detail-lines"></tbody></table></div><div class="row-actions" id="detail-actions" style="margin-top:20px"></div><div id="return-area"></div></section>`;
  document.querySelector("#detail-ref").textContent = order.client_ref;
  document.querySelector("#detail-status").textContent = order.status;
  document.querySelector("#detail-status").className = `pill ${order.status}`;
  document.querySelector("#detail-id").textContent = order.id;
  document.querySelector("#detail-total").textContent = money(order.total_cents);
  document.querySelector("#detail-version").textContent = order.version;
  document.querySelector("#detail-count").textContent = order.lines.length;
  for (const line of order.lines) {
    const row = node("tr");
    [line.sku, line.quantity, money(line.unit_price_cents), line.returned_quantity].forEach(value => row.append(node("td", {}, value)));
    document.querySelector("#detail-lines").append(row);
  }
  if (state.user.role === "viewer") return;
  const actions = document.querySelector("#detail-actions");
  const action = (label, testid, endpoint, className) => {
    const button = node("button", {type: "button", className, "data-testid": testid, "data-mutation": "true"}, label);
    button.addEventListener("click", () => runMutation(
      key => api(`/api/orders/${order.id}/${endpoint}`, {method: "POST", key, body: {expected_version: order.version}}),
      async result => { await showOrders(); message(`Order ${result.client_ref} is ${result.status}.`, "success"); }, button
    ));
    actions.append(button);
  };
  if (order.status === "draft") {
    action("Reserve stock", "reserve-order", "reserve", "primary");
    action("Cancel order", "cancel-order", "cancel", "danger");
  } else if (order.status === "reserved") {
    action("Ship order", "ship-order", "ship", "primary");
    action("Cancel order", "cancel-order", "cancel", "danger");
  } else if (order.status === "shipped") renderReturnForm(order);
}

function renderReturnForm(order) {
  const host = document.querySelector("#return-area");
  const form = node("form");
  form.append(node("h2", {}, "Record a return"), node("p", {className: "muted"}, "Enter quantities for the items received. Leave others at zero."));
  for (const line of order.lines) {
    const remaining = line.quantity - line.returned_quantity;
    const grid = node("div", {className: "return-grid"});
    const id = `return-${line.sku}`;
    const input = node("input", {id, type: "number", min: "0", max: String(remaining), step: "1", value: "0", "data-testid": "return-quantity", "data-sku": line.sku});
    if (!remaining) input.disabled = true;
    grid.append(node("label", {for: id}, line.sku), node("span", {className: "muted"}, `${remaining} available to return`), input);
    form.append(grid);
  }
  form.append(node("button", {type: "submit", className: "primary", "data-testid": "submit-return", "data-mutation": "true"}, "Submit return"));
  form.addEventListener("submit", event => {
    event.preventDefault();
    const lines = [...form.querySelectorAll("[data-testid='return-quantity']")].map(input => ({sku: input.dataset.sku, quantity: Number(input.value)})).filter(line => line.quantity > 0);
    if (!lines.length) { message("Enter at least one positive return quantity."); return; }
    runMutation(key => api(`/api/orders/${order.id}/returns`, {method: "POST", key, body: {expected_version: order.version, lines}}), async result => {
      await showOrders();
      message(`Return recorded for ${result.client_ref}.`, "success");
    }, form);
  });
  host.append(form);
}

async function showAudit() {
  const page = await api("/api/audit?limit=20");
  state.audit = page.items;
  state.auditCursor = page.next_cursor;
  const content = document.querySelector("#content");
  content.innerHTML = `<p class="eyebrow">History</p><h1 class="page-title">Audit history</h1><p class="page-lead">Committed stock and order changes in chronological order.</p><section class="card"><div class="table-wrap"><table data-testid="audit-table"><thead><tr><th scope="col">ID</th><th scope="col">Action</th><th scope="col">Entity</th><th scope="col">Actor</th><th scope="col">Time</th></tr></thead><tbody id="audit-body"></tbody></table></div><div class="pagination" id="audit-page"></div></section>`;
  renderAuditRows();
  renderNotice(document.querySelector("#notice"));
}

function renderAuditRows() {
  const body = document.querySelector("#audit-body");
  body.replaceChildren();
  if (!state.audit.length) body.append(node("tr", {}, node("td", {colspan: "5", className: "empty"}, "No activity yet.")));
  for (const entry of state.audit) {
    const row = node("tr");
    [entry.id, entry.action.replaceAll("_", " "), entry.entity_id, entry.actor, new Date(entry.created_at).toLocaleString()].forEach(value => row.append(node("td", {}, value)));
    body.append(row);
  }
  const page = document.querySelector("#audit-page");
  page.replaceChildren();
  if (state.auditCursor) page.append(node("button", {className: "secondary", type: "button", onClick: async event => {
    event.currentTarget.disabled = true;
    try {
      const more = await api("/api/audit?limit=20&cursor=" + encodeURIComponent(state.auditCursor));
      state.audit.push(...more.items);
      state.auditCursor = more.next_cursor;
      renderAuditRows();
    } catch (error) { message(error.message); event.currentTarget.disabled = false; }
  }}, "Load more events"));
}

async function boot() {
  if (!state.token) return renderLogin();
  try {
    state.user = await api("/api/me");
    renderShell();
    await showView();
  } catch (error) {
    state.token = null;
    sessionStorage.removeItem("depotflow_token");
    renderLogin();
  }
}
boot();
