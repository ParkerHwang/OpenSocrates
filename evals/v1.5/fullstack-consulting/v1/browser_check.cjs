// Frozen neutral browser flow. Browser plugin not available; bundled Playwright.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const [url, output] = process.argv.slice(2);
fs.mkdirSync(output, {recursive:true});
(async () => {
  const browser = await chromium.launch({headless:true,executablePath:process.env.EVAL_CHROMIUM});
  const context = await browser.newContext({viewport:{width:1365,height:900}});
  const page = await context.newPage();
  const groups=[], consoleEvents=[], errors=[];
  page.on('console',m=>consoleEvents.push({type:m.type(),text:m.text()}));
  page.on('pageerror',e=>errors.push(String(e)));
  async function group(name, fn) {
    try { const detail=await fn();groups.push({name,pass:true,details:detail??null}); }
    catch(e){groups.push({name,pass:false,details:String(e)});}
    fs.writeFileSync(path.join(output,'browser-progress.json'),JSON.stringify({groups,consoleEvents,errors},null,2));
  }
  function control(id){return page.getByTestId(id);}
  async function click(id){if(!await control(id).count())throw Error(`Missing ${id}`);await control(id).click();}
  async function fill(id,value){if(!await control(id).count())throw Error(`Missing ${id}`);await control(id).fill(value);}
  async function login(role,tenant='north'){
    await fill('login-email',`${role}@${tenant}.example`);await fill('login-password','DepotDemo!2026');await click('login-submit');
    await control('nav-inventory').waitFor({state:'visible'});
  }
  await group('page_identity_and_login',async()=>{
    await page.goto(url,{waitUntil:'domcontentloaded'});
    if((await page.locator('body').innerText()).trim().length<20)throw Error('Blank page');
    await page.screenshot({path:path.join(output,'01-login.png'),fullPage:true});
    await login('admin');return {url:page.url(),title:await page.title()};
  });
  await group('inventory_rendered',async()=>{
    await click('nav-inventory');await control('inventory-table').waitFor({state:'visible'});
    const text=await control('inventory-table').innerText();for(const sku of ['BOLT','CABLE','SAMPLE'])if(!text.includes(sku))throw Error(`Absent ${sku}`);
    await page.screenshot({path:path.join(output,'02-inventory-desktop.png'),fullPage:true});return text;
  });
  await group('create_reserve_ship_return_flow',async()=>{
    await click('nav-orders');await click('new-order');await fill('order-client-ref','BROWSER-CHECK');
    await control('line-sku').first().selectOption('BOLT');await control('line-quantity').first().fill('2');
    await click('add-line');await control('line-sku').nth(1).selectOption('CABLE');await control('line-quantity').nth(1).fill('1');
    await click('submit-order');await control('order-detail').waitFor({state:'visible'});
    if(!(await control('order-detail').innerText()).includes('BROWSER-CHECK'))throw Error('Created order not shown');
    await click('reserve-order');await page.waitForFunction(()=>document.querySelector('[data-testid="order-detail"]')?.innerText.toLowerCase().includes('reserved'));
    await click('ship-order');await page.waitForFunction(()=>document.querySelector('[data-testid="order-detail"]')?.innerText.toLowerCase().includes('shipped'));
    await page.screenshot({path:path.join(output,'03-shipped.png'),fullPage:true});
    await control('return-quantity').nth(0).fill('2');await control('return-quantity').nth(1).fill('1');await click('submit-return');
    await page.waitForFunction(()=>document.querySelector('[data-testid="order-detail"]')?.innerText.toLowerCase().includes('returned'));
    return await control('order-detail').innerText();
  });
  await group('audit_rendered',async()=>{
    await click('nav-audit');await control('audit-table').waitFor({state:'visible'});const text=await control('audit-table').innerText();
    if(text.trim().length<20)throw Error('Empty audit');return text;
  });
  await group('mobile_layout',async()=>{
    await page.setViewportSize({width:390,height:844});await click('nav-inventory');
    await page.screenshot({path:path.join(output,'04-inventory-mobile.png'),fullPage:true});
    const size=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
    if(size.document>size.viewport+5)throw Error(JSON.stringify(size));return size;
  });
  await group('viewer_workflow_read_only',async()=>{
    await page.setViewportSize({width:1365,height:900});await click('logout');await login('viewer');await click('nav-orders');
    const n=control('new-order');if(await n.count()&&await n.isVisible()&&await n.isEnabled())throw Error('Viewer offered enabled new-order control');
    await page.screenshot({path:path.join(output,'05-viewer.png'),fullPage:true});
  });
  await group('no_uncaught_client_error',async()=>{if(errors.length)throw Error(JSON.stringify(errors));});
  const result={groups,passed:groups.filter(g=>g.pass).length,total:groups.length,consoleEvents,errors,automation:'bundled Playwright; fresh headless Chromium context; library native wait behavior',flow:'login -> inventory -> create multi-line order -> reserve -> ship -> return -> audit -> viewer'};
  fs.writeFileSync(path.join(output,'browser.json'),JSON.stringify(result,null,2));
  await browser.close();console.log(JSON.stringify(result));
})().catch(e=>{fs.writeFileSync(path.join(output,'browser-harness-error.json'),JSON.stringify({error:String(e)}));process.exitCode=1;});
