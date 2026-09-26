# QueueForge

QueueForge is a local, multi-tenant HTTP work queue backed by one SQLite file. It stores payloads but never executes them. `X-Tenant-ID` is a synthetic already-authenticated identity, not an authentication mechanism.

## Build and run

```sh
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db /absolute/path/queue.sqlite --max-pending 100000 --max-inflight 100000
```

The first stdout line is `{"port":<actual port>}`. Diagnostics go to stderr. `--clock-file /absolute/path/clock.txt` supplies a decimal Unix millisecond timestamp read on each operation; omit it for the real clock. Send SIGTERM for a graceful stop.

All API calls except `GET /health` require `X-Tenant-ID`. Submit calls require `Idempotency-Key`.

```sh
curl -H 'X-Tenant-ID: demo' -H 'Idempotency-Key: first' \
  -H 'Content-Type: application/json' \
  -d '{"queue":"mail","payload":{"n":1}}' \
  http://127.0.0.1:PORT/v1/jobs
```

Run checks with `go test ./...` and `go test -race ./...`. The tests cover concurrency, tenant isolation, leases, deadlines, batch validation, scheduling, admission, cancellation, pagination, and database reopen. The original lifecycle test assumes immediate retry for a new job; the version 2 default is 1,000 ms, so that preserved assertion fails.

## Modules

- `cmd/server`: CLI, listener, startup output, and shutdown.
- `internal/queue/http.go`: routing, validation, JSON response shape.
- `internal/queue/store.go`: SQLite schema, transactions, idempotency, job lifecycle, and clock.
- `internal/platform`: pinned SQLite driver registration and its supplied test.

## Storage and limits

The database uses WAL and `synchronous=FULL`. Mutations use `BEGIN IMMEDIATE` transactions, including admission checks, claim reconciliation and selection, cancellation, and lease updates. SQLite coordinates independent processes. The schema is version 2; startup migrates version 1 in one transaction. Historical jobs retain zero retry base. Unknown future versions fail before journal mode is changed. The database persists jobs, completion replay tokens, and idempotency keys. A busy or unavailable database yields HTTP 503.

Submit accepts `priority` (-10 through 10), `run_at_ms` (nonnegative Unix milliseconds), and `retry_base_ms` (0 through 60000). Defaults are 0, immediate, and 1000 respectively. Ready claims choose the highest priority eligible job, then the oldest creation sequence. Retry delays double by attempt up to 60 seconds; expired leases use their deadline as the base. `POST /v1/jobs/{id}/cancel` cancels ready or leased jobs. `GET /v1/jobs` returns keyset pages sorted by creation sequence, with an upper bound fixed by the first page. Cursor values are bound to tenant and queue. The claim index groups tenant, queue, and state before priority and creation sequence; an inflight index supports live lease counts. Tenant and tenant plus queue creation indexes support unfiltered and filtered pages.

`--max-pending` counts ready and leased jobs per tenant; `--max-inflight` counts nonexpired leases per tenant and queue. Both flags require positive integers. Admission is atomic across processes; identical idempotency replay remains available when full. Completion, death, and cancellation release pending capacity. Execution is at least once with fenced completion; arbitrary external effects are outside the queue's control.

Request bodies are limited to 1 MiB; payload and completion result objects are limited to 16 KiB. Batches contain at most 100 jobs. No job retention or idempotency-key expiry is implemented. The test clock is intended only for controlled local tests. The API binds to IPv4 loopback only and does not provide TLS or real authentication.
