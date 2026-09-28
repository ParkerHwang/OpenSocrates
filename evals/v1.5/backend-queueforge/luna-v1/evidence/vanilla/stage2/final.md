Implemented the follow-up across the existing enqueue, claim, and mutation paths. Added version 1 to version 2 migration, scheduling and retry fields, priority ordering, transactional admission limits, cancellation, and snapshot keyset listing. Updated the README and project notes.

Verification passed: `go test ./...`, `go test -race ./...`, build, and loopback checks for legacy replay and lease continuity, retry timing, priority eligibility, quota and cancellation contention across processes, batch rollback, pagination snapshots, and unchanged bytes on future-schema refusal. Concurrent migration checks passed. `go.mod` and `go.sum` are unchanged; all owned test processes were stopped.

The Python harness emitted a macOS `xcrun` cache diagnostic, but each reported check completed successfully. Test scripts and databases remain in `.owned-temp`. No commits were made.
