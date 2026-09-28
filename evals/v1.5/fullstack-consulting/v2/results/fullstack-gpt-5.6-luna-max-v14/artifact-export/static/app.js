(function () {
  "use strict";

  const state = {
    token: localStorage.getItem("depotflow-token"),
    user: null,
    view: "inventory",
    inventory: [],
    orders: [],
    selectedOrderId: null,
    compose: false,
    draftClientRef: "",
    draftLines: [{ sku: "", quantity: 1 }],
    orderFilters: { status: "", q: "" },
    orderCursor: null,
    auditCursor: null,
    busy: false,
  };

  const root = document.getElementById("app");

  function el(tag, props, children) {
    const node = document.createElement(tag);
    const attributes = props || {};
    Object.entries(attributes).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      if (key === "className") node.className = value;
      else if (key === "textContent") node.textContent = value;
      else if (key === "checked" || key === "disabled" || key === "selected" || key === "required") node[key] = Boolean(value);
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, String(value));
    });
    (children || []).forEach((child) => {
      if (child !== null && child !== undefined) node.append(child.nodeType ? child : document.createTextNode(String(child)));
    });
    return node;
  }

  function formatMoney(cents) {
    return `$${(Number(cents) / 100).toFixed(2)}`;
  }

  function titleCase(value) {
    return String(value).charAt(0).toUpperCase() + String(value).slice(1);
  }

  function formatDate(value) {
    try { return new Date(value).toLocaleString(); } catch (_) { return value; }
  }

  function setNotice(message, kind) {
    const notice = document.getElementById("notice");
    if (!notice) return;
    notice.className = `notice ${kind || ""}`;
    notice.textContent = message || "";
  }

  function errorMessage(err) {
    return err && err.message ? err.message : "The request could not be completed.";
  }

  async function api(path, options) {
    const opts = options || {};
    const headers = { Accept: "application/json" };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (opts.mutation) headers["Idempotency-Key"] = opts.idempotencyKey || crypto.randomUUID();
    const response = await fetch(path, {
      method: opts.method || "GET",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    let data;
    try { data = await response.json(); } catch (_) { data = {}; }
    if (!response.ok) {
      const err = new Error(data.error && data.error.message ? data.error.message : `Request failed (${response.status})`);
      err.status = response.status;
      err.code = data.error && data.error.code;
      throw err;
    }
    return data;
  }

  function renderLogin() {
    state.user = null;
    const email = el("input", { id: "login-email-input", type: "email", autocomplete: "username", required: true, "data-testid": "login-email" });
    const password = el("input", { id: "login-password-input", type: "password", autocomplete: "current-password", required: true, "data-testid": "login-password" });
    const feedback = el("p", { className: "notice", role: "status", "aria-live": "polite" });
    const form = el("form", { className: "stack" }, [
      el("label", {}, ["Email", email]),
      el("label", {}, ["Password", password]),
      el("button", { className: "button primary", type: "submit", "data-testid": "login-submit" }, ["Sign in"]),
      feedback,
    ]);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = form.querySelector("[data-testid=login-submit]");
      submit.disabled = true;
      feedback.className = "notice pending";
      feedback.textContent = "Signing in…";
      try {
        const data = await api("/api/session", { method: "POST", body: { email: email.value, password: password.value } });
        state.token = data.token;
        state.user = data.user;
        localStorage.setItem("depotflow-token", state.token);
        renderApp();
        navigate("inventory");
      } catch (err) {
        feedback.className = "notice error";
        feedback.textContent = errorMessage(err);
        submit.disabled = false;
      }
    });
    root.replaceChildren(el("div", { className: "login-shell" }, [
      el("section", { className: "login-card", "aria-labelledby": "login-title" }, [
        el("p", { className: "eyebrow" }, ["Fulfillment operations"]),
        el("h1", { className: "brand", id: "login-title" }, ["DepotFlow"]),
        el("p", { className: "muted" }, ["Sign in to manage inventory, orders, and audit history."]),
        form,
      ]),
    ]));
  }

  function renderApp() {
    const navItems = [
      ["inventory", "Inventory", "nav-inventory"],
      ["orders", "Orders", "nav-orders"],
      ["audit", "Audit", "nav-audit"],
    ];
    const nav = el("nav", { className: "nav-list", "aria-label": "Main navigation" }, navItems.map(([view, label, testid]) => {
      const button = el("button", { className: "nav-button", type: "button", "data-view": view, "data-testid": testid }, [label]);
      button.addEventListener("click", () => navigate(view));
      return button;
    }));
    const logout = el("button", { className: "button secondary", type: "button", "data-testid": "logout" }, ["Log out"]);
    logout.addEventListener("click", () => {
      state.token = null;
      state.user = null;
      localStorage.removeItem("depotflow-token");
      renderLogin();
    });
    const sidebar = el("aside", { className: "sidebar" }, [
      el("div", {}, [el("p", { className: "brand" }, ["DepotFlow"]), el("p", { className: "tenant-chip" }, [`${state.user.tenant} warehouse`])]),
      nav,
      el("div", { className: "sidebar-footer" }, [
        el("div", { className: "small" }, [`${state.user.email} · ${state.user.role}`]),
        logout,
      ]),
    ]);
    const content = el("section", { className: "content", id: "content", "aria-live": "polite" });
    const main = el("main", { className: "main-area" }, [
      el("header", { className: "topbar" }, [
        el("div", {}, [el("p", { className: "eyebrow" }, ["Operations console"]), el("h1", { id: "page-title" }, ["Inventory"])]),
        el("div", { className: "user-badge" }, ["Signed in as ", el("strong", {}, [state.user.email])]),
      ]),
      el("div", { id: "notice", className: "notice", role: "status", "aria-live": "polite" }),
      content,
    ]);
    root.replaceChildren(el("div", { className: "app-shell" }, [sidebar, main]));
  }

  function updateNav(view) {
    document.querySelectorAll(".nav-button").forEach((button) => {
      button.classList.toggle("active", button.getAttribute("data-view") === view);
    });
    const title = document.getElementById("page-title");
    if (title) title.textContent = view === "inventory" ? "Inventory" : titleCase(view);
  }

  async function navigate(view) {
    state.view = view;
    updateNav(view);
    const content = document.getElementById("content");
    if (!content) return;
    content.replaceChildren(el("p", { className: "loading" }, ["Loading…"]));
    setNotice("", "");
    if (view === "inventory") await renderInventory(content);
    else if (view === "orders") await renderOrders(content);
    else await renderAudit(content);
  }

  function metric(label, value) {
    return el("div", { className: "metric" }, [el("span", { className: "value" }, [String(value)]), el("span", { className: "label" }, [label])]);
  }

  async function renderInventory(content) {
    try {
      const [dashboard, inventory] = await Promise.all([api("/api/dashboard"), api("/api/inventory")]);
      if (state.view !== "inventory") return;
      state.inventory = inventory.items;
      const counts = dashboard.orders_by_status || {};
      const metrics = el("div", { className: "metric-grid" }, [
        metric("Inventory units", dashboard.inventory_units),
        metric("Reserved units", dashboard.reserved_units),
        metric("Open orders", Number(counts.draft || 0) + Number(counts.reserved || 0)),
        metric("Shipped orders", counts.shipped || 0),
      ]);
      const table = el("table", { "data-testid": "inventory-table" });
      table.append(el("thead", {}, [el("tr", {}, [
        el("th", {}, ["SKU"]), el("th", {}, ["Name"]), el("th", { className: "number" }, ["On hand"]),
        el("th", { className: "number" }, ["Reserved"]), el("th", { className: "number" }, ["Available"]),
        el("th", { className: "number" }, ["Price"]), el("th", { className: "number" }, ["Version"]),
      ])]));
      const body = el("tbody");
      state.inventory.forEach((item) => body.append(el("tr", {}, [
        el("td", {}, [el("strong", {}, [item.sku])]), el("td", {}, [item.name]),
        el("td", { className: "number" }, [String(item.on_hand)]), el("td", { className: "number" }, [String(item.reserved)]),
        el("td", { className: "number" }, [String(item.available)]), el("td", { className: "number" }, [formatMoney(item.price_cents)]),
        el("td", { className: "number" }, [String(item.version)]),
      ])));
      table.append(body);
      const inventoryCard = el("section", { className: "card" }, [
        el("div", { className: "split" }, [el("div", {}, [el("h2", {}, ["Current stock"]), el("p", { className: "muted small" }, ["Available = on hand − reserved."])]),]),
        state.inventory.length ? el("div", { className: "table-wrap" }, [table]) : el("p", { className: "empty" }, ["No inventory found."]),
      ]);
      const children = [el("section", { className: "metric-grid" }, [metrics]), inventoryCard];
      if (state.user.role === "admin") children.push(stockAdjustmentCard());
      content.replaceChildren(...children);
    } catch (err) {
      content.replaceChildren(el("section", { className: "card" }, [el("p", { className: "error-copy" }, [errorMessage(err)])]));
    }
  }

  function stockAdjustmentCard() {
    const sku = el("select", { id: "adjust-sku" });
    state.inventory.forEach((item) => sku.append(el("option", { value: item.sku }, [item.sku])));
    const delta = el("input", { id: "adjust-delta", type: "number", step: "1", required: true });
    const reason = el("input", { id: "adjust-reason", required: true, placeholder: "Cycle count or receiving note" });
    const form = el("form", { className: "toolbar" }, [
      el("label", {}, ["SKU", sku]), el("label", {}, ["Signed delta", delta]), el("label", {}, ["Reason", reason]),
      el("button", { className: "button secondary", type: "submit" }, ["Adjust stock"]),
    ]);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const item = state.inventory.find((entry) => entry.sku === sku.value);
      const button = form.querySelector("button");
      button.disabled = true;
      setNotice("Saving stock adjustment…", "pending");
      try {
        await api("/api/stock/adjustments", { method: "POST", mutation: true, body: { sku: sku.value, delta: Number(delta.value), expected_version: item.version, reason: reason.value } });
        await navigate("inventory");
        setNotice("Stock adjustment saved.", "success");
      } catch (err) {
        setNotice(errorMessage(err), "error");
        button.disabled = false;
      }
    });
    return el("section", { className: "card" }, [el("h2", {}, ["Admin stock adjustment"]), el("p", { className: "muted small" }, ["Adjustments use the current inventory version." ]), form]);
  }

  function statusPill(status) {
    return el("span", { className: `status-pill ${status}` }, [titleCase(status)]);
  }

  async function loadOrders() {
    const params = new URLSearchParams();
    if (state.orderFilters.status) params.set("status", state.orderFilters.status);
    if (state.orderFilters.q) params.set("q", state.orderFilters.q);
    params.set("limit", "20");
    if (state.orderCursor) params.set("cursor", state.orderCursor);
    return api(`/api/orders?${params.toString()}`);
  }

  async function renderOrders(content) {
    let inventory;
    try {
      if (!state.inventory.length) state.inventory = (await api("/api/inventory")).items;
      inventory = state.inventory;
      const heading = el("div", { className: "split" }, [
        el("div", {}, [el("h2", {}, ["Orders"]), el("p", { className: "muted small" }, ["Oldest orders appear first."])]),
        state.user.role !== "viewer" ? el("button", { className: "button primary", type: "button", "data-testid": "new-order" }, ["New order"]) : null,
      ]);
      const filterForm = el("form", { className: "toolbar" }, [
        el("label", {}, ["Search client reference", el("input", { type: "search", value: state.orderFilters.q, placeholder: "e.g. web-1042" })]),
        el("label", {}, ["Status", el("select", {}, [el("option", { value: "" }, ["All statuses"]), ...["draft", "reserved", "shipped", "cancelled", "returned"].map((status) => el("option", { value: status, selected: state.orderFilters.status === status }, [titleCase(status)]))])]),
        el("button", { className: "button secondary", type: "submit" }, ["Apply filters"]),
      ]);
      filterForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const inputs = filterForm.querySelectorAll("input, select");
        state.orderFilters.q = inputs[0].value;
        state.orderFilters.status = inputs[1].value;
        state.orderCursor = null;
        renderOrders(content);
      });
      const listCard = el("section", { className: "card" }, [heading, filterForm, el("div", { className: "loading" }, ["Loading orders…"]) ]);
      content.replaceChildren();
      content.append(listCard);
      const newButton = listCard.querySelector("[data-testid=new-order]");
      if (newButton) newButton.addEventListener("click", () => {
        state.compose = true;
        state.draftClientRef = "";
        state.draftLines = [{ sku: inventory[0] ? inventory[0].sku : "", quantity: 1 }];
        renderOrders(content);
      });
      if (state.compose) listCard.append(buildOrderForm(content, inventory));
      const result = await loadOrders();
      if (state.view !== "orders") return;
      state.orders = result.items;
      const list = el("div", { className: "order-list" });
      if (!state.orders.length) list.append(el("p", { className: "empty" }, ["No orders match these filters."]));
      state.orders.forEach((order) => {
        const open = el("button", { className: "button link", type: "button" }, ["View details"]);
        open.addEventListener("click", () => { state.selectedOrderId = order.id; state.compose = false; renderOrders(content); });
        list.append(el("div", { className: "order-row" }, [
          el("div", {}, [el("strong", {}, [order.client_ref]), el("div", { className: "order-row-meta" }, [`${order.lines.length} line(s) · ${formatMoney(order.total_cents)} · v${order.version}`])]),
          el("div", { className: "row" }, [statusPill(order.status), open]),
        ]));
      });
      const paging = [];
      if (result.next_cursor) {
        const next = el("button", { className: "button secondary", type: "button" }, ["Load older orders"]);
        next.addEventListener("click", () => { state.orderCursor = result.next_cursor; renderOrders(content); });
        paging.push(next);
      }
      const listMount = el("div", { className: "stack" }, [list, el("div", { className: "row" }, paging)]);
      listCard.replaceChildren(heading, filterForm, listMount);
      if (state.compose) listCard.append(buildOrderForm(content, inventory));
      if (state.selectedOrderId) {
        const detailMount = el("section", { className: "card" }, [el("p", { className: "loading" }, ["Loading order detail…"])]);
        content.append(detailMount);
        await renderOrderDetail(detailMount, state.selectedOrderId);
      }
    } catch (err) {
      content.replaceChildren(el("section", { className: "card" }, [el("p", { className: "error-copy" }, [errorMessage(err)])]));
    }
  }

  function buildOrderForm(content, inventory) {
    const clientRef = el("input", { type: "text", required: true, value: state.draftClientRef, placeholder: "Unique tenant reference", "data-testid": "order-client-ref" });
    clientRef.addEventListener("input", () => { state.draftClientRef = clientRef.value; });
    const lineWrap = el("div", { className: "stack" });
    const renderLines = () => {
      lineWrap.replaceChildren();
      state.draftLines.forEach((line, index) => {
        const select = el("select", { "data-testid": "line-sku" });
        inventory.forEach((item) => select.append(el("option", { value: item.sku, selected: item.sku === line.sku }, [`${item.sku} — ${item.name}`])));
        select.addEventListener("change", () => { state.draftLines[index].sku = select.value; });
        const quantity = el("input", { type: "number", min: "1", step: "1", required: true, value: line.quantity, "data-testid": "line-quantity" });
        quantity.addEventListener("input", () => { state.draftLines[index].quantity = quantity.value === "" ? "" : Number(quantity.value); });
        const remove = el("button", { className: "button secondary line-remove", type: "button" }, ["Remove"]);
        remove.disabled = state.draftLines.length === 1;
        remove.addEventListener("click", () => { state.draftLines.splice(index, 1); renderLines(); });
        lineWrap.append(el("div", { className: "line-editor" }, [el("label", {}, ["SKU", select]), el("label", {}, ["Quantity", quantity]), remove]));
      });
    };
    renderLines();
    const add = el("button", { className: "button secondary", type: "button", "data-testid": "add-line" }, ["Add line"]);
    add.addEventListener("click", () => { state.draftLines.push({ sku: inventory[0] ? inventory[0].sku : "", quantity: 1 }); renderLines(); });
    const submit = el("button", { className: "button primary", type: "submit", "data-testid": "submit-order" }, ["Create order"]);
    const form = el("form", { className: "card stack" }, [el("div", {}, [el("h2", {}, ["New order"]), el("p", { className: "muted small" }, ["Prices are taken from the server catalog."])]), el("label", {}, ["Client reference", clientRef]), el("div", {}, [el("h3", {}, ["Lines"]), lineWrap]), el("div", { className: "row form-actions" }, [add, submit])]);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      setNotice("Creating order…", "pending");
      try {
        const data = await api("/api/orders", { method: "POST", mutation: true, body: { client_ref: state.draftClientRef, lines: state.draftLines.map((line) => ({ sku: line.sku, quantity: Number(line.quantity) })) } });
        state.compose = false;
        state.selectedOrderId = data.id;
        state.orderCursor = null;
        state.draftClientRef = "";
        state.draftLines = [{ sku: inventory[0] ? inventory[0].sku : "", quantity: 1 }];
        await renderOrders(content);
        setNotice("Order created.", "success");
      } catch (err) {
        setNotice(errorMessage(err), "error");
        submit.disabled = false;
      }
    });
    return form;
  }

  async function renderOrderDetail(mount, orderId) {
    try {
      const order = await api(`/api/orders/${encodeURIComponent(orderId)}`);
      const detail = el("section", { "data-testid": "order-detail" }, [
        el("div", { className: "split" }, [el("div", {}, [el("h2", {}, ["Order detail"]), el("p", { className: "muted small" }, [`Version ${order.version}`])]), statusPill(order.status)]),
        el("div", { className: "detail-grid" }, [
          el("div", {}, [el("span", { className: "muted small" }, ["Client reference"]), el("div", { className: "detail-value" }, [order.client_ref])]),
          el("div", {}, [el("span", { className: "muted small" }, ["Status"]), el("div", { className: "detail-value" }, [order.status])]),
          el("div", {}, [el("span", { className: "muted small" }, ["Total"]), el("div", { className: "detail-value" }, [formatMoney(order.total_cents)])]),
        ]),
      ]);
      const lineTable = el("table", { className: "order-lines" }, [el("thead", {}, [el("tr", {}, [el("th", {}, ["SKU"]), el("th", { className: "number" }, ["Quantity"]), el("th", { className: "number" }, ["Unit price"]), el("th", { className: "number" }, ["Returned"])] )]), el("tbody")]);
      const lineBody = lineTable.querySelector("tbody");
      order.lines.forEach((line) => lineBody.append(el("tr", {}, [el("td", {}, [line.sku]), el("td", { className: "number" }, [String(line.quantity)]), el("td", { className: "number" }, [formatMoney(line.unit_price_cents)]), el("td", { className: "number" }, [String(line.returned_quantity)])])));
      detail.append(el("div", { className: "table-wrap" }, [lineTable]));
      if (state.user.role !== "viewer") {
        const actions = el("div", { className: "action-bar" });
        if (order.status === "draft") {
          const reserve = el("button", { className: "button primary", type: "button", "data-testid": "reserve-order" }, ["Reserve stock"]);
          reserve.addEventListener("click", () => runOrderAction(`/api/orders/${order.id}/reserve`, { expected_version: order.version }, reserve, "Order reserved."));
          actions.append(reserve);
        }
        if (order.status === "reserved") {
          const ship = el("button", { className: "button primary", type: "button", "data-testid": "ship-order" }, ["Ship order"]);
          ship.addEventListener("click", () => runOrderAction(`/api/orders/${order.id}/ship`, { expected_version: order.version }, ship, "Order shipped."));
          actions.append(ship);
        }
        if (order.status === "draft" || order.status === "reserved") {
          const cancel = el("button", { className: "button danger", type: "button", "data-testid": "cancel-order" }, ["Cancel order"]);
          cancel.addEventListener("click", () => runOrderAction(`/api/orders/${order.id}/cancel`, { expected_version: order.version }, cancel, "Order cancelled."));
          actions.append(cancel);
        }
        detail.append(actions);
        if (order.status === "shipped") detail.append(buildReturnForm(order));
      }
      mount.replaceChildren(detail);
    } catch (err) {
      mount.replaceChildren(el("p", { className: "error-copy" }, [errorMessage(err)]));
    }
  }

  async function runOrderAction(path, body, button, successMessage) {
    button.disabled = true;
    setNotice("Saving order transition…", "pending");
    try {
      const data = await api(path, { method: "POST", mutation: true, body });
      state.selectedOrderId = data.id;
      await navigate("orders");
      setNotice(successMessage, "success");
    } catch (err) {
      setNotice(errorMessage(err), "error");
      button.disabled = false;
    }
  }

  function buildReturnForm(order) {
    const lineInputs = [];
    const lineWrap = el("div", { className: "stack" });
    order.lines.forEach((line) => {
      const remaining = line.quantity - line.returned_quantity;
      const input = el("input", { type: "number", min: "1", max: String(Math.max(remaining, 1)), step: "1", value: "", disabled: remaining <= 0, "data-testid": "return-quantity" });
      lineInputs.push({ sku: line.sku, input });
      lineWrap.append(el("label", {}, [`${line.sku} (up to ${remaining})`, input]));
    });
    const submit = el("button", { className: "button secondary", type: "submit", "data-testid": "submit-return" }, ["Submit return"]);
    const form = el("form", { className: "card stack" }, [el("div", {}, [el("h3", {}, ["Record a return"]), el("p", { className: "muted small" }, ["Returned units are added back to on-hand stock."])]), lineWrap, submit]);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const lines = lineInputs.filter((entry) => entry.input.value !== "").map((entry) => ({ sku: entry.sku, quantity: Number(entry.input.value) }));
      if (!lines.length) { setNotice("Enter a positive return quantity.", "error"); return; }
      submit.disabled = true;
      setNotice("Saving return…", "pending");
      try {
        const data = await api(`/api/orders/${order.id}/returns`, { method: "POST", mutation: true, body: { expected_version: order.version, lines } });
        state.selectedOrderId = data.id;
        await navigate("orders");
        setNotice("Return recorded.", "success");
      } catch (err) {
        setNotice(errorMessage(err), "error");
        submit.disabled = false;
      }
    });
    return form;
  }

  async function renderAudit(content) {
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (state.auditCursor) params.set("cursor", state.auditCursor);
      const data = await api(`/api/audit?${params.toString()}`);
      if (state.view !== "audit") return;
      const table = el("table", { "data-testid": "audit-table" }, [el("thead", {}, [el("tr", {}, [el("th", {}, ["Time"]), el("th", {}, ["Action"]), el("th", {}, ["Entity"]), el("th", {}, ["Actor"])] )]), el("tbody")]);
      const body = table.querySelector("tbody");
      data.items.forEach((item) => body.append(el("tr", {}, [el("td", {}, [formatDate(item.created_at)]), el("td", {}, [item.action]), el("td", {}, [item.entity_id]), el("td", {}, [item.actor])] )));
      const card = el("section", { className: "card" }, [el("h2", {}, ["Audit history"]), el("p", { className: "muted small" }, ["Successful stock and order mutations are recorded here."]), data.items.length ? el("div", { className: "table-wrap" }, [table]) : el("p", { className: "empty" }, ["No audit events yet."])]);
      if (data.next_cursor) {
        const older = el("button", { className: "button secondary", type: "button" }, ["Load older events"]);
        older.addEventListener("click", () => { state.auditCursor = data.next_cursor; renderAudit(content); });
        card.append(older);
      }
      content.replaceChildren(card);
    } catch (err) {
      content.replaceChildren(el("section", { className: "card" }, [el("p", { className: "error-copy" }, [errorMessage(err)])]));
    }
  }

  async function bootstrap() {
    if (!state.token) { renderLogin(); return; }
    try {
      const data = await api("/api/me");
      state.user = data;
      renderApp();
      await navigate("inventory");
    } catch (_) {
      state.token = null;
      localStorage.removeItem("depotflow-token");
      renderLogin();
    }
  }

  bootstrap();
}());
