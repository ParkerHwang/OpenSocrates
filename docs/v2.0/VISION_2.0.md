# OpenSocrates 2.0 product direction and requirements

Status: development basis reflecting the owner interview of 2026-11-02. This records product direction, not proof of implementation, installation support, learning effectiveness or release completion. [한국어](VISION_2.0.ko.md).

## Intended experience

A person requests work in a conversation in their existing desktop AI app. OpenSocrates interprets an imperfect request, asks material questions and explains deliverable choices when needed, then prepares the work prompt. It selects reasoning guidance and context for the current task and sends work to new, real app conversation sessions. Those sessions coordinate and return results through the OpenSocrates layer. The person can focus on results and consequential decisions without organizing the team or repeatedly explaining the same background.

Each person's OpenSocrates creates and develops reasoning guides from actual work. A guide goes beyond facts or prohibitions to help determine what context and perspective to think from. OpenSocrates also becomes a real program with a lightweight, fast database, communication and state management.

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

| ID | Requirement | Acceptance example |
| --- | --- | --- |
| P01 | Infer purpose, constraints and desired results from imperfect requests. Ask concrete questions only about gaps that affect decisions. | A disorganized report request leads to a focused question about a consequential choice without asking again for supplied information. |
| P02 | Show an approximate picture of content, format and use, with consultation suited to the person's understanding in this situation. | Explain the editing, sharing and usage differences between Word and HTML when needed. Do not unnecessarily push a person away from an already selected format or repeat consultation for every minor action. |
| P03 | Perform no actual deliverable production in the user's request conversation. | That session handles intent, work-prompt preparation, guide/context preparation, status and consequential-decision consultation. Research, analysis, charts, document production and actual artifact integration happen in new work sessions. The request session may present or deliver the completed result. |
| P04 | Perform work in real app conversation sessions. | The person can ordinarily stay in the request conversation. If needed, they can open a work session in the app's conversation list to inspect or participate. Verify creation and access through capabilities each app permits. |
| P05 | Route all inter-agent communication and delegation through OpenSocrates. | A research session that needs a chart sends the request to OpenSocrates. The layer handles work routing and guidance/context delivery; results and discussion return through that path. Direct bypass communication does not satisfy this requirement. Do not assume all host-internal behavior can be observed or controlled. |
| P06 | Delegate dynamically with a single task prompt that clearly describes work and expected output. | Form sessions for the current task without a predefined role inventory or role-specific AGENTS.md. Clarify the request, output and relevant constraints for that particular assignment. |
| P07 | Judge app/model selection and delegation needs in context. | OpenSocrates selects among apps, models, tools and permissions actually available on that computer. Distinguish assumed capability from the quality of the observed result. |
| P08 | Deliver relevant reasoning guides and context to every executing session. | Additional work and guide-recomposition sessions receive the inputs they need. Transmission success, reading in the session, actual application and output quality remain separate observations. |
| P09 | Prefer appropriate personal guides and use the base 48 when no suitable personal guide exists. | Exercise the same task for a new user and one with accumulated personal experience. Do not force an unrelated personal guide; explicit user conditions take precedence. |
| P10 | Select context by user, project, work type and time, with priority and version management. | Do not indiscriminately apply experience from another project. Recover the relevant line of work when the user returns to an earlier direction, distinguishing old assumptions from currently established facts. Git-tree behavior is an analogy; an actual Git implementation is undecided. |
| P11 | Judge which consequential decisions require user confirmation in context. | Evaluate combinations of individually small decisions that together produce a consequential change. Preserve confirmation, delegated authority and settled choices. Learned preferences do not create new permissions. |
| P12 | Learn quietly from real work and allow relevant changes during ongoing tasks. | Treat relevant experiences as learning candidates without a “learn this” command. Track applicability and distinguish personal preference, project constraints and one-off circumstances when testing changes. |
| P13 | Record the progress of background learning itself and resume after interruption. | Distinguish observed experience, open learning questions, applied guides and unconfirmed outcomes. Recheck intervening context changes and test duplicate application and mistaken completion on recovery. Do not store private hidden reasoning. |
| P14 | Manage files, folders and versions contextually. | Judge when to edit an existing file, retain a new version or organize related folders according to the work and existing practices. This does not grant authority to change unrelated files. |
| P15 | Discover and interpret external file changes on later relevant work. | Do not continuously watch every folder. Compare permitted prior state records with the current file. Without comparable prior content, do not claim to know the detailed difference. Do not infer authorship or intent without separate grounds. |
| P16 | Let one team operate autonomously while reducing the person's routing and team-management burden. | Agents can discover needed work and coordinate through OpenSocrates. Consequential decisions return to the request conversation. Make interruptions and host limitations explicit. |

## Settled learning direction and open mechanism

The settled direction is personal learning, adjustment through actual work, quiet ordinary updates, applicability to relevant ongoing tasks, and tracking the learning process. Corrections and review arising in agent collaboration can become learning questions inside that person's OpenSocrates. Treating something as an “issue” here means an internal learning problem, not creating a GitHub issue.

RL currently describes the intended feedback loop. Reward signals, learning units, guide representation and adoption/hold/retirement criteria require specification and experiments. Do not imply that a particular reinforcement-learning algorithm, model-weight update or improvement of internal token alignment has been selected or demonstrated. Absence of user edits alone does not establish satisfaction or success.

Do not turn quiet learning into repeated per-update approval. At the same time, the open decisions below must define how mistaken learning can be recognized and corrected and how scope and versions are handled. This document does not elevate unadopted proposals into confirmed user requirements.

## Data and authority boundaries

Current [AGENTS.md](../../AGENTS.md) prohibits telemetry, credential collection, raw prompts/transcripts, screenshot retention, workspace-content retention and hidden-reasoning capture. [CONTRIBUTING.md](../../CONTRIBUTING.md) also contains related privacy restrictions. This plan does not amend those policies.

Work that can be designed under current policy includes scoped task/guide identifiers, versions, state, permitted source references and minimal file-state fingerprints. Personal guides must not become a store of copied conversations or documents. Specify authority to send project content to another app, the personal state retained, and deletion scope.

Detailed file comparison requires available prior versions or equivalent change material. A proposal for OpenSocrates to retain new source copies or workspace snapshots for learning can conflict with current policy. Before implementing that capability, obtain an explicit product-owner policy decision and separate review. Until then, distinguish change detection from available detailed comparison; add neither blanket file monitoring nor raw-content retention.

## Design decisions before implementation

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
