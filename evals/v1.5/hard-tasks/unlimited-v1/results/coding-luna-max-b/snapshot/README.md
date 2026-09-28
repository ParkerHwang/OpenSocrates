# AuditLedger

AuditLedger is a tenant-scoped synthetic allocation ledger backed by SQLite.
It has no external service dependencies. Build and run it with Go 1.26.3 and
the pinned `modernc.org/sqlite v1.59.0` module:

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

The database is the source of truth. Its version 2 schema stores current
accounts, transfers, holds, object IDs, per-tenant entry sequences, immutable
ledger entries, and tenant-scoped idempotency results. Historical summaries
derive balances and reservations from entries at the requested snapshot.

Each write uses one SQLite `BEGIN IMMEDIATE` transaction. The transaction
checks the tenant-wide idempotency key, applies all account/object/entry
changes, stores the successful HTTP response, and commits them together. A
failed operation rolls back and leaves its key unused. A SQLite busy timeout
and ordinary file locking allow multiple server processes to use the same
database.

Startup migrates an empty database directly to version 2 or imports a genuine
version 1 database in one transaction. Migration infers opening balances from
the legacy final balances and movements, writes openings and movements in
contract order, and preserves every legacy table and row. The old notes and
movement tables are retained unchanged. Migration is skipped after
`user_version` reaches 2.

The process handles SIGINT and SIGTERM by stopping new HTTP work and allowing
active requests up to ten seconds to finish before closing SQLite.
