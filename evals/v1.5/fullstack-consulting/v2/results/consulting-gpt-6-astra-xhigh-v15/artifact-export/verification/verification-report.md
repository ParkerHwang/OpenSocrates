# Verification record

The delivered cohort, scenarios and workbook pass the checks in `checks.json`. This record describes performed checks and limits; it is not a claim that synthetic planning assumptions have been validated in the real world.

## Computational checks actually run

- All 14 source-room collected files (including index) and two supplemental live text extracts match their independently recorded SHA256. The four public archive files also match the provider's supplied hashes. ECB CSV bytes match the original ZIP member. This establishes archive integrity relative to the supplied evidence, not independent historical authentication of every observation.
- A separate implementation rebuilds the accounting from raw files using **rational FX arithmetic and integer-cent half-up rounding**, without importing the production calculation. It checks every included order and every monthly and country additive measure and margin.
- Reconciled order flow: 1,328 raw rows − 13 exact repeats − 18 superseded revisions = 1,297 IDs; less 24 cancellations, 18 tests and one future order = **1,254 eligible orders**. The 12 zero-price shipments (739 units) remain.
- Reconciled return flow: 264 raw rows − 20 exact repeats − one superseded revision = 243 IDs; one after-cutoff exclusion and one orphan quarantine = **241 included IDs**. The inclusive 31 January return is included and 1 February excluded. The revised EUR149 refund replaces EUR150.
- All 24 PLN/CZK monthly means match an independent rational calculation. All 36 World Bank observations match saved raw responses; vintage metadata is checked. No requested public observation or eligible cost/rate is missing.
- All 24 hub/scenario increments and positive-only paybacks are independently checked. All 22 portfolios are enumerated; 18 feasible choices and four staffing/capex failures are checked. Country increments add to pairs; capex is not charged to the annual measure.
- The XLSX reopens successfully. Its cached monthly/country/scenario values agree with JSON, all nine reconciliation controls read PASS, no cached error cell or `#REF!` exists, and both native charts contain cached numeric series.
- **All 1,314 actual workbook formulas** are independently evaluated by `formula_check.py` and agree with stored caches. Supported functions cover all formulas present: `SUM`, `SUMIF`, `SUMIFS`, `IF`, `AND`, `OR`, `ROUND`, references, ranges, comparisons and arithmetic. Lazy IF avoids evaluating undefined defer payback.
- `checks.json` contains **15,132 passing assertions, zero failures** for the delivered run. Most assertions are individual row/field comparisons; the count is not a confidence score.

## Rendering and manual inspection

- The report has **12 pages**, and the board presentation has **11 slides**. Both PDFs contain selectable text and linked source citations.
- Every page was rasterized with PDFium at 1.4× scale. Full PNGs are in `rendered/`; contact sheets and extracted text are retained.
- Both complete contact sheets were visually reviewed. The dense report portfolio table (page 7), implementation table (page 10), board scenario chart (slide 6) and implementation slide (slide 9) were additionally inspected at full-page resolution. Text, tables, labels, negative signs, EUR units and page footers were legible; no clipping or overlap was observed in those checks.
- The PDF builder checks every paragraph/table bounding box against the page. No recorded content box crosses the page or footer limit. Every PDF page has meaningful text; no TODO/TBD/template placeholder was found.
- XLSX chart XML, cached series, column widths, merged regions, freeze panes, filters, styles and formula references were inspected programmatically. Input instructions and audit-column widths were corrected during review. **Native Excel/LibreOffice visual rendering and recalculation were not performed.** The independent formula evaluator is a scoped numerical check, not a substitute for all spreadsheet application behavior.

## Issues detected and resolved during work

- The initial shell here-document write was blocked by the restricted temporary directory. Files were created with workspace-safe patching; no source was lost or changed.
- Direct Python and curl HTTPS retrieval of the supplemental public pages failed local certificate validation. Official-page retrieval through the web tool succeeded. Saved files are clearly labeled web-tool text extracts, not original HTML bytes; the failure has no effect on archive-only core calculations.
- The first verification pass used a ten-row test range for nine workbook reconciliation controls. The test range and print area were corrected; the accounting values themselves already matched the independent reconstruction.
- Full source and correction reconciliation exposed duplicate records, revisions, cancelled/test/future rows, cutoff edge cases, missing cancelled shipment dates, free shipments and an orphan return. Each is explicitly retained in row-level audit outputs or quality notes.
- The hub saving/cost-scope mismatch was detected analytically. Required scenarios were preserved; a separately labeled capped-savings sensitivity and commitment gate were added to all decision deliverables.

## Material limits

No real customer data, interviews, vendor quotes, pilot results, live client account, bank data or general ledger were accessed. No native spreadsheet rendering was claimed. No probabilities, causal hub effects, statistical significance or full investment cash-flow model are established. The required stress preserves an unchanged normal baseline by policy; defer zero is a decision-model convention.

The release decision still depends on avoidable-cost scope, new local costs, demand/cannibalization, actual FX settlement exposure, staffing/capacity, inventory, working capital and cash timing. The report's implementation and KPI plan assigns proposed owners and observable gates for these gaps.

`reproduction.json` records the actual offline rebuild and before/after metrics hashes. `delivery-manifest.json` records output/file hashes; the package script verifies ZIP member integrity. Original TASK.md and TOOLING.md are preserved.
