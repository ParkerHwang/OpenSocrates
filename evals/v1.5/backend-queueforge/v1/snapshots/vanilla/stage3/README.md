# QueueForge

QueueForge is a local, durable, multi-tenant work queue API. It stores jobs and lease state in SQLite. The `X-Tenant-ID` header is a synthetic already-authenticated tenant context for this benchmark.

## Build and run

Use Go 1.26.3 with the pinned module files. No external service is needed.

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db /absolute/path/queue.sqlite --max-pending 100000 --max-inflight 100000
```

The server writes `{"port":12345}` to stdout once it is listening. It writes diagnostics to stderr. Optional `--clock-file /absolute/path/clock.txt` reads a Unix millisecond integer from that file for each request. It is intended for local tests. Send SIGTERM for graceful shutdown.

Example:

```sh
curl -X POST http://127.0.0.1:12345/v1/jobs \
  -H 'X-Tenant-ID: demo' -H 'Idempotency-Key: first' \
  -H 'Content-Type: application/json' \
  --data '{"queue":"mail","payload":{"n":1},"max_attempts":3}'
```

Other routes are `GET /health`, `POST /v1/jobs/batch`, `GET /v1/jobs/{id}`, `GET /v1/jobs?queue=mail&limit=50&cursor=...`, `POST /v1/queues/{queue}/claim`, `POST /v1/jobs/{id}/heartbeat`, `POST /v1/jobs/{id}/complete`, `POST /v1/jobs/{id}/fail`, `POST /v1/jobs/{id}/cancel`, and `GET /v1/stats?queue=mail`. Submit inputs accept `priority` (-10..10), `run_at_ms` (nonnegative Unix milliseconds), and `retry_base_ms` (0..60000). Defaults are 0, immediate, and 1000 respectively. Cancellation accepts `{}`.

## Design

- `cmd/server` handles flags, loopback listening, readiness output, and shutdown.
- `internal/queue/http.go` validates JSON, tenant context, and routes requests.
- `internal/queue/store.go` owns the SQLite schema and transactional queue operations.
- `internal/platform` registers the supplied pinned pure-Go SQLite driver; its existing helper and test are preserved.

SQLite schema version 2 uses WAL and `synchronous=FULL`. Startup checks the schema version before changing journal mode. A v1 database migrates inside one immediate transaction; existing jobs retain zero retry base. Each mutation uses `BEGIN IMMEDIATE`, so separate processes serialize claims, capacity checks, and idempotent submissions through the database. Idempotency records store the normalized logical command and job IDs. A v1 command with its original omitted retry field can replay; an explicitly supplied retry base must match its historical zero value. Leases use random tokens; only claim responses expose them. Expired leases are reconciled when a queue is claimed. Passive reads report stored state. The claim index starts with tenant, queue and state, then priority and creation sequence for ordered selection. The expiry index locates expired leases, and the pending index supports tenant quota counts. Listing uses an upper creation sequence and keyset cursor.

## Verification

```sh
go test ./...
go test -race ./...
go build -o bin/queueforge ./cmd/server
scripts/process-check.sh # requires curl and jq
```

The focused tests cover concurrent duplicate submissions, tenant isolation, token fencing, heartbeat, deadline equality, max attempts, scheduling, capacity contention, cancellation, v1 migration, and batch rollback. The migration regression checks original replay and explicit retry changes through HTTP. The local two-process smoke check uses one database, distinct claims, SIGKILL after acknowledged claims, and a restart read. An earlier local check created v1 data with the preceding executable and exercised two v2 processes against the migrated file.

## Limits

This is not an authentication or TLS service. It does not execute job payloads or schedule work by itself. Expiry cleanup happens on claim, so a passive read can show a stored leased job after its deadline. SQLite serializes writes; high write contention can return HTTP 503 if the busy period exceeds the configured wait. Pending capacity counts stored ready and leased jobs; expired leases stay pending until claim reconciliation. Execution of external effects is at least once and should be idempotent at the worker.
