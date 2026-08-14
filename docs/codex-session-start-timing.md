# Codex `SessionStart` timing gate

[한국어](codex-session-start-timing.ko.md)

The native `darwin-arm64` release gate measures the command users receive, not a
synthetic executable or `version --json` proxy:

```text
${PLUGIN_ROOT}/bin/launch.sh hook codex session_started
```

The gate reads that command and its two-second timeout from the generated
`hooks/hooks.json`, then runs it from the generated onedir package. Each of the
20 samples launches a new process with a generated valid `SessionStart` envelope
and unique hermetic home, temporary, Codex-home, and workspace directories. An
empty owner-only OAuth metadata marker exercises the selector-available branch
if startup ever regresses into full runtime composition; no selector request is
started.

Within a Codex runtime build, the first configured hook runs before any
`version --json` smoke so a warm-up cannot conceal its cost. Final release
assembly repeats the gate from `dist/codex` before the final-package version
smoke. Passing requires all of the following:

- every process exits zero with literal empty stdout and stderr;
- the first configured hook and every sample finish below the configured 2,000
  ms timeout;
- nearest-rank p95 is at most 1,000 ms, preserving a 50% budget margin; and
- at least 20 new-process samples are measured (the tool accepts at most 100).

The closed JSON evidence records only the target, release-manifest identity,
process model, sample count, first/p50/p95/max latency, configured timeout, and
pass/fail. It never records callback input or output, user prompts, credentials,
environment values, or local paths. Run the gate after assembling a native
package with:

```bash
make codex-hook-timing
```

Normal `startup`, `resume`, and `clear` callbacks are fail-open no-ops before
runtime composition. `compact` alone opens the minimal artifact store needed to
restore the existing instruction reference. The 24-hour crash-residue sweep runs
on `UserPromptSubmit` and before compact restoration, so moving normal starts off
the full path does not remove privacy cleanup.

This gate supports the built artifact on the Apple-silicon Mac where it runs. It
does not establish live Codex hook delivery, signing/notarization, quarantine
behavior, or clean-machine installation.
