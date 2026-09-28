# Project notes

## Objective

Implement the AuditLedger HTTP contract with durable tenant isolation,
idempotency, historical reads, and one-time v1 SQLite migration.

## Current source findings

- The starter was a TODO process plus the generic `modernc.org/sqlite` opener.
- `legacy/produce.py` creates a real v1 database; `fixture.json` includes two
  tenants, movements, and a Unicode/newline legacy note.
- The existing Go toolchain is 1.26.3 and the pinned SQLite module is cached.

## Work completed

- Added the SQLite schema and transactional migration in
  `internal/ledger/store.go`.
- Added strict JSON handling, all HTTP routes, atomic writes and retries,
  entries, and entry-derived snapshots in `internal/ledger/http.go`.
- Added graceful signal shutdown and migration-before-listen in
  `cmd/server/main.go`; documented storage and run steps in `README.md`.
- Write transactions use `BEGIN IMMEDIATE`; SQLite remains the source of truth
  across process restarts and concurrent processes.

## Checks and limits

- Built with Go 1.26.3 and cached dependencies.
- Local HTTP checks passed for legacy import and note preservation, strict
  inputs, tenant isolation, retry replay/conflicts, staged batch rollback,
  holds/capture/release, reversal, history snapshots, restart replay, and
  concurrent identical writes through two server processes sharing one
  database. Two simultaneous starters also migrated a separate genuine v1
  database once while preserving its old rows and note bytes.
- `go test ./...`, `go vet ./...`, and `git diff --check` passed. A malformed
  percent-encoded query was also confirmed to return 400 `invalid`.
- The independent performance meter was not run, as required. Recheck the
  source and status before relying on these notes in a later session.
