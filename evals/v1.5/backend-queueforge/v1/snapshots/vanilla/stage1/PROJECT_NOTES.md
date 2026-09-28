# Maintained project notes

Accepted intent: durable acknowledged jobs and lease fencing across restarts; strict tenant isolation; SQLite WAL with synchronous=FULL; source and task contract govern current facts. Synthetic tenant headers are not production authentication.

Current implementation: Go HTTP server in `cmd/server`, request validation and routing in `internal/queue/http.go`, SQLite schema and transactional queue operations in `internal/queue/store.go`. The supplied driver helper and module files remain in place. Jobs, idempotency records, and leases are stored in SQLite. The clock file is read on each request when configured.

Verification completed: `go test ./...` and `go build -o bin/queueforge ./cmd/server`; two live server processes used one SQLite file, claimed distinct jobs, were SIGKILLed after acknowledged responses, and a restarted process read both persisted leases. An initial simultaneous startup exposed a SQLite busy error during schema setup; bounded setup retries fixed it, and two subsequent runs passed.

Final checks: `go test -race ./...`, `go build -o bin/queueforge ./cmd/server`, and the local two-process check passed after the last code change. The process check was saved as `scripts/process-check.sh` for reproduction. No deployment or publication is authorized.
