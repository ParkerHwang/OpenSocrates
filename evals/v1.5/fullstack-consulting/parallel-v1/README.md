# User-authorized concurrency amendment

The user explicitly requested the maximum practical simultaneous execution after
the original three-worker schedule proved too slow. This amendment changes only
queue scheduling and its provenance. All 36 identities, tasks, sources, exact
model/effort/client/package tuples, isolation, Fast OFF, unlimited individual
resource budgets, artifact checks and outcome-retention rules remain unchanged.
No subject is coached, interrupted, restarted or repaired.

- `plan_objective_measure`: remove avoidable queue delay. Observed baseline was
  17 naturally completed, 3 active and 16 queued. The connected Apple M5 has 10
  cores and 32 GiB RAM; the read-only memory-pressure probe reported 59% available
  and zero swap used before dispatch. These are observations, not a capacity SLA.
- `do_scope`: transfer all still-unclaimed queued cells to a new executor with one
  worker per transferred cell. Existing subjects and their observer keep running.
- `check_rule`: use atomic exclusive directory publication. An existing result
  directory always belongs to the original executor and is never replaced. The
  original executor sees an explicit administrative transfer marker and skips
  that queue entry; the new executor verifies ownership and refuses any existing
  call receipt. Count each subject once and preserve all failures/null usage.
- `act_standardize_decision`: adopt the requested concurrency for the remaining
  fixed matrix. Do not expand the task count or infer better model performance.
  Observe actual overlap, resource pressure, provider errors and natural endings.

`manifest.json` is frozen before any transfer or new-executor outcome call;
`dispatch.json` freezes actual ownership before the new executor starts. A
`skipped.json` with reason `transferred_to_parallel_v1` is an administrative marker
for the old queue, not a skipped outcome. Original frozen files are unchanged.
The new runner is a reviewable copy of the frozen runner with only path selection,
ownership checks, scheduling and provenance additions; the model command, prompt,
profile and outcome checks are unchanged. No process receives a signal.

Per-call elapsed times and self-reported load tests may now reflect greater host
and account contention. Already-running subjects can overlap the new regime.
Preserve the amendment timestamp and per-call provenance; do not pool timings as
if concurrency were unchanged. Independent performance qualification still runs
serially after outcomes. Backend concurrency capacity and billing remain unknown.
Provider failures are retained; no automatic outer retries or hidden substitutions.

OpenSocrates grounding: pdca-cycle@3 (primary scheduling decision; application unverified).
