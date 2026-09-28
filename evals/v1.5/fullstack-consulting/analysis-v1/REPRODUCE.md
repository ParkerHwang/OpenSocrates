# Reading and reproducing the analysis

The frozen generation cohort is `../v2/manifest.json`; the qualified candidate
package/source is unchanged. All qualification versions preserve their original
results. Do not overwrite a result directory, repair a candidate, or launch another
outcome model to reproduce this analysis.

The recorded analysis commands, run from the repository root, were:

```text
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/qualification-v1/qualify.py office --storage <original-storage> --workroot <fresh-resolved-per-user-temp>
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/qualification-v1/qualify.py coding --storage <original-storage> --workroot <fresh-resolved-per-user-temp>
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/qualification-diagnostic-v1/diagnose.py <original-storage> <separate-resolved-temp>
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/qualification-diagnostic-v2/diagnose.py <original-storage> <separate-resolved-temp>
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/qualification-diagnostic-v3/diagnose.py <original-storage> <separate-resolved-temp>
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/qualification-mobile-v1/diagnose.py <original-storage> <separate-resolved-temp>
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/analysis-v1/office_semantics.py --storage <original-storage>
PYTHONDONTWRITEBYTECODE=1 python3 evals/v1.5/fullstack-consulting/analysis-v1/synthesize.py
python3 evals/v1.5/fullstack-consulting/analysis-v1/write_tables.py
```

Qualification results are now exclusive historical receipts. Existing result
directories are intentionally skipped or rejected. A necessary retest requires a
new declared diagnostic version with its own input hashes, scope and result paths.
No such retest is needed to inspect the committed evidence.

`office_semantics.py` reads original locked metrics and compares pair effects to
country sums. Two workbook-only pair representations were checked separately in
`office-pair-workbook-checks.json`; their exact cell references and input hashes
are retained. `synthesize.py` and `write_tables.py` regenerate the derived summary
from the preserved receipts. Empty CSV fields are missing/not applicable, never
imputed zero; `summary.json` is authoritative for structured/null values.

The original local storage is recorded in the task handoff and untracked mutable
`monitor-state.json`. Public artifacts live under `../v2/results/*/artifact-export`.
Their export maps explicitly identify redacted bytes. Full unchanged dependency
caches remain in the local boundary; publication manifests identify omitted files
and exact distributions. Follow `../PUBLICATION.md` on another machine. Do not
assert byte-identical reconstruction or original-source qualification from a
redacted copy without checking the recorded maps and inventories.

The evaluation host was Apple-silicon macOS, with sandbox-exec, Python3.12.14
servers and the frozen Playwright/Chromium paths. The coordinator used
Python3.14.4. These commands are exact historical commands with named path
placeholders, not an instruction to copy the author's credentials or alter global
settings on another machine. The repository and receipts are sufficient to
understand and review results without authentication files.

Document inspection used `inspect_documents.py`, the bundled Python3.12.14
libraries, Poppler and LibreOfficeDev26.8. Workbook range imports/renders used
`render_workbooks.cjs` with bundled `@oai/artifact-tool`, using its declared public
APIs only. The local `workbook-source.json` jobs are intentionally unpublished
because they contain scratch paths. Inventories bind source hashes, selected
pages and ranges. Native workbook cross-checks converted the unmodified XLSX to a
separate PDF through a fresh LibreOffice profile and inspected the first page;
the original hash was rechecked. Full derivative conversions remain local;
representative images and receipts are committed.

Static figures were produced with `plot_results.py` using task-local
matplotlib3.11.2, numpy2.5.3 and pillow12.3.0. Those installations did not modify the
candidate environments or active plugin. Final figures were visually inspected.
No hidden reasoning text, additional model judge or human score was collected.
