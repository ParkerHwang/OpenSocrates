# Completed provisional Astra review

All **60 prepared packets** have a validated first-pass assessment and a separately
recorded evidence-phase assessment: 52 expanded packets plus eight diagnostics,
48 English and 12 Korean. First passes were locked at commit
`ae03321843018a0e4a3b625ba19cfe2b62af9669` before any deterministic disclosure.
The combined final rating lock was committed at
`23daa6d80db6a2877cad41d4dd0bd37ed017905b` before analytic unblinding.
No candidate artifact, historical outcome, frozen rubric or first-pass rating was
changed. No candidate outcome cell was rerun. **Human reviews: 0; human scores: null.**

These are one Astra configuration's provisional assessments. Completion of this
lane does not establish held-out quality, profile validity, human acceptance,
account-side memory isolation or a v1.5 release. PR #95 remains Draft and the
product/package version remains 1.4.0.

Product inputs are unchanged from the pre-review candidate: assistance guide 4,
mutation guide 2, and the [qualified candidate ZIP](../../validation-receipt.guide4.json)
SHA-256 `a3a65b1ee9671c8e2d2bf684e4ae64b3a5cfc048105052fd14819589a90557c1`.
Earlier outcome conditions retain their own package/guide hashes. The review
itself loads no product plugin; plugins and hooks are disabled for the assessor.

## Provenance and recoverable records

- Exact user agent: `opensocrates_bilingual_reviewer`; `gpt-6-astra`, `xhigh`,
  `read-only`. [Archived definition](reviewer-definition.toml), SHA-256
  `324906ab9460043d75202b199167cf2f8590941014a0a06c2459294a2cfb48d5`.
- The CLI has no exposed custom-agent invocation flag, so the exact behavioral
  TOML was loaded through a named disposable configuration profile. Only metadata
  name/description was omitted from runtime settings. Model, effort and sandbox
  were also pinned explicitly. The non-model preflight verified role text and
  read-only permissions. [Runtime profile](runtime-profile.toml), SHA-256
  `89f5aeb44fa112fa9eb003a4f7dd809a70b8541b7c74150b91e2bbbff4dadba9`.
- Client: ChatGPT desktop-bundled `codex-cli 0.155.0-alpha.16.3`, SHA-256
  `c67698d0990aae05211d9c43ab343ad9517e406824dea77eca103a2806232b3a`.
  Completed requests establish access to the requested tuple on this client/account
  condition. Independent backend model echo and billed cost remain null.
- Fixed [judge procedure](../../JUDGE_PROCEDURE.v2.md), SHA-256
  `be161958546ac752ce516805cdbfad97a1c5b08b0a1f9bcee04e26d36782e12e`.
  Each invocation used a new isolated workspace/profile with hooks, plugins,
  native memory/import, web and delegation disabled. No implementation conversation,
  other assignment's ratings, treatment map or hidden checker was delivered.
  EN/KO partners were separate in the initial pass. All copied input hashes and
  disposable credential cleanup checks passed; account-side isolation is unproven.
- Initial review [v1](../astra-xhigh-v1/manifest.json), corrected schema
  [v2](../astra-xhigh-v2/manifest.json), smaller assignments
  [v3](../astra-xhigh-v3/manifest.json), and final single-packet
  [v4](manifest.json) were separately frozen before their calls. The final manifest
  SHA-256 is `2f146e46d38c3278eae6b9dca95f666f30088a22714382f2f965f871fd541712`.
- [Final lock](locks/all-ratings.lock.json), [joined assessments](unblinded-assessments.json),
  [descriptive synthesis](synthesis.json), [all request receipts](review-usage-ledger.json),
  [integrator audit](integrator-audit.json), and [claim-specific readiness](readiness-assessment.json).
  The [analysis scope](../astra-xhigh-v3/ANALYSIS_SCOPE.md) was committed before
  analytic unblinding. All 60 source result files match pre-review commit `cccc2f6`;
  the [integrity receipt](analysis-input-integrity.json) pins their bytes.

The judge classified blinding as limited for 50 packets and intact for 10. These
are declarations, not a universal blinding attestation. Memory references and
characteristic wording can reveal conditions. Fresh contexts are not independent
human raters; the scoring streams share the same synthetic artifacts.

## Findings and their limits

**Coding:** Three of six invoice artifacts have a real static shipping defect:
`subtotal == 0` is used as an emptiness test. A nonempty zero-priced line therefore
receives zero shipping instead of 700 cents domestically or 2000 internationally.
The affected packets are [89067e22cbf3cead](../astra-xhigh-v2/inputs/first/89067e22cbf3cead.json),
[8b2269d24162dda4](../astra-xhigh-v2/inputs/first/8b2269d24162dda4.json) (both Luna-alone
repetitions), and [910ff109ba7de051](../astra-xhigh-v2/inputs/first/910ff109ba7de051.json)
(one installed-Luna repetition). The other installed-Luna output and both Sol
outputs track actual emptiness. The [frozen checker](../../checks_v2.py) omits the
nonempty zero-price case. All six old deterministic flags stay unchanged. This
single task does not estimate a general Luna–Sol gap or treatment effect.

One EVAL-01 output, [28931385f4a0932b](../astra-xhigh-v2/inputs/first/28931385f4a0932b.json),
also admits fractional seats and returns floating-point amounts. The behavior is
visible, but the guard was already absent in the author-written seed; the other
three outputs add it. A future fixture should make the allowed seat domain
explicit. Do not call this an established memory-caused regression. Developer
collaboration artifacts in both languages otherwise received task and
maintainability scores of 4; missing execution receipts still leave critical
verification gates unassessable.

**Collaboration:** The Korean diagnostic
[b86f97dc91521c4f](../astra-xhigh-v2/inputs/first/b86f97dc91521c4f.json) contains the
actual $100 budget-increase approval question in `public_messages_by_turn[1][2]`,
before the final message. The reviewer correctly distinguishes this from the old
final-message-only false flag. In the separate English expanded failure
[d9fee7df784166df](../astra-xhigh-v2/inputs/first/d9fee7df784166df.json), earlier
messages were not retained. Its question delivery stays unassessable; the Korean
run cannot reconstruct the English history. Required questions, answers about
capacity versus attendance, budget authority and continuing the task are judged
from available public messages, not from artifact booleans alone.

All 12 language pairs were matched within cohort, task family, condition, model
and repetition. Four pairs have a one-point lower Korean communication score;
one expanded installed nondeveloper pair has a one-point higher Korean initiative
score. Other available paired axes match, while missing values remain null.
Three of the communication differences belong to different diagnostic conditions;
they are not pooled into a language effect. Denser Korean public audit prose was
a provisional communication concern, not evidence about internal reasoning cost.
Required content must not be removed merely to shorten output.

**Memory and review evidence:** Both guide-2 memory-arm finals disclose unfinished
scoped forgetting, although the judge calls one gate failed and the other
unassessable. Three diagnostic packets also show the withdrawn capacity retained
in accepted records. Correct artifacts do not erase these obligations. Conversely,
the later guide-4 final-state checks pass, but the packet views do not supply the
operation evidence needed to judge exact deletion mechanism/scope. H02 views also
lack sufficient retrieval detail for the judge. These are packet-coverage limits;
they neither prove universal activation nor erase separately scoped engineering
receipts. A [post-lock supplemental index](supplemental-evidence-index.json) locates
78 unchanged source receipts for later review; it was not delivered to this judge.

**Assessor limitations:** The model called the retention flag for
[117cc94a4fb2b69d](../astra-xhigh-v2/inputs/first/117cc94a4fb2b69d.json) a false negative.
The integrator disagrees: its only record is `proposed`, while the
[checker](../../diagnostic_runner_v3.py) deliberately requires `accepted` records.
The text preserves intent, but the lifecycle condition fails. This correction is
separate from the untouched model judgment. The model also assigns efficiency 3
to one EVAL-03 packet using only aggregate counts/timing, while 11 similar packets
remain unassessable. That sufficiency inconsistency prevents comparative efficiency
interpretation. One venue packet's empty `unresolved` array versus its availability
caveat is a plausible minor consistency issue, not a clearly specified hard failure.

The model emitted 82 missing-evidence entries and eight entries labelled rubric
defects. These are entries, not unique packets or eight verified bugs. The
integrator's nine cited findings distinguish supported behavior, checker coverage,
input-domain limits, assessor error and genuinely missing evidence. Raw scores,
flags and reasons are preserved.

## Per-lane and per-language record

`score:count` describes the task-outcome axis; U means unassessable. These are
scope summaries across conditions, not treatment comparisons. All six dimensions,
null/NA reasons, per-condition strata, and the 12 paired differences are in the
[synthesis](synthesis.json). Critical status is fail if any recorded gate fails,
otherwise unassessable if any gate is unassessable, otherwise pass. Gate granularity
varies, so these are **not accepted-run or product-success rates**.

| Cohort / lane | Domain | Locale | Packets | Task-outcome score counts | Critical pass / fail / unassessable |
| --- | --- | --- | ---: | --- | --- |
| diagnostic-v3 / DIAG-dialogue | general | en | 1 | 4:1 | 1 / 0 / 0 |
| diagnostic-v3 / DIAG-dialogue | general | ko | 1 | 4:1 | 0 / 0 / 1 |
| diagnostic-v3 / DIAG-memory | general | en | 1 | U:1 | 0 / 0 / 1 |
| diagnostic-v3 / DIAG-memory | general | ko | 1 | 2:1 | 0 / 1 / 0 |
| diagnostic-v4 / DIAG-memory | general | en | 1 | 2:1 | 0 / 1 / 0 |
| diagnostic-v4 / DIAG-memory | general | ko | 1 | 2:1 | 0 / 1 / 0 |
| diagnostic-v5 / DIAG-memory | general | en | 1 | U:1 | 0 / 0 / 1 |
| diagnostic-v5 / DIAG-memory | general | ko | 1 | U:1 | 0 / 0 / 1 |
| expanded-guide2 / EVAL-01 | coding | en | 4 | 3:1, 4:3 | 0 / 1 / 3 |
| expanded-guide2 / EVAL-02 | coding | en | 6 | 2:3, 4:3 | 0 / 3 / 3 |
| expanded-guide2 / EVAL-02 | general | en | 6 | 3:1, 4:5 | 5 / 0 / 1 |
| expanded-guide2 / EVAL-03 | general | en | 12 | 4:12 | 6 / 0 / 6 |
| expanded-guide2 / EVAL-04 | general | en | 6 | 2:1, 3:1, 4:3, U:1 | 0 / 1 / 5 |
| expanded-guide2 / EVAL-05 | coding | en | 4 | 4:4 | 0 / 0 / 4 |
| expanded-guide2 / EVAL-05 | coding | ko | 4 | 4:4 | 0 / 0 / 4 |
| expanded-guide2 / EVAL-05 | general | en | 4 | 4:3, U:1 | 0 / 0 / 4 |
| expanded-guide2 / EVAL-05 | general | ko | 4 | 4:4 | 0 / 0 / 4 |
| expanded-guide2 / H02 | general | en | 2 | U:2 | 0 / 0 / 2 |

The overall critical-status counts are 12 pass, 8 fail and 40 unassessable both
before and after evidence. Only one axis changes score/status after disclosure:
EVAL-03 efficiency null to 3, qualified above. The evidence phase used fresh
contexts with their own locked first passes, so any change could include rerating
variation; it is not a causal estimate of evidence disclosure.

## Attempts, failures and usage

There are **59 review/transport invocations** and **50 accepted assignment
responses**: 17 first-pass assignments and 33 final evidence assignments. Every
first-pass assignment held at most four packets; continuations reduced that to
two and then one. No model or effort was substituted.

| Execution event | Count | Handling |
| --- | ---: | --- |
| Schema-rejected first review request and zero-packet transport diagnostic | 2 | Kept with null usage; v2 added explicit JSON types without changing the rubric. |
| Calls reaching the 900-second bound | 3 | Two v2 four-packet calls and the last v3 two-packet call; kept with null usage. |
| Coordinator interruptions after the first two timeouts | 2 | Stopped queued dispatch; retained partial receipts and null usage; verified unchanged inputs and removed disposable profiles. |
| Citation validation rejections | 2 | Both A16P1 responses and usage retained; v4 clarified named-field syntax and reviewed packets individually. |
| Accepted responses | 50 | All structured fields, citations, identity and immutable first-pass checks passed. |

Two additional local non-model configuration inspections are retained separately.
The first rejected unsupported `--strict-config`; the corrected inspection verified
the exact role text and read-only permissions. They made no model call.

Available review usage totals: **7,515,751 input**, including **5,951,488 cached
input**; **492,837 output**, including **101,910 reasoning-output tokens**.
Reported cache-write input sums to 0, with seven calls missing that category.
All five token categories are missing for seven invocations, so complete totals
are null. Do not add cached input to input or reasoning output to output. Billed
cost and independent backend model echo are null. There are 609 observed tool
actions; three invocations have missing tool counts. Summed call wall time is
19,394.020 seconds, including parallel calls, not end-to-end elapsed time. These
are review resources, separate from candidate resource outcomes. No raw reasoning
or event stream is retained; only synthetic/public assessment evidence and receipts
are stored inside this evaluation boundary.

## Verification and next action

The complete review verifier checks frozen bytes, original result anchors,
all 60 initial/final assessments, scope, citations, identity, phase order,
first-pass preservation and cleanup. Ten in-memory corruption probes confirm that
wrong model/effort, fabricated human/backend identity, missing packets, changed
initial grounds, bad scores and invented citations are rejected. The full source
and installer suite passed at `ae03321`; no product, guide, canonical schema or
packaging input changed in this lane. [Source validation receipt](../astra-xhigh-v2/source-validation.json).
Exact final-head CI and the current commit are recorded in PR #95 and issue #94.
The user's original untracked agent definition remains preserved.

No numerical quality/noninferiority margin or held-out sample size can be
justified from one provisional assessor, selected authored tasks, uncertain rater
calibration and missing practical-loss tolerance. Human review remains unavailable;
that does not prevent completion of this AI-review lane. No held-out call is made,
no profile is promoted, and no release/version claim is synchronized.

The next bounded preparation is a **new** prospective fixture/checker version
covering nonempty zero-price orders, an explicit seat domain and accepted-memory
lifecycle, with complete public dialogue and privacy-safe operation/state receipts.
Calibrate those quality measures on additional independent tasks and justify a
claim-specific practical tolerance before freezing any held-out protocol. Account-
side isolation, billing, live Windows Codex and separately authorized destructive
host qualification remain attached to their own claims; they do not negate this
completed review. No human recruitment is required to hand off these provisional
results.
