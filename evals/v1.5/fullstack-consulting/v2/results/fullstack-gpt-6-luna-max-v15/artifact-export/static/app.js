(() => {
  "use strict";

  const root = document.getElementById("app");
  const state = {
    token: localStorage.getItem("depotflow_token") || "",
    user: null,
    section: "inventory",
    inventory: [],
    dashboard: null,
    orders: [],
    ordersCursor: null,
    orderSearch: "",
    orderStatus: "",
    selectedOrder: null,
    showCreate: false,
    audit: [],
    auditCursor: null,
    loading: false,
    loadGeneration: 0,
    notice: null,
  };
  const pendingKeys = new Map();
  const isWriter = () => state.user && state.user.role !== "viewer";
  const isAdmin = () => state.user && state.user.role === "admin";

  function element(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null) continue;
      if (key === "className") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "dataset") Object.assign(node.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2).toLowerCase(), value);
      else if (key === "checked" || key === "disabled" || key === "required" || key === "readOnly") node[key] = Boolean(value);
      else if (key === "value") node.value = value;
      else node.setAttribute(key, String(value));
    }
    for (const child of (Array.isArray(children) ? children : [children])) {
      if (child === null || child === undefined) continue;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function append(parent, ...children) {
    for (const child of children) {
      if (child === null || child === undefined) continue;
      parent.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return parent;
  }

  function button(text, options = {}) {
    return element("button", {
      type: "button",
      className: options.className || "btn",
      text,
      disabled: options.disabled,
      "data-testid": options.testid,
      "aria-label": options.ariaLabel,
      onclick: options.onClick,
    });
  }

  function labelField(labelText, control, id) {
    const label = element("label", { for: id, className: "field-label", text: labelText });
    const wrapper = element("div", { className: "field" });
    append(wrapper, label, control);
    return wrapper;
  }

  function formatMoney(cents) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
  }

  function titleCase(value) {
    return value ? value[0].toUpperCase() + value.slice(1) : "";
  }

  function alertNode(message, level = "error") {
    return element("div", { className: `alert ${level === "error" ? "alert-error" : level === "success" ? "alert-success" : ""}`, role: level === "error" ? "alert" : "status", text: message });
  }

  function showNotice(message, level = "error") {
    state.notice = { message, level };
    const slot = document.getElementById("notice-slot");
    if (slot) {
      slot.replaceChildren(alertNode(message, level));
    }
  }

  function canonical(value) {
    if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
    if (value && typeof value === "object") {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
    }
    return JSON.stringify(value);
  }

  async function request(path, options = {}) {
    const method = options.method || "GET";
    const headers = { Accept: "application/json" };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    let body;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
    if (options.idempotent) {
      const signature = `${method}:${path}:${canonical(options.body)}`;
      if (!pendingKeys.has(signature)) pendingKeys.set(signature, crypto.randomUUID());
      headers["Idempotency-Key"] = pendingKeys.get(signature);
      try {
        const result = await fetchJson(path, { method, headers, body });
        pendingKeys.delete(signature);
        return result;
      } catch (error) {
        throw error;
      }
    }
    return fetchJson(path, { method, headers, body });
  }

  async function fetchJson(path, options) {
    let response;
    try {
      response = await fetch(path, options);
    } catch (error) {
      const networkError = new Error("Could not reach DepotFlow. Check the connection and retry.");
      networkError.code = "network_error";
      throw networkError;
    }
    let payload;
    try {
      payload = await response.json();
    } catch (_) {
      payload = null;
    }
    if (!response.ok) {
      const error = new Error(payload && payload.error && payload.error.message ? payload.error.message : `Request failed (${response.status}).`);
      error.status = response.status;
      error.code = payload && payload.error ? payload.error.code : "request_failed";
      throw error;
    }
    return payload;
  }

  async function withPending(control, task) {
    const original = control ? control.textContent : "";
    if (control) {
      control.disabled = true;
      control.textContent = "Working…";
    }
    try {
      await task();
    } catch (error) {
      let message = error.message;
      if (error.code === "stale_version") message += " Your entries are still on this screen; refresh the order when ready.";
      showNotice(message, "error");
    } finally {
      if (control && control.isConnected) {
        control.disabled = false;
        control.textContent = original;
      }
    }
  }

  function renderLogin() {
    root.replaceChildren();
    const wrap = element("main", { className: "login-wrap" });
    const card = element("section", { className: "login-card", "aria-labelledby": "login-title" });
    const mark = element("div", { className: "brand-mark" }, [element("span", { className: "brand-icon", text: "D" }), "DepotFlow"]);
    const intro = element("p", { className: "login-intro", text: "Sign in to manage warehouse inventory, orders, and returns." });
    const notice = element("div", { id: "login-notice" });
    if (state.notice) notice.append(alertNode(state.notice.message, state.notice.level));
    const form = element("form", { id: "login-form" });
    const email = element("input", { id: "login-email-input", type: "email", autocomplete: "username", required: true, "data-testid": "login-email" });
    const password = element("input", { id: "login-password-input", type: "password", autocomplete: "current-password", required: true, "data-testid": "login-password" });
    const submit = element("button", { type: "submit", className: "btn full-width", text: "Sign in", "data-testid": "login-submit" });
    append(form, labelField("Work email", email, email.id), labelField("Password", password, password.id), submit);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      submit.textContent = "Signing in…";
      state.notice = null;
      try {
        const result = await request("/api/session", { method: "POST", body: { email: email.value, password: password.value } });
        state.token = result.token;
        state.user = result.user;
        localStorage.setItem("depotflow_token", result.token);
        state.section = "inventory";
        state.notice = null;
        render();
        await loadSection();
      } catch (error) {
        notice.replaceChildren(alertNode(error.message));
        submit.disabled = false;
        submit.textContent = "Sign in";
      }
    });
    const demo = element("details", { className: "demo-users" });
    append(demo, element("summary", { text: "Local demo accounts" }), element("p", { text: "north and south each have admin, operator, and viewer accounts. Password: DepotDemo!2026" }));
    append(card, mark, element("h1", { id: "login-title", text: "Welcome back" }), intro, notice, form, demo);
    append(wrap, card);
    root.append(wrap);
  }

  function render() {
    if (!state.user) {
      renderLogin();
      return;
    }
    root.replaceChildren();
    const shell = element("div", { className: "shell" });
    const sidebar = element("aside", { className: "sidebar", "aria-label": "Main navigation" });
    const brand = element("div", { className: "brand-mark" }, [element("span", { className: "brand-icon", text: "D" }), "DepotFlow"]);
    const nav = element("nav", { className: "nav-list" });
    const sections = [
      ["inventory", "Inventory", "nav-inventory"],
      ["orders", "Orders", "nav-orders"],
      ["audit", "Audit log", "nav-audit"],
    ];
    for (const [section, text, testid] of sections) {
      nav.append(element("button", {
        type: "button",
        className: "nav-item",
        text,
        "data-testid": testid,
        "aria-current": state.section === section ? "page" : null,
        onclick: () => navigate(section),
      }));
    }
    const tenant = element("div", { className: "tenant-badge" });
    append(tenant, element("strong", { text: `${titleCase(state.user.tenant)} warehouse` }), element("span", { text: `${titleCase(state.user.role)} access` }));
    append(sidebar, brand, nav, tenant);
    const workspace = element("div", { className: "workspace" });
    const topbar = element("header", { className: "topbar" });
    const title = state.section === "inventory" ? "Warehouse overview" : state.section === "orders" ? "Order management" : "Inventory history";
    const user = element("div", { className: "user-meta" });
    append(user, element("span", { text: `${state.user.email} · ${titleCase(state.user.role)}` }), button("Log out", { className: "btn btn-secondary btn-small", testid: "logout", onClick: logout }));
    append(topbar, element("div", { className: "topbar-title", text: title }), user);
    const content = element("main", { className: "content" });
    append(content, element("div", { id: "notice-slot" }));
    if (state.section === "inventory") renderInventory(content);
    else if (state.section === "orders") renderOrders(content);
    else renderAudit(content);
    append(workspace, topbar, content);
    append(shell, sidebar, workspace);
    root.append(shell);
    const noticeSlot = document.getElementById("notice-slot");
    if (noticeSlot && state.notice) noticeSlot.append(alertNode(state.notice.message, state.notice.level));
  }

  function renderInventory(content) {
    const heading = element("div", { className: "page-heading" });
    append(heading, element("div", {}, [element("h1", { text: "Inventory" }), element("p", { text: "Current stock, reservations, and tenant activity." })]));
    content.append(heading);
    if (state.loading) {
      content.append(element("div", { className: "panel empty", role: "status", text: "Loading inventory…" }));
      return;
    }
    const counts = state.dashboard ? state.dashboard.orders_by_status : {};
    const cards = element("section", { className: "cards", "aria-label": "Warehouse summary" });
    const metrics = [
      ["Inventory units", state.dashboard ? state.dashboard.inventory_units : "—"],
      ["Reserved units", state.dashboard ? state.dashboard.reserved_units : "—"],
      ["Open orders", Number(counts.draft || 0) + Number(counts.reserved || 0)],
      ["Shipped orders", counts.shipped || 0],
    ];
    for (const [label, value] of metrics) cards.append(element("article", { className: "metric" }, [element("div", { className: "metric-label", text: label }), element("div", { className: "metric-value", text: value })]));
    content.append(cards);
    const panel = element("section", { className: "panel" });
    const panelHeading = element("div", { className: "panel-heading" });
    append(panelHeading, element("div", {}, [element("h2", { text: "Stock by SKU" }), element("p", { text: "Available stock equals on hand minus reserved units." })]));
    panel.append(panelHeading);
    if (!state.inventory.length) panel.append(element("div", { className: "empty", text: "No inventory items are configured." }));
    else {
      const table = element("table", { "data-testid": "inventory-table" });
      const head = element("thead", {}, [element("tr", {}, ["SKU", "Item", "On hand", "Reserved", "Available", "Unit price", "Version"].map((label, index) => element("th", { text: label, className: index >= 2 ? "numeric" : "" })))]);
      const body = element("tbody");
      for (const item of state.inventory) {
        body.append(element("tr", {}, [
          element("td", { className: "sku-code", text: item.sku }),
          element("td", { text: item.name }),
          element("td", { className: "numeric", text: item.on_hand }),
          element("td", { className: "numeric", text: item.reserved }),
          element("td", { className: "numeric", text: item.available }),
          element("td", { className: "numeric money", text: formatMoney(item.price_cents) }),
          element("td", { className: "numeric", text: item.version }),
        ]));
      }
      append(table, head, body);
      panel.append(element("div", { className: "table-wrap" }, [table]));
    }
    content.append(panel);
    if (isAdmin()) content.append(renderAdjustmentForm());
  }

  function renderAdjustmentForm() {
    const panel = element("section", { className: "panel", "aria-labelledby": "adjust-title" });
    append(panel, element("h2", { id: "adjust-title", text: "Adjust stock" }), element("p", { className: "helper", text: "Admin only. Each adjustment checks the inventory version shown above." }));
    const form = element("form", {});
    const sku = element("select", { id: "adjust-sku" });
    for (const item of state.inventory) sku.append(element("option", { value: item.sku, text: `${item.sku} · ${item.name}` }));
    const delta = element("input", { id: "adjust-delta", type: "number", step: "1", required: true, placeholder: "e.g. 12 or -3" });
    const reason = element("input", { id: "adjust-reason", type: "text", required: true, placeholder: "Reason for the adjustment" });
    const row = element("div", { className: "toolbar" });
    append(row, labelField("SKU", sku, sku.id), labelField("Signed quantity", delta, delta.id), labelField("Reason", reason, reason.id));
    const submit = element("button", { type: "button", className: "btn", text: "Save adjustment" });
    const saveAdjustment = async () => {
      if (submit.disabled || !form.reportValidity()) return;
      const item = state.inventory.find((entry) => entry.sku === sku.value);
      const amount = Number(delta.value);
      if (!Number.isSafeInteger(amount) || amount === 0) {
        showNotice("Enter a nonzero whole-number adjustment.");
        return;
      }
      await withPending(submit, async () => {
        await request("/api/stock/adjustments", { method: "POST", idempotent: true, body: { sku: sku.value, delta: amount, expected_version: item.version, reason: reason.value } });
        await afterMutation("Stock adjustment saved.");
      });
    };
    submit.addEventListener("click", saveAdjustment);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      saveAdjustment();
    });
    append(form, row, submit);
    panel.append(form);
    return panel;
  }

  function renderOrders(content) {
    const heading = element("div", { className: "page-heading" });
    const titleGroup = element("div");
    append(titleGroup, element("h1", { text: "Orders" }), element("p", { text: "Create orders, reserve stock, ship, and record returns." }));
    append(heading, titleGroup);
    if (isWriter()) heading.append(button(state.showCreate ? "Close form" : "New order", { className: "btn", testid: "new-order", onClick: () => { state.showCreate = !state.showCreate; render(); } }));
    content.append(heading);
    if (state.loading) {
      content.append(element("div", { className: "panel empty", role: "status", text: "Loading orders…" }));
      return;
    }
    const filterPanel = element("section", { className: "panel" });
    const filter = element("form", { className: "toolbar", "aria-label": "Filter orders" });
    const search = element("input", { type: "search", id: "order-search", value: state.orderSearch, placeholder: "Search client reference" });
    const status = element("select", { id: "order-status" });
    status.append(element("option", { value: "", text: "All statuses" }));
    for (const value of ["draft", "reserved", "shipped", "cancelled", "returned"]) status.append(element("option", { value, text: titleCase(value) }));
    status.value = state.orderStatus;
    append(filter, labelField("Client reference", search, search.id), labelField("Status", status, status.id), element("button", { type: "submit", className: "btn btn-secondary", text: "Apply filters" }));
    filter.addEventListener("submit", async (event) => {
      event.preventDefault();
      state.orderSearch = search.value;
      state.orderStatus = status.value;
      state.ordersCursor = null;
      state.orders = [];
      state.selectedOrder = null;
      state.loading = true;
      state.notice = null;
      render();
      try {
        await loadOrders(false, false);
      } catch (error) {
        showNotice(error.message, "error");
      } finally {
        state.loading = false;
        render();
      }
    });
    filterPanel.append(filter);
    content.append(filterPanel);
    if (state.showCreate && isWriter()) content.append(renderCreateForm());
    if (!state.orders.length) {
      content.append(element("section", { className: "panel empty" }, [element("strong", { text: "No orders found" }), "Try a different search or create an order."]));
    } else {
      const panel = element("section", { className: "panel" });
      append(panel, element("h2", { text: "Order list" }));
      const table = element("table");
      const head = element("thead", {}, [element("tr", {}, ["Client reference", "Status", "Lines", "Total", "Version"].map((label) => element("th", { text: label })))]);
      const body = element("tbody");
      for (const order of state.orders) {
        const row = element("tr", { className: "order-row", tabindex: "0", "aria-label": `Open order ${order.client_ref}`, onclick: () => selectOrder(order.id) });
        row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectOrder(order.id); } });
        append(row,
          element("td", {}, [element("button", { type: "button", className: "link-button", text: order.client_ref, onclick: (event) => { event.stopPropagation(); selectOrder(order.id); } })]),
          element("td", {}, [statusBadge(order.status)]),
          element("td", { text: order.lines.length }),
          element("td", { className: "money", text: formatMoney(order.total_cents) }),
          element("td", { text: order.version }),
        );
        body.append(row);
      }
      append(table, head, body);
      panel.append(element("div", { className: "table-wrap" }, [table]));
      if (state.ordersCursor) {
        const more = button("Load more orders", { className: "btn btn-secondary btn-small" });
        more.addEventListener("click", () => withPending(more, () => loadOrders(true)));
        panel.append(more);
      }
      content.append(panel);
    }
    if (state.selectedOrder) content.append(renderOrderDetail(state.selectedOrder));
  }

  function renderCreateForm() {
    const panel = element("section", { className: "panel", "aria-labelledby": "create-order-title" });
    append(panel, element("h2", { id: "create-order-title", text: "Create order" }), element("p", { className: "helper", text: "Prices come from the warehouse catalog and are saved with this order." }));
    const form = element("form", {});
    const clientRef = element("input", { id: "order-client-ref-input", type: "text", required: true, autocomplete: "off", placeholder: "e.g. PO-1042", "data-testid": "order-client-ref" });
    append(form, labelField("Client reference", clientRef, clientRef.id));
    const lineBox = element("div", { id: "order-lines" });
    const rows = [];
    let nextLineIndex = 0;
    const addLine = () => {
      const index = nextLineIndex++;
      const row = element("div", { className: "line-editor" });
      const select = element("select", { id: `line-sku-${index}`, "data-testid": "line-sku" });
      const availableItems = state.inventory.length ? state.inventory : [
        { sku: "BOLT", name: "Steel bolt kit" }, { sku: "CABLE", name: "Cable assembly" }, { sku: "SAMPLE", name: "Sample pack" },
      ];
      for (const item of availableItems) select.append(element("option", { value: item.sku, text: `${item.sku} · ${item.name}` }));
      const quantity = element("input", { id: `line-quantity-${index}`, type: "number", min: "1", step: "1", value: "1", required: true, "data-testid": "line-quantity" });
      append(row, labelField("SKU", select, select.id), labelField("Quantity", quantity, quantity.id));
      if (rows.length > 0) row.append(button("Remove line", { className: "btn btn-secondary btn-small remove-line", onClick: () => { row.remove(); rows.splice(rows.indexOf(row), 1); } }));
      rows.push(row);
      lineBox.append(row);
    };
    addLine();
    const add = button("Add line", { className: "btn btn-secondary btn-small", testid: "add-line", onClick: addLine });
    const submit = element("button", { type: "submit", className: "btn", text: "Create order", "data-testid": "submit-order" });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const lines = rows.filter((row) => row.isConnected).map((row) => ({
        sku: row.querySelector('[data-testid="line-sku"]').value,
        quantity: Number(row.querySelector('[data-testid="line-quantity"]').value),
      }));
      await withPending(submit, async () => {
        const order = await request("/api/orders", { method: "POST", idempotent: true, body: { client_ref: clientRef.value, lines } });
        state.selectedOrder = order;
        state.showCreate = false;
        await afterMutation("Order created.");
      });
    });
    const actions = element("div", { className: "form-actions" });
    append(actions, add, submit);
    append(form, lineBox, actions);
    panel.append(form);
    return panel;
  }

  function statusBadge(status) {
    return element("span", { className: `badge badge-${status}`, text: status });
  }

  function renderOrderDetail(order) {
    const panel = element("section", { className: "panel", "data-testid": "order-detail", "aria-labelledby": "order-detail-title" });
    const heading = element("div", { className: "panel-heading" });
    const title = element("div");
    append(title, element("div", { className: "detail-title" }, [element("h2", { id: "order-detail-title", text: order.client_ref }), statusBadge(order.status)]), element("div", { className: "detail-meta", text: `Order ${order.id} · version ${order.version}` }));
    append(heading, title, button("Close detail", { className: "btn btn-secondary btn-small", onClick: () => { state.selectedOrder = null; render(); } }));
    panel.append(heading);
    const table = element("table");
    const head = element("thead", {}, [element("tr", {}, ["SKU", "Quantity", "Returned", "Unit price", "Line total"].map((label) => element("th", { text: label })))]);
    const body = element("tbody");
    for (const line of order.lines) {
      append(body, element("tr", {}, [
        element("td", { className: "sku-code", text: line.sku }),
        element("td", { text: line.quantity }),
        element("td", { text: line.returned_quantity }),
        element("td", { className: "money", text: formatMoney(line.unit_price_cents) }),
        element("td", { className: "money", text: formatMoney(line.unit_price_cents * line.quantity) }),
      ]));
    }
    append(table, head, body);
    panel.append(element("div", { className: "table-wrap" }, [table]));
    panel.append(element("p", { className: "detail-meta", text: `Order total: ${formatMoney(order.total_cents)}` }));
    if (isWriter()) {
      const actions = element("div", { className: "action-row" });
      if (order.status === "draft") actions.append(actionButton("Reserve stock", "reserve-order", order, "reserve"));
      if (order.status === "reserved") actions.append(actionButton("Ship order", "ship-order", order, "ship"));
      if (order.status === "draft" || order.status === "reserved") actions.append(actionButton("Cancel order", "cancel-order", order, "cancel", true));
      panel.append(actions);
      if (order.status === "shipped") panel.append(renderReturnForm(order));
    }
    return panel;
  }

  function actionButton(text, testid, order, operation, danger = false) {
    const control = button(text, { className: danger ? "btn btn-danger" : "btn", testid });
    control.addEventListener("click", () => withPending(control, async () => {
      const result = await request(`/api/orders/${encodeURIComponent(order.id)}/${operation}`, {
        method: "POST", idempotent: true, body: { expected_version: order.version },
      });
      state.selectedOrder = result;
      await afterMutation(`${titleCase(operation)} completed.`);
    }));
    return control;
  }

  function renderReturnForm(order) {
    const form = element("form", { className: "panel", "aria-labelledby": "return-title" });
    append(form, element("h3", { id: "return-title", text: "Record a return" }), element("p", { className: "helper", text: "Enter the quantity received back for each line. Leave other lines at zero." }));
    const inputs = [];
    for (const line of order.lines) {
      const remaining = line.quantity - line.returned_quantity;
      const input = element("input", { className: "return-input", type: "number", min: "0", max: String(remaining), step: "1", value: "0", "data-testid": "return-quantity", "aria-label": `Return quantity for ${line.sku}` });
      const row = element("div", { className: "return-grid" });
      append(row, element("div", {}, [element("strong", { text: line.sku }), ` · ${remaining} remaining`]), input);
      form.append(row);
      inputs.push({ sku: line.sku, input });
    }
    const submit = element("button", { type: "submit", className: "btn", text: "Submit return", "data-testid": "submit-return" });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const lines = inputs.filter(({ input }) => Number(input.value) > 0).map(({ sku, input }) => ({ sku, quantity: Number(input.value) }));
      await withPending(submit, async () => {
        const result = await request(`/api/orders/${encodeURIComponent(order.id)}/returns`, {
          method: "POST", idempotent: true, body: { expected_version: order.version, lines },
        });
        state.selectedOrder = result;
        await afterMutation("Return recorded.");
      });
    });
    form.append(submit);
    return form;
  }

  function renderAudit(content) {
    const heading = element("div", { className: "page-heading" });
    append(heading, element("div", {}, [element("h1", { text: "Audit log" }), element("p", { text: "Committed inventory and order changes for this warehouse." })]));
    content.append(heading);
    if (state.loading) {
      content.append(element("div", { className: "panel empty", role: "status", text: "Loading audit history…" }));
      return;
    }
    if (!state.audit.length) {
      content.append(element("section", { className: "panel empty" }, [element("strong", { text: "No activity yet" }), "Successful changes will appear here."]));
      return;
    }
    const panel = element("section", { className: "panel" });
    const table = element("table", { "data-testid": "audit-table" });
    const head = element("thead", {}, [element("tr", {}, ["Time", "Action", "Entity", "Actor"].map((label) => element("th", { text: label })))]);
    const body = element("tbody");
    for (const item of state.audit) {
      append(body, element("tr", {}, [
        element("td", { text: new Date(item.created_at).toLocaleString() }),
        element("td", { text: item.action }),
        element("td", { text: item.entity_id }),
        element("td", { text: item.actor }),
      ]));
    }
    append(table, head, body);
    panel.append(element("div", { className: "table-wrap" }, [table]));
    if (state.auditCursor) {
      const more = button("Load more activity", { className: "btn btn-secondary btn-small" });
      more.addEventListener("click", () => withPending(more, () => loadAudit(true)));
      panel.append(more);
    }
    content.append(panel);
  }

  async function navigate(section) {
    state.section = section;
    state.notice = null;
    state.loading = true;
    render();
    await loadSection();
  }

  async function loadSection() {
    const generation = ++state.loadGeneration;
    state.loading = true;
    render();
    try {
      if (state.section === "inventory") await loadInventory();
      else if (state.section === "orders") {
        await Promise.all([loadOrders(false, false), loadInventory()]);
      } else await loadAudit(false, false);
    } catch (error) {
      if (generation !== state.loadGeneration) return;
      if (error.status === 401) {
        logout();
        return;
      }
      showNotice(error.message, "error");
    } finally {
      if (generation === state.loadGeneration) {
        state.loading = false;
        render();
      }
    }
  }

  async function loadInventory(renderAfter = false) {
    const [inventory, dashboard] = await Promise.all([request("/api/inventory"), request("/api/dashboard")]);
    state.inventory = inventory.items;
    state.dashboard = dashboard;
    if (renderAfter) render();
  }

  async function loadOrders(appendPage = false, renderAfter = true) {
    const params = new URLSearchParams();
    params.set("limit", "20");
    if (state.orderStatus) params.set("status", state.orderStatus);
    if (state.orderSearch) params.set("q", state.orderSearch);
    if (appendPage && state.ordersCursor) params.set("cursor", state.ordersCursor);
    const result = await request(`/api/orders?${params.toString()}`);
    state.orders = appendPage ? state.orders.concat(result.items) : result.items;
    state.ordersCursor = result.next_cursor;
    if (state.selectedOrder) {
      try { state.selectedOrder = await request(`/api/orders/${encodeURIComponent(state.selectedOrder.id)}`); }
      catch (error) { if (error.status === 404) state.selectedOrder = null; else throw error; }
    }
    if (renderAfter) render();
  }

  async function selectOrder(id) {
    try {
      state.selectedOrder = await request(`/api/orders/${encodeURIComponent(id)}`);
      state.notice = null;
      render();
    } catch (error) {
      showNotice(error.message, "error");
    }
  }

  async function loadAudit(appendPage = false, renderAfter = true) {
    const params = new URLSearchParams({ limit: "30" });
    if (appendPage && state.auditCursor) params.set("cursor", state.auditCursor);
    const result = await request(`/api/audit?${params.toString()}`);
    state.audit = appendPage ? state.audit.concat(result.items) : result.items;
    state.auditCursor = result.next_cursor;
    if (renderAfter) render();
  }

  async function afterMutation(message) {
    state.notice = { message, level: "success" };
    try {
      await Promise.all([
        loadInventory(),
        loadOrders(false, false),
        loadAudit(false, false),
      ]);
      render();
      showNotice(message, "success");
    } catch (error) {
      render();
      showNotice(`${message} The saved change is confirmed, but a refresh failed: ${error.message}`, "error");
    }
  }

  function logout() {
    state.token = "";
    state.user = null;
    state.notice = null;
    pendingKeys.clear();
    localStorage.removeItem("depotflow_token");
    render();
  }

  async function boot() {
    if (!state.token) {
      render();
      return;
    }
    try {
      state.user = await request("/api/me");
      await loadSection();
    } catch (_) {
      state.token = "";
      state.user = null;
      localStorage.removeItem("depotflow_token");
      render();
    }
  }

  boot();
})();
