#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}

"$PYTHON_BIN" --version
"$PYTHON_BIN" -m py_compile "$PROJECT_DIR/server.py"
"$PYTHON_BIN" -m compileall -q "$PROJECT_DIR/tests" "$PROJECT_DIR/load_test.py"
echo "DepotFlow is ready; it uses only the Python standard library."
