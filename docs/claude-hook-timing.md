# Packaged Claude hook timing

OpenSocrates v1.1.2 was measured on macOS 26.5.2, Apple silicon (`arm64`),
through the actual packaged Claude `bin/launch.sh` and native runtime. The
reproducible command is:

```bash
make claude-hook-timing
```

The harness creates an owner-only temporary HOME and TMPDIR, a synthetic
instruction artifact with no user content, and native-shaped PostToolUse and
Stop envelopes. Every measured PostToolUse invocation must create a valid
authenticated read receipt. Every measured Stop invocation must return
literal-empty output and remove the artifact turn tree. Payloads, paths,
artifact content, session identifiers, stdout, and stderr are not written to
the report.

| Condition | Event | Runs | p50 | p95 | Max | p95 margin to 3s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Fresh package path, first invocation | PostToolUse receipt | 20 | 1,290.519 ms | 1,333.067 ms | 2,012.395 ms | 1,666.933 ms |
| Fresh package path, first invocation | Stop cleanup | 20 | 749.715 ms | 751.827 ms | 757.069 ms | 2,248.173 ms |
| Reused package path | PostToolUse receipt | 20 | 751.993 ms | 768.718 ms | 789.278 ms | 2,231.282 ms |
| Reused package path | Stop cleanup | 20 | 751.418 ms | 758.062 ms | 762.613 ms | 2,241.938 ms |

All 40 receipts and all 40 cleanups were verified. The worst p95 is
1,333.067 ms, leaving 1,666.933 ms—more than half of the 3-second host budget.
No sample reached the deadline, so the current timeout does not need to change.

“Fresh package path” means the package was copied to a new path before its
first invocation. The measurement does not purge macOS kernel, filesystem, or
hardware caches and makes no such cold-cache claim. It is evidence for this
local Apple-silicon machine only, not other machines or platforms.

The complete privacy-safe receipt is
[`docs/evidence/claude-hook-timing-v1.1.2-darwin-arm64.json`](evidence/claude-hook-timing-v1.1.2-darwin-arm64.json).
