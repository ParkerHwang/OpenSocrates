// Browser workflow check; run against a seeded local server with EVAL_BROWSER_WS set.
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.connect(process.env.EVAL_BROWSER_WS);const context=await browser.newContext();const page=await context.newPage();
 try{
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8000');
  await page.getByTestId('login-email').fill('operator@north.example');await page.getByTestId('login-password').fill('DepotDemo!2026');await page.getByTestId('login-submit').click();
  await page.getByTestId('inventory-table').waitFor();await page.getByTestId('nav-orders').click();await page.getByTestId('order-client-ref').fill('browser-'+Date.now());
  await page.getByTestId('line-sku').selectOption('SAMPLE');await page.getByTestId('line-quantity').fill('2');await page.getByTestId('submit-order').click();
  await page.getByTestId('order-detail').waitFor();await page.getByTestId('reserve-order').click();await page.getByTestId('ship-order').waitFor();await page.getByTestId('ship-order').click();
  await page.getByTestId('return-quantity').fill('1');await page.getByTestId('submit-return').click();await page.waitForFunction(()=>{const d=document.querySelector('[data-testid="order-detail"]');return d&&d.querySelector('tbody tr td:last-child')?.textContent==='1'});
  await page.getByTestId('return-quantity').fill('1');await page.getByTestId('submit-return').click();await page.getByTestId('submit-return').waitFor({state:'detached'});await page.getByTestId('order-detail').getByText('returned',{exact:true}).waitFor();
  await page.getByTestId('nav-audit').click();await page.getByTestId('audit-table').waitFor();
  await page.getByTestId('logout').click();await page.getByTestId('login-email').fill('viewer@north.example');await page.getByTestId('login-password').fill('DepotDemo!2026');await page.getByTestId('login-submit').click();await page.getByTestId('nav-orders').click();
  if(await page.getByTestId('new-order').count())throw new Error('Viewer was offered order creation');
  console.log(JSON.stringify({result:'passed',workflow:'operator login, inventory, create, reserve, ship, partial/full return, audit; viewer login read-only',url:page.url()}));
 }finally{await context.close();await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
