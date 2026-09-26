Implemented the QueueForge backend with SQLite-backed jobs, idempotent single and batch submissions, tenant isolation, lease fencing, expiry reconciliation, stats, and graceful server shutdown. The supplied driver helper and exact `go.mod`/`go.sum` were preserved. No commit was made.

Verification passed: `go test ./...`, `go test -race ./...`, and `go build -o bin/queueforge ./cmd/server`. The reproducible [process check](<WORKSPACE>/scripts/process-check.sh) also confirmed distinct claims from two servers sharing one database and persisted leases after both servers were killed and one restarted. An initial simultaneous startup hit a SQLite lock; bounded startup retries fixed it, and subsequent runs passed.

Build and API commands are in the [README](<WORKSPACE>/README.md). Limits: tenant headers are synthetic authentication context, expiry is reconciled on claim, and sustained SQLite write contention may return 503.
