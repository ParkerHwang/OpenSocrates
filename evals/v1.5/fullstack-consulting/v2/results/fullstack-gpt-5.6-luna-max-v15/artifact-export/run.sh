#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "DepotFlow requires Python 3" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/app.py"
