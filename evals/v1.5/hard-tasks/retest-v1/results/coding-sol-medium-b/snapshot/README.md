# AuditLedger

A tenant-scoped synthetic resource ledger backed by SQLite. It uses Go 1.26.3 and the pinned `modernc.org/sqlite v1.59.0` driver. No external service is required.

## Run

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

`GET /health` becomes available after schema creation or migration. Send `X-Tenant` on all other requests and `Idempotency-Key` on writes. Stop with SIGINT or SIGTERM for graceful HTTP shutdown.

## Storage and consistency

The schema has tenant-keyed `accounts`, `holds`, `transfers`, `entries`, `tenant_sequences`, and `idempotency` tables. The entry sequence is tenant-local. Each successful write acquires SQLite's `BEGIN IMMEDIATE` lock, checks the tenant-wide idempotency key, validates current state, posts every change and entry, stores the original HTTP result, and commits. Failures roll back and do not consume the key. SQLite's busy timeout allows two server processes to serialize writers against the same database. Reads of entries and historical summaries use a transaction; explicit snapshot sequence numbers remain stable across later writes and restarts.

Account balances include reserved units. Entries record signed balance and reservation deltas. Historical summaries sum entries through the chosen snapshot; account rows serve current-state reads and version checks.

## Legacy migration

On opening a v1 database, migration runs inside one immediate transaction. It infers each opening from final balance plus outgoing movements minus incoming movements, writes tenant-ordered opening entries, then imports movements by legacy ID as reversible transfers and entries. It checks reconstructed final balances, keeps all legacy tables and notes intact, and sets `user_version=2` only with the completed migration. Concurrent starts serialize on the same SQLite lock. New databases also become version 2.

## Checks

```sh
go test ./...
python3 tests/integration.py
```

The integration script builds no dependencies; it expects `./server` from the build command. It exercises two simultaneous processes, retry identity, rollback, holds, reversals, snapshots, and a generated legacy database.
