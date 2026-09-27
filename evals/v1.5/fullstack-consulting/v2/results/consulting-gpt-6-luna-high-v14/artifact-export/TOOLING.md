# Available environment

Python: <SHARED_RUNTIME>/python/bin/python3
Node: <SHARED_RUNTIME>/node/bin/node
Shared Node packages: <SHARED_RUNTIME>/node/node_modules
Go: /usr/local/go/bin/go
System shell, curl, git and local toolchains are available. Choose your own programming language/stack. Public network/dependency downloads are enabled. Install dependencies only within this disposable workspace/profile.
Bundled Python has pandas, openpyxl, python-docx, python-pptx, reportlab and PDF/image tools. Bundled Node has Playwright; NODE_PATH and PLAYWRIGHT_BROWSERS_PATH are set. Use headless Chromium for local browser verification.

A fresh isolated Chromium tool is already running for this cell. Connect using Playwright: const {chromium}=require('playwright'); const browser=await chromium.connect(process.env.EVAL_BROWSER_WS); const context=await browser.newContext(); const page=await context.newPage(); Close your context and browser connection when done. Do not call chromium.launch() inside the Codex shell: macOS shell IPC blocks browser startup. This WebSocket tool has its own filesystem isolation and no existing browsing profile.

Source room: http://127.0.0.1:49789/
Collect from its index and preserve source provenance. Public research is also available.
