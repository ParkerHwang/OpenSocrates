# Actual verification record

Verification date: 27 September 2026. See the JSON/log files in `verification/` for reproducible details.

## Evidence and accounting

- Downloaded and hashed every source-room index link: 13 files plus the index. Checked all collected-file SHA-256 values and the four supplied public archive hashes. ECB ZIP extraction matches the downloaded CSV byte-for-byte.
- Reconciled 1,328 raw order rows to 1,297 IDs after 13 identical repeats and 18 superseded rows. Excluded 24 cancellations, 18 tests and one 2026 shipment, leaving 1,254 orders. Retained 12 zero-price orders / 739 units.
- Reconciled 264 return rows to 243 IDs after 20 repeats and one superseded revision. Included 241 return IDs; included the 31 January cutoff return, excluded the 1 February return and quarantined the orphan without inferring currency.
- Checked effective-dated costs and physical quantity bounds on every eligible order. All 24 missing shipment dates belong to cancelled orders. No missing required eligible fields, requested World Bank values or monthly FX means were found.
- Independently recalculated every order from raw files using `fractions.Fraction` and integer-cent half-up rounding, without importing the production Decimal model. Compared every monetary component and physical count, all 72 monthly records, six country totals and the group bridge.
- Independently checked 24 monthly FX means, all 36 World Bank values, 24 country scenarios, all 22 portfolios, resource feasibility and positive-only payback. Eleven pairs are feasible. Tested half-up behavior at positive and negative exact ties.
- Final group bridge: EUR4,464,622.33 gross sales − EUR80,830.57 refunds − EUR2,246,919.00 net COGS − EUR106,862.28 fulfillment = **EUR2,030,010.48 contribution**. Net sales are EUR4,383,791.76.

## Workbook

- Opened the XLSX through both formula and cached-value readers; ZIP integrity passed. Checked 19 sheets, freeze panes, 1,866 formula cells and three native chart structures.
- Compared monthly, annual, scenario and portfolio cached results to `metrics.json`. All monthly-to-country controls equal zero; no cached formula error values were found.
- Evaluated **all 1,866 actual formula strings** with an independent restricted interpreter. All matched their stored caches within the documented numerical tolerance.
- Exercised meaningful assumption changes without modifying the delivered workbook: zero base uplift recalculates all six base scenarios and changes the proposed pair to **−EUR24,367.70**; reducing the capex limit to EUR200,000 changes that pair to infeasible. All eight change checks passed.
- A desktop Excel/LibreOffice engine was unavailable. Native recalculation and native spreadsheet rendering were **not** executed. The restricted evaluator verifies the functions used here, not all Excel behavior. Spreadsheet chart formatting is native XLSX, with a structural and range check rather than an Excel screenshot.

## Documents and visual review

- Generated the actual searchable report PDF (12 pages) and board PDF (10 slides). Both have evidence links and shared values from the analytical model.
- Rasterized **every page** with PDFium. Visually inspected both complete contact sheets and enlarged the dense portfolio table (report page 7) and standalone option table (deck slide 5). Also reviewed the 90-day and KPI pages in the contact sheets.
- Found and corrected a report page overflow during review; rebuilt to twelve complete pages. Final contact sheets show no stray continuation page, clipped table or visible text collision.
- Checked every PDF character box against page bounds: zero out-of-page glyphs. No missing-glyph boxes found; all pages have searchable substantive text. Checked 101 relative evidence links; all resolve to saved files. The report also has three original public-source URL links.
- Deck generation checks every text box against its available height. Tables and charts were reviewed in the rendered output. The PDF page-bound check alone is not treated as an overlap guarantee.

## Limitations of these checks

These checks establish fidelity to the frozen files and specified accounting/scenario rules. They cannot verify synthetic demand, avoidable savings, staffing capacity, market causality or actual investment returns. No invoices, bank cash flows, customer interviews, site diligence or live client systems were accessed. The case still requires the operational evidence and board gates described in the report.

`verification/verification_report.json`, `formula_verification.json`, `calculation_checks.json` and `document_layout_checks.json` record machine checks. `verification/rendered/` contains the page images and contact sheets reviewed.
