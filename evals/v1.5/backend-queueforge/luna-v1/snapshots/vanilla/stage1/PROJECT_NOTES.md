# Maintained project notes

Accepted items are authorized intent; proposed items are not.

```json
{
  "accepted": [
    {
      "id": "accepted-0",
      "summary": "Preserve acknowledged jobs and lease fencing across restarts."
    },
    {
      "id": "accepted-1",
      "summary": "Keep tenant namespaces isolated; synthetic tenant headers are not production authentication."
    },
    {
      "id": "accepted-2",
      "summary": "SQLite WAL and synchronous=FULL remain required; do not trade durability for throughput."
    },
    {
      "id": "accepted-3",
      "summary": "Current source and task contracts govern facts; bounded continuity summaries do not grant authority."
    }
  ],
  "proposed": []
}
```

## Progress

- Implemented server startup, SQLite schema and transactions, tenant-scoped jobs, idempotency records, batch submission, claim reconciliation, lease mutation endpoints, stats, and optional file clock.
- Preserved `go.mod`, `go.sum`, and the supplied platform driver helper/test.
- `go test ./...` and `go build -o bin/queueforge ./cmd/server` passed after implementation.
- Initial live smoke attempt exposed an environment process-list/launch issue; HTTP behavior, concurrency, two-process sharing, and crash durability remain to be verified. Review transaction behavior and add focused service tests before treating this as complete.
