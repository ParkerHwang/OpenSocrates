# Product identity and combined capabilities

Status: user clarification recorded on 2026-09-23. This governs product framing
and interpretation of the implementation workstreams. It does not claim measured
improvement or add an unimplemented host integration.

## Founding premise: supplied text shapes model behavior

The user states the product's starting point as: the text injected into an LLM can
strongly determine the performance observed in a task. The implementation-facing
interpretation is that the same model can produce materially different judgments
and work depending on the guidance, evidence, constraints, examples, and context
it receives. This is the product thesis, not a measured claim that OpenSocrates
already improves every model or that model capability and tools are irrelevant.

OpenSocrates therefore owns the quality, selection, preparation, timing, and delivery
of useful text within the host's allowed instruction/context surfaces. It should
help the chosen model use its capabilities well. A catalogue, memory database,
or coding workflow is valuable insofar as it improves that supplied context and
the resulting work. Text volume, method count, and a successful delivery receipt
are not outcome measures.

The original authored methods supply reasoning guidance. Project memory supplies
relevant prior public decisions, constraints, uncertainty, and continuity. Coding
support supplies current domain evidence about implementations and dependencies.
Model adaptation tunes how this material is discovered and used without weakening
its evidence and permission contracts.

Keep instruction and evidence roles distinct: trusted authored procedures can
guide behavior, while source files and recalled content remain attributed data.
The founding text-injection premise is not permission to elevate source-embedded
instructions, capture private reasoning, or override user/host authority.

## The product remains general judgment support

OpenSocrates helps an AI identify the judgment it needs to make, examine assumptions,
compare alternatives, evaluate evidence, and revise its conclusion when relevant
facts change. The 48 authored methods are the existing foundation for that work.
They are applicable beyond programming.

The user clarified that coding functionality is an addition that can make the
original OpenSocrates capabilities more powerful in combination. The recent
specification openings and pitches overemphasized coding memory and did not
adequately communicate that relationship. This is a correction of that framing,
not a pivot away from the existing product.

## How the capabilities work together

| Capability | Contribution |
| --- | --- |
| General reasoning core | Examine the present question, assumptions, alternatives, evidence, uncertainty, and decision conditions |
| Project memory | Recover permitted public decisions, supporting references, unresolved context, and operational continuity without treating past conclusions as automatically true |
| Coding-domain support | Connect reasoning to existing implementations, reuse alternatives, dependency effects, and appropriate verification |
| Host/model adaptation | Deliver the right guidance at the right time, preserve task completion, and verify behavior on supported Codex/model combinations |

For a coding decision, memory can recall why a shared component exists; the core
can compare reusing, extending, or replacing it; coding exploration can reveal
actual consumers and constraints; and verification can test the resulting change.
The public outcome then updates the relevant project record. No single layer is
evidence that the model understood or correctly applied the others.

For a non-coding decision, the same core may compare product directions or examine
whether new evidence undermines an earlier assumption. Available public context
can help preserve the original goal and the reason for the earlier choice.
There is no need to force code search or a programming guide into that task.
Memory remains optional, and its detailed source capabilities must be stated honestly.

The design opportunity is continuity plus reconsideration: retain useful context
and still ask whether it supports today's judgment. Neither storage alone nor
repeated method instructions establish a better answer.

## Host scope and task scope are different

Codex is the supported delivery environment in v1.4 and the current v1.5 plan.
That is distinct from the domains in which reasoning methods can help. A supported
Codex environment can be used for non-coding judgment work; do not equate its name
with a developer-only audience.

Embedding OpenSocrates in ordinary ChatGPT chat is still a separate integration
question. This boundary does not justify pitching the product's reasoning value
as relevant only to coding or to people who can read code.

## Pitch correction

Lead with the general purpose: improve the guidance and context an AI receives so
it can make better-grounded judgments and carry useful context into continuing work.
Then explain what v1.5 adds and show coding as a concrete, consequential application
of the combined capabilities. Avoid presenting the product as only a memory feature
or only a software-development assistant.

For non-developers, explain the reasoning benefit through decisions, alternatives,
assumptions, and changed evidence. An old project choice resurfacing is one example;
it is not the complete definition of OpenSocrates.

The earlier deck and audience rehearsals leaned heavily on the coding-memory
story. Preserve their records, but treat their audience-fit conclusions as feedback
on that narrower pitch. They do not establish that non-developers lack a use for
the original general reasoning function. Future full-product pitches should apply
this corrected framing before deriving audience conclusions.

## Implementation consequence

The user is the primary source for the product's intended identity; that intent
is established by the clarification. Better task outcomes from the proposed
combination remain an unverified performance hypothesis. Earlier role-play
reactions to a narrower brief do not establish or refute that hypothesis.

The strongest practical counterargument is that a capable model may already have
sufficient guidance, while extra instructions or recalled context can distract,
conflict, or become stale. The response is selective delivery and matched outcome
evaluation, not maximum injection. Revise or remove a delivery rule when the same
model, tools, and task conditions show that its added context worsens correctness,
judgment quality, or completion without a justified compensating benefit.

Keep shared records and controller logic free of unnecessary coding-only meaning.
Keep code-specific retrieval/analysis in domain adapters and guides. Preserve
non-coding behavior while improving GPT-6 discovery and completion, and test the
combined use of core reasoning, memory, and code evidence through G01–G03.

This clarification does not require every possible non-coding source adapter in
v1.5 or a universal memory product. The coding vertical slice remains a useful
first implementation target, while the general reasoning foundation remains the
product being extended.
