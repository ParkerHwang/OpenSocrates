# Meridian Parts — reproducible board case

The recommended planning choice is to launch Spain first and reserve Czechia as a
second hub subject to a day-60 gate. The combined ceiling is €225,000 year-zero
capex and five FTE. Under the synthetic client base assumptions the pair adds
€198,099.31 annual contribution after recurring hub fixed costs; under the
defined joint return-rate/FX stress it adds €32,179.71. The stress-leading
alternative is Netherlands plus Spain at €107,630.13/year. These are scenario
outputs, not measured causal effects or forecasts with known probabilities.

## Deliverables

- `deliverables/meridian_executive_report.pdf` — five-page decision report with
  accounting, context, option screen, risks and staged implementation.
- `deliverables/meridian_board_presentation.pdf` — seven-slide board brief.
- `deliverables/meridian_analytical_workbook.xlsx` — monthly and country
  accounting, FX, market context, single/pair scenarios, quality/source tabs,
  reconciliation formulas and decision charts.
- `deliverables/metrics.json` — deterministic machine-readable exchange,
  including all 72 country-month rows, 24 monthly FX means, 18 World Bank
  country-years, all six single-hub scenarios and all pair/defer scenarios.

## Saved inputs and provenance

The files in `evidence/raw/` were downloaded from the frozen source-room index
at `http://127.0.0.1:65178/`. No live client account was accessed. The raw
client transactions, hub choices and policies are entirely synthetic. The
World Bank and ECB files are archived copies of official public responses,
collected by the source room on 2026-09-27. The original public URLs,
archive retrieval timestamps, local download timestamps, SHA-256 hashes,
periods, units, source revision and source status are in
`evidence/source_register.csv`. The World Bank responses report
`lastupdated=2026-07-13`; historical values may contain later revisions.

`evidence/order_audit.csv` records the selected highest revision and disposition
of every order ID; `evidence/return_audit.csv` does the same for returns;
`evidence/order_ledger.csv` contains every eligible order's rounded EUR
components and original-month FX quote. The unmatched return is quarantined,
and the 2026-02-01 return is outside the inclusive cutoff.

## Reproduce from saved inputs

From the project root, using the supplied Python environment:

```sh
python analysis/build.py
python analysis/publish.py
python analysis/verify.py
```

The first command is offline and rebuilds the ledger, register and JSON. The
second creates the XLSX and PDFs. The third checks exact monthly/country and
ledger reconciliation, inclusion decisions, raw-source hashes, ECB ZIP/CSV
identity, all 24 FX means, scenario addition/feasibility, workbook values and
charts, and PDF text bounds while rendering every page. `analysis/render/`
contains visual previews. `analysis/verify.py` imports the locally installed
PyMuPDF wheel from `analysis/vendor/`; if absent, install locally with
`python -m pip install --target analysis/vendor PyMuPDF`.

Accounting follows `evidence/raw/data-dictionary.md`: resolve revisions across
both extract pages and corrections, retain shipped non-test 2025 orders
including free orders, attach only eligible returns known by 2026-01-31, and
use the original shipment month's ECB local-units-per-EUR mean for gross sales
and summed refunds. Monetary components are rounded per order to cents, half
up. Month is the original sale month. `evidence/raw/scenario-policy.md` defines
the client assumptions, stress and simple undiscounted payback.

## Decision limits

The source room does not include actual transaction settlement FX, a cash or
receivables ledger, site/3PL quotes, comparable route-time data, a demand
experiment, or customer interviews. The 90-day plan sets owners by role and
proposed gates; it does not claim those operating results already exist. No
Excel or LibreOffice desktop renderer was available, so the workbook was
checked structurally and for formula/chart presence, while the PDFs were
rendered and visually inspected.
