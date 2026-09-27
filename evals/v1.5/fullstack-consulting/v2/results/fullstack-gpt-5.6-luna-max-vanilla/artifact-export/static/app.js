(() => {
  "use strict";

  const state = {
    token: window.localStorage.getItem("depotflow_token"),
    user: null,
    view: "inventory",
    busy: false,
    busyAction: "",
    inventory: [],
    dashboard: null,
    orders: [],
    orderCursor: null,
    order: null,
    orderSearch: "",
    orderStatus: "",
    orderFormOpen: false,
    draftLines: [{ sku: "", quantity: "" }],
    draftClientRef: "",
    returnQuantities: {},
    audit: [],
    auditCursor: null,
    auditHasMore: false,
  };

  const $ = (id) => document.getElementById(id);
  const content = $("app-content");

  class ApiError extends Error {
    constructor(status, code, message) {
      super(message);
      this.status = status;
      this.code = code;
    }
  }

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }

  function button(text, className, handler, testid) {
    const node = el("button", text, className || "secondary");
    node.type = "button";
    if (testid) node.dataset.testid = testid;
    node.addEventListener("click", handler);
    return node;
  }

  function setChildren(parent, ...children) {
    parent.replaceChildren(...children.filter(Boolean));
    return parent;
  }

  function money(cents) {
    return `$${(Number(cents) / 100).toFixed(2)}`;
  }

  function humanStatus(status) {
    return status ? status[0].toUpperCase() + status.slice(1) : "";
  }

  function formatDate(value) {
    try { return new Date(value).toLocaleString(); } catch (_) { return value; }
  }

  function key(prefix) {
    if (window.crypto && window.crypto.randomUUID) return `${prefix}-${window.crypto.randomUUID()}`;
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  async function api(path, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      options = { ...options, body: JSON.stringify(options.body) };
    }
    if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
    const response = await fetch(path, { ...options, headers });
    let data = null;
    try { data = await response.json(); } catch (_) { data = {}; }
    if (!response.ok) {
      const detail = data && data.error ? data.error : { code: "http_error", message: `Request failed (${response.status})` };
      throw new ApiError(response.status, detail.code, detail.message);
    }
    return data;
  }

  function showFlash(message, isError = false) {
    const flash = $("flash");
    flash.hidden = !message;
    flash.classList.toggle("error", isError);
    flash.textContent = message || "";
  }

  function showLogin(message = "") {
    $("login-screen").hidden = false;
    $("app-shell").hidden = true;
    $("login-error").textContent = message;
  }

  function showApp() {
    $("login-screen").hidden = true;
    $("app-shell").hidden = false;
    $("tenant-label").textContent = `${state.user.tenant} tenant`;
    $("user-label").textContent = `${state.user.email} · ${state.user.role}`;
    ["inventory", "orders", "audit"].forEach((name) => {
      $(`nav-${name}`).classList.toggle("active", state.view === name);
    });
  }

  function loading(text = "Loading…") {
    setChildren(content, el("p", text, "loading"));
  }

  async function login(event) {
    event.preventDefault();
    const submit = $("login-submit");
    submit.disabled = true;
    $("login-error").textContent = "";
    try {
      const data = await api("/api/session", {
        method: "POST",
        body: { email: $("login-email").value, password: $("login-password").value },
      });
      state.token = data.token;
      state.user = data.user;
      window.localStorage.setItem("depotflow_token", state.token);
      await loadWorkspace();
      showFlash("Signed in successfully.");
    } catch (error) {
      $("login-error").textContent = error.message || "Unable to sign in.";
    } finally {
      submit.disabled = false;
    }
  }

  async function loadWorkspace() {
    showApp();
    loading();
    try {
      const [me, inventory, dashboard, orders, audit] = await Promise.all([
        api("/api/me"), api("/api/inventory"), api("/api/dashboard"), api("/api/orders?limit=20"), api("/api/audit?limit=20"),
      ]);
      state.user = me;
      state.inventory = inventory.items;
      state.dashboard = dashboard;
      state.orders = orders.items;
      state.orderCursor = orders.next_cursor;
      state.audit = audit.items;
      state.auditCursor = audit.next_cursor;
      state.auditHasMore = Boolean(audit.next_cursor);
      showApp();
      render();
    } catch (error) {
      if (error.status === 401) logout();
      else showFlash(error.message, true);
    }
  }

  function logout() {
    state.token = null;
    state.user = null;
    state.view = "inventory";
    state.order = null;
    state.orderFormOpen = false;
    window.localStorage.removeItem("depotflow_token");
    showLogin();
  }

  async function refreshInventoryDashboard() {
    const [inventory, dashboard] = await Promise.all([api("/api/inventory"), api("/api/dashboard")]);
    state.inventory = inventory.items;
    state.dashboard = dashboard;
  }

  async function refreshOrders() {
    const query = new URLSearchParams({ limit: "20" });
    if (state.orderStatus) query.set("status", state.orderStatus);
    if (state.orderSearch) query.set("q", state.orderSearch);
    const data = await api(`/api/orders?${query.toString()}`);
    state.orders = data.items;
    state.orderCursor = data.next_cursor;
  }

  async function refreshOrder(orderId = state.order && state.order.id) {
    if (!orderId) return;
    state.order = await api(`/api/orders/${encodeURIComponent(orderId)}`);
    for (const line of state.order.lines) {
      if (state.returnQuantities[line.sku] === undefined) state.returnQuantities[line.sku] = "";
    }
  }

  async function chooseView(view) {
    state.view = view;
    showApp();
    showFlash("");
    if (view === "orders" && !state.orders.length) {
      loading();
      try { await refreshOrders(); } catch (error) { showFlash(error.message, true); }
    }
    if (view === "audit") {
      loading();
      try { await loadAudit(true); } catch (error) { showFlash(error.message, true); }
    }
    render();
  }

  function render() {
    if (!state.user) return;
    showApp();
    if (state.view === "inventory") renderInventory();
    else if (state.view === "orders") renderOrders();
    else renderAudit();
  }

  function stat(label, value) {
    const card = el("div", undefined, "stat-card");
    card.append(el("div", label, "stat-label"), el("div", value, "stat-value"));
    return card;
  }

  function renderInventory() {
    const dashboard = state.dashboard || { orders_by_status: {}, inventory_units: 0, reserved_units: 0 };
    const stats = el("div", undefined, "stats-grid");
    stats.append(
      stat("Inventory units", dashboard.inventory_units),
      stat("Reserved units", dashboard.reserved_units),
      stat("Open orders", (dashboard.orders_by_status.draft || 0) + (dashboard.orders_by_status.reserved || 0)),
      stat("Shipped", dashboard.orders_by_status.shipped || 0),
    );
    const heading = el("div", undefined, "section-heading");
    const headingCopy = el("div");
    headingCopy.append(el("h2", "Inventory"), el("p", "Live stock position for this tenant.", "muted"));
    heading.append(headingCopy);
    const panel = el("section", undefined, "panel");
    const tableWrap = el("div", undefined, "table-wrap");
    const table = el("table");
    table.dataset.testid = "inventory-table";
    const head = el("thead");
    const headRow = el("tr");
    ["SKU", "On hand", "Reserved", "Available", "Price", "Version"].forEach((title, index) => {
      headRow.append(el("th", title, index > 0 ? "numeric" : ""));
    });
    head.append(headRow);
    const body = el("tbody");
    if (!state.inventory.length) body.append(emptyRow(6, "No inventory found."));
    for (const item of state.inventory) {
      const row = el("tr");
      const sku = el("td");
      sku.append(el("span", item.sku, "sku-label"), el("span", item.name, "subtext"));
      row.append(sku, cell(item.on_hand, "numeric"), cell(item.reserved, "numeric"), cell(item.available, `numeric ${item.available < 5 ? "low-stock" : ""}`), cell(money(item.price_cents), "numeric"), cell(item.version, "numeric"));
      body.append(row);
    }
    table.append(head, body); tableWrap.append(table); panel.append(tableWrap);

    const fragments = [stats, heading, panel];
    if (state.user.role === "admin") fragments.push(renderAdjustmentPanel());
    else fragments.push(el("p", "Viewer access is read-only. Inventory changes require an admin.", "role-note"));
    setChildren(content, ...fragments);
  }

  function cell(value, className = "") { return el("td", value, className); }

  function emptyRow(span, message) {
    const row = el("tr");
    const cellNode = el("td", message, "empty-state");
    cellNode.colSpan = span; row.append(cellNode); return row;
  }

  function renderAdjustmentPanel() {
    const panel = el("section", undefined, "panel");
    const heading = el("div", undefined, "panel-heading");
    heading.append(el("h3", "Adjust stock"), el("span", "Admin only", "status-badge"));
    const form = el("form");
    const grid = el("div", undefined, "admin-grid");
    const skuLabel = el("label", "SKU");
    const sku = document.createElement("select"); sku.id = "adjust-sku";
    for (const item of state.inventory) sku.append(new Option(`${item.sku} — ${item.name}`, item.sku));
    skuLabel.append(sku);
    const deltaLabel = el("label", "Signed change");
    const delta = document.createElement("input"); delta.id = "adjust-delta"; delta.type = "number"; delta.step = "1"; delta.required = true; deltaLabel.append(delta);
    const reasonLabel = el("label", "Reason");
    const reason = document.createElement("input"); reason.id = "adjust-reason"; reason.required = true; reason.placeholder = "Cycle count or receiving"; reasonLabel.append(reason);
    const submit = button("Apply adjustment", "primary", async () => {
      if (!form.reportValidity() || state.busy) return;
      const item = state.inventory.find((entry) => entry.sku === sku.value);
      state.busy = true; submit.disabled = true;
      try {
        await api("/api/stock/adjustments", { method: "POST", body: { sku: sku.value, delta: Number(delta.value), expected_version: item.version, reason: reason.value }, idempotencyKey: key("stock") });
        await refreshInventoryDashboard();
        delta.value = ""; reason.value = ""; showFlash("Stock adjustment committed."); render();
      } catch (error) { showFlash(error.message, true); }
      finally { state.busy = false; submit.disabled = false; }
    });
    grid.append(skuLabel, deltaLabel, reasonLabel, submit); form.append(grid); panel.append(heading, form); return panel;
  }

  function renderOrders() {
    const heading = el("div", undefined, "section-heading");
    const copy = el("div"); copy.append(el("h2", "Orders"), el("p", "Receive, reserve, ship, and return tenant orders.", "muted"));
    heading.append(copy);
    if (state.user.role !== "viewer") heading.append(button("New order", "primary", () => { state.orderFormOpen = true; showFlash(""); render(); }, "new-order"));
    const toolbar = el("div", undefined, "toolbar");
    const searchWrap = el("div", "", "toolbar-field search");
    const searchLabel = el("label", "Search client reference");
    const search = document.createElement("input"); search.type = "search"; search.value = state.orderSearch; search.placeholder = "e.g. web-1042"; searchLabel.append(search); searchWrap.append(searchLabel);
    const statusWrap = el("div", undefined, "toolbar-field");
    const statusLabel = el("label", "Status"); const status = document.createElement("select");
    const statusOptions = [["", "All statuses"], ["draft", "Draft"], ["reserved", "Reserved"], ["shipped", "Shipped"], ["cancelled", "Cancelled"], ["returned", "Returned"]];
    statusOptions.forEach(([value, label]) => status.append(new Option(label, value))); status.value = state.orderStatus; statusLabel.append(status); statusWrap.append(statusLabel);
    const apply = button("Apply filters", "secondary", async () => {
      state.orderSearch = search.value; state.orderStatus = status.value; state.order = null; state.orderCursor = null; loading();
      try { await refreshOrders(); render(); } catch (error) { showFlash(error.message, true); render(); }
    });
    toolbar.append(searchWrap, statusWrap, apply);
    if (state.orderFormOpen) return setChildren(content, heading, renderOrderForm(), toolbar);
    const layout = el("div", undefined, "order-layout");
    const listPanel = el("section", undefined, "panel order-list");
    if (!state.orders.length) listPanel.append(el("div", "No orders match these filters.", "empty-state"));
    state.orders.forEach((order) => {
      const item = button("", `order-list-item ${state.order && state.order.id === order.id ? "selected" : ""}`, async () => {
        try { await refreshOrder(order.id); showFlash(""); render(); } catch (error) { showFlash(error.message, true); }
      });
      item.dataset.orderId = order.id;
      const ref = el("span", order.client_ref, "order-list-ref");
      const meta = el("span", undefined, "order-list-meta"); meta.append(el("span", humanStatus(order.status)), el("span", `${order.lines.length} line${order.lines.length === 1 ? "" : "s"}`));
      item.append(ref, meta); listPanel.append(item);
    });
    if (state.orderCursor) {
      listPanel.append(button("Load more", "secondary small-button", async () => {
        try {
          const query = new URLSearchParams({ limit: "20", cursor: state.orderCursor }); if (state.orderStatus) query.set("status", state.orderStatus); if (state.orderSearch) query.set("q", state.orderSearch);
          const data = await api(`/api/orders?${query.toString()}`); state.orders.push(...data.items); state.orderCursor = data.next_cursor; render();
        } catch (error) { showFlash(error.message, true); }
      }));
    }
    const detailPanel = el("section", undefined, "panel");
    if (state.order) detailPanel.append(renderOrderDetail());
    else { const emptyDetail = el("div", "Choose an order to inspect its lifecycle.", "empty-state"); emptyDetail.dataset.testid = "order-detail"; detailPanel.append(emptyDetail); }
    layout.append(listPanel, detailPanel);
    setChildren(content, heading, toolbar, layout);
  }

  function renderOrderForm() {
    const panel = el("section", undefined, "panel order-form");
    const heading = el("div", undefined, "panel-heading"); heading.append(el("h3", "Create order"), button("Close", "secondary small-button", () => { state.orderFormOpen = false; render(); }));
    const form = el("form");
    const clientLabel = el("label", "Client reference");
    const clientInput = document.createElement("input"); clientInput.id = "order-client-ref"; clientInput.dataset.testid = "order-client-ref"; clientInput.required = true; clientInput.placeholder = "shopify-1042"; clientInput.value = state.draftClientRef; clientInput.addEventListener("input", () => { state.draftClientRef = clientInput.value; }); clientLabel.append(clientInput);
    const linesHeading = el("div", undefined, "panel-heading"); linesHeading.append(el("h3", "Order lines"));
    const lineEditor = el("div", undefined, "line-editor");
    state.draftLines.forEach((line, index) => {
      const row = el("div", undefined, "line-row");
      const skuLabel = el("label", "SKU"); const sku = document.createElement("select"); sku.dataset.testid = "line-sku"; sku.required = true; sku.append(new Option("Select SKU", ""));
      state.inventory.forEach((item) => sku.append(new Option(`${item.sku} — ${item.name}`, item.sku))); sku.value = line.sku; sku.addEventListener("change", () => { line.sku = sku.value; }); skuLabel.append(sku);
      const quantityLabel = el("label", "Quantity"); const quantity = document.createElement("input"); quantity.dataset.testid = "line-quantity"; quantity.type = "number"; quantity.min = "1"; quantity.step = "1"; quantity.required = true; quantity.value = line.quantity; quantity.addEventListener("input", () => { line.quantity = quantity.value; }); quantityLabel.append(quantity);
      row.append(skuLabel, quantityLabel);
      if (state.draftLines.length > 1) row.append(button("Remove", "danger small-button remove-line", () => { state.draftLines.splice(index, 1); render(); }));
      lineEditor.append(row);
    });
    const add = button("+ Add line", "secondary small-button", () => { state.draftLines.push({ sku: "", quantity: "" }); render(); }, "add-line");
    const submit = button("Create draft order", "primary", async () => {
      if (state.busy || !form.reportValidity()) return;
      state.busy = true; submit.disabled = true;
      try {
        const data = await api("/api/orders", { method: "POST", body: { client_ref: state.draftClientRef, lines: state.draftLines.map((line) => ({ sku: line.sku, quantity: Number(line.quantity) })) }, idempotencyKey: key("order") });
        state.orderFormOpen = false; state.draftClientRef = ""; state.draftLines = [{ sku: "", quantity: "" }]; state.order = data; await Promise.all([refreshOrders(), refreshInventoryDashboard()]); showFlash("Draft order created."); render();
      } catch (error) { showFlash(error.message, true); }
      finally { state.busy = false; submit.disabled = false; }
    }, "submit-order");
    form.append(clientLabel, linesHeading, lineEditor, add, el("div", undefined, "form-actions")); form.lastChild.append(submit); panel.append(heading, form); return panel;
  }

  function renderOrderDetail() {
    const wrapper = el("div"); wrapper.dataset.testid = "order-detail";
    const header = el("div", undefined, "order-detail-header");
    const title = el("div"); title.append(el("h3", state.order.client_ref));
    const badge = el("span", humanStatus(state.order.status), `status-badge ${state.order.status}`); title.append(badge); header.append(title);
    const actions = el("div", undefined, "order-detail-actions");
    if (state.user.role !== "viewer") {
      if (state.order.status === "draft") actions.append(actionButton("Reserve", "reserve-order", "reserve"));
      if (state.order.status === "reserved") actions.append(actionButton("Ship", "ship-order", "ship"));
      if (state.order.status === "draft" || state.order.status === "reserved") actions.append(actionButton("Cancel", "cancel-order", "cancel", "danger"));
    }
    header.append(actions); wrapper.append(header);
    const meta = el("div", undefined, "detail-meta");
    meta.append(el("span", undefined)); meta.lastChild.append(el("strong", "Client ref: "), el("span", state.order.client_ref));
    const version = el("span"); version.append(el("strong", "Version: "), el("span", state.order.version)); meta.append(version); wrapper.append(meta);
    const tableWrap = el("div", undefined, "table-wrap"); const table = el("table"); const head = el("thead"); const headRow = el("tr"); ["SKU", "Quantity", "Unit price", "Returned"].forEach((name, index) => headRow.append(el("th", name, index ? "numeric" : ""))); head.append(headRow);
    const body = el("tbody"); state.order.lines.forEach((line) => { const row = el("tr"); row.append(cell(line.sku), cell(line.quantity, "numeric"), cell(money(line.unit_price_cents), "numeric"), cell(line.returned_quantity, "numeric")); body.append(row); }); table.append(head, body); tableWrap.append(table); wrapper.append(tableWrap);
    if (state.user.role !== "viewer" && state.order.status === "shipped") {
      const returnPanel = el("div", undefined, "panel"); returnPanel.style.marginTop = "16px"; returnPanel.append(el("h3", "Process return"), el("p", "Enter returned units; a full return closes the order.", "muted"));
      const form = el("form"); state.order.lines.forEach((line) => { const row = el("div", undefined, "return-row"); const label = el("label", `${line.sku} · shipped ${line.quantity - line.returned_quantity} remaining`); const input = document.createElement("input"); input.dataset.testid = "return-quantity"; input.type = "number"; input.min = "0"; input.max = String(line.quantity - line.returned_quantity); input.step = "1"; input.value = state.returnQuantities[line.sku] || ""; input.addEventListener("input", () => { state.returnQuantities[line.sku] = input.value; }); label.append(input); row.append(label, el("span")); form.append(row); });
      const submit = button("Submit return", "primary", async () => {
        if (state.busy || !form.reportValidity()) return;
        const lines = state.order.lines.map((line) => ({ sku: line.sku, quantity: Number(state.returnQuantities[line.sku] || 0) })).filter((line) => line.quantity > 0);
        if (!lines.length) { showFlash("Enter at least one returned unit.", true); return; }
        state.busy = true; submit.disabled = true;
        try { const data = await api(`/api/orders/${encodeURIComponent(state.order.id)}/returns`, { method: "POST", body: { expected_version: state.order.version, lines }, idempotencyKey: key("return") }); state.order = data; state.returnQuantities = {}; await Promise.all([refreshOrders(), refreshInventoryDashboard()]); showFlash("Return committed."); render(); }
        catch (error) { showFlash(error.message, true); if (error.code === "stale_version") { try { await refreshOrder(); render(); } catch (_) {} } }
        finally { state.busy = false; submit.disabled = false; }
      }, "submit-return"); form.append(el("div", undefined, "form-actions")); form.lastChild.append(submit); returnPanel.append(form); wrapper.append(returnPanel);
    }
    return wrapper;
  }

  function actionButton(label, testid, action, style = "secondary") {
    return button(label, `${style} small-button`, () => mutateOrder(action), testid);
  }

  async function mutateOrder(action) {
    if (state.busy || !state.order) return;
    state.busy = true;
    const expected = state.order.version;
    try {
      const data = await api(`/api/orders/${encodeURIComponent(state.order.id)}/${action}`, { method: "POST", body: { expected_version: expected }, idempotencyKey: key(`order-${action}`) });
      state.order = data; await Promise.all([refreshOrders(), refreshInventoryDashboard()]);
      const actionWords = { reserve: "reserved", ship: "shipped", cancel: "cancelled" };
      showFlash(`Order ${actionWords[action] || action} successfully.`); render();
    } catch (error) { showFlash(error.message, true); if (error.code === "stale_version") { try { await refreshOrder(); render(); } catch (_) {} } }
    finally { state.busy = false; }
  }

  async function loadAudit(reset = false) {
    if (reset) { state.audit = []; state.auditCursor = null; }
    const query = new URLSearchParams({ limit: "20" });
    if (state.auditCursor) query.set("cursor", state.auditCursor);
    const data = await api(`/api/audit?${query.toString()}`);
    if (state.auditCursor) state.audit.push(...data.items); else state.audit = data.items;
    state.auditCursor = data.next_cursor; state.auditHasMore = Boolean(data.next_cursor);
  }

  function renderAudit() {
    const heading = el("div", undefined, "section-heading"); const copy = el("div"); copy.append(el("h2", "Audit trail"), el("p", "Committed changes for this tenant, oldest first.", "muted")); heading.append(copy);
    const panel = el("section", undefined, "panel"); const wrap = el("div", undefined, "table-wrap"); const table = el("table"); table.dataset.testid = "audit-table"; const head = el("thead"); const row = el("tr"); ["Time", "Action", "Entity", "Actor"].forEach((value) => row.append(el("th", value))); head.append(row); const body = el("tbody");
    if (!state.audit.length) body.append(emptyRow(4, "No committed events yet."));
    state.audit.forEach((event) => { const tr = el("tr"); tr.append(cell(formatDate(event.created_at)), cell(event.action, "audit-action"), cell(event.entity_id), cell(event.actor)); body.append(tr); }); table.append(head, body); wrap.append(table); panel.append(wrap);
    if (state.auditHasMore) { const pagination = el("div", undefined, "pagination-row"); pagination.append(button("Load more", "secondary", async () => { try { await loadAudit(); render(); } catch (error) { showFlash(error.message, true); } })); panel.append(pagination); }
    setChildren(content, heading, panel);
  }

  $("login-form").addEventListener("submit", login);
  $("logout").addEventListener("click", logout);
  $("nav-inventory").addEventListener("click", () => chooseView("inventory"));
  $("nav-orders").addEventListener("click", () => chooseView("orders"));
  $("nav-audit").addEventListener("click", () => chooseView("audit"));

  (async () => {
    if (!state.token) { showLogin(); return; }
    try {
      state.user = await api("/api/me");
      await loadWorkspace();
    } catch (_) {
      state.token = null; window.localStorage.removeItem("depotflow_token"); showLogin("Your session has expired. Please sign in again.");
    }
  })();
})();
