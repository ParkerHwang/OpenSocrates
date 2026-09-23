# Product definition and intended behavior

OpenSocrates helps people get better work from their chosen LLM by supplying
appropriate reasoning guidance, relevant evidence, and useful remembered context.
It serves developers and non-developers. Its foundation is that the text a model
receives can materially influence what it does with its existing capabilities.

v1.5.0 combines adaptive assistance, project memory, natural collaboration, and
coding-domain support. These are target behaviors until implementation and
evaluation establish their actual support. The supported delivery host is Codex.

## Product outcomes

| Outcome | Desired behavior | Evidence required |
| --- | --- | --- |
| More capable inexpensive models | Supply missing structure, relevant facts, and focused verification so a model such as Luna completes more tasks successfully | Improvement over the same unassisted model and task-bounded gap measurement against Sol |
| More efficient capable models | Preserve quality while avoiding redundant exploration, clarification, and repeated checking | Same-model quality-preserving reductions in total cost, latency, or unnecessary actions |
| Useful memory | Resume goals and work accurately, retrieve applicable decisions, and reconsider outdated assumptions | Fresh-session continuation, source-change, correction, and forgetting fixtures |
| Natural collaboration | Understand intent, use proportionate initiative, adapt to corrections, and explain what matters | Observable English/Korean interaction and outcome assessment |
| Better software work | Reuse appropriately, understand dependencies, and produce maintainable changes | Source-backed behavior tests, review, and a subsequent change |

Closing a Luna/Sol quality gap on a declared task suite is a target, not a promise
of universal model equivalence. A stronger model's shorter answer is not evidence
of less internal reasoning. Judge completed work, total resources, and user effort.

## Operating principle

Identify the intended outcome and constraints. Supply assistance that can change
the next consequential action. Recover context when needed, check current evidence,
act within authorization, verify proportionately, and finish once completion
conditions are satisfied. Reconsider when task, evidence, or constraints change.

The existing 48 canonical methods remain the reasoning foundation. Memory supplies
continuity; domain guides connect judgments to concrete evidence; model/task
profiles adjust surrounding assistance. Mandatory procedure, evidence, permission,
and stop contracts remain intact at every assistance level.

## Representative experiences

- A non-developer revises an event plan after venue capacity changes. The agent
  recalls the accessibility goal, checks the updated local brief, adjusts the
  plan, and asks only about a material unresolved choice.
- A researcher revisits a conclusion after new evidence arrives. The agent
  distinguishes the old rationale from current support and updates the deliverable.
- A developer adds behavior to an existing project. The agent finds reusable
  implementation, checks its consumers, compares suitable alternatives, implements
  the change, and verifies affected contracts.
- A user requests a routine edit. The agent completes it without a project scan,
  extended deliberation ritual, or irrelevant memory retrieval.

These are synthetic acceptance scenarios, not measured user outcomes.

## Natural collaboration

Human-like collaboration means practical attentiveness: preserve intent, remember
relevant context, notice changed circumstances, recover from corrections, and
know when to act, ask, explain, or stop. Style follows the user's language and
purpose. Friendly wording cannot compensate for forgotten constraints, repeated
permission requests, invented certainty, or incomplete work.

Do not simulate a human identity, personal experiences, or emotions to satisfy
this requirement. Do not infer permanent personal traits or cross-project
preferences from an isolated interaction. Scoped explicit preferences can be
remembered under the same project policy as other attributed decisions.

## Scope and success

Both Git code projects and bounded non-Git local text projects are in scope.
Ordinary ChatGPT integration, global personal memory, and universal document
connectors are separate work. Memory is optional; the core works without it.

The release requires adaptive, general, memory, collaboration, and coding behavior
coverage. Performance claims require the appropriate study in 06. If a profile
adds overhead without useful quality benefit, or saves resources by weakening
correctness, narrow or withdraw it rather than expanding its instructions.
