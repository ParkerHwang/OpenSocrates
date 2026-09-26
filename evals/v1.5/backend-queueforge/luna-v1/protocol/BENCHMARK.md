# Prospective performance and correctness protocol

Status: preparation; exact executable harness hashes are frozen before model calls.
One matched three-session development episode per condition, nine planned model calls
total, all using the same gpt-6-luna/medium/client tuple. No outcome substitution,
extra judge matrix or automatic favorable-result rerun. Model-call runtime cap is
1200 seconds each. Stage3 receives only that arm's own stage2 measurements/errors.

## Common implementation boundary

QueueForge is a Go1.26.3/SQLite API server using standard net/http and database/sql
with modernc.org/sqlite v1.59.0. No UI, external service, real authentication or
external job side effects. Runtime dependencies are predownloaded, locked and
identical. Candidates are free to choose internal modules, SQL schema/indexes,
ownership boundaries and reuse strategy. Benchmarks do not reward a syntax style,
module count or shorter output as a substitute for correctness or less reasoning.

Compare vanilla Codex (no extra plugins or personal instructions), actual released
OpenSocrates1.4, and the repaired unpublished1.5RC package in separate disposable
profiles. Local native memories/import/hooks and
subagents are disabled. Remote-plugin catalog and connector apps are also disabled
in each disposable profile; vanilla must have zero installed plugins and each
OpenSocrates arm exactly its one pinned local plugin before calls. Vanilla and the v1.4 baseline get competent instructions and a maintained
PROJECT_NOTES control; candidate native memory has the same initial facts and
stable task identity. Explicit current guide/schema references are supplied.
No sibling code, previous outcome summaries or evaluator solutions enter a build.
Raw synthetic source/public commands/results stay only in this evaluation boundary;
product memory stores only allowed bounded public intent/checkpoints/references.

## Correctness first

An independent checker uses actual HTTP, two processes sharing one database,
controlled test time, actual prior-stage data and process restarts. It checks
isolation, duplicate creation, stale-worker completion, retry/dead-letter rules,
quota conservation, atomic bulk submission, pagination and acknowledged durability.
Unknown/missing evidence is unassessable, never zero or a pass. Race-instrumented
executables are used for correctness, not performance. Semantic required fields
are checked; compatible extra response fields do not create false failures.

Performance rows retain their correctness qualification. A failing essential gate
means diagnostic-only throughput/latency; a fast incorrect implementation is not a
winner. Preserve all failed attempts and original artifacts. Only the planned
stage3 session may repair the measured artifact; retain stage2 and final separately.

## Workloads and measurements

Use one server process per timed performance cell, GOMAXPROCS4, and a separate
Go load generator with GOMAXPROCS2. Both run on this same connected Mac; no CPU
affinity or dedicated-hardware claim. Capture host/toolchain and background CPU
observations. Do not load different conditions at once. Requests are localhost
only, with redirects and proxy use disabled. The generator reports its own resource
use and scheduler misses so client saturation is visible.

- Read: seeded immutable job IDs; uniform GET selection over 10000 jobs across
  four synthetic tenants. Validate response status/identity and sample full fields.
- Lifecycle: claim then complete against a large ready backlog across four tenants;
  validate tokens, IDs, statuses and completion conservation. Report completed jobs/s
  separately from HTTP requests/s. Idle claims, failed acknowledgements, duplicate
  completion IDs and timeouts are not successful job throughput.
- Closed-loop concurrency1,16,64, with zero think time. Preliminary stage2: one
  fixed3s warmup +8s measurement per workload/concurrency/arm. Final: three repetitions
  of3s warmup +10s measurement. Cycle arm order deterministically by repetition: vanilla/v1.4/v1.5, then
  v1.4/v1.5/vanilla, then v1.5/vanilla/v1.4.
- A final fixed-arrival read sweep at100,500,1000 requests/s uses the same3s+10s
  periods, three repetitions and the same cyclic arm order. Bound in-flight requests
  at256, per-request timeout2s and drain budget3s. Record scheduled versus actually
  dispatched/completed requests, lag, drops and latency from both schedule and send.
  Do not silently omit overload or use successful-request latency as the only view.
  Distinguish full start-cohort outcomes during drain from responses completed
  inside the measurement window. Window-completed RPS/jobs-per-second is the main
  throughput metric; retain both definitions and all censored/drain counts.

Clone a stopped, clean seeded database per measurement cell; do not rewrite private
tables to manufacture expected results. Seed via the public bulk API and retain seed
checks. A lifecycle backlog may be recycled only with newly seeded public jobs;
record idle/drain effects and do not claim saturation from an exhausted queue.
Prepare enough jobs for the bounded run and report the exact seed size and payload.
Use identical bodies and seeds for all three arms. Warmup outcomes do not enter timed
latency/throughput but still count for state conservation.

Report attempted/completed/successful HTTP RPS, completed jobs/s, p50/p95/p99,
errors/timeouts/idle claims, duplicate/lost acknowledgements, server and generator
CPU seconds, peak RSS, final database/WAL sizes and sample counts. Per-request raw
timing samples may be retained as synthetic numeric data. Missing metrics are null.
Root may losslessly gzip per-cell JSON after measurement and remove the stopped
owned cell DB after retaining metrics/conservation. Preserve originals by digest
and retain failed-cell evidence; do not downsample to hide errors or alter scores.
Timeout latencies are censored; identify them rather than inferring complete tails.
Summarize median and observed range across repeated cells. Do not invent statistical
significance or confuse repeated load samples with independent model implementations.

## Stop and interpretation

Cap final performance wall time at30 minutes and total prepared DB data at2GiB;
stop a broken cell on a server crash, repeated transport failure or resource cap.
Report why a metric/cell is unavailable. No uncontrolled target-rate search or
optimization loop. If generator capacity or host noise makes a comparison unclear,
label that cell inconclusive instead of rerunning until an advantage appears.

Keep implementation time, model tokens/cache/reasoning categories and tool actions
separate from the generated API server's performance. One three-condition project can show
observable differences between these artifacts; it does not isolate all causes or
prove general OpenSocrates superiority. Human review, billed cost and independent
backend model echo are not required and remain unavailable unless actually observed.

`plan_objective_measure`: test a more coupled backend using correctness and load
metrics against the real released baseline and fixed repaired candidate.
`do_scope`: nine bounded development calls plus prospective deterministic tests and
repeated localhost loads, with independent prep only outside the treatments.
`check_rule`: qualified performance, fixed budgets/order and complete failure/usage
accounting; retain stage2 and final artifacts separately.
`act_standardize_decision`: report improvements, ties, regressions and limits;
stop at the frozen boundary and do not generalize one generated implementation per condition.

OpenSocrates grounding: pdca-cycle@3

## Luna replication boundary

New disposable projects start from the identical common driver seed. No Sol-generated source, outcomes, reviews, answers or repair hints enter a Luna workspace. The corrected meter is used prospectively, so unlike the earlier Sol study, stage3 may receive valid own-arm performance feedback. Within-Luna comparisons are matched; a causal Luna-versus-Sol gap claim is not supported by these two differing feedback conditions. All changes to orchestration are frozen before calls. No model fallback, escalation or candidate repair by the integrator. The first planned vanilla stage1 call rechecks exact Luna access; on an unchanged global access failure, other calls are skipped. Once access succeeds, two independent builders may run concurrently. Compilation caches are newly primed from the common seed only; prior model-created code or caches are not copied.
