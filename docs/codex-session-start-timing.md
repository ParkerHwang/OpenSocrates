# Codex SessionStart timing gate

[한국어](codex-session-start-timing.ko.md)

The Go-native timing harness reads the exact generated `hooks/hooks.json`
SessionStart command and two-second timeout. The command invokes the package's
`runtime/<target>/opensocrates[.exe]` directly; there is no first-party shell,
PowerShell, JavaScript or Python launcher. Run after the complete package is
assembled, before warming the runtime with a version smoke:

```text
go run ./src/opensocrates/cmd/opensocrates-dev acceptance timing --package /absolute/path/to/codex-package --runs 20 --report build/evidence/codex-hook-timing.json
```

The native target must match the executing macOS ARM64 or Windows x64 machine.
The closed inventory and release identity are verified before execution. Each
`startup` and `compact` source has 20–100 fresh processes with distinct hermetic
home/temp/Codex-home/workspace roots and generated callback input. This is a
synthetic timing test, not a live conversation or authentication probe.

Every process must exit zero with empty stderr. Startup output is empty;
compact output must match the exact bounded decision discovery envelope. Each
sample must finish below 2,000 ms and nearest-rank p95 must be at most 1,000 ms,
preserving 50% margin. Record the first process before any runtime smoke.
The report contains target/artifact identity, configured timeout, process model,
source sample counts, first/p50/p95/max latency and pass/fail. It retains no
callback input/output, prompts, credentials, environment values or local paths.

SessionStart ordinary startup/resume/clear callbacks remain fail-open no-ops;
compact restores discovery without selecting a method or opening an artifact
store. Input is bounded and inspected in memory. Legacy cleanup belongs to its
explicit compatibility lifecycle; default discovery does not initialize user
storage or authentication. Missing/unsafe/read-only cleanup state is skipped
rather than repaired.

Run on each claimed native target. A Mac timing pass does not establish Windows
timing, live Codex delivery, host trust, signing/notarization, quarantine,
SmartScreen or clean-machine installation. Previous release timings remain
historical and cannot qualify the Go executable.
