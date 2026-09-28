Implemented the backend in [cmd/server/main.go](<WORKSPACE>/cmd/server/main.go) and added run instructions and documented limits in [README.md](<WORKSPACE>/README.md). The service includes tenant-scoped job routes, idempotent submission, batch insertion, lease operations, stats, SQLite WAL with synchronous FULL, and the optional per-operation clock file.

**Verified:** `go test ./...` passed, the required build succeeded, and a loopback smoke check confirmed health, job creation, and claim responses. The test server was stopped.

**Remaining limits:** the supplied test only covers driver availability; I did not add the requested focused automated tests for concurrency, tenant isolation, lease boundaries, atomic batch failure, shared-database processes, or restart durability. Those behaviors remain unverified. No external services were used.
