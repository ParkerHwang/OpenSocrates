#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m py_compile "$SCRIPT_DIR/server.py"
echo "DepotFlow is dependency-free; setup check passed. Start with ./run.sh."
