#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"
export PORT="${PORT:-8000}"
export DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"
exec "${PYTHON:-python3}" app.py
