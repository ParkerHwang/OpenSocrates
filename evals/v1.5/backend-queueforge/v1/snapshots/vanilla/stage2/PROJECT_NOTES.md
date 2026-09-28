# Maintained project notes

Accepted intent: durable multi-tenant queue with transactional SQLite writes, fenced leases, scheduled priority claims, bounded tenant admission, cancellation, and snapshot keyset listing. Synthetic tenant headers are not production authentication. At-least-once attempts do not guarantee exactly-once external effects.

Current source: `cmd/server/main.go` owns flags and process lifecycle; `internal/queue/http.go` validates and routes requests; `internal/queue/store.go` owns schema migration, transactions and job lifecycle. Source and contracts govern implementation facts. Supplied module files and platform driver helper/test are preserved.

Decisions: schema version 2 migrates v1 inside `BEGIN IMMEDIATE`; old rows receive priority 0 and retry base 0. The original v1 idempotency command shape replays with new request defaults. Pending and inflight counts run inside the same write transaction as submission or claim. Claim reconciles expiry using the expired deadline for backoff. Listing cursors carry tenant, queue, last sequence, and the first page's upper sequence.

Verification: `go test ./...`, `go test -race ./...`, build, and existing two-process restart smoke check passed. A previous executable built from this workspace's HEAD created actual v1 data; two new processes migrated and read it, replayed the key, continued the lease, and exercised priority, retry, capacity, cancellation, and listing. An unsupported future version exited while database file bytes stayed unchanged. A failed intermediate expiry test assertion was corrected to the specified deadline plus backoff.

Final checks: the race suite, build, live migration check, and `git diff --check` passed after the last source change. Test server processes were terminated by their harness cleanup. No deployment or publication is authorized.
