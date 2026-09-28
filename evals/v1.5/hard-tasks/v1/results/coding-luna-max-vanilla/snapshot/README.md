# AuditLedger

AuditLedger is a tenant-scoped Go HTTP service backed by SQLite. It stores the
current account state, holds, transfers, append-only ledger entries, and
successful idempotency results in the same database. Tenant IDs are supplied
with `X-Tenant`; writes also require an `Idempotency-Key`.

## Build and run

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

The database file and retry results survive restarts. `SIGINT` and `SIGTERM`
stop the HTTP server gracefully. The Go module pins `modernc.org/sqlite v1.59.0`.

## Storage and transaction model

The application tables are `accounts`, `holds`, `transfers`, `entries`,
`object_ids`, and `idempotency`. `entries` uses a tenant-local increasing
sequence. Current account values are materialized for efficient reads, while
historical summaries are recomputed from entries at or below the requested
snapshot. Account versions change once per affected account per operation;
each transfer in a batch is its own version step.

Every write starts with SQLite `BEGIN IMMEDIATE`, checks the tenant-wide retry
key, applies the operation, appends its entries, stores the original status and
JSON result, then commits. A failed operation rolls back without consuming its
key. The immediate database lock serializes writers across processes; the
driver's SQLite busy timeout lets competing requests wait for the lock. No
in-memory ledger state is authoritative.

Startup migration reads `PRAGMA user_version` while holding the same write
lock. A new database receives the application schema and version 2. A v1
database keeps all legacy tables and rows, derives opening balances from final
balances and legacy movements, imports openings and movements in order, then
sets version 2. Schema creation, imported entries, and the version change share
one SQLite transaction, so a second process cannot repeat a partial import.
