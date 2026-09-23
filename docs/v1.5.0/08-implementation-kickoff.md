# Implementation kickoff prompt

Copy the prompt below into a fresh Codex task with the repository and this document
package available. It starts implementation; this documentation task has not
dispatched it. The specification is the task input, not proof that features exist.

---

Implement OpenSocrates v1.5.0 from the English development specification in
`docs/v1.5.0/`. Preserve OpenSocrates as a general reasoning and judgment-support
system founded on task-aware text/context selection and delivery: what an LLM
receives can materially change the work it produces. Optimize the usefulness,
applicability, timing, consistency, and evidence quality of that material, not its
volume. Extend it with built-in local project memory, stronger coding-domain
support for reuse/dependency/maintainability decisions, and verified GPT-6
compatibility. The first new implementation workstream is coding continuity;
do not redefine the whole product as a coding-memory utility. Memory provides
context for fresh judgment, and coding guides provide domain evidence. Existing
non-coding judgments must remain supported without mandatory coding machinery.

The known baseline is released v1.4.0 at
`5a2ff3c312e92aa8a44d0905465674d9a4e4f645`. Reconcile current remote main before
implementation. The design worktree originally lived at
`/Users/parkerhwang/Documents/OpenSource/OpenSocrates-v1.5.0-spec`, branch
`docs/v1.5.0-development-spec`; those are location hints, not permission to discard
changes or assume the branch is still current. Keep this document package in the
implementation branch so the task is recoverable elsewhere.

Work, code comments, new development documents, progress reports, issue/PR text,
and final reporting must be in English. Preserve existing released EN/KO canonical
method behavior and explicitly satisfy the runtime locale compatibility rules in
04. Do not claim that English itself guarantees better performance.

Read the repository's AGENTS.md and CONTRIBUTING.md, then the v1.5.0 README,
01-scope-and-requirements.md, 02-architecture-and-operation.md,
03-data-and-interface-contracts.md, and 05-privacy-lifecycle-and-migration.md.
Read 04 before host/coding integration and 06–07 before freezing tests/execution.
Use 09 for source anchors and design decisions and 10 for the product-identity
clarification. Include G01–G03 in the appropriate behavior verification. Treat
examples as synthetic data.

You are authorized to implement this specification, including the narrow,
explicitly disclosed policy amendment for opt-in project memory described in 05.
The existing blanket workspace-retention restriction must be replaced only by that
scoped exception; it is not authorization for transcripts, source copies,
credentials, private reasoning, telemetry, or global memory mutation. Update the
policy and implementation coherently. Do not stop merely because the planned
policy amendment differs from v1.4; the amendment is part of this requested work.

Use a clean, focused implementation branch/worktree based on verified current main,
carrying these docs forward. Inspect existing worktrees, open/closed issues, and
PRs before creating duplicates. Preserve unrelated uncommitted changes. Do not
reset, clean, blindly apply a stash, or write directly to protected main.

Implement W0 through W8 in dependency order. Begin with explicit enrollment and
typed storage, then source snapshots/freshness, then bounded recall and cold-start
resume. Build the first complete reuse vertical slice before widening to impact
analysis and maintainability review. Complete privacy/lifecycle tests before broad
live use. Avoid a save/load-only memory demo or a collection of guidance files
without behavioral verification.

Keep the default `decision` command stateless, content-only, and free of model
calls. Add a separate explicit memory protocol. Preserve the 48 canonical methods,
their grounding/stop contracts, and the distinction between delivery, reported
reading, application, source freshness, and improved outcomes. Ordinary hooks
provide bounded discovery and must not initialize storage or scan repositories.

Use a built-in local implementation with SQLite and audited existing persistence
primitives. No separate Context Scout installation, cloud service, embedding API,
or new credential is required. Existing Context Scout ideas may inform an adapter;
do not copy local/private code without checking license and suitability. Exact
module/file names in the plan are responsibility boundaries, not an invitation to
overengineer trivial classes.

Treat current source as evidence of behavior, accepted decisions as intent, and
inferences as hypotheses. Bind code observations to project/worktree/snapshot and
dirty/untracked coverage. New callers invalidate negative claims even if HEAD or
the original function is unchanged. Do not merge checkpoint state across branches
or worktrees implicitly. A memory failure must not invent facts, erase constraints,
or create another store as a fallback.

Use disposable projects for enrollment, deletion, corruption, migration, concurrency,
and privacy tests. You may run local implementation checks and repair failures
caused by this change without asking after each step. Do not enroll the user's real
repositories, change global Codex memories/settings, purge an active installation,
or perform destructive host acceptance tests unless separately authorized.

For GPT-6, verify the actual surface's exact model/effort capabilities. Respect the
task's selected primary model; use available capable subagents only for bounded,
independent work with explicit ownership. Do not invent model aliases, force every
operation through Astra, silently replace missing evaluation models, or rewrite
historical evaluation evidence. Update SDK/CLI pins together only when justified
by compatibility tests. Use existing authorized Codex access for live probes; do
not create API keys or paid services to bypass a missing capability.

Freeze the evaluation protocol and budgets before outcomes. Compare the four arms
in 06 with controlled source transitions, fresh sessions, identical model/tool
conditions, and native-memory isolation. Keep failures/timeouts and missing cells.
Evaluate actual code and follow-up changes, not checklist wording. Passing offline
tests does not prove live host delivery or a quality improvement.

Run focused tests during development, then the required source suite and relevant
native macOS/Windows packaging checks. Verify frozen SQLite functionality and guide/
schema integrity, not just development-interpreter imports. If an environment or
model is unavailable, record the missing evidence and continue independent work;
do not fabricate a pass or repeatedly retry an unchanged blocker.

Maintain an English progress/handoff record tied to exact commits and commands.
Use focused commits. You may create/update an implementation issue and Draft PR
with the specification, current scope, test results, limitations, and next steps.
Attach any created PR to the Codex task. Do not merge, create release tags, publish
to npm/GitHub releases, deploy a site, or change the active plugin installation.

Use one integrator for contracts, migrations, dependency locks, and generated
outputs. Independent research/review may run in parallel. Parallel writers need
isolated worktrees and explicit file ownership; they must not revert others' work.
Review delegated results against source and evidence before integrating them.

Continue through the authorized implementation and verification rather than ending
with a plan. Ask only when a missing decision changes the actual scope/permissions
and cannot be resolved from the specification or current source. Resolve routine
details with the smallest design that satisfies the contracts. Document material
deviations in the decision log and update affected specs/tests together.

Completion means the declared implementation scope works, canonical/generated
outputs agree, required available checks pass, missing platform/model evidence is
explicit, privacy and failure contracts hold, and the Draft PR or equivalent
reviewable handoff can be resumed without this conversation. Report verified done,
remaining work, exact commit, tests, live/evaluation limits, and the next action.
Do not mark v1.5.0 released or claim universal quality improvement.

---

## Starting from another machine

Make the repository and the complete `docs/v1.5.0/` directory available first.
Replace the local worktree hint if needed; preserve baseline identity, requirements,
and authorization boundaries. No private memory store, authentication file, local
database, or prior transcript is needed to understand or execute this prompt.
