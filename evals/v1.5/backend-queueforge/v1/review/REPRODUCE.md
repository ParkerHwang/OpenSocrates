# Read and reproduce the QueueForge evidence

Start with [the comparison](REPORT.md) and [the source review](SOURCE_REVIEW.md).
The three unchanged final source trees are:

- [Vanilla](../snapshots/vanilla/stage3/README.md)
- [Released OpenSocrates 1.4 condition](../snapshots/v1.4.0/stage3/README.md)
- [Repaired OpenSocrates 1.5 RC condition](../snapshots/v1.5.0-rc/stage3/README.md)

The initial/migration/final task contracts are in `../protocol/stage1.md`,
`stage2.md`, and `stage3.md`. The genuine preceding stage-1 source is retained for
each condition. There are no integrator source repairs in these folders.

From the compact export root, validate hashes and accounting without a model:

```sh
python3 review/verify_export.py
```

For one condition's actual behavior, use Go1.26.3 with its locked dependencies.
Run `go test -race ./...` in its stage-3 directory. This command is expected to
fail the documented obsolete lifecycle assertion for the candidate; do not change
it to make this original artifact pass. Downloading the pinned public modules may
be necessary on a new machine. No credential or external database is needed.

Build normal and race executables from an unchanged source tree into an unused
temporary output directory. Example from the export root:

```sh
queueforge_output="$(mktemp -d)"
(cd snapshots/vanilla/stage1 && go build -race -o "$queueforge_output/legacy" ./cmd/server)
(cd snapshots/vanilla/stage3 && go build -race -o "$queueforge_output/final-race" ./cmd/server)
(cd snapshots/vanilla/stage3 && go build -o "$queueforge_output/final" ./cmd/server)
python3 protocol/checker/acceptance.py --binary "$queueforge_output/final-race" --stage 3 --legacy-binary "$queueforge_output/legacy" --output "$queueforge_output/checks.json"
```

Use the corresponding same-arm legacy executable when checking another condition.
Inspect the JSON scenario statuses; the API checker and self-tests are distinct.
These toy executables use POSIX absolute paths and synthetic tenant headers. The
observed environment was Apple-silicon macOS, not a production deployment or a
portable platform-support certification for the toy server.

The repaired load tool can be rebuilt and checked independently:

```sh
(cd benchmark-v2/loadgen && go test -race ./... && go build -o loadgen . && ./loadgen --selfcheck)
python3 -m unittest discover -s benchmark-v2 -p 'test_*.py' -v
```

`benchmark-v2/runner.py` exposes `prepare_seed` and `run_cell`. For a new measurement,
use a new output directory and freeze the workload and execution order first.
The original exact 18/81 schedules are in the manifests. Do not run the historical
model runner or mutate this result bundle to recreate an outcome. Local paths in
archived manifests/scripts are replaced by declared `$STUDY`, `$PRODUCT` and
`$BUNDLED_CODEX` placeholders, so they are provenance, not directly runnable model
setup scripts in this portable export.

`summary.json` and `performance-cells.csv` retain all corrected cells and gate
states. Original invalid load summaries are retained separately. Full raw timing
samples are excluded from this compact public bundle; SHA-256 compression receipts
and the independent numeric audit bind the local evidence. Aggregate receipts
cannot reconstruct every raw percentile without those local samples. The public
export manifest lists original and exported file hashes and every transformation.
