# Meridian Parts — European service-hub decision

The completed recommendation is a **staged Czechia + Spain envelope: EUR225,000 capex and five FTE**, with Spain first. The base incremental annual contribution is **EUR198,099.31**, after EUR95,000 recurring hub fixed cost. Low / high / specified stress results are EUR64,619.11 / EUR331,579.51 / EUR32,179.71. The base simple payback is 1.14 years at steady state.

Netherlands + Spain is the strongest stress-resilient alternative: EUR270,000, six FTE, EUR166,931.43 base and EUR107,630.13 stress annual contribution. Demand, saving scope and FX exposure can change the second-site decision; these are explicit release gates, not measured facts.

## Read the deliverables

- [Executive report — 12-page PDF](deliverables/meridian_report.pdf): evidence-linked diagnosis, all feasible alternatives, sensitivity, limitations and the 90-day implementation/KPI plan.
- [Board presentation — 10-slide PDF](deliverables/meridian_board.pdf): the recommendation, strongest alternative and proposed capital gates.
- [Analytical workbook — XLSX](deliverables/meridian_analysis.xlsx): 20 sheets, 12,263 formula cells, two native Excel charts, source/quality notes and editable scenario inputs.
- [Metrics — JSON](deliverables/metrics.json): all required arrays plus portfolios, supplemental sensitivity, thresholds and model definitions.
- [Public decision basis](deliverables/decision_basis.json): evidence states, trade-offs, assumptions and observable switching conditions. It contains no private reasoning.
- [Verification record](deliverables/VERIFICATION.md) and [machine checks](deliverables/verification.json).

## Saved evidence and audit trail

`evidence/raw/` contains the unchanged source-room index and every one of its 13 linked files. `evidence/collection-manifest.json` records actual analyst collection times and hashes. `evidence/source-register.csv` and `.json` add original publisher URLs, archive retrieval times, units, periods, source status and revision vintage. `evidence/raw/source-register.json` remains the original supplied register.

Client transactions, costs, options and scenario rules are entirely **synthetic**. The World Bank and ECB files are **archived official observations**. Public archive retrieval occurred on 2026-09-27 at 06:36 UTC; this analysis downloaded those saved bytes from the frozen source room at 10:12 UTC. No live public data refresh, real client account or customer interview was used. World Bank source `lastupdated` is 2026-07-13, so historical values may include subsequent revisions.

`deliverables/audit/` includes the retained ID records, per-order ledger, duplicate/revision actions, exclusions, 510 FX currency-date observations, 72 monthly records, country totals, scenarios, all 22 portfolios × four cases and supplemental sensitivities. The 22 portfolios comprise defer, six singles and all 15 pairs; four pairs are infeasible.

## Reproduce from saved inputs

The financial analysis itself uses only Python's standard library. Python 3.12.14 was used. Install the pinned artifact dependencies locally if they are unavailable:

```sh
python3 -m pip install --target .deps -r requirements.txt
python3 scripts/run_all.py
```

`run_all.py` sets local dependency/cache paths for its child processes. It performs no network access, does not refresh evidence and writes only inside this project. It runs:

1. `scripts/analyze.py` — verifies source hashes, reconciles IDs and computes the financial/market/scenario outputs using Decimal half-up arithmetic.
2. `scripts/build_workbook.py` — builds the formula-linked XLSX with exact model values cached for immediate viewing.
3. `scripts/build_documents.py` — generates both PDFs, PNG/PDF charts and the public decision basis.
4. `scripts/verify.py` — independently rebuilds the financial calculations from raw CSVs using SQL revision selection and rational arithmetic; checks XLSX caches/wiring and renders every PDF page.
5. `scripts/workbook_preview.py` — generates a self-contained browser preview of cached workbook data for visual review.

When running an individual artifact script outside the bundled environment, first set the local search path:

```sh
export PYTHONPATH="$PWD/.deps${PYTHONPATH:+:$PYTHONPATH}"
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
python3 scripts/build_workbook.py
```

In the supplied environment, Python is available at `<SHARED_RUNTIME>/python/bin/python3`.

Financial JSON is deterministic. A complete offline rebuild was checked for byte-identical `metrics.json`; PDF/XLSX creation metadata can change even when figures do not. Rebuilding overwrites generated deliverables and refreshes verification hashes. It never modifies `TASK.md`, `TOOLING.md` or raw evidence.

Optional browser QA uses the already supplied isolated Chromium connection, when available:

```sh
node scripts/check_browser.cjs
```

This uses Playwright from the supplied Node environment and `EVAL_BROWSER_WS`. It does not launch or access a personal browser. Without that connection, open `deliverables/verification/workbook_preview.html` manually. The preview is a separate rendering of cached values, **not native Excel rendering or recalculation**.

Only if an intentional source re-collection is needed while the local source room is available:

```sh
python3 scripts/collect_sources.py --url http://127.0.0.1:49799/
```

This replaces saved raw files and their collection manifest; do not run it for an ordinary offline rebuild.

## Workbook use

Open `Decision`, then `Guide`. Blue cells on `Inputs` hold editable capex, FTE, annual fixed cost, unit savings, uplifts and shock rates. `Scenarios` and `Portfolios` link to those inputs. Intermediate scenario columns are grouped so key results fit on screen; use Excel's `+` outline controls to expand them. `Orders` feeds `Monthly`, which feeds `Countries`; FX means are linked to published observations. The workbook has filters, frozen headers, conditional loss/feasibility formatting and cached formula results.

The recommendation text, supplemental sensitivities, source notes and browser preview are analyst snapshots, not automatically rewritten by Excel edits. Rebuild the package after source changes. Annual fixed costs are used as supplied; staffing is checked as a separate resource constraint, with no additional payroll expense invented. Confirm what the quoted fixed costs include before commitment.

## Rules and material limits

- Include shipped, non-test 2025 records after whole-row highest-revision replacement. Keep zero-price shipments. Count order IDs, not raw rows.
- Include eligible returns received through 2026-01-31 inclusive. Quarantine orphan IDs; sum legitimate distinct return IDs by original order. Later returns remain outside the defined cohort.
- Gross means quantity × price less discount, before refunds and excluding tax. Translate gross and summed credits with the original shipment month's mean **local units per EUR**; divide, never invert the quote. EUR = 1.
- Round each order's gross, credits, gross/recovered COGS and fulfillment half-up to cents, then sum. Recover product cost only for physically restocked units, at original effective cost. Margin is contribution/net sales, or null for zero net sales.
- Scenario results are steady-state annual increments after recurring fixed costs. Capex is separate. Simple payback is null for nonpositive annual increment. Country scenario totals are rounded to cents before summing pairs.
- The prescribed stress compares the shocked hub case with an unchanged normal baseline. It has no probability attached and is not an exact exchange-rate translation of a 10% depreciation.
- All six assumed savings exceed recorded fulfillment cost per unit. A separately labeled cap-to-fulfillment sensitivity exposes this gap; required client scenarios remain intact. Even eliminating all fulfillment cost is not a demonstrated saving.
- Demand uplift, saving attainment, service baseline, site quotes, working capital, ramp, financing, tax and realized cash are unverified or missing. Population and current-US$ GDP per capita are context, not product-demand evidence. A short pilot does not prove sustained demand uplift.
- No native Excel/LibreOffice engine was available. All formula caches and key wiring were checked; the full model was independently recomputed. Native application recalculation/rendering remains a stated limitation.

OpenSocrates native selection emitted complete trade-off and sensitivity procedures. Native activation/application remains unconfirmed. Evidence calibration used the complete installed canonical reference after initial selector request failures. Public grounds and limitations are in the report and `decision_basis.json`.

OpenSocrates grounding: evidence-hierarchy@3, trade-off-analysis@3, sensitivity-analysis@3
