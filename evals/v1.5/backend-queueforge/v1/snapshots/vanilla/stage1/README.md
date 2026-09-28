# QueueForge

QueueForge is a local, durable, multi-tenant work queue API. It stores jobs and lease state in SQLite. The `X-Tenant-ID` header is a synthetic already-authenticated tenant context for this benchmark.

## Build and run

Use Go 1.26.3 with the pinned module files. No external service is needed.

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db /absolute/path/queue.sqlite
```

The server writes `{"port":12345}` to stdout once it is listening. It writes diagnostics to stderr. Optional `--clock-file /absolute/path/clock.txt` reads a Unix millisecond integer from that file for each request. It is intended for local tests. Send SIGTERM for graceful shutdown.

Example:

```sh
curl -X POST http://127.0.0.1:12345/v1/jobs \
  -H 'X-Tenant-ID: demo' -H 'Idempotency-Key: first' \
  -H 'Content-Type: application/json' \
  --data '{"queue":"mail","payload":{"n":1},"max_attempts":3}'
```

Other routes are `GET /health`, `POST /v1/jobs/batch`, `GET /v1/jobs/{id}`, `POST /v1/queues/{queue}/claim`, `POST /v1/jobs/{id}/heartbeat`, `POST /v1/jobs/{id}/complete`, `POST /v1/jobs/{id}/fail`, and `GET /v1/stats?queue=mail`.

## Design

- `cmd/server` handles flags, loopback listening, readiness output, and shutdown.
- `internal/queue/http.go` validates JSON, tenant context, and routes requests.
- `internal/queue/store.go` owns the SQLite schema and transactional queue operations.
- `internal/platform` registers the supplied pinned pure-Go SQLite driver; its existing helper and test are preserved.

SQLite uses WAL and `synchronous=FULL`. Each mutation uses `BEGIN IMMEDIATE`, so separate processes serialize claims and idempotent submissions through the database. Idempotency records store the normalized logical command and job IDs. Leases use random tokens; only claim responses expose them. Expired leases are reconciled when a queue is claimed. Passive reads report stored state.

## Verification

```sh
go test ./...
go build -o bin/queueforge ./cmd/server
scripts/process-check.sh # requires curl and jq
```

The focused tests cover concurrent duplicate submissions, two database handles, cross-tenant reads, token fencing, heartbeat, deadline equality, max attempts, batch validation, and restart reads. A local two-process smoke check also used one database, distinct claims, SIGKILL immediately after acknowledged claims, and a restart read.

## Limits

This is not an authentication or TLS service. It does not execute job payloads or schedule work by itself. Expiry cleanup happens on claim, so a passive read can show a stored leased job after its deadline. SQLite serializes writes; high write contention can return HTTP 503 if the busy period exceeds the configured wait.
