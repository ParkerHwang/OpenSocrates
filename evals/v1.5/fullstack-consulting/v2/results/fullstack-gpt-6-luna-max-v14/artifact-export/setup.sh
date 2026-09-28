#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${PYTHON:-python3}
"$PYTHON_BIN" -c 'import sqlite3, sys; print("Python", sys.version.split()[0], "· SQLite", sqlite3.sqlite_version)'
"$PYTHON_BIN" -m py_compile "$PROJECT_DIR/app.py"
printf '%s\n' 'DepotFlow is ready. No third-party packages are required.'
