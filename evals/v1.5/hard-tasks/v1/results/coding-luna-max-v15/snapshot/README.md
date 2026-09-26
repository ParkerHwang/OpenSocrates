# AuditLedger

AuditLedger is a tenant-scoped synthetic allocation ledger backed by SQLite.
The database is the source of truth for accounts, holds, transfers, entries, and
idempotency results.

## Run

Use Go 1.26.3 and the pinned `modernc.org/sqlite v1.59.0` module already listed
in `go.mod` and `go.sum`:

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

Send `X-Tenant` on every request except `GET /health`. Every write also needs an
`Idempotency-Key`. The HTTP contract and routes are documented in `TASK.md`.
SIGINT and SIGTERM trigger graceful HTTP shutdown.

## Storage and transactions

Schema version 2 uses tenant-keyed `accounts`, `holds`, `transfers`, and
`idempotency` tables, an `ids` registry for tenant-wide opaque ID uniqueness,
and an append-only `entries` table. SQLite's global autoincrement sequence is
used for entry ordering; each tenant therefore has increasing sequence values
with permitted gaps. WAL mode and SQLite's busy timeout support local readers
and writers from multiple server processes.

Each write starts an immediate SQLite transaction, checks the tenant-wide
idempotency key, validates current state, applies every account and entry
change, stores the successful response, and commits once. A failed operation
rolls the whole transaction back and does not use its key. Read snapshots use a
separate deferred connection pool; historical summaries derive account values
from entries at or below the requested sequence.

## Migration

Startup migration and `PRAGMA user_version` changes run in one SQLite write
transaction. Empty databases become version 2. A version 1 database keeps its
legacy tables unchanged: migration derives each opening balance from the final
balance and ordered movements, writes opening entries in tenant/account order,
then imports movements by legacy ID as reversible transfer rows and entries.
The imported account versions include the number of movements touching each
account. A second process waits on SQLite's normal write lock and then observes
the completed version, so the import is not repeated.
