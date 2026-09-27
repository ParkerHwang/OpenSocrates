#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PORT="${PORT:-8080}"
export DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"
export SEED_DEMO="${SEED_DEMO:-0}"
exec python3 "$PROJECT_DIR/server.py"
