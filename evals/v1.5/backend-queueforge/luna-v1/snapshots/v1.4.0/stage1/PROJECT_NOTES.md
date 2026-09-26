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

## Implementation progress

The initial service implementation is in `cmd/server/main.go`; the root README
records run instructions and known service limits. SQLite stores jobs and
idempotency commands, uses WAL and synchronous FULL, and serializes writes through
database transactions. The test clock is read per operation when configured.

Verified during this session: `go test ./...` passes (the supplied driver test),
`go build -o bin/queueforge ./cmd/server` succeeds, and an owned loopback process
returned valid health, creation, and claim responses. That smoke check was stopped.
The detailed concurrency, cross-process, restart, and lifecycle boundary cases
still need dedicated automated verification; the smoke check does not establish
them. Recheck the source before relying on these notes.
