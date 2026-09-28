# Meridian Parts evidence pack

This project is reproducible from the saved source-room inputs in `evidence/raw/`.
The client source room is frozen; no live customer account or credentials were used.

## Rebuild

From the project root, run:

```bash
python3 analysis/analysis.py
python3 analysis/make_deliverables.py
```

The first command reads the raw CSV/JSON/ECB files, applies the data dictionary,
writes normalized tables to `analysis/outputs/`, creates `deliverables/metrics.json`,
updates `evidence/source-register-collected.json`, and builds the XLSX workbook.
The second command builds the PDF report and PPTX deck from those outputs.

## Key methods

- Order rows from both extracts and corrections are concatenated, exact duplicates
  are collapsed, and the highest numeric `revision` wins by `order_id`.
- Return exact duplicates are collapsed and the highest `revision` wins by
  `return_id`; distinct valid return IDs remain additive. Orphans and returns after
  2026-01-31 are visible in the quality audit and excluded from accounting.
- Eligible orders are shipped, non-test, with `shipped_at` in 2025. Zero-price
  shipments remain included. Order-level monetary components use Decimal
  half-up-cent rounding before aggregation.
- PLN/CZK conversion uses the arithmetic mean of available 2025 ECB business-day
  reference quotes in local currency per EUR for the original sale month; EUR=1.
- Returns are attributed to the original sale month for order-level accounting.
  This supports the requested original-sale-month FX rule but is not a cash-flow
  timing view.
- Hub scenarios follow `scenario-policy.md` exactly. Pairs add country figures
  without synergy; capex is year-zero and excluded from annual contribution.

## Outputs and checks

- `deliverables/meridian_parts_board_report.pdf`: executive consulting report.
- `deliverables/meridian_parts_board_presentation.pptx`: board deck.
- `deliverables/meridian_parts_analysis.xlsx`: filterable analysis workbook,
  charts, source/quality notes, scenarios and audit tables.
- `deliverables/metrics.json`: deterministic exchange schema requested in TASK.md.
- `analysis/outputs/`: normalized order calculations, monthly/country totals, FX,
  market context, hub options/scenarios and quality audit.
- `evidence/source-register-collected.json`: local SHA-256 hashes, source URLs,
  retrieval time, periods, units and synthetic/public status.

The analysis run checks that monthly and country contribution totals reconcile. A
verification pass also confirmed 72 monthly rows, 6 country totals, 36 monthly FX
rows, 18 market-context rows, 24 hub scenario rows, one workbook decision chart,
7-page PDF text extraction, and 8 PPTX slides. Known limitations remain visible
in the report and quality audit: synthetic demand inputs, no causal/DCF model,
no customer interviews, one quarantined orphan return, one post-cutoff return,
and ECB reference rates as analytical rather than transaction FX.
