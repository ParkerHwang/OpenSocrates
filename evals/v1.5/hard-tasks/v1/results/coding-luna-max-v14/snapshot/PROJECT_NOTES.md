# Project notes

## Scope

Implement the supplied synthetic AuditLedger contract only. Do not change task,
evaluation, or legacy fixture producer files. Do not run the independent
performance meter in this session.

## Current implementation

- Go HTTP server is in `cmd/server` and `internal/ledger`.
- `internal/platform` configures the pinned SQLite driver with WAL, a busy
  timeout, and immediate transactions.
- Schema v2 stores current account state, holds, transfers, idempotency results,
  tenant sequence heads, and append-only entries.
- Startup migration imports v1 final balances by deriving openings and replaying
  imported movements only into history. Legacy tables are left in place.
- Writes persist effects, entries, sequence heads, and successful idempotency
  results in one SQLite transaction.

## Checks and remaining work

Build and focused localhost contract checks are still required after the current
source changes. Confirm migration against the supplied v1 producer, restart and
retry behavior, historical snapshots, and concurrent writers. Stop all test
servers before handing back. Do not claim the external acceptance or performance
results; they have not been run here.
