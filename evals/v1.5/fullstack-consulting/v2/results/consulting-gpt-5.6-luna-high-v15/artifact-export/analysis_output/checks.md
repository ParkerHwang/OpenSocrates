# Verification record

Run after the final build on 2026-09-27 (Asia/Seoul; build timestamp 2026-09-27T08:45:59Z).

- `python3 scripts/build_deliverables.py` completed and produced the PDF, PPTX, XLSX, `metrics.json`, and source register.
- `python3 scripts/verify_outputs.py` passed: required JSON schema; 72 monthly rows; monthly-to-country reconciliation; margin convention; scenario capex/FTE limits; positive-only payback; workbook sheet/table structure; PDF text checks; PPTX ZIP integrity and content checks.
- PDF rendering: PyMuPDF rendered all 3 pages to PNG under `analysis_output/report_page_1.png` through `report_page_3.png`; visual inspection found the tables legible after wrapping the 90-day plan table.
- Workbook read-back: `openpyxl` loaded the workbook and confirmed native tables on monthly, country, FX, market, scenario and source-register sheets.
- Presentation package read-back: `unzip -t` reported no errors; slide XML contains the recommendation, 90-day gate, World Bank and ECB references.

Material limitation: a native office renderer was not available in the environment, so the PPTX was checked structurally and by extracted slide XML rather than by a rendered slide image. The PDF was rasterized and visually inspected.
