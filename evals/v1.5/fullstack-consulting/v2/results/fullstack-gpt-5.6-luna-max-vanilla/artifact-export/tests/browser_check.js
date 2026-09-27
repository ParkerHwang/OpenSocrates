const { chromium } = require("playwright");

(async () => {

const base = process.env.BASE_URL || "http://127.0.0.1:18081";
const clientRef = `browser-flow-${Date.now()}`;
const browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
const consoleErrors = [];
page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
page.on("pageerror", (error) => consoleErrors.push(String(error)));

await page.goto(`${base}/`);
await page.locator('[data-testid="login-email"]').fill("operator@north.example");
await page.locator('[data-testid="login-password"]').fill("DepotDemo!2026");
await page.locator('[data-testid="login-submit"]').click();
await page.locator('[data-testid="inventory-table"]').waitFor();
const inventoryRows = await page.locator('[data-testid="inventory-table"] tbody tr').count();
if (inventoryRows !== 3) throw new Error("inventory rows missing");

await page.locator('[data-testid="nav-orders"]').click();
await page.locator('[data-testid="new-order"]').click();
await page.locator('[data-testid="order-client-ref"]').fill(clientRef);
await page.locator('[data-testid="line-sku"]').nth(0).selectOption("BOLT");
await page.locator('[data-testid="line-quantity"]').nth(0).fill("1");
await page.locator('[data-testid="add-line"]').click();
await page.locator('[data-testid="line-sku"]').nth(1).selectOption("SAMPLE");
await page.locator('[data-testid="line-quantity"]').nth(1).fill("1");
await page.locator('[data-testid="submit-order"]').click();
await page.locator('[data-testid="order-detail"]').waitFor();
if (!(await page.locator('[data-testid="order-detail"]').textContent()).includes(clientRef)) throw new Error("order detail missing reference");

await page.locator('[data-testid="reserve-order"]').click();
await page.locator('[data-testid="ship-order"]').waitFor();
await page.locator('[data-testid="ship-order"]').click();
await page.locator('[data-testid="submit-return"]').waitFor();
await page.locator('[data-testid="return-quantity"]').nth(0).fill("1");
await page.locator('[data-testid="return-quantity"]').nth(1).fill("1");
await page.locator('[data-testid="submit-return"]').click();
await page.waitForFunction(() => document.querySelector('[data-testid="order-detail"]')?.textContent.includes("Returned"));

await page.locator('[data-testid="nav-audit"]').click();
await page.locator('[data-testid="audit-table"]').waitFor();
const auditRows = await page.locator('[data-testid="audit-table"] tbody tr').count();
if (auditRows < 4) throw new Error("audit events missing");
const overflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
if (!overflow) throw new Error("mobile horizontal overflow");

await page.locator('[data-testid="logout"]').click();
await page.locator('[data-testid="login-email"]').fill("viewer@north.example");
await page.locator('[data-testid="login-password"]').fill("DepotDemo!2026");
await page.locator('[data-testid="login-submit"]').click();
await page.locator('[data-testid="inventory-table"]').waitFor();
await page.locator('[data-testid="nav-orders"]').click();
if (await page.locator('[data-testid="new-order"]').count() !== 0) throw new Error("viewer saw new-order control");
await page.locator('[data-order-id]').first().click();
await page.locator('[data-testid="order-detail"]').waitFor();
if (await page.locator('[data-testid="reserve-order"]').count() !== 0 || await page.locator('[data-testid="submit-return"]').count() !== 0) throw new Error("viewer saw mutation controls");

console.log(JSON.stringify({
  title: await page.title(),
  inventory_rows: inventoryRows,
  audit_rows: auditRows,
  viewer_mutation_controls: 0,
  mobile_no_overflow: overflow,
  console_errors: consoleErrors,
}));
await context.close();
await browser.close();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
