Implemented the QueueForge version 2 follow-up in the disposable workspace. The existing [submission, claim, and lease paths](<WORKSPACE>/internal/queue/store.go:238) now handle scheduling and admission; the same store adds [transactional migration](<WORKSPACE>/internal/queue/store.go:84), cancellation, and bounded keyset listing. [HTTP validation and routes](<WORKSPACE>/internal/queue/http.go:96), [CLI limits](<WORKSPACE>/cmd/server/main.go:24), tests, and README are updated.

The new indexes support priority claims, live lease counts, and tenant or queue pagination by creation sequence. Migration leaves historical retry bases at zero and preserves legacy idempotency fingerprints.

**Verification:** focused queue tests passed with `-race`; build, vet, driver tests, and `git diff --check` passed. Loopback probes passed for simultaneous two-process migration, legacy replay and live-lease continuity, historical expiry timing, cross-process limits, and future-schema file-byte invariance. Owned probe processes were stopped.

**Remaining test conflict:** `go test -race ./...` fails at the preserved `TestLifecycleAndIsolation` assertion on line 94. It expects immediate reclaim of a newly submitted job at lease expiry; version 2 requires that job’s default 1,000 ms retry delay. The supplied test was left unchanged.
