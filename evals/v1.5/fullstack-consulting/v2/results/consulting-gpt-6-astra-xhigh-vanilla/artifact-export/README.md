# Meridian Parts: board decision handoff

The recommendation is to **reserve EUR225,000 and five FTE for Spain and Czechia, with Spain first and each capital release gated**. The pair generates EUR198,099.31 annual incremental contribution in the supplied base case, after EUR95,000 annual recurring fixed costs. Low / high / stress increments are EUR64,619.11 / EUR331,579.51 / EUR32,179.71. These are conditional steady-state scenarios, not measured demand or guaranteed returns.

Netherlands plus Spain is the strongest stress alternative. All assumed savings per unit exceed the recorded fulfillment costs, and fully loaded hub costs remain unvalidated. The report explains the implications and decision thresholds.

## Deliverables

| File | Purpose |
| --- | --- |
| [Executive report](deliverables/Meridian_executive_report.pdf) | 12 pages: evidence-linked diagnosis, public context, options, all feasible portfolios, sensitivities, capital gates, 90-day plan and KPI ownership |
| [Board presentation](deliverables/Meridian_board_presentation.pdf) | 10 searchable, vector PDF slides with the coherent decision story |
| [Analytical workbook](deliverables/Meridian_analytical_workbook.xlsx) | 19 sheets, 1,866 formula cells, three native charts, editable assumptions, cached results, source notes and detailed audit trail |
| [metrics.json](deliverables/metrics.json) | Requested deterministic arrays plus totals, portfolios, breakpoints and additional sensitivities |
| [Complete handoff ZIP](deliverables/Meridian_complete_handoff.zip) | All documents, evidence, scripts and verification records, with a checked SHA-256 inventory |
| [Detailed tables](deliverables/data/) | Order ledger, all raw-row resolution decisions, exclusions, 72 monthly results, countries, FX daily/monthly, market context and scenarios |
| [Source register](evidence/source_register.csv) | Collection and original URLs, analyst and archive retrieval times, SHA-256, units, periods, vintage and synthetic/public status |
| [Raw evidence](evidence/raw/) | All 13 source-room files plus its index, preserved as downloaded |
| [Verification](VERIFICATION.md) | Actual checks, visual review and limitations |

Keep the folder structure intact: PDF evidence links resolve to `../evidence/raw/`. Original World Bank and ECB URLs are also embedded in the report and register. `TASK.md` and `TOOLING.md` are unchanged.

## Reproduce from saved evidence

No network or source-room service is needed for reproduction. Run from the project root:

```sh
MERIDIAN_PYTHON=<SHARED_RUNTIME>/python/bin/python3 bash analysis/reproduce.sh
```

For a portable environment, Python 3.11+ is suitable. The handoff was checked with the supplied Python runtime. Install dependencies **inside this project**, then run:

```sh
python3 -m venv .venv
PIP_CACHE_DIR="$PWD/.pip-cache" .venv/bin/python -m pip install -r requirements.txt
MERIDIAN_PYTHON="$PWD/.venv/bin/python" bash analysis/reproduce.sh
```

The supplied runtime is Python 3.12.14. The script runs:

1. `analysis/analyze.py`: verifies evidence hashes and ECB ZIP extraction; resolves revisions; derives the per-order Decimal ledger and all metrics; enriches the source register.
2. `analysis/build_workbook.py`: generates the XLSX with cached formula outputs and decision charts.
3. `analysis/build_documents.py`: builds the report and board PDFs from the saved metric values.
4. `analysis/render_documents.py`: rasterizes every PDF page and creates contact sheets for human visual inspection.
5. `analysis/verify.py`: independently recalculates from raw inputs with exact rational arithmetic, then checks outputs, workbook caches, PDF content/bounds and evidence links.
6. `analysis/verify_formulas.py`: independently evaluates all actual XLSX formula strings, compares their caches and exercises input-change tests. It is a restricted formula interpreter, not a desktop Excel engine.
7. `analysis/package.py`: creates the complete handoff ZIP and verifies every archived file against its SHA-256 inventory.

Machine-readable check results are written to `verification/`. Numerical outputs reproduce from the same evidence. PDF/XLSX container metadata may contain build timestamps, so byte-for-byte document identity is not promised. The narrative and implementation plan are intentionally authored around this frozen case; editing source data requires reviewing them as well as rebuilding calculations.

### Source collection, separate from reproduction

`analysis/collect_sources.py` downloaded all links from `http://127.0.0.1:55588/` and saved exact bytes, collection timestamps and SHA-256 hashes. It can be rerun only while that frozen service is available; doing so replaces collection timestamps and saved source files. **Do not recollect to reproduce this handoff.** The archived original public URLs and retrieval vintage are preserved in `evidence/raw/source-register.json`; the enriched register separately records the analyst download time.

There was no live World Bank/ECB re-fetch, customer interview, site visit or live client account access. Client transactions, costs and planning assumptions are synthetic; archived official series are public observations.

## Model conventions

- Highest numeric revision per order across both extracts and corrections; exact repeated rows count once. Corrections replace entire rows. Then include non-test, shipped orders with 2025 shipment dates, including valid zero-price shipments.
- Independently resolve return revisions; include received dates through 2026-01-31 inclusive and only eligible linked orders. Quarantine the orphan, exclude the late return and assign eligible refunds/returned units to the original sale month.
- Calculate available-business-day arithmetic mean PLN/CZK quotes for each month in 2025, in **local units per EUR**. EUR equals 1. Divide gross local sales and summed local refunds by the original shipment-month mean. No inverted or current rate is used.
- Latest valid unit cost on/before original shipment; recover product cost only for physically restocked units. Fulfillment is actual nonrefundable EUR cost.
- Round each order's gross sales, summed refunds, gross COGS, recovered COGS and fulfillment half up to cents, then sum. Net sales and contribution are cent-exact differences. Margin is contribution/net sales, null for zero denominator.
- Scenario annual increment: `C*u + U*(1+u)*s - F`. Low/base/high uplift: 10%/25%/40%. Stress is exactly the source policy, measured against unchanged normal baseline. Intermediate scenario terms are unrounded; final country annual increments are rounded half up to cents. Pairs sum these country amounts.
- Capex is at year zero; fixed expense is annual recurring. Payback is capex/positive annual increment, otherwise null. At most two hubs, EUR450,000 capex and seven FTE; defer is included.
- World Bank population: persons. GDP per capita: current US$, not PPP/real income. Preserve all 2022–2024 observations and missingness. None of the 36 requested values is missing; metadata lastupdated is 2026-07-13, archived on 2026-09-27.

## Workbook use

Open **Read Me** first. **Decision** and **Decision Charts** show the board comparisons. Yellow cells on **Inputs** drive **Hub Scenarios**, **Portfolios**, **Sensitivity** and charts. Cached outputs are present for viewers without automatic calculation; enable automatic calculation in your spreadsheet application when editing assumptions.

Country and monthly summaries sum the fixed **Order Ledger**. **Reconciliation** compares each country total with its twelve months. Editing the historical accounting/FX/cutoff inputs requires a script rebuild; the ledger is deliberately a frozen audited output. **Portfolios** includes all 22 choices, including four infeasible pairs. Its saved rank is static: sort the updated Base EUR column after changing assumptions. Blank paybacks mean nonpositive annual contribution.

## Material limitations

No measured volume uplift, cost-pool validation, site quotes, service baseline, customer-level data, payroll coverage, cash ledger or working-capital plan is supplied. Revision timestamps are absent; revision selection and received-date cutoff follow the dictionary rather than reconstructing a historical system snapshot. Late-2025 returns have less observation time. The scenario model omits tax, financing, discounting, ramp-up, cannibalization and capacity effects. Five proposed direct hub roles are not proof of staffing sufficiency.

All native XLSX formulas and caches were independently evaluated with the included interpreter, including input-change tests. A native desktop Excel/LibreOffice recalculation and native spreadsheet rendering were not available in this environment. PDF rendering and source-link integrity were checked. The model's internal validity does not validate its synthetic commercial assumptions.
