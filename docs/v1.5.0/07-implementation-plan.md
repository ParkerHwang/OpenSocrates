# Implementation plan

## Planning coverage

Root question: How can v1.5.0 deliver source-grounded coding continuity across
fresh sessions while preserving the current judgment and privacy boundaries?

Tree type: `how`. Decomposition axis: product responsibilities. The branches are
policy/contracts, durable storage, current-source knowledge, context delivery,
coding judgment, host/model integration, and verification/distribution. This is
a work decomposition, not proof that the proposed design improves outcomes.

Branches are mutually clear by ownership: storage does not infer meaning, indexes
do not set intent, retrieval does not accept decisions, and host delivery does not
certify application. Their data dependencies are explicitly sequenced below.
Coverage is checked against every requirement in 01 and every case in 06.

Status: all work packages below are planned; no implementation or model-quality
result is claimed by this documentation package.

## Ordered work packages

| Work | Scope and deliverables | Dependencies | Exit criterion / leaf test |
| --- | --- | --- | --- |
| W0 — Baseline and policy | Reconcile main/issues; freeze protocol; adopt narrow storage-policy amendment; add machine-readable memory schemas and illustrative fixtures | Current source + this spec | Policy disclosures agree; strict schema/authority cases specified; baseline tests and unavailable evidence recorded |
| W1 — Enrollment and store | Owned project/worktree registry, SQLite records/versioning, explicit memory CLI, inspect/status, idempotency and conflict handling | W0 | T01–T06, T15–T18, T26 pass in disposable projects; disabled path creates nothing |
| W2 — Snapshots and freshness | Dirty/untracked inventory, safe source references, negative-query coverage, branch/worktree reconciliation | W1 | T07–T11 pass, including new caller with unchanged HEAD/source file |
| W3 — Retrieval and resume | Bounded lexical/Python structural index, recall/refresh, packs, checkpoints, fresh-session recovery | W2 | T12–T14, T22, T25 pass; cold process recovers only valid scoped context |
| W4 — Coding vertical slice | Reuse guide + source inspection + final code check + checkpoint; then impact and maintainability guides | W3 | C01/C02 first; then C03–C06; guides alter actual code behavior where justified |
| W5 — Lifecycle and privacy completion | Disable/export/delete/prune, exclusions, journals/backups, injection handling, uninstall/update behavior | W1–W3; before broad live use | T19–T24 pass; no real-project capture in fixture testing |
| W6 — Codex/GPT-6 integration | Controller pointers, packaged launcher/schema/guide identities, explicit live fixture flow, capability/model matrix; SDK changes only if justified | W4/W5 | H01–H03 and exact package content checks pass for claimed combinations |
| W7 — Evaluation and native release candidate | Frozen pilot/held-out runs, blinded review, supported platform builds, documentation/claim reconciliation | W6 | P01/P02 and scoped EVAL-01 report; failures preserved; release blockers explicit |
| W8 — Reviewable handoff | Independent review, fixes, final source checks, current Draft PR and durable evidence summary | W7 or explicit narrower handoff | Exact commit, results, missing evidence, remaining work, and next action recoverable without this conversation |

W1–W4 form the first end-to-end development target, but W5's privacy boundaries
must be applied from W1 onward. W5 is completion/adversarial verification, not
permission to store prohibited data earlier. Do not postpone identity/freshness
until after a demo that can silently use stale data.

## First vertical slice

Use one small synthetic Python repository with an existing shared helper and a
documented design constraint. Enroll the fixture, record an attributed decision,
observe source, retrieve reuse candidates, implement a small feature, and save a
checkpoint. Start a new process with no previous chat, add an untracked caller,
and request a follow-up change. The old negative caller claim must be rejected or
refreshed, the decision must be recoverable, and behavior tests must pass.

This slice is complete only with inspectable evidence and failure tests. A CLI
that saves/loads JSON or an agent that says it remembered is not enough.

## Proposed code boundaries

```text
src/opensocrates/project_memory/
  models.py           # closed records, scope, snapshots, packs
  transitions.py      # lifecycle, supersession, conflict rules
  registry.py         # explicit project/worktree enrollment
  store.py            # SQLite transactions, versions, migrations
  sources.py          # safe current-source observations
  freshness.py        # footprint and coverage invalidation
  index.py            # regenerable index generations
  retrieval.py        # scoped deterministic candidate selection
  assembly.py         # bounded evidence packs
  lifecycle.py        # disable, export, deletion, retention
src/opensocrates/cli/memory.py
plugin-src/shared/coding/
schemas/source/        # memory contracts through existing generators
tools/                 # focused memory/coding checks and evaluation harness
```

These names express ownership, not a required one-file-per-class design. Combine
small cohesive modules when simpler; split only when responsibilities or tests
justify it. Follow import boundaries and reuse audited primitives rather than
copying unsafe partial implementations. The source map in 09 identifies existing
integration points.

## Work coordination

One integrator owns shared schemas, identity rules, migrations, dependency locks,
and generated outputs. Independent read-only research/review may run in parallel.
Parallel implementation requires explicit file ownership and isolated worktrees;
workers must not revert one another's edits. Reconcile contract changes before
merging dependent work. Use the cheapest capable available model for bounded
subtasks and verify results; keep architecture and final review with the integrator.

Create focused commits/PRs with current descriptions. Do not push to protected
main. Keep the implementation as Draft until its declared review scope is checked.
Do not merge, tag, publish, or modify the active user installation from this kickoff.

## Checks and progress

Run meaningful focused checks after each work package and the required source
suite before requesting implementation review. Do not run the entire native
release suite after every documentation or localized edit. Expand tests only for
new code, failures, or unresolved risk. New generated schemas/guides require
canonical/generated equality; new storage requires native platform qualification.

Maintain a concise English progress record with:

- exact current and last-verified commits;
- completed work package and observable behavior;
- exact commands/results and checks not run;
- open decisions, known gaps, next action;
- whether evidence is implementation, local validation, native package, live host,
  or comparative quality evidence.

Do not retain raw sessions, private reasoning, source dumps, or authentication
material in progress/evaluation artifacts. Do not mistake a status update for a
completed work package.

## Priority, pruned work, and reopening conditions

Priority is correctness of identity/retention/freshness, then cold-start usefulness,
then coding benefit, then efficiency tuning. This ordering follows the user's
project-coding goal and the damage caused by stale or unauthorized memory; no
numerical utility score is claimed.

Pruned branches: cloud sync, universal graphs, raw transcript storage, automatic
global memory updates, and unsupported native platforms. Reasons are in 01.
Known coverage gaps: full runtime dependency resolution, untested language adapters,
future host APIs, and availability of every model/client/platform combination.
Each gap has a bounded behavior (declare unknown/unavailable) and a test in 06.

Reopen the architecture if scoped freshness cannot be made reliable, current
privacy bounds prevent necessary evidence, a host changes delivery capabilities,
or controlled tests show poor retrieval/quality despite correct mechanics. Reopen
only the affected decision; do not restart unrelated finished work.

Stop planning when each leaf has an executable test/next action. Implementation
should begin with W0/W1, not another broad requirements interview.
