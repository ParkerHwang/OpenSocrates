# OpenSocrates v1.5.0 development specification

Status: implementation-ready design; product implementation has not started.
Working language: English. Reviewed baseline: `v1.4.0`, commit
`5a2ff3c312e92aa8a44d0905465674d9a4e4f645`, also the remote `main` head
when checked on 2026-09-23.

OpenSocrates starts from the premise that the text supplied to an LLM can materially
change the judgments and work it produces. Its product function is to select,
prepare, and deliver useful reasoning guidance and task context at the points where
they matter. The intended result is better-grounded judgment and more effective
work from the chosen model, not a claim that text is the only determinant of performance.

The existing reasoning methods help an AI examine assumptions, compare alternatives,
evaluate evidence, and reconsider conclusions. v1.5.0 extends that foundation with
persistent project context, deeper coding-domain evidence, and GPT-6 adaptation.
These capabilities work together to improve what the model receives. Coding is an
added application of the general product, not a replacement for its broader purpose.

The first implementation workstream exercises these additions on existing software
projects: recover relevant decisions, find suitable code, understand change impact,
and verify maintainable changes across sessions. The shared memory model must retain
the distinction between intent, evidence, inference, and unfinished work. Persistent
memory is built in and explicitly enabled per project; ordinary judgment work does
not require enabling it. Codex is the supported host, not a restriction of judgment
support to programming tasks.

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
| [10 — Product identity and combined capabilities](10-product-identity-and-combined-capabilities.md) | General reasoning foundation, shared memory, and additive coding support |
| [Validation record](VALIDATION.md) | Checks actually performed on this document package |
| [Pitch rehearsal record](pitch-rehearsals/README.md) | Simulated audience feedback, proposed follow-ups, and evidence limits |

The package also includes [synthetic contract examples](examples/README.md) and a
[documentation validator](validate_documents.py). Run the validator from the
repository root with `python3 docs/v1.5.0/validate_documents.py`.

Read this index and 01 first. An implementation agent must then read 02, 03, and
05 before adding storage; 04 before changing host behavior; and 06–08 before
starting the execution plan. Read source files only for the current work package.

## Authority and evidence

`MUST`, `SHOULD`, and `MAY` define requirements of this proposed implementation.
They do not describe behavior already present in v1.4.0. Implementation tasks
must preserve the user's goals, permissions, and acceptance conditions.

The user requested this development package and the built-in memory direction.
This task produces documents and a kickoff prompt. It does not start another
Codex task, enable memory for a real workspace, modify the active installation,
publish data, merge code, or release v1.5.0.

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

- The memory and coding behavior is specified through observable inputs, states,
  outputs, failures, and tests.
- Each implementation work package has dependencies and an exit criterion.
- The kickoff prompt is usable without the previous conversation.
- Existing behavior, proposed behavior, and unverified quality claims are distinct.
- Document links, examples, source references, and cross-document contracts are checked.

Product completion and release completion are separately defined in 06 and 07.
English is the requested working language; no measured performance advantage from
English is claimed.
