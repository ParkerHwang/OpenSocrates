# QueueForge

QueueForge is a local, durable, multi-tenant work queue API. It does not run job payloads. Tenant IDs in `X-Tenant-ID` represent synthetic authenticated context for this benchmark; the service does not provide authentication or TLS.

## Build and run

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db /absolute/path/queueforge.sqlite
```

The server writes one `{"port":N}` line to stdout after listening. Diagnostics go to stderr. Send SIGTERM for graceful shutdown. For deterministic local tests, pass `--clock-file /absolute/path/clock.txt`; the file must contain a Unix millisecond integer and can be atomically replaced between requests.

`--max-pending` limits a tenant's ready and leased jobs (default 100000). `--max-inflight` limits current leases per tenant and queue (default 100000). Both require positive integers. A full pending quota returns HTTP 429 `capacity`; an identical idempotency replay still succeeds. A full inflight quota makes claim return a null job.

For example, with the printed port:

```sh
curl -H 'X-Tenant-ID: demo' -H 'Idempotency-Key: first' -H 'Content-Type: application/json' -d '{"queue":"mail","payload":{"n":1}}' http://127.0.0.1:PORT/v1/jobs
```

`go test ./...` runs the focused API and supplied driver tests. `go test -race ./...` also checks concurrent test access.

## Modules and storage

- `cmd/server` parses flags, binds loopback, prints the port, and handles signals.
- `internal/queueforge` implements JSON routing, validation, transactions, leases, idempotency, and stats.
- `internal/platform` registers the pinned SQLite driver and retains the supplied driver test.

SQLite is the source of truth. It uses WAL, synchronous `FULL`, and `BEGIN IMMEDIATE` for each mutation, including expiry reconciliation, quota checks, and claims. Schema version 2 migrates version 1 in one transaction, retaining legacy idempotency and lease data. Startup rejects future versions before setting journal mode. Idempotency keys are scoped by tenant and endpoint. A replay returns current job state and the original resource IDs. Job responses omit lease tokens; claim returns the token separately.

Single and batch submissions share validation and insertion. Each job accepts `priority` (-10 to 10, default 0), `run_at_ms` (nonnegative Unix milliseconds, default now), and `retry_base_ms` (0 to 60000, default 1000). Eligible jobs are claimed by priority descending, then creation sequence. Retryable failure and lease expiry use capped exponential backoff. Legacy jobs retain a zero retry base. `POST /v1/jobs/{id}/cancel` accepts `{}` and fences a live lease. `GET /v1/jobs` supports optional `queue`, `limit` (1 to 100, default 50), and an opaque keyset `cursor`; later inserts stay outside the first page's creation bound.

The version 2 claim index orders ready candidates by tenant, queue, state, priority, and sequence. Separate indexes support current inflight counts, tenant pending counts, and queue-filtered listing. Availability remains a predicate so a future high-priority job cannot block an eligible lower-priority job.

## Limits

Bodies are limited to 1 MiB, job payload objects to 16 KiB, batches to 100 jobs, lease durations to 10–300000 ms, and attempts to 1–10. Busy storage operations return 503. Stats show stored state and do not reconcile expired leases; a claim reconciles expired leases for its tenant and queue. Expired stored leases still consume pending quota until that reconciliation. The optional clock file is for tests. The service is local only and does not implement authentication, TLS, or job execution. Attempts are at least once with fenced completion; arbitrary external effects are not exactly once.
