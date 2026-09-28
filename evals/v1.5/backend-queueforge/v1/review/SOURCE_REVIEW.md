# QueueForge source and handoff review

This is the primary integrator's unblinded source review, after all nine outcome
calls. It is not an independent human score or a frozen model-judge rating. No
generated source was repaired by the integrator. Each arm has one implementation.

## Confirmed failure and its layer

All three stage-2 implementations accepted a changed `retry_base_ms: 1000` under
an idempotency key originally created by the genuine stage-1 executable. They
returned 200 instead of 409. Original-body replay succeeded. This was a generated
application compatibility defect, not a demonstrated OpenSocrates runtime defect.
The planned final sessions repaired it and all three independently passed the
same 19-scenario checker. The actual old executables, database transitions,
source hashes and earlier failed outcomes remain retained.

The candidate's full self-test suite still fails `TestLifecycleAndIsolation`.
The test was created in its own stage-1 session, not supplied in the common seed.
It creates a job without `retry_base_ms`, advances the clock to the expired lease
deadline, and expects immediate reclaim (`internal/queue/http_test.go:53,94`).
Stage 2 explicitly changes the default to 1000ms. `resolve` correctly applies that
default (`http.go:113`); expiry schedules from the old deadline (`store.go:331`).
The null claim at time 1150 is therefore correct. The test should have explicitly
requested zero delay for its existing lifecycle purpose, or checked 2150 for the
new default. Neither alteration was made here.

The candidate's public messages repeatedly describe this self-authored assertion
as a supplied test that must remain unchanged. The common instruction protects
only the supplied driver helper/test and locked module files. Extending that
restriction to its own test is an instruction-scope and maintenance error. Its
checkpoint retains a broader description of the protected tests; this is an
observed persistence of the interpretation, not proof that memory caused it.
The final answer accurately disclosed the failing suite. API behavior, truthful
reporting and incomplete test maintenance are separate findings. The frozen
artifact gate remains false; performance is reported as diagnostic for this arm.

## Reuse and separation

| Topic | Vanilla | OpenSocrates 1.4 | OpenSocrates 1.5 RC |
| --- | --- | --- | --- |
| HTTP / persistence | Separate `http.go` and `store.go` | Combined in `service.go` | Separate `http.go` and `store.go` |
| Single / batch policy | One `normalize` and `Store.Submit` path | One normalization and `submit` path | One `resolve` and `Store.Submit` path |
| Atomic mutation | Shared `Store.write` | Shared `Service.write` | Shared `Store.write` |
| Lease state changes | Distinct typed methods for heartbeat/complete/fail | Common lifecycle handler, including cancellation | Shared `LeaseAction` switch; separate cancellation |
| Pure helpers | Scheduling/retry calculation and input checks | Normalization/canonicalization/backoff | Input/default resolution; retry formula within store |
| Domain Go lines / test Go lines | 1074 / 598 | 1003 / 527 | 993 / 574 |

Counts include the common driver and executable and describe size only. They do
not score maintainability. Both vanilla and the candidate have useful separation
of HTTP concerns from storage. All three reuse real transactional paths across
single/batch operations. The candidate's common lease method reduces repeated
fencing logic but couples multiple operations to an action string and switch;
vanilla's distinct methods have more explicit parameter contracts. The baseline's
924-line service puts routing, validation, SQL and response composition together,
which makes isolated storage reuse less direct. None is primarily a functional
programming implementation; imperative SQL transactions are central in all three.
There is no evidence that only an OpenSocrates condition can produce reusable code.

## Durability, concurrency and performance interpretation

All three use SQLite WAL, explicitly select synchronous=FULL, restrict each SQL
pool to one connection, and serialize mutations with BEGIN IMMEDIATE. The API
checker uses race builds, independent server processes on one DB, real stage-1
state, lease fencing and SIGKILL/restart checks. No candidate removes fsync or
replaces durable writes with an in-memory response to improve benchmark numbers.

The 1.4 implementation also reasserts synchronous and busy timeout on each acquired
write connection (`service.go:207`); the other two set those at startup. Connection
replacement/fault injection and physical power-loss durability were not tested.
WAL plus the process-crash checks do not prove power-loss behavior on every disk.

Claim indexes lead with tenant, queue, state and priority/creation order. Expiry and
inflight checks have matching state/deadline indexes. The baseline and candidate
also add pagination indexes. Candidate claims read a job once and construct its
updated leased projection; vanilla and 1.4 fetch the job after the update. These
are observable SQL/ownership choices, not an established cause of any timing gap.
All servers serialize requests at the one-connection pool, so more client
concurrency need not increase throughput. No distributed worker or external job
side-effect exactly-once guarantee is claimed.

The fixture uses synthetic tenant headers, localhost, one machine, a 50,000-job
backlog and 256-byte payloads. Production authentication, TLS, deployment,
retention, failover, slow-client exhaustion, connection churn and large-payload
capacity are outside its acceptance boundary. The fixed-arrival sweep reaches
1000 requests/s; it does not determine the maximum sustainable production rate.

## Evaluation-tool defect

The original load timer cancelled closed-loop requests at the warmup boundary.
Its six executed cells are invalid meter observations, not zero-throughput
servers. Version 2 repairs the timer, adds a realistic-duration regression, and
measures identical frozen binaries. No candidate receives those new results for
another optimization pass. Stage-3 correctness repair is observed; optimization
informed by valid external performance feedback is not established.

The new comparison explicitly disables account-remote plugins and apps before
verifying vanilla's empty plugin inventory. A fresh CODEX_HOME alone had not
achieved this in preflight. Older studies remain unchanged and are not silently
credited with this stronger control. Account-side native-memory transfer remains
unproven. Installed-package references, successful native operations and observed
artifacts are separate from universal hook or method-application proof.
