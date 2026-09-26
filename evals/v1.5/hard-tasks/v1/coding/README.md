# AuditLedger benchmark packet

This is preparation material, not a candidate solution or outcome evidence.
`TASK.md` is the candidate instruction. Copy only `starter/` into its coding
workspace and supply the task. The starter executable deliberately exits TODO.
No acceptance/performance tool is meant to run during the model episode.

The pinned Go module and sum were sourced solely from the common generic
QueueForge dependency seed; no candidate snapshots or outcome contents were
read. The platform wrapper/test registers and probes SQLite without ledger logic.
The legacy producer creates real v1 tables with final balances, movements, and
preserved notes. `oracle.json` documents separately calculated known values.

Run after building the candidate (source root identifies exactly which code was
checked; no source contents are copied into result bundles):

```
python3 acceptance.py /absolute/server --source /absolute/candidate --output /absolute/acceptance.json
python3 measure.py /absolute/server --source /absolute/candidate --acceptance /absolute/acceptance.json --output /absolute/measure.json
```

Callable interfaces are `acceptance.run_checks(binary, output, source=None,
startup_timeout=10, only=None)` and `measure.measure(binary, output,
acceptance=None, source=None)`. `output` is a JSON filename. Acceptance has 28
independent groups and fresh state for each; failures do not stop later groups.
Artifacts include server logs, real v1 database fixtures, exact synthetic HTTP
requests/responses, source file hashes, binary hash, and failing traceback.

The meter first prepares 10,002 entries using 250 public batch requests. It stops
the seed process and uses SQLite backup to retain WAL state, then clones that
same volume into each of exactly 12 serial cells: read/write × concurrency 1/16
× 3 repetitions. Read requests use a fixed populated historical snapshot;
posting requests alternate one-unit transfers per worker. Cell databases are
fresh clones, not cumulative state. Each cell uses 1 second warmup, 5 seconds
measurement, and bounded 3-second request drains. There are no request retries.
Never overlap the meter with model calls, other performance cells, or builds.

Raw attempt records retain warmup and measured starts/completions, latencies,
HTTP failures, and exact failed request/response. In-window throughput counts
successful completions during the half-open measurement window (warmup requests
completing in that window are included and separately identifiable). Latency
quantiles describe requests started in the measured window, including failures
and late drains. Final conservation and posting/version counts include ALL
successful warmup, measured, and drained requests. Throughput remains diagnostic
if any cell fails conservation or if matching-binary full acceptance is absent,
failed, or unknown. Missing observations are JSON null, never fabricated zeros.
CPU is the server process CPU delta across warmup/measurement/drain; RSS is a
sampled peak, not a guaranteed process maximum. Both are null if unavailable.

`python3 acceptance.py --selfcheck` and `python3 measure.py --selfcheck` check
checker primitives using deliberate bad status/body controls, response extension
tolerance, genuine old schema checks, and failed/late boundary-window records.
No selfcheck implements a ledger backend; a model-produced solution is still
required for a positive end-to-end acceptance run.

Integrator pre-freeze clarification: throughput credits only successful requests
that both start and complete in the measured window. Warmup carry-in completions
are counted separately; start-cohort latency includes drained requests. Models see
the task and generic starter, not the post-episode checker or oracle.
