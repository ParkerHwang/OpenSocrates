#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
MERIDIAN_PYTHON="${MERIDIAN_PYTHON:-python3}"
mkdir -p verification
"$MERIDIAN_PYTHON" analysis/analyze.py > verification/analysis_run.log
"$MERIDIAN_PYTHON" analysis/build_workbook.py
"$MERIDIAN_PYTHON" analysis/build_documents.py
"$MERIDIAN_PYTHON" analysis/render_documents.py
"$MERIDIAN_PYTHON" analysis/verify.py > verification/verification_run.log
"$MERIDIAN_PYTHON" analysis/verify_formulas.py > verification/formula_verification_run.log
"$MERIDIAN_PYTHON" analysis/package.py
"$MERIDIAN_PYTHON" -c 'import json; from pathlib import Path; p=Path("verification"); a=json.loads((p/"verification_report.json").read_text()); b=json.loads((p/"formula_verification.json").read_text()); print("Reproduction complete:", a["status"], "independent/data checks;", b["status"], "formula evaluation;", a["pdfs"][0]["pages"], "report pages and", a["pdfs"][1]["pages"], "slides.")'
