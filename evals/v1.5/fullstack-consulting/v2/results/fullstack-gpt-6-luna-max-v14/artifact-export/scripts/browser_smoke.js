const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

async function main() {
  if (!process.env.EVAL_BROWSER_WS) throw new Error('EVAL_BROWSER_WS is required for the isolated browser workflow.');
  const port = process.env.PORT || '8000';
  const browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.setDefaultTimeout(7000);
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  const waitForStatus = async (status) => {
    await page.locator('[data-testid="order-detail"] .detail-title .badge').getByText(status, { exact: true }).waitFor();
  };
  try {
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle' });
    await page.getByTestId('login-email').fill('operator@north.example');
    await page.getByTestId('login-password').fill('DepotDemo!2026');
    await page.getByTestId('login-submit').click();
    await page.getByTestId('inventory-table').waitFor({ state: 'visible' });
    console.log('browser checkpoint: signed in and inventory rendered');
    assert.match(await page.locator('body').innerText(), /operator@north\.example/);

    await page.getByTestId('nav-orders').click();
    await page.getByTestId('new-order').click();
    const clientRef = `BROWSER-${Date.now()}`;
    await page.getByTestId('order-client-ref').fill(clientRef);
    await page.getByTestId('line-sku').nth(0).selectOption('BOLT');
    await page.getByTestId('line-quantity').nth(0).fill('2');
    await page.getByTestId('add-line').click();
    await page.getByTestId('line-sku').nth(1).selectOption('CABLE');
    await page.getByTestId('line-quantity').nth(1).fill('1');
    await page.getByTestId('submit-order').click();
    await page.getByTestId('order-detail').getByText(clientRef, { exact: true }).waitFor();
    await waitForStatus('draft');
    console.log('browser checkpoint: multi-line draft created');

    await page.getByTestId('reserve-order').click();
    await waitForStatus('reserved');
    await page.getByTestId('ship-order').click();
    await waitForStatus('shipped');
    console.log('browser checkpoint: order reserved and shipped');
    assert.equal(await page.getByTestId('return-quantity').count(), 2);
    await page.getByTestId('return-quantity').nth(0).fill('1');
    await page.getByTestId('return-quantity').nth(1).fill('1');
    await page.getByTestId('submit-return').click();
    await page.waitForFunction(() => {
      const inputs = Array.from(document.querySelectorAll('[data-testid="return-quantity"]'));
      return inputs.length === 2 && inputs[0].max === '1' && inputs[1].disabled;
    });
    await page.getByTestId('return-quantity').nth(0).fill('1');
    await page.getByTestId('submit-return').click();
    await waitForStatus('returned');
    console.log('browser checkpoint: partial and full returns recorded');

    const evidenceDir = path.join(process.cwd(), 'evidence');
    fs.mkdirSync(evidenceDir, { recursive: true });
    await page.screenshot({ path: path.join(evidenceDir, 'browser-order-workflow.png'), fullPage: true });
    await page.getByTestId('nav-audit').click();
    await page.getByTestId('audit-table').waitFor({ state: 'visible' });
    assert.ok(await page.getByTestId('audit-table').locator('tbody tr').count() >= 5);
    console.log('browser checkpoint: audit trail rendered');
    await page.getByTestId('logout').click();
    await page.getByTestId('login-email').fill('viewer@north.example');
    await page.getByTestId('login-password').fill('DepotDemo!2026');
    await page.getByTestId('login-submit').click();
    await page.getByTestId('inventory-table').waitFor({ state: 'visible' });
    await page.getByTestId('nav-orders').click();
    assert.equal(await page.getByTestId('new-order').count(), 0);
    assert.equal(await page.getByTestId('reserve-order').count(), 0);
    console.log('browser checkpoint: viewer controls hidden');
    await page.setViewportSize({ width: 390, height: 844 });
    const widths = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, document: document.documentElement.scrollWidth }));
    assert.ok(widths.document <= widths.viewport, `unexpected horizontal overflow: ${JSON.stringify(widths)}`);
    assert.deepEqual(pageErrors, []);
    console.log(JSON.stringify({ result: 'passed', workflow: 'login → multi-line order → reserve → ship → partial return → full return → audit → viewer read-only check', viewport: widths, pageErrors }, null, 2));
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
