# AuditLedger

AuditLedger is a tenant-scoped synthetic resource ledger backed by SQLite. It
stores accounts, holds, transfers, immutable entries, and successful
idempotency results in one database. It has no external service dependencies.

## Build and run

Use Go 1.26.3 and the pinned `modernc.org/sqlite v1.59.0` dependency:

```sh
go build -o server ./cmd/server
./server --db ./ledger.db --listen 127.0.0.1:8080
```

The server migrates the database before it begins listening. Send
`X-Tenant: tenant-name` on every request other than `GET /health`; writes also
require a valid `Idempotency-Key` header.

## Storage and transaction boundaries

The schema uses tenant/name primary keys for accounts, tenant-scoped object IDs
for transfers and holds, an append-only `entries` table with a tenant-local
sequence, and a `(tenant,key)` idempotency table. A sequence allocator and
unique `(tenant,seq)` constraint serialize entry numbering with each write.
Account rows are the current state; entry rows are the durable source for
historical summaries and pagination. The server uses WAL mode, full synchronous
commits, foreign-key checking, and SQLite's busy timeout.

Every write acquires a SQLite `BEGIN IMMEDIATE` transaction before checking its
idempotency key or current state. Account changes, object state, entries, and
the successful response/status are committed together. A failed request rolls
back all staged effects and does not consume its key. Independent processes
serialize writers through SQLite and can share the same database file.

Batches apply transfers in request order inside one transaction. Each transfer
updates touched account versions once; a later failure rolls back the whole
batch. Historical summaries replay entries at or below the requested sequence
snapshot, so later writes do not change an earlier view.

## Migration

Startup reads `PRAGMA user_version` while holding the SQLite writer lock. A new
database receives the current schema and version 2. A v1 database keeps all
legacy tables and notes; migration derives each opening balance from the final
balance and legacy movements, creates opening entries in tenant/name order,
then imports movements in ID order as reversible transfers. Imported entries
retain their `legacy_id`. All schema creation and import work commits together,
and `user_version` changes to 2 only on success. Later starts see version 2 and
do not import the legacy rows again. An earlier version-2 entry layout is
converted transactionally to tenant-local sequences while preserving its
existing sequence values and entry details.
