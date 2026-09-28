#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "DepotFlow requires Python 3" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sqlite3
print(f"Python SQLite available: {sqlite3.sqlite_version}")
PY
echo "DepotFlow uses only the Python standard library; no dependency install is required."
