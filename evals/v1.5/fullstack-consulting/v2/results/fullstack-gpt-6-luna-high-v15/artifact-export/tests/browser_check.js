const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),net=require('net');
function port(){return new Promise((resolve,reject)=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p))});s.on('error',reject)})}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const p=await port(),data=fs.mkdtempSync(path.join(__dirname,'browser-data-'));
 const child=spawn(path.resolve(__dirname,'../run.sh'),[],{env:{...process.env,PORT:String(p),DATA_DIR:data,SEED_DEMO:'1'},stdio:'ignore'});
 let browser,context;
 try{
  let ready=false;for(let i=0;i<100;i++){try{const r=await fetch(`http://127.0.0.1:${p}/api/health`);if(r.ok){ready=true;break}}catch{}await wait(30)}if(!ready)throw Error('server did not become ready');
  browser=await chromium.connect(process.env.EVAL_BROWSER_WS);context=await browser.newContext({viewport:{width:1280,height:850}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${p}/`);await page.getByTestId('login-email').fill('operator@north.example');await page.getByTestId('login-password').fill('DepotDemo!2026');await page.getByTestId('login-submit').click();await page.getByTestId('inventory-table').waitFor();
  await page.getByTestId('nav-orders').click();await page.getByTestId('new-order').click();await page.getByTestId('order-client-ref').fill('browser-flow-1');await page.getByTestId('line-sku').selectOption('BOLT');await page.getByTestId('line-quantity').fill('2');await page.getByTestId('submit-order').click();await page.getByTestId('order-detail').waitFor();
  if(!(await page.getByTestId('order-detail').innerText()).includes('browser-flow-1'))throw Error('order detail did not show client reference');
  await page.getByTestId('reserve-order').click();await page.getByTestId('ship-order').waitFor();await page.getByTestId('ship-order').click();await page.getByTestId('submit-return').waitFor();
  const token=await page.evaluate(()=>sessionStorage.token),orders=await (await fetch(`http://127.0.0.1:${p}/api/orders?q=browser-flow-1`,{headers:{Authorization:'Bearer '+token}})).json(),order=orders.items[0];
  await fetch(`http://127.0.0.1:${p}/api/orders/${order.id}/returns`,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','Idempotency-Key':'external-stale-check'},body:JSON.stringify({expected_version:order.version,lines:[{sku:'BOLT',quantity:1}]})});
  await page.getByTestId('return-quantity').fill('1');await page.getByTestId('submit-return').click();await page.getByText(/This order is stale/).waitFor();if(await page.getByTestId('return-quantity').inputValue()!=='1')throw Error('stale return input was not retained');
  await page.getByText('Refresh order').click();await page.getByTestId('order-detail').waitFor();if(await page.getByTestId('return-quantity').inputValue()!=='1')throw Error('return input was lost on refresh');await page.getByTestId('submit-return').click();await page.getByText('Status: returned').waitFor();
  await page.getByTestId('nav-audit').click();await page.getByTestId('audit-table').waitFor();
  await page.setViewportSize({width:390,height:844});await page.getByTestId('nav-orders').click();if(await page.locator('body').evaluate(e=>e.scrollWidth>window.innerWidth+2))throw Error('mobile viewport has horizontal page overflow');
  await page.getByTestId('logout').click();await page.getByTestId('login-submit').waitFor();await page.getByTestId('login-email').fill('viewer@north.example');await page.getByTestId('login-password').fill('DepotDemo!2026');await page.getByTestId('login-submit').click();await page.getByTestId('nav-orders').click();if(await page.getByTestId('new-order').count())throw Error('viewer was offered create order');
  if(errors.length)throw Error('browser errors: '+errors.join('; '));
  console.log(JSON.stringify({result:'passed',workflow:['login','inventory','create','reserve','ship','stale-version message and retained return input','partial return','full return','audit','mobile viewport','viewer read-only UI'],browserErrors:errors}));
 }finally{if(context)await context.close();if(browser)await browser.close();child.kill('SIGTERM');await new Promise(r=>child.once('exit',r));fs.rmSync(data,{recursive:true,force:true})}
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1});
