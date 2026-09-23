# Coding workflows and GPT-6 integration

## Entry and delivery

Keep the existing controller as a small router. Add concise pointers to separate
engineering guides under the proposed `plugin-src/shared/coding/` directory and
include them in generated Codex references. A guide has its own revision/hash;
it is not secretly a 49th canonical method. Preserve method count/identity and
the existing method selection algorithm unless a separately reviewed change is
needed. An empty/ineligible method selection remains valid.

All new development documents, work prompts, code comments, and implementation
reports are English. Existing EN/KO canonical procedures and interfaces remain
compatible. Author the new guidance in English; any localized release surface
required by the existing product contract must be deliberately aligned and tested.
Do not claim Korean guide coverage from English-only tests or silently remove
existing Korean content. This specification itself is English-only.

Ordinary SessionStart/submission/compaction hooks may point to the memory/coding
capability, but must not scan a repository, open a database, store user content,
or call a model. Preserve current bounded hook tests. An active agent can invoke
memory operations explicitly after reading the trusted guide. Do not assume that
a hook sees every decision or runs before every interruption.

## Reuse suitability

Trigger when introducing a behavior, shared function/component, dependency, or
abstraction, or when overlapping implementations are discovered.

1. Describe the required behavior, inputs/outputs, failure handling, and ownership.
2. Recall applicable decisions and candidate locations; revalidate against current
   source. Search existing modules, standard facilities, and installed dependencies.
3. Inspect candidate bodies, real use sites, and relevant tests/contracts. Version
   and configuration compatibility matter; similar names alone are insufficient.
4. Choose direct reuse, extension, adaptation, or a separate implementation.
5. Verify the changed behavior and affected existing uses; checkpoint the result.

Public evidence includes searched scope, candidates, the selected option, rejected
candidate reasons, and tests/unknowns. Do not maximize reuse rate: separating code
with different change reasons can be the correct outcome. Do not add a library
just because its name matches the desired feature.

Stop exploring when a suitable choice is supported and remaining information is
unlikely to change it. If no candidate is found, report the scope searched; do
not claim universal absence. Missing tools produce a narrower declared coverage,
not invented structural evidence.

## Change impact

Trigger before changing a shared behavior, public type, state owner, configuration
contract, registration rule, or interface consumed by another module.

Retrieve accepted intent and incoming/outgoing relationships. Inspect data shapes,
error propagation, retries, cancellation, side effects, resource lifecycle, and
ordering where relevant. Trace concrete source references to affected tests and
co-edits. Classify lexical candidates, structurally established relationships,
inferred contracts, and unresolved dynamic behavior separately.

An observed reference is not proof that a runtime path executes. A lack of lexical
matches is not proof of no consumers. Refresh negative claims when inventory,
configuration, generated interfaces, or untracked callers change. Define the
smallest sufficient verification for the actual change and widen it only for
new failures or material uncertainty.

## Maintainability review

Trigger before completing a non-mechanical code change, with review depth based
on the changed behavior and affected contracts.

Review the final diff and relevant surrounding code for coherent responsibilities,
duplicated domain rules, unnecessary abstractions/options, brittle coupling,
failure behavior, testability, and fit with project conventions. Findings require
location, concrete consequence/change scenario, evidence, and proportionate repair.
Stylistic preferences without a project rule or consequence are not defects.

Use linters, type checks, complexity/duplication signals, and behavioral tests as
different evidence. No single line count, complexity score, test pass, or model
rating certifies maintainability. Preserve working code outside the requested
scope; propose larger unrelated refactors separately.

Complete after required corrections/checks and a truthful report of remaining
limitations. Do not repeatedly rerun unchanged tests, create mirror tests for
trivial edits, or keep searching for unavailable proof of method application.

## End-to-end operating example

Synthetic task: add retries to a profile API call.

Recall finds a project decision that authentication refresh belongs to a shared
client and a source observation identifying that client. Freshness detects that
another worktree's earlier caller list is inapplicable. Current exploration finds
read and payment callers; the payment path makes unconditional retry unsafe.
The agent chooses a scoped policy, implements it, and runs relevant behavior tests.
It records a bounded public decision proposal and a checkpoint with actual
verification status. A new session restores that state without the old transcript.

The memory system supplies evidence and continuity. It does not autonomously
change code, approve the design, or promote the test report into native proof.

## GPT-6 compatibility

The default `decision` route makes zero selector-model calls. Most GPT-6 work here
concerns discovery, instruction clarity, retrieval behavior, and completion.
The retained SDK selector is a separate path pinned to SDK/CLI `0.144.4` at the
baseline, with medium effort and no explicit model name in its turn invocation.

Implementation must:

- Resolve model availability from the actual host surface. Target exact
  `gpt-6-astra`, `gpt-6-sol`, and `gpt-6-luna` IDs when available; never invent a
  `gpt-6` alias or a model ID combining effort with model name.
- Preserve user-selected models and validated task/effort roles. Do not force all
  memory retrieval or ordinary work through the flagship model.
- Keep source indexing/retrieval deterministic. Optional synthesis uses an
  explicitly selected, bounded host capability and is not a release prerequisite.
- Inspect SDK/client compatibility before changing pins. Upgrade matching SDK and
  CLI dependencies together only when necessary; update bootstrap/lock/package
  checks. Do not rewrite historical model evidence as if it used GPT-6.
- Make continue/stop boundaries clear. Preserve authorization and required
  constraints, while avoiding unnecessary approval pauses and repeated checks.
- Record exact model, effort, client, plugin/guide versions, memory policy, and
  capabilities for every live probe. Unsupported combinations stay unverified.

OpenAI's current guidance describes Astra sensitivity to skill instructions,
clarification pauses, and overbroad testing. These are tuning hypotheses for this
workload, not proof of an OpenSocrates defect or improvement. Sources are in 09.

## Host memories and compaction

Use native Codex memories/context management only as optional surrounding host
capabilities. Do not edit their global files/settings, import complete host
transcripts, or make project-memory correctness depend on their timing.

On compaction or handoff, re-establish required project context, source freshness,
and method content availability. A persisted receipt that another agent read a
guide cannot certify the current agent's read. Query correctness, pack delivery,
reported reading, application, and coding quality have separate evidence states.
