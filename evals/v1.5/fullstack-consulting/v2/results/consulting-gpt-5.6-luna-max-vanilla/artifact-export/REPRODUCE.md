# Meridian Parts deliverables

This project is reproducible from the preserved files under `evidence/raw/`.
The source room was a frozen local source room; client exports and policy inputs
are synthetic, while the ECB and World Bank files are archived official public
snapshots. No live customer account, credentials, interviews or private data were
used.

## Rebuild

Use the bundled Python from `TOOLING.md` (it already contains pandas, openpyxl,
python-pptx, reportlab and pypdf):

```bash
PYBIN=<SHARED_RUNTIME>/python/bin/python3
$PYBIN scripts/analyze.py
$PYBIN scripts/create_deliverables.py
$PYBIN scripts/verify_outputs.py
```

`analyze.py` reads only `evidence/raw/` and writes:

- `analysis/processed/` — order-level, monthly, country, FX, market and scenario tables;
- `evidence/source-register.json` and `.csv` — URL, retrieval time, SHA-256, bytes, units, period, status and provenance;
- `deliverables/metrics.json` — the requested deterministic arrays and quality notes.

`create_deliverables.py` reads the saved processed tables and metrics to create:

- `deliverables/meridian_parts_executive_report.pdf`;
- `deliverables/meridian_parts_board_presentation.pptx`;
- `deliverables/meridian_parts_analytical_workbook.xlsx`.

`verify_outputs.py` checks the metrics schema and counts, monthly-to-country
reconciliation, source hashes, ECB month coverage, scenario formula spot checks,
recommendation values, workbook sheets/charts, PDF text and deck slide content.

## Accounting and scenario notes

The script follows `evidence/raw/data-dictionary.md`: highest revision per
`order_id`/`return_id`, exact-repeat removal, eligibility filters, inclusive
return cutoff, orphan quarantine, sale-month ECB means, effective-dated unit
costs, order-level half-up cent rounding and additive return IDs. It retains
valid zero-price shipments. The stress case follows
`evidence/raw/scenario-policy.md`; capex is year-zero and excluded from annual
incremental contribution.

The recommendation is a transparent risk-adjusted rule: feasible pairs must be
positive in low/base/high/stress and are ranked first by defined-stress
incremental contribution, then by base contribution. It is not a statistical,
causal or certain demand forecast.

## Deliverable map

| Path | Purpose |
| --- | --- |
| `deliverables/metrics.json` | Machine-readable requested metrics and quality log |
| `deliverables/meridian_parts_executive_report.pdf` | Board-ready consulting report |
| `deliverables/meridian_parts_board_presentation.pptx` | Ten-slide board presentation |
| `deliverables/meridian_parts_analytical_workbook.xlsx` | Filterable analysis, source and decision workbook |
| `evidence/raw/` | Downloaded frozen source-room evidence |
| `evidence/source-register.json` | Provenance and hash register |
| `scripts/analyze.py` | Source processing and calculations |
| `scripts/create_deliverables.py` | Report, deck and workbook generation |
| `scripts/verify_outputs.py` | Reproducibility and artifact checks |
