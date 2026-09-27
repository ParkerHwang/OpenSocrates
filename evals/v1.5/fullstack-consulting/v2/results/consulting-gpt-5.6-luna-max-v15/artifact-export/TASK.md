# Meridian Parts: European service-hub expansion

Act as an operations consultant for the synthetic client Meridian Parts. Its
board must choose whether to fund up to two local service hubs in Germany (DEU),
France (FRA), Netherlands (NLD), Poland (POL), Czechia (CZE) and Spain (ESP). The
company sells replacement assemblies, currently shipping from a central hub.
Build an evidence-based recommendation, not a generic market overview.

Collect source files yourself from the source-room URL in TOOLING.md. It contains
raw client exports, corrections, assumptions and archived official World Bank
and ECB data with original URLs and retrieval vintage. This is a frozen source
room, not a live client account. You may also collect additional public evidence.
Use archived official series for comparable core calculations; clearly distinguish
archive collection from live research, synthetic inputs from public observations,
and facts from assumptions. Do not invent customer interviews or source access.

Choose your analysis tools and document-generation approach. There is no imposed
duration, token, tool-call, retry or document-length budget. Make the actual files,
check their calculations and rendering, and report material gaps honestly.

## Decision and accounting rules

Analyze 2025 shipped sales and returns known by the inclusive cutoff 2026-01-31.
The source room's `data-dictionary.md` defines grain, revisions, currencies and
accounting. Reconcile all extract pages and correction files. Do not count raw
rows as distinct orders, treat cancelled/test transactions as revenue, lose valid
zero-price shipments, apply January 2026 orders to the 2025 base, or silently
join orphan returns. Record exclusions, duplicate handling and missing values.

For each country and calendar month, calculate shipped orders/units, gross sales
EUR, refunds EUR, net sales EUR, net COGS EUR, fulfillment cost EUR, contribution
EUR and returned units. Report country/year totals and reconcile them to the
monthly records. Use the original sale month's ECB mean business-day quote
(local currency units per EUR) for both sale and refund conversion. EUR is 1.
Round individual monetary components per order to cents using half-up rounding,
then sum. Report margin as contribution divided by net sales; null if denominator
is zero. Explain differences between booked revenue, cash and contribution.

Collect 2022–2024 population and GDP per capita (current US$) for all six markets
from the archived World Bank responses. Preserve years, units, missing values,
source URLs and revision vintage. Compare population change and economic context;
do not treat GDP per capita or population as direct proof of product demand.
Calculate twelve monthly 2025 PLN and CZK ECB reference-rate means. Do not invert
the quote or use today's rate on historical sales.

Use client `hub-options.csv` and `scenario-policy.md` to estimate incremental
annual contribution after recurring hub fixed cost, capex, payback when positive,
and staffing for every option and feasible pair. Distinguish year-zero capex from
annual recurring costs. Budget EUR450,000 capex and seven FTE; up to two hubs, with
the option to defer all. Evaluate low/base/high volume assumptions and the defined
return-rate/FX stress. Explain what assumption would change the decision, compare
the strongest alternative and give a staged 90-day implementation with owners,
dependencies, decision gates, risks and a measurable KPI plan.

## Deliverables

- An executive consulting report (PDF or DOCX), with evidence-linked diagnosis,
  quantified options, recommendation, limitations and implementation plan.
- A board presentation (PDF or PPTX) coherent with the report and calculations.
- A usable XLSX analytical workbook with source/quality notes, monthly/country
  results, market context, scenario comparisons and legible decision charts.
- Downloaded/raw evidence with a source register (URL, retrieval time, hash, units,
  period, synthetic/public status), analysis scripts/notebook and reproducible
  instructions. Another analyst should reproduce figures from saved inputs.
- `deliverables/metrics.json` with top-level `monthly`, `countries`, `fx_monthly`,
  `market_context`, `hub_scenarios`, `recommendation`, `quality`.

For deterministic exchange, `monthly` and `countries` are arrays. Both use
`country`, `shipped_orders`, `shipped_units`, `gross_sales_eur`, `refunds_eur`,
`net_sales_eur`, `net_cogs_eur`, `fulfillment_eur`, `contribution_eur`,
`returned_units`, `margin`; monthly adds `month` in YYYY-MM format.
`fx_monthly` is an array of `{currency,month,local_per_eur}`.
`market_context` is an array of `{country,year,population,gdp_per_capita_usd}`.
`hub_scenarios` is an array of `{country,scenario,incremental_contribution_eur,
capex_eur,fte,payback_years}` for low/base/high/stress.
`recommendation` includes `countries` (array), `capex_eur`, `fte` and rationale.
`quality` describes detected anomalies and their handling; do not hide them just
to produce a complete table. Other fields and documents are welcome.

Keep values and units consistent across prose, tables, charts, workbook and JSON.
A correctly formatted JSON file is not a substitute for the consulting work.
Do not claim a favored recommendation is statistically proven, causal or certain.
