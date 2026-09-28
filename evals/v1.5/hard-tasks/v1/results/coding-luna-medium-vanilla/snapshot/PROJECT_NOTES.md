# Project notes

## Current implementation review

The starter driver was inspected. `internal/platform/api.go` now implements initialization and a v1 migration, account reads/creation, transfers and batches, holds/capture/release, entries, summaries, and basic idempotency persistence. The HTTP server handles SIGINT/SIGTERM and closes gracefully.

## Remaining correctness gaps

This implementation is not acceptance complete. Recheck and finish these before relying on it:

- Idempotency response persistence is separate from the transaction that applies effects, leaving a crash window and concurrent-key race.
- Transfer reversal is not implemented.
- Some mutations read account state through the DB pool while their transaction is open; batch state/response versions may be stale, and subsequent updates may not see staged values.
- Request object validation is incomplete for some routes (unknown fields and optional versions need consistent validation).
- Tenant-local sequence numbers currently use a global AUTOINCREMENT sequence; gaps are allowed, but snapshot max handling and the required tenant-local semantics need review.
- Migration movement ordering is correct, but opening-entry ordering across tenants and sequence locality need review.

The binary builds. No performance sweep was run. Source facts should be rechecked before continuing.
