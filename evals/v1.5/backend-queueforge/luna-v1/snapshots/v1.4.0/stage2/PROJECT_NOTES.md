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

The HTTP API, transaction logic and schema are in `cmd/server/main.go`; the
pinned SQLite registration and unchanged helper test are under
`internal/platform`. Schema version 2 adds priority and retry-base columns;
version 1 migration adds those columns transactionally with historical retry
base zero. A priority-aware claim index and tenant/state pending-count index
support scheduling and admission. Writers acquire SQLite's write reservation
inside their transaction so independent processes serialize admission and
lifecycle changes. The README contains current CLI limits and API additions.

Verified in this session: `go test -race ./...` and the build pass. An owned
loopback harness checked fail and expiry retry boundaries, priority selection,
pending/inflight limits, capacity replay, cancellation races and fencing,
snapshot pagination, invalid-batch noninsertion, two-process capacity
contention, concurrent v1 migration, replay and lease continuity, preservation
of a completed result, and future-version byte preservation. Every launched
server was terminated. The temporary harness is in
`.owned-temp/verify_followup.py`; rerun it after source changes.
The harness does not establish arbitrary exactly-once external effects or
production authentication, which are outside this service contract.
