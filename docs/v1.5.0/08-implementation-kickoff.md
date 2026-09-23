# Implementation kickoff prompt

Use the prompt below with the repository and complete specification package.
This document is prepared for execution; its presence is not a dispatched task.

---

Implement OpenSocrates v1.5.0 from the English specification in `docs/v1.5.0/`.
The product helps developers and non-developers get better work from their chosen
LLM through adaptive reasoning guidance, useful project memory, relevant evidence,
and natural collaboration. Coding reuse, dependency understanding, and
maintainability extend the general reasoning foundation.

Deliver four shared outcomes: improve inexpensive-model task quality; preserve
capable-model quality while reducing unnecessary work; maintain useful continuity
across sessions; and collaborate naturally through intent understanding,
proportionate initiative, correction, and completion. Treat Luna/Sol gap reduction
and Sol/Astra efficiency as separate measured hypotheses. Do not promise universal
model equivalence or treat shorter responses as proof of less internal reasoning.

Read AGENTS.md and CONTRIBUTING.md, then README, 10-product-identity-and-combined-capabilities.md,
11-adaptive-assistance-and-collaboration.md, and 01-scope-and-requirements.md.
Read 02, 03, and 05 before storage work; 04 before coding/host changes; and 06-07
before freezing tests and executing work packages. Use 09 for source anchors and
architectural decisions. This package is self-contained; no previous conversation
or product-development history is needed.

The reviewed baseline is v1.4.0 at
`5a2ff3c312e92aa8a44d0905465674d9a4e4f645`. Reconcile current remote main, existing
worktrees, and open/closed issues/PRs before implementation. Preserve unrelated
changes. Create a focused implementation branch/worktree from verified current
main, carry this package forward, and never reset/clean or push to protected main.

Use English for work, comments, development documents, progress reports, and PRs.
Preserve released EN/KO behavior; align new localized runtime guidance deliberately.
English/Korean interaction fixtures must test equivalent behavior.

Implement W0-W9 in dependency order. Begin with closed contracts, baseline fixtures,
and the adaptive core without memory. Then implement explicit enrollment, durable
records, source freshness, bounded retrieval, and cold resume. Complete both the
non-Git text-project and coding continuity slices. Apply privacy boundaries from
the first storage write and complete lifecycle/adversarial checks before broad use.

Use a small deterministic assistance policy with none/light/structured optional
support, versioned model profiles, and a task-based fallback. Candidate profiles
are for configured evaluation runs until validated. Preserve the selected model
and effort. Do not introduce a hidden model selector or assume model names prove
capability. Mechanical work bypasses extra policy/retrieval calls. Finish after
required checks unless new evidence or changes justify reopening the work.

Keep the existing `decision` command stateless, content-only, and free of model
calls. Preserve all 48 canonical methods, eligibility, complete-procedure grounding,
zero-to-two selection bounds, and stop contracts. Add explicit assistance and memory
commands with separate strict schemas; do not extend the existing closed decision
envelope casually. Hooks remain bounded discovery without source scans or writes.

Implement optional local memory with SQLite under the owned product data root.
No separate memory plugin, cloud service, new credential, or embedding API is
required. Support Git workspaces and non-Git local Markdown/plain-text directories
through a shared workspace identity and explicit adapter capabilities. Bind source
claims to content/inventory snapshots. Changed documents and new callers invalidate
old claims even when HEAD or the original source file is unchanged.

Current sources govern observed behavior, accepted decisions represent scoped
intent, and inferences remain hypotheses. Do not merge checkpoint state across
workspaces implicitly. Apply new user corrections to the next action and artifact;
update permitted scoped memory under existing enrollment policy. Do not build a
global personality profile. A memory failure does not invent facts, erase
constraints, or authorize an action.

You are authorized to implement the narrow policy amendment in 05 for explicitly
enabled project memory, coherently updating policy, schemas, and behavior. This
permits bounded public decisions/checkpoints/source metadata, not raw prompts,
transcripts, source-file copies, credentials, hidden reasoning, or telemetry.
Product configuration and the stateless assistance command must not retain user
content. Existing authorization is sufficient; do not add repetitive consent steps.

Use disposable fixtures for enrollment, corruption, concurrency, migration, deletion,
and privacy tests. Do not enroll real user projects, change global memories/settings,
purge the active installation, or perform destructive host tests without separate
authorization. Reuse safe source/persistence primitives after checking suitability.

Verify the actual host's exact model/effort/client capabilities. Respect the selected
primary model. Use bounded capable subagents only for independent work with explicit
ownership and verification. Do not silently replace missing evaluation models.
Update SDK/CLI pins together only when justified by compatibility tests. Use existing
authorized host access for probes; do not create paid services or API keys to bypass
missing access. Record actual usage and limits separately from availability.

Freeze each evaluation lane in 06 before outcomes. Compare Luna alone, Luna with
OpenSocrates, and Sol alone on identical bounded tasks; compare Sol and Astra with
and without assistance at the same model/effort; test general/coding fresh-session
memory against disabled-memory and maintained-note controls; and test natural
English/Korean collaboration. Keep coding ablation and paired source replay distinct.
No stronger-model assistance may be hidden inside a Luna-only treatment. Include
all attempts, repairs, retrieval, tool work, and failures in cost/quality reporting.

Run focused checks during implementation, then required source/native checks for
the declared scope. Verify actual frozen SQLite and packaged guide/schema behavior.
Do not claim model-quality improvement from document, package, or policy tests.
If a model/platform is unavailable, record missing evidence and continue independent
work. Do not repeatedly retry unchanged blockers or promote unvalidated profiles.

Use one integrator for contracts, profile data, migrations, locks, and generated
outputs. Independent reviewers may run in parallel; parallel writers need isolated
worktrees and explicit ownership. Never revert another worker's unrelated edits.

Maintain exact-commit progress and evidence. You may create/update an implementation
issue and Draft PR with current scope, commands/results, limitations, and next steps.
Attach created PRs to the task. Do not merge, tag, publish, deploy, or change the active
plugin installation. Keep a reviewable handoff that works without this conversation.

Continue through authorized implementation and verification. Resolve routine choices
with the smallest design satisfying the contracts. Ask only for a material missing
scope/permission decision not settled here. Record meaningful deviations in 09 and
update affected contracts/tests together. Report verified completion, remaining
work, exact commit, checks, live/model evidence limits, and next action. Do not call
v1.5.0 released or claim universal quality improvement.

---

No private memory store, authentication file, local database, or prior transcript
is needed to understand this prompt. Make the repository and specification available
on the execution machine; preserve baseline identity and authorization boundaries.
