# Meridian Parts deliverables

This disposable project contains the frozen source-room inputs, reproducible analysis, and board materials for the European service-hub decision.

## Reproduce

The source room was collected into `evidence/raw/`. Run from the project root:

```bash
python3 scripts/build_deliverables.py
python3 scripts/verify_outputs.py
```

`build_deliverables.py` reads only the saved files under `evidence/raw/`. It writes `deliverables/metrics.json`, the Excel workbook, PDF report, PPTX presentation, `deliverables/source-register.csv`, and `analysis_output/build_summary.json`. It also refreshes `evidence/source-register.csv` with file hashes and provenance metadata.

## Calculation boundary

- 2025 shipped orders only, with returns received through and including 2026-01-31.
- Exact repeated rows are collapsed; highest numeric revision wins for each `order_id` and `return_id`.
- Cancellations, tests, future shipments, orphan returns, and post-cutoff returns are excluded as documented in `metrics.json` and the workbook Quality sheet.
- PLN/CZK are converted using the original sale month’s mean ECB business-day quote in local currency units per EUR. EUR is 1.
- Monetary components are rounded per order to cents using half-up rounding before aggregation.
- Hub scenarios follow the saved synthetic `scenario-policy.md`; capex is year-zero and excluded from annual contribution, and pairs have no synergy.

## Deliverables

- `deliverables/meridian_parts_board_report.pdf` — executive consulting report.
- `deliverables/meridian_parts_board_presentation.pptx` — board presentation.
- `deliverables/meridian_parts_analysis.xlsx` — workbook with notes, quality controls, monthly/country results, FX, market context, scenarios, source register, and native Excel charts.
- `deliverables/metrics.json` — deterministic exchange schema requested in the task.
- `evidence/raw/` — downloaded source-room files; `deliverables/source-register.csv` records URLs, retrieval timestamps, hashes, units, periods and public/synthetic status.

## Limits

Client extracts and hub assumptions are synthetic. World Bank and ECB data are archived public snapshots with the recorded vintage; no live client account, customer interviews, actual transaction FX, labor quotes, causal hub test, or full discounted cash-flow model was available. The recommendation is a planning judgment with explicit gates, not a statistically proven or certain forecast.
