# Project notes

## Current source facts

- `go.mod` pins Go 1.26.3 and `modernc.org/sqlite v1.59.0`.
- The original starter contained only the SQLite driver wrapper and server
  placeholder; the API and schema are implemented in `internal/ledger`.
- `legacy/produce.py` creates an actual v1 SQLite database and refuses to
  overwrite an existing target. The supplied producer and fixture remain
  unchanged.

## Implementation state

- `internal/platform.Open` configures SQLite WAL, full synchronous commits,
  foreign keys, a 15-second busy timeout, and a bounded connection pool.
- Startup uses `BEGIN IMMEDIATE` for schema setup and v1 import. Writes use the
  same lock boundary for business checks, mutations, entries, and idempotency
  response storage.
- Current account rows hold versions and reservation state. Append-only entries
  supply tenant-scoped pagination and historical summaries.
- Legacy movement rows are imported as reversible transfers after inferred
  openings. Legacy source tables and notes are left intact.
- `cmd/server` runs the HTTP API and shuts down on SIGINT or SIGTERM.

## Checks completed

- `go build -o server ./cmd/server` succeeds with the installed Go 1.26.3 toolchain.
- Local HTTP checks cover fresh accounts, transfers, holds, capture, reversal,
  retries, batch rollback, versions, strict body/query validation, tenant
  isolation, pagination, and historical summary values.
- Twelve concurrent identical retries produced one stored result. Two
  independent server processes sharing one file completed concurrent writes
  without lost updates.
- The supplied v1 producer database migrated to version 2. All 4 accounts,
  10 initial entries, and legacy notes were preserved; an imported transfer
  reversed successfully, and restart did not repeat migration.
- No performance meter or hidden acceptance tool was run in this session.

## Remaining verification

- The independent post-episode acceptance and performance runs remain external
  and were not available in this implementation session.
