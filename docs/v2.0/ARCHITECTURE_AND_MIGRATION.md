# OpenSocrates 2.0 architecture and migration plan

Status: implementation design, not a claim of shipped behavior. Start from the
released 1.5.3 product and its documented contracts. The user has withdrawn the
separate 1.6 release work; its PRs, branches, and evidence are historical inputs
to inspect, not a release to complete or a source to merge without review. The
historical v1.5 memory candidate was also withdrawn; repository governance
explicitly prohibits merging, cherry-picking, or copying its code and guides.
Its observations inform new design and tests, not implementation provenance.

## Scope and fixed baseline

2.0 retains 48 authored methods in 10 languages, separates conversation and
artifact language, guides task initiation, intermediate judgments and
reader-oriented delivery, and adds working memory and history. It must support
Codex, Claude Code, Claude account content, Antigravity, and Cursor. A bot
profile for Dot, Grok Bot and Claude Duet is researched against real host
capabilities; its exact release cells remain to be qualified. Plain conversation
must stay responsive. Installation, scheduling, storage and updates must
respect host and operating-system authority.

The [1.5.3 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3)
contains the ten locales; method procedure files were counted at 48 per locale.
Complete files do not prove a translation is correct or that a host loaded a
particular language. The released tree has no project-memory implementation.
Its Mac Codex automatic updater is opt-in; Windows and added Claude/Antigravity
profiles do not use that same scheduled path. Account ZIP creation is not
account installation or activation. Source identity, delivery, complete read,
claimed use and actual application remain different observations.

The [withdrawn Go draft](https://github.com/ParkerHwang/OpenSocrates/pull/112)
contains source and fixture work worth auditing. Its listed macOS ARM64 and
Windows ARM64 fixture gates passed at the reported head, while the Windows x64
first-install watchdog failed. A separate faster run does not erase the failure.
Production signing, live signed update and recovery, original-installer
migration, clean-machine acceptance and live-host activation remain unverified.
No existing result proves 2.0 behavior, model quality, or end-to-end latency.

## Component boundaries and work packages

| Component | Responsibility | Required behavior |
| --- | --- | --- |
| Host adapter | Observe supported native events, enforce input limits and return only outputs permitted by that event. | Declare capabilities, event timing and evidence; distinguish local, account and cloud surfaces. |
| Task intent | Determine objective, constraints, intended reader, artifact and completion conditions. | Ask only when the missing answer materially changes the task. Do not infer authority from retrieved content. |
| Decision router | Select applicable complete methods at substantive judgments. | Permit an empty selection and mechanical bypass; reuse valid delivery within its actual scope; no invented application receipt. |
| Language resolver | Track user conversation, sources, instructions, and each output artifact separately. | Explicit request wins; do not load every locale for a single-language task; preserve quoted text and code. |
| Delivery composer | Produce artifact and separate user-facing work note. | Show uncertainty in the artifact only when the recipient needs it or the user requests it; never invent certainty or commitments. |
| Continuity service | Provide task checkpoints and project-level history through a scoped store. | Preserve accepted intent, attribution, freshness and deletion; report unavailable or insufficient budget. |
| Independent review | Optionally run a bounded, evidence-seeking review concurrently with independent work. | Final artifact checks requiring the artifact remain sequential; integration and validation stay with the main agent. |
| Lifecycle manager | Install, migrate, update, disable, remove and recover per host/scope. | Operate only on identified owned state; protect unrelated files, host trust, user choices and running sessions. |

Define versioned, documented contracts and generated schemas for these seams
before code. Keep method text and public evidence/stop conditions intact unless
a separately reviewed content change is explicitly authorized. A hook output
does not grant permissions or prove that the model read or applied a method.
Each host needs tests for actual event input/output and timing; a shared internal
event vocabulary is not proof that every host can emit every event. If an event
or storage capability is absent, use a documented content-only or no-intervention
fallback and continue ordinary authorized work.

## Working memory and history

**Working memory** is a bounded task continuation checkpoint. Proposed fields:
scope identifiers, objective, output and audience, user-authorized constraints,
completion criteria, accepted decisions and sources, observed completed actions,
remaining actions, unresolved questions, pending effects, version and freshness.
It is restored on an actual continuation boundary when the host can provide
one, not on every model invocation. A checkpoint is a report, not proof of
completed effects or new permission. If the host exposes no reliable compaction
event, use explicit task-boundary/checkpoint guidance and mark automatic
restoration unverified.

**History** is a project/workstream record of consequential decisions, rationale,
milestones, changes and outcomes. A history item should carry its scope,
author/authority, time, source reference, status (proposed, accepted, observed,
superseded or deleted), and revalidation condition when appropriate. Proposed
and accepted states must not collapse; newer source evidence can invalidate a
fact without revoking an accepted objective. A past decision is not blanket
authorization for future external actions.

The first design milestone must settle user-visible enrollment and defaults,
scope hierarchy, data location, retention, quotas, inspect/export/disable/delete,
portable migration and cloud availability. Do not assume cross-host sync. A
local owner-only store is a candidate for native hosts; account-only or bot
surfaces require an independently supported storage path or an honest
content-only fallback. Do not retain raw prompts/transcripts, workspace source
content, credentials, screenshots or hidden reasoning; do not add telemetry.
Record only bounded public decision content and permitted source identifiers.
Deletion must cover managed records and derived indexes/caches; document that
unmanaged exports and system backups are outside product control.

Proposed operations: preview enrollment and scope; enable/disable; prepare a
checkpoint; commit with version precondition and retry identity; retrieve an
applicable bounded context pack; inspect/export; correct, supersede or forget a
specific record; remove a project. A reviewable proposal does not become an
accepted decision merely by saving it. On conflict return current version and
preserve both writers; on replay return the original result, not duplicate
effects. A short pack must not silently omit binding constraints: return an
explicit budget-insufficient state and recover without fabricated context.
An unavailable, deleted or stale record must not appear as current or be
reconstituted by a cache. User or host authority remains superior to a memory.

Implement the service as a new 2.0 design with isolated store, schema
migrations, permission checks and host adapters. Start with deterministic
scope/identity and source freshness; semantic similarity may rank optional
records but must not remove applicable constraints or establish authority.
Avoid serial model calls for storage protocol mechanics; measure any retrieval
or checkpoint overhead. Preserve only observed, approved data across handoff.

## Installation, updates and migration

Provide a verifiable, discoverable official installation entry so a user may ask
their agent to install OpenSocrates. Detect actual host, platform and existing
owned state, then use the supported host-specific installation method. An agent
may guide a user through host trust, account upload or login when it cannot do
those actions. Do not claim activation from archive extraction or status alone.
The Go native distribution should allow a supported end-user path without
requiring Go, Python, npm or a command-line background; actual no-terminal
bootstrap remains a host-specific implementation and usability test.

Use a single owner for each installed component and scope. Inspect existing
installation and disabled state; stage a candidate outside the active version;
verify identity, manifest, signature and compatibility; acquire a bounded
operation lock; record a recovery journal; activate per host; then verify and
commit. Restore a verified prior state on interruption or failed activation.
Never overwrite unknown ownership, unrelated settings or host trust. Existing
1.5.3/npm installations need an explicit, tested transition: do not assume an
old updater discovers a new native channel. Preserve language preferences,
disabled state and old schedules; do not run old and new update managers
concurrently. Test authentic 1.5.3 installers as well as older supported versions.

Verify initial installer trust separately from downloadable checksums. Evaluate
signed update metadata with a pinned trust root, expiry, replay/downgrade defense,
key rotation, size limits and exact platform/artifact hashes. Apply updates only
at a verified safe host boundary, retaining current or recoverable binaries and
compatible data. Hooks must not perform network updates. Show state and failures;
make schedules and major-version policy user-understandable. The choice of
automatic-update default remains a product decision; respect pre-existing
opt-in and disabled choices during migration. Account skills and cloud agents
must use documented host-specific update or a visible manual fallback. Package
manager-owned installations require one designated updater. No signing, stable
publication or production rollback claim is valid without actual release evidence.

## Host capability map

| Surface | Integration route | Evidence required before support claim |
| --- | --- | --- |
| Codex | Native plugin and host-supported event hooks; optional local state. | Trust, actual event delivery, normal tasks, compaction continuation, and install/update per supported platform. |
| Claude Code | Native plugin/hooks where supported. | A separate live-host cell, approvals and scope; do not generalize from Codex. |
| Claude chat/Cowork | Account skill/content and surface-specific account features. | Upload/activation and actual selection on each surface; no assumption of local hooks or silent account updates. |
| Antigravity | Existing rule/skill distribution; native hook extension only after verification. | App/IDE/CLI and global/workspace scope separately; exact documented event capabilities. |
| Cursor | New mandatory adapter using documented skills, plugin and hook surfaces. | Fresh install, trust, supported event payloads, progress and end delivery, actual content use, update/restart behavior and selected platforms. |
| Dot, Grok Bot, Claude Duet | Lightweight skill/profile where the host permits it. | Direct conversation versus delegated/local/cloud behavior, automatic selection, permissions, persistent state, update and latency; unavailable access stays unknown. |

Do not equate a skill available to a delegated worker with automatic execution
in a bot's direct conversation. A current host implementation can change; bind
each qualification to app version, surface, account and operating system.

## Acceptance and failure tests

1. Fresh and resumed synthetic office tasks preserve task intent, recipient and
   completion conditions; the message artifact contains no irrelevant internal
   uncertainty or unauthorized commitments. Where a recipient needs to know an
   uncertainty, the artifact communicates it accurately.
2. Korean conversation to English or Japanese artifact, mixed-language sources,
   all ten instruction locales, and language changes mid-task retain explicit
   output language and avoid unnecessary locale payloads. Inspect real delivered
   text and measure tokens rather than infer from archive size.
3. Task checkpoint survives restart/compaction; history is scoped; accepted and
   proposed states remain distinct; stale evidence is revalidated; deletion
   survives fresh process, cache/index rebuild and exports under product control.
   Test malformed requests, timeouts, conflict, retries, partial writes, quota,
   concurrent updates, and disabled or unavailable stores.
4. Exercise all actual host adapters in synthetic disposable profiles. Record
   registration, event delivery, method reading, reported application and useful
   result separately. Missing live environments are not passes.
5. Compare ordinary host, 1.5.3, sequential review and parallel review on the
   same frozen tasks and model/settings. Record first response, total completion,
   distributions including slow cases, input/output/cache tokens, tool rounds,
   reviewer errors and reader usefulness. Measure checkpoint/router/installer
   costs separately. Define target thresholds only after baseline observations.
6. Exercise fresh install, disabled prior installation, authentic original npm
   adoption, simultaneous schedules, offline, tampered/expired metadata, crash at
   every stage, schema migration, interrupted rollback and major-version update.
   Test supported OS/architecture and account paths independently, including an
   ordinary-user clean machine and live host approval where applicable.

Document each case, version, environment, preconditions, exact operation and
observed result. A fixture test does not replace live-host evidence; an OS or
account cell not run remains unverified. The product must continue ordinary
authorized work when optional reasoning or memory is unavailable.

## Work sequencing and decisions

1. Freeze v1.5.3 compatibility and inventory actual 1.6 historical source,
   failures and reusable concepts; do not merge a withdrawn branch by default.
2. Specify common task/language/continuity contracts and host capabilities;
   freeze synthetic cases and baseline timings before implementation outcomes.
3. Implement and qualify native lifecycle, 1.5.3 adoption and safe updates;
   develop host adapters and Cursor on the same explicit contract.
4. Implement localized reader delivery and scoped memory/history behind
   user-visible policy; integrate genuine continuation boundaries per host.
5. Evaluate selective independent review and bot-specific profiles; record
   capability and performance limits. Complete claims only for tested cells.
6. Reconcile full release scope, signed distribution, upgrade and rollback,
   privacy and documentation before a release decision.

Decisions still needed: release scope per bot and OS; memory opt-in, retention,
and cross-device policy; update default and 1.x-to-2.x transition; exact
performance and usability thresholds after baseline; how to handle hosts with
no reliable event or account update interface. These are design choices, not
reasons to represent missing capabilities as completed.
