# DevDay-style developer pitch rehearsal

Date: 2026-09-23.
Status: completed opening pitch and Q&A, followed by a corrected concept-stage
discussion after the user clarified the intended evaluation.
Language: English. Product state: v1.5.0 specification, not an implemented memory release.

This was a simulated audience, not contact with actual DevDay attendees, OpenAI
employees, or external developers. Three fresh agent contexts supplied different
lenses. All used the GPT-6 Sol family; this is neither a representative sample nor
independent empirical evidence of demand, safety, or product quality.

| Simulated lens | Model/effort | Focus |
| --- | --- | --- |
| Application developer | `gpt-6-sol`, medium | Daily Codex work, setup burden, repeat use, and useful changes |
| Platform/reliability engineer | `gpt-6-sol`, high | Freshness, worktree isolation, unavailable storage, latency, and trust |
| Open-source maintainer | `gpt-6-sol`, medium | Existing docs/search/tests, contributor burden, inspectability, and removal |

The opening pitch preserved the shipped v1.4 versus proposed v1.5 distinction.
It described local opt-in memory, stale-source checks, reuse/impact/review guides,
limited language-adapter coverage, and the absence of measured v1.5 results.
The retry scenario was illustrative. The reviewers did not receive the VC memo
or each other's initial reactions. They did hear a pitch already incorporating
the maintained-note comparison from the earlier rehearsal; this was not a blinded
audience-comparison experiment.

## Moderator correction and primary question

The user correctly pointed out that this is a pitch for a product to be developed.
The initial closing question asked whether attendees would try it immediately,
wait for a working demo, or pass. Although the pitch disclosed its unbuilt state,
that question biased the discussion toward trial readiness. A demand for execution
proof does not answer whether the proposed direction is worthwhile.

The presenter acknowledged this framing error and asked the same personas for
reasoned concept-stage opinions: value, intended situations, first implementation,
design changes, omissions, and unresolved ownership questions. They were told not
to assume measured benefits or demand, but also not to withhold design advice
merely because implementation had not happened. The following concept feedback is
the primary result. The earlier adoption-framed exchange remains below as history.

## Concept-stage feedback

| Lens | Opinion on the proposed direction | Most valuable first behavior | Simplification or concern |
| --- | --- | --- | --- |
| Application developer | Worth developing for continuity when the reason behind a constraint matters more than a generic conversation summary | Retrieve relevant accepted intent, compare it with current source, and briefly expose a conflict before a dependent change | Avoid a second diary or approval ritual; omit a separate generalized lessons category initially |
| Platform engineer | Worth developing if it stays narrow and keeps provenance and authority clear | An inspectable intent/observation ledger that can say supported, conflicting, or unknown in the current worktree | Omit broad lesson capture and broad dependency-analysis claims; do not turn old checkpoints into present certainty |
| Maintainer | Worth developing as a complement to repository guidance and tests, especially for one developer's continuity | Retrieve a few attributed decisions, recheck source, and provide a clear correction path | Team intent belongs in reviewed project guidance; local memory should not become private team policy |

These are hypothetical professional opinions from AI personas, not customer demand
or a validated product recommendation. They nevertheless provide actionable design
feedback at the requested pre-implementation stage.

## Authority and ownership clarification

All three raised who can establish or supersede accepted intent. The presenter
clarified the existing proposal: an agent inference stays proposed; an explicit
user decision or reviewed maintainer document supplies accepted intent. Capture
an already explicit decision with attribution without asking the same permission
again. Refreshing source observations must not silently erase a human decision.
Conflicts should be surfaced before an action that depends on resolving them.

For the final concept exchange, the presenter assumed an initial focus on one
developer's local continuity across Codex sessions. Team rules remain in AGENTS.md
and reviewed docs; shared-memory sync is outside the initial scope. This was a
discussion assumption, not a new user-approved commercial segment or team product.

With that clarified scope, all three supported a limited operational checkpoint:
goal, remaining work, verification state, and next action. The platform and
maintainer personas revised their earlier suggestion to omit checkpoints after
the presenter reconnected the design to the user's context-window/resumption goal.
The checkpoint should remain short-lived operational state, separate from durable
knowledge or authorization. Where the host already preserves a field reliably,
reference it instead of creating a competing source.

The maintainer retained a substantive caution: private local continuity may help
an individual prepare a change, but that alone does not establish improved shared
maintenance practice for a team. Lead with the narrower experience and evaluate
broader quality claims later. This dissent is not removed by the narrower agreement.

## Recommended first product experience

During an ordinary coding request, retrieve only the relevant prior intent, show
the source and the current disagreement or uncertainty, and make the next action
clear. Save minimal operational state when it helps a later session continue.
Expose memory to the user when it changes a decision, flags a conflict, or resumes
unfinished work. Avoid requiring the user to manage a parallel memory system after
every small task.

The proposed first release should prioritize decision/observation recall and
correction plus minimal handoff state. Generalized lesson capture, broad graph
coverage, and multi-user approval/synchronization can wait until a distinct need
justifies them. These are recorded suggestions, not silent edits to the core spec.

## Earlier adoption-framed reactions (secondary)

Under the presenter's initial trial-readiness question, all three personas selected
**wait for a working demo**. This was an answer to that question, not a rejection
of the product concept. It is superseded as the primary result by the concept-stage
discussion above. These are not three interested customers or recorded adoption.

| Lens | What they understood | Observable condition for a disposable-project trial |
| --- | --- | --- |
| Application developer | Relevant decisions and checkpoints can help a fresh session, if current source checks prevent misuse | Show a new caller invalidating an old observation, the exact retrieved record, a concise warning, the recheck, patch/test, and total developer effort against maintained notes |
| Platform engineer | Current source, accepted intent, and remembered claims need different authority | Show two worktrees, an untracked caller, and a locked store; disclose the deadline, measured elapsed time/status, next action, and resulting code/tests without claiming an inaccessible snapshot was validated |
| Maintainer | Optional memory could make disagreements between intent and current code visible | Demonstrate enroll, record, export, disable, delete, and ordinary Codex/project checks afterward; inspect repository diff and managed state, with readable exports |

## What the presenter answered

### Practical workflow

The intended workflow has one explicit project enrollment followed by ordinary
Codex requests. The agent should manage typed memory operations within policy;
users should not write JSON or maintain a second diary after every edit. The
warning must identify its source, the changed evidence, the proposed recheck,
and the action affected. No such interaction has been demonstrated yet.

The application developer asked to see this exact interaction within the first
ten minutes, including extra user actions and the resulting code. The presenter
agreed that the maintained-note control must receive the same relevant facts,
source state, tools, guidance, and budget.

### Unavailable storage and source freshness

When the store is locked or unavailable, the memory command must report that state
within a bounded operation. The agent may inspect its current authorized checkout
through ordinary tools. If the earlier snapshot is inaccessible, it cannot claim
that it compared the current source against that snapshot. The comparison remains
unknown. A known constraint already in context does not disappear when storage fails.

A modification depending on a missing authoritative decision may need to pause,
while independent work continues. Current sufficient evidence can support ordinary
authorized work. There must be no cross-worktree fallback, invented recalled fact,
or silently initialized replacement store. Tool output alone does not prove that
the coding agent follows these rules; an end-to-end run is necessary.

The platform engineer identified a precise gap: the specification's **two-second
database lock wait** is not a caller-visible end-to-end deadline. A proposed
acceptance addition is to freeze that complete budget before testing and measure
startup, waiting, cleanup, structured status, exit status, and subsequent action.
A watchdog timeout must be reported as a timeout rather than a graceful busy result.
Interrupted mutations need state reconciliation before retry. No measured bound
or new performance promise was established in the rehearsal.

### Easy removal

The proposed exit demonstration uses a disposable project and inspects both its
repository diff and owned runtime state. Disabling automatic memory use does not
block explicit management/deletion. Deleting the managed store must preserve
source and contributor instructions. User-owned exports remain unless separately
deleted, and they must be readable without the plugin.

This is primarily a request to demonstrate existing lifecycle requirements, not
a justification for a new cloud service, dashboard, or broader collection policy.

## Pitch changes requested in the earlier exchange

1. Lead with the stale-record/retry walkthrough and its observable outcome.
2. Keep the comparison with native Codex and well-maintained project notes.
3. Move the inventory of reasoning methods and memory categories after the workflow.
4. Make the moment of intent/source conflict visible, not merely an architecture claim.
5. Show failure and exit behavior alongside the successful path.

## Proposed developer demo sequence

This is a future demo brief, not an executed script or a claim that v1.5 commands
exist today.

1. State the small change and the existing shared client in a disposable repository.
2. Show the relevant recorded decision and source observation, with their evidence states.
3. Start a fresh session, add a new caller, and expose the stale observation.
4. Show the concise warning, source recheck, scoped patch, and relevant tests.
5. Repeat under the maintained-note control with comparable information and effort accounting.
6. Exercise the locked-store/worktree case under a predeclared end-to-end deadline.
7. Export, disable, delete, and show ordinary project work still functioning.

## Relationship to existing requirements

| Finding | Existing coverage | Remaining proposal |
| --- | --- | --- |
| Stale/untracked caller and worktree behavior | MEM-05/06, T07–T11, C03/C05 | Put the interaction early in the developer demo and observe user effort |
| Bounded unavailable-store behavior | MEM-11, T17/T22, declared lock wait | Add a caller-visible complete deadline and measurement contract |
| Removal and readable export | MEM-10, T19–T21 | Demonstrate the exit path and inspect residue/repository state |
| Value over maintained notes | Existing controls plus the investor rehearsal suggestion | Explicitly add the strong note baseline before a causal improvement claim |

These proposed follow-ups were recorded but not silently promoted into the core
specification. No product code, evaluation results, pricing, active installation,
or real-workspace enrollment changed in this rehearsal.

## Evidence and limits

Sources: the English [specification index](../README.md),
[data/interface contracts](../../../v1.5.0/03-data-and-interface-contracts.md),
[coding workflows](../../../v1.5.0/04-coding-and-gpt6-integration.md),
[privacy/lifecycle contract](../../../v1.5.0/05-privacy-lifecycle-and-migration.md), and
[verification plan](../../../v1.5.0/06-verification-and-evaluation.md), initially committed at
`430feaacbdb2cedb8661b8d1057e96d5a4d20abe`.

The corrected panel supports a reasoned, conditional concept recommendation:
build a narrow connection between prior intent and current source, with minimal
operational continuity. It does not establish developer demand, actual willingness
to install, safe operation, or a quality advantage. Those empirical conclusions
remain separate from the useful design opinions obtained before implementation.

OpenSocrates grounding: critical-thinking@3
