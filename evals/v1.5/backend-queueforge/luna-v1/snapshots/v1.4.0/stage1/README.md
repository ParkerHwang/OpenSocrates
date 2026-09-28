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

All job data and idempotency records live in SQLite. WAL plus synchronous=FULL
are enabled. Tenant ID is synthetic request context and is not authentication.

## Limits

Request bodies are limited to 1 MiB and payload/result objects to 16 KiB. Jobs
are never executed. This benchmark service provides no production authentication,
TLS, cancellation endpoint, metrics, or background expiration worker. Expiration
is reconciled when a matching queue is claimed; passive reads show stored state.
