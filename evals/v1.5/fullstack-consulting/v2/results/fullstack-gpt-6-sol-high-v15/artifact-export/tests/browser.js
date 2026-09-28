const {chromium}=require('playwright');
(async()=>{
 const browser=process.env.EVAL_BROWSER_WS?await chromium.connect(process.env.EVAL_BROWSER_WS):await chromium.launch({headless:true});
 const width=Number(process.env.VIEWPORT_WIDTH||390),height=Number(process.env.VIEWPORT_HEIGHT||844);
 const context=await browser.newContext({viewport:{width,height}});
 const page=await context.newPage();
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 const ref='browser-'+Date.now();
 async function waitStatus(status){await page.waitForFunction(value=>{const d=document.querySelector('[data-testid="order-detail"]');return d&&d.textContent.includes('Status'+value)},status)}
 try{
  await page.goto('http://127.0.0.1:'+(process.env.PORT||8765)+'/');
  await page.getByTestId('login-email').fill('operator@north.example');
  await page.getByTestId('login-password').fill('DepotDemo!2026');
  await page.getByTestId('login-submit').click();
  await page.getByTestId('inventory-table').waitFor();
  await page.getByTestId('nav-orders').click();
  await page.getByTestId('new-order').click();
  await page.getByTestId('order-client-ref').fill(ref);
  await page.getByTestId('line-sku').first().selectOption('BOLT');
  await page.getByTestId('line-quantity').first().fill('2');
  await page.getByTestId('add-line').click();
  await page.getByTestId('line-sku').nth(1).selectOption('SAMPLE');
  await page.getByTestId('line-quantity').nth(1).fill('1');
  await page.getByTestId('submit-order').click();
  await page.getByTestId('order-detail').getByText(ref).waitFor();
  await page.getByTestId('reserve-order').click();
  await waitStatus('reserved');
  await page.getByTestId('ship-order').click();
  await waitStatus('shipped');
  await page.getByTestId('return-quantity').first().fill('2');
  await page.getByTestId('return-quantity').nth(1).fill('1');
  await page.getByTestId('submit-return').click();
  await waitStatus('returned');
  await page.getByTestId('nav-audit').click();
  await page.getByTestId('audit-table').getByText('order_returned').first().waitFor();
  await page.getByTestId('nav-inventory').click();
  await page.getByTestId('inventory-table').waitFor();
  await page.getByTestId('logout').click();
  await page.getByTestId('login-email').fill('viewer@south.example');
  await page.getByTestId('login-password').fill('DepotDemo!2026');
  await page.getByTestId('login-submit').click();
  await page.getByTestId('inventory-table').waitFor();
  await page.getByTestId('nav-orders').click();
  if(await page.getByTestId('new-order').count())throw Error('Viewer has create control');
  if(errors.length)throw Error('Page errors: '+errors.join('; '));
  console.log(JSON.stringify({result:'pass',viewport:`${width}x${height}`,workflow:'login, create two-line order, reserve, ship, full return, audit, inventory, logout, viewer controls',pageErrors:errors.length}));
 }finally{await context.close();await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
