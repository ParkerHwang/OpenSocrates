# Reproduce the paired retest

The input freeze is commit `5742a31aa3e8512c255bdc1d3a706d2df94af0ec`, manifest
SHA-256 `0df6ddf6e4828b13f250eb2561b804a666c0196eabd5f15d410aa7ededc747ef`.
The compared product source is the prior qualified `a6f3414` candidate; the guide8
archive is an independently retained old build. Neither archive is a published1.5
release. Do not substitute the active installed1.4 plugin or another1.5 ZIP.

No new outcome call is necessary to audit committed results. Use Python3.12:

```sh
python3 evals/v1.5/hard-tasks/retest-v1/verify.py --complete
```

This checks the original pre-call input hashes, exact declared tuples/client and
package identities, attempts/failures/null usage, outcome inventories, frozen review
inputs, all lossless timing samples and preserved historical file bytes. Historical
membership is read from the recorded base commit, so later additive evidence does
not invalidate that file-set assertion. A full Git checkout containing that base
commit is required. No original verifier, protocol or result is edited.

For local retained storage, add `--storage /path/to/the/recorded/run` to verify
auth cleanup, protected source and raw timing hashes. The original fixture, oracle
and checkers are reused from `../v1/` and remain excluded from outcome workspaces.
Snapshot text has private fixture paths normalized, with original and exported
hashes recorded separately. Workbook bytes and compressed timing rows are retained
losslessly. Raw event streams, private reasoning, credentials and databases are
not committed. Product memory contains only permitted public synthetic records.

The first lock covers calls and generated artifacts before post-episode checks;
the final lock includes qualification/performance receipts. Review input locks
identify the exact memo/workbook/public-message files. Provisional progress counts
are not final totals. Primary semantic review remains unblinded and is not a human
rating or a changed objective score.

`runner.py` supports `preflight`, `execute`, `qualify`, and `measure` with the
fixed manifest SHA and explicit storage/package/toolchain paths. `execute` uses
exclusive creation; never rerun it over existing outcomes. A future repetition
requires a new versioned evidence directory and a new pre-call freeze. It must
retain both arms, budgets and exact requested tuples, or declare a different task.
