# Meridian Parts — European service-hub decision

The completed analysis recommends **conditionally reserving EUR225,000 and five FTE for Czechia + Spain**, with Spain first and a separate Czechia release gate. The prescribed base model adds **EUR198,099.31 per full run-rate year** after recurring hub fixed costs. This is an analyst recommendation under an explicit preference for base contribution, not an unconditional spending approval or causal demand estimate.

The material challenge is the saving assumption: all six proposed savings exceed recorded fulfillment cost per unit. Capping savings at that recorded cost gives CZE+ESP **EUR164,331.65 base and -EUR1,587.95 stress**. Netherlands + Spain is the strongest downside alternative. Read the report before using the model for a decision.

## Main deliverables

| File | Contents |
|---|---|
| [Executive report](deliverables/Meridian_executive_report.pdf) | 12 pages: recommendation, reconciliation, market/FX evidence, every feasible choice, switching conditions, limitations, 90-day gates and KPI plan |
| [Board presentation](deliverables/Meridian_board_presentation.pdf) | 11 landscape slides with the same decision, economics, trade-offs and evidence gates |
| [Analytical workbook](deliverables/Meridian_analytical_workbook.xlsx) | 17 sheets; 1,314 formula cells with caches; two native charts; order/return audit detail; input controls; all scenarios and portfolios |
| [Metrics JSON](deliverables/metrics.json) | Required deterministic arrays and fields, plus totals, portfolios, thresholds and quality disclosures |
| [Decision support](deliverables/decision-support.json) | Criteria provenance, savings-cap sensitivity and observable switching conditions |
| [Source register](deliverables/source-register.csv) | Original and collection URLs, separate retrieval times, SHA256, byte sizes, units, periods, vintage and synthetic/public status |
| [Verification record](verification/verification-report.md) | Checks actually performed, visual review, corrected issues and material limitations |

The ZIP package contains this directory structure, saved evidence, analytical outputs, source code and verification records. No deployment, publication, paid service, real customer data, helper agent or other model was used.

## Reproduce from saved evidence (offline)

Python 3.12 was used. The supplied runtime already contains all dependencies:

```sh
<SHARED_RUNTIME>/python/bin/python3 scripts/reproduce.py
```

On another machine, use an isolated environment with the recorded dependency versions:

```sh
mkdir -p .tmp .cache
TMPDIR="$PWD/.tmp" python3 -m venv .venv
TMPDIR="$PWD/.tmp" .venv/bin/python -m pip install --cache-dir "$PWD/.cache/pip" -r requirements.txt
.venv/bin/python scripts/reproduce.py
```

Run commands from the project root. The reproduction command reads saved inputs only; it does not call the source room or public sites. It rebuilds the analysis, workbook and both PDFs, then independently verifies accounting/formulas and rasterizes every PDF page. A successful run prints its check summary and returns exit code zero. Verification timestamps and PDF metadata can change between runs; the financial JSON and CSV results are deterministic for these saved inputs.

Report fonts use Arial when available in the macOS system font directory and otherwise fall back to PDF Helvetica. This can change line wrapping on another machine; layout bounds are checked during generation, and rendered output should be reviewed after a font change. No external font or image download is required. Figures are vector drawings, not generated imagery.

To rebuild the distribution ZIP after verification:

```sh
python3 scripts/package_delivery.py
```

Optional archive collection is separate:

```sh
python3 scripts/collect_sources.py
```

That last command re-collects the frozen room at `http://127.0.0.1:49804/` and changes analyst collection timestamps. It requires that disposable endpoint to exist; it is **not needed for reproduction**. The original `TASK.md` and `TOOLING.md` are preserved.

## Files and calculation flow

1. `raw/` preserves all 13 linked source-room files plus its index. `raw/live/` preserves two supplemental official-page web-tool text extracts. The live pages were used only for definitions; live rates and GDP observations never enter core calculations. Direct shell HTTPS attempts failed certificate verification; web-tool retrieval succeeded and its extracted-text format is disclosed.
2. `scripts/analyze.py` verifies hashes, selects revisions across every extract/correction, applies eligibility and the inclusive return cutoff, computes original sale-month FX means, applies effective-dated costs and half-up order rounding, and emits accounting/scenarios/quality files.
3. `scripts/decision.py` adds the explicit decision preference, conditional recommendation, sensitivities and switching thresholds. Required policy scenarios remain intact.
4. `scripts/build_workbook.py` builds the usable XLSX. `scripts/build_documents.py` builds the report and board PDFs from the same metrics.
5. `scripts/verify.py` independently recalculates the raw accounting using rational arithmetic and integer cents, checks scenarios/provenance, inspects XLSX and PDF structure and rasterizes documents. `scripts/formula_check.py` independently evaluates the workbook's actual formulas using a scoped Decimal evaluator.

Detailed outputs include `monthly.csv`, `countries.csv`, `order-ledger.csv`, `order-audit.csv`, `return-audit.csv`, `fx-daily-2025.csv`, `fx-monthly.csv`, `market-context.csv`, `hub-scenarios.csv`, `portfolio-scenarios.csv`, and `decision-thresholds.csv`. The canonical ledger retains winning file/line, original shipment month, FX, effective cost, restocking and linked return IDs. Audit tables retain every raw input row with its disposition.

## Workbook use

- Start at **Dashboard**, then **Countries**, **Monthly**, **Scenarios** and **Portfolios**. **Sources** and **Quality** explain provenance and handling; **Orders** and the audit sheets expose the row-level trail.
- Blue **Hub Inputs** cells B6:E11 and L6:L13 are editable assumptions. Scenario and portfolio formulas and chart ranges update in compatible spreadsheet software. **Historical ledger, recommendation text, static base ranks and supplemental sensitivities describe the delivered run.** Re-run the scripts and reassess the decision after changing assumptions or source data; narrative does not automatically rewrite itself.
- Amounts are EUR unless explicitly local currency or GDP per capita current USD. FX is local units per EUR; displayed six-decimal means do not replace full-precision means in accounting. Margin is a fraction, not a percentage-point number. A blank payback represents a nonpositive increment or defer, not zero years.
- The **Checks** sheet reconciles the nine additive measures between the order ledger and country totals. Monthly/country margins are recomputed from their own denominators. Formula caches support viewers that do not immediately recalculate.
- Native Excel/LibreOffice rendering and recalculation were not available in this run. All 1,314 formulas were independently evaluated within the supported subset and matched caches. Chart XML, cached series, widths, row formats, references and error cells were checked. Native spreadsheet appearance remains a stated rendering limitation.

## Accounting and evidence rules

The inclusion basis is shipped status, `is_test=false` and `shipped_at` in calendar 2025. Ordered dates do not define the sales cohort. Highest numeric revision wins; corrections replace the full order. Identical duplicate rows do not create orders or returns. Zero-price shipments count and retain costs.

Included returns are received on or before **2026-01-31**, linked to an eligible order. Legitimate distinct return IDs are additive, although this file has no eligible order with multiple distinct return IDs. Orphans are quarantined without guessing an order or currency. Refunds are assigned to the original sale month, not the return month.

Gross local sales are quantity × unit price minus discount. Gross sales and summed refund credits are divided by that original month’s arithmetic mean ECB quote. Monetary components are half-up rounded to cents **per order before aggregation**. Cost is the latest SKU EUR cost effective on or before shipment; only restocked quantities recover cost at that original rate. Fulfillment is nonrefundable. Margin = contribution / net sales, null when net sales is zero.

The 2025 results contain 1,254 orders, 77,436 shipped units, EUR4,383,791.76 net sales and EUR2,030,010.48 contribution. Contribution is not cash, EBITDA or net profit. No bank, receivables or general-ledger reconciliation is available. Return credits use analytical reference-rate translation, not actual settlement FX.

The provider's World Bank/ECB archives were retrieved on **2026-09-27**. World Bank reports **lastupdated 2026-07-13**; later historical revisions may be incorporated. All requested 2022–2024 core public values are present. Saved JSON preserves source metadata and original observations. Population and GDP/person describe context; neither is proof of replacement-assembly demand. Current USD GDP/person is neither PPP nor a real-income series.

## Scenario interpretation and limitations

Normal increment = `C*u + U*(1+u)*s - F`. Low/base/high uplifts are 10%/25%/40%. Stress applies the exact client formula: `C_stress = C - 0.03*G - FX_shock`, with `FX_shock=0.10*N` only for PLN/CZK markets; increment = `1.25*C_stress - C + 1.25*U*s - F`. This compares to an unchanged normal baseline. Defer is zero by the decision policy, not a forecast of the macroeconomy.

Country scenario increments are rounded half up to cents at the final step; pairs add those figures. Payback divides capex by positive reported annual increment. Capex is year zero, recurring fixed cost is annual, and FTE is a separate hard constraint. All 15 pairs, six singles and defer are evaluated; 18 of 22 choices are feasible.

The analysis assumes a full run-rate year, additive countries, no synergy, stable unit economics and no cannibalization. No ramp, working capital, tax, financing, discounting, closure cost or residual value is modeled. Whether quoted fixed costs cover the required payroll, site, systems and service scope must be verified. No real demand test, supplier quote, service-level study, capacity assessment or customer interview exists in the source room.

The action choice can be reopened independently of the accounting. New eligible corrections reopen cohort totals. Observed demand, cost or FX exposure reopen estimates. The board's preference for downside protection can select Netherlands + Spain even while the base arithmetic remains unchanged. All public evidence states and conditions are documented; no private reasoning is retained.

OpenSocrates grounding: trade-off-analysis@3. Native method application confirmation remains unverified; this instrumentation limit is separate from the completed deliverable checks.
