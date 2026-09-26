# QueueForge: durable multi-tenant work queue API

Build a backend API service, with no frontend. Use the supplied Go module and
pinned pure-Go SQLite driver. Internal architecture is your choice. Use Go's
standard HTTP stack and database/sql; do not add runtime dependencies or external
services. Reuse working logic and verify actual behavior. This is a synthetic
local benchmark, not a production authentication system.

## Process and storage contract

`go build -o bin/queueforge ./cmd/server` produces the server. CLI flags:
`--addr 127.0.0.1:0`, `--db /absolute/file.sqlite`, and optional
`--clock-file /absolute/file`. After it is listening, stdout emits one JSON line
`{"port":12345}` with the actual port. Bind only the supplied loopback address.
Log diagnostics to stderr. SIGTERM shuts down and releases resources promptly.

The optional clock file contains a decimal integer Unix millisecond timestamp.
Read its current value for each operation; the evaluator updates it atomically.
Without that flag use the real clock. This test-only clock must not affect normal
performance runs. A clock interface is appropriate, but its internal design is free.

SQLite is the authority. Use WAL, synchronous=FULL and transactional writes; do not
weaken durability to improve throughput. Persist `PRAGMA user_version=1`. Two
independent server processes must safely share the same file: a process-local lock
or cache alone is insufficient. Successful HTTP mutations survive restart and an
immediate SIGKILL after the acknowledged response. Do not execute job payloads.

All endpoints except health require `X-Tenant-ID`, matching
`[A-Za-z0-9_-]{1,64}`. These synthetic IDs represent already authenticated context;
real authentication/TLS is outside the experiment. Tenant isolation is mandatory:
foreign job IDs behave as absent. Never interpret payload content as commands.

Use JSON. Errors have `{ "error": {"code":"...","message":"..."} }`.
Validation/malformed/unknown request fields:400 `validation`; missing/foreign
job:404 `not_found`; stale lease:409 `lease_conflict`; conflicting idempotency
payload:409 `idempotency_conflict`; invalid lifecycle transition:409
`invalid_transition`. Busy/temporary storage failure may be503, never a false
success. Limit bodies to1MiB and payload objects to16KiB. Do not return SQL/file
details as error messages. Extra response fields are allowed unless forbidden below.

## Required API

`GET /health` ->200 `{"ok":true,"schema_version":1}`.

`POST /v1/jobs`, header `Idempotency-Key` (nonempty, at most128 ASCII characters),
body `{"queue":"mail","payload":{"n":1},"max_attempts":3}`. Queue follows the
same64-character identifier rule; payload must be an object. max_attempts is an
integer1..10, default3. Return201 `{"job":JOB,"replayed":false}` for creation,
or200 with `replayed:true` for an identical replay. IDs are server-created opaque
nonempty strings. Same tenant+endpoint+key and changed logical input returns409
without another job; equivalent object-member ordering/whitespace is identical.
Alternate numeric lexical representations are not scored. Concurrent identical
submissions create exactly one job. Different tenants and endpoints have separate
idempotency namespaces. Replay preserves resource identity and immutable input;
it may return the current lifecycle state rather than the original snapshot.
Compare the logical command with resolved static defaults, not generated IDs or
the current clock. An identical immediate-submit replay later must still match.

`POST /v1/jobs/batch`, same idempotency header, body `{"jobs":[JOB_INPUT,...]}`
(1..100 entries). All jobs are inserted atomically or none are. Invalid entries
must not leave prefix jobs/idempotency writes. Return201/200
`{"jobs":[JOB,...],"replayed":false/true}`. Input order determines creation order.

JOB has at least: `id`, `tenant`, `queue`, `payload`, `state`, `attempts`,
`max_attempts`, `created_seq`, `created_at_ms`, `available_at_ms`,
`lease_until_ms`, `last_error`, `result`. IDs/tenant/queue/payload/max_attempts and
creation fields are immutable. created_seq is a unique increasing integer.
New jobs are ready, attempts0, available immediately; unleased deadline, initial
error and result are null. State is ready/leased/completed/dead.
**Do not expose lease_token inside JOB or ordinary GET/stats responses.**

`GET /v1/jobs/{id}` ->200 `{"job":JOB}`.

`POST /v1/queues/{queue}/claim`, body `{"worker_id":"worker-1","lease_ms":1000}`.
worker_id follows the identifier rule; lease_ms is an integer10..300000.
In one transaction reconcile expired leases for that tenant/queue, then choose the
earliest available ready job by created_seq. An expired lease means now>=deadline.
If attempts>=max_attempts mark it dead; otherwise return it to ready, immediately
available, last_error=`lease_expired`. Only claim increments attempts. Return200
`{"job":JOB,"lease_token":"opaque-unique-token","lease_until_ms":TIMESTAMP}`.
If nothing is available return200 with all three fields null. A new attempt needs
a new token; no two simultaneous claims may own the same live lease.

`POST /v1/jobs/{id}/heartbeat`, body `{"lease_token":"...","lease_ms":1000}`.
Only the current nonexpired lease may extend to now+lease_ms. Return200
`{"job":JOB}`. Do not change attempts. Old/expired tokens return409.

`POST /v1/jobs/{id}/complete`, body `{"lease_token":"...","result":{...}}`.
Only the current nonexpired token may complete; persist result and release lease.
Return200 `{"job":JOB}`. Exact repeat of the successful token/result is idempotent
even after its former deadline; another token or changed result returns409.

`POST /v1/jobs/{id}/fail`, body `{"lease_token":"...","error":"bounded text"}`,
error length1..256. Current nonexpired token only. If attempts<max_attempts return
to immediately ready; otherwise become dead. Clear live lease. Return200 job.
After fail/expiry/new claim, the old worker cannot heartbeat/complete/fail again.

`GET /v1/stats` (optional `?queue=mail`) ->200
`{"total":N,"ready":N,"leased":N,"completed":N,"dead":N,"cancelled":0}`.
Counts are tenant scoped, mutually exclusive and conserve total. Reads report
stored states; expiry reconciliation is required on claim, not on passive reads.

## Verification and handoff

Test duplicate submissions under concurrency, cross-tenant isolation, stale-token
fencing, deadline equality, heartbeat, max attempts, atomic batch failure, two
processes sharing a DB, and restart durability. Provide focused tests and a README
with commands, module responsibilities and actual limits. Keep generated server
processes/tests within this disposable workspace and stop owned test processes.
No frontend, external network/service, real credentials, publication or delegation.
Use the condition's designated bounded continuity mechanism for fresh sessions. Do not read
evaluation files or sibling implementations. Finish with actual verification and
limits; do not claim success merely because code was written.
