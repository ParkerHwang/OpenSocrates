# AuditLedger

AuditLedger is a tenant-scoped synthetic unit ledger implemented in Go with the pinned `modernc.org/sqlite v1.59.0` driver. Build with:

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

Every request except `GET /health` requires `X-Tenant`; every write also requires an `Idempotency-Key`. The database is the source of truth. Current accounts are stored in `accounts`, transfers and holds in their respective detail tables, successful retry results in `idempotency`, and the append-only `entries` table drives historical reads and summaries. Entry sequence values are SQLite generated and may have gaps.

Each mutation uses one SQLite transaction for its business changes, entries, and successful idempotency response. Validation or business failures roll the transaction back and do not reserve the retry key. Reads derive historical account totals from entries at or below their selected snapshot. WAL mode and SQLite busy timeout support ordinary local concurrent database access.

At startup, schema setup checks `PRAGMA user_version`. Version 1 is migrated in a transaction: legacy final balances are retained, opening entries are inferred by reversing movement effects, then old movements are imported in ID order. Legacy tables and notes are left intact. Version 0 empty databases and migrated databases advance to version 2; later starts do not repeat migration.

The server handles interrupt and SIGTERM by closing its HTTP listener and then closing the database.
