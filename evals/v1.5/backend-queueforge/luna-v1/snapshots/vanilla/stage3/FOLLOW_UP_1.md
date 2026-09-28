# Follow-up: scheduling, admission limits, cancellation and migration

Preserve the existing API and durable transaction/tenant/fencing contracts. Extend
working behavior rather than adding separate domain paths for batch and single
operations. Re-read current source; notes or memory cannot override it.

New stores/writes have PRAGMA user_version2. Migrate a genuine version1 database
created by the preceding executable without losing job IDs, attempts, leases,
completion results or idempotency. Migration must be transactional and safe when
two processes start concurrently. Unknown future schema versions fail startup
without changing persisted database bytes, schema or data (including journal-mode
header changes). Historical jobs get priority0 and retry_base_ms0;
do not retroactively apply a new retry policy to them.
Replaying an original version1 submission with its original key and body must
still return the original job after migration, including when the new fields were
absent. An explicitly changed command under that key must still conflict.

## New job fields and behavior

Both single and batch inputs additionally accept priority (integer -10..10,
default0), run_at_ms (nonnegative integer, default immediate; past values are
eligible), and retry_base_ms (integer0..60000, default1000). Return priority and
retry_base_ms in JOB. Preserve their accepted values for that job.

Claim only jobs whose available_at_ms<=now. Among eligible jobs use priority
descending, then created_seq ascending. A future high-priority job must not block
an eligible lower-priority job. Atomic bulk operations preserve the same rules.

For retryable fail, available_at_ms = now + min(60000,
retry_base_ms * 2^(attempts-1)). For expired leases, calculate from the expired
lease deadline instead of discovery time. Jobs exhausting max_attempts become
dead. A zero base gives immediate eligibility. Fencing and attempt accounting stay
unchanged. Read-only stats can still report stored states before a claim reconciles
expiry. This is at-least-once attempts with fenced completion, not exactly-once
execution of arbitrary external effects.

Add flags `--max-pending N` (default100000, tenant-wide ready+leased count) and
`--max-inflight N` (default100000, current nonexpired leases per tenant+queue).
Both are positive integers. Reject a new enqueue/batch that would exceed pending
limit with429 `capacity`, atomically. Identical replay must still succeed while
at capacity. Claim at inflight capacity returns the ordinary null-job response;
heartbeat does not consume another slot. Concurrent processes must jointly respect
both limits. Terminal states release pending capacity. Expired stored leases count
as pending until reconciliation; they do not count as current inflight leases.

`POST /v1/jobs/{id}/cancel`, empty object body: ready or leased ->cancelled and
invalidate the lease; already cancelled is an idempotent200. Completed/dead ->409
invalid_transition. Return200 `{"job":JOB}`. Update mutually exclusive stats.

## Bounded keyset listing

`GET /v1/jobs?queue=mail&limit=50&cursor=...` ->200
`{"items":[JOB,...],"next_cursor":STRING_OR_NULL}`. Queue optional; limit integer
1..100, default50. Sort created_seq ascending. First page fixes the upper creation
sequence so subsequent pages exclude later inserts and neither skip nor duplicate
the pre-existing matching jobs. Bind the cursor to its tenant and queue filter;
malformed or mismatched cursors are400 validation. No status filter is required.
Jobs remain listable after lifecycle transitions. Do not expose lease tokens.

## Verify before handoff

Use actual previous data and cross-process requests. Check legacy replay/lease
continuity, delayed retry boundaries, priority and FIFO ties, cancellation races,
quota contention, snapshot pagination during insertion and rollback on batch
failure. Re-run affected earlier tests and `go test -race ./...`. Provide public
source evidence for reused paths and explain the meaningful schema/index choices.
Do not change evaluator code, parent/sibling workspaces or global configuration.
