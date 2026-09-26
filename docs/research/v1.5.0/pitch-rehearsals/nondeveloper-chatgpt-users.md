# Non-developer ChatGPT audience rehearsal

Date: 2026-09-23.
Status: completed opening pitch, a clarification exchange, and final concept opinions.
Language: English. Product stage: proposed v1.5.0 behavior, not an implemented release.

Three fresh GPT-6 Sol/medium agent contexts played fictional audience members:
a nontechnical maker, a writing/research knowledge worker, and an everyday
learning/planning user. They did not read prior audience verdicts or one another's
initial reactions. These are simulated opinions, not interviews, actual DevDay
feedback, customer demand, or independent evidence of product performance.

## Scope made explicit in the pitch

The concrete release design is a Codex add-on with local project memory. Ordinary
ChatGPT integration is not in the current release scope. The pitch did not imply
that non-developers must be programmers to understand the idea, or that they can
already use v1.5 in their regular ChatGPT conversations.

ChatGPT already has Projects and memory-related features. The concept was not
presented as fixing an absolute inability of ChatGPT to remember. Its proposed
focus is relevant project decisions, changes that affect them, and continuity
that keeps source and uncertainty visible.

General writing, research, learning, or planning uses in ordinary ChatGPT were
allowed as future extension ideas, clearly separate from current v1.5 scope.
No integration or new product surface was committed during the rehearsal.

## Plain-language pitch delivered

OpenSocrates would help an AI assistant bring back important choices you made,
check them against the project as it exists now, and continue unfinished work
without making you explain everything again. The memory feature is designed but
not built; the initial concrete home is Codex project work.

Illustration: a person asks AI to build a booking site and chooses to collect
names and email addresses only. A later reminder request may affect that choice.
The intended helper should use the relevant previous decision, examine what
exists now, and help resolve a real conflict without quietly changing the user's
plan or making old preferences permanent. A short handoff preserves the goal,
remaining work, what was checked, and the next action.

The user should not have to understand code organization or maintain a second
diary. Project scope, inspection, correction, disabling, and deletion are visible
controls. A temporary thought must not become a global personal rule.

## Audience opinions

| Simulated audience | Concept value | Scope or design reservation | Recommended first experience |
| --- | --- | --- | --- |
| Nontechnical maker | Worthwhile for a site/tool developed across several sessions; preserves earlier choices while allowing a change of mind | A ChatGPT user could wrongly assume it works in normal chat; system-language obscures the useful interaction | The reminder request, with the prior choice surfaced only when relevant and correction available in ordinary language |
| Writing/research knowledge worker | Deliberate choices, tentative ideas, and short handoffs could help extended work | Current Codex-focused v1.5 does not directly address ordinary ChatGPT writing/planning; those uses are future scope | If extended later, a short source-linked account of decisions, tentative points, changes, and next action |
| Everyday learning/planning user | Useful for revisited creative/site-building projects when it explains the consequence of changing a choice | Does not currently address everyday ChatGPT use; memory wording may imply global personal memory or entirely local AI processing | Simple correction at the moment a choice appears, with brief handoffs and details on demand |

These statements are conditional opinions about a hypothetical experience. They
are not recorded willingness to pay, actual installation, or a claim that all
non-developers share the same needs.

## Question that mattered across the conversation

The audience focused on what happens when a new request differs from an old
choice. Does the assistant help the user change course, or require the user to
defend every revision and manage another record system?

The presenter proposed this interaction rule:

1. Compatible routine requests proceed using the existing project choice, with a
   brief assumption stated when useful. An email-only project can add email reminders.
2. A clear new instruction can change the earlier preference within its stated
   scope. If the user explicitly requests SMS and phone collection, do not ask the
   same permission again solely because the old preference was email-only.
3. A material unresolved conflict gets one concrete explanation and a scoped
   question. SMS reminders combined with "collect no additional contact data" is
   different from a clear decision to change the collection policy.
4. Continue independent work. An old memory does not automatically stop the task.
5. Let the user correct scope or change/forget the choice in ordinary language.
   Show the origin on demand; do not require long logs or technical confidence badges.

The proposed correction phrases were: "Only for the earlier task," "Change it
from now on," and "Forget this choice." These were introduced by the presenter
and then prioritized by a persona; they are not spontaneous findings from a
blinded usability study. They describe proposed interaction, not existing UI.

One closing response compressed the SMS example into a general request for a
question. The narrower clarified rule above is preserved: an explicit new choice
does not require redundant confirmation. Ordinary permission and safety boundaries
still apply independently of memory.

## Implications for the pitch and proposed design

- Lead with a recognizable moment in a project: an earlier choice matters to the
  current request, the consequence becomes clear, and the person can continue or
  change direction.
- Explain the concrete Codex home early. Do not sell the current release as a
  ChatGPT-wide personal memory feature.
- Keep memory management out of the ordinary conversational path. Inspection,
  correction, and deletion should remain accessible without becoming a second job.
- Keep the handoff short: goal, what remains, what was checked, and next action.
- Distinguish a non-developer making software with AI from a person using only
  ordinary ChatGPT for knowledge work. The former is closer to the current scope;
  the latter may inform a separate future product decision.
- Local record storage does not imply that ordinary model processing stays local.
  Avoid that misleading privacy inference in copy and presentations.

No participant was asked to withhold concept feedback until a demo existed. Later
validation remains necessary for empirical claims, but did not replace useful
pre-implementation opinions in this discussion.

## Sources and boundaries

Product scope: [requirements](../../../v1.5.0/01-scope-and-requirements.md),
[architecture](../../../v1.5.0/02-architecture-and-operation.md), and
[coding/host integration](../../../v1.5.0/04-coding-and-gpt6-integration.md).

Current platform context was checked against official OpenAI documentation:
[ChatGPT quickstart](https://learn.chatgpt.com/docs/quickstart) describes Projects
with chats, files, and instructions; [Memories](https://learn.chatgpt.com/docs/customization/memories)
distinguishes ChatGPT memory from local Codex memory and its controls. These pages
do not establish that OpenSocrates integrates with ordinary ChatGPT or improves it.

This record adds audience-specific concept feedback. It does not change the core
release scope, implement an ordinary-ChatGPT extension, or rewrite the deck.

## Corrective rebrief: coding is additive

The user subsequently clarified that coding strengthens the original OpenSocrates
function rather than replacing it. The presenter acknowledged that the initial
brief underrepresented the general reasoning core. The same three personas received
one corrective rebrief: existing methods apply to assumptions, alternatives,
evidence, objections, and revised conclusions in non-coding work too; memory and
coding support add to that foundation. Codex is the host, not a coding-only domain.

The maker then saw a broader judgment helper and suggested a workshop-planning
decision where a prior accessibility goal matters to pricing options. The knowledge
worker suggested revisiting whether a research brief should rely on a small survey,
using the earlier decision to treat it as exploratory as relevant context. The
personal-use persona suggested reconsidering a learning plan when time or budget
changes. These are hypothetical examples, not actual observed needs or advice to
make a specific financial decision.

Remaining concerns were appropriate intervention frequency, an accessible workflow
for non-coding projects on the supported host, and avoiding a pitch that makes the
user think they must learn 48 methods or merely manage another generic memory.
The personas explicitly acknowledged that their initial feedback applied to the
narrower coding-memory brief, not the complete product. Ordinary ChatGPT integration
remains separate; general non-coding reasoning value does not require that
integration to be part of the product's existing scope.

After this rebrief, the user further stated the product's founding text-injection
theme. That theme is now recorded in the [product identity document](../../../v1.5.0/10-product-identity-and-combined-capabilities.md).
It was not independently re-pitched to the panel, so this record does not invent a
new audience verdict on the fully restated thesis.

OpenSocrates grounding: critical-thinking@3
