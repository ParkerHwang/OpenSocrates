#!/bin/sh
# Optional browser-test tooling only. The application itself has no npm dependencies.
set -eu
cd "$(dirname "$0")"
mkdir -p .local
export npm_config_cache="$PWD/.local/npm-cache"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$PWD/.local/browsers}"
if ! node -e 'require("playwright")' >/dev/null 2>&1; then
  npm install --ignore-scripts --no-audit --no-fund
fi
if [ -z "${EVAL_BROWSER_WS:-}" ]; then
  browser_cli=$(node -p 'require("node:path").join(require("node:path").dirname(require.resolve("playwright/package.json")), "cli.js")')
  node "$browser_cli" install chromium
fi
printf '%s\n' 'Browser tooling ready. Run: PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers" node scripts/browser.cjs'
