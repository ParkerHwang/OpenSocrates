# AuditLedger

A durable HTTP ledger for synthetic tenant-scoped units. Build with Go 1.26.3 and the pinned local modules:

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

All write requests need `X-Tenant` and `Idempotency-Key` headers. All requests except `/health` need `X-Tenant`. Bodies are JSON objects. See `TASK.md` for the route and response contract.

## Storage and transactions

SQLite tables hold current accounts, holds, transfers, tenant-local entries, sequence counters, and successful idempotency results. Each write uses `BEGIN IMMEDIATE`; it validates current state, updates all affected rows, appends entries, and stores the successful HTTP response before commit. A failed operation rolls back everything. The key is tenant-wide across write routes, and replay reads the stored response before business or version checks. SQLite's write lock serializes writers across processes; a busy timeout lets the second process wait. Each process uses one SQLite connection. Read transactions keep each entries page or summary internally consistent.

Entries are the historical source for `/summary`; current accounts are maintained transactionally alongside them. A supplied snapshot caps reads at a tenant-local entry sequence. The same snapshot can be used after later writes or a restart.

## Migration

On startup, a transaction checks `PRAGMA user_version`. A new database creates the v2 schema. A v1 database keeps every legacy table and row, infers opening balances from final balances and ordered movements, imports openings and reversible transfers, then sets `user_version=2`. The transaction makes a concurrent startup safe and prevents partial or repeated import. Unknown schema versions stop startup without resetting the database.

The server handles SIGINT and SIGTERM with graceful HTTP shutdown.
