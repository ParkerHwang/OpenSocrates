Implemented the QueueForge backend API, SQLite store, server CLI, focused tests, and [README](<WORKSPACE>/README.md). The supplied driver files and `go.mod`/`go.sum` were unchanged. No commit was made.

Verification passed with Go 1.26.3: `go build -o bin/queueforge ./cmd/server`, `go test ./...`, and `go vet ./...`. Tests cover concurrent idempotency, simultaneous claims, tenant isolation, lease fencing and deadline equality, heartbeat, max attempts, batch validation, and database reopen. A separate two-process check confirmed shared-database replay and claim, then read the acknowledged lease after SIGKILL and restart. All test processes were stopped.

Limits: there is no job retention or idempotency-key expiry. Tenant headers are synthetic identity; the service provides no real authentication or TLS.
