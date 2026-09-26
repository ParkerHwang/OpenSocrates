# AuditLedger

AuditLedger is a Go HTTP service backed by SQLite. It stores synthetic tenant scoped accounts, holds, transfers, retry results, and an append only entry history.

## Run

```sh
go build -o server ./cmd/server
./server --db ledger.db --listen 127.0.0.1:8080
```

Each request except `GET /health` requires `X-Tenant`. Every write also requires an `Idempotency-Key`. SQLite uses a 10 second busy timeout, WAL mode, and immediate write transactions so separate server processes serialize write decisions through the database. Send SIGINT or SIGTERM for process shutdown.

## Storage and transaction model

Schema version 2 stores current account balance/reserved/version, transfer and hold state, append only entries, and successful idempotency responses. Every business write runs in one SQLite transaction. It checks an existing tenant/key result before current state, then validates and applies all account changes and entries, stores the response, and commits. Failures roll back and do not reserve keys. Batch members execute in order in the same transaction. Reads do not change versions.

The entries table is the source for historical summaries and paginated reads. A snapshot is the maximum visible entry sequence at request time; aggregation uses only entries at or below that value. Current accounts are updated in the same transaction as their entries.

On startup, the service takes a SQLite write transaction and reads `user_version`. Version 1 rows are imported atomically: inferred openings are final balance plus outgoing minus incoming movements, then movements become transfer entries in legacy ID order. Account versions include the number of imported movements touching each account. Legacy tables and notes are retained. New databases and migrated databases use `user_version=2`; migration does not repeat after restart.
