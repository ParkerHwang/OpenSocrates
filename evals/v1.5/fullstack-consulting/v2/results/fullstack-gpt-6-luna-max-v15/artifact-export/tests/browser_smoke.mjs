import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import net from "node:net";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const password = "DepotDemo!2026";

function reservePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

async function waitReady(base, process) {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    if (process.exitCode !== null) throw new Error(`DepotFlow exited during startup (${process.exitCode}).`);
    try {
      const response = await fetch(`${base}/api/health`);
      if (response.ok && (await response.json()).status === "ok") return;
    } catch (_) {}
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error("DepotFlow did not become ready in 10 seconds.");
}

const dataDir = mkdtempSync(path.join(root, ".browser-smoke-"));
const port = await reservePort();
const base = `http://127.0.0.1:${port}`;
const child = spawn(path.join(root, "run.sh"), [], {
  cwd: root,
  env: { ...process.env, PORT: String(port), DATA_DIR: dataDir, SEED_DEMO: "1" },
  stdio: "ignore",
});
let browser;
let context;
const pageErrors = [];
const apiFailures = [];

try {
  await waitReady(base, child);
  assert.ok(process.env.EVAL_BROWSER_WS, "EVAL_BROWSER_WS must point to the supplied isolated Chromium instance.");
  browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
  context = await browser.newContext({ viewport: { width: 1280, height: 850 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400) apiFailures.push(`${response.status()} ${response.url()}`);
  });
  await page.goto(base, { waitUntil: "domcontentloaded" });
  assert.equal(await page.title(), "DepotFlow · Fulfillment");

  async function login(email) {
    await page.getByTestId("login-email").fill(email);
    await page.getByTestId("login-password").fill(password);
    await page.getByTestId("login-submit").click();
    await page.getByTestId("nav-inventory").waitFor({ state: "visible" });
  }

  await login("operator@north.example");
  await page.getByTestId("inventory-table").waitFor({ state: "visible" });
  assert.match(await page.getByTestId("inventory-table").innerText(), /Steel bolt kit/);

  const clientRef = `browser-${crypto.randomUUID().slice(0, 8)}`;
  await page.getByTestId("nav-orders").click();
  await page.getByTestId("new-order").click();
  await page.getByTestId("order-client-ref").fill(clientRef);
  await page.getByTestId("line-sku").nth(0).selectOption("BOLT");
  await page.getByTestId("line-quantity").nth(0).fill("2");
  await page.getByTestId("add-line").click();
  await page.getByTestId("line-sku").nth(1).selectOption("CABLE");
  await page.getByTestId("line-quantity").nth(1).fill("1");
  await page.getByTestId("submit-order").click();
  const detail = page.getByTestId("order-detail");
  await detail.waitFor({ state: "visible" });
  await detail.getByRole("heading", { name: clientRef, exact: true }).waitFor({ state: "visible" });
  const waitForStatus = async (status) => page.waitForFunction((expected) => document.querySelector('[data-testid="order-detail"] .detail-title .badge')?.textContent.trim() === expected, status);
  const waitForVersion = async (version) => page.waitForFunction((expected) => document.querySelector('[data-testid="order-detail"] .detail-meta')?.textContent.includes(`version ${expected}`), version);
  assert.equal(await detail.locator(".detail-title .badge").innerText(), "Draft");

  await page.getByTestId("reserve-order").click();
  await waitForStatus("reserved");
  await waitForVersion(2);
  await page.getByTestId("ship-order").click();
  await waitForStatus("shipped");
  await waitForVersion(3);
  await page.getByTestId("return-quantity").nth(0).fill("1");
  await page.getByTestId("return-quantity").nth(1).fill("0");
  await page.getByTestId("submit-return").click();
  await waitForVersion(4);
  await page.getByTestId("return-quantity").nth(0).fill("1");
  await page.getByTestId("return-quantity").nth(1).fill("1");
  await page.getByTestId("submit-return").click();
  await waitForStatus("returned");
  await waitForVersion(5);

  const draftRef = `viewer-${crypto.randomUUID().slice(0, 8)}`;
  await page.getByTestId("new-order").click();
  await page.getByTestId("order-client-ref").fill(draftRef);
  await page.getByTestId("line-sku").nth(0).selectOption("SAMPLE");
  await page.getByTestId("line-quantity").nth(0).fill("1");
  await page.getByTestId("submit-order").click();
  await page.getByTestId("order-detail").waitFor({ state: "visible" });
  await page.getByTestId("nav-audit").click();
  await page.getByTestId("audit-table").waitFor({ state: "visible" });
  const auditRows = await page.getByTestId("audit-table").locator("tbody tr").count();
  assert.ok(auditRows >= 5, `expected at least five audit events, got ${auditRows}: ${await page.getByTestId("audit-table").innerText()}`);

  await page.setViewportSize({ width: 390, height: 844 });
  const widthFits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  assert.equal(widthFits, true, "mobile page should not overflow horizontally");

  await page.getByTestId("logout").click();
  await login("viewer@north.example");
  await page.getByTestId("nav-orders").click();
  await page.getByRole("button", { name: draftRef, exact: true }).click();
  await page.getByTestId("order-detail").waitFor({ state: "visible" });
  assert.equal(await page.getByTestId("new-order").count(), 0);
  assert.equal(await page.getByTestId("reserve-order").count(), 0);
  assert.equal(await page.getByTestId("ship-order").count(), 0);
  assert.equal(await page.getByTestId("cancel-order").count(), 0);
  assert.equal(await page.getByTestId("submit-return").count(), 0);

  await page.getByTestId("logout").click();
  await login("admin@north.example");
  await page.getByTestId("nav-inventory").click();
  await page.getByText("Adjust stock", { exact: true }).waitFor({ state: "visible" });
  assert.equal(await page.locator("#adjust-sku").count(), 1);
  await page.locator("#adjust-sku").selectOption("SAMPLE");
  await page.locator("#adjust-delta").fill("1");
  await page.locator("#adjust-reason").fill("Browser smoke verification");
  await page.getByRole("button", { name: "Save adjustment" }).click();
  await page.waitForFunction(() => Boolean(document.querySelector("#notice-slot")?.textContent.trim()));
  assert.match(await page.locator("#notice-slot").innerText(), /Stock adjustment saved\./);

  assert.deepEqual(pageErrors, []);
  assert.deepEqual(apiFailures, []);
  console.log(JSON.stringify({
    browser: "supplied isolated Chromium via EVAL_BROWSER_WS",
    workflow: "login, inventory, multi-line create, reserve, ship, partial and full return, audit, viewer read-only controls, admin stock adjustment",
    viewport: "390x844 mobile overflow check passed",
    client_ref: clientRef,
    page_errors: pageErrors,
    api_failures: apiFailures,
  }, null, 2));
} finally {
  if (context) await context.close().catch(() => {});
  if (browser) await browser.close().catch(() => {});
  if (child.exitCode === null) {
    child.kill("SIGTERM");
    await new Promise((resolve) => {
      const timeout = setTimeout(() => { child.kill("SIGKILL"); resolve(); }, 3000);
      child.once("exit", () => { clearTimeout(timeout); resolve(); });
    });
  }
  rmSync(dataDir, { recursive: true, force: true });
}
