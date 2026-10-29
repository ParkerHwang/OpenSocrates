# OpenSocrates 2.0 master plan

Status: preparation and proposed execution architecture, 29 October 2026. The owner selected 2.0 as the target and explicitly withdrew the standalone 1.6 track. This document is an implementation handoff, not proof of delivered behavior or release qualification.

## Product outcome

Help a person turn an ordinary request into a useful result: understand intent and constraints, select relevant thinking when a decision materially changes, communicate to the actual recipient, and continue long-running work without losing governing context. The output must be usable by its intended audience, with internal working uncertainties separately communicated to the requesting user. Preserve uncertainty in the artifact when the recipient needs it for a correct decision or the user specifically requests it; never convert unknowns into false facts or invented commitments.

2.0 retains the 48-method foundation and ten instruction locales, while adding task continuity, reader-oriented artifacts, language separation, installation and lifecycle improvements, mandatory Cursor support, and research toward an adaptive bot profile. The owner accepts additional token use if it materially reduces elapsed time; no speed or quality improvement is assumed before measurement.

## Evidence baseline and preserved work

- Released baseline: [v1.5.3](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3), main `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c`. The Git tree contains 48 `procedure` files for each of ten languages. File existence does not prove translation quality, complete packaged delivery or actual method application.
- The Codex controller template `plugin-src/codex/skills/opensocrates/SKILL.md.tmpl` contains ten controller and ten response-policy insertion points plus multilingual guide passages. This establishes template construction, not how much each host actually includes in the model context. Measure actual discovery, skill read, per-locale method delivery and repeated calls independently.
- v1.5.3 supports opt-in scheduled Codex updates on macOS; its installer rejects Windows automatic updates and the additional Claude/Antigravity profile auto-update paths. The account skill export is not account installation.
- [Go implementation PR](https://github.com/ParkerHwang/OpenSocrates/pull/112), head `8c49b2debbc622d58a928204a9a4ddb3118f5a08`, and [preparation PR](https://github.com/ParkerHwang/OpenSocrates/pull/110), head `2893da99980538408ac004d03f23a43de4eab92d`, preserve substantial work. Both are superseded as 1.6 release work, not proof of 2.0 implementation. Windows x64 first-install CI failed; production signing, live signed update/rollback, authentic legacy migration, clean-machine and authenticated-host evidence remain incomplete. Historical test claims stay attached to their exact revisions. Preserve branch heads and inspect changes before reuse.
- The older project-memory implementation was an unpublished candidate, not a v1.5.3 release feature. In particular the historical v1.5 refocus withdrew the earlier candidate in full; do not merge, cherry-pick or copy its code or guides. Its evaluation results may inform independently designed 2.0 requirements without elevating its evidence.
- [Application-coverage issue](https://github.com/ParkerHwang/OpenSocrates/issues/124) and [office-work evaluation lab](https://github.com/ParkerHwang/OpenSocrates/issues/134) are separate active work; do not close them merely because 2.0 is planned.

## Work packages and exit conditions

Each package must produce the behavior and tests described in the referenced specifications. Dependencies are ordering guidance, not permission to assume unverified host capabilities.

### WP0: Baseline and evaluation

Inventory release and retained drafts, freeze synthetic task cases and compare ordinary host, v1.5.3 and proposed v2 arms under equal model, task and environment. Separate installed, hook delivered, selected, full read, reported application and actual useful output. Record first response and end-to-end latency, slow-tail behavior, failures, tool calls and token use. Establish targets only after measurement. Exit: reproducible baseline, source identities, known missing live cells and artifact-first reader assessments.

### WP1: Work contract and lifecycle

Define an explicit internal task contract for goal, artifact, audience, authority, confirmed facts, constraints and completion conditions; do not expose internal ceremony in ordinary output. Define logical entry, material decision change, artifact preparation and context recovery. Bind each host only to events it actually exposes and use a portable guidance fallback. Preserve valid empty selection, complete eligible methods, required stops and ordinary-work fallback. Exit: synthetic ambiguous, explicit, mechanical, changed-fact, no-method and unavailable-runtime cases pass without repeat questions or fabricated receipts.

### WP2: Recipient-oriented writing

Detect intended author and recipient, preserve supported commitments, supply necessary background and separate sendable content from user-facing working notes. Keep material recipient-facing uncertainty when needed; do not insert internal verification narration into the deliverable. Exit: blinded readers can identify context and next action, drafts do not invent consent or promises, Korean and English cases include multi-recipient and uncertainty-boundary tests.

### WP3: Language and content delivery

Separate conversation, output, source and procedure instruction languages. Explicit user request wins; define scoped preference, ambiguity, multilingual artifacts and unsupported-language behavior. Preserve all 48 methods in all ten languages and complete-method/evidence/stop contracts. Load only needed languages when host behavior permits. Exit: package inventory and semantic checks, mixed-language cases, locale precedence, no unwanted translation and actual-host context measurements.

### WP4: History and working memory

History captures durable decisions and changes; working memory supports the current task across compaction or sessions. Define task/project/user scopes, explicit authorization, attribution, accepted versus proposed status, freshness, retention, editable/deletable records and recoverable storage. Test exact recovery, changed evidence, false authority, conflicts, concurrent writes, deletion through derived indexes, privacy and no-store fallback. No raw transcripts, private reasoning or workspace content retention may be introduced under current repository policy without an explicit policy change. Exit: continuation and deletion work in real consumer paths without cross-project leakage or unsupported claims of speedup.

### WP5: Host adapters and mandatory Cursor

Implement and qualify Codex, Claude Code, supported Claude account surfaces, Antigravity and new Cursor support. Explicitly distinguish local, desktop, cloud and account scopes. Cursor requires separate event mapping, package discovery, supported lifecycle behavior and real installation tests. Complete method delivery and actual invocation are different from installation. Exit: per-surface support matrix with ordinary-request tests, trust handling, controls, failure fallback and no unverified support claims.

### WP6: Installation, update and migration

Support a natural-language installation request with official discovery, environment detection, safe setup and concise human steps where the host requires them. Preserve unrelated settings and disabled state. Design signed, verified staged updates, safe activation, failure recovery, version-policy control and migration from authentic v1.5.3 installations. Establish which host/account surfaces support unattended updates versus a user step; do not equate updater fixture tests with live production evidence. Exit: clean-machine and existing-install scenarios, offline/failure/recovery tests, supported major upgrade path and practical status reporting.

### WP7: Independent review and latency

When complex lanes are independent, explore a writer plus evidence-grounded reviewer in parallel; completed-artifact review still follows draft availability. Keep simple and sequential tasks lightweight, preserve user authorization, and define deadline/fallback handling. Exit: compare four arms, include actual errors and review quality, preserve failures and demonstrate improvement before making performance claims.

### WP8: Bot profile and research

Investigate ChatGPT Dot, Grok Bot and Claude Duet, including direct conversation versus delegated tasks, skill discovery, updates, storage, authorization and bounded latency. Short conversational interaction and substantive background work have different needs; preserve canonical meaning and stop rules in any derived compact guidance. Exit: sources and reproducible capability probes plus a tested initial profile for every bot claimed as supported. Access and native platform restrictions may limit initial claims; user confirmation is needed to reduce an explicitly selected mandatory scope.

### WP9: Release and public documentation

Choose 2.0 migration and compatibility contracts; reconcile Go draft on current main without importing withdrawn candidate code. Verify canonical/generated consistency, all claimed host and OS cells, security, ordinary-user installation, updates, user controls and recoverability. Record unavailable evidence and risks; release only through the repository's protected workflow. Provide aligned English/Korean public instructions. Exit: reviewable release candidate with exact evidence and explicit unresolved constraints.

## Dependencies and sequencing

WP0 precedes comparative claims. WP1 task semantics inform WP2–WP5; WP3 governs localized delivery. WP4 stores structured public state rather than hidden reasoning. WP5 and WP6 jointly prove installation and delivery, with Cursor mandatory. WP7 and WP8 can be researched in parallel but cannot bypass WP0 or their host-specific evidence. WP9 integrates all claimed features. Scope changes require preserving the owner's decisions above.

## Decisions to resolve during preparation

1. Which OS and surface combinations can be supported and verified for each mandatory host, particularly Cursor cloud versus local?
2. Which bot surfaces can be accessed and integrated in 2.0, and which limitations must be shown explicitly?
3. Which 1.6 Go changes can be independently reviewed and ported without changing product contracts or inheriting unverified claims?
4. Which automatic-update defaults and major-version transition provide the promised ease while respecting user and organization controls?
5. What are the storage defaults, retention, scope and user controls for history and working memory?
6. After freezing the baseline, what quality and latency budgets are reasonable per task class and host?

## Work discipline

Keep active 1.5.x release work separate, do not mutate installed user environments to test, and do not overwrite historical measurements. Before implementation consult `AGENTS.md`, `CONTRIBUTING.md`, current `main`, this packet and the active 2.0 tracking issue. Use disposable fixtures and synthetic content. Do not promise release dates or an automatic update on a platform that does not support one.
