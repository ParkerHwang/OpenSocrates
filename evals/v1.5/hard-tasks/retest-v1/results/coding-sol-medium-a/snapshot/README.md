# AuditLedger

A durable JSON HTTP ledger for synthetic tenant-scoped units. It uses Go 1.26.3 and the pinned `modernc.org/sqlite v1.59.0` driver.

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

`GET /health` requires no tenant header. Every other request requires `X-Tenant`; every POST also requires `Idempotency-Key`. The eleven routes and request/response formats are specified in `TASK.md`. Invalid requests and failed business operations have no effects and do not consume a key. Send SIGINT or SIGTERM for graceful HTTP shutdown.

## Storage and transactions

SQLite stores accounts, holds, transfers, tenant-local entries and sequence counters, and successful idempotency responses. Account rows hold current balance, reserved units, and version. Entries hold signed balance and reservation deltas. `GET /summary` aggregates entries through its snapshot; `GET /entries` pages over the same fixed tenant-local sequence boundary. A snapshot therefore remains readable after later writes or a restart.

Each POST opens a SQLite `BEGIN IMMEDIATE` transaction. It first checks the tenant-wide idempotency key, then validates current versions and funds, writes every affected row and entry, stores the exact successful status and JSON response, and commits. A failed operation rolls back. Batches apply transfers in order within that single transaction. SQLite's file locks serialize writers across server processes; a busy timeout covers ordinary contention. Startup retries transient lock contention while two processes initialize the same file. WAL mode permits readers during writes. No process memory is the source of ledger state.

## Legacy migration

On a version 1 database, initialization locks the database, creates the version 2 tables, and reads legacy accounts and movements. It infers each opening as final balance plus outgoing units minus incoming units, emits openings in tenant/name order, then imports movements in ID order as reversible transfers and entries with `legacy_id`. It verifies imported current balances against the legacy final balances, advances `user_version` to 2, and commits everything together. Existing legacy tables and notes are untouched. Version 2 startups do not import again. A new empty database also becomes version 2.

## Checks

```sh
go test ./...
```

Tests cover ordered batch effects, rollback, replay across changed state and restart, tenant isolation, historical pagination and summary, legacy migration, and concurrent requests from independent database handles. A live check also started two server processes on a produced legacy fixture and reversed one imported transfer through one process while replaying it through the other.
