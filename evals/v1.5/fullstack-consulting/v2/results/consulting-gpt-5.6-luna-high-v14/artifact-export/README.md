# Meridian Parts — European service-hub expansion

This workspace contains the reproducible analysis and board deliverables for the synthetic Meridian Parts client.

## Reproduce

The frozen source-room files are preserved in `evidence/source_room/`. The analysis does not require live client access or live public pulls. Run:

```bash
PYTHONPATH=.deps <SHARED_RUNTIME>/python/bin/python3 scripts/build_analysis.py
PYTHONPATH=.deps <SHARED_RUNTIME>/python/bin/python3 scripts/verify_outputs.py
```

`matplotlib` is installed only in the workspace-local `.deps/` directory for chart generation; the supplied runtime provides pandas, openpyxl, python-pptx, reportlab and PDF inspection libraries.

## Outputs

- `deliverables/meridian_parts_board_report.pdf` — executive consulting report.
- `deliverables/meridian_parts_board_presentation.pptx` — board presentation.
- `deliverables/meridian_parts_analysis.xlsx` — analytical workbook with source/quality notes, reconciled order and return tabs, monthly/country results, market context, FX, scenario detail and decision charts.
- `deliverables/metrics.json` — deterministic exchange structure requested in `TASK.md`.
- `evidence/source_register.json` — source register with original URL, retrieval vintage/time, local path, hash, units, period and synthetic/public status.
- `analysis/` — reconciled inputs, calculation outputs and run manifest.

## Scope and method notes

The pipeline selects the highest numeric revision per order/return ID, removes identical repeats, keeps valid zero-price shipments, excludes cancelled/test/non-2025 shipments, quarantines orphan returns, applies the inclusive 2026-01-31 return cutoff, uses the original sale month’s ECB mean business-day quote for both sales and refunds, rounds monetary components per order half-up to cents, and reconciles country totals to monthly rows. The scenario policy is applied exactly as supplied, with capex separated from recurring annual contribution.

Synthetic client inputs, archived official World Bank/ECB snapshots, assumptions, computed values and limitations are labelled in the workbook and report. No customer interviews or live account access were used.
