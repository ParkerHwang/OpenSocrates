# Meridian Parts | European service-hub decision

This is a reproducible analysis of the frozen synthetic client source room supplied with the task. The board-facing recommendation is conditional funding for Czechia + Spain (CZE+ESP), with live evidence gates before irreversible commitments.

## Deliverables

- `deliverables/meridian_board_report.pdf` — eight-page executive consulting report.
- `deliverables/meridian_board_presentation.pdf` — six-slide board presentation.
- `deliverables/meridian_analysis.xlsx` — analysis workbook, source/quality notes, all country-month and country totals, FX means, market context, option scenarios, ledgers and two native charts.
- `deliverables/metrics.json` — deterministic machine-readable outputs.
- `deliverables/source_register.csv` — copy of the evidence register for convenient handoff.
- `evidence/source_room/` — raw frozen source files, including both order pages, corrections, returns, assumptions, ECB archive and World Bank responses.
- `analysis/source_register.csv` — URL, retrieval timestamp, SHA-256, units, period, synthetic/public status and vintage notes for each collected source file.
- `analysis/` — reproducible monthly, annual, scenario and audit ledgers; `analysis/qa/` retains rendered PDF contact sheets used during visual review.
- `scripts/` — source collection, input profiling, calculation, workbook, PDF and optional PDF-render QA scripts.

`TASK.md` and `TOOLING.md` are preserved as supplied.

## Reproduce the figures and documents

Use Python 3. The core metrics script uses the saved source-room files and Python's standard library; it does not require a live client, World Bank or ECB connection. The document builders use `openpyxl` and `reportlab`.

```text
python3 scripts/analyze.py
python3 scripts/build_workbook.py
python3 scripts/build_pdfs.py
python3 scripts/verify_outputs.py
```

To re-collect the frozen source room while its local endpoint is available, run `python3 scripts/collect_sources.py`. The copied evidence is already saved; the endpoint is local to the disposable environment and may not remain available later. `scripts/profile_inputs.py` is an additional profile of row counts and revision conflicts.

For the optional PDF visual-render check, install `pypdfium2` into the workspace with `python3 -m pip install --target .local_packages pypdfium2`, then run `python3 scripts/render_pdf_qa.py`. This task's PDFs were rasterized and reviewed as contact sheets. The workbook was reopened and checked with `openpyxl` for sheet counts, table row counts, key totals and native chart objects; no spreadsheet application renderer is installed in the environment.

## Accounting and decision basis

The analysis selects the highest base-case annual incremental contribution among defer, six single hubs and 11 feasible pairs, subject to capex ≤ EUR450,000, ≤7 FTE and no more than two hubs. Low/base/high use 10%/25%/40% volume uplifts; the stress is the specified joint refund/FX shock. Scenario assumptions have no probabilities, and the primary choice rule is an explicit analyst default because the source room contains no board risk weights. NLD+ESP is shown as the stress-resilient alternative; deferral remains available if actual site and operating evidence fails the day-90 gate.

The transaction exports, returns, unit costs, hub options and scenario policy are synthetic. World Bank and ECB observations are saved archived official snapshots, not fresh live research. See the report and workbook for revision handling, exclusions, rounding, cash/contribution boundaries, source vintage and limitations.
