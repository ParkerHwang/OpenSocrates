# Meridian Parts European hub analysis

This project analyzes the frozen synthetic client package saved under `evidence/source-room/`. The calculation is reproducible from those local inputs; the source-room server and internet access are not needed after collection.

## Rebuild

Use Python 3.10+ and install the report/workbook dependencies in a local virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/analyze.py
python scripts/build_deliverables.py
```

The first script selects revisions, applies eligibility and return rules, converts at the archived ECB rate means, and writes `analysis/metrics.json`, `analysis/order_ledger.json`, and `analysis/reconciliation.json`. It uses Python’s standard library. The second script checks the archived public-source hashes against the source-room register and builds the board materials, source register, workbook, and processed audit extracts.

Optional QA tools are listed in `requirements-qa.txt`:

```sh
python -m pip install -r requirements-qa.txt
python scripts/verify_deliverables.py
python scripts/render_checks.py
```

The render script writes PDF contact sheets to `analysis/render_checks/` for visual review.

## Key outputs

- `deliverables/meridian_executive_report.pdf` — consulting recommendation, diagnosis, scenarios, limitations, implementation gates, and source links.
- `deliverables/meridian_board_presentation.pdf` — six-page board presentation, consistent with the report and workbook.
- `deliverables/Meridian_Analysis.xlsx` — country/month results, FX means, archived market context, source and quality notes, order audit, scenarios, comparisons, and charts.
- `deliverables/metrics.json` — exchange format with monthly, country, FX, market-context, option/pair scenario, recommendation, and quality arrays/objects.
- `deliverables/source_register.csv` and `.json` — local collection timestamp, original/archive retrieval time where provided, URL, SHA-256, units, period, synthetic/public classification, and vintage.
- `deliverables/verification.json` — saved results of arithmetic, schema, archive-hash, workbook-structure, and PDF-page checks.
- `evidence/source-room/` — unchanged raw downloads from the frozen source room, including original archives and its source register.
- `evidence/processed/` — order-level EUR audit, every latest-row order exclusion with its reason, derived monthly/country/FX/market/scenario CSVs, and return exceptions.

## Calculation decisions

The highest numeric order revision is selected across both extracts and the correction file before filtering to non-test shipped records with a 2025 ship date. Exact repeated rows count once. Return revisions are selected before applying the inclusive 2026-01-31 cutoff and linking to eligible orders; orphan returns are quarantined. Free shipments remain orders and units. Gross and summed refunds use the original sale-month arithmetic mean of ECB daily reference quotes (local units per EUR); EUR is 1. Components are rounded per order to cents using `ROUND_HALF_UP`. Net COGS credits only returned units explicitly marked restocked.

Scenario inputs and formulas are in the synthetic `scenario-policy.md` and `hub-options.csv`. Annual incremental contribution is separate from year-zero capex; simple payback is shown only for positive annual incremental contribution. Pairs sum their country assumptions with no synergy. GDP per capita is current USD and population is national context, not proof of product demand. Archived source vintage and limitations are documented in the report and source register.
