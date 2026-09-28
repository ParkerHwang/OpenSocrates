# O24 Go/TypeScript comparison: live handoff

Status: **24 O-office episodes are running; no comparative quality result or
external qualification is complete.** This handoff belongs to Draft PR #95 and
issue #94. The original comparison draft is preserved byte-for-byte beside its
Go/TypeScript amendment.

The product baseline is `d0156a86cfd4dc197554f1be0261c258cec7da2e`.
The O24 execution checkout is the clean, no-longer-edited
`/private/tmp/opensocrates-go-ts-o24-execution-20260928` at
`88a1243d2dc0873d65e44a29db58283e5e7eb4e3`. The 24-cell frozen manifest
is [O24_FREEZE.json](O24_FREEZE.json), SHA-256
`730847ffea5ff543f8eac7af8e2bf356663aa568a024b063239270ce67aea21e`.
The exact host invocation is [O24_INVOCATION.json](O24_INVOCATION.json), SHA-256
`99fee33065dff444a9475f4a7f17c5cba036273e18d5ce79c18b3d2ce8ff64cd`.
The results root is `/private/tmp/opensocrates-go-ts-o24-results-20260928`;
the local coordinator began as PID `19850` in unified exec session `77265`.
These host-local paths are execution evidence, not portable replacements for
the committed protocol.

The hard O v2 fixture came from commit
`9ffd7a0b5c5590372e5896bfe8e7d88c03ca6018`. Its standalone descriptor,
independent verifier and `FREEZE_PREP.json` retain their original bytes. The
shared descriptor changes only the two relative path prefixes documented in
[O_V2_INTEGRATION.json](O_V2_INTEGRATION.json). Its 160-order, 219-event,
10-portfolio data room was controlled before calls: three positives passed,
18 deliberately defective controls were rejected, native static checks passed,
and strict child policy denied direct and symlinked private-oracle reads. The
older small O fixture remains controls-only and is not pooled with O v2.

The real role-client boundary was observed once with an exact approved helper
command, matched start/completion identity, zero exit and six expected canary
booleans. [PROBE_RESULT_V6.json](PROBE_RESULT_V6.json) retains the original
`isolation_verified: false` because an extra unclassified `item.completed`
`error` was counted by the frozen probe. The narrower primary decision is
documented in `BOUNDARY_GATE_DECISION.json` and checked against both that
result and `PROBE_RECONCILIATION_V6.json`. The error item's cause remains
unknown; the probe was not rerun. The client executable is
`codex-cli 0.158.0-alpha.2` with SHA-256
`c3e30211bd454da70ceb4d9cbc2e05fe6466812ab05c311c3bbff6addeb14202`.
The experiment records the shim hash separately. Every cell rehashes the
client, B/D archive copies, runtime/guide/schema files, checker executables
and verifier before starting. The shim does not rehash the underlying client
between roles; an observed mid-run change makes affected identity uncertain.

No-model checks on the exact O execution checkout passed:

- `run_main.py dry-run --task O`: 24 prepared, zero model calls.
- `verify_freeze`: ready, 24 unique IDs, 24 workers, no blockers.
- Focused observer/usage/boundary/lineage/qualification/export and dispatch
  controls passed; the dispatch control covers incomplete markers and
  observed overlap accounting.

The live runner atomically claimed all 24 O cells and recorded all 24 initial
role starts; this does not mean 24 episodes or artifacts passed. Use the
read-only monitor to distinguish role calls, terminal episodes and externally
qualified variants:

```text
python3 -B /private/tmp/opensocrates-go-ts-runner-20260928/evals/v1.5/orchestration/comparison-go-ts-v1/monitor.py --results /private/tmp/opensocrates-go-ts-o24-results-20260928 --coordinator-pid 19850
```

No model clock/token/tool/output budget or automatic retry is imposed; fast
mode is off. Failures, unknowns, null usage and partial versions remain. Each
cell uses its exact requested tuple for every native role and repair. After
all O generation is terminal, run external qualification **serially** on
locked disposable copies, with actual O-analysis version lineage and the
qualified-analysis dependency for each document version. A missing/failed
artifact is not scored as a fast efficient success. Per-call native token
fields are reported with missingness; cached input and reasoning output are
subsets, not extra tokens. Account-side model attestation, billing and
unobserved backend retries remain unavailable.

Next: wait for all 24 one-shot cells to reach terminal or explicit unknown;
audit the dispatch overlap/resource index and client identity; run the frozen
serial external verifier; synthesize first/final correctness, review and
repair receipts and whole-workflow usage. S24 and continuity8 retain separate
pending freezes. Do not merge, tag, publish, change active installations,
enroll a real project, or reset earlier evidence as part of this handoff.
