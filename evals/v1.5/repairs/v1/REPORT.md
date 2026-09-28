# Post-review repairs: checkpoint usability and GearDesk

This is the new repair boundary authorized after the larger GearDesk code review.
It is separate from every original model comparison and provisional review.
OpenSocrates remains an unpublished 1.5.0 release candidate; PR #95 remains Draft.

## Product repair

Product commit: `9260a1a1fe869b44cae9621e51797b801501af04`.
The previous request example claimed `runtime_observed`, which the runtime
correctly refused from a caller. Caller actions now have a schema restricted to
`agent_reported`, `inferred` and `imported`. Stored/returned native records retain
their full vocabulary, the defensive service guard remains, and SQLite layout
and migration are unchanged. The old example is corrected, and document validation
checks every example action. No stronger evidence is granted to an agent.

Assistance guide 6 links complete EN/KO checkpoint examples and create/inspect/update/
fresh-reference flow. Coding guides 2 narrowly cover operation-specific defaults,
mutable result ownership, missing historical facts and transaction-copy boundaries.
Normal task fallback and experimental/inactive model profiles are unchanged.

Focused source memory tests pass 28/28. Both packaged language examples pass actual
native create/inspect/update/replay/recall checks; forbidden support values reject
without a database write. All 41 external and 41 embedded schemas, plus assistance
and coding references (94 members total), equal canonical source bytes.
[Native receipt](native-package.json), [commands](commands.json).

## Derivative application repair and corrected measurement

The [portable GearDesk handoff](geardesk/README.md) includes original and repaired
synthetic sources, real prior-stage storage sources, diffs, frozen checkers and
compact evidence exports. The primary inspected delegated diffs and independently
ran the frozen checker on both derivatives.

| Condition | v1.4 generated app | v1.5 generated app |
| --- | --- | --- |
| Original strict final score, unchanged | 34 pass | 32 pass / 1 fail / 1 unassessable |
| Original code, corrected main checker | 34 pass | 34 pass |
| Original code, new supplemental checks | 20 pass / 5 fail | 14 pass / 10 fail |
| Repaired code, corrected main checker | 34 pass | 34 pass |
| Repaired code, new supplemental checks | 25 pass | 24 pass |
| Repaired app's own tests | 29 pass | 23 pass |

Check counts differ by applicable storage format; they are not quality percentages.
The old whole-quote comparison rejected a compatible default field. Corrected
checks preserve historical money/lines/audit/refunds and isolate migration from
unrelated cumulative accounting. Six deliberate predicate controls pass; an
unavailable-migration control leaves the independent main accounting check passing.

The baseline now refuses ambiguous historical mixed-item partial refunds rather
than inventing a 3,000/3,000 allocation, while preserving the known aggregate full
refund. New known line amounts preserve a 5,000 camera refund and 1,000 tripod
remainder despite current catalog changes. Both repairs reject invalid partial dates
and detach mutable results/replay evidence. The candidate uses one owned transaction
draft: the normalized 20-command batch's whole-store clone count drops from 20 to 1.
Migration/I/O and throughput are outside that measurement. All original inputs and
outcomes remain frozen; these derivatives are integrator-authored repairs.

## Bounded installed-package usability

The [manifest](usability/manifest.json) was committed at
`2dde5577ebbfebea7801d10846e798e9f4e08452` before any of its four outcome calls.
Manifest SHA-256: `0d28ef49d8601dbb8f6f2968bb136d496a45cf7b22e2c79bf14a1b6431bec584`.
The exact tuple is `gpt-6-sol / medium / codex-cli 0.158.0-alpha.2`, with the
unchanged client SHA-256
`50ab38ba21d0d9f8346f32f41848382f15b556190f3c7a07e885a4fb73e379c8`.
The first planned call also rechecks current access; it is included in the four.

New native macOS archive SHA-256:
`1aae2efefc76c4e628ad2da7a63174f5d96e093b984fe0ed5551b66eaa6dae0d`.
The previous local RC archive remains separately preserved under its original
`d1b8f9b4c1879bc1dcdee87c9e4ae45f1d93f484343e94c248d582b251709bc6` digest.
The retest uses temporary installed profiles, disabled hooks/native memories/import,
stable task IDs, accepted synthetic intent, exact artifact checks and current-source
correction. No outcome substitution or favorable-result rerun is allowed.

All **4/4 calls and 4/4 artifact/state episodes pass**, with zero failed model
calls, retries or substitutions. Seven checkpoint writes, four recalls and ten
inspects succeed (21 model-initiated memory operations, zero rejection). Both first
sessions reach checkpoint version2; fresh EN reaches version4 and KO version3.
Both continuations select Bay80 after Cedar changes64 to40, preserving the accepted
48-attendee/step-free/no-booking intent. The primary reviewed public command/message
order: create after source/choice, inspect the actual version, update after artifact
validation, and inspect the returned reference in the fresh session.
[Counted results](usability/summary.json), [integrator review](usability/integrator-review.json),
[immutable outcomes](usability/outcomes.lock.json).

| Language / stage | Saved version | Artifact | Model seconds | Tool actions |
| --- | ---: | --- | ---: | ---: |
| English create/update | 2 | Cedar64, revision1 | 118.539 | 19 |
| English fresh correction | 4 | Bay80, revision2 | 128.175 | 21 |
| Korean create/update | 2 | Cedar64, revision1 | 94.171 | 14 |
| Korean fresh correction | 3 | Bay80, revision2 | 101.984 | 16 |

Reported totals are 1,241,299 input tokens (1,082,880 cached), 16,663 output tokens
(2,613 reasoning output), cache-write0, 70 tool actions and 442.869 model-call seconds.
Cached input and reasoning output are subsets. No token category is missing;
billing/backend echoes remain null. The one nonzero tool action is an absent
AGENTS.md search. English continuation retains two selector submissions; their raw
status was not retained by the schema-filtered extractor, so no status is invented.
It also saves two continuation checkpoints rather than one. This is usability
with explicit metadata/guidance, not lower-overhead or autonomous-discovery proof.
Three implementation/preparation delegations are separate; their usage is unavailable.
Disposable auth copies were removed; no global settings or active install changed.

## Qualification and evidence boundaries

The complete source-gate invocation passed through smoke. Ten installer lifecycle
fixtures failed under restricted process inspection (241/251); the same disposable
suite passed 251/251 plus npx smoke with process inspection available. No real-account
purge/reinstall was run. Native `make release-check` passed at the product commit,
including frozen SQLite, deterministic generation, hook timing, schemas and package
entry points. Exact command scopes are in [commands.json](commands.json).

[Failures and repairs](failures.json) retain environment, harness, checker and
implementation failures. The initial native probe incorrectly required exit0 for
a deliberately invalid request; the corrected probe expects documented exit2 with
`invalid_request`. The prepared model runner's adapter copy arity was corrected
before freeze/calls. Neither failure is counted as a model outcome or hidden retry.

The [integrity verifier](verify.py) checks 2,097 unchanged historical files; current
`STATUS.md` is explicitly mutable. It runs the old practical/pilot/review verifiers
unchanged against historical commit `dd51e130f037544c5c75fdcc64beced49246b34b`.
This preserves their original functional-source scope without falsely requiring
today's repaired schema/guides to equal the old product. No old scores are rewritten.

Human review, billing, independent backend echo and account-side memory isolation
remain unavailable; no broad quality, efficiency or isolated memory-effect claim
follows. Live Windows Codex and physical clean-machine/destructive-host acceptance
remain unavailable or outside authorization. Exact final CI belongs to the pushed
commit handoff. Publication and active-installation replacement remain separate.

`plan_objective_measure`: repair the confirmed contracts and application boundaries.
`do_scope`: reversible product/guide/checker changes, derivative apps and four calls.
`check_rule`: frozen state/artifact checks, negative controls and retained failures.
`act_standardize_decision`: accept only passed repairs; hold stronger claims and
stop when the required handoff is complete.

OpenSocrates grounding: pdca-cycle@3
