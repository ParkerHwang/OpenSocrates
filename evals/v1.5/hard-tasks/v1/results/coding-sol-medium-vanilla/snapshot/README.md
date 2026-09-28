# AuditLedger

A tenant scoped synthetic unit ledger backed by SQLite. It uses the pinned Go 1.26.3 module dependencies and has no external services.

```sh
go build -o server ./cmd/server
./server --db ledger.sqlite --listen 127.0.0.1:8080
```

Every route except `GET /health` requires `X-Tenant`. Every POST requires `Idempotency-Key`. JSON request fields are checked strictly. The complete API and response shapes are in `TASK.md`.

## Storage and transaction model

`accounts` holds current balance, reserved units, and version. `holds` tracks reservation state. `transfers` stores ordinary, capture, reversal, and imported transfers. `entries` is the append only tenant sequence used by pagination and historical summaries. `retries` stores the successful write's canonical JSON body, path, status, and response. Primary keys include the tenant. Database state, including retries, survives process restarts.

All writes use `BEGIN IMMEDIATE` through a dedicated SQLite connection. The transaction checks the retry key first, then checks current versions and available units, updates objects, appends entries, and stores the successful response before commit. A failed write rolls back all changes and leaves its key reusable. SQLite's write lock serializes concurrent writers across server processes. Each process sets a busy timeout and uses one connection, so it cannot lose per connection pragmas.

`GET /entries` fixes a tenant sequence snapshot for stable pagination. `GET /summary` aggregates only entries through the requested snapshot. A current summary is therefore independently derived from the event ledger rather than copied from current account rows.

## Migration

On startup, schema initialization and migration run in one immediate transaction. A new database becomes schema version 2. For a version 1 database, migration reads legacy rows without changing or dropping them, infers each account's opening balance from its final balance and movements, emits opening entries in tenant and account order, then imports movements in ID order. Imported transfers remain reversible and expose `legacy_id` in their entries. Version 2 prevents reimport on restart. A failed migration rolls back and leaves the old database intact.
