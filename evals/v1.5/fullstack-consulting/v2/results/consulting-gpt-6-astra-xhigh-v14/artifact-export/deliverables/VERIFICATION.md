# Verification and material limitations

The final package passed **718 automated checks**. The complete check list, run time and core artifact SHA-256 values are in [verification.json](verification.json).

## Financial and evidence checks performed

- SHA-256 verification of all 14 collected files; all four public archive entries matched the supplied source register. The ECB ZIP member and saved CSV are byte-identical.
- An independent reconstruction from raw CSVs, without importing the main analysis implementation: SQLite selected distinct rows and highest revisions; rational arithmetic and integer cents independently reproduced order accounting. The main model uses Decimal half-up arithmetic.
- Exact agreement for all 1,254 eligible order calculations, 72 country-month records and six country totals, including every monetary component, units, return quantities and margins.
- Explicit cutoff, orphan, future-shipment, zero-price, July cost-change, revision-replacement and half-cent-rounding checks. The 12 free shipments retain 739 units and EUR14,565.90 of negative contribution.
- Independent calculation of all 24 monthly FX means, with 255 observations per currency; comparison of all 18 World Bank country-years for both indicators with saved source values.
- Independent agreement for all 24 country scenarios, 88 portfolio-scenario records and 24 supplemental sensitivity results. Payback is blank/null where contribution is nonpositive. Eleven pairs are feasible; the base winner and maximin alternative were checked.
- Offline end-to-end rebuilding produced a byte-identical `metrics.json`: `4ff3ff7437cf50cd5e968d27449246d077616da0aa71b4fc8ac1429ca19fa508`. See [reproduction.json](verification/reproduction.json). Subsequent workbook presentation refinements did not change that financial JSON.

## Workbook checks performed

- Opened the XLSX successfully with openpyxl in both formula and cached-value modes: 20 worksheets, 12,263 formula cells and two native charts.
- All formula cells contain usable caches or intentional blanks; no Excel error values were found. Monthly/country/scenario/portfolio caches match the analytical JSON, and key formula references were inspected.
- No external workbook formula links. Native chart references were inspected, and the package XML contains six country-series points plus 20 portfolio-series points in chart caches.
- Intermediate scenario columns and portfolio composition columns are grouped so key results are visible together. Inputs are marked blue; headers freeze and data sheets have filters. The workbook Guide explains editable inputs and static narrative/sensitivity limitations.
- Generated a separate HTML preview from cached XLSX values. The supplied isolated Chromium rendered ten panels and eight screenshots with no page errors. Inspected the Decision, Monthly, Scenarios, Portfolios and Inputs previews for legibility. Screenshots and `browser_check.json` are under `verification/`.

**Limit:** no native Excel or LibreOffice engine is installed. Native workbook rendering and recalculation were not performed. The browser preview does not reproduce Excel layout or evaluate formulas. Excel's binary arithmetic may differ at rare half-cent boundaries after recalculation; the delivered caches and JSON are the verified Decimal results.

## PDF checks performed

- Generated and rasterized all 12 report pages and all ten board slides with PyMuPDF. No empty pages or text outside page boundaries were detected.
- Visually inspected all report pages and board slides using rendered contact sheets. Tables, chart labels, page numbers and decision figures are readable; three long slide titles were shortened to improve spacing.
- The report contains 46 link annotations, including internal source references and original public source endpoints. Key recommendation numbers agree across PDFs, JSON and workbook.
- Page images, contact sheets and extracted text are saved under `verification/`. Rendering files are review aids, not additional source evidence.

## Material analytical limits

The calculation checks establish reproducibility within the supplied synthetic case. They do not establish that opening a hub causes the assumed 25% volume uplift or realizes the supplied unit savings. Every supplied saving exceeds historical fulfillment cost per unit; a separate saving-cap sensitivity highlights the unresolved scope. Customer demand, net saving scope, site quotes, cash collections, working capital, ramp, financing, taxes and service baselines remain missing or unverified.

The World Bank and ECB observations were collected from a frozen archive, not refreshed live. Historical revisions are preserved; current-US-dollar GDP per capita and population do not establish replacement-parts demand. Returns are censored at the inclusive 2026-01-31 cutoff; later credits are outside the requested base.

OpenSocrates selection delivered complete comparison/sensitivity procedures, but native activation/application is unconfirmed. Initial evidence-selector requests failed; evidence calibration used the complete installed canonical reference. These instrumentation limits do not change the recorded financial or rendering checks.

No helper agents, other models, real customer data, paid services, deployments or publishing were used. `TASK.md` and `TOOLING.md` were preserved. All generated files and installed dependencies stayed within the supplied workspace/profile.
