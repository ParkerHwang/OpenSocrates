# Maintained project notes

Accepted intent:
- Keep SQLite WAL, synchronous FULL, tenant isolation, idempotency, and fenced leases across restarts.
- Extend the existing single and batch transaction paths for scheduling and admission limits.
- Preserve version 1 data and replay behavior; reject future schema versions without mutation.
- Current source and task contracts govern facts. These notes are bounded continuity, not implementation authority.

Current progress (verify against source):
- Version 2 migration runs under an immediate transaction. Historical jobs receive priority 0 and retry base 0; new jobs default to retry base 1000.
- Submission handles priority, scheduled availability, pending quota, and legacy replay. Claim reconciles expiration with deadline-based backoff, honors priority and inflight quota. Cancellation fences leases. Listing uses a bounded creation-sequence cursor.
- New tests cover scheduling, retry boundaries, quota rollback, cancellation races, pagination during insertion, migration continuity, and future-version byte preservation.

Verification:
- Go 1.26.3 `go test -race ./...` passed with the earlier and new tests.
- A loopback check built the preceding executable from this repository's baseline, created jobs and leases with it, then opened two current processes on its database. Replay, lease continuity, completion data, and two-process pending and inflight quota contention passed. An initial concurrent startup lock was fixed by retrying the read-only version check.
- The supplied driver helper and test, go.mod, and go.sum remain unchanged. No source commit was made.

Remaining limits:
- The service has no real authentication, TLS, or payload execution. Attempts are at least once, while completion is fenced.
