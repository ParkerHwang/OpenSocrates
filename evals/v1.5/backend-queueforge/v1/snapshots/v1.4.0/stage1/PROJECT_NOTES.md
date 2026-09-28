# Maintained project notes

Accepted intent:
- Preserve acknowledged jobs and lease fencing across restarts.
- Keep tenant namespaces isolated; synthetic tenant headers are not production authentication.
- Keep SQLite WAL and synchronous=FULL; do not trade durability for throughput.
- Current source and task contracts govern facts. These notes are bounded continuity, not implementation authority.

Current progress (verify against source):
- Implemented the server, SQLite schema, API handlers, idempotent submit and batch, claim and lease lifecycle, stats, and test clock.
- Focused tests cover concurrent duplicate submission, tenant isolation, deadline equality, heartbeat, stale token fencing, completion replay, batch validation and order, shared database claims, and maximum attempts.
- A manual loopback check opened two processes on one SQLite file, replayed through the second process, then SIGKILLed the first and confirmed the job remained after a new process opened the file. The first attempt revealed a concurrent schema startup lock; bounded startup retry fixed it.

Verification:
- `go test ./...`, `go test -race ./...`, and `go build -o bin/queueforge ./cmd/server` passed after the final validation change.
- The supplied `go.mod`, `go.sum`, driver helper, and driver test have no tracked diff.

Remaining limits:
- The manual two-process check covered replay and restart persistence, while the in-process shared-database test covered claim serialization. The manual check did not attempt simultaneous cross-process claims.
- This benchmark service has no real authentication, TLS, or job execution.
