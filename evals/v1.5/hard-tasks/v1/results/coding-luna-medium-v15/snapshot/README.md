# AuditLedger

AuditLedger is a Go 1.26.3 HTTP service backed by SQLite (`modernc.org/sqlite` v1.59.0). Build and run it with:

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

Every request except `GET /health` requires `X-Tenant`. Writes also require a tenant-wide `Idempotency-Key`. The service implements accounts, transfers, batches, holds, capture/release, reversals, paginated entries, and entry-derived historical summaries as described by the wire contract.

## Persistence and transaction model

Schema version 2 stores current account balances/reservations/versions, transfer and hold details, an append-only entry journal, and successful idempotency responses. Every write runs in one SQLite transaction; the account changes, entries, object state, and retry response commit together. Failed requests roll back and do not claim their key. SQLite uses a busy timeout, WAL journaling, and immediate write transactions so separate processes serialize writers through the database. No ledger state is held only in process memory.

Entry sequence numbers are SQLite-generated and ordered globally; filtering by tenant yields that tenant's increasing sequence with permissible gaps. Snapshot reads use the entry journal, so the same snapshot remains stable after later writes. Account state is materialized for efficient current reads and updated in the same transaction as journal entries.

## Legacy migration

On startup, migration runs under a SQLite write transaction and advances `PRAGMA user_version` to 2. For v1 legacy tables it reads final balances and movements without changing or dropping the source tables. It computes each opening as final balance plus outgoing units minus incoming units, writes openings sorted by tenant and account, imports movements by legacy ID as ordinary reversible transfers, and initializes account versions from the number of touching movements. Transactional versioning prevents a second process or restart from importing the same rows twice. New empty databases are initialized directly at version 2.

SIGINT and SIGTERM trigger a bounded graceful HTTP shutdown.
