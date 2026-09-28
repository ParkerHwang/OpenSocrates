# Reproducing the Meridian Parts analysis

All calculation inputs used for this package are saved under `evidence/source_room/`. Rebuilding the figures does not require network access. Client order, return, cost, hub-option and policy files are synthetic. The archived World Bank and ECB files are public official-source snapshots; their original URLs, retrieval vintages, collection times, units and SHA-256 hashes are in `deliverables/source_register.json` and `.csv`.

## Rebuild

Use the Python and Node executables listed in the preserved `TOOLING.md`, from the workspace root:

```sh
python3 analysis/build_analysis.py
python3 analysis/build_workbook.py
python3 analysis/build_documents.py
node analysis/render_documents.js
python3 analysis/verify_deliverables.py
```

`build_analysis.py` applies whole-row revision selection, return-cutoff and exact-key join rules, archived ECB monthly FX conversion, per-order half-up cent rounding, country/month reconciliation, World Bank context, the specified individual/pair scenarios and the documented sensitivity analysis. It writes `deliverables/metrics.json`, expanded source registers and transparent order-level/intermediate CSVs in `analysis/output/`.

`build_workbook.py` creates the XLSX and checks sheet dimensions, native charts and 54 monthly-to-country reconciliations. `build_documents.py` creates self-contained HTML print masters. `render_documents.js` uses the provided `EVAL_BROWSER_WS` Chromium connection to write the two PDFs and page/slide previews. The HTML masters are retained so another analyst can inspect or re-export the exact content.

`verify_deliverables.py` independently checks saved source hashes and archive integrity, source-to-ledger accounting and FX calculations, scenario arithmetic, workbook reconciliation cells and chart presence, PDF page/text output, and preview dimensions. The workbook was checked structurally with `openpyxl`; this environment did not provide Excel or LibreOffice for an application-native XLSX rendering check. PDF pages and slide previews were visually inspected.

To recollect the frozen source room before using the saved inputs, run `python3 analysis/collect_source_room.py` while the provided source-room endpoint is available. The downloaded bytes and timestamps will then reflect that collection run; the outputs in this package use the preserved files and hashes listed in the source register.

## Output map

- `deliverables/executive_report.pdf` and `executive_report.html`
- `deliverables/board_presentation.pdf` and `board_presentation.html`
- `deliverables/meridian_analysis.xlsx`
- `deliverables/metrics.json`, `source_register.json`, and `source_register.csv`
- `evidence/source_room/` contains the collected raw files and collection manifest; `analysis/` contains the rebuild scripts, independent verifier and reproducibility notes.
- `analysis/output/` contains monthly/country data, per-order rounded components, exclusions, FX, market context, options, feasible pairs, sensitivity ranges/results/switching values and quality notes.
- The workbook's `Sensitivity` sheet and `metrics.json`'s `sensitivity_analysis` object record tested ranges, portfolio winners, extrapolated volume switching values and the explicitly hypothetical stress-floor switch.

The financial scenario values are arithmetic over synthetic inputs and stated assumptions; they are not measured causal hub results or probability-weighted forecasts.
