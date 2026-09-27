# AuditLedger

AuditLedger is a tenant-scoped synthetic unit ledger backed by SQLite. It uses the pinned `modernc.org/sqlite` driver and stores accounts, append-only entries, transfers, holds, and successful idempotency results in the same database.

## Run

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

Send `X-Tenant` on every request other than `GET /health`. Every write also needs an `Idempotency-Key`. SQLite WAL mode and a busy timeout let independent server processes share the database.

## Data and transaction model

Each write runs in one SQLite transaction. The transaction takes the SQLite writer lock before checking the tenant-wide idempotency key, checks business conditions against staged account state, then commits account changes, entries, operation objects, and the successful response together. Failed operations roll back and do not reserve keys. A replay returns the stored status and JSON response.

Entries are the historical source for `/entries` and `/summary`; summaries aggregate only entries at or below the selected tenant-local sequence snapshot. Current account rows are maintained alongside entries for efficient live reads. All balance and reservation updates, emitted entries, hold or transfer state changes, and retries are durable.

## Migration

Startup creates the v2 schema for an empty database or transactionally migrates a genuine v1 database while holding a SQLite write lock. Legacy final balances are converted to inferred opening entries, then legacy movements are imported by ID. Legacy tables and notes remain untouched. `PRAGMA user_version` becomes `2` only when migration commits, so another process or later restart will not repeat it.
