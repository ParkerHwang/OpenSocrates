# Independent bounded load tooling

This directory contains tooling, not a QueueForge implementation. Go1.26.3 stdlib
load generator and Python stdlib orchestration are independent of candidate code.
No candidate executable was run during preparation. All HTTP is loopback127.0.0.1,
with proxy and redirects disabled. Public bodies use four synthetic tenants and a
payload object whose compact serialized UTF-8 JSON is exactly256bytes.

Build and controls:

```sh
cd benchmark/loadgen
go build -o loadgen .
go test -race ./...
./loadgen --selfcheck
cd ../..
python3 -m unittest discover -s benchmark -p 'test_*.py'
python3 benchmark/runner.py --selfcheck
```

The selfcheck uses an ephemeral tiny HTTP mock: controlled5ms response delay,
known immutable identity, one claim/completion followed by idle claims, malformed
JSON responses, exact100rps dispatch count, and drain/counter predicates. An additional200ms slow read control starts10requests
in the100ms measure window: all10complete in drain, cohort completions remain10,
window completions and successful RPS are0. Unit
controls additionally cover timeout/error classification, null empty percentiles,
known median, resource collection and database size cap. These are tooling tests;
they do not establish candidate correctness or API implementation quality.

Import `benchmark/runner.py` with importlib or add benchmark to sys.path:

```python
seed = prepare_seed(binary: Path, output_dir: Path, env: dict | None = None)
row = run_cell(binary: Path, seed_metadata: dict, config: dict,
               output_dir: Path, env: dict | None = None)
```

Output directories must be new. `prepare_seed` publicly submits500 batches of100
jobs (125batches per tenant), validates their bodies and tenant stats, stops its
producer, runs SQLite metadata-only WAL checkpoint(TRUNCATE) with busy0, reopens
through the candidate HTTP API to verify counts and representative IDs, stops and
checkpoints again. No private tables/schema are read or modified. It returns `db`,
`refs` (10000jobs,2500per tenant), `lifecycle_refs` (all50000jobs), seed checks,
checkpoint tuples and resource measurements; seed.json retains the same metadata. Seed preparation has an absolute120s work
deadline, including startup/reopen/checkpoints; bounded owned-process cleanup may
follow expiry. Public seed/stats calls have a2s absolute total request deadline
covering trickling headers and bodies, enforced by shutdown of the owned socket.
`run_cell` clones this clean stopped DB, starts one server GOMAXPROCS4, runs a
separate generator GOMAXPROCS2 and stops owned processes. It returns result.json.

`config` keys: workload read|lifecycle; concurrency1|16|64; rate0 for closed-loop
or100|500|1000 for final fixed-arrival read; warmup_seconds3; measure_seconds8 for
stage2 or10 for stage3. Optional stage/arm/repetition tags are retained. Root owns
paired/cyclic arm ordering and correctness qualification. Do not overlap server
loads with model builds. Single-arm CLI is available:

```sh
python3 benchmark/runner.py --binary /absolute/server --stage 2 \
  --arm label --output /absolute/new-directory
```

Stage2 runs one repetition of six closed-loop cells. Stage3 runs three repetitions
of the same six cells plus100/500/1000rps read cells. Root scheduling should use
run_cell directly to alternate arms. User-authorized third-arm extension sets the
prospective global final wall cap to30minutes; CLI enforces30minutes for its own
suite. Root must enforce the shared global wall cap and2GiB aggregate database
cap across all arms. Each cell checks its parent tree's DB/WAL/SHM bytes, has a60s
outer deadline,2s per-request timeout and3s drain. Twenty consecutive transport
failures stop generation; server crash or resource cap makes a cell unavailable.
No favorable reruns or target-rate search.

Result schema: phases.warmup and phases.measure retain cohort_attempts,
cohort_completed_requests, cohort_successful_http, cohort_completed_jobs (also
available under the original count names). These include responses during drain.
window_attempts, window_completed_requests, window_successful_http and
window_completed_jobs require dispatch/response completion inside the corresponding
window. All RPS fields use these window counts divided by window duration.
drain_completed_requests, drain_successful_http and drain_completed_jobs are
separate. Warmup cohort responses finishing in measure remain excluded from measure
throughput. Raw samples include finish_offset_ms.

Other phase fields include attempts, completed_requests
(HTTP response obtained), successful_http (correct status/body), their separate
RPS, completed_jobs and completed_jobs_per_second, errors/timeouts/idle_claims,
duplicates/status_counts/sample_count, drops, scheduled_count (null closed-loop),
scheduler_misses (lag greater than one arrival interval), send_latency_ms,
scheduled_latency_ms and scheduler_lag_ms p50/p95/p99. Latencies include failed
requests, not only useful successes; timeout tails are marked censored. `samples`
retain synthetic per-request identity, tenant, phase, operation, status, send and
schedule offsets, both latencies, lag, errors and validity. Warmup cycles crossing
the boundary remain warmup, including their completion acknowledgement.

Lifecycle claim IDs must exist in the50000seed manifest for the responding tenant;
job required fields, immutable values, payload, attempt/state and acknowledgement
result are checked. A bad parse/body never contributes useful throughput.
Duplicate claims/acks are scoped by tenant+ID. claimed_unique, acknowledged_unique
and lost_acknowledgements include warmup. Conservation retains initial/final public
stats for every tenant, checking total/state conservation and final completions
against acknowledged jobs; read cells must preserve all states. Idle queues and
unacknowledged leases remain visible. No exactly-once external-effects claim.

server_resources/generator_resources report owned PID CPU seconds and peak RSS
from wait4 resource usage (server process lifetime includes startup, warmup and
public stats; generator lifetime includes warmup/measure/drain). resource_samples
retain timestamped ps PID/RSS/CPU time/%CPU/state every~200ms. DB/WAL byte sizes are
recorded before load, at measure end before shutdown, and after shutdown. Unknown
metrics are null. Peak RSS is a process high-water mark, not sampled RSS maximum.
Missing metrics and unavailable cells must not be translated into zeros or passes.

This is a shared Mac with no affinity or dedicated hardware. Closed-loop latency
limits offered work; fixed arrivals expose overload through lag and dropped work.
Root must report host/background observations, correctness qualification, capacity
flags, medians and observed ranges across cells. Repetitions are repeated workload
samples, not independent model implementations. Per-model development runtime,
usage/cache/token categories and tool actions belong to root's separate generation
ledger; stage3 feedback may summarize only that arm's observed checks/load rows.
