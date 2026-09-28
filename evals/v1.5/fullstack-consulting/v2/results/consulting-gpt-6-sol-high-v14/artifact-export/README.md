# Meridian Parts board package

This package uses a frozen local source-room download, not a live client account.
The synthetic client files are under `sources/raw/`; `population.json`,
`gdp-per-capita.json` and `ecb-history.zip` are archived official public
responses. `sources/source_register.json` records the local collection URL and
time, SHA-256, units, period, synthetic/public status, and original public URL
and retrieval vintage where available. Archived public hashes match the
source-room register. No live World Bank or ECB series was mixed into the core
calculation.

## Reproduce

From the project root, use the Python supplied in `TOOLING.md`:

```sh
<SHARED_RUNTIME>/python/bin/python3 analysis/build.py > analysis/run_summary.json
<SHARED_RUNTIME>/python/bin/python3 analysis/artifacts.py
<SHARED_RUNTIME>/python/bin/python3 analysis/verify.py
```

The first script writes `deliverables/metrics.json`, the order audit,
scenario matrix and source register. The second writes the report, presentation
and workbook. The third independently checks monthly-to-country reconciliation,
accounting identities, scenario arithmetic and feasibility, archived hashes,
workbook sheets/charts and PDF extraction. The scripts need only the saved inputs
and bundled `openpyxl`, `reportlab` and `pypdf` packages. Re-running will refresh
generated files but leaves `TASK.md`, `TOOLING.md` and raw source files intact.

## Accounting and decision conventions

The base includes shipped, non-test orders with 2025 shipment dates. Latest
numeric revisions replace entire records; identical repeated rows collapse to
one ID. Returns are selected by latest revision and included when received by
2026-01-31 inclusive and linked to an eligible order. The orphan return remains
in the quality log. Returns are assigned to the original sale month; refunds use
the original sale month's ECB arithmetic mean of available business-day quotes.
The quotes are local currency units per EUR. Per-order monetary components are
rounded half-up to cents before aggregation. Gross COGS is recovered only for
physically restocked units at the original effective-dated unit cost. All 12
months for each market are present even if zero; margin is null when net sales
is zero.

The model compares every feasible zero-, one- and two-hub choice under the
client's low/base/high/stress assumptions. Hub capex is year-zero expenditure,
while fixed hub costs reduce annual contribution. Payback is simple and
undiscounted, only shown when annual increment is positive. The recommended
Czechia + Spain program maximizes modeled base annual contribution; the second
site is conditional on the 90-day gates in the report. Netherlands + Spain is
the stronger joint-stress alternative. No scenario is assigned a probability.

## Verified outputs and limits

`analysis/verify.py` passed after the final build. Rasterized PDF inspection
confirmed five report pages and seven landscape presentation pages without
visible clipping; the rendered previews are in `analysis/rendered/`. The workbook
has 72 monthly records, 18 market-context rows, 24 monthly FX rates, 72 feasible
scenario records and two native charts. The archive SHA-256 checks passed.

The client files are synthetic. Hub uplift, unit savings, fixed cost and stress
are assumptions, not causal estimates or a demand forecast. The accounting base
lacks payment timing, settlement FX, taxes, corporate overhead and inventory
working capital. Simple payback omits ramp delays, discounting, taxes and
residual value. The archived World Bank vintage may revise earlier years;
population and current-dollar GDP per capita are contextual, not product-demand
measures. Operational gate thresholds in the report are proposed by the
consultant and need board acceptance.
