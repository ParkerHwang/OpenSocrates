// Browser-only preview of cached XLSX values. Uses the isolated supplied browser.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const root = path.resolve(__dirname, '..');
  const target = path.join(root, 'deliverables', 'verification');
  const browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
  const context = await browser.newContext({ viewport: { width: 1600, height: 1050 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  try {
    await page.setContent(fs.readFileSync(path.join(target,'workbook_preview.html'),'utf8'), { waitUntil:'load' });
    for (const name of ['Decision','Countries','Monthly','Inputs','Scenarios','Portfolios','Quality','Sources']) {
      await page.getByRole('button', {name, exact:true}).click();
      await page.screenshot({path:path.join(target, 'workbook-'+name.toLowerCase()+'.png'),fullPage:true});
    }
    const counts = await page.locator('section').count();
    const result = {status:errors.length===0?'passed':'failed',panels:counts,screenshots:8,page_errors:errors,native_excel_render:false};
    fs.writeFileSync(path.join(target,'browser_check.json'), JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
    if(errors.length)process.exitCode=1;
  } finally { await context.close(); await browser.close(); }
})();
