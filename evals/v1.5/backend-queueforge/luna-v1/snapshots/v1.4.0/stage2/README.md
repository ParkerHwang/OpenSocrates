# QueueForge

A small Go HTTP service backed by SQLite. It stores JSON payloads as inert data.

## Build and run

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:8080 --db /absolute/path/queue.sqlite
```

`--clock-file /absolute/path/clock` enables the test clock; its contents are a
Unix millisecond integer read for each operation. The server prints its bound
port as one JSON line on stdout and logs diagnostics to stderr. Send SIGTERM to
shut it down.

## Modules

- `cmd/server`: HTTP routing, validation, SQLite schema and queue lifecycle.
- `internal/platform`: registration of the pinned pure-Go SQLite driver.

All job data and idempotency records live in SQLite schema version 2. Startup
migrates version 1 transactionally, retaining jobs, leases, results and
idempotency rows. WAL plus synchronous=FULL are enabled. Tenant ID is synthetic
request context and is not authentication.

`--max-pending N` sets the positive tenant-wide ready plus leased limit
(default 100000). `--max-inflight N` sets the positive per-tenant, per-queue
nonexpired lease limit (default 100000). Capacity is checked in SQLite write
transactions, and idempotent replays remain available at capacity. Enqueue
inputs support `priority` (-10..10), `run_at_ms` (nonnegative; omitted means
immediate), and `retry_base_ms` (0..60000; omitted means 1000). Retry delays
double by attempt and cap at 60000 ms. Existing version 1 jobs retain retry
base zero.

`GET /v1/jobs` provides created-sequence keyset pages with a tenant and optional
queue-bound cursor. `POST /v1/jobs/{id}/cancel` cancels ready or leased jobs and
fences any former lease token. Claim reconciles expired leases; passive reads
and stats continue to show stored states until then.

## Limits

Request bodies are limited to 1 MiB and payload/result objects to 16 KiB. Jobs
are never executed. This benchmark service provides no production authentication,
TLS, metrics, or background expiration worker. Retry attempts are at least once;
lease fencing protects queue state, not arbitrary external effects.
