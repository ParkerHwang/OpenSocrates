# Verification and evaluation

Implementation correctness, package delivery, actual host use, and improved code
quality require different evidence. Keep each result tied to the exact commit,
configuration, platform, commands, and artifacts that produced it.

## Deterministic acceptance cases

These are requirements for new tests, not results already obtained.

| ID | Scenario | Observable passing condition |
| --- | --- | --- |
| T01 | Memory disabled; status and normal decision/hook calls | No memory directory, database, scan, model request, or new persistent content |
| T02 | Enrollment preview/apply and policy disclosure | Preview creates no state; apply binds the matching scope/policy and records actual authorization attribution, never inferring consent from a flag |
| T03 | Submission/start/compaction hooks | Existing bounded discovery behavior; no database access or workspace list/read for memory |
| T04 | Forged runtime support or applied state in input | Reject/normalize to the caller's actual attribution; no fabricated observation/application proof |
| T05 | Accepted intent and conflicting current source | Return both, distinct authority/scope, and an unresolved conflict |
| T06 | Inference/proposal/import claims human acceptance | No implicit promotion; explicit attributed acceptance operation required |
| T07 | HEAD/ref change or incompatible worktree | Reconcile or reject reuse; no stale code claim or checkpoint silently treated as current |
| T08 | Staged/unstaged edit with unchanged HEAD | Relevant observation invalidated or revalidated against actual content |
| T09 | New untracked caller outside original source file | Old negative search claim invalidated through scope inventory; no false no-callers result |
| T10 | Configuration/lockfile/registration or dynamic edge changes | Revalidate affected claims; unresolved dynamic coverage stays unknown |
| T11 | File rename, symlink/reparse replacement, or change during read | Safe re-resolution or bounded unavailable/unstable result; no mixed snapshot or outside-root read |
| T12 | Fresh process with no old conversation or native memories | Recover explicit decision/checkpoint and current citations from the enrolled store |
| T13 | Pack/scan budget exhausted | Omitted scope and next retrieval reported; no silent loss of required constraints |
| T14 | Duplicate evidence, contradictory records, incomplete adapter | Preserve lineage/conflict/unknown status; no false independent corroboration or complete graph |
| T15 | Concurrent record/checkpoint updates | One expected-version mutation wins; conflict returned to the other; no lost update |
| T16 | Repeated idempotency key, interrupted commit | Same intent yields same committed result; changed payload rejected; no duplicate side effect |
| T17 | Corrupt/busy/read-only/unsafe store | Bounded unavailable result; ordinary authorized work and decision command remain usable; no alternate store |
| T18 | Interrupted migration; newer schema on older runtime | Atomic old/new state or recoverable owned backup; no silent data loss or unsupported write |
| T19 | Disabled/read-only modes, management, and export | Mode matrix honored; management does not enable recall; export is bounded JSON with consistent pagination and no private roots/source dumps |
| T20 | Delete record/project and repeat deletion | Record tombstone blocks identified replay while enrolled; full deletion removes registration/tombstones; fresh enrollment never autoimports; unrelated files preserved |
| T21 | Prune and uninstall/update/purge | Retention references honored; uninstall preserves memory; explicit memory deletion targets only owned files |
| T22 | Missing memory needed for a real authorization/constraint | Do not treat absence as permission; hold only dependent action and continue independent work |
| T23 | Prompt injection in imported record/source text | No command execution, routing/permission change, or authority escalation |
| T24 | Secret canaries in tracked/ignored/source/query/error inputs | Forbidden bytes absent from DB, journal, temp, export, backup, and logs |
| T25 | Index rebuild/eviction with retained decisions | Rebuild removes only derived state and preserves authoritative record versions |
| T26 | Oversized/malformed/unknown-field requests | Bounded rejection before uncontrolled allocation; existing runtime remains intact |

Use real filesystem/process fixtures for identity, locking, interrupted writes,
and deletion cases. Schema-only mocks are insufficient. Native Windows reparse
and ACL cases require Windows evidence; POSIX fixtures are not a substitute.
Secret-canary tests demonstrate the declared cases, not universal secret detection.

## Coding acceptance fixtures

| ID | Fixture | Passing behavior |
| --- | --- | --- |
| C01 | Existing helper satisfies new behavior | Discover and inspect it; reuse or justify a better scoped alternative; relevant tests pass |
| C02 | Similar code with incompatible semantics | Avoid forced common abstraction; explain the actual semantic conflict with source evidence |
| C03 | Shared return/error contract change | Identify affected callers/co-edits and verify the changed contract |
| C04 | Dynamic/configuration-driven dependency | State coverage limit and investigate the relevant configuration/runtime evidence; no false exhaustive claim |
| C05 | Feature followed by a second change | Review produces grounded findings; follow-up avoids regressions and unnecessary duplication/coupling |
| C06 | Mechanical edit | Complete accurately without unnecessary memory/architecture procedures |

Fixture tests should judge externally observable behavior, not exact wording or
whether an agent printed a required checklist. Include successful separation as
well as successful reuse. The reference solution is one acceptable implementation,
not a formatting template.

## Host and packaging gates

| ID | Required evidence |
| --- | --- |
| H01 | Existing normal hook timing, bounded entry, and zero-selector-call contracts still pass |
| H02 | A live Codex task explicitly retrieves an installed memory pack and completes a dependent fixture; denied/missing hooks remain a tested fallback |
| H03 | Exact available GPT-6 model/effort/client combinations recorded; unsupported combinations explicitly omitted from support claims |
| P01 | Frozen Apple-silicon macOS runtime imports SQLite, creates/queries/migrates/deletes an isolated fixture store, and includes required schemas/guides |
| P02 | Equivalent native Windows x64 fixture plus ownership/ACL, locking, reparse, and lifecycle evidence |

Preserve the established source-level commands from CONTRIBUTING:

```text
make bootstrap
make format-check
make lint
make generated-check
make content-check
make adjudication-check
make docs-check
make governance-check
make package-check
make security-scan
make smoke
make installer-check
```

Add focused memory/coding checks to the appropriate targets; first run targeted
tests while implementing. Run `make release-check` for native macOS release
qualification and the documented Windows build plus
`uv run --locked python tools/check_windows.py --packages` for Windows evidence.
Do not claim commands ran merely because they are listed here.

A docs-only change needs documentation checks, not an invented product-suite pass.
When required platform checks cannot run, keep the missing evidence explicit and
finish independent implementation work. Do not mark a release fully qualified.

## EVAL-01: controlled multi-session quality study

Freeze prompts, fixtures, follow-up changes, controls, judge rubric, model/effort,
client/plugin hashes, time/token limits, and failure rules before outcomes.
Store the protocol separately from outcomes. Never rewrite old evaluation records.

Four arms isolate effects:

| Arm | Configuration | Interpretation |
| --- | --- | --- |
| A | Codex without OpenSocrates | Ordinary host baseline |
| B | Released v1.4.0 | Existing judgment controller |
| C | v1.5 candidate with coding guides, memory disabled | Guidance contribution |
| D | Same candidate with enrolled project memory | Memory-enabled treatment; isolated replay below identifies retrieval contribution |

Hold model, tools, task prompts, initial repository, source transitions, and budgets
constant within comparisons. Primary runs disable native host memories/context
recall in an isolated supported harness; do not modify the user's active settings.
If isolation cannot be demonstrated, label that run confounded and do not use it
to claim an incremental memory effect. Native-memory interaction is a separately
reported secondary condition.

Each naturalistic episode has two fresh sessions. Session one explores/changes a repository
and may record public state under its arm. Session two receives the same follow-up
request after a predeclared code/ref/configuration change, with no previous chat
history. Code and ordinary project files are available to every arm; only D receives
its dedicated memory store. Hidden tests and held-out changes are never stored
in the agent's memory or retrieval inputs. First-session patches may differ across
arms, so this measures end-to-end treatment effects, not an isolated second-session
retrieval effect.

Add a paired second-session replay for C versus D: take the same frozen first-session
repository artifact, public decisions, task, model, and source transition; start two
fresh sessions and vary only availability of the first-session memory store. Freeze
that store before authoring/exposing the hidden follow-up. Both arms get identical
ordinary project files, prompts, tools, and budgets. Report this replay separately
from naturalistic runs. Do not attribute differences between different starting
patches solely to memory retrieval.

Initial pilot: four fixture families (positive reuse, false similarity, added
untracked caller, mechanical edit), four arms, three available GPT-6 models, one
episode per cell: at most 48 episodes / 96 sessions. Add paired C/D replay for two
of those frozen fixtures across three models: 12 additional sessions, for a maximum
of 108 pilot/replay sessions. This is an engineering pilot,
not a superiority study. Run model/host feasibility smoke first. Missing models
remain missing cells, not silently substituted models or excluded failures.
Publish the chosen per-session limits in the frozen run configuration before calls.

After repairing pilot failures, freeze a separate held-out protocol covering
shared contracts, intent/source conflict, branch/worktree resume, and dynamic
dependencies in Python and TypeScript fixtures. Choose sample size and effect
criteria before outcomes, based on the intended claim and available resources.
Do not turn the small pilot into a statistical quality claim.

Measure separately:

- Retrieval: citation validity, relevant-decision recall, irrelevant/stale material,
  omitted dependencies, unknown coverage, and pack size.
- Coding: functional correctness, regressions, appropriate reuse/separation,
  dependency coverage, grounded review findings, and follow-up maintainability.
- Continuity: recovered goals/constraints/remaining work, repeated completed work,
  branch leakage, and stale decision misuse.
- Cost: actual input/cache/output tokens, elapsed time, scans, storage, and failures.

Use blinded diff/behavior review by repository-competent humans where available;
model judges are supplemental and record their exact identity and independence.
Do not count multiple runs of one judge as independent human ground truth. Remove
arm/version labels from review packets without deleting evidence needed to judge
correctness. Record non-blindable cues as a limitation.

All attempted runs, timeouts, interruptions, missing outputs, and retries remain
in denominators. A saved patch before timeout is not a completed delivery. A
candidate privacy/authority/cross-worktree critical failure blocks promotion until
repaired and checked in a separately identified run.

## Release and claim boundary

Functional release qualification requires deterministic gates, required source
checks, supported native packaging, and accurately scoped live host evidence.
Quality claims additionally require the relevant controlled outcome evidence.
Do not claim universal maintainability, dependency completeness, cost reduction,
or GPT-6 superiority from passing package tests or a small pilot.

If the candidate increases overhead without reliable coding benefit, reduce its
intervention/retrieval burden or keep the memory feature experimental. If recall
precision is the bottleneck, improve retrieval before increasing model effort.
