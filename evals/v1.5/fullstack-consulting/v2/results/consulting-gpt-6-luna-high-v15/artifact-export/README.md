# Meridian Parts analysis package

## Reproduce

From the project root, with Python 3.12 and the provided local dependencies:

```sh
python3 analysis/analyze.py
PYTHONPATH=.deps python3 analysis/build_outputs.py
python3 analysis/verify.py
```

`analysis/analyze.py` uses the saved source files in `evidence/raw/`. It has no network requirement. `analysis/build_outputs.py` creates the XLSX, consulting report PDF, seven-slide presentation PDF and PPTX, charts and source register. It needs `openpyxl`, `reportlab`, `python-pptx`, `matplotlib` and the standard Python library. These packages were available in the supplied runtime; matplotlib and its dependencies are installed under `.deps/`. To install dependencies in a separate environment, run `python3 -m pip install -r requirements.txt` and omit `PYTHONPATH=.deps`.

## Evidence and status

- `evidence/raw/` contains the complete frozen source-room download, including both order pages, corrections, returns, data dictionary, client assumptions, ECB archive ZIP/CSV and World Bank responses.
- The synthetic client files are not real company data. Seed: `2026092736`.
- ECB and World Bank files are official public archive snapshots, not live API pulls for this analysis. Retrieval times, original URLs, hashes, units, periods and archive notes are in `evidence/source-register.json`; source vintage is also preserved in `evidence/raw/source-register.json`.
- ECB PLN/CZK rates are arithmetic means of available daily business-day quotes, local-currency units per EUR. The archived rates are translation assumptions, not transaction rates.
- World Bank GDP per capita is current US dollars, not PPP or constant-price income. Population and GDP are context, not evidence of product demand.

## Decision and limits

The recommendation is to stage Netherlands + Spain and release capex only after the proposed 90-day validation gates. It leads the client-defined joint stress case, while Czechia + Spain has the highest base-case annual increment. The conservative stress ranking is an explicit consultant default because the board supplied no risk weights; it is not a board-approved preference or a weighted score. Both outcomes depend on synthetic option assumptions and do not estimate causal hub impact. Capex is year-zero; the annual incremental contribution includes recurring fixed cost but not capex. Payback is simple and undiscounted.

The analysis follows `evidence/raw/data-dictionary.md` and `scenario-policy.md`, preserves per-order half-up rounding, uses original sale-month FX on refunds, and reconciles all additive monthly results to country totals. Quality exceptions and treatment are available in `deliverables/metrics.json` and the workbook's Quality tab.
