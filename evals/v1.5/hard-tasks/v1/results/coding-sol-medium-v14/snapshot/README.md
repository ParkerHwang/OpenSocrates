# AuditLedger

AuditLedger is a tenant-scoped synthetic unit ledger served over JSON HTTP. It uses Go 1.26.3 and the pinned `modernc.org/sqlite v1.59.0` driver.

```sh
GOTOOLCHAIN=local GOPROXY=off go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

`GET /health` needs no headers. Every other request needs `X-Tenant`; writes also need `Idempotency-Key`. The API routes, request fields, responses, limits, and error codes are specified in `TASK.md`.

## Storage and transactions

SQLite `user_version=2` contains tenant-keyed `accounts`, `holds`, `transfers`, `entries`, and `idem` tables. Entries have a tenant-local sequence. Account rows hold current balance, reserved units, and version; historical summaries sum entry deltas through the requested snapshot. The `idem` table stores the successful request path, canonical JSON body, status, and exact JSON result. A replay returns that stored result even after account state changes.

Each write obtains a SQLite `BEGIN IMMEDIATE` transaction on a dedicated connection. It checks the tenant-wide idempotency key first, then validates current state and versions, applies all changes, appends entries, and stores the success result before committing. Failed requests roll back and leave the key free. SQLite WAL mode permits concurrent readers while SQLite serializes writers across server processes. Read endpoints use a read transaction so the chosen snapshot and returned rows share one database view. Each connection used for a write has a busy timeout, and startup retries SQLite lock contention during simultaneous migration.

## Legacy migration

At startup, a v1 database is migrated in one immediate transaction. For each old account, the opening balance is inferred from its final balance plus outgoing movements minus incoming movements. Opening entries are inserted in tenant/name order; movements are imported in ID order as reversible transfers with `legacy_id` on their entries. Current account balances remain the supplied final balances, and versions count imported movements. Existing legacy tables and notes remain untouched. The transaction sets `user_version=2`; restarts do not reimport. A new empty database is initialized directly as v2.

`SIGINT` and `SIGTERM` trigger graceful HTTP shutdown. State is held in SQLite; the process keeps no authoritative ledger state.
