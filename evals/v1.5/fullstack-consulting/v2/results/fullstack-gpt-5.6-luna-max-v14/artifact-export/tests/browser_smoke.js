#!/usr/bin/env node
const { chromium } = require("playwright");

const baseUrl = process.env.DEPOTFLOW_URL || "http://127.0.0.1:8765";

(async () => {
  const browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const checks = [];
  function check(condition, message) {
    if (!condition) throw new Error(message);
    checks.push(message);
  }
  await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
  check(await page.getByTestId("login-email").count() === 1, "login email marker");
  check(await page.getByTestId("login-password").count() === 1, "login password marker");
  await page.getByTestId("login-email").fill("operator@north.example");
  await page.getByTestId("login-password").fill("DepotDemo!2026");
  await page.getByTestId("login-submit").click();
  await page.getByTestId("nav-inventory").waitFor();
  await page.getByTestId("inventory-table").waitFor();
  check(await page.getByTestId("inventory-table").locator("tbody tr").count() === 3, "inventory rows");

  await page.getByTestId("nav-orders").click();
  await page.getByTestId("new-order").click();
  await page.getByTestId("order-client-ref").fill("browser-flow-1");
  await page.getByTestId("line-sku").first().selectOption("SAMPLE");
  await page.getByTestId("line-quantity").first().fill("2");
  await page.getByTestId("add-line").click();
  check(await page.getByTestId("line-sku").count() === 2, "multiple order lines");
  await page.getByTestId("line-sku").nth(1).selectOption("BOLT");
  await page.getByTestId("line-quantity").nth(1).fill("1");
  await page.getByTestId("submit-order").click();
  await page.getByTestId("order-detail").waitFor();
  check((await page.getByTestId("order-detail").innerText()).includes("browser-flow-1"), "order reference shown");
  check((await page.getByTestId("order-detail").innerText()).includes("draft"), "draft status shown");
  await page.getByTestId("reserve-order").click();
  await page.getByTestId("ship-order").waitFor();
  check((await page.getByTestId("order-detail").innerText()).includes("reserved"), "reserved status shown");
  await page.getByTestId("ship-order").click();
  await page.getByTestId("submit-return").waitFor();
  check(await page.getByTestId("return-quantity").count() === 2, "return inputs per line");
  await page.getByTestId("return-quantity").first().fill("1");
  await page.getByTestId("submit-return").click();
  await page.getByTestId("nav-audit").click();
  await page.getByTestId("audit-table").waitFor();
  check(await page.getByTestId("audit-table").locator("tbody tr").count() >= 4, "audit events shown");

  await page.getByTestId("logout").click();
  await page.getByTestId("login-submit").waitFor();
  await page.getByTestId("login-email").fill("viewer@north.example");
  await page.getByTestId("login-password").fill("DepotDemo!2026");
  await page.getByTestId("login-submit").click();
  await page.getByTestId("nav-orders").click();
  await page.getByTestId("new-order").waitFor({ state: "detached" });
  check(await page.getByTestId("new-order").count() === 0, "viewer has no new-order control");
  check(await page.getByTestId("reserve-order").count() === 0, "viewer has no reserve control");

  await page.setViewportSize({ width: 375, height: 800 });
  await page.getByTestId("nav-inventory").click();
  await page.getByTestId("inventory-table").waitFor();
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  check(dimensions.scroll <= dimensions.width + 2, `narrow layout scroll width ${dimensions.scroll}/${dimensions.width}`);
  console.log(JSON.stringify({ passed: checks, dimensions }));
  await context.close();
  await browser.close();
})().catch(async (error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
