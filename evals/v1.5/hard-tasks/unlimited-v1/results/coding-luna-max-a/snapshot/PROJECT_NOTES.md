# Project notes

## Current source facts

- `go.mod` pins Go 1.26.3 and `modernc.org/sqlite v1.59.0`.
- The backend is implemented in `internal/ledger`; `cmd/server` initializes the
  database before listening and shuts down on SIGINT or SIGTERM.
- SQLite WAL, full synchronous commits, foreign keys, a 15-second busy timeout,
  and bounded connection pools are configured by `internal/platform`.
- Account rows hold current balances, reservations, and versions. Append-only
  entries use unique `(tenant,seq)` values allocated in the same transaction;
  reads derive stable historical summaries and pages from those entries.
- Startup migration and every write serialize through `BEGIN IMMEDIATE`.
  Successful idempotency results are committed with their effects.

## Implementation state

- The v1 importer keeps legacy tables and notes intact, infers opening balances
  from final balances and movements, and imports reversible transfer details.
- Startup converts the earlier version-2 global entry sequence layout to the
  tenant-local layout in one transaction, preserving existing sequence values
  and entry details.
- The supplied producer and fixture remain unchanged. The README documents
  schema, transaction boundaries, migration, and run commands.

## Checks completed

- `go build -o server ./cmd/server` succeeds with Go 1.26.3 and module
  downloads disabled; `go test ./...` passes.
- Local HTTP checks covered strict validation, transfers, staged batch rollback,
  holds/capture/release, reversal, idempotency replay/conflict, pagination,
  historical summaries, tenant isolation, concurrent identical retries,
  concurrent writes through two processes, restart persistence, and graceful
  SIGTERM shutdown.
- The real v1 producer database was migrated while two processes started.
  Tenant-local entry order, inferred final balances, imported reversals, version
  2, and legacy table definitions plus text values compared as raw bytes were
  checked; restart did not repeat the import. A deliberately invalid temporary
  v1 database confirmed migration rollback preserves legacy rows and version 1.
- A synthetic earlier version-2 database was converted; historical sequence
  values and entries survived conversion and restart.
- No independent acceptance tool or performance meter was run.

## Remaining verification

- Independent acceptance and performance results are not available in this
  workspace. The task explicitly reserves the performance run for after model
  and build work, so it remains for that external stage.
