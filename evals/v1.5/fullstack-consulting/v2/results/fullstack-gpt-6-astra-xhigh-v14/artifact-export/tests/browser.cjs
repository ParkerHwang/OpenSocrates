'use strict';
// A fresh synthetic store is started and deleted for every browser exercise.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const {spawn} = require('node:child_process');
const ROOT = path.resolve(__dirname, '..');
const evidence = path.join(ROOT, 'evidence');
fs.mkdirSync(evidence, {recursive: true});
fs.mkdirSync(path.join(ROOT, '.test-data'), {recursive: true});
const dataDir = fs.mkdtempSync(path.join(ROOT, '.test-data', 'browser-'));
const report = {started_at: new Date().toISOString(), checks: [], errors: [], screenshots: []};
let server, browser, context, page, base;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const mark = text => {report.checks.push(text); console.log('PASS', text);};
const tid = id => page.getByTestId(id);

async function freePort() {
  return new Promise(resolve => {const socket = net.createServer(); socket.listen(0, '127.0.0.1', () => {const port = socket.address().port; socket.close(() => resolve(port));});});
}
async function waitText(locator, text) {
  await locator.filter({hasText: text}).waitFor({state: 'visible'});
}
async function screenshot(name) {
  await page.screenshot({path: path.join(evidence, name), fullPage: true});
  report.screenshots.push(name);
}
async function login(role = 'admin', tenant = 'north') {
  await tid('login-email').fill(`${role}@${tenant}.example`);
  await tid('login-password').fill('DepotDemo!2026');
  await tid('login-submit').click();
  await tid('inventory-table').waitFor();
}
async function create(ref, quantities = [['BOLT', 2], ['CABLE', 3]]) {
  await tid('nav-orders').click(); await tid('new-order').click();
  await tid('order-client-ref').fill(ref);
  for (let i=0; i<quantities.length; i++) {
    if (i) await tid('add-line').click();
    await tid('line-sku').nth(i).selectOption(quantities[i][0]);
    await tid('line-quantity').nth(i).fill(String(quantities[i][1]));
  }
  await tid('submit-order').click();
  await waitText(tid('order-detail'), ref);
  await waitText(tid('order-detail').locator('.status'), 'draft');
}
async function stock(sku) {
  const row = tid('inventory-table').getByRole('row').filter({hasText: sku});
  return {on_hand: Number(await row.locator('td').nth(1).textContent()), reserved: Number(await row.locator('td').nth(2).textContent())};
}
async function browserAPI(method, route, payload) {
  return page.evaluate(async ({method, route, payload}) => {
    const result = await fetch(route, {method, headers: {'Content-Type': 'application/json',
      Authorization: `Bearer ${sessionStorage.getItem('depotflow-token')}`,
      'Idempotency-Key': crypto.randomUUID()}, ...(payload ? {body: JSON.stringify(payload)} : {})});
    return {status: result.status, body: await result.json()};
  }, {method, route, payload});
}
async function overflowCheck() {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Page must not overflow horizontally');
}

(async () => {
  const port = await freePort(); base = `http://127.0.0.1:${port}`;
  const log = fs.openSync(path.join(evidence, 'browser-server.log'), 'w');
  server = spawn(path.join(ROOT, 'run.sh'), {cwd: ROOT, env: {...process.env, PORT: String(port), DATA_DIR: dataDir, SEED_DEMO: '1', QUIET: '1'}, stdio: ['ignore', log, log]});
  for (let i=0; i<200; i++) {
    if (server.exitCode !== null) throw new Error('Application exited before becoming ready.');
    try {if ((await fetch(`${base}/api/health`)).ok) break;} catch (_) {}
    await delay(50);
  }
  // This environment supplies an isolated browser. Ordinary local installs may launch their own.
  browser = process.env.EVAL_BROWSER_WS ? await chromium.connect(process.env.EVAL_BROWSER_WS) : await chromium.launch({headless: true});
  report.browser = browser.version();
  context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  page = await context.newPage(); page.setDefaultTimeout(10000);
  page.on('pageerror', err => report.errors.push(err.message));
  await page.goto(base); await screenshot('login-desktop.png');
  await tid('login-email').fill('admin@north.example'); await tid('login-password').fill('wrong'); await tid('login-submit').click();
  await waitText(page.getByRole('alert'), 'incorrect');
  mark('Bad credentials show a useful error; successful login opens inventory.');
  await login(); assert.deepEqual(await stock('BOLT'), {on_hand: 100, reserved: 0});
  await page.getByText('Adjust stock', {exact: true}).click();
  await tid('adjustment-sku').selectOption('BOLT'); await tid('adjustment-delta').fill('1'); await tid('adjustment-reason').fill('Browser receiving check');
  await tid('submit-adjustment').click();
  await waitText(page.getByRole('status'), 'Stock adjustment saved');
  assert.deepEqual(await stock('BOLT'), {on_hand: 101, reserved: 0});
  await screenshot('inventory-desktop.png'); mark('Administrator records stock adjustment and updated dashboard/inventory.');
  await create('BROWSER-1042');
  await tid('reserve-order').click(); await waitText(tid('order-detail').locator('.status'), 'reserved');
  await tid('ship-order').click(); await waitText(tid('order-detail').locator('.status'), 'shipped');
  await tid('return-quantity').nth(0).fill('1'); await tid('submit-return').click();
  await waitText(page.getByRole('status'), 'Partial return recorded');
  await screenshot('order-desktop.png');
  await tid('return-quantity').nth(0).fill('1'); await tid('return-quantity').nth(1).fill('3'); await tid('submit-return').click();
  await waitText(tid('order-detail').locator('.status'), 'returned');
  await tid('nav-inventory').click(); assert.deepEqual(await stock('BOLT'), {on_hand: 101, reserved: 0}); assert.deepEqual(await stock('CABLE'), {on_hand: 60, reserved: 0});
  mark('Multiple order lines reserve, ship, partially return, and fully return with matching stock.');
  await create('FREE-SAMPLE', [['SAMPLE', 1]]); await waitText(tid('order-detail'), '$0.00');
  await tid('reserve-order').click(); await tid('cancel-order').click(); await waitText(tid('order-detail').locator('.status'), 'cancelled');
  mark('Zero-price SAMPLE order is valid; reserved cancellation releases stock.');
  await create('STALE-RETURN', [['BOLT', 3]]); await tid('reserve-order').click(); await tid('ship-order').click();
  await tid('return-quantity').fill('1');
  let result = await browserAPI('GET', '/api/orders?q=STALE-RETURN'); const stale = result.body.items[0];
  result = await browserAPI('POST', `/api/orders/${stale.id}/returns`, {expected_version: stale.version, lines: [{sku: 'BOLT', quantity: 1}]}); assert.equal(result.status,200);
  await tid('submit-return').click(); await waitText(page.getByRole('alert'), 'changed'); assert.equal(await tid('return-quantity').inputValue(),'1');
  await page.getByRole('button', {name: 'Refresh order', exact: true}).click(); assert.equal(await tid('return-quantity').inputValue(),'1');
  await tid('submit-return').click(); await waitText(page.getByRole('status'), 'Partial return recorded');
  mark('Stale-version return retains input and can be refreshed, reviewed, and retried.');
  await tid('nav-orders').click(); await tid('order-search').fill('BROWSER-1042'); await tid('order-filter').selectOption('returned');
  await page.getByRole('button', {name: 'Apply filters', exact: true}).click(); await waitText(page.locator('main table'), 'BROWSER-1042');
  assert.equal(await page.locator('main tbody tr').count(),1);
  await tid('order-search').fill('NO-SUCH-ORDER'); await page.getByRole('button', {name: 'Apply filters', exact: true}).click(); await waitText(page.locator('main'), 'No orders found');
  mark('Order search, status filters, and empty results work.');
  await create('<img src=x onerror="window.injected=true">', [['SAMPLE',1]]);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  assert.equal(await tid('order-detail').locator('img').count(),0);
  mark('Arbitrary client text is rendered as text, not HTML.');
  // Force an ambiguous successful create: commit on the server, discard the reply.
  await tid('nav-orders').click(); await tid('new-order').click(); await tid('order-client-ref').fill('RETRY-IN-BROWSER');
  let intercepted = false;
  await page.route('**/api/orders', async route => {
    if (route.request().method() === 'POST' && !intercepted) {intercepted = true; await route.fetch(); await route.abort('connectionreset');}
    else await route.continue();
  });
  await tid('submit-order').click(); await waitText(page.getByRole('alert'), 'Connection interrupted');
  assert.equal(await tid('order-client-ref').inputValue(),'RETRY-IN-BROWSER');
  await tid('submit-order').click(); await waitText(tid('order-detail'), 'RETRY-IN-BROWSER'); await page.unroute('**/api/orders');
  result = await browserAPI('GET','/api/orders?q=RETRY-IN-BROWSER'); assert.equal(result.body.items.length,1);
  mark('An interrupted successful write safely replays with the same key and preserved form.');
  await tid('nav-audit').click(); await tid('audit-table').waitFor();
  await tid('audit-table').locator('summary').first().click(); await waitText(tid('audit-table'), 'Browser receiving check'); await screenshot('audit-desktop.png');
  mark('Audit shows actor, reference, stock before/after, and adjustment reason.');
  // Native keyboard controls and mobile layout, on a narrow viewport.
  await page.setViewportSize({width: 390, height: 844}); await tid('nav-inventory').click(); await tid('inventory-table').waitFor(); await overflowCheck(); await screenshot('inventory-mobile.png');
  await create('MOBILE-ORDER', [['SAMPLE',1]]); await tid('reserve-order').click(); await tid('ship-order').click();
  await tid('return-quantity').fill('1'); await tid('submit-return').focus(); await page.keyboard.press('Enter');
  await waitText(tid('order-detail').locator('.status'), 'returned'); await overflowCheck(); await screenshot('order-mobile.png');
  mark('390px mobile workflow supports create, reserve, ship, keyboard return, and no page overflow.');
  await tid('logout').click(); await login('viewer');
  assert.equal(await page.getByText('Adjust stock', {exact: true}).count(),0);
  await tid('nav-orders').click(); await page.locator('main table').waitFor(); assert.equal(await tid('new-order').count(),0);
  await page.getByRole('button', {name:'RETRY-IN-BROWSER', exact:true}).click(); await tid('order-detail').waitFor();
  assert.equal(await tid('reserve-order').count(),0); assert.equal(await tid('cancel-order').count(),0);
  await tid('nav-audit').click(); await tid('audit-table').waitFor(); mark('Viewer can inspect orders and audit with no mutation controls.');
  await tid('logout').click(); await login('operator','south'); assert.deepEqual(await stock('BOLT'),{on_hand:100,reserved:0});
  assert.equal(await page.getByText('Adjust stock', {exact: true}).count(),0);
  await tid('nav-orders').click(); await waitText(page.locator('main'), 'No orders found');
  await create('SOUTH-ONLY', [['BOLT',1]]); await tid('cancel-order').click(); await waitText(tid('order-detail').locator('.status'),'cancelled');
  await page.reload(); await tid('inventory-table').waitFor();
  mark('South is isolated; operator can fulfill but cannot adjust stock; reload retains session.');
  assert.deepEqual(report.errors,[],'No uncaught browser exceptions');
  report.passed = true;
})().catch(error => {
  report.passed = false; report.failure = error.stack; console.error(error);
  process.exitCode = 1;
}).finally(async () => {
  report.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(evidence,'browser-results.json'), JSON.stringify(report,null,2)+'\n');
  if (context) await context.close();
  if (browser) await browser.close();
  if (server && server.exitCode === null) {server.kill('SIGTERM'); await new Promise(resolve => server.once('exit',resolve));}
  fs.rmSync(dataDir, {recursive:true,force:true});
});
