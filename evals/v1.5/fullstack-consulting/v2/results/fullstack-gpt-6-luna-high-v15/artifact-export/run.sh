#!/bin/sh
set -eu
cd "$(dirname "$0")"
export PORT="${PORT:-8000}"
export DATA_DIR="${DATA_DIR:-$PWD/data}"
export SEED_DEMO="${SEED_DEMO:-0}"
exec python3 app.py
