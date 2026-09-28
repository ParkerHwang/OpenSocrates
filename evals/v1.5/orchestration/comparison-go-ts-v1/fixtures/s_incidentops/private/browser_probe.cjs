const path = require('path');
const {chromium} = require(path.join(process.env.OPENSOCRATES_EVAL_DEPS, 'npm/node_modules/playwright'));

(async () => {
  const base = process.env.EVAL_BASE_URL;
  const candidate = process.env.EVAL_CANDIDATE;
  const browser = await chromium.connectOverCDP(process.env.EVAL_CDP_URL);
  const context = await browser.newContext({viewport:{width:1100,height:800}});
  const page = await context.newPage();
  let posted = 0, filtered = 0, navigations = 0;
  const networkFailures = [];
  page.on('framenavigated', frame => { if(frame === page.mainFrame()) navigations++; });
  page.on('requestfailed', request => { if(request.url().startsWith(base)) networkFailures.push({path:new URL(request.url()).pathname,error:request.failure()?.errorText || 'unknown'}); });
  page.on('response', response => {
    const url = response.url();
    if(url.includes('/api/events') && response.request().method() === 'POST' && response.status() === 201) posted++;
    if(url.includes('/api/incidents?') && url.includes('severity=P1') && response.status() === 200) filtered++;
  });
  try {
    await page.goto(base, {waitUntil:'networkidle'});
    const summary = page.getByRole('heading',{name:/^Summary$/i}).locator('..');
    const search = page.getByLabel('Search',{exact:true});
    await search.fill('browser-');
    await search.dispatchEvent('change');
    await page.waitForFunction(() => document.body.innerText.includes('browser-alpha') && document.body.innerText.includes('browser-beta'));
    if(!/\b2\b/.test(await summary.innerText())) throw new Error('filtered summary missing total');
    await page.getByLabel('Severity').selectOption('P1');
    await page.waitForFunction(() => document.body.innerText.includes('browser-alpha') && !document.body.innerText.includes('browser-beta'));
    if(!/\b1\b/.test(await summary.innerText()) || filtered < 1) throw new Error('filter did not refresh actual network results');
    await page.getByLabel('Role').selectOption('viewer');
    const viewerAction = page.getByRole('button',{name:/^ACK$/i});
    if(await viewerAction.count() && !(await viewerAction.first().isDisabled())) throw new Error('viewer write control enabled');
    await page.getByLabel('Role').selectOption('operator');
    const operatorAction = page.getByRole('button',{name:/^ACK$/i});
    await operatorAction.waitFor({state:'visible'});
    const before = navigations;
    const marker = `eval-${Date.now()}`;
    await page.evaluate(value => { window.__evalDocumentMarker = value; }, marker);
    const actionResponse = page.waitForResponse(response => response.url().includes('/api/events') && response.request().method() === 'POST');
    await operatorAction.click();
    const accepted = (await actionResponse).status() === 201;
    await page.waitForFunction(() => document.body.innerText.includes('browser-alpha') && document.body.innerText.includes('acknowledged'));
    const sameDocument = await page.evaluate(value => window.__evalDocumentMarker === value, marker);
    if(!accepted || !sameDocument) throw new Error(`action/reload accepted=${accepted} same_document=${sameDocument}`);
    await page.setViewportSize({width:390,height:780});
    const width = await page.evaluate(() => ({scroll:document.documentElement.scrollWidth,inner:window.innerWidth}));
    if(width.scroll > width.inner + 2) throw new Error('mobile horizontal overflow');
    process.stdout.write(JSON.stringify({passed:true,network_posts:posted,filtered_responses:filtered,same_document:sameDocument,navigations_after_action:navigations-before,mobile_width:width}));
  } catch (error) {
    try { await page.screenshot({path:path.join(candidate,'.eval-browser-failure.png')}); } catch (_) {}
    process.stdout.write(JSON.stringify({passed:false,error:String(error).slice(0,180),network_posts:posted,filtered_responses:filtered,network_failures:networkFailures.slice(0,8)}));
    process.exitCode = 1;
  } finally { await browser.close(); }
})().catch(error => { process.stdout.write(JSON.stringify({passed:false,error:String(error).slice(0,180)})); process.exitCode = 1; });
