#!/usr/bin/env node

const { chromium } = require("playwright");

const base = process.env.DEPOTFLOW_BASE || "http://127.0.0.1:8000";

async function main() {
  if (!process.env.EVAL_BROWSER_WS) {
    throw new Error("EVAL_BROWSER_WS is required; use the supplied isolated Chromium connection");
  }
  const browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  try {
    console.log("browser: login");
    await page.goto(`${base}/`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("login-email").fill("operator@north.example");
    await page.getByTestId("login-password").fill("DepotDemo!2026");
    await page.getByTestId("login-submit").click();
    await page.getByTestId("inventory-table").waitFor();
    console.log("browser: inventory");
    await page.getByTestId("nav-orders").click();
    await page.getByTestId("new-order").click();
    const reference = `browser-${Date.now()}`;
    await page.getByTestId("order-client-ref").fill(reference);
    await page.getByTestId("line-sku").first().selectOption("BOLT");
    await page.getByTestId("line-quantity").first().fill("1");
    await page.getByTestId("add-line").click();
    await page.getByTestId("line-sku").nth(1).selectOption("CABLE");
    await page.getByTestId("line-quantity").nth(1).fill("1");
    await page.getByTestId("submit-order").click();
    await page.getByTestId("order-detail").waitFor();
    console.log("browser: order created");
    await page.getByTestId("order-detail").getByText(reference).first().waitFor();
    await page.getByTestId("order-detail").getByText("Draft").first().waitFor();
    await page.getByTestId("reserve-order").click();
    await page.getByTestId("ship-order").click();
    console.log("browser: shipped");
    await page.getByTestId("return-quantity").first().fill("1");
    await page.getByTestId("submit-return").click();
    await page.getByTestId("return-quantity").nth(1).fill("1");
    await page.getByTestId("submit-return").click();
    await page.getByTestId("order-detail").getByText("Returned").first().waitFor();
    console.log("browser: returned");
    await page.getByTestId("nav-audit").click();
    await page.getByTestId("audit-table").waitFor();
    await page.getByTestId("audit-table").getByText("order_created").first().waitFor();
    console.log("browser: audit");
    const auditText = await page.getByTestId("audit-table").innerText();
    if (!auditText.includes("order_created") || !auditText.includes("order_shipped")) {
      throw new Error("audit table did not show the order lifecycle events");
    }
    await page.getByTestId("logout").click();
    await page.getByTestId("login-email").fill("viewer@north.example");
    await page.getByTestId("login-password").fill("DepotDemo!2026");
    await page.getByTestId("login-submit").click();
    await page.getByTestId("nav-inventory").click();
    await page.getByTestId("inventory-table").waitFor();
    console.log("browser: viewer");
    if (!(await page.getByTestId("new-order").isHidden())) {
      throw new Error("viewer can see the new-order control");
    }
    await page.getByTestId("nav-orders").click();
    if (!(await page.getByTestId("new-order").isHidden())) {
      throw new Error("viewer can see the new-order control on the order view");
    }
    console.log(JSON.stringify({
      ok: true,
      workflow: "login -> inventory -> multi-line order -> reserve -> ship -> partial/full return -> audit",
      viewer_controls_hidden: true,
    }));
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || error);
  process.exitCode = 1;
});
