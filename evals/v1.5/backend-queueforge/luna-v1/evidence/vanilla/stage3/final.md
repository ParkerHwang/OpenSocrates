Implemented the feedback repairs:

- Explicit `max_attempts: 0` now returns 400; omission still defaults to 3.
- V1 idempotency replay comparison now uses the legacy retry default of 0.
- SQLite uses one pooled connection per process so all operations receive the configured busy timeout. WAL and `synchronous=FULL` remain enabled.
- Added regression tests for validation, batch atomicity, shared-file contention, and v1 replay.

**Verification:** `go test -race ./...`, server build, and `git diff --check` passed. `go.mod` and `go.sum` are unchanged. The feedback load runs had failed correctness gates; I did not rerun the full workload, so the load impact remains unmeasured. The shared-file contention regression test uses two store instances, not two server processes.

Updated [PROJECT_NOTES.md](<WORKSPACE>/PROJECT_NOTES.md). No commit was made.
