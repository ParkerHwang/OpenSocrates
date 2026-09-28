# Verification record — 2026-09-27

The final commands completed successfully after the last source-register and report edits:

```sh
python analysis/build.py
python analysis/publish.py
python analysis/verify.py
```

Actual checks passed:

- 72 country-month JSON rows sum exactly at order-rounded cents to all six
  country totals; each ledger order satisfies gross minus refunds equals net
  sales, and net sales minus net COGS minus fulfillment equals contribution.
- 1,254 unique eligible shipped-order IDs reconcile to the ledger and monthly
  data. The resolved audits contain 1,297 order IDs and 243 return IDs;
  241 return IDs enter the cohort, one orphan is quarantined and one
  after-cutoff return is excluded. Twelve zero-price shipments remain included.
- All 13 saved source files match the hashes and sizes in the generated source
  register. The ECB CSV is byte-identical to a CSV entry in the saved official
  ZIP; all 24 PLN/CZK means were recomputed independently from saved daily rows.
- The 88 defer/single/pair scenario rows add country results correctly and
  honor the €450,000, seven-FTE and two-hub constraints. CZE+ESP leads the
  feasible low/base/high cases; NLD+ESP leads the defined stress.
- Saved XLSX values match JSON for every monthly and country contribution;
  reconciliation formulas and both decision charts are present.
- The five-page report and seven-slide deck were rendered to PNG, checked for
  nonempty text and page-bound text, and visually reviewed via
  `analysis/render/contact_sheet.png`. A clipped deck card found in an earlier
  render was corrected before this final check.

Material limits: no Excel or LibreOffice desktop renderer was installed, so
native workbook display was not checked. The model uses synthetic client inputs
and archived official data, not live series. Actual settlement FX, cash timing,
site quotes, service baselines, customer demand and a hub experiment are absent.
The scenario arithmetic is a conditional planning comparison, not a causal
estimate or a probability-weighted investment appraisal.
