# Implementation plan

Current completion authority: [Practical completion standard](PRACTICAL_COMPLETION.md),
revised by the user on 2026-09-26. Bounded usability and a small fair v1.4.0
comparison govern this release candidate. Statistical studies below describe
optional stronger-claim work, not release prerequisites. Frozen historical
evidence remains unchanged.

Status: source implementation and provisional review completed; practical
qualification and release-candidate packaging remain. Development reporting uses English.

## Work decomposition and coverage

Root question: How can v1.5.0 improve inexpensive-model task quality, preserve
strong-model quality with less unnecessary work, and provide useful continuity
and natural collaboration for developer and non-developer tasks?

This is a how-plan. The decomposition axis is implementation responsibility:
assistance policy, memory state, source evidence, agent behavior, host delivery,
and verification. These are candidate design branches, not demonstrated effects.
Policy does not persist memory; storage does not decide intent; source adapters
establish scoped facts; guides shape observable behavior; host delivery does not
prove application. Integration tests cover the dependencies across branches.

Every terminal work package below has a deliverable and an observable exit test.
Collective coverage includes A, U, G, T, C, H, and P acceptance families and all
five evaluation lanes in 06. Unknown profile efficacy and actual host/model access
remain measured implementation work, not unspecified product requirements.

## Ordered work packages

| Work | Scope and deliverables | Dependencies | Exit criterion |
| --- | --- | --- | --- |
| W0 - Baseline, contracts, and fixtures | Reconcile main/issues; freeze strict schemas, policy defaults, privacy amendment, general/coding fixtures, and study manifest | Current source and specifications | Source anchors verified; baseline checks recorded; every requirement maps to an executable fixture or study |
| W1 - Adaptive core | Pure assistance policy, task-based fallback, explicit stateless command, candidate profile format, authored EN/KO guides | W0 | A01-A08 policy/command fixtures pass; selected model unchanged; zero model calls and no workspace/persistent-state access; G01 and U01/U02 behavior smoke |
| W2 - Enrollment and durable state | Project/workspace registry, Git/directory discriminators, SQLite records, status/inspect, version and idempotency rules | W0 | T01-T06, T15-T18, T26 pass in disposable Git and non-Git projects; disabled path creates nothing |
| W3 - Source snapshots and freshness | Local text inventory, Git/dirty/untracked state, document/source references, negative-query coverage, safe identity checks | W2 | T07-T11 and G05 pass; changed documents and new callers invalidate old claims |
| W4 - Bounded retrieval and resume | Lexical/Python adapters, recall/refresh, evidence packs, checkpoints, scoped preference/decision continuity | W3 | T12-T14, T22, T25 and G04 pass; cold process restores relevant context with no transcript |
| W5 - Integrated behavior | General planning/research continuation plus code reuse, impact, maintainability, correction, and stopping behavior | W1, W4 | G01-G05, U01-U06, C01-C06 pass bounded behavior fixtures; compare actual artifacts, not checklist text |
| W6 - Privacy and lifecycle completion | Modes, export/delete/prune, exclusions, sidecars/backups, injection, uninstall/update | W2-W4; before broad live use | T19-T24 pass in both workspace kinds; prohibited content absent from declared capture surfaces |
| W7 - Codex/model/native integration | Launcher/generator/schema/guide identities, frozen SQLite, capability and exact model/effort matrix | W5, W6 | H01-H03, P01/P02 for claimed platforms; unsupported tuples remain explicit; candidate profiles are not promoted by packaging tests |
| W8 - Practical usability comparison | Approximately six matched released-v1.4/candidate scenarios; initial cap 24 model invocations, all attempts and observable artifacts/messages/state retained | Functional source/native qualification | Bounded results report improvements, ties, regressions and missing measurements; task fallback remains normal; no statistical proof or profile promotion required |
| W9 - Reviewable handoff | Independent review/fixes, final source checks, accurate support/claim docs, Draft PR | Completed declared scope | Exact commit, commands/results, missing evidence, remaining work, and next action recoverable without prior conversation |

Privacy boundaries apply from W2 onward; W6 is completion/adversarial verification,
not permission to retain prohibited content earlier. Profiles remain candidate
until the declared outcome criteria pass. Missing evaluation resources do not block
independent implementation; they do block profile promotion and unsupported claims.

## First complete slices

1. **General assistance without memory:** a routine edit finishes directly; a
   coupled planning task receives bounded structure; a consequential missing fact
   prompts one focused question while independent work proceeds. Compare actual
   behavior under the same selected model. This establishes W1 before storage work.
2. **Non-Git continuity:** enroll a synthetic local event-planning directory with
   a Markdown brief, accepted accessibility goal, and checkpoint. Start a fresh
   process, change venue capacity and one user constraint, and produce an updated
   plan. Recover the goal, reject stale facts, apply the correction, and retain
   only permitted public context. Test forgetting and an unrelated copied directory.
3. **Coding continuity:** enroll a small Python fixture with an existing shared
   helper and design constraint. Implement a feature, checkpoint, start a fresh
   process, add an untracked caller, and request a follow-up change. Revalidate the
   old caller claim, inspect reuse suitability, and pass relevant behavior tests.

Both continuity slices are release acceptance. The noncoding path must work
without Git and the coding path must preserve its stronger Git/adapter contracts.
A save/load demo or a policy receipt alone does not complete these slices.

## Proposed code boundaries

```text
src/opensocrates/assistance/
  policy.py           # pure task/profile rules and defaults
  profiles.py         # closed validated package configuration
src/opensocrates/cli/assistance.py
src/opensocrates/project_memory/
  models.py           # records, workspace variants, snapshots, packs
  transitions.py      # authority, lifecycle, supersession, conflicts
  registry.py         # explicit project/workspace enrollment
  store.py            # SQLite transactions, versions, migrations
  sources.py          # safe local-text and Git source adapters
  freshness.py        # footprint and coverage invalidation
  index.py            # regenerable metadata index generations
  retrieval.py        # scoped deterministic candidate selection
  assembly.py         # bounded evidence packs
  lifecycle.py        # modes, export, deletion, retention
src/opensocrates/cli/memory.py
plugin-src/shared/assistance/  # guide and canonical profile configuration
plugin-src/shared/coding/
schemas/source/              # independent assistance and memory contracts
```

Names express ownership, not one class per file. Reuse audited primitives, keep
pure policy/state logic separate from platform I/O, and avoid a persistent service.
Update canonical/generated assets together through the existing generators.

## Ownership and handoff

One integrator owns shared contracts, profiles, migrations, locks, and generated
outputs. Independent research/review can run in parallel. Parallel writers need
explicit file ownership and isolated worktrees; they must not revert others' work.
Use the cheapest capable available model for a bounded subtask, count all usage,
and verify delegated output before integration. Retain the selected primary model.

Maintain progress with exact commit, completed scope, tests/commands, live evidence,
missing checks, known limits, and next action. Use focused commits and a Draft PR.
The revised authority permits v1.5.0 candidate metadata and artifacts after
functional qualification. Do not merge, tag, publish, deploy, or update the active
installation without separate explicit authorization. A partial handoff must state its narrower completed scope.

## Priorities, excluded branches, and revision conditions

Priority order is shared behavior/contracts, adaptive core, useful memory with
freshness, integrated general/coding slices, native delivery, then outcome claims.
Storage and guidance may be developed independently only after shared contracts
are frozen. Do not let a coding pilot stand in for general product coverage.

Cloud sync, universal document connectors, automatic model switching, global
personality memory, and autonomous repository rewrites are excluded because they
add unrelated operations, privacy, or authority scope. Their omission is explicit;
no untestable miscellaneous branch remains hidden in the plan.

Revise a branch when a required general/coding fixture fails, a host cannot honor
a declared contract, or held-out results show added overhead or quality regression.
Retain the failure evidence, narrow the supported capability/profile, and update
all affected requirements together. The hierarchy organizes work; it is not proof
that text guidance or memory will produce a performance gain.
