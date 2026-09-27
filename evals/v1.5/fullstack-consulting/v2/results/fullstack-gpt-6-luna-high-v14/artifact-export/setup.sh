#!/bin/sh
set -eu
# DepotFlow uses only Python's standard library and SQLite; setup is intentionally local and empty.
python3 --version
python3 -c 'import sqlite3; print("SQLite", sqlite3.sqlite_version)'
