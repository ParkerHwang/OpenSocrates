// Uses the provided isolated Chromium WebSocket: EVAL_BROWSER_WS=... node tests/browser_workflow.js
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(7000);
  const errors = [];
  const reference = `browser-flow-${Date.now()}`;
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(process.env.DEPOTFLOW_URL || 'http://127.0.0.1:8127');
  await page.getByTestId('login-email').fill('operator@north.example');
  await page.getByTestId('login-password').fill('DepotDemo!2026');
  await page.getByTestId('login-submit').click();
  await page.getByTestId('inventory-table').waitFor();
  await page.getByTestId('nav-orders').click();
  await page.getByTestId('new-order').click();
  await page.getByTestId('order-client-ref').fill(reference);
  await page.getByTestId('line-quantity').first().fill('2');
  await page.getByTestId('add-line').click();
  await page.getByTestId('line-sku').nth(1).selectOption('SAMPLE');
  await page.getByTestId('line-quantity').nth(1).fill('1');
  await page.getByTestId('submit-order').click();
  await page.getByText('Status: draft').waitFor();
  await page.getByTestId('reserve-order').click();
  await page.getByText('Status: reserved').waitFor();
  await page.getByTestId('ship-order').click();
  await page.getByText('Status: shipped').waitFor();
  await page.getByTestId('return-quantity').nth(0).fill('1');
  await page.getByTestId('submit-return').click();
  await page.getByText('Return recorded.').waitFor();
  await page.getByText('Status: shipped').waitFor();
  await page.getByTestId('return-quantity').nth(0).fill('1');
  await page.getByTestId('return-quantity').nth(1).fill('1');
  await page.getByTestId('submit-return').click();
  await page.getByText('Return recorded.').waitFor();
  await page.getByText('Status: returned').waitFor();
  await page.getByTestId('nav-audit').click();
  await page.locator('[data-testid="audit-table"] tbody tr').first().waitFor();
  const auditRows = await page.locator('[data-testid="audit-table"] tbody tr').count();
  await page.getByTestId('logout').click();
  await page.getByTestId('login-email').fill('viewer@north.example');
  await page.getByTestId('login-password').fill('DepotDemo!2026');
  await page.getByTestId('login-submit').click();
  await page.getByTestId('nav-orders').click();
  await page.getByText(reference).first().click();
  const result = {
    title: await page.title(), auditRows,
    viewerCreateHidden: await page.getByTestId('new-order').isHidden(),
    viewerReserveControls: await page.getByTestId('reserve-order').count(),
    pageErrors: errors,
  };
  console.log(JSON.stringify(result));
  await context.close();
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
