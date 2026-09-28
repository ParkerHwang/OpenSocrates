# QueueForge

QueueForge is a durable, tenant-scoped SQLite work queue API. It stores opaque payload objects and never executes them. The synthetic tenant header is test context, not authentication.

## Run

```sh
mkdir -p bin
go build -o bin/queueforge ./cmd/server
./bin/queueforge --db /absolute/path/queue.sqlite --addr 127.0.0.1:0
```

The server prints its bound port as one JSON line. `--clock-file` optionally selects the millisecond test clock. `--max-pending` limits tenant ready plus leased jobs; `--max-inflight` limits nonexpired tenant/queue leases. Both default to 100000 and must be positive.

## Modules and storage

`cmd/server` owns flags, listener startup and graceful signal shutdown. `internal/queue/http.go` validates and routes JSON requests. `internal/queue/store.go` owns the SQLite schema, transactional idempotency, admission, lease fencing, scheduling, cancellation, pagination and stats. `internal/platform` registers the pinned SQLite driver.

Schema version 2 adds `priority` and `retry_base_ms` with historical defaults 0. The claim index narrows by queue, state and availability before priority ordering; pending and inflight indexes support tenant admission counts, while tenant and tenant/queue creation indexes support snapshot keyset scans. SQLite WAL and synchronous FULL remain enabled. Retryable failures and expired leases schedule from failure time and lease deadline respectively. Attempts are at least once; fencing protects queue state, not arbitrary external effects.

## Checks

```sh
go test ./...
go test -race ./...
go build -o bin/queueforge ./cmd/server
```
