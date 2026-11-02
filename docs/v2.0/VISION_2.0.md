# OpenSocrates 2.0 product direction and requirements

Status: development basis reflecting the owner interview of 2026-11-02. This records product direction, not proof of implementation, installation support, learning effectiveness or release completion. [한국어](VISION_2.0.ko.md).

## Intended experience

A person requests work in a conversation in their existing desktop AI app. OpenSocrates interprets an imperfect request, asks material questions and explains deliverable choices when needed, then prepares the work prompt. It selects reasoning guidance and context for the current task and sends work to new, real app conversation sessions. Those sessions coordinate and return results through the OpenSocrates layer. The person can focus on results and consequential decisions without organizing the team or repeatedly explaining the same background.

Each person's OpenSocrates creates and develops reasoning guides from actual work. A guide goes beyond facts or prohibitions to help determine what context and perspective to think from. OpenSocrates also becomes a real program with a lightweight, fast database, communication and state management.

The user wants real, user-visible conversations across different apps to work as one team. That is distinct from a universal technical claim that no subagent can do anything similar. The user also chose task/expected-result prompts and reasoning guides without a predefined role roster because fixed role definitions may constrain capable models. The general effect of role prompts and the quality advantage of this choice need separate evaluation; this does not prohibit describing the capabilities, tools and results a particular assignment needs.

## Operation and outstanding evidence at a glance

This is the **target experience**, not a claim that the connections or quality already work.

| What the user experiences | What OpenSocrates is intended to do | What development must establish |
| --- | --- | --- |
| Make an imperfect request in a familiar app and discuss deliverable format when useful. | Clarify purpose, choices and authority in the intake conversation; prepare suitable guidance and context. | Are settled choices preserved without repeated questions? Does intake avoid producing the actual artifact? |
| Focus on the result and consequential decisions. | Delegate work to a separate real conversation. Open additional conversations when useful and connect requests and replies through the layer. | Can each app/mode/OS create real conversations, identify recipients, deliver guidance/context and exchange results? |
| Explain less over time while retaining the ability to change choices and return to an earlier direction. | Develop personal guides from permitted experience and combine or reassemble them where suitable. Also use applicable guidance from the initial 48. | Does personalization actually help? Do in-flight application and learning pause/resume respect current choices? |
| Receive a usable result in the chosen format and continue working with existing files when needed. | Return execution-session results and manage relevant file and context state. Check outside changes at the next related task. | Can the file actually be opened and edited as requested? Can outside changes, concurrent writes and user access be assessed? |

When a connection is unavailable, continue feasible consultation and unrelated work while distinguishing unconfirmed starts, receipt and completion from success. Preserve current policy against copying raw conversations or workspace content into the program's persistent store. Continue with the [system structure](SYSTEM_2.0.md) for flows and failure boundaries, the [development roadmap](ROADMAP_2.0.md) for starting and integration, and the [validation plan](VALIDATION_2.0.md) for evidence and comparisons.

## Confirmed scope and deferred work

| Item | First 2.0 development scope |
| --- | --- |
| Apps | ChatGPT desktop and Claude desktop. |
| Operating systems | macOS and Windows. Qualify the four app/OS combinations independently. |
| Experiences inside ChatGPT | Treat Chat, Work and Codex as experiences within the same desktop app. Investigate each experience's integration capabilities separately. |
| Execution | Use real conversation sessions in the person's existing apps. Direct model-provider API execution that builds a separate agent app is outside the current scope. |
| Computer interaction | When necessary, use app-provided computer use or existing open-source tools. Choose the actual tools after host investigation. |
| Devices | Initially operate on one computer. Cross-computer synchronization and personal-data transfer are later-update scope. |
| Deferred hosts | Grok Bot, Cursor, Antigravity and other app connections are not first-version support targets. This does not rewrite prior releases' support records. |

macOS and Windows coverage is a product requirement. A document, skill file or successful run on one OS does not establish support for another combination. An inaccessible combination remains unverified; reducing mandatory scope requires a separate product-owner decision.

## Three kinds of guidance

| Kind | Origin and change authority | Use |
| --- | --- | --- |
| The 48 base reasoning guides | Supplied at installation and versioned with the product. | Use before personal guides exist, or when no suitable personal guide applies to the current task. |
| Shared guide-generation instructions | Common to all users; evolve through OpenSocrates version updates. | Govern how personal learning turns experience into guides and evaluates them. Individual learning does not autonomously rewrite these common instructions. |
| Personal generated reasoning guides | Created and developed from each person's work, choices, edits and relevant experience. | Prefer suitable personal guidance. Multiple guides can be selected, combined and recomposed. |

Personal generated guides have no fixed product count limit such as 48. This does not imply infinite disk, context or account usage. Retrieval, delivery size, duplicate and stale-guide handling, and storage budgets remain measurable design work.

Recomposition is broader than concatenating documents. The system can choose and connect relevant parts into a suitable thinking approach for the current job. It may request a separate agent session through OpenSocrates for that work. Whether a recomposed guide stays task-specific or becomes a reusable personal guide is also a contextual judgment informed by experience. Specify and evaluate the criteria before implementation.

## Requirements and observable outcomes

This table uses `REQ-01`–`REQ-16` for product requirements, distinct from roadmap work packages `P01`–`P15`. Vision `P01`–`P16` in the earlier draft maps to the same-numbered `REQ-01`–`REQ-16`.

| ID | Requirement | Acceptance example |
| --- | --- | --- |
| REQ-01 | Infer purpose, constraints and desired results from imperfect requests. Ask concrete questions only about gaps that affect decisions. | A disorganized report request leads to a focused question about a consequential choice without asking again for supplied information. |
| REQ-02 | Show an approximate picture of content, format and use, with consultation suited to the person's understanding in this situation. | Explain the editing, sharing and usage differences between Word and HTML when needed. Do not unnecessarily push a person away from an already selected format or repeat consultation for every minor action. |
| REQ-03 | Perform no actual deliverable production in the user's request conversation. | That session handles intent, work-prompt preparation, guide/context preparation, status and consequential-decision consultation. Research, analysis, charts, document production and actual artifact integration happen in new work sessions. The request session may present or deliver the completed result. |
| REQ-04 | Perform work in real app conversation sessions. | The person can ordinarily stay in the request conversation. If needed, they can open a work session in the app's conversation list to inspect or participate. Verify creation and access through capabilities each app permits. |
| REQ-05 | Route all inter-agent communication and delegation through OpenSocrates. | A research session that needs a chart sends the request to OpenSocrates. The layer handles work routing and guidance/context delivery; results and discussion return through that path. Direct bypass communication does not satisfy this requirement. Do not assume all host-internal behavior can be observed or controlled. |
| REQ-06 | Delegate dynamically with a single task prompt that clearly describes work and expected output. | Form sessions for the current task without a predefined role inventory or role-specific AGENTS.md. Clarify the request, output and relevant constraints for that particular assignment. |
| REQ-07 | Judge app/model selection and delegation needs in context. | OpenSocrates selects among apps, models, tools and permissions actually available on that computer. Distinguish assumed capability from the quality of the observed result. |
| REQ-08 | Deliver applicable reasoning guides and context to each conversation making judgments, including intake, execution, reassembly and learning. | Intake also needs guidance useful for interpreting and consulting. Learning conversations receive the full product-versioned common generation instructions, or a product-defined complete module together with its required dependencies and safeguards. Do not force irrelevant guidance; distinguish delivery, reading, use and quality. |
| REQ-09 | Prefer appropriate personal guides and use the base 48 when no suitable personal guide exists. | Exercise the same task for a new user and one with accumulated personal experience. Do not force an unrelated personal guide; explicit user conditions take precedence. |
| REQ-10 | Select context by user, project, work type and time, with priority and version management. | Do not indiscriminately apply experience from another project. Recover the relevant line of work when the user returns to an earlier direction, distinguishing old assumptions from currently established facts. Git-tree behavior is an analogy; an actual Git implementation is undecided. |
| REQ-11 | Judge which consequential decisions require user confirmation in context. | Evaluate combinations of individually small decisions that together produce a consequential change. Preserve confirmation, delegated authority and settled choices. Learned preferences do not create new permissions. |
| REQ-12 | Learn quietly from real work and allow relevant changes during ongoing tasks. | Treat relevant experiences as learning candidates without a “learn this” command. Track applicability and distinguish personal preference, project constraints and one-off circumstances when testing changes. |
| REQ-13 | Record the progress of background learning itself and resume after interruption. | Distinguish observed experience, open learning questions, applied guides and unconfirmed outcomes. Recheck intervening context changes and test duplicate application and mistaken completion on recovery. Do not store private hidden reasoning. |
| REQ-14 | Manage files, folders and versions contextually. | Judge when to edit an existing file, retain a new version or organize related folders according to the work and existing practices. This does not grant authority to change unrelated files. |
| REQ-15 | Discover and interpret external file changes on later relevant work. | Do not continuously watch every folder. Compare permitted prior state records with the current file. Without comparable prior content, do not claim to know the detailed difference. Do not infer authorship or intent without separate grounds. |
| REQ-16 | Let one team operate autonomously while reducing the person's routing and team-management burden. | Agents can discover needed work and coordinate through OpenSocrates. Consequential decisions return to the request conversation. Make interruptions and host limitations explicit. |

## What the necessary and sufficient conditions are conditions for

**First distinguish the claim.** Fulfilling the full 2.0 scope chosen by the user, observing one collaboration in a particular environment, and delivering a useful product that real users continue to use are different claims. This summarizes the user's decisions and the evaluation plan; it does not claim the conditions are already satisfied.

| Claim | What is needed and how to assess it | Why that alone is not enough |
| --- | --- | --- |
| **Full 2.0 scope** | Meet `REQ-01`–`REQ-16` above and the agreed app/OS scope under each requirement's applicable conditions. Initial 48 guides and evolving personal guidance, separate intake and real execution conversations, layer-mediated collaboration, user choices and authority, and continuity of context, files and learning are all required. | Guide files, synthetic checks or success in one app alone do not satisfy the other capabilities and environments. A particular database, fixed roles or creating a new guide from every experience is not a user-established necessity. |
| **Observation of one specified collaboration** | For example, for a synthetic report that requires a separate chart task, observe the real execution conversations, delivery of suitable guidance, actual layer-mediated request and return, and the chosen artifact's checks in the specified app/OS. | A send attempt or selected guide ID does not prove receipt or use. One observed case does not establish other environments or long-term personalization effects. |
| **A useful product that real people keep using** | The product must actually help people and be used. To support that claim, separately examine real-work output quality, burden, trust and use. An evaluation must state for whom, over what period and by what measure success is judged. | A feature list, document or demonstration alone cannot guarantee satisfaction or adoption. A missing comparative evaluation also does not prove a product is not actually useful. |

**Necessary and sufficient conditions apply only to a narrowly defined judgment.** For example, if a synthetic report test defines `PASS` as “in the specified environment, all of the following are observed: a real separate conversation, delivery of guidance required by this test, at least one layer-mediated request and return, and the artifact checks,” observing those items is necessary and sufficient *by definition for that test's PASS*. The equivalence comes from the test definition. Passing it does not automatically establish behavior outside its observation scope, all of `REQ-01`–`REQ-16`, other app/OS combinations, or benefit to real users. If a stage cannot be observed, record it as **unknown**, distinct from an observed failure. The [validation plan](VALIDATION_2.0.md) specifies more detailed criteria, evidence and limits.

Test conditional requirements according to their meaning. A task may appropriately use only one execution conversation when further delegation is unnecessary, but if no inter-session communication occurs, the statement “all communication went through the layer” cannot by itself establish a **successful round trip**. Test that capability on a separate task requiring an actual exchange. When a user has stopped learning or guide use within a particular scope, following that choice is correct behavior. The capability itself still needs separate tests with permitted conditions and relevant evidence. One experience that produces no personal guide is not by itself success or failure.

An unsupported confirmed route and other unverified routes are different; a restriction in one host route does not establish that all alternatives are impossible. Nor does one cell's success or unknown state establish complete support. Reducing the agreed app/OS scope requires the user's decision. This plan establishes no sufficient condition guaranteeing actual product success or a particular person's response.

## Settled learning direction and open mechanism

The settled direction is personal learning, adjustment through actual work, quiet ordinary updates, applicability to relevant ongoing tasks, and tracking the learning process. Corrections and review arising in agent collaboration can become learning questions inside that person's OpenSocrates. Treating something as an “issue” here means an internal learning problem, not creating a GitHub issue.

RL currently describes the intended feedback loop. Reward signals, learning units, guide representation and adoption/hold/retirement criteria require specification and experiments. Do not imply that a particular reinforcement-learning algorithm, model-weight update or improvement of internal token alignment has been selected or demonstrated. Absence of user edits alone does not establish satisfaction or success.

Do not turn quiet learning into repeated per-update approval. At the same time, the open decisions below must define how mistaken learning can be recognized and corrected and how scope and versions are handled. This document does not elevate unadopted proposals into confirmed user requirements.

## Three user-facing situations — planning examples

These fictional dialogues explain intended behavior; they are not a fixed script or a record of a live app run.

### 1. The output format needs consultation

A user asks, “Please pull together churn material for an investor.” The intake conversation checks available material and context and describes an approximate result. For example: “I understand this as material to examine the churn trend, causes and next choices. Word is convenient for an editable document; HTML may work for material opened as a link. How do you plan to use it?” Actual sharing and access needs can change the tradeoff; do not push a format before the user chooses.

If the user chooses Word, preserve that choice and purpose for the work. The intake conversation prepares applicable guides, relevant material and authority, then delegates actual work to a new app conversation. If a chart is needed and separate delegation is useful, route that assignment through OpenSocrates to another real conversation. The intake conversation coordinates content and status and communicates the confirmed result.

### 2. An experienced user has already made the choices

The user requests, “Update the existing report with the latest metrics, three pages in Word.” If the file, audience, purpose and permitted scope are clear in context, do not ask them to choose the format again. When an edit to that file is already authorized, do not repeatedly ask merely because it overwrites. The execution conversation checks the material and permitted file state, performs the work and communicates the result and materially important uncertainty.

Even with metrics and length settled, the material may differ depending on whether the reader is being **persuaded to invest** or is receiving a **balanced decision document**. If that difference matters and cannot be resolved from existing context, explain and ask about that choice. “Metrics first” and “decision focused” can coexist; do not invent a forced choice between them.

### 3. Direction changes during actual work

The user opens an execution conversation and says, “Lead with what we should do next, not the causes.” If OpenSocrates can lawfully observe the change and deliver it to that execution conversation, it can reflect the current-task decision and consider a guide candidate for relevant work. Do not infer that the correction is a preference for every task. If in-flight delivery is unavailable or unobservable, leave that application pending/unknown and do not present an old result as incorporating the new decision.

Learning does not require a separate “learn this” instruction. Actual observation paths, runnable times, retention policy and evidence levels must be verified by surface. Judge the amount of user-facing consultation and reporting in context; do not turn the number of turns in these examples into a universal rule.

## Data and authority boundaries

Current [AGENTS.md](../../AGENTS.md) prohibits telemetry, credential collection, raw prompts/transcripts, screenshot retention, workspace-content retention and hidden-reasoning capture. [CONTRIBUTING.md](../../CONTRIBUTING.md) also contains related privacy restrictions. This plan does not amend those policies.

The user has already requested generation, retention and quiet use of personal guides. Do not categorically prohibit all guide prose or repeatedly seek separate approval for prose that does not reproduce raw conversations or workspace content forbidden by current policy. Design automatic pre-storage checks and test their detection limits; do not promise they catch every leak or require a human approval on every update. Work that can be designed under current policy includes scoped task/guide identifiers, versions, state, permitted source references and minimal file-state fingerprints. Personal guides must not become a store of copied conversations or documents. Specify authority to send project content to another app, the personal state retained, and deletion scope.

Detailed file comparison requires available prior versions or equivalent change material. A proposal for OpenSocrates to retain new source copies or workspace snapshots for learning can conflict with current policy. Before implementing that capability, obtain an explicit product-owner policy decision and separate review. Until then, distinguish change detection from available detailed comparison; add neither blanket file monitoring nor raw-content retention.

## Design decisions to develop during implementation

| Decision | Decision responsibility | Required input |
| --- | --- | --- |
| Shared generation-instruction format/version and generated-guide representation | Content/learning implementers propose; product owner reviews. | Synthetic learning cases, differently scoped edits/counterexamples, and recomposition comparisons. |
| Guide/context applicability, combination and base-guide fallback | Learning/context implementers propose. | New and experienced users, multiple projects and conflicting-guide cases. |
| Session creation, guidance delivery and status recovery for each app experience | Host implementers. | Actual capabilities by app/OS/version/account/permission; do not transfer evidence between cells. |
| Timing/scope of in-flight guide changes and recovery semantics | Learning/coordination implementers propose. | Concurrent tasks with different purposes, interruption and newer-context cases. |
| Learning improvement/regression, attribution and correction controls | Evaluation implementers propose; product owner reviews. | Blinded artifact assessments, mistaken generalization and unexplained user edits. |
| Storage, permission, deletion, recovery and any file-comparison policy change | Implementation/security contributors propose; product owner explicitly decides. | Minimal-data design, current-policy differences and actual host permissions. |
| Stack, database, execution lifetime and usage budgets | Implementers propose. | Measured device costs/latency and failure/recovery experiments; quantify the lightweight/fast objective. |

Distinguish requirements from technical choices. A user-centered team, evolving personal guides and the mediating layer are confirmed product direction. MoE, Git and RL analogies do not prove a particular data structure or algorithm necessary or sufficient. Component existence alone does not establish product success; evaluate observed user experience, quality, authority and continuity.
