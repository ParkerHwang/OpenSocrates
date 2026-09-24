# Candidate implementation status

The implementation remains Draft PR [#95](https://github.com/ParkerHwang/OpenSocrates/pull/95),
tracked by [#94](https://github.com/ParkerHwang/OpenSocrates/issues/94). Remote main
was reconciled at `5a2ff3c312e92aa8a44d0905465674d9a4e4f645`. Product/package metadata
remains 1.4.0; this is not a v1.5 release. No active installation or real project
was enrolled or changed.

## Source and integration

W0-W7 source slices implement stateless task-based assistance with candidate-only
profiles; separate explicit project memory for Git and non-Git roots; source
freshness and bounded cold recall; owner-only SQLite lifecycle; transactional
schema-1 to 2 migration and managed backup/deletion; bilingual general/coding
support; and frozen macOS/Windows packaging. The 48-method stateless decision
path and locked legacy SDK/CLI dependencies remain intact.

A live continuation exposed a scoped-forgetting gap. Supersession preserves
history, so assistance guide revision 4 now links conditional EN/KO mutation
instructions (revision 2) for preserving retained intent and deleting the exact
old record. The generated memory request schema now expresses the bounded
`authorization_basis`/`acceptance_basis` reference rule already enforced at
runtime. Negative/positive source and frozen-runtime tests cover the previously
rejected prose request and the valid `user:current-request` counterpart.

The [guide-4 validation receipt](../../evals/v1.5/expanded/validation-receipt.guide4.json)
records full source/installer checks at `6e843fb`, native `make release-check` at
`07611e5`, exact package/guide/schema identities, and external/internal/canonical
byte checks. All 41 schemas remain present; only the memory request schema changed.
Exact final-head hosted CI and the current commit are maintained in the PR/issue.
Live Windows Codex and destructive account-home lifecycle remain unverified;
hosted native fixtures are a different evidence layer.

## Outcome work and remaining gates

The original immutable engineering evidence is preserved. Its fuller audit covers
109 declared calls, including failed harness batches and missing receipts. The
new independent task matrix completes 50 quality-pilot cells with two repetitions
and two H02 cells: 68 calls, 49/50 strict artifact gates, and 2/2 dependent host
artifacts. Those artifact passes do not erase incomplete memory obligations or
missing dialogue evidence.

Separate diagnostics preserve four unsuccessful guide-3 memory calls (two with
parser-lost usage). After the reference-contract repair, two new EN/KO guide-4
calls pass both artifact and independent persisted-forgetting checks. Dialogue
traces demonstrate a legacy checker false negative when the necessary question
appears before the final message. No old outcome or rubric is rewritten.

The [provisional Astra review](../../evals/v1.5/expanded/reviews/astra-xhigh-v4/REPORT.md)
completes both locked phases for all 60 artifact/diagnostic packets using the
verified `gpt-6-astra` / `xhigh` / read-only agent definition. It retains all 59
review/transport invocations, including seven process/transport failures and two
citation rejections. Static inspection supports three invoice shipping defects
missed by the original checker; the integrator also corrects one judge
interpretation that ignored memory lifecycle. The review does not change old
outcomes, rerun candidate cells or establish human acceptance. Human scores
remain unavailable. Local native memory use/generation/import were
disabled in disposable profiles and local output/job tables are empty; account-side
isolation remains unproven. Memory comparisons are confounded. Backend model echo,
billed cost, adequate independent quality variance, numerical held-out margins,
and a held-out study remain unavailable. Candidate profiles are not promoted.

W8 has bounded pilots and a completed provisional model review, not held-out
outcome validation.
W9 supplies the source fixes, verified receipts, review packets and recoverable
Draft handoff. Read the [results](../../evals/v1.5/expanded/RESULTS.md),
[audit](../../evals/v1.5/expanded/AUDIT.md), and
[held-out readiness decision](../../evals/v1.5/HELD_OUT_READINESS.md) before making
quality, efficiency, memory-effect, or release claims.
