Fixed the v1 migration replay boundary. The original submission still replays when its retry field was omitted; an explicitly changed nonzero `retry_base_ms` now returns `409 idempotency_conflict`. I added an HTTP regression test and updated [PROJECT_NOTES.md](<WORKSPACE>/PROJECT_NOTES.md) and [README.md](<WORKSPACE>/README.md).

The focused tests, `go test -race ./...`, build, and `git diff --check` passed. The independent correctness check has not been rerun. Its load results were unassessable after the failed gate, so I made no speed change or throughput claim.
