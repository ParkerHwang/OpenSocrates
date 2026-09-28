/* Real Chromium workflow; owns an isolated seeded store and records evidence. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const readline = require('node:readline');

const root = path.resolve(__dirname, '..');
fs.mkdirSync(path.join(root, '.local'), {recursive: true});
fs.mkdirSync(path.join(root, 'evidence'), {recursive: true});
const dataDir = fs.mkdtempSync(path.join(root, '.local', 'browser-'));
const logs = fs.openSync(path.join(dataDir, 'server.log'), 'a');
const server = spawn(path.join(root, 'run.sh'), [], {
  cwd: root, env: {...process.env, DATA_DIR: dataDir, PORT: '0', SEED_DEMO: '1'}, stdio: ['ignore', 'pipe', logs],
});
const results = [];
let browser, context, page;
const testid = name => page.getByTestId(name);
const record = name => { results.push({check: name, result: 'passed'}); console.log(`PASS ${name}`); };
async function settled() {
  await page.waitForFunction(() => document.querySelector('main[aria-busy="false"]'));
}
async function click(name) {
  await testid(name).click();
  if (name === 'logout') await testid('login-submit').waitFor();
  else await settled();
}
async function status(name) {
  await page.waitForFunction(s => document.querySelector('[data-testid="order-detail"] .badge')?.textContent === s, name);
}
async function login(role = 'operator', tenant = 'north') {
  await testid('login-email').fill(`${role}@${tenant}.example`);
  await testid('login-password').fill('DepotDemo!2026');
  await testid('login-submit').click(); await settled();
}
async function create(ref, lines = [{sku: 'BOLT', quantity: 3}]) {
  await click('nav-orders'); await click('new-order');
  await testid('order-client-ref').fill(ref);
  for (let i = 0; i < lines.length; i++) {
    if (i) await click('add-line');
    await testid('line-sku').nth(i).selectOption(lines[i].sku);
    await testid('line-quantity').nth(i).fill(String(lines[i].quantity));
  }
  await click('submit-order'); await status('draft');
}
async function api(url, options = {}) {
  const token = await page.evaluate(() => sessionStorage.getItem('depotflow-token'));
  const response = await page.request.fetch(url, {...options, headers: {Authorization: `Bearer ${token}`, 'Idempotency-Key': require('node:crypto').randomUUID()}});
  assert(response.ok(), await response.text());
  return response.json();
}
async function screenshot(name) {
  const buffer = await page.screenshot({fullPage: true});
  fs.writeFileSync(path.join(root, 'evidence', name), buffer);
}

(async () => {
  const base = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Server startup timeout')), 20000);
    const lines = readline.createInterface({input: server.stdout});
    lines.on('line', line => {
      if (line.startsWith('DepotFlow listening on ')) { clearTimeout(timeout); resolve(line.split(' on ')[1]); }
    });
    server.on('exit', code => {clearTimeout(timeout); reject(new Error(`Server exited ${code}`));});
  });
  // In the supplied environment use its fresh isolated browser, never shell launch.
  browser = process.env.EVAL_BROWSER_WS
    ? await chromium.connect(process.env.EVAL_BROWSER_WS)
    : await chromium.launch({headless: true});
  context = await browser.newContext({viewport: {width: 1440, height: 1050}, baseURL: base});
  page = await context.newPage();
  const browserErrors = [];
  page.on('pageerror', error => browserErrors.push(error.message));
  await page.goto(base);
  await testid('login-email').fill('operator@north.example');
  await testid('login-password').fill('wrong');
  await testid('login-submit').click();
  await page.getByRole('alert').waitFor();
  assert.match(await page.getByRole('alert').innerText(), /incorrect/);
  await login();
  await testid('inventory-table').waitFor();
  assert.match(await testid('inventory-table').innerText(), /Steel bolt kit/);
  assert.equal(await testid('adjust-stock').count(), 0);
  record('Login errors, operator login, inventory/dashboard, role controls');

  await create('WEB-1042', [{sku: 'BOLT', quantity: 3}, {sku: 'CABLE', quantity: 2}]);
  assert.match(await testid('order-detail').innerText(), /\$87\.48/);
  await click('reserve-order'); await status('reserved');
  await screenshot('desktop-orders.png');
  await click('ship-order'); await status('shipped');
  record('Multi-line order creation, reserve, ship, server-priced total');

  await testid('return-quantity').nth(0).fill('1');
  const order = (await api('/api/orders?q=WEB-1042')).items[0];
  await api(`/api/orders/${order.id}/returns`, {method: 'POST', data: {expected_version: order.version, lines: [{sku: 'BOLT', quantity: 1}]}});
  await click('submit-return');
  assert.match(await page.getByRole('alert').innerText(), /changed.*input has been kept/s);
  assert.equal(await testid('return-quantity').nth(0).inputValue(), '1');
  await click('submit-return'); await status('shipped');
  await testid('return-quantity').nth(0).fill('1');
  await testid('return-quantity').nth(1).fill('2');
  await click('submit-return'); await status('returned');
  record('Stale-version feedback preserves entered return quantity; partial and full returns');

  await create('SAMPLE-FREE', [{sku: 'SAMPLE', quantity: 1}]);
  assert.match(await testid('order-detail').innerText(), /\$0\.00/);
  await click('reserve-order'); await click('cancel-order'); await status('cancelled');
  record('Zero-price order and reserved cancellation');

  await click('new-order');
  await testid('order-client-ref').fill('DOUBLE-CLICK');
  let creates = 0;
  const listener = request => {if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/orders') creates++;};
  page.on('request', listener);
  await testid('submit-order').evaluate(button => {button.click(); button.click();});
  await settled(); await status('draft');
  page.off('request', listener);
  assert.equal(creates, 1);
  record('Double submission produces one create request');

  await click('new-order');
  await testid('order-client-ref').fill('AMBIGUOUS-RESPONSE');
  let intercepted = false;
  await page.route('**/api/orders', async route => {
    if (route.request().method() === 'POST' && !intercepted) {
      intercepted = true;
      const response = await route.fetch(); assert.equal(response.status(), 201);
      await route.abort('failed'); // Commit succeeds; the browser never receives the response.
    } else await route.continue();
  });
  await click('submit-order');
  await testid('retry-mutation').waitFor();
  assert.match(await page.getByRole('alert').innerText(), /did not confirm/);
  assert.equal(await testid('order-client-ref').inputValue(), 'AMBIGUOUS-RESPONSE');
  await page.reload(); await settled();
  assert.match(await page.getByRole('alert').innerText(), /previous request/);
  await click('retry-mutation'); await status('draft');
  await page.unroute('**/api/orders');
  assert.equal((await api('/api/orders?q=AMBIGUOUS-RESPONSE')).items.length, 1);
  const ambiguous = (await api('/api/orders?q=AMBIGUOUS-RESPONSE')).items[0];
  assert.equal((await api('/api/audit?limit=100')).items.filter(e => e.entity_id === ambiguous.id).length, 1);
  record('Lost successful response survives reload and retries with original key and one audit event');

  const malicious = '<img src=x onerror="window.depotXss=1">';
  await create(malicious);
  assert.match(await testid('order-detail').innerText(), /<img src=x/);
  assert.equal(await page.evaluate(() => window.depotXss), undefined);
  assert.equal(await testid('order-detail').locator('img').count(), 0);
  await testid('order-search').fill('sample-free');
  await testid('order-status').selectOption('cancelled');
  await click('apply-filters');
  assert.equal(await testid('open-order').count(), 1);
  assert.equal(await testid('open-order').innerText(), 'SAMPLE-FREE');
  await testid('order-search').fill('no-such-reference'); await click('apply-filters');
  await page.getByText('No orders here yet', {exact: true}).waitFor();
  record('Literal rendering of client text, order search/status filters and empty state');

  await click('nav-audit');
  assert.match(await testid('audit-table').innerText(), /operator@north.example/);
  assert.match(await testid('audit-table').innerText(), /order returned/i);
  await screenshot('desktop-audit.png');
  await click('nav-inventory');
  const inventory = (await api('/api/inventory')).items;
  assert.equal(inventory.find(i => i.sku === 'BOLT').on_hand, 100);
  assert.equal(inventory.find(i => i.sku === 'BOLT').reserved, 0);
  await screenshot('desktop-inventory.png');
  await page.reload(); await settled();
  assert.match(await testid('inventory-table').innerText(), /BOLT/);
  record('Audit inspection, inventory refresh and session restoration on reload');

  await click('logout'); await login('admin');
  await click('adjust-stock');
  await testid('adjust-sku').selectOption('CABLE');
  await testid('adjust-delta').fill('7');
  await testid('adjust-reason').fill('Received supplier carton');
  await click('submit-adjustment');
  assert.equal((await api('/api/inventory')).items.find(i => i.sku === 'CABLE').on_hand, 67);
  record('Admin stock adjustment form updates persisted inventory');

  await click('adjust-stock');
  await testid('adjust-delta').fill('5');
  await testid('adjust-reason').fill('Private north draft reason');
  await click('logout'); await login('admin', 'south');
  await click('adjust-stock');
  assert.equal(await testid('adjust-delta').inputValue(), '');
  assert.equal(await testid('adjust-reason').inputValue(), '');
  record('Logout clears unfinished tenant-specific stock adjustment input');

  await click('logout'); await login('viewer');
  assert.equal(await testid('adjust-stock').count(), 0);
  await click('nav-orders');
  assert.equal(await testid('new-order').count(), 0);
  await testid('open-order').filter({hasText: 'DOUBLE-CLICK'}).click(); await settled();
  await status('draft');
  for (const id of ['reserve-order', 'ship-order', 'cancel-order', 'submit-return']) assert.equal(await testid(id).count(), 0);
  record('Viewer can inspect details and has no writable controls');

  await click('logout'); await login('operator', 'south');
  assert.equal((await api('/api/inventory')).items.find(i => i.sku === 'CABLE').on_hand, 60);
  await click('nav-orders');
  assert.equal(await testid('open-order').count(), 0);
  await page.setViewportSize({width: 390, height: 844});
  await create('MOBILE-2001', [{sku: 'SAMPLE', quantity: 2}]);
  await click('reserve-order'); await click('ship-order'); await status('shipped');
  await testid('return-quantity').fill('2'); await click('submit-return'); await status('returned');
  await screenshot('mobile-order.png');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await click('nav-inventory'); await screenshot('mobile-inventory.png');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  record('South workspace isolation; complete mobile workflow at 390 px with no page overflow');

  await click('logout');
  await testid('login-email').focus();
  await testid('login-email').fill('viewer@south.example');
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(() => document.activeElement.dataset.testid), 'login-password');
  await page.keyboard.type('DepotDemo!2026');
  await page.keyboard.press('Enter'); await settled();
  record('Keyboard login via labels, tab order and Enter');
  assert.deepEqual(browserErrors, []);
  record('No browser JavaScript errors');
  const report = {date: new Date().toISOString(), browser: browser.version(), playwright: require('playwright/package.json').version,
    viewports: [{width: 1440, height: 1050}, {width: 390, height: 844}], checks: results, pageErrors: browserErrors};
  fs.writeFileSync(path.join(root, 'evidence', 'browser-results.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(`Completed ${results.length} browser checks.`);
})().catch(async error => {
  console.error(error);
  if (page) { try {await screenshot('browser-failure.png');} catch (_) {} }
  process.exitCode = 1;
}).finally(async () => {
  if (context) await context.close();
  if (browser) await browser.close();
  server.kill('SIGTERM');
  fs.closeSync(logs);
});
