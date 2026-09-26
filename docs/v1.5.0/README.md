# OpenSocrates v1.5.0 development specification

Status: practical qualification and v1.5.0 release-candidate preparation.
The [2026-09-26 completion standard](PRACTICAL_COMPLETION.md) supersedes earlier
statistical release gates; historical evidence is preserved.
Working language: English. Reviewed baseline: `v1.4.0`, commit
`5a2ff3c312e92aa8a44d0905465674d9a4e4f645`, also the remote `main` head
when checked on 2026-09-23.

OpenSocrates helps developers and non-developers get better work from their chosen
LLM through task-aware reasoning guidance, relevant evidence, and useful memory.
v1.5.0 has four shared outcomes: improve inexpensive-model task quality, reduce
unnecessary work by capable models without reducing quality, preserve continuity
across sessions, and make collaboration attentive and natural. Coding reuse,
dependency understanding, and maintainability extend the same general foundation.

The product adapts optional assistance to the task and evaluated model profile.
It preserves the existing 48 canonical methods and their evidence/stop contracts.
Memory is built in, local, and explicitly enabled per project. Both Git code
projects and bounded non-Git local text projects are in scope. Codex is the current
host; ordinary ChatGPT integration is a separate capability.

All improvements are evaluation targets. Luna/Sol gap reduction is task-bounded;
strong-model efficiency requires preserved outcome quality. No prior conversation,
product-development history, or audience rehearsal is required to implement this
package. Start with the final product contract in 10 and behavior policy in 11.

## Read this package

| Document | Purpose |
| --- | --- |
| [01 — Scope and requirements](01-scope-and-requirements.md) | Outcomes, boundaries, normative requirements, and what is not included |
| [02 — Architecture and operation](02-architecture-and-operation.md) | Components, storage authority, identity, freshness, retrieval, and recovery |
| [03 — Data and interface contracts](03-data-and-interface-contracts.md) | Records, states, operations, limits, errors, and illustrative JSON |
| [04 — Coding and GPT-6 integration](04-coding-and-gpt6-integration.md) | Three coding workflows, Codex integration, model compatibility, and delivery evidence |
| [05 — Privacy, lifecycle, and migration](05-privacy-lifecycle-and-migration.md) | Explicit retention change, opt-in, data boundaries, deletion, and platform behavior |
| [06 — Verification and evaluation](06-verification-and-evaluation.md) | Acceptance cases, controlled model studies, and release evidence |
| [07 — Implementation plan](07-implementation-plan.md) | Ordered work packages, ownership boundaries, dependencies, and executable exit criteria |
| [08 — Implementation kickoff](08-implementation-kickoff.md) | Complete prompt to start implementation in a fresh Codex task |
| [09 — Decisions and source map](09-decisions-and-source-map.md) | Architectural decisions, alternatives, source evidence, and reopening conditions |
| [10 — Product definition](10-product-identity-and-combined-capabilities.md) | Target users, outcomes, representative experiences, and success conditions |
| [11 — Adaptive assistance and collaboration](11-adaptive-assistance-and-collaboration.md) | Task/model policy, assistance levels, profiles, and observable interaction behavior |
| [Validation record](VALIDATION.md) | Checks actually performed on this document package |
| [Practical completion standard](PRACTICAL_COMPLETION.md) | Current usability gates, bounded comparison, RC authority and stop rule |
| [Implementation status](IMPLEMENTATION_STATUS.md) | Candidate source slices, evidence boundary, and remaining gates |
| [Evaluation status](../../evals/v1.5/STATUS.md) | Frozen pilot receipts, exact treatment versions, and missing outcome evidence |
| [Platform acceptance handoff](PLATFORM_ACCEPTANCE_HANDOFF.md) | Disposable host procedure and separate destructive-test permission boundary |

The package also includes [synthetic contract examples](examples/README.md) and a
[documentation validator](validate_documents.py). Run the validator from the
repository root with `python3 docs/v1.5.0/validate_documents.py`.

Read this index, 10, 11, and 01 first. An implementation agent must then read 02, 03, and
05 before adding storage; 04 before changing host behavior; and 06–08 before
starting the execution plan. Read source files only for the current work package.

## Authority and evidence

`MUST`, `SHOULD`, and `MAY` define requirements of this proposed implementation.
They do not describe behavior already present in v1.4.0. Implementation tasks
must preserve the user's goals, permissions, and acceptance conditions.

The development specification was completed before implementation. The
implementation branch adds candidate source behavior and disposable fixtures.
It does not enroll a real workspace, modify the active installation, merge,
publish, or release v1.5.0.

The kickoff prompt explicitly authorizes implementation and the narrow policy
revision specified in 05. Until that implementation changes the active repository
policy, these documents are a proposal, not a silent exception to
[AGENTS.md](../../AGENTS.md) or [SECURITY.md](../../SECURITY.md).

When statements disagree, resolve the conflict before affected implementation.
Requirements and privacy bounds take priority over illustrative examples.
Update all affected documents together and record a decision in 09; do not choose
the most permissive wording. Examples are synthetic and are not implementation,
runtime evidence, benchmark results, or existing public API contracts.

## Definition of done for this package

- Adaptive assistance, general/coding memory, and collaboration have observable inputs, states,
  outputs, failures, and tests.
- Each implementation work package has dependencies and an exit criterion.
- The kickoff prompt is usable without the previous conversation.
- Existing behavior, proposed behavior, and unverified quality claims are distinct.
- Document links, examples, source references, and cross-document contracts are checked.

Product completion and release completion are separately defined in 06 and 07.
English is the requested working language; no measured performance advantage from
English is claimed.
