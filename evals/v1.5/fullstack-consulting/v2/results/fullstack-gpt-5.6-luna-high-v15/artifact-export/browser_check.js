const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.connect(process.env.EVAL_BROWSER_WS); const context=await browser.newContext(); const page=await context.newPage();
 await page.goto('http://127.0.0.1:18765/');
 await page.getByTestId('login-email').fill('operator@north.example'); await page.getByTestId('login-password').fill('DepotDemo!2026'); await page.getByTestId('login-submit').click();
 await page.getByTestId('nav-inventory').waitFor(); if (!(await page.getByTestId('inventory-table').isVisible())) throw new Error('inventory table not visible');
 await page.getByTestId('nav-orders').click(); await page.getByTestId('new-order').click(); const clientRef='browser-order-'+Date.now(); await page.getByTestId('order-client-ref').fill(clientRef); await page.getByTestId('line-sku').selectOption('SAMPLE'); await page.getByTestId('line-quantity').fill('1'); await page.getByTestId('submit-order').click();
 await page.getByTestId('order-detail').waitFor(); if (!(await page.getByTestId('order-detail').innerText()).includes(clientRef)) throw new Error('order detail missing client ref');
 await page.getByTestId('nav-audit').click(); await page.getByTestId('audit-table').waitFor();
 await page.getByTestId('logout').click(); await page.getByTestId('login-email').fill('viewer@north.example'); await page.getByTestId('login-password').fill('DepotDemo!2026'); await page.getByTestId('login-submit').click(); await page.getByTestId('nav-orders').click(); await page.getByRole('button',{name:'Open'}).first().click();
 if (await page.getByTestId('reserve-order').count() !== 0 || await page.getByTestId('new-order').count() !== 0) throw new Error('viewer controls incorrect');
 console.log('browser workflow: PASS'); await context.close(); await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
