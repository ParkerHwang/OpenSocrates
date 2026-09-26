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
- Final follow-up narrows legacy idempotency compatibility to requests that omit all version 2 scheduling fields. Explicit version 2 defaults conflict with an original version 1 key; new version 2 keys retain resolved-default equivalence.

Verification:
- Go 1.26.3 `go test -race ./...` passed with the earlier and new tests.
- A loopback check built the preceding executable from this repository's baseline, created jobs and leases with it, then opened two current processes on its database. Replay, lease continuity, completion data, and two-process pending and inflight quota contention passed. An initial concurrent startup lock was fixed by retrying the read-only version check.
- The supplied driver helper and test, go.mod, and go.sum remain unchanged. No source commit was made.
- Stage 2 feedback reported one migration replay failure and passed its other 18 API scenarios. Preliminary single-client read warmup returned 15,097 successful requests; its measurement failed with transport errors, and other load cases were unavailable. No comparative speed conclusion follows.
- After the replay repair, Go 1.26.3 `go test -race ./...` and `go build -o bin/queueforge ./cmd/server` passed. The focused migration test now checks explicit version 2 defaults against a historical key and resolved defaults against a new key.

Remaining limits:
- The service has no real authentication, TLS, or payload execution. Attempts are at least once, while completion is fenced.
- The corrected artifact has not been rerun through the independent frozen API/load feedback; the earlier load data cannot validate its throughput. Submission still counts tenant pending rows, claim checks expiry and inflight rows under an immediate write transaction, and listing fetches page jobs by ID. No measured bottleneck justified changing these paths in this follow-up.
