# Reproduce the evidence without another model call

The manifest and original outcome directories are immutable evidence. New checks
belong in a separate temporary directory; never overwrite an old score or repair
a candidate in place. The final report distinguishes original results from any
later diagnostic. No authentication file is needed to read or verify this packet.

## Portable accounting and integrity

From the repository root, after the outcome export is complete:

```sh
python3 evals/v1.5/hard-tasks/v1/verify.py --complete
```

This verifies the pre-outcome manifest, all frozen file digests, every scheduled
cell and attempt, missing usage, exported source hashes, protected-input receipts,
review input locks and outcome lock. It independently recomputes timing counts,
start-cohort throughput and nearest-rank quantiles from the committed lossless
`timing-samples.json.gz` files. It does not invoke Codex, native project memory,
network services or generated application code.

With the original disposable storage still present, also supply
`--storage /private/tmp/opensocrates-hard-run-20260927`. That checks the private
raw timing records against the same calculation, verifies current protected bytes
and confirms each finished profile's temporary authentication copy was removed.
The private storage contains synthetic run material; it is not product memory.

The five reported usage fields are raw client totals with missing values retained
as null. Cached input and reasoning output are subsets of input/output, not
additional categories to sum. `summary.json` distinguishes successful CLI turns,
artifact gates and complete episodes. Tool-action totals count client events;
lexical native-command counts are not native activation/application receipts.

## Artifact checks in a new directory

Coding snapshots are under `results/coding-*/snapshot/`. Their inventory records
the original and exported bytes; inspect any redaction difference before treating
an exported file as identical. The retained Go sources have their own digests.
Use Go1.26.3 and the pinned modernc.org/sqlite1.59.0 dependency. Copy a chosen
snapshot into a new temporary working directory and use an independent cache.
Do not run from the historical snapshot itself.

```sh
go test -race ./...
go build -o /path/to/new/server ./cmd/server
python3 /path/to/repository/evals/v1.5/hard-tasks/v1/coding/acceptance.py \
  /path/to/new/server --source /path/to/new/workspace \
  --output /path/to/new/acceptance.json
```

The checker has 28 isolated groups and retains exact synthetic HTTP requests and
responses. A build or startup failure is evidence, not a reason to patch the old
artifact and replace its result. Source review follows `CODING_REVIEW.md` and
documents consequences of ownership, shared rules, transaction design and tests.

Office snapshots are under `results/office-*/snapshot/output/`. The checker reads
their five artifacts without changing them; Python with openpyxl is required:

```sh
python3 evals/v1.5/hard-tasks/v1/office/check.py \
  /path/to/copied/output --report /path/to/new/office-checks.json
```

Unsupported uncached formulas or missing/unreadable mandatory artifacts remain
unassessable. The original checker label `pending_human_semantic_rubric` is retained;
the actual frozen procedure is `office/PROSE_RUBRIC.md`, which specifies separate
provisional primary review. Human scores are unavailable. A numerical pass does
not erase memo factual errors or workbook unit-formatting defects.

## Backend measurements

Run only after all model calls/builds finish and other benchmark servers stop.
Use the same binary checked by acceptance, with `GOMAXPROCS=4`. The original
host observation is in `host-observation.json`; other hosts produce new evidence.

```sh
python3 evals/v1.5/hard-tasks/v1/coding/measure.py /path/to/new/server \
  --source /path/to/new/workspace --acceptance /path/to/new/acceptance.json \
  --output /path/to/new/performance.json
```

This creates the populated seed through the public API and 12 fresh-state cells
per binary. Throughput credits only successful requests whose start and completion
are inside the measurement window; latency follows every start in that window,
including drain. Failures, carry-in, server CPU and sampled RSS have explicit
scopes. All 28 checks, own tests, protected inputs and conservation must pass for
an eligible performance claim. Otherwise the measurements are diagnostic.
Three load repetitions of one program are not three model replications.

## Original execution and postprocessing

The original runner modes are `preflight`, `execute`, `qualify` and `measure`, each
requiring the manifest hash and explicit storage/package/toolchain paths. Execute
is intentionally non-resumable and refuses existing directories. Do not rerun it
against the original evidence or assume it will skip completed model cells.

In this run, completed office batches were qualified with the unchanged frozen
`runner.qualify` function and locked before prose assessment. After all generation
finishes, `qualify_remaining.py` runs only as-yet-unqualified artifacts. It does
not repeat those office checks or invoke a model. `export_evidence.py` exports
HTTP logs and all timing rows without databases or model event streams;
`analyze.py --storage ... --write` writes exclusive summaries and outcome locks.

Plots use `plot_results.py` with matplotlib3.10.8 in a separate analysis-only
environment. The figure displays grouped checks and episode wall time; it is not
a composite quality score or a significance test. Read-only workbook previews
can have renderer differences: native XLSX styles, formulas and values take
precedence over a preview when diagnosing the candidate.

The package archive digests and before-call client version/launcher digest are
in `manifest.json`. `client-observation.json` explicitly labels the later actual
Mach-O executable digest; it must not be backdated into the original freeze.
Use an available exact historical archive or declare a newly built package as a
new condition. The local1.4 development ZIP is not the published1.4 baseline.
No merge, tag, package publication or active-install change is authorized by
these reproduction instructions.
