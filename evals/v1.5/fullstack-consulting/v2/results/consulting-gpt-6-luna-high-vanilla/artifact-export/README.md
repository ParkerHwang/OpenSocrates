# Meridian Parts analysis pack

## Reproduce

The workspace includes the frozen source-room capture under `evidence/raw/`.
Python 3 with pandas, openpyxl, python-docx, reportlab, python-pptx and
matplotlib is required. The supplied environment included the document and
spreadsheet libraries; matplotlib was installed locally in `.deps/`. PyMuPDF
was also installed locally for PDF render inspection.

From the workspace root:

```sh
PYTHONPATH=.deps python3 scripts/analyze.py
python3 scripts/make_docs.py
```

`analyze.py` resolves revisions and eligibility, converts order amounts, creates
monthly and country metrics, rates, market context, option scenarios, workbook,
charts, metrics JSON and source register. `make_docs.py` reads those outputs to
create the report and presentation. Raw files are preserved; neither script
contacts the source room or refreshes public data. To install the one locally
added package in a fresh environment, run `python3 -m pip install --target .deps
matplotlib` (network access required).

## Artifact map

- `deliverables/board_report.pdf` and `.docx`: executive consulting report.
- `deliverables/board_deck.pdf` and `.pptx`: six-slide board presentation.
- `deliverables/meridian_analysis.xlsx`: source notes, monthly/country metrics,
  monthly FX, World Bank context and comparison, hub scenarios and feasible portfolios with
  decision charts.
- `deliverables/metrics.json`: deterministic machine-readable metric arrays,
  recommendation and anomaly notes.
- `evidence/raw/`: all captured input files, including original ECB ZIP and
  extracted CSV, archive register, client exports, corrections and policy.
- `evidence/source-register.csv`: URL, retrieval time, SHA-256, bytes, units,
  period and synthetic/public classification for each saved source file.
- `scripts/`: calculation and document-generation source.

## Scope and assumptions

The source room is frozen and its client data are synthetic. World Bank and ECB
records are official public archives captured in the room; World Bank files
report `lastupdated` 2026-07-13 and the room retrieval vintage is 2026-09-27.
No customer interviews or live customer account were accessed. See the report,
workbook Read me sheet, metrics quality block, and source files for accounting,
anomaly treatment, scenario policy and limitations.
