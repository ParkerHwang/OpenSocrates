# Meridian Parts reproducibility

The project uses the saved source-room files under `evidence/raw/`. The source-room index and the supplied client metadata are preserved; `TASK.md` and `TOOLING.md` are not modified.

From the project root, run:

```bash
<SHARED_RUNTIME>/python/bin/python3 analysis/reproduce.py
```

The script rebuilds:

- `deliverables/metrics.json` and derived CSVs under `deliverables/data/`;
- `deliverables/source-register.json`, including SHA-256, URL, retrieval time, units, period and synthetic/public status;
- `deliverables/meridian_parts_analytical_workbook.xlsx`;
- `deliverables/meridian_parts_executive_report.pdf`;
- `deliverables/meridian_parts_board_presentation.pptx`; and
- chart PNGs under `deliverables/figures/`.

The workbook and report are generated from the same in-memory data frames as the JSON. The calculation path is explicit in `reproduce.py`: highest order/return revisions, eligibility and cutoff filters, effective-dated unit costs, half-up cents rounding, archived ECB monthly means, World Bank parsing, country/month reconciliation, and the client scenario policy.

The chart layer uses a local `.deps/` installation of matplotlib created inside this disposable project. The bundled Python libraries provide pandas, openpyxl, python-pptx and reportlab. No live client data, credentials, paid service, deployment or account access is used.

If `.deps/` is absent in a fresh disposable copy, install the chart dependency locally before running the script:

```bash
mkdir -p .deps
<SHARED_RUNTIME>/python/bin/python3 -m pip install --no-cache-dir --target .deps matplotlib==3.11.2
```

For a quick core-only check without regenerating documents:

```bash
<SHARED_RUNTIME>/python/bin/python3 -c 'import sys; sys.path.insert(0, "analysis"); import reproduce; c = reproduce.run_core(); print(c["countries"].to_string(index=False)); print(c["recommendation"])'
```
