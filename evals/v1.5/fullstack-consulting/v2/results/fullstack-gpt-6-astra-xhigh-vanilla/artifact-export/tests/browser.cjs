const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const base = process.env.BASE_URL || 'http://127.0.0.1:8000';
const output = path.resolve('evidence');
fs.mkdirSync(output, {recursive: true});
const result = {started_at: new Date().toISOString(), base_url: base, steps: [], browser_errors: [], server_errors: []};
let browser, context, page;
function record(name) { result.steps.push({name, status: 'passed'}); console.log(`PASS ${name}`); }
async function screenshot(filename) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({path: path.join(output, filename), fullPage: true});
}
async function textIncludes(locator, text) { await locator.getByText(text, {exact: false}).first().waitFor(); }
async function login(role, tenant = 'north') {
  await page.getByTestId('login-email').fill(`${role}@${tenant}.example`);
  await page.getByTestId('login-password').fill('DepotDemo!2026');
  await page.getByTestId('login-submit').click();
  await page.getByTestId('inventory-table').waitFor();
}
async function logout() { await page.getByTestId('logout').click(); await page.getByTestId('login-email').waitFor(); }
async function notice(text) { await textIncludes(page.locator('#notice'), text); }
async function request(route, body) {
  const token = await page.evaluate(() => sessionStorage.getItem('depot-token'));
  const response = await fetch(base + '/api' + route, {method: body ? 'POST' : 'GET', headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID()}, body: body ? JSON.stringify(body) : undefined});
  assert.ok(response.ok, `${route}: ${response.status}`); return response.json();
}
async function newOrder(ref, lines) {
  await page.getByTestId('nav-orders').click();
  await page.getByTestId('new-order').click();
  await page.getByTestId('order-client-ref').fill(ref);
  for (let i = 0; i < lines.length; i++) {
    if (i) await page.getByTestId('add-line').click();
    await page.getByTestId('line-sku').nth(i).selectOption(lines[i].sku);
    await page.getByTestId('line-quantity').nth(i).fill(String(lines[i].quantity));
  }
  await page.getByTestId('submit-order').click();
  await page.getByTestId('order-detail').waitFor();
  await notice('Draft created');
}

(async () => {
  try {
    browser = process.env.EVAL_BROWSER_WS ? await chromium.connect(process.env.EVAL_BROWSER_WS) : await chromium.launch({headless: true});
    result.browser_version = browser.version();
    context = await browser.newContext({viewport: {width: 1440, height: 1100}});
    page = await context.newPage();
    page.on('pageerror', error => result.browser_errors.push(error.message));
    page.on('response', response => { if (response.status() >= 500) result.server_errors.push({url: response.url(), status: response.status()}); });
    await page.goto(base);
    await screenshot('login-desktop.png');
    await page.getByTestId('login-email').fill('admin@north.example');
    await page.getByTestId('login-password').fill('bad-password');
    await page.getByTestId('login-submit').click();
    await textIncludes(page.locator('#login-error'), 'incorrect');
    await login('admin');
    assert.match(await page.getByTestId('inventory-table').innerText(), /BOLT/);
    record('Login errors and authenticated inventory');

    await page.locator('#adjust-delta').fill('5');
    await page.locator('#adjust-reason').fill('Receiving dock count');
    await request('/stock/adjustments', {sku: 'BOLT', delta: 2, expected_version: 1, reason: 'Concurrent count'});
    await page.getByRole('button', {name: 'Adjust stock', exact: true}).click();
    await notice('This record changed');
    assert.equal(await page.locator('#adjust-delta').inputValue(), '5');
    await page.getByRole('button', {name: 'Refresh record · keep input'}).click();
    await notice('Your input was kept');
    assert.equal(await page.locator('#adjust-reason').inputValue(), 'Receiving dock count');
    await page.getByRole('button', {name: 'Adjust stock', exact: true}).click();
    await notice('Stock adjusted');
    assert.match(await page.getByTestId('inventory-table').innerText(), /107/);
    await screenshot('inventory-desktop.png');
    record('Admin stock adjustment and stale-version recovery preserves input');

    await newOrder('NORTH-1042', [{sku: 'BOLT', quantity: 4}, {sku: 'CABLE', quantity: 3}]);
    await textIncludes(page.getByTestId('order-detail'), 'draft');
    await page.getByTestId('reserve-order').click(); await notice('reserved');
    await page.getByTestId('ship-order').click(); await notice('shipped');
    let order = (await request('/orders?q=NORTH-1042')).items[0];
    await page.getByTestId('return-quantity').nth(0).fill('1');
    await request(`/orders/${order.id}/returns`, {expected_version: order.version, lines: [{sku: 'BOLT', quantity: 1}]});
    await page.getByTestId('submit-return').click(); await notice('This record changed');
    assert.equal(await page.getByTestId('return-quantity').nth(0).inputValue(), '1');
    await page.getByRole('button', {name: 'Refresh record · keep input'}).click(); await notice('Your input was kept');
    assert.equal(await page.getByTestId('return-quantity').nth(0).inputValue(), '1');
    await page.getByTestId('submit-return').click(); await notice('return received');
    await textIncludes(page.getByTestId('order-detail'), 'shipped');
    await screenshot('order-detail-desktop.png');
    await page.getByTestId('return-quantity').nth(0).fill('2');
    await page.getByTestId('return-quantity').nth(1).fill('3');
    await page.getByTestId('submit-return').click(); await notice('return received');
    await textIncludes(page.getByTestId('order-detail'), 'returned');
    assert.equal(await page.getByTestId('submit-return').count(), 0);
    record('Multi-line create, reserve, ship, partial/full returns, and stale return recovery');

    await newOrder('FREE-SAMPLE', [{sku: 'SAMPLE', quantity: 1}]);
    await textIncludes(page.getByTestId('order-detail'), '$0.00');
    await page.getByTestId('reserve-order').click(); await notice('reserved');
    await page.getByTestId('cancel-order').click(); await notice('cancelled');
    record('Zero-price order and reserved cancellation');

    await newOrder('ATOMIC-FAILURE', [{sku: 'SAMPLE', quantity: 1}, {sku: 'BOLT', quantity: 999}]);
    const before = await request('/inventory');
    await page.getByTestId('reserve-order').click(); await notice('Not enough available stock');
    assert.deepEqual(await request('/inventory'), before);
    await textIncludes(page.getByTestId('order-detail'), 'draft');
    record('Atomic reservation failure leaves UI order and inventory unchanged');

    await page.getByTestId('new-order').click();
    const hostile = '<img src=x onerror=alert(1)>';
    await page.getByTestId('order-client-ref').fill(hostile);
    await page.getByTestId('line-sku').selectOption('SAMPLE');
    let aborted = false;
    await page.route('**/api/orders', async route => {
      if (!aborted && route.request().method() === 'POST') {
        aborted = true; await route.fetch(); await route.abort('failed');
      } else await route.continue();
    });
    await page.getByTestId('submit-order').click(); await notice('Cannot reach DepotFlow');
    assert.equal(await page.getByTestId('order-client-ref').inputValue(), hostile);
    await page.getByTestId('submit-order').click(); await notice('Draft created');
    await page.unroute('**/api/orders');
    await textIncludes(page.getByTestId('order-detail'), hostile);
    assert.equal(await page.getByTestId('order-detail').locator('img').count(), 0);
    assert.equal((await request('/orders?q=' + encodeURIComponent(hostile))).items.length, 1);
    record('Lost response retry creates once and client text stays inert');

    await page.locator('#order-search').fill('north');
    await page.locator('#order-status').selectOption('returned');
    await page.getByRole('button', {name: 'Apply filters'}).click();
    await page.waitForFunction(() => [...document.querySelectorAll('table')].at(-1).querySelectorAll('tbody tr').length === 1);
    await textIncludes(page.locator('table').last(), 'NORTH-1042');
    assert.equal(await page.locator('table').last().locator('tbody tr').count(), 1);
    await page.locator('#order-search').fill('does-not-exist');
    await page.getByRole('button', {name: 'Apply filters'}).click();
    await page.getByText('No orders to display', {exact: true}).waitFor();
    await page.getByTestId('nav-audit').click(); await page.getByTestId('audit-table').waitFor();
    await textIncludes(page.getByTestId('audit-table'), 'stock.adjusted');
    await page.getByTestId('audit-table').locator('summary').first().click();
    await textIncludes(page.getByTestId('audit-table'), 'Concurrent count');
    await screenshot('audit-desktop.png');
    record('Search/status filters, empty state, and audit change details');

    await logout(); await login('viewer');
    assert.equal(await page.locator('#adjustment-form').count(), 0);
    await page.getByTestId('nav-orders').click();
    await page.getByRole('button', {name: 'View NORTH-1042', exact: true}).click();
    await page.getByTestId('order-detail').waitFor();
    for (const id of ['new-order', 'reserve-order', 'ship-order', 'cancel-order', 'submit-return']) assert.equal(await page.getByTestId(id).count(), 0);
    await page.getByTestId('nav-audit').click(); await page.getByTestId('audit-table').waitFor();
    record('Viewer can inspect all views and receives no writable controls');

    await logout(); await login('operator', 'south');
    const south = await request('/inventory');
    assert.equal(south.items.find(item => item.sku === 'BOLT').on_hand, 100);
    await page.getByTestId('nav-orders').click(); await page.getByText('No orders to display', {exact: true}).waitFor();
    record('South organization has independent stock and no north orders');

    await page.setViewportSize({width: 390, height: 844});
    await newOrder('MOBILE-ORDER', [{sku: 'BOLT', quantity: 1}, {sku: 'SAMPLE', quantity: 1}]);
    await page.getByTestId('reserve-order').click(); await notice('reserved');
    await page.getByTestId('ship-order').click(); await notice('shipped');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await screenshot('order-mobile.png');
    await page.getByTestId('nav-inventory').click(); await page.getByTestId('inventory-table').waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await screenshot('inventory-mobile.png');
    await page.reload(); await page.getByTestId('inventory-table').waitFor();
    await logout();
    await page.getByTestId('login-email').focus(); await page.keyboard.press('Tab');
    assert.equal(await page.getByTestId('login-password').evaluate(node => node === document.activeElement), true);
    record('390px mobile fulfillment, page reload session, logout, and keyboard labels');
    await page.setViewportSize({width: 1440, height: 1100});
    await login('operator');
    for (let i = 0; i < 23; i++) await request('/orders', {client_ref: `PAGING-${i}`, lines: [{sku: 'SAMPLE', quantity: 1}]});
    await page.getByTestId('nav-orders').click();
    await page.getByRole('button', {name: 'Load more orders'}).waitFor();
    assert.equal(await page.locator('table tbody tr').count(), 20);
    await page.getByRole('button', {name: 'Load more orders'}).click();
    await page.getByRole('button', {name: 'Load more orders'}).waitFor({state: 'hidden'});
    assert.equal(await page.locator('table tbody tr').count(), 27);
    await page.getByTestId('new-order').click();
    await page.getByTestId('order-client-ref').fill('DOUBLE-CLICK');
    await page.getByTestId('submit-order').evaluate(node => { node.click(); node.click(); });
    await notice('Draft created');
    assert.equal((await request('/orders?q=DOUBLE-CLICK')).items.length, 1);
    record('Load-more pagination and rapid double submission');
    assert.deepEqual(result.browser_errors, []); assert.deepEqual(result.server_errors, []);
    result.status = 'passed';
    fs.rmSync(path.join(output, 'browser-failure.png'), {force: true});
  } catch (error) {
    result.status = 'failed'; result.failure = error.stack; console.error(error);
    if (page) await page.screenshot({path: path.join(output, 'browser-failure.png'), fullPage: true}).catch(() => {});
    process.exitCode = 1;
  } finally {
    result.finished_at = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
    if (context) await context.close(); if (browser) await browser.close();
  }
})();
