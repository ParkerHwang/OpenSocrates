# QueueForge

QueueForge is a local, durable, multi-tenant work queue API. It does not run job payloads. Tenant IDs in `X-Tenant-ID` represent synthetic authenticated context for this benchmark; the service does not provide authentication or TLS.

## Build and run

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db /absolute/path/queueforge.sqlite
```

The server writes one `{"port":N}` line to stdout after listening. Diagnostics go to stderr. Send SIGTERM for graceful shutdown. For deterministic local tests, pass `--clock-file /absolute/path/clock.txt`; the file must contain a Unix millisecond integer and can be atomically replaced between requests.

For example, with the printed port:

```sh
curl -H 'X-Tenant-ID: demo' -H 'Idempotency-Key: first' -H 'Content-Type: application/json' -d '{"queue":"mail","payload":{"n":1}}' http://127.0.0.1:PORT/v1/jobs
```

`go test ./...` runs the focused API and supplied driver tests. `go test -race ./...` also checks concurrent test access.

## Modules and storage

- `cmd/server` parses flags, binds loopback, prints the port, and handles signals.
- `internal/queueforge` implements JSON routing, validation, transactions, leases, idempotency, and stats.
- `internal/platform` registers the pinned SQLite driver and retains the supplied driver test.

SQLite is the source of truth. It uses WAL, synchronous `FULL`, and `BEGIN IMMEDIATE` for each mutation, including expiry reconciliation and claims. Idempotency keys are scoped by tenant and endpoint. A replay returns current job state and the original resource IDs. Job responses omit lease tokens; claim returns the token separately.

## Limits

Bodies are limited to 1 MiB, job payload objects to 16 KiB, batches to 100 jobs, lease durations to 10–300000 ms, and attempts to 1–10. Busy storage operations return 503. Stats show stored state and do not reconcile expired leases; a claim reconciles expired leases for its tenant and queue. The optional clock file is for tests. The service is local only and does not implement authentication, TLS, scheduling beyond immediate availability, or job execution.
