# Meridian Parts board decision package

This package recommends a **staged Spain (ESP) then Czechia (CZE) service-hub program**, with Spain launched first and Czechia's €95,000 capex released only after a day-90 gate. The two-hub base case adds €198,099.31 of annual contribution after recurring fixed costs on €225,000 of year-zero capex and five FTE. Under the specified joint refund/FX stress, the pair adds only €32,179.71 a year; Spain alone adds €70,006.66, while Netherlands plus Spain leads the stress case at €107,630.13. These are scenario outputs from synthetic client inputs, not causal estimates or forecasts.

## Deliverables and evidence

- `deliverables/executive_report.pdf` — four-page board report with diagnosis, recommendation, alternatives, risks, 90-day plan and source references.
- `deliverables/board_presentation.pdf` — six-slide board presentation.
- `deliverables/meridian_analysis.xlsx` — ten-tab analytical workbook with monthly and annual economics, FX and market context, all feasible scenarios, two decision charts, source register and quality log.
- `deliverables/metrics.json` — deterministic machine-readable metrics; `monthly.csv`, `countries.csv`, `hub_scenarios.csv` and `order_audit.csv` expose the calculations.
- `deliverables/verification.json` — actual automated checks and material limitations.
- `evidence/raw/` — unchanged files downloaded from the frozen source room at `http://127.0.0.1:49684/`, including both order extract pages, corrections, returns, options and the archived official series. `evidence/source_register.csv` and `.json` give each file's room URL, collection timestamp, SHA-256, units, period, synthetic/public status, and any original public URL and archive retrieval time.

The public World Bank and ECB series were **collected from the frozen source room**, not refreshed live. The room's public archive was retrieved on 2026-09-27 and preserves original endpoint URLs and hashes in `evidence/raw/source-register.json`. Its World Bank responses say `lastupdated: 2026-07-13`; they can include later revisions to 2022–2024 values. Client extracts, hub options and scenario policy are entirely synthetic. No customer interview or live client account was used.

## Reproduce

From this directory, use Python 3.12+ with `xlsxwriter`, `reportlab`, `openpyxl` and `pypdf` (the supplied bundled Python already has them):

```sh
<SHARED_RUNTIME>/python/bin/python3 scripts/analyze.py
<SHARED_RUNTIME>/python/bin/python3 scripts/render.py
<SHARED_RUNTIME>/python/bin/python3 scripts/verify.py
```

On another machine, run the same scripts with an environment containing the versions recorded in `requirements.txt`. `analyze.py` uses only Python's standard library. All scripts read saved local inputs; reproduction does not require the source room or public internet. Re-running `render.py` updates its `room_collected_utc` field from saved file modification times; the archived public retrieval time and file hashes remain fixed.

## Calculation contract

Orders are selected by highest numeric revision of each `order_id` across `orders-part1.csv`, `orders-part2.csv` and `order-corrections.csv`. Identical repeat rows collapse to one. Corrections replace the whole order row. Only non-test orders with `status=shipped` and a 2025 shipment date are included; valid zero-price shipments still count. Returns are selected by highest `return_id` revision, included only if received through 2026-01-31 inclusive and linked to an eligible order. Orphans and later returns are quarantined. Multiple distinct return IDs on an order are additive.

For each eligible shipment, gross local sales are `quantity × unit_price_local − discount_local`. Gross sales and the sum of linked local refunds are each divided by the **original shipment month's arithmetic mean ECB business-day quote**, local currency units per EUR (EUR = 1). The effective unit cost is the most recent cost on or before shipment. Net COGS equal gross COGS less cost recovered only on `restocked_quantity`. Gross sales, summed refunds, gross COGS, recovered COGS and fulfillment are rounded separately **per order** to EUR cents using half-up rounding; monthly and country figures sum those per-order values. Returns are attributed to the original sale month. Contribution is net sales minus net COGS minus fulfillment. Margin is contribution/net sales, or null when net sales are zero. Booked sales and credit notes are distinct from cash collection; contribution is neither cash flow nor accounting profit.

The 2025 ECB PLN/CZK means have twelve months each and retain the original quote direction. The World Bank market table has six countries by three years for population (persons) and GDP per capita (current US$). GDP per capita is neither PPP nor real income, and neither population nor GDP per capita proves demand for replacement assemblies.

For each hub, the synthetic low/base/high volume uplifts are 10%/25%/40%. Annual incremental contribution after recurring fixed cost is `C × u + U × (1+u) × saving_per_unit − annual_fixed`, where `C` and `U` are 2025 contribution and shipped units. Stress holds uplift at 25% but first reduces baseline contribution by 3% of gross sales in extra refunds and, for PLN/CZK only, 10% of net sales as an FX depreciation proxy, with no extra cost recovery. It then compares the stressed 1.25× contribution with the unchanged baseline, adds savings on 1.25× units and deducts annual fixed cost. Pair results add single-market outputs with no synergy. Capex is a year-zero outlay, excluded from annual contribution; simple undiscounted payback is capex divided by positive annual incremental contribution, otherwise null. The workbook and JSON include all six single hubs, all eleven feasible pairs and defer under four scenarios.

## Checks and limitations

`scripts/verify.py` ran **163 checks**: archived and local hashes, row/revision/exclusion identities, inclusive cutoff, zero-price handling, effective-cost revision, monthly/annual reconciliation, all 24 ECB means, independent scenario formulas and pair feasibility, workbook tabs/charts, and PDF page/text integrity. Both PDFs were rendered to images and visually inspected; the report has four nonblank pages, the deck six. `deliverables/verification.json` records the checks. Reported source anomalies are 13 identical order duplicates, 18 superseded order revisions, 24 cancelled and 18 test orders, one 2026 shipment, 12 valid zero-price shipments, 20 identical return duplicates, one superseded return revision, one post-cutoff return and one orphan return. All 24 blank raw shipment dates belong to cancelled orders; no eligible shipment date, return field, effective unit-cost or World Bank value is missing. Exactly 209 eligible orders appear in each market, a synthetic balanced pattern that should not be mistaken for market evidence.

The source room has no measured delivery times, inventory capacity, customer conversion, realized settlement FX, 2026 demand, tax, financing, working capital or discounted cash-flow inputs. The scenario's volume uplift and unit savings are assumptions; stress is a deliberately conservative joint case with no assigned probability. The proposed gate and KPI thresholds are management decision rules. They do not make the recommendation statistically proven or certain.
