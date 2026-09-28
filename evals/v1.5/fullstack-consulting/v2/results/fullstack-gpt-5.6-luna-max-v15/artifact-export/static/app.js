(() => {
  "use strict";

  const state = {
    token: localStorage.getItem("depotflow_token"),
    user: null,
    view: "inventory",
    inventory: [],
    orders: [],
    selectedOrder: null,
    composerLines: [],
    filters: { q: "", status: "" },
    busy: false,
  };

  const $ = (id) => document.getElementById(id);
  const test = (id) => document.querySelector(`[data-testid="${id}"]`);

  function setText(element, text) {
    element.textContent = text == null ? "" : String(text);
  }

  function showMessage(text, success = false) {
    const element = $("global-message");
    setText(element, text);
    element.classList.toggle("success", success);
  }

  function showLoginMessage(text) {
    setText($("login-message"), text);
  }

  function formatMoney(cents) {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(cents / 100);
  }

  function statusLabel(status) {
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function isWritable() {
    return state.user && state.user.role !== "viewer";
  }

  function isAdmin() {
    return state.user && state.user.role === "admin";
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
    if (options.body !== undefined) headers.set("Content-Type", "application/json");
    const response = await fetch(path, { ...options, headers });
    let body = null;
    try { body = await response.json(); } catch (_) { body = null; }
    if (response.status === 401 && path !== "/api/session") {
      logout(false);
      throw new Error("Your session expired. Please sign in again.");
    }
    if (!response.ok) {
      const message = body && body.error && body.error.message ? body.error.message : `Request failed (${response.status})`;
      const error = new Error(message);
      error.status = response.status;
      error.code = body && body.error ? body.error.code : "request_failed";
      throw error;
    }
    return body;
  }

  function newIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  async function mutation(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Idempotency-Key": newIdempotencyKey() },
      body: JSON.stringify(body),
    });
  }

  function setBusy(button, busy) {
    if (!button) return;
    button.disabled = busy;
    if (busy) button.dataset.previousText = button.textContent;
    if (busy) button.textContent = "Working…";
    else if (button.dataset.previousText) button.textContent = button.dataset.previousText;
  }

  function showApp() {
    $("login-view").hidden = true;
    $("app-view").hidden = false;
    setText($("identity-text"), `${state.user.email} · ${state.user.role} · ${state.user.tenant}`);
    $("stock-adjustment-panel").hidden = !isAdmin();
    document.querySelectorAll(".writable-only").forEach((element) => {
      element.hidden = !isWritable();
    });
    switchView(state.view);
  }

  function logout(show = true) {
    state.token = null;
    state.user = null;
    localStorage.removeItem("depotflow_token");
    $("app-view").hidden = true;
    $("login-view").hidden = false;
    if (show) showLoginMessage("You have been logged out.");
  }

  async function login(email, password) {
    const button = test("login-submit");
    setBusy(button, true);
    showLoginMessage("");
    try {
      const result = await api("/api/session", { method: "POST", body: JSON.stringify({ email, password }) });
      state.token = result.token;
      state.user = result.user;
      localStorage.setItem("depotflow_token", state.token);
      showApp();
      await loadInventory();
    } catch (error) {
      showLoginMessage(error.message);
    } finally {
      setBusy(button, false);
    }
  }

  async function restoreSession() {
    if (!state.token) return;
    try {
      state.user = await api("/api/me");
      showApp();
      await loadInventory();
    } catch (_) {
      logout(false);
    }
  }

  function switchView(view) {
    state.view = view;
    $("inventory-view").hidden = view !== "inventory";
    $("orders-view").hidden = view !== "orders";
    $("audit-view").hidden = view !== "audit";
    ["inventory", "orders", "audit"].forEach((name) => {
      $(`nav-${name}`).classList.toggle("active", name === view);
    });
    if (view === "inventory") loadInventory();
    if (view === "orders") loadOrders();
    if (view === "audit") loadAudit();
  }

  function clearElement(element) {
    while (element.firstChild) element.removeChild(element.firstChild);
  }

  function makeCell(text) {
    const cell = document.createElement("td");
    setText(cell, text);
    return cell;
  }

  function renderDashboard(dashboard) {
    const container = $("dashboard-cards");
    clearElement(container);
    const metrics = [
      ["Inventory units", dashboard.inventory_units],
      ["Reserved units", dashboard.reserved_units],
      ["Draft orders", dashboard.orders_by_status.draft || 0],
      ["Shipped orders", dashboard.orders_by_status.shipped || 0],
      ["Returned orders", dashboard.orders_by_status.returned || 0],
    ];
    metrics.forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "metric";
      const labelElement = document.createElement("div");
      labelElement.className = "metric-label";
      setText(labelElement, label);
      const valueElement = document.createElement("div");
      valueElement.className = "metric-value";
      setText(valueElement, value);
      card.append(labelElement, valueElement);
      container.append(card);
    });
  }

  function renderInventory(items) {
    state.inventory = items;
    const body = $("inventory-body");
    clearElement(body);
    const select = $("adjustment-sku");
    clearElement(select);
    items.forEach((item) => {
      const row = document.createElement("tr");
      row.append(
        makeCell(item.sku), makeCell(item.name), makeCell(item.on_hand), makeCell(item.reserved),
        makeCell(item.available), makeCell(formatMoney(item.price_cents)), makeCell(item.version)
      );
      body.append(row);
      const option = document.createElement("option");
      option.value = item.sku;
      setText(option, item.sku);
      select.append(option);
    });
    if (!items.length) {
      const row = document.createElement("tr");
      const cell = makeCell("No inventory found.");
      cell.colSpan = 7;
      row.append(cell);
      body.append(row);
    }
    setText($("inventory-state"), items.length ? `${items.length} SKUs` : "No items");
  }

  async function loadInventory() {
    if (!state.user) return;
    setText($("inventory-state"), "Loading…");
    try {
      const [inventory, dashboard] = await Promise.all([api("/api/inventory"), api("/api/dashboard")]);
      renderInventory(inventory.items);
      renderDashboard(dashboard);
    } catch (error) {
      setText($("inventory-state"), "Unable to load");
      showMessage(error.message);
    }
  }

  function renderOrders(orders) {
    state.orders = orders;
    const list = $("orders-list");
    clearElement(list);
    if (!orders.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      setText(empty, "No orders match this view.");
      list.append(empty);
      setText($("orders-state"), "Empty");
      return;
    }
    orders.forEach((order) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "order-card";
      button.classList.toggle("selected", state.selectedOrder && state.selectedOrder.id === order.id);
      const title = document.createElement("strong");
      setText(title, order.client_ref);
      const status = document.createElement("span");
      status.className = "status-pill";
      setText(status, statusLabel(order.status));
      const summary = document.createElement("small");
      setText(summary, `Order #${order.id} · ${formatMoney(order.total_cents)} · v${order.version}`);
      button.append(title, status, summary);
      button.addEventListener("click", () => loadOrderDetail(order.id));
      list.append(button);
    });
    setText($("orders-state"), `${orders.length} order${orders.length === 1 ? "" : "s"}`);
  }

  async function loadOrders() {
    if (!state.user) return;
    setText($("orders-state"), "Loading…");
    const params = new URLSearchParams({ limit: "100" });
    if (state.filters.q) params.set("q", state.filters.q);
    if (state.filters.status) params.set("status", state.filters.status);
    try {
      const result = await api(`/api/orders?${params.toString()}`);
      renderOrders(result.items);
    } catch (error) {
      setText($("orders-state"), "Unable to load");
      showMessage(error.message);
    }
  }

  function detailValue(label, value) {
    const wrapper = document.createElement("div");
    const labelElement = document.createElement("div");
    labelElement.className = "muted";
    setText(labelElement, label);
    const valueElement = document.createElement("div");
    valueElement.className = "detail-value";
    setText(valueElement, value);
    wrapper.append(labelElement, valueElement);
    return wrapper;
  }

  function actionButton(testId, label, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.dataset.testid = testId;
    setText(button, label);
    button.addEventListener("click", action);
    return button;
  }

  function renderOrderDetail(order) {
    state.selectedOrder = order;
    $("order-detail-panel").hidden = false;
    const container = $("order-detail");
    clearElement(container);
    const heading = document.createElement("div");
    const eyebrow = document.createElement("p");
    eyebrow.className = "eyebrow";
    setText(eyebrow, `Order #${order.id}`);
    const title = document.createElement("h3");
    setText(title, order.client_ref);
    heading.append(eyebrow, title);
    const grid = document.createElement("div");
    grid.className = "detail-grid";
    grid.append(detailValue("Client reference", order.client_ref), detailValue("Status", statusLabel(order.status)), detailValue("Version", order.version), detailValue("Total", formatMoney(order.total_cents)));
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    ["SKU", "Quantity", "Unit price", "Returned"].forEach((headingText) => headerRow.append(makeCell(headingText)));
    thead.append(headerRow);
    const tbody = document.createElement("tbody");
    order.lines.forEach((line) => {
      const row = document.createElement("tr");
      row.append(makeCell(line.sku), makeCell(line.quantity), makeCell(formatMoney(line.unit_price_cents)), makeCell(line.returned_quantity));
      tbody.append(row);
    });
    table.append(thead, tbody);
    container.append(heading, grid, table);

    if (isWritable()) {
      const actions = document.createElement("div");
      actions.className = "detail-actions";
      if (order.status === "draft") actions.append(actionButton("reserve-order", "Reserve", () => transition(order, "reserve")));
      if (order.status === "reserved") actions.append(actionButton("ship-order", "Ship", () => transition(order, "ship")));
      if (order.status === "draft" || order.status === "reserved") actions.append(actionButton("cancel-order", "Cancel", () => transition(order, "cancel")));
      container.append(actions);
      if (order.status === "shipped") renderReturnForm(container, order);
    }
    document.querySelectorAll(".order-card").forEach((card) => card.classList.toggle("selected", card.textContent.includes(order.client_ref)));
  }

  function renderReturnForm(container, order) {
    const form = document.createElement("form");
    form.className = "return-form";
    const heading = document.createElement("h3");
    setText(heading, "Record a return");
    const intro = document.createElement("p");
    intro.className = "muted";
    setText(intro, "Enter positive quantities for the lines being returned.");
    const editor = document.createElement("div");
    editor.className = "line-editor";
    order.lines.forEach((line) => {
      const label = document.createElement("label");
      setText(label, `${line.sku} · max ${line.quantity - line.returned_quantity}`);
      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.max = String(line.quantity - line.returned_quantity);
      input.value = "0";
      input.dataset.testid = "return-quantity";
      input.dataset.sku = line.sku;
      label.append(input);
      editor.append(label);
    });
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "primary";
    submit.dataset.testid = "submit-return";
    setText(submit, "Submit return");
    form.append(heading, intro, editor, submit);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const attemptedValues = Object.fromEntries(Array.from(editor.querySelectorAll("[data-testid=return-quantity]"))
        .map((input) => [input.dataset.sku, input.value]));
      const lines = Array.from(editor.querySelectorAll("[data-testid=return-quantity]"))
        .map((input) => ({ sku: input.dataset.sku, quantity: Number(input.value) }))
        .filter((line) => Number.isInteger(line.quantity) && line.quantity > 0);
      if (!lines.length) {
        showMessage("Enter at least one returned quantity.");
        return;
      }
      setBusy(submit, true);
      try {
        const updated = await mutation(`/api/orders/${order.id}/returns`, { expected_version: order.version, lines });
        renderOrderDetail(updated);
        await Promise.all([loadOrders(), loadInventory()]);
        showMessage("Return recorded.", true);
      } catch (error) {
        showMessage(error.message);
        if (error.code === "stale_version") {
          await loadOrderDetail(order.id);
          document.querySelectorAll("[data-testid=return-quantity]").forEach((input) => {
            if (Object.prototype.hasOwnProperty.call(attemptedValues, input.dataset.sku)) {
              input.value = attemptedValues[input.dataset.sku];
            }
          });
        }
      } finally {
        setBusy(submit, false);
      }
    });
    container.append(form);
  }

  async function loadOrderDetail(id) {
    try {
      const order = await api(`/api/orders/${id}`);
      renderOrderDetail(order);
    } catch (error) {
      showMessage(error.message);
    }
  }

  async function transition(order, action) {
    const button = test(`${action}-order`);
    setBusy(button, true);
    try {
      const updated = await mutation(`/api/orders/${order.id}/${action}`, { expected_version: order.version });
      renderOrderDetail(updated);
      await Promise.all([loadOrders(), loadInventory()]);
      const labels = { reserve: "reserved", ship: "shipped", cancel: "cancelled" };
      showMessage(`Order ${labels[action] || action} successfully.`, true);
    } catch (error) {
      showMessage(error.message);
      if (error.code === "stale_version") await loadOrderDetail(order.id);
    } finally {
      setBusy(button, false);
    }
  }

  function lineEditorRow(line = {}) {
    const row = document.createElement("div");
    row.className = "line-row";
    const skuLabel = document.createElement("label");
    setText(skuLabel, "SKU");
    const select = document.createElement("select");
    select.dataset.testid = "line-sku";
    state.inventory.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.sku;
      setText(option, `${item.sku} · ${item.name}`);
      if (line.sku === item.sku) option.selected = true;
      select.append(option);
    });
    skuLabel.append(select);
    const quantityLabel = document.createElement("label");
    setText(quantityLabel, "Quantity");
    const quantity = document.createElement("input");
    quantity.type = "number";
    quantity.min = "1";
    quantity.step = "1";
    quantity.required = true;
    quantity.value = line.quantity || "1";
    quantity.dataset.testid = "line-quantity";
    quantityLabel.append(quantity);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.setAttribute("aria-label", "Remove line");
    setText(remove, "×");
    remove.addEventListener("click", () => {
      if ($("order-lines").children.length > 1) row.remove();
    });
    row.append(skuLabel, quantityLabel, remove);
    return row;
  }

  function openComposer() {
    if (!isWritable()) return;
    const editor = $("order-lines");
    clearElement(editor);
    editor.append(lineEditorRow({ sku: state.inventory[0] && state.inventory[0].sku, quantity: 1 }));
    $("order-client-ref").value = "";
    $("order-composer").hidden = false;
    $("order-client-ref").focus();
  }

  function closeComposer() {
    $("order-composer").hidden = true;
  }

  async function submitOrder(event) {
    event.preventDefault();
    const button = test("submit-order");
    const clientRef = $("order-client-ref").value.trim();
    const lines = Array.from($("order-lines").querySelectorAll(".line-row")).map((row) => ({
      sku: row.querySelector("[data-testid=line-sku]").value,
      quantity: Number(row.querySelector("[data-testid=line-quantity]").value),
    }));
    if (!clientRef || !lines.length || lines.some((line) => !Number.isInteger(line.quantity) || line.quantity < 1)) {
      showMessage("Enter a client reference and positive integer quantities.");
      return;
    }
    setBusy(button, true);
    try {
      const order = await mutation("/api/orders", { client_ref: clientRef, lines });
      closeComposer();
      state.selectedOrder = order;
      await loadOrders();
      renderOrderDetail(order);
      showMessage("Draft order created.", true);
    } catch (error) {
      showMessage(error.message);
    } finally {
      setBusy(button, false);
    }
  }

  async function submitAdjustment(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    const sku = $("adjustment-sku").value;
    const item = state.inventory.find((entry) => entry.sku === sku);
    const delta = Number($("adjustment-delta").value);
    const reason = $("adjustment-reason").value.trim();
    if (!item || !Number.isInteger(delta) || delta === 0 || !reason) {
      showMessage("Enter a nonzero integer delta and a reason.");
      return;
    }
    setBusy(button, true);
    try {
      await mutation("/api/stock/adjustments", { sku, delta, expected_version: item.version, reason });
      form.reset();
      await loadInventory();
      showMessage("Stock adjustment committed.", true);
    } catch (error) {
      showMessage(error.message);
      await loadInventory();
    } finally {
      setBusy(button, false);
    }
  }

  async function loadAudit() {
    setText($("audit-state"), "Loading…");
    try {
      const result = await api("/api/audit?limit=100");
      const body = $("audit-body");
      clearElement(body);
      result.items.forEach((item) => {
        const row = document.createElement("tr");
        row.append(makeCell(new Date(item.created_at).toLocaleString()), makeCell(item.action), makeCell(item.entity_id), makeCell(item.actor));
        body.append(row);
      });
      if (!result.items.length) {
        const row = document.createElement("tr");
        const cell = makeCell("No committed events yet.");
        cell.colSpan = 4;
        row.append(cell);
        body.append(row);
      }
      setText($("audit-state"), `${result.items.length} event${result.items.length === 1 ? "" : "s"}`);
    } catch (error) {
      setText($("audit-state"), "Unable to load");
      showMessage(error.message);
    }
  }

  $("login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    login($("login-email").value.trim(), $("login-password").value);
  });
  $("logout").addEventListener("click", () => logout(true));
  $("nav-inventory").addEventListener("click", () => switchView("inventory"));
  $("nav-orders").addEventListener("click", () => switchView("orders"));
  $("nav-audit").addEventListener("click", () => switchView("audit"));
  $("refresh-inventory").addEventListener("click", loadInventory);
  $("refresh-audit").addEventListener("click", loadAudit);
  $("new-order").addEventListener("click", openComposer);
  $("close-composer").addEventListener("click", closeComposer);
  $("cancel-composer").addEventListener("click", closeComposer);
  $("add-line").addEventListener("click", () => $("order-lines").append(lineEditorRow({ sku: state.inventory[0] && state.inventory[0].sku, quantity: 1 })));
  $("order-form").addEventListener("submit", submitOrder);
  $("stock-adjustment-form").addEventListener("submit", submitAdjustment);
  $("order-filter-form").addEventListener("submit", (event) => {
    event.preventDefault();
    state.filters.q = $("order-search").value.trim();
    state.filters.status = $("order-status-filter").value;
    loadOrders();
  });

  restoreSession();
})();
