# OpenSocrates 2.0 development plan

**Status: development plan. It does not establish 2.0 implementation, effectiveness, or live host integration.** This packet incorporates the user's new direction and supersedes older 2.0 planning where scope or product direction differs. It does not change repository privacy, security, release, or generated-source rules.

OpenSocrates 2.0 is a program that develops reasoning guidance from a user's real work and connects communication, context, and delegation so conversation sessions across apps can work as one user-centered team. The existing 48 guides are used initially; suitable personal guides are selected, combined, or reassembled, with appropriate initial guidance as fallback. Common guide-generation instructions evolve with product releases; personal guides evolve from each user's experience.

First-version targets are **the ChatGPT desktop app's Chat, Work, and Codex experiences and the Claude desktop app on macOS and Windows**. Actual integration must be verified separately for each mode and OS. Direct model-provider API execution, new Grok Bot/Cursor integration, and cross-computer sync are outside the current first-version scope.

## Current plan: reading order

1. [Product vision and requirements](VISION_2.0.md): user experience and chosen scope.
2. [System architecture and data flow](SYSTEM_2.0.md): communication layer, real app work sessions, guide/context delivery and personal learning.
3. [Development roadmap and handoff](ROADMAP_2.0.md): work breakdown, dependencies, open decisions and first scenario.
4. [Validation and evaluation](VALIDATION_2.0.md): each host and OS, continuity, security, quality and real-use evaluation.
5. [한국어 문서](README.ko.md).
6. [Standalone Korean HTML plan](PLAN_2.0.ko.html). This is a snapshot of the four Korean planning documents. Refresh it separately after source changes and recheck its content and links.

The packet records proposed behavior and unresolved decisions. Internal model alignment, improved personalized quality, and automatic host-to-host delivery have not been established. The user's request session handles consultation and coordination; new sessions perform actual deliverable work. All inter-agent communications pass through the OpenSocrates layer.

## Earlier plans and preserved evidence

Older 2.0 documents remain historical evidence and must not override the current scope. In particular, their **mandatory Cursor** and **fixed 48-method selection** assumptions do not replace the user's present direction. See the status notices in the [earlier master plan](MASTER_PLAN.md), [backlog](IMPLEMENTATION_BACKLOG.md), [product/evaluation plan](PRODUCT_AND_EVALUATION.md), [architecture](ARCHITECTURE_AND_MIGRATION.md), [start guide](START_HERE.md), [host research](HOSTS_AND_BOTS.md), and [evaluation cases](EVALUATION_CASES.md).

The [v1.5.3 package and source inventory](RELEASE_BASELINE_1.5.3.md) remains a partial inventory of past packages and source, not evidence of actual host delivery, complete reads, application, or quality. Support and comparison claims need direct evidence for the relevant host and stage.
