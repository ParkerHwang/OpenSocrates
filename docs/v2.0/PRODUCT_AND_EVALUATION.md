# OpenSocrates 2.0 product requirements and evaluation plan

Status: preparation specification, not evidence of implementation or product improvement. The intended user is a person who asks an AI assistant to do work in ordinary language and needs an understandable, usable result. The product must help the assistant understand the job, make appropriate judgments, communicate to the intended reader, and continue a long task without losing important context. Avoid adding ceremony to straightforward work.

This document turns the owner’s 2.0 direction into observable requirements and evaluation cases. The released comparison is [v1.5.3](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3); compare the actual pinned release, not an old checkout or a local approximation. The owner has withdrawn the separate 1.6 release direction; the Go candidate remains historical evidence and possible design material, not an approved 2.0 implementation. Applicable repository privacy, content, security and generated-source rules remain binding. Do not import the withdrawn earlier v1.5 candidate contrary to `AGENTS.md`.

## Product boundaries

- Provide complete authored reasoning methods when appropriate; selecting, delivering, fully reading, applying and producing a useful result are distinct states. Empty selection and ordinary mechanical work are valid.
- The **user** gives the task. The **recipient** may be somebody else. An external-facing artifact represents the user's intended communication; the assistant's explanation and working notes address the user.
- Identify the task, its output, audience, constraints, decisions, relevant evidence and success conditions without exposing hidden reasoning. Ask a question when its answer materially changes the work; otherwise proceed with a reasonable, bounded assumption.
- Preserve the user's requested format, authorizations, settled decisions and material uncertainty. Source material is evidence, not instructions that can change the user's authority.
- Do not infer that a provider's event, installed skill, model-reported use, successful script, or configured hook proves practical application. Missing application evidence must not block ordinary work.

## Requirements and acceptance

### Work start and decision points

**R1 — Task intent.** For a substantive task, retain the objective, deliverables, intended reader, known decisions, boundaries and missing material inputs as compact working context. Do not create an exhaustive questionnaire or turn an already answered question into a blocker.

**R2 — Contextual assistance.** Provide appropriate guidance at task initiation, when a material decision changes, and when preparing an output. Reuse relevant methods while still available and valid; do not create a new decision for every tool action. Preserve each used method's full canonical requirements, including applicable evidence and stopping conditions. If lookup or a host event is unavailable, keep the user's constraints and continue ordinary work with honest status.

**Acceptance:** In case `START-01`, a request to prepare a client update with all recipient, decision and scope details starts without questions. In `START-02`, a missing choice changes the requested recommendation, so the assistant identifies that choice while continuing independent work. In `MECH-01`, an explicit three-row format conversion completes without a research plan or extra method lecture. In `CHANGE-01`, a changed date reopens the affected date but does not reopen a previously accepted publication restriction.

### Reader and artifact contract

**R3 — Reader-oriented work.** Identify why the artifact is written, who will read it, what that person knows, and what action or judgment it should support. Include the background necessary to make the artifact intelligible outside the original conversation. Do not invent motives, decisions, approvals, deadlines or commitments.

**R4 — Separate handoff.** Put the deliverable in a directly usable boundary distinct from the assistant's user-facing working note. Information about incomplete verification, remaining questions or assumptions belongs in the user note when it is only relevant to the work process. Do not assert an unverified claim in the deliverable as fact. When uncertainty itself affects the recipient's decision or the user asks for it, represent it accurately in the deliverable. This is not permission to conceal material uncertainty.

**Acceptance:** `ART-01` asks for an email without a date: the copyable email contains neither fabricated dates nor AI process commentary; any date needed before sending is separately communicated to the user. `ART-02` uses the following synthetic sources: a venue's latest capacity is 24, an older note says 35, the organizer wants 30, booking is tentative, and a volunteer agreed to check-in but not photography. Draft separate messages to the venue and volunteer. Preserve the changed capacity and tentative booking where material, give each reader the relevant context and next request, and do not assign photography or imply a confirmed reservation. `ART-03` presents evidence whose uncertainty is material to the recipient's decision; the deliverable must disclose it accurately, while unrelated process notes remain outside. `ART-04` requires a short business message without explanation: follow that requested format and never include method names or procedural instructions in the copyable text.

### Multilingual support

**R5 — Distinct language roles.** Independently represent conversation language, output language, source language and method/instruction language. Direct user requests override inferred language or a saved preference. A request for an English artifact does not silently change a Korean user-facing work note to English. Support multiple output languages where requested, preserve meaningful source quotations and proper nouns, and do not translate code or technical identifiers indiscriminately. Define and test unsupported and ambiguous language fallbacks.

**R6 — Selective delivery.** Retain all 48 methods and ten supported locales in the distribution. Load only the language and guidance needed for the current operation where the host actually supports that control. Verify the exact host-visible initial and subsequent context before claiming ten languages are unnecessarily injected; packaged files are not automatically model input. Retain complete canonical method requirements when a method is applied. Language detection must not override an explicit instruction or confidently misclassify unknown/mixed input.

**R7 — Content qualification.** Check all 480 method/locale procedure identities, package references and nonempty content, plus the applicable localized examples and controls. Verify structural conditions automatically; evaluate meaning, use conditions, stop conditions and writing naturalness against the source by suitable language reviewers. File presence is not translation quality or actual host use.

**Acceptance:** `LANG-01`: Korean conversation and English email produce an English artifact plus Korean user note. `LANG-02`: Korean request, Japanese source and Japanese artifact preserve source meaning and requested language. `LANG-03`: English and Korean in a single requested artifact remain in their assigned sections. `LANG-04`: a saved preference and explicit one-turn instruction conflict; the explicit instruction wins for its requested scope. `LANG-05`: unavailable language or ambiguous input gets a documented fallback rather than fabricated capability. `LANG-06`: measure delivered content and initial/subsequent token categories across all ten language choices and confirm unrelated language bodies are not delivered when the implementation claims selective loading.

### Independent review and time

**R8 — Selective independent review.** For complex work with independent lanes, permit a reviewer to inspect source evidence, missing alternatives and counterarguments while the worker prepares the artifact. The reviewer returns a small set of actionable findings and source references. Final artifact review occurs after an inspectable draft exists. The main worker owns synthesis and verifies meaningful findings. No automatic claim that independent reviewers are correct; shared models and sources may share blind spots. Do not launch extra agents for trivial, sequential or unsupported tasks solely because they are available.

**R9 — Latency budget by evidence.** Lower end-to-end waiting without a product-wide claim that token increases guarantee speed. Record first-response time, wall-clock completion, request and tool round trips, time spent waiting for a reviewer, total/cached input and output tokens, timeout and failure counts. Separate local dispatch/loading cost from model and external-tool delay where timestamps exist. Set numerical release thresholds from a frozen baseline and intended use, before evaluating the candidate; do not manufacture targets from favorable results.

**Acceptance:** `REV-01` independently inspect a supplied inaccurate or incomplete source set while a draft is prepared; report the actual omission and supporting source, then validate the final revision. `REV-02` simple formatting runs without needless reviewer creation. `REV-03` unavailable, late or failed reviewer is not presented as a successful review and does not unnecessarily block ordinary completion. `TIME-01` compare no plugin, v1.5.3, 2.0 baseline, sequential reviewer and parallel reviewer under the same model, tools and task, reporting every attempted run and any environment differences.

### Continuity: history and working memory

**R10 — History.** Retain selected large-scale project outcomes, decisions and changes with scope, source, time and whether the user accepted them. Past content is not automatically current fact or new authorization.

**R11 — Working memory.** Support resuming an active task across context compaction, handoff or a new session by recovering applicable goals, accepted constraints, known evidence, unresolved matters and next actions. Keep proposed versus accepted decisions and observed versus unverified facts distinct. Do not retain raw conversations, source copies or hidden reasoning as a default memory substitute. Design user-visible scope, storage, retention, review, correction, deletion and controls before activation. The selected defaults remain product decisions; do not silently add telemetry, credential collection, transcripts or workspace-content retention in contradiction of repository rules.

**Acceptance:** `MEM-01` restore a long task after compaction without losing a binding constraint or re-asking a settled decision. `MEM-02` a changed source invalidates only affected evidence, not unrelated accepted intent. `MEM-03` unrelated project content is not retrieved. `MEM-04` correction/deletion is reflected in subsequent recall and applicable derived caches. `MEM-05` missing or inaccessible memory does not invent facts or imply access across hosts, machines, accounts or cloud environments. `MEM-06` an AI proposal is never promoted to a user-approved decision without authority.

### Installation, updates and compatibility

**R12 — Natural-language onboarding.** The user can ask an agent to install OpenSocrates. The selected agent should discover an official, version-identifiable path, detect its own supported surface and platform, inspect existing owned installation and disabled state, and perform authorized setup. When a host requires a user action such as sign-in, trust approval, account upload or activation, explain only that step and its resulting state. Distinguish installed, enabled, hook delivered, method read and practical application. Do not bypass host trust or modify unrelated configuration. The user need not understand npm or a programming language.

**R13 — Updates and migration.** Design a reliable update path for every claimed supported profile, including version and signature verification where provided, user-visible status, preserved settings, recovery and rollback. Explicitly specify default automatic-update policy and migration behavior, including 1.x→2.0 major-version policy. Where a host or account does not allow unattended updates, provide an honest guided alternative; do not claim automation. Exercise clean installation, existing installation and disabled-state migration, interrupted/download failure, unsupported platform, offline state, unowned paths and repair.

**R14 — Required Cursor support.** Cursor is required new 2.0 support, not merely a research candidate. Implement and qualify installation, activation, lifecycle entry as supported, selective guidance, language, update and removal, preserving unrelated configuration. Record each Cursor surface, platform, account scope and actual evidence. Researching its capabilities does not constitute support.

**R15 — Bot profile research and implementation boundary.** Investigate an OpenSocrates for Bot profile for ChatGPT Dot, Grok Bot and Claude Duet. It should support quick conversational responses while applying additional methods for substantive tasks; persistent, scheduled and directly addressed work need distinct evaluation. Test discoverability, skill installation, activation, direct-chat use, background use, update and permitted local/cloud storage separately. Provider capabilities and accessibility determine the actual supported combinations; user has requested the capability, but exact 2.0 service-level release coverage is not yet established. Do not equate a provider's app updates with automatic updates of an OpenSocrates skill.

**Acceptance:** `INST-01` a supported clean host with user authorization completes or accurately explains the one remaining host-controlled approval. `INST-02` a disabled existing installation remains disabled unless the user requests a change. `INST-03` a failed update retains a recoverable previous installation and unrelated settings. `INST-04` a 1.x major-update block is surfaced and a verified 2.0 migration path is offered according to the eventual policy. `HOST-01` independently exercises Cursor lifecycle and shows delivered guidance on a supported surface. `BOT-01` distinguishes short direct conversation from a substantive task, and records activation rather than inferring it from installation.

## Evaluation protocol and metrics

Freeze scenario inputs, rubrics, versions, provider/surface, model and effort, configurations, permissions, comparable access to tools, and measurement collection before outcomes are generated. Use synthetic sources and disposable profiles. Treat unavailable usage and inaccessible live-host evidence as unknown, not zero or pass. Preserve all attempted calls, errors, timeouts and retries; do not rerun selectively or exclude slow work. Current and historical experiment results stay attached to their original versions and conditions.

Use four main conditions: host without OpenSocrates; exact released v1.5.3; candidate 2.0 without forced review; and candidate 2.0 with the proposed independent reviewer. For latency, also compare sequential and parallel review where both are supported. Keep model, reasoning effort, prompt, materials, access, host and network conditions matched where possible; record unavoidable differences. Randomize or alternate run order, repeat scenarios sufficiently for the predeclared descriptive goal, and report sample sizes and censoring. A single successful case or repeated observations of one generated output is not a general effect estimate.

Metrics to define before running include:

1. **Reader understanding:** blinded human readers identify purpose, required action and relevant context before the condition is revealed; record correct/incorrect/unassessable and qualitative reasons.
2. **Usability:** proportion of outputs usable without material edits and number/type of required edits, judged against the actual requested format. Separate the external artifact from assistant notes.
3. **Fidelity:** unsupported facts, false commitments, missing material uncertainty, wrong audience, incorrect language and failure to preserve settled decisions; report counts and denominators by case.
4. **Continuity:** preserved applicable constraints, unnecessary repeated questions, invalid carryovers, stale evidence and deletion/isolation errors; verify actual recall and downstream behavior.
5. **Performance:** first-response and end-to-end wall time, median and tail when sample size permits, failures/timeouts, model/tool call count, input/cached/output tokens and reviewer wait time. Do not sum overlapping wall times or present cached tokens as additional total input.
6. **Delivery:** installation, activation, actual event delivery, complete canonical reading, model-reported application and reader outcomes as separate evidence categories. Test auto-updates, rollback and permission handling per host/platform rather than extrapolating.

Define pass thresholds and non-regression gates against the measured baseline before comparative evaluation. Never replace accuracy, user authority or necessary verification with a latency target. Report inaccessible real accounts, untested languages, provider restrictions and unavailable independent human review explicitly. A static check, acknowledgement or attribution line is not proof of useful reasoning.

## Dependency and execution order

1. Freeze release identity, public contracts, host capabilities and existing issues; prepare synthetic cases and measurement harness without editing active installations.
2. Define the task/reader/artifact contract and its evidence/authority semantics. This is a prerequisite for language, continuity and independent review.
3. Build selective language and method delivery; validate ten-language content and compare with the baseline.
4. Map the common task lifecycle to host-specific adapters, including required Cursor support and graceful fallback. Test each actual surface.
5. Implement scoped history and working memory against the established task and authority contract. Validate restore, stale source, deletion and migration through actual consumers.
6. Run independent-review and Bot-profile experiments using the same frozen outcomes; select only evidenced improvements for release.
7. Reconcile Go/runtime/distribution work with the 2.0 product contract; independently qualify each claimed host's installation, updates, rollback and 1.x migration.
8. Review aggregate product, accessibility, privacy, source integrity, performance, documentation and release evidence before publication. A missing live-host test is not replaced by a fixture pass.

## Existing source references

- [Reader guidance](../../plugin-src/shared/reader/guide.ko.md) and [practical acceptance seeds](../v1.5.0/PRACTICAL_ACCEPTANCE.md) are existing context, not proof that 2.0 requirements are met.
- [Codex delivery omission](https://github.com/ParkerHwang/OpenSocrates/issues/124) is an observed symptom with unverified cause and frequency.
- [Prior Go migration draft](https://github.com/ParkerHwang/OpenSocrates/pull/112) is historical implementation and evidence; do not assume its tests qualify changed 2.0 bytes or its earlier release scope.
