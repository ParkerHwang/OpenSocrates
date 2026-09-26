# QueueForge

QueueForge is a local, multi-tenant HTTP work queue backed by one SQLite file. It stores payloads but never executes them. `X-Tenant-ID` is a synthetic already-authenticated identity, not an authentication mechanism.

## Build and run

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db /absolute/path/queue.sqlite
```

The first stdout line is `{"port":<actual port>}`. Diagnostics go to stderr. `--clock-file /absolute/path/clock.txt` supplies a decimal Unix millisecond timestamp read on each operation; omit it for the real clock. Send SIGTERM for a graceful stop.

All API calls except `GET /health` require `X-Tenant-ID`. Submit calls require `Idempotency-Key`.

```sh
curl -H 'X-Tenant-ID: demo' -H 'Idempotency-Key: first' \
  -H 'Content-Type: application/json' \
  -d '{"queue":"mail","payload":{"n":1}}' \
  http://127.0.0.1:PORT/v1/jobs
```

Run checks with `go test ./...`. The integration tests cover concurrent idempotency, tenant isolation, leases, deadlines, batch validation, max attempts, and database reopen.

## Modules

- `cmd/server`: CLI, listener, startup output, and shutdown.
- `internal/queue/http.go`: routing, validation, JSON response shape.
- `internal/queue/store.go`: SQLite schema, transactions, idempotency, job lifecycle, and clock.
- `internal/platform`: pinned SQLite driver registration and its supplied test.

## Storage and limits

The database uses WAL and `synchronous=FULL`. Mutations use `BEGIN IMMEDIATE` transactions, including claim reconciliation and selection. SQLite coordinates independent processes. The schema is version 1 and persists jobs, completion replay tokens, and idempotency keys. A busy or unavailable database yields HTTP 503.

Request bodies are limited to 1 MiB; payload and completion result objects are limited to 16 KiB. Batches contain at most 100 jobs. No job retention or idempotency-key expiry is implemented. The test clock is intended only for controlled local tests. The API binds to IPv4 loopback only and does not provide TLS or real authentication.
