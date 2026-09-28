# Fixed review procedure

Do not send observations, findings, scores or fixes into running subject sessions.
After natural completion, hash-lock each deliverable tree before qualification.
Run candidate code on disposable copies with fresh DATA_DIR. Never repair a
candidate. A checker defect is retained and corrected only as a separately
versioned diagnostic, without changing original scores.

## Coding

Run `api_check.py` against the documented run.sh startup. Retain each HTTP request,
response, duration, and failed check. Restart with the same DATA_DIR; verify stock,
orders and idempotent replay against the locked persistence expectation. Then use
a fresh seeded DATA_DIR for `browser_check.cjs`. Capture real desktop/mobile UI,
console events and the multi-line order/reserve/ship/return/viewer interaction.
Browser plugin is not available in this session; bundled Playwright is the
declared automation. Library-native operation waits are separate from subject
generation: no experimenter-imposed model deadline exists.

Performance runs after outcomes, without another benchmark in flight. Each eligible
backend receives a fresh database and a seeded admin session. At concurrency 1 and
8, execute 500 authenticated inventory GETs and 200 unique draft-order POSTs per
cell. Record every request latency/status, including failures; report throughput,
p50/p95/p99 and error counts. This fixed workload defines the observation, not a
deadline. There is no target RPS. Do not drop errors or compare a backend missing
critical tenant/transaction/retry/correctness behavior as performance-equivalent.
Measure performance independently of self-reported subject load results.

Primary code review (unblinded, no extra model judge): inspect domain invariants,
transaction/concurrency implementation, authorization, reuse and module boundaries,
functional core/side-effect separation where useful, validation, tests, frontend
state and error handling. Functional programming style itself is not a reward.
Record concrete file/line evidence, severity, counterexamples and limits. A code
organization issue, candidate bug, product-guidance defect and harness defect are
different conclusions. Never infer a runtime OpenSocrates defect from any one
generated program bug. Verify the claimed use of guidance from public delivery
events, separately from outcome and causal effect.

## Consulting

Run `office_check.py` without changing deliverables. Inspect all numerical mismatch
details, not just a total. Confirm raw source collection from server request logs
and saved source files/registers. Review units, dates, revisions, exclusions,
currency conversion, return/COGS accounting, denominator handling, scenario
arithmetic, feasibility and report/workbook/deck consistency. Collect artifact
file identities and render representative report/deck/workbook pages. Inspect
legibility, clipping, meaningful charts and whether sources are traceable.

Primary consulting review (unblinded, no extra model judge): assess supported
diagnosis, genuine alternatives, assumptions/sensitivity, grounded recommendation,
defer option, implementation feasibility, owners/gates and measurable KPIs. Look
for unsupported causal claims, invented collection/interviews, factual conflicts,
and executive conclusions not supported by the numbers. Cite artifact evidence.
Missing public messages or artifacts make dependent conclusions unassessable.

## Observation and synthesis

For all 36 intended cells, retain requested exact tuple/arm, client/package/config
hashes, start/end timestamps, elapsed time, all available usage categories, public
messages, timestamped tool starts/completions/failures, lexical repeated commands,
provider errors, malformed events, setup failures, source-room HTTP requests,
sampled process CPU/RSS and host load, artifact hashes and native-memory checks.
Repeated commands are not automatically unnecessary work. Cached input is a subset
of input; reasoning output is a subset of output where supplied. Never sum a
subset twice; missing is null. Numeric reasoning usage is not hidden reasoning.
Report tool duration and waiting time as observed, not inferred internal cognition.

One output per cell supports examples, not significance, model ranking certainty,
profile promotion, billing proof or universal superiority. Report within-tuple
arm comparisons before cross-model descriptions. Keep coding, office, process,
artifact, performance and provisional review conclusions separate. Fast-off config
and live successful calls are stronger evidence than a model catalog, but do not
invent independent backend model/tier echo or account-memory isolation.

First-pass deterministic outcomes are immutable. Findings inform a later explicit
improvement decision; this observational matrix contains no integrator repair lane.
