#!/bin/sh
set -eu
cd "$(dirname "$0")"
python_bin="${PYTHON:-python3}"
"$python_bin" -c 'import sys, sqlite3; assert sys.version_info >= (3, 10), "Python 3.10+ is required"; print("Python", sys.version.split()[0], "· SQLite", sqlite3.sqlite_version, "· runtime ready (no external dependencies)")'
if [ "${1:-}" = "--browser" ]; then
  mkdir -p .test-data/npm-cache
  npm ci --ignore-scripts --cache "$PWD/.test-data/npm-cache"
  if [ -n "${EVAL_BROWSER_WS:-}" ]; then
    echo "Browser verification will use the supplied isolated Chromium connection."
  else
    PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" npx --no-install playwright install chromium
    echo "Run with PLAYWRIGHT_BROWSERS_PATH=\"\$PWD/.browsers\" python3 scripts/run_browser.py"
  fi
fi
