# AuditLedger

AuditLedger is a tenant-scoped synthetic allocation ledger backed by SQLite. It
uses the pinned `modernc.org/sqlite v1.59.0` driver and Go 1.26.3.

## Run

```sh
go build -o server ./cmd/server
./server --db ./ledger.db --listen 127.0.0.1:8080
```

Every request except `GET /health` needs a valid `X-Tenant` header. Every POST
write needs a tenant-wide `Idempotency-Key`. The HTTP API, request fields, and
response shapes are specified in `TASK.md`.

## Storage and transactions

The version 2 schema stores current accounts, holds, transfers and reversals,
append-only tenant-local entries, per-tenant sequence heads, and successful
idempotency results. Account reads use the current account row. Entries and
historical summaries are reconstructed from immutable deltas at or below the
requested sequence snapshot.

Every write uses a SQLite immediate transaction. The transaction checks the
tenant/key retry record, validates current state and optional versions, applies
all balance and reservation changes, appends entries, advances the sequence,
and stores the successful status and JSON response. A failed operation rolls
back without consuming its key. The SQLite busy timeout and WAL mode allow
separate server processes to coordinate through the database file; no in-memory
state is authoritative.

## Legacy migration

Startup migrates `user_version=1` databases inside one immediate transaction.
It reads but does not rewrite or remove `legacy_accounts`,
`legacy_movements`, or `legacy_notes`. For each account, it computes the opening
balance as final balance plus outgoing movements minus incoming movements,
writes openings in tenant/name order, then imports movements in legacy ID
order. Current account balances remain the supplied final balances; imported
movement entries are not applied a second time. The migration sets
`user_version=2` only when the entire import commits. A fresh empty database is
also initialized directly to version 2.
