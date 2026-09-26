# Structural revision: implemented and practically checked

The candidate adds selective official-document reference prompts, scoped completion
obligations, read-only checkpoint preparation, provenance-bearing recall and
actionable request recovery. The new interfaces are implemented and locally/native
validated. The targeted Korean repair episode passes all10 artifact/state checks.
The original two-call result remains **one pass and one incomplete episode**;
the third call is a different, separately frozen repair condition, not a rewritten
score or an additional favorable replication.

## Product and provenance

- Initial implementation: `1626dc6c6f542b4d556921d704e5884cc59ed44a`.
- Recovery repair: `391dd8e71c9842716c5113af35cd25bdde6206b3`.
- Repair freeze: `4b9bfeb5f59ebeed473cbfd250a9406a734e0855`, before the call.
- Repair manifest SHA-256: `c1c9392fdafc2fa6e7b36715175f2b30fcf4538ebacda7924b5e7c5a069e088f`.
- Final local native archive SHA-256: `f26b77374e38261acd3296739093a4e388f1cd25cdef48a2b3de16dec0417b7d`.
- Exact requested tuple: `gpt-6-luna / medium / codex-cli 0.158.0-alpha.2`.
  Client SHA-256: `50ab38ba21d0d9f8346f32f41848382f15b556190f3c7a07e885a4fb73e379c8`.
- Documentation guide1, assistance guide8, impact guide3, maintainability guide2;
  reuse guide2 and all48 canonical methods remain. Package version1.5.0 is an
  unpublished candidate. The active installation is unchanged and PR95 stays Draft.

The initial `a9dd0435...` package and prior `1aae2efe...` RC archive were retained
separately before rebuilding. Exact hashes remain in their original manifests;
the currently named local ZIP is not substituted for historical bytes.

## User-visible behavior

The documentation command emits fixed EN/KO reference instructions and separate
publisher/URL/version/read metadata. Existing authorized host tools read actual
pages. Native code performs no web/model call, does not retain document bodies,
and does not turn external text into permission or routing policy. The initial
catalog covers8 publishers; unknown publishers remain unverified and use the
guide's first-party discovery path. Catalog membership, caller-reported reading,
version declarations and actual application remain distinct.

Separate closed v1.1 contracts preserve all41 original v1.0 schema bytes and the
SQLite format. Preparation reads an explicitly enrolled task's current version
without initializing/migrating/expiring backups. Submission still uses CAS,
idempotency and existing authority/privacy rules. Scoped recall filters delivered
source evidence while preserving applicable accepted intent and each original
snapshot's revalidation footprint. Its new projection preserves lifecycle/support
and checkpoint metadata, including valid previously accepted checkpoints.

Scoped completion reuses the existing required-criterion semantics. It returns
ready work separately from input-dependent work and does not turn an optional
suggestion into a mandatory blocker. Missing required evidence prevents conditional
finish, while caller reports remain unverified. The existing task fallback,
stateless decision route and inactive model profiles are retained.

## Bounded live observations

| Condition | Complete episode | Official read + cited answer | Plan + scoped deletion | Checkpoint | Tool actions | Call seconds |
| --- | --- | --- | --- | --- | ---: | ---: |
| Initial EN, guide7 | pass | pass | pass | version3 | 26 | 205.873 |
| Initial KO, guide7 | incomplete | pass | pass | stayed version1 | 21 | 126.948 |
| Targeted KO repair, guide8 | pass | pass | pass | version2 | 23 | 211.217 |

All three calls completed as CLI turns; no model transport failure, substitution
or automatic outcome retry occurred. Each context was fresh and received no prior
answer or review. No stronger model assisted inside a Luna outcome. Two read-only
Sol/medium development audit lanes (four delegated turns) informed source repairs outside treatments;
their usage is unavailable and not counted as0.

The repair call uses the same Korean task/source transition/expected artifact,
fresh seeded continuity and a new package. Its adapter additionally permits the
existing read-only export operation after the earlier harness denial. Those
differences prevent an isolated causal or efficiency claim. The task explicitly
requests the new interfaces; this does not prove spontaneous discovery.

The integrator inspected all six public messages in the repair call and the actual
persisted checkpoint. It chose Bay80 for48 attendees, step-free access and cost6000
within the settled7000 ceiling, kept booked=false, cited the live Python3.12
JSONDecoder mapping null→None, deleted only the obsolete proposal, preserved the
accepted record exactly and saved a nonempty task checkpoint with agent-reported
support. It asked no unnecessary permission question. The checkpoint does not
claim native source/execution attestation; its source freshness remains unknown.

The repair still guessed two invalid envelopes: documentation `read_state: read`
and assistance `task_kind: mixed`/obligation `kind: question`. Both were corrected
within the same call. A wrong reference-directory search also failed. Two direct
decision-command attempts are visible and the final message reports their rejection;
their native stdout was not retained, so exact statuses are unavailable despite
shell exit0. Canonical-method application is not established by this smoke test.
These failures remain in the evidence; no further outcome call is required.

| Counted resource | Initial EN | Initial KO | Repaired KO |
| --- | ---: | ---: | ---: |
| Native-adapter attempts | 19 | 13 | 15 |
| Native OK / invalid / no native response | 15 / 3 / 1 | 6 / 3 / 4 | 13 / 2 / 0 |
| Input tokens | 570144 | 595265 | 706955 |
| Cached input subset | 496896 | 533248 | 645120 |
| Output tokens | 9032 | 4954 | 8973 |
| Reasoning-output subset | 1690 | 558 | 2568 |

All three explicitly reported cache-write0; none of these five usage categories
is missing. Total accounting is3 calls,70 tool actions,47 adapter attempts,
544.038 call-seconds,1872364 input (1675264 cached) and22959 output (4816 reasoning).
These are accounting totals across different conditions, not pooled outcome scores.
Billing, backend echo, human scores and account-side isolation remain unavailable.
Preparation, native tests and integration time are outside model-call time.

## Failures, repairs and verification

- Initial development checks found formatting/import/type issues and overly complex
  helpers; those were repaired before outcome calls. A v2 failure-response test
  caught null request IDs outside its schema; v2 now explicitly permits them.
- Independent source review caught credential-bearing URL fragments, optional
  inputs becoming required, accepted-checkpoint reader incompatibility and trusted
  asset failures misclassified as caller errors. Focused regression controls pass.
- Initial package checking reached a stale pre-revision distributable launcher.
  Full native assembly replaced that candidate output; the retained old archive
  was not rewritten or relabelled.
- Initial KO used memory schema1.0 for the new prepare operation. Guide8 adds
  complete v1.1 examples; native diagnostics name the required version, known
  failing field and allowed values without echoing rejected content. Guessed
  synonyms remain rejected. The English export rejection was in the evaluator;
  product export was unchanged.
- The old repair verifier initially rejected the deliberately changed guide.
  It now runs unchanged against its original source boundary; current historical
  outcomes are also byte-compared against baseline. No verifier or score is edited.
- New fixture file reads explicitly use UTF-8 for Windows compatibility. Hosted
  Windows execution belongs to exact-head CI; live Windows Codex remains unavailable.

`make release-check` passed on the initial and repaired product commits, including
frozen SQLite lifecycle/backup/deletion, hook timing, package entry points and the
new installed command fixtures. The focused final native probe verified122
canonical external/embedded members, including47 schema pairs and EN/KO assets,
stateless noninitialization, read-only preparation, scoped recall and deletion.

The complete required source command passed at `4b9bfeb5f59ebeed473cbfd250a9406a734e0855`:
`make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check`.
It includes8 documentation controls,15 structural-revision controls, existing
memory/source/selector checks,251 installer/lifecycle tests and npx smoke. The
subsequent UTF-8 fixture-only change passed focused lint and the native122-member
probe. Final exact-head CI and source/package identities are recorded in PR95.

Historical verification preserves3054 prior evaluation files and41 original
schemas. Unchanged earlier pilot/practical/Astra/repair verifiers pass at their
declared source boundaries; Sol376-file and Luna362-file backend exports also pass.
See [offline verification](verify.py), [original report](../revision-v2/REPORT.md),
[summary](summary.json) and [outcome lock](outcomes.lock.json).

## Limits and handoff

This is bounded usability and deterministic qualification, not broad superiority,
noninferiority, savings, universal application or prompt-injection-immunity proof.
Public official documents were fetched during the calls with URL/time/digest
receipts. No hidden reasoning, raw event stream or credential is retained. Raw
synthetic task/public-message/artifact evidence stays within the declared evaluation
boundary; product memory stores bounded public state only. Disposable auth copies
were removed. Global settings/memories and the active plugin were not changed.

Native macOS is locally qualified; native Windows is evaluated by hosted CI.
Live Windows Codex and destructive account-home/clean-machine tests are unavailable
or outside this task. No universal release blocker is invented from those limits.
No further model study or human recruitment is needed for this bounded revision.
Remaining release action: review the Draft PR and obtain separate explicit
merge/tag/publication/active-install authority.

`plan_objective_measure`: close the observed request-recovery gap and verify useful
official-source, continuity and completion behavior without changing historical scores.
`do_scope`: one diagnosed product/guide repair and one prospective Korean Luna call.
`check_rule`: independent artifact/store checks, actual source read, public messages,
all attempts and required source/native gates, with missing evidence explicit.
`act_standardize_decision`: retain the qualified RC behavior and recorded limits;
stop model evaluation and hand off the exact pushed candidate for review.

OpenSocrates grounding: pdca-cycle@3
