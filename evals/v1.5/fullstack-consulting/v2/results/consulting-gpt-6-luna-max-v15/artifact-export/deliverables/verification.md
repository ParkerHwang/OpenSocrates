# Deliverable verification

Status: **pass**
Verified at: 2026-09-27T08:29:12.725875+00:00

Checks:
- PASS — metrics top-level schema: All required top-level metrics fields exist.
- PASS — monthly schema and grid: 72 rows; required fields and month present.
- PASS — country schema and grid: Six rows; required fields present.
- PASS — country-month-to-year reconciliation: Every country's 12 months equal its country total for counts and monetary fields.
- PASS — order ledger population: 1254 eligible order records match the metrics quality count.
- PASS — order accounting formulas: Each eligible order satisfies gross−refunds=net sales and net sales−net COGS−fulfillment=contribution.
- PASS — FX grid: 12 monthly mean quotes each for PLN and CZK; EUR=1 is disclosed as convention.
- PASS — ECB monthly means: All PLN/CZK monthly means independently recomputed from saved daily CSV within 1e-7.
- PASS — World Bank context grid: 18 country-year rows for six markets and 2022–2024; nulls remain representable.
- PASS — hub scenario coverage: Four scenarios for six singles, 11 feasible pairs and DEFER.
- PASS — scenario payback: Positive scenarios use capex/annual contribution; nonpositive scenarios have null payback.
- PASS — recommendation capex constraint: EUR 225,000 <= EUR 450,000
- PASS — recommendation staffing constraint: 5 FTE; 2 hubs.
- PASS — recommendation and alternative: Base-ranked alternative and stress-resilient alternative are explicit.
- PASS — saved evidence hashes: All 14 collected source-room objects match their recorded SHA-256.
- PASS — source register fields: 14 source rows carry URL/time/hash/units/period/status.
- PASS — workbook structure: 15 sheets; monthly=72, country=6, scenario=72 records plus header.
- PASS — workbook charts: Two native Excel charts are embedded.
- PASS — workbook values: Country totals in workbook equal metrics.json for all count and monetary fields.
- PASS — PDF structure and content: Report has 8 pages, presentation 6 pages; required recommendation, alternatives, cutoff and funding values extract from PDF text.
- PASS — PDF visual render: Both PDFs were rasterized with pypdfium2 and contact sheets reviewed; page layouts fit without observed table overlaps after revisions.

Limitations:
- The workbook was structurally reopened and its tables/charts/data were checked with openpyxl; an installed spreadsheet GUI renderer was unavailable, so workbook visual rendering was not directly inspected.
- PDFs were rasterized and visually reviewed. Source observations are frozen archive snapshots and client data is synthetic.
