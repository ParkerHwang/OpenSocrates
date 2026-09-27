# Verification record

Recorded 27 September 2026 after the final build.

- Ran `scripts/generate_all.py` with the bundled Python runtime. It completed and rebuilt the analysis outputs, charts, workbook, executive report, board presentation, source register and `metrics.json`.
- Ran `scripts/verify_outputs.py`. Result: `All metrics, source hashes, reconciliations, workbook, PDF, PPTX and chart checks passed.`
- Verified the JSON contract: 72 monthly records, 6 country totals, 24 FX means (12 PLN + 12 CZK), 18 market-context records, 68 scenario records (24 individual + 44 feasible-pair records), and recommendation `CZE` + `ESP`.
- Independently recomputed the 2025 FX monthly means from `evidence/raw/ecb-history.csv`, recomputed low/base/high/stress scenario arithmetic from country totals and `hub-options.csv`, and checked feasible-pair sums.
- Checked source-register SHA-256 values against every saved raw input.
- Opened the XLSX with `openpyxl` and checked required sheets and row counts; opened the PPTX with `python-pptx` and checked 10 slides; read the PDF with `pypdf` and checked 10 pages plus required decision, accounting, limitations and implementation text.
- Visually inspected the saved PNG chart assets used by the workbook, report and presentation for labels, clipping and legibility.

Material limitations are intentional and disclosed in the report, workbook Quality sheet,
`metrics.json` and `REPRODUCE.md`: synthetic hub demand/cost assumptions are not
measured demand; the ECB series is a reference-rate translation assumption; World Bank
population and nominal GDP per capita are context rather than demand evidence; cash
settlement data, lane-level operating quotes, customer interviews, local regulatory/tax/
labor evidence and a discounted cash-flow model are not in the source room; post-cutoff
and orphan returns are excluded from the base by rule.
