#!/bin/sh
set -eu
cd "$(dirname "$0")"
export DATA_DIR="${DATA_DIR:-$PWD/data}"
export PORT="${PORT:-8000}"
exec "${PYTHON:-python3}" -m depotflow.server
