# QueueForge

A Go HTTP backend for a durable tenant scoped work queue. It uses `database/sql` with the supplied pinned `modernc.org/sqlite` driver; the driver registration lives in `internal/platform`. Queue storage, idempotency, lease transitions, expiry reconciliation, and tenant scoped statistics are in `internal/queue`. `cmd/server` validates loopback binding, owns process flags and graceful shutdown.

## Build and run

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db "$PWD/queueforge.sqlite"
```

The server prints the selected port as one JSON line on stdout. Diagnostics go to stderr. Add `--clock-file /absolute/path/to/clock` for a decimal Unix millisecond test clock; without it, the real clock is used. SIGTERM performs HTTP shutdown and closes SQLite.

Run the focused suite with `go test ./...` and `./scripts/process-check.sh`. The API uses `X-Tenant-ID` as synthetic authenticated context. It does not implement production authentication, TLS, worker execution, cancellation, or an administrative UI. Job payloads are stored as JSON objects and never executed. SQLite uses WAL, `synchronous=FULL`, transactional mutations, and schema version 1.
