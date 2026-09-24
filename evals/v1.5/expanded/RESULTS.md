# Expanded pilot results and interpretation

The guide-2 matrix frozen at `9dd94c6f70ec2badd990aa306246e6dc89637b05` completed
all 52 scheduled cells and all 68 model invocations. Its 50 quality-pilot cells
passed 49 frozen artifact gates; both separate H02 artifacts passed. This is a
completed engineering pilot, not a held-out study or 49 fully validated user
outcomes. See [machine-readable results](summary.v2.json), [frozen tasks and
conditions](execution-freeze.v2.json), and [the audit](AUDIT.md).

| Lane | Frozen artifact gates | Model calls | Practical limit |
| --- | --- | --- | --- |
| EVAL-01 | 4/4 | 4 | Authored paired source replay, two repetitions; no new naturalistic four-arm study or maintainability ratings |
| EVAL-02 | 12/12 | 12 | Two tasks, Luna alone/installed and Sol alone; no observed correctness gap on these tasks and no gap-closure ratio |
| EVAL-03 | 12/12 | 12 | One mechanical task; same-model baseline, installed ablation, and extra wrapper remain distinct |
| EVAL-04 | 6/6 | 6 | Both memory arms explicitly reported incomplete forgetting; the old artifact gate did not measure that persisted obligation |
| EVAL-05 | 15/16 | 32 | One English installed cell failed the final-message question check; earlier public messages were not retained |
| H02 | 2/2 | 2 | Accepted activity code recovered into a dependent artifact, normal and disabled hooks; not universal native application proof |

All eight developer EVAL-05 cells pass their deterministic gates across EN/KO.
Seven of eight nondeveloper cells pass. The failing English final message says
it asked for a $100 increase, and the artifact correctly represents that pending
approval. Four public messages existed in the turn but only the final one was
retained. The strict failure is preserved; whether an earlier question occurred
is unassessable from that packet.

## Resource observations

Every number below is descriptive, not a savings estimate. Each arm has only two
repetitions of the same task. Samples share authored inputs and account conditions.
The standard deviations below have one degree of freedom and cannot support a
broad efficiency or quality noninferiority claim.

| Task / arm | Mean model-turn wall seconds | Sample SD |
| --- | ---: | ---: |
| Mechanical, Sol alone | 22.104 | 2.385 |
| Mechanical, Sol installed ablation | 21.718 | 0.712 |
| Mechanical, Sol extra wrapper | 28.396 | 3.666 |
| Mechanical, Astra alone | 24.465 | 1.506 |
| Mechanical, Astra installed ablation | 26.794 | 0.887 |
| Mechanical, Astra extra wrapper | 24.288 | 0.569 |
| General continuity, disabled memory | 88.916 | 15.835 |
| General continuity, enrolled memory | 218.904 | 13.856 |
| General continuity, maintained note | 114.506 | 4.624 |

The 68 turns report 13,410,514 input tokens, including 12,144,384 cached input;
156,380 output tokens; and 31,287 aggregate reasoning-output tokens. Cache-write
input is explicitly reported as zero. Categories remain separate; cached input
must not be added to input, and these counters are not an invoice or a measurement
of private thought. All 68 turns expose their usage; billed cost and independently
echoed backend identity remain null.

The ledger contains 540 observed tool actions, 24 failed tool actions, and seven
structured protocol-rejection observations. Actual policy and memory API totals
remain null because indirect shell/Python invocations can evade the lexical
classifier. Direct counts are lower bounds, not zero-filled substitutes. Per-cell
setup time, memory enrollment operations, note seeding, and total time including
setup are separate fields. Human note-maintenance time is unknown; note-update
correctness after the turn was not independently captured. Preparation and primary
agent/subagent usage are outside the treatment counters and are not assumed free.

## Guide-3 diagnostics and failure preservation

New guide revision 3 responds to an actual obligation missed by the artifact-only
EVAL-04 gate. Supersession preserves old summaries/history; scoped forgetting
requires preserving retained intent and deleting the exact old record. Both
local-language documented-payload tests and the rebuilt native package checks
pass, with all 41 schema bytes unchanged. The product/runtime protocol and the
48 canonical methods are unchanged; model profiles remain candidate.

The [v3 diagnostic freeze](diagnostic-freeze.v3.json) deliberately uses separate
tasks/conditions and cannot be pooled into v2. Its two memory calls returned CLI
exit zero, but an array-valued `inspect` response exposed a parser defect. Their
usage and public messages are missing, not zero. Persisted postchecks still show
incomplete memory state: the English case retained only a proposed replacement;
the Korean case retained the old accepted fact plus a proposed replacement.
Both failures remain in [v3 records](diagnostic-results-v3/).

The v3 English/Korean collaboration diagnostics retain all public messages.
Both contain an actual $100 approval question and the correct pending artifact.
The Korean turn asks the question before its final report, so the unchanged
legacy final-message checker fails despite the earlier question being visible.
This is a demonstrated rubric-placement error for that new Korean case. The
original strict score is unchanged, and the separately preregistered
any-public-message observation is positive in both languages. Human semantic
quality scores are still null.

The [v4 repair freeze](diagnostic-freeze.v4.json) changes only the diagnostic
harness's handling of non-object memory results and repeats the two affected
memory cases. Its positive/negative parser fixture preserves status and usage for
array, object, string, numeric, and null response payloads. These new attempts
are additional evidence, not replacements for the failed v3 calls.

## Review and claim limits

The v4 parser repair retained the exact failed acceptance requests: they supplied
ordinary sentences in `acceptance_basis`. Runtime validation already required a
bounded reference, while the published request schema and guide were broader.
Both v4 memory cases therefore remained incomplete. The verified fix aligns the
two memory authorization-reference schema fields with that existing restriction
and publishes an exact `accept` example using `user:current-request` in EN/KO.
Assistance guide revision is now **4**, and the conditional mutation guide is
revision **2**. Only the request schema changes among the 41 schemas; accepted
runtime values, storage behavior, model profiles, and canonical methods do not.

The [v5 freeze](diagnostic-freeze.v5.json) precedes the two new calls against this
package. **Both EN/KO cases pass the plan and persisted-forgetting checks.** Each
export has one accepted record preserving 52 attendees, step-free entry, quiet
room, the $1,400 ceiling, and no booking; the withdrawn capacity fact is absent.
Independent post-run inspect/export/recall all pass. See [all diagnostic results](diagnostic-summary.json)
and [blinded diagnostic packets](blinded-diagnostics/). These two successful calls
do not replace the four earlier guide-3 memory failures or prove general reliability.

The full new execution has **81 CLI invocations**: three access probes, 68 v2
pilot/host calls, six v3 calls, two v4 calls, and two v5 calls. All CLI processes
returned zero; two v3 memory calls lost event/usage receipts to the parser bug and
retain null usage. Parser-fallback event/action zeros in those immutable records
mean missing instrumentation, not zero work. The diagnostic summary normalizes
those observations to null. All other turns have exposed usage. No extra outcome
call was made after the final bounded correction checks passed.

There are 52 blinded v2 artifact packets, separate judge-evidence files, a fixed
[judge procedure](JUDGE_PROCEDURE.v2.md), and an unblinding map. Keep the map and
outcome summaries away from assessors until ratings are locked. The v2 packets
contain designated artifacts and final public messages; they are not full
filesystem or dialogue transcripts. V3 dialogue records remedy public-message
retention for their new condition only. Characteristic method wording and memory
references may reveal condition, so complete blinding is not guaranteed.

No independent human assessor has scored these packets, and no model-judge quality
score has been substituted. Local native memory settings were disabled and the
recorded local native output/job tables remain empty, but account-side isolation
is unproven. All memory-effect comparisons are labelled confounded. Numerical
held-out margins/sample size remain unfrozen; no held-out model call was made.
Package metadata stays 1.4.0 on a Draft v1.5 candidate. No release, universal
quality, model-equivalence, noninferiority, efficiency, or monetary-saving claim
is supported by this pilot.
