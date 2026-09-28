# Specialized production and independent acceptance

Status: implementation contract, frozen before product edits on 2026-09-28.
Baseline: `edab8f8d5c8434a705e706422ce5e8d6dc540e32`, Draft PR #95, issue #94.
This supersedes the earlier revision's no-subagent development constraint for
this explicitly authorized workflow only. The candidate remains unpublished.

## Scope and authority

The primary owns user intent, classification, accepted contracts, permissions,
integration and final evidence. Add an explicit optional `orchestrate` command.
Ordinary hooks, stateless decisions, 48 canonical procedures, model profiles,
existing memory enrollment and specialist locale/registration boundaries remain.
No automatic agent launch, enrollment, global setting or active-plugin change.
Source observations do not adopt policy. A reviewer pass does not imply user
acceptance of a new design policy. External effects retain normal authorization.

V1 is a bounded sequential workflow for text artifacts, including source code,
JSON calculations and Markdown documents. Binary office artifacts can be a later
adapter; do not claim this slice generates or visually checks them. Production
and material design artifacts both require independent review and execution
verification. The parent publishes only declared candidate artifacts; integration
into an existing project remains the primary's responsibility and must recheck
affected final bytes. No concurrent writers or arbitrary model-supplied commands.

## Classification and owned work

Classify each bounded unit on independent axes:

- Domain: `software`, `data`, `document`, `research`, `unknown`.
- Work kind: `judgment`, `mechanical`.
- Role: `design`, `production`, `review`, `execution_verification`.

A graph names each artifact's sole producer, paths, dependencies and completion
obligations. Shared schemas, locks, migrations and generated assets have one
designated owner. Reject cycles, missing dependencies, duplicate/overlapping path
ownership and unowned required artifacts. Unknown specialties return an explicit
classification gap to the primary. Mechanical work skips optional reasoning
guidance, never independent acceptance. A document needing a program dispatches
a software unit; an implementation needing a substantive contract change returns
to its design owner. No silent specialty/role switching.

## Assignment and state contracts

Use closed independently versioned orchestration schemas, not a new decision
union or SQLite layout. Bound request/assignment/candidate content; reject an
overflow without truncating required constraints or guides. A plan contains:
run/task identity, revision, attributed authorization reference, fixed model and
effort, locale, current constraints, owned units, dependency graph, source digests,
required obligations, declared executable checks and optional enrolled-memory
binding or explicit project handoff. The runtime validates mechanical consistency;
the primary remains responsible for semantic classification and authorization.

Each role receives a fresh assignment with objective, permissions, prohibitions,
completion conditions, owned paths, governing requirements and accepted design,
complete relevant role/domain guidance, exact current input/source identities,
dependencies, relevant memory projection, uncertainty and output/evidence schema.
Do not include conversation history, private reasoning, irrelevant explorations,
author self-assessment, prior ratings or same-attempt proposed lessons in first
review. Reusing a bounded maker repair context is allowed; changing role requires
a fresh context. The initial slice may use fresh contexts for every repair too.

State: validated -> ready -> producing -> candidate frozen -> independent review
-> execution verification -> qualified candidate -> integration pending/reconciled.
Failure states identify invalid input, unavailable capability, blocked dependency,
source conflict, repair required and cancellation. A process exit is not semantic
acceptance. Keep required failed/unknown obligations open. Continue independent
units when only one dependency is blocked.

Runtime-owned identities and SHA-256 manifests bind role inputs, candidate version,
review and verification. The author cannot review/verify its artifact. Reviewers
cannot patch candidates. Findings name artifact digest, governing requirement,
location, expected and observed result, independent reproduction/calculation,
impact and missing evidence. A confidence label alone is insufficient. The
designated maker repairs; changed bytes invalidate prior acceptance and require
review/verification again. Check affected dependency closure before completion.
Bound retries by an explicit repair count, never an arbitrary model time cutoff.

## Supported execution and limits

Use a real fresh `codex exec` process, never resume/fork: explicit model/effort,
`--ephemeral`, `--json`, read-only sandbox and structured final output. The tested
client candidate is bundled `codex-cli 0.158.0-alpha.2`. Check required features
before launch; an incompatible client reports unavailable and emits preparation
that can be handed to a capable host. No fabricated agent API or backend receipt.
The [official noninteractive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
describes these primitives; local capability and actual outcomes remain separate.

Capture the caller-authorized configured primary model and effort in the plan.
Every maker, reviewer, verifier and repair call must use that exact tuple; reject
role-specific substitutions. For this development/qualification run it is
`gpt-6-astra` / `max`. Unavailable access returns unavailable, never a different
model. Record configured values without claiming independent backend attestation.

Use a fresh temporary working directory with scoped source inputs and complete
guidance. Disable native memories, hooks, apps/plugins and child redelegation for
this adapter, without changing global settings. Verify actual command/config
behavior before live qualification. Fresh conversation and read-only shell policy
do not prove account/backend isolation or prohibit every unrelated file read;
record the tested scope and remaining limitation explicitly. Never claim prompt
instructions are an OS access-control boundary.

Children return bounded candidate files; the runtime alone validates ownership,
path safety, output size and source stability before candidate publication.
Independent execution uses explicit operator-approved check argument arrays, not
commands taken from model output, source comments or recalled memory. A distinct
verifier interprets the actual receipts. Missing executable verification blocks
the affected acceptance. Temporary test data must not mutate production artifacts.
Run checks in a scoped temporary candidate directory through the supported
`codex sandbox -P :read-only -C <candidate-directory> <argv...>` boundary, with a
controlled environment and network disabled. Rehash all candidate inputs after
each check. Unsupported enforcement or changed bytes fails closed. V1 requires
checks that need no filesystem writes; future scratch-write support needs its own
explicit confined scope. Do not execute approved check arrays unsandboxed.
Only public bounded findings, hashes, process states and exposed aggregate usage
are retained. Drop raw event bodies, reasoning events, prompts and tool-output
dumps. Missing usage is null; count every maker/reviewer/verifier/repair/failed call.

## Scoped continuity

Reuse the existing decision/observation/lesson/checkpoint records, provenance,
snapshots, CAS/idempotency, enrollment and deletion contracts. No new memory store.
Accepted intent, observed facts, proposed inferences, supported lessons and task
state have distinct projections. Preserve acceptance, support, freshness and review
state separately. Retrieve full applicable accepted constraints when current recall
summaries are insufficient; never drop them to meet a budget. Current source governs
observed behavior; source-dependent remembered claims require revalidation.

Freeze eligible record IDs/versions before production. First review excludes the
author's current-attempt self-assessment, checkpoints and unverified lessons, while
keeping accepted constraints and independently supported project knowledge. A
public lesson states conditions, mechanism, exceptions/counterexamples, provenance
and evidence references; it is not hidden thought transfer. Existing bounded public
summary/rationale and source-reference fields can carry this structure without a
database migration. No automatic promotion or fabricated native execution support.
Independent review state requires a receipt bound to the exact record/version;
missing such evidence is unknown, regardless of accepted lifecycle or freshness.

Recall must honor task/path scope and deletion. Memory absent, disabled, stale or
unavailable explicitly identifies lost continuity and uses current accepted contract
plus a bounded caller-owned project handoff. It does not initialize storage or erase
constraints. No raw prompts/transcripts/source copies/credentials/reasoning enter
product memory. Only existing authorized enrollment/capture operations may persist
bounded public records. Tests enroll disposable fixtures only.

## Ownership and acceptance before execution

Design author: `orchestration_design`; primary freezes and integrates its contract.
An independent design reviewer checks this contract before product edits. One
implementation maker owns runtime, schemas, launchers, packaged EN/KO guidance,
generated assets and focused checks. A separate read-only reviewer checks the exact
candidate version; a separate verifier runs independent acceptance. Every worker
must preserve others' changes and must not redelegate. The primary owns evidence
qualification, final integration and feature-branch handoff. User-owned `.codex/`
and the historical monitor state are excluded from all writes and commits.

Deterministic gates cover routing, complete contexts, missing/overlapping ownership,
fresh role identity, author/reviewer separation, snapshot mismatch, repair/recheck,
required obligations, source conflicts, disabled/stale memory, privacy, scoped
forgetting, old schema bytes, canonical methods, bilingual/package parity and errors.
Freeze a separate live manifest before calls: exact source/guide/package/client and
model identities, fixtures, expected outcomes, checks, repairs and failure handling.
Exercise a software design -> implementation workflow, a calculation -> document
workflow, and a continuation with scoped knowledge or explicit unavailable fallback.
Include a real mixed-domain boundary and a defective artifact that an independent
reviewer must detect. Preserve unfavorable outcomes. No broad model matrix.

Run focused checks, then all CONTRIBUTING source checks and appropriate native,
embedded-schema/guide and frozen-SQLite package checks. Keep correctness, privacy,
authorization, installation/platform evidence and quality-benefit claims separate.
Stop expansion after the functional gates pass. Keep PR #95 Draft. Merge, tagging,
publication, deployment, real-project enrollment and active installation replacement
require separate release authority.
