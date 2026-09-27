const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

async function renderDocument(browser, source, selector, pdfPath, previewDir, prefix, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 2 });
  const page = await context.newPage();
  const html = fs.readFileSync(source, 'utf8');
  await page.setContent(html, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const count = await page.locator(selector).count();
  const dimensions = await page.locator(selector).evaluateAll(nodes => nodes.map(n => {
    const r = n.getBoundingClientRect();
    return { width: Math.round(r.width), height: Math.round(r.height), scrollHeight: n.scrollHeight, clientHeight: n.clientHeight };
  }));
  fs.mkdirSync(previewDir, { recursive: true });
  for (let i = 0; i < count; i++) {
    const locator = page.locator(selector).nth(i);
    await locator.screenshot({ path: path.join(previewDir, `${prefix}-${String(i + 1).padStart(2, '0')}.png`), scale: 'device' });
  }
  await page.emulateMedia({ media: 'print' });
  const cdp = await context.newCDPSession(page);
  const result = await cdp.send('Page.printToPDF', { printBackground: true, preferCSSPageSize: true, transferMode: 'ReturnAsBase64' });
  const pdf = Buffer.from(result.data, 'base64');
  fs.writeFileSync(pdfPath, pdf);
  await context.close();
  return { source, pdf: pdfPath, pages: count, dimensions, bytes: pdf.length };
}

(async () => {
  if (!process.env.EVAL_BROWSER_WS) throw new Error('EVAL_BROWSER_WS is not set');
  const browser = await chromium.connect(process.env.EVAL_BROWSER_WS);
  try {
    const root = path.resolve(__dirname, '..');
    const results = [];
    results.push(await renderDocument(
      browser,
      path.join(root, 'deliverables', 'executive_report.html'),
      '.page',
      path.join(root, 'deliverables', 'executive_report.pdf'),
      path.join(root, 'deliverables', 'previews', 'report'),
      'report',
      { width: 1280, height: 900 }
    ));
    results.push(await renderDocument(
      browser,
      path.join(root, 'deliverables', 'board_presentation.html'),
      '.slide',
      path.join(root, 'deliverables', 'board_presentation.pdf'),
      path.join(root, 'deliverables', 'previews', 'deck'),
      'slide',
      { width: 1400, height: 900 }
    ));
    process.stdout.write(JSON.stringify(results, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
