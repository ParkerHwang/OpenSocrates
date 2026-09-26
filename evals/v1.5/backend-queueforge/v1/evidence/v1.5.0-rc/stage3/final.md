Fixed the migrated stage 1 idempotency replay failure. The replay fallback now accepts the original command when version 2 scheduling fields are absent and returns 409 when any is explicitly supplied. Added a regression test using a genuine stage 1 schema and documented the boundary in [README.md](<WORKSPACE>/README.md).

The focused race tests and server build pass. `go test -race ./...` still fails at the preserved lifecycle test’s immediate retry assertion: version 2 specifies a 1,000 ms default delay. I left the supplied test and that contract behavior unchanged.

The feedback’s load run had a failed correctness gate and lost transport in its measured window, so it did not justify an optimization. No server was started during this follow-up.
