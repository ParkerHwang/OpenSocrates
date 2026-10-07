# v1.5.0 product direction and host support

Effective 2026-10-07. The user has accepted this product direction and host
scope. Implementation and host qualification for this revision are pending.
The latest earlier candidate is `f04d57fa84a82fbb0e3feb6894ec1210f135b3a8`.

OpenSocrates helps people who are not expert AI users obtain results they can
understand, judge, and use. v1.5.0 focuses on the original reasoning assistance,
Claude support including Windows, and Google Antigravity support. Dedicated
coding support is excluded from this version's new product scope.

This revision supersedes the earlier scope where it conflicts on product goals,
host coverage, or dedicated coding features. The earlier candidate's documents 01 through 15 and frozen evaluations remain
on its historical branch; this preparation branch does not import that candidate.
Affected requirements, runtime entry points, packaging, installer and host policy
must be reconciled before implementation; this scope change does not itself
restore a removed host or remove existing candidate code.

## Core user outcome

A representative task combines extensive source material, several stakeholders'
contexts, synthesis, and messages addressed to those stakeholders. The result
should connect facts, positions, unresolved issues, and requested actions so that
its intended reader can follow the situation and act.

Improve substantive interpretation and organization as well as expression:

- Distinguish facts, claims, decisions, assumptions, and unresolved agreement.
- Understand different stakeholders' knowledge, interests, and responsibilities
  without inventing motives.
- Connect conclusions to enough background and evidence for the intended reader.
- Select and order information around the reader's purpose and next action.
- Preserve material context and uncertainty while avoiding unnecessary procedure,
  verbosity, and repeated requests for settled permissions.

The user reported a substantial improvement in one real task after reinstalling
OpenSocrates and repeating the work. The paired artifacts have not been inspected
in this revision. This experience guides the product focus; it does not establish
a general causal effect, a particular method's contribution, or market demand.

## Host scope

| Surface | Required direction | Current evidence boundary |
| --- | --- | --- |
| Codex | Preserve the existing automatic entry and original reasoning assistance | Released 1.4.0 remains the current installed product; revised behavior needs its own checks |
| Claude Code on macOS and Windows | Restore support with automatic lifecycle entry, without requiring an OpenSocrates command on each request | Earlier adapters exist in tagged history; current candidate is Codex-only |
| Claude web and desktop | Provide the same core reasoning content through supported skills and persistent instructions; qualify ordinary Chat and Cowork separately | Skill availability and invocation do not prove automatic use on every relevant request |
| Antigravity on macOS and Windows | Restore support, using a concise persistent entry rule and complete selectively read skills, without repeated explicit invocation | Historical Windows explicit-skill delivery exists; current automatic entry and revised packages are unqualified |

The user's Gemini request means **Google Antigravity**. Ordinary Gemini web/mobile
and standalone Gemini CLI are not additional targets of this request. Installing
into an IDE does not add dedicated coding-specialist features to this release.

## Automatic participation

Users describe their task normally. The entry layer makes OpenSocrates available
and directs eligible judgment work to complete relevant procedures. Mechanical
work needs no added reasoning ceremony. Avoid loading all methods on every turn.

For Claude Code, evaluate lifecycle hooks and bounded context delivery. For
ordinary Claude Chat, evaluate a small account or project instruction with an
enabled skill; do not describe skill selection as a deterministic hook. Cowork's
plugin capability must be qualified separately on the actual account and client.

For Antigravity, qualify an `always_on` entry rule in the intended global or
workspace scope, with skills supplying full procedures when relevant. Check the
installed surface's rule syntax, discovery locations, token limits, and competing
instructions rather than assuming the historical plugin layout still applies.
Do not use a manual-only rule as the default automatic entry.

For every host, distinguish entry delivery, complete procedure reading, reported
application, and the user's final result. Installation alone is insufficient.

## Practical acceptance

Use the reported real task as the first reference case once its artifacts are
available, with a small set of further synthesis, decision, and communication
tasks. Compare whether the intended reader can understand the situation, follow
the reasoning, identify disagreements, and use the result with less correction or
repeated explanation. Retain regressions and cases where intervention adds work.
These observations do not require a universal model superiority claim.

For each claimed host and operating system, verify installation, normal requests
without an OpenSocrates command, relevant complete-guide access, a usable result,
continuation, disablement, update, and removal within the owned scope. Preserve
unrelated user instructions and settings. Record unavailable live cells without
promoting another platform's result to a pass.

Keep the existing privacy, user-authority, canonical evidence/stop, and explicit
unknown-state contracts. This v1.4-based implementation includes no new project
memory store; the old candidate's opt-in memory remains a deferred historical
scope with its original privacy requirements.
Broad orchestration, coding specialist procedures, and coding benchmark success
are not prerequisites for this product direction. Historical results stay intact.
Release publication and active installation changes remain separate actions.

## Host references

Official capabilities were checked on 2026-10-07; they establish host mechanisms,
not current OpenSocrates delivery or improved results.

- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code Windows setup](https://code.claude.com/docs/en/setup)
- [Claude skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude)
- [Claude persistent instructions](https://support.claude.com/en/articles/10185728-understanding-claude-s-personalization-features)
- [Claude plugin surfaces](https://support.claude.com/en/articles/13837440-use-plugins-in-claude)
- [Antigravity rules](https://www.antigravity.google/docs/rules/)
- [Antigravity skills](https://www.antigravity.google/docs/skills?tab=ide)
- [Historical Antigravity evidence](../antigravity-support.md)
