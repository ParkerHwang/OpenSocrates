# Meridian Parts analysis: reproduce and verify

All source inputs used by the analysis are retained in `sources/raw/`. Rebuilds do not need network access. `sources/source-register.json` records the saved file hashes, byte counts, URLs, units, periods, status and retrieval vintage. The frozen World Bank and ECB files are public snapshots; transaction, unit-cost and hub-option files are synthetic case inputs.

## Environment

Use Python 3.10 or later with `pandas`, `openpyxl`, `python-docx`, `python-pptx` and `reportlab`. The supplied environment has these libraries installed. No additional dependency is required for the build. I rendered the PDFs for visual inspection with a temporary PyMuPDF install, then removed that review-only dependency and its preview images; it is not used by the build scripts.

## Rebuild

Run these commands from the project directory:

```sh
python3 analysis/build.py
python3 analysis/render_pdfs.py
python3 analysis/verify.py
```

`build.py` reads the preserved files and produces the metrics JSON, XLSX workbook, DOCX report and PPTX deck. `render_pdfs.py` produces PDF editions of the report and deck. `verify.py` checks the required JSON arrays, all 72 monthly-to-country reconciliations, margins, scenario/payback bounds, recommendation rank, saved-source hashes, workbook-to-JSON values, workbook chart, and office/PDF file structure.

## Key calculation choices

- Keep the highest numeric order revision across both order extracts and the correction file; identical rows are deduplicated. Keep the highest return revision by `return_id`.
- Include only non-test shipped orders with `shipped_at` in calendar 2025. Include zero-price shipments. Include return credits received through and including 2026-01-31 only when linked to an eligible selected order; quarantine orphans.
- Translate local gross sales and refunds with the original sale month’s arithmetic mean of published ECB business-day reference rates, local currency units per EUR. Use EUR = 1.
- Round order-level gross sales, refunds, gross COGS, recovered COGS and fulfillment to EUR cents with decimal half-up rounding before aggregation. Net COGS deducts recovered cost only for restocked quantity.
- Build every country-month cell, then reconcile annual country totals from those rows. Margin is annual contribution divided by annual net sales, and is null when net sales are zero.
- Apply the exact low/base/high/stress equations in `sources/raw/scenario-policy.md`. Recurring cost is in annual contribution; capex remains year-zero. Pairs are additive without synergy.
- The recommendation uses the feasible alternative with the highest minimum annual increment across the supplied low/base/high/stress cases. This is a conservative ranking choice because the board supplied no probabilities or preference weights. The strongest different alternative is compared by base contribution. Neither ranking is causal or statistically proven.

## Outputs

- `deliverables/meridian_board_brief.pdf` and `.docx`
- `deliverables/meridian_board_deck.pdf` and `.pptx`
- `deliverables/meridian_analysis.xlsx`
- `deliverables/metrics.json`
- `sources/raw/` and `sources/source-register.json`

`TASK.md` and `TOOLING.md` are retained unchanged.
