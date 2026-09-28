#!/bin/sh
set -eu
python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("DepotFlow requires Python 3.10 or newer.")
print(f"Python {sys.version.split()[0]} is ready; DepotFlow uses only the standard library.")
PY
