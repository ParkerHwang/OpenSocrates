# QueueForge

A Go HTTP backend for a durable tenant scoped work queue. It uses `database/sql` with the supplied pinned `modernc.org/sqlite` driver; the driver registration lives in `internal/platform`. Queue storage, idempotency, lease transitions, expiry reconciliation, and tenant scoped statistics are in `internal/queue`. `cmd/server` validates loopback binding, owns process flags and graceful shutdown.

## Build and run

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db "$PWD/queueforge.sqlite"
```

The server prints the selected port as one JSON line on stdout. Diagnostics go to stderr. Add `--clock-file /absolute/path/to/clock` for a decimal Unix millisecond test clock; without it, the real clock is used. SIGTERM performs HTTP shutdown and closes SQLite.

Run checks with `go test ./...` and `go test -race ./...`. Optional capacity flags are `--max-pending` (tenant wide ready plus leased jobs) and `--max-inflight` (live leases per tenant and queue); both default to 100000. Inputs support priority (-10 through 10), `run_at_ms`, and retry base (0 through 60000 ms). Listing uses bounded keyset cursors, and cancellation invalidates any live lease. The claim index follows tenant, queue, state, priority descending and creation sequence so eligible jobs can be returned in priority/FIFO order; pending and inflight indexes support the two tenant-scoped admission counts inside the same SQLite write transactions. Startup checks the schema version before journal changes and upgrades version 1 transactionally, assigning historical jobs retry base zero. New databases use version 2, WAL, and `synchronous=FULL`.

Attempts are at least once. Lease tokens fence queue state changes, but cannot make arbitrary external effects exactly once. The API uses `X-Tenant-ID` as synthetic authenticated context. It does not implement production authentication, TLS, worker execution, or an administrative UI. Job payloads are stored as JSON objects and never executed.
