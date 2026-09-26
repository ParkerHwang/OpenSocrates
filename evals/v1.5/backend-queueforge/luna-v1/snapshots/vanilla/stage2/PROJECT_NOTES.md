# Maintained project notes

Accepted items are authorized intent; proposed items are not.

```json
{
  "accepted": [
    {"id":"accepted-0","summary":"Preserve acknowledged jobs and lease fencing across restarts."},
    {"id":"accepted-1","summary":"Keep tenant namespaces isolated; tenant headers are synthetic context, not production authentication."},
    {"id":"accepted-2","summary":"SQLite WAL and synchronous FULL remain required."},
    {"id":"accepted-3","summary":"Current source and task contracts govern facts; bounded notes do not grant authority."},
    {"id":"accepted-4","summary":"Support schema v2 migration, scheduled priority retries, admission limits, cancellation and snapshot keyset listing."}
  ],
  "proposed": []
}
```

## Progress

- Extended the shared single/batch submission path with priority, scheduling and retry policy; transactional tenant pending admission keeps identical replay available at capacity.
- Added transactional version 1 to version 2 migration. Existing jobs receive priority 0 and retry base 0; legacy idempotency commands are compared using their original defaults. Version checks occur before journal-mode changes; transactional schema-lock DDL serializes concurrent first opens/migrations.
- Added priority and availability claim ordering, deadline-based expiry retry, tenant/queue inflight admission, fenced cancellation and tenant/queue-bound snapshot cursors.
- Verified source contains no lease token in ordinary job serialization. `go test ./...`, `go test -race ./...`, and server build passed. Owned loopback checks exercised fail retry boundary, future high-priority eligibility, cancellation fencing, replay at pending capacity, cursor insertion snapshot/mismatch, v1 leased-job and idempotency continuity, and two-process pending/inflight contention and a cancellation/completion race; invalid batch rollback and repeated simultaneous v1 migration; and refusal of a future schema with unchanged database bytes. All owned test processes were stopped; check scripts and databases remain under `.owned-temp`.
