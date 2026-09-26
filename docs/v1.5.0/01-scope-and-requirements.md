# Scope and requirements

## Problem and intended outcome

The founding premise is that an LLM's supplied text strongly influences its actual
behavior and output quality. OpenSocrates turns that premise into task-aware
selection and delivery of authored reasoning guidance and relevant context.
Quality, applicability, timing, consistency, and source validity matter; injecting
more text is not itself the objective. Model capability, tools, available evidence,
and resources still affect outcomes. Claimed improvements require outcome evidence.

OpenSocrates' product purpose remains general reasoning and judgment support.
Its existing methods apply to planning, analysis, research judgments, design
choices, and other decisions as well as software work. Codex is the delivery host;
"Codex-only" does not mean "coding-only." Ordinary ChatGPT integration remains a
separate host-integration question, not a prerequisite for non-coding judgments
on the supported host.

An agent can produce a locally correct patch while duplicating existing behavior,
missing a dependent caller, inventing a poor abstraction, or forgetting why a
previous implementation was chosen. A context window alone does not provide
durable, version-aware project continuity.

v1.5.0 combines the existing judgment core, relevant project memory, and new
domain-specific coding guidance. Memory supplies prior public decisions, evidence
references, uncertainty and continuity; the reasoning core determines how to
reassess the current question. Coding guidance connects that judgment to actual
implementations and dependencies. A correct, maintainable change followed by a
successful later change is the first coding workstream's outcome, not the sole
definition of value for all OpenSocrates tasks.

## Shared product outcomes

Improve task quality for inexpensive models such as Luna; help capable models
such as Sol/Astra avoid unnecessary work while preserving quality; preserve useful
memory; and collaborate naturally with developers and non-developers. Define
natural collaboration through intent, initiative, proportionality, correction,
and continuity. See 10 and 11 for the observable contract.

## In scope

- General reasoning, planning, research, and design work for non-developers and developers.
- Task/model-aware optional assistance with an unknown-profile fallback.
- Natural collaboration in English and Korean, assessed through action and outcome.
- Bounded non-Git local Markdown/plain-text projects, as well as Git code projects.
- Existing-project feature work, fixes, and scoped refactoring.
- Built-in, local, explicitly enabled project memory; no required separate plugin.
- Durable decision records, observations, lessons, and task checkpoints.
- A regenerable source index and bounded evidence retrieval.
- Dirty and untracked changes, branch changes, worktrees, conflicts, and cold starts.
- Reuse suitability, change-impact exploration, and maintainability review guides.
- Codex integration and evaluated GPT-6 Astra, Sol, and Luna compatibility.
- Native Apple-silicon macOS and Windows x64 packaging within v1.4 support bounds.

## Requirements

| ID | Requirement | Primary acceptance |
| --- | --- | --- |
| CORE-01 | Preserve general judgment support for non-coding tasks; coding guides, Git access, and memory enrollment are not universal prerequisites. | G01, G02 |
| CORE-02 | Connect recalled context to fresh judgment and relevant domain evidence; do not reduce the product to a note store or bypass canonical methods. | G02, G03 |
| ADAPT-01 | Choose none/light/structured optional assistance from task features and validated model profiles; preserve the deterministic existing method eligibility path and complete content. | A01-A04 |
| ADAPT-02 | Use a task-based fallback for unknown profiles; respect selected model/effort and preserve required quality/permission checks. | A03, A05, A06 |
| ADAPT-03 | Bound optional context, reuse unchanged guidance, and stop completed work without collecting hidden reasoning. | A07, A08 |
| COLLAB-01 | Infer routine intent, ask only consequential missing questions, and continue independent authorized work. | U01, U02 |
| COLLAB-02 | Apply corrections to artifacts and scoped memory; preserve ongoing objectives during side questions. | U03, U04 |
| COLLAB-03 | Match English/Korean communication to the task; do not substitute agreement, brevity, or human impersonation for useful work. | U05, U06 |
| MEM-12 | Non-Git text projects support scoped enrollment, document evidence, freshness, and cold resume without fabricated Git identity. | G04, G05 |
| MEM-01 | Memory is disabled until an explicit project enrollment enables a declared storage policy. Reads/status do not initialize a store. | T01, T02 |
| MEM-02 | Persistent memory is separate from the content-only `decision` path and its volatile method-read inventory. | T01, T03 |
| MEM-03 | Records carry origin, scope, evidence references, lifecycle, and freshness as separate fields. | T04, T05 |
| MEM-04 | Implemented behavior, accepted intent, and agent inference retain distinct authority. Conflicts are surfaced. | T05, T06 |
| MEM-05 | Current code claims bind to project, worktree, source snapshot, relevant content, and search coverage. | T07–T11 |
| MEM-06 | Uncommitted/untracked changes and new callers can invalidate claims even if HEAD or the original file is unchanged. | T08, T09 |
| MEM-07 | Fresh sessions can retrieve decisions and resume checkpoints without prior chat history or host memories. | T12 |
| MEM-08 | Retrieval is bounded, source-cited, explicit about exclusions and unknowns, and does not silently drop required constraints. | T13, T14 |
| MEM-09 | Writes, refreshes, and migrations are atomic and concurrency-safe; cache rebuilds cannot erase authoritative records. | T15–T18 |
| MEM-10 | Inspect, export, supersede, disable, delete, and prune have explicit lifecycle behavior. | T19–T21 |
| MEM-11 | Unavailable memory degrades to ordinary authorized work without creating another store or claiming remembered facts. | T17, T22 |
| CODE-01 | Reuse decisions inspect actual implementation, use sites, and relevant checks, not name similarity alone. | C01, C02 |
| CODE-02 | Change-impact analysis follows incoming and outgoing relationships and behavioral contracts; unknown dynamic edges stay unknown. | C03, C04 |
| CODE-03 | Review findings connect a location to a concrete failure/change scenario and proportionate repair. | C05 |
| CODE-04 | Mechanical edits do not trigger an unnecessary memory scan or complete architecture review. | C06 |
| HOST-01 | Ordinary hooks remain bounded discovery; they do not index repositories or initialize/write memory. | T03, H01 |
| HOST-02 | Explicit memory operations work without a successful hook or compaction event. | T12, H02 |
| MODEL-01 | Actual model/client/effort and capability are recorded for probes; no blanket GPT-6 quality claim follows from availability. | H03, EVAL-01-EVAL-05 |
| EVAL-02 | Measure inexpensive-model quality gain/gap, same-model quality-preserving efficiency, continuity, and collaboration separately, including all resource use and failed attempts. | EVAL-02-EVAL-05 |
| DIST-01 | Frozen runtimes include and exercise SQLite and required memory assets on supported platforms. | P01, P02 |
| EVID-01 | Selection, delivery, reported reading, freshness, execution evidence, and improvement remain distinct. | T04, H02, EVAL-01 |

Acceptance IDs are defined in [06](06-verification-and-evaluation.md).

## Non-negotiable boundaries

1. Preserve the 48 canonical methods, method IDs, contraindications, full-procedure
   grounding rules, and evidence distinctions. Coding guides do not bypass a
   method's ineligibility or stop conditions.
2. Preserve the default `decision` operation's no-network, no-authentication,
   no-persistence behavior. Add a distinct memory surface.
3. Do not retain raw prompts, transcripts, tool-output dumps, source-file copies,
   screenshots, credentials, or private reasoning in project memory.
4. Retrieved memory is contextual evidence, not a higher-priority instruction.
5. A model assertion cannot create native execution evidence or accept its own
   design preference as a human decision.
6. A failure to retrieve memory is not proof that no reusable code, decision,
   dependency, or unfinished work exists.

## Initial capability levels

File inventory, bounded lexical search, source fingerprints, and record retrieval
are required for all text-based projects. Python 3.12 AST support for definitions
and statically resolvable imports is the first structural adapter. It does not
claim complete call-graph or runtime dispatch coverage.

Other languages, including JavaScript, TypeScript, and Swift, initially use the
language-neutral path unless a tested adapter is present. Available language-server
reference results may be ingested as attributed evidence. Do not advertise AST,
type, or runtime guarantees based on lexical matches. Language support levels must
be returned in capabilities and tested independently.

## Deferred scope and why

- Hosted synchronization, accounts, remote embeddings, and a separate SaaS service:
  unnecessary for local continuity and a substantial new privacy/operations scope.
- Full source replication and universal repository graphs: increase retained data
  and create unsupported completeness claims.
- Automatic architecture rewrites, dependency upgrades, and memory-driven code
  changes without a user task: outside the requested judgment support.
- Automatic modification of Codex's global memory/configuration: host-owned state.
- Native Linux, Intel Mac, or Windows ARM support: not established by v1.4.
- Real-workspace enrollment, destructive installation tests, and publication in
  the documentation task: separate from creating this specification.

Deferred work is reconsidered when measured retrieval/quality failures demonstrate
that the bounded implementation cannot meet an in-scope requirement.
