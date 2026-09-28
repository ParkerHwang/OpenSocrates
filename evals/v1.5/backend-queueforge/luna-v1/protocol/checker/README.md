# QueueForge independent API checker

Python standard library; no dependency installation or candidate source access.
All traffic is synthetic HTTP on loopback. The executable starts with documented
flags and its first stdout JSON line determines the port. Each scenario owns a
fresh temporary DB and atomically updated clock; every owned process is stopped.

```
python3 protocol/checker/acceptance.py --binary /absolute/bin/queueforge-race \
  --stage 1 --output /absolute/new-stage1.json
python3 protocol/checker/acceptance.py --binary /absolute/bin/current-race \
  --stage 2 --legacy-binary /absolute/bin/stage1-race --output /absolute/new-stage2.json
python3 protocol/checker/acceptance.py --binary /absolute/bin/final-race \
  --stage 3 --legacy-binary /absolute/bin/stage1-race --output /absolute/new-final.json
cd protocol/checker && python3 -m unittest -v test_checker.py
```

Output uses exclusive creation (`x`); existing reports are never overwritten.
Pass exits 0; failure, error, missing legacy binary, and unassessable gates exit 1.
Missing measurements are null. This is correctness acceptance, not load testing.
A missing/unassessable essential gate cannot qualify performance.

`Runner(binary, stage, legacy_binary=None, temp_root=None)` and `Fixture` are
importable process/request helpers; `Runner.run()` returns the JSON report.
`Fixture.start()`, `set_time(milliseconds)`, and `close()` manage public process
lifecycle. `Runner.request(...)` records each HTTP attempt including request,
response, expected status/code, elapsed time and transport errors. Diagnostics
retain bounded stdout/stderr; DATA RACE detection remains sticky even if old log
bytes are truncated. Race-instrumented executables are caller supplied.

Stage 1 checks semantic JOB/envelope fields, validation and state invariants,
logical static-default idempotency (including time advancement and key ordering),
tenant/endpoint namespaces, two-process identical enqueue/claim contention,
atomic bulk rollback and key reuse, heartbeat, exact deadline expiry, stale-token
fencing, attempt/dead-letter accounting, result persistence, exact completion
replay, and acknowledged lease/completion/idempotency SIGKILL restart.

Stages 2/3 add priority/FIFO scheduling, future-job nonblocking, fail/expiry retry
boundaries and cap, joint pending/inflight quotas, terminal capacity release,
quota-safe replay and bulk rejection, cancellation and cancellation/completion
races, snapshot listing during insertion/state change and cursor tenant/filter
binding. Migration uses a genuine previous executable to populate the DB, then
starts two current processes: old live lease/token, attempts, completion result,
zero historical policy, original-body replay and changed-command conflict are
checked. An explicitly future user_version fixture containing a sentinel table/row
must fail startup without changing DB bytes, version, schema or data. The report
retains the original DB bytes as base64 plus before/after hashes and byte counts. No private tables are fabricated for migration.

Each independent scenario starts fresh. Setup failure marks the scenario
unassessable and dependent checks are not attempted. Other assertions stop only
that scenario and preserve its request journal. Expected 4xx responses count only
with tested follow-up state invariants. A temporary 503 is bounded-retried **only**
for concurrent enqueue with exactly the same body/key, at most three total HTTP
attempts per worker; every attempt remains recorded. Transport failures, claims,
fails, and performance requests are never blindly retried. Remaining unavailability
is unassessable. Requests have a three-second socket timeout and a total request socket-shutdown
deadline, the checker stops
starting work at 165 seconds, and a 175-second process watchdog kills owned
servers to bound stalled HTTP and finish below the 180-second budget.

Fifteen deterministic controls include scripted localhost boundaries that reject
duplicate batch IDs,
partial invalid-batch writes, false-success stale-token completion, wrong retry
delay and wrong conflict codes; compatible batch/conflict controls pass. A slow localhost
header control also confirms the total request deadline. Additive GET/completion
JOB fields pass while required-field changes or omissions fail. Future-store
controls accept unchanged refusal and reject mutation despite retained user_version. These
fixtures are canned responses, not a reference implementation.

Limits: finite sampled concurrency does not prove absence of every race. HTTP plus
SIGKILL demonstrates acknowledged process-crash recovery, not power-loss/faulted
fsync durability. WAL, synchronous=FULL, transactional schema migration, dependency
lock and reused source paths require the separate source review. Resource metrics
are not measured here. The checker does not execute payloads or test external job
side effects, authentication, TLS, or production security.
