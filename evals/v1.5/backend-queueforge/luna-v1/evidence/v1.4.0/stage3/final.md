Fixed the two correctness gaps reported in `FEEDBACK.json`:

- Job submission now rejects explicit `null` input fields instead of treating them as zero values and applying defaults.
- Legacy idempotency comparison now resolves an omitted `max_attempts` to `3` before comparing commands.

Documented these boundaries in [README.md](<WORKSPACE>/README.md) and recorded progress in [PROJECT_NOTES.md](<WORKSPACE>/PROJECT_NOTES.md).

**Checks:** `go test -race ./...`, build, the existing loopback verification harness, and focused single/batch null rejection and zero-side-effect checks passed. Python emitted a nonfatal macOS `xcrun` cache-file warning during harness execution. `git diff --check` passed; `go.mod` and `go.sum` are unchanged.

The feedback’s load results remain diagnostic because its artifact gate failed. I made no performance or durability changes based on those measurements. No owned test server remains running.
