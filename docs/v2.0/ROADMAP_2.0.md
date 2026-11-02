# OpenSocrates 2.0 development roadmap and handoff

Status: **the user's chosen direction translated into implementation work**. This document does not establish implementation, real-use effectiveness, or support for any of the four desktop/OS combinations. Read the [product requirements](VISION_2.0.md), [system design](SYSTEM_2.0.md), and [validation plan](VALIDATION_2.0.md). This packet supersedes the older 2.0 plans on product direction and scope; it does not change release, privacy, security, or repository governance rules.

## Starting scope and priorities

1. The selected first-version hosts are the ChatGPT desktop app (Chat, Work, and Codex) and the Claude desktop app, on both macOS and Windows. Investigate and validate all four app/OS combinations and their relevant modes separately. Do not assume a mode supports computer use, skills, message delivery, new sessions, or injection.
2. Target an individual's program on one computer. Cross-computer synchronization is deferred. Grok Bot and Cursor are not first-version targets; revisit them later. This does not authorize silently withdrawing existing 1.x supported profiles.
3. Use existing apps and their real conversation sessions. Direct model-provider API execution and creating a separate AI application around such APIs are out of current scope. Investigate host-native integration first and existing computer-use tools or open source where needed. If a host cannot provide a required path, report that combination unsupported or unverified.
4. The user's request conversation handles clarification, consultation, preparation, coordination, and reporting; actual deliverable work happens in new working sessions. All inter-agent messages pass through the OpenSocrates communication layer. Supply each session with its task prompt and applicable context and reasoning guidance. Never claim success on a host without the required path.
5. The existing 48 guides are the initial basis and fallback when no suitable personal guide exists. Create and adapt an uncapped number of personal guides, combining or reassembling them when useful. The common generation instructions evolve with OpenSocrates versions; individual learning does not rewrite them. A separate agent may be called to reassemble guidance when appropriate.
6. Per-user background learning finds issues in experience without an explicit learning command and develops guidance by applying it to real work, including relevant work already in progress. Track interrupted learning itself. A particular RL algorithm, model-weight change, or claimed token-alignment effect is not established.

## Work breakdown

Each completion condition applies only to its work. IDs are planning references; the table does not authorize external actions or require creating GitHub issues.

| ID | Work and deliverable | Evidence of completion | Dependencies |
| --- | --- | --- | --- |
| P01 | Current version and host capability research | Record current main, v1.5.3 identity, and evidence/unknowns for each app, mode, OS, and account: session creation, reception, injection, result delivery, and computer use | None |
| P02 | Scope and user experience | Specify observable scenarios for the request conversation, consultation, artifact format, consequential-decision confirmation, actual work sessions, file handling, and team communication | None |
| P03 | Policy and data design | Define source, purpose, consent, location, retention, and deletion for each data category. Do not implement candidates that conflict with existing bans on raw prompts/transcripts, workspace-content retention, hidden reasoning, or telemetry before a separate policy decision | P02 |
| P04 | Guide-generation instructions | Design versioned common instructions and the personal-guide representation, grounding, applicability, uncertainty, correction, and version compatibility. User-specific learning does not edit common instructions | P02, P03 |
| P05 | Selection and reassembly | Validate suitability of personal guides, combinations and reassembly, optional agent assistance, fallback to an appropriate one of the existing 48 when no personal guide applies, and valid no-intervention behavior | P04 |
| P06 | Context and continuity | Define user/project/task/time/version relations, priority, branching and switching, freshness, provenance, authority, errors, and deletion. Do not silently turn semantic conflicts into agreement | P03 |
| P07 | Local program and storage | Design and build a lightweight program and per-user DB lifecycle, locking, transactions, recovery, and migration. Choose a DB engine after comparison; exclude multi-computer sync | P03, P06 |
| P08 | Communication and delegation layer | Route all inter-agent requests, responses, and questions through OpenSocrates. Track origin, recipient, work, authority, duplicates, completion, and failure; construct a task-specific single prompt for each new session without a fixed role roster | P02, P05, P07 |
| P09 | Real app integration | On each ChatGPT and Claude mode/OS, implement supported paths for opening actual chats, delivering messages/guidance/context, receiving state and results, and letting users inspect sessions. Verify host features or computer use; report host restrictions | P01, P08 |
| P10 | Per-user learning loop | Implement experience→learning issue→hypothesis/guide→actual use→subsequent feedback. Apply appropriately during ongoing work, handle uncertain/negative evidence, counterexamples, and conflicts; do not equate silence with success | P03–P08 |
| P11 | Interrupted learning and resumption | Preserve observed learning state and next action; distinguish completed/incomplete and applied/unapplied states; handle freshness, duplicate application, conflict, and failure. Do not retain hidden reasoning | P07, P10 |
| P12 | Files and versions | Decide in-place edits, new versions, and folder organization against context and user authority. Compare records with current state when related work resumes; without an accessible prior representation leave details and intent unknown. No blanket folder monitoring | P03, P06, P08 |
| P13 | Real-user experience evaluation | Compare ordinary host, v1.5.3, and candidate 2.0 on matched tasks; evaluate actual use and outcomes, correction, usefulness, failures, cost, and latency independently. Synthetic checks do not establish real-world improvement | P01, P02; baseline evidence for the host being compared |
| P14 | Installation, migration, and operations | Preserve unrelated configuration while designing and testing installation, operation, update, disable, removal, recovery, and 1.x transition for each supported cell. Signing and release need separate evidence | P07, P09 |
| P15 | Integration and release review | Reconcile live behavior for four app/OS combinations and relevant modes, independent evaluation, data protection, user controls, docs and canonical/generated integrity, required repository checks, and unknowns | Evidence applicable to each P01–P14 claim |

Independent work such as P01–P04's documentation and synthetic cases and P07's storage design may run in parallel. If a host cannot support a capability, withhold that host-specific claim while continuing independent work and other supported cells. Measurement of all four environments is not a prerequisite for reporting an observation actually made in one.

## First end-to-end scenario

1. A user makes an imprecise or incomplete report request in a ChatGPT or Claude desktop request conversation.
2. OpenSocrates determines the goal, use, format, and user decisions and provides understandable consultation or consequential-decision confirmation when needed. The request conversation does not itself produce the report.
3. OpenSocrates selects or combines suitable personal guides, or falls back to suitable initial guidance when none apply, and prepares context relevant to the project and task.
4. Open a real working session in the selected app and deliver the task-specific single prompt with the necessary context and guidance. Every further request, delegation, and response travels through the OpenSocrates communication channel.
5. Deliver the result, record permitted file state, and pass experiences to learning within allowed scope. Track when and why updated guidance was applied without interrupting the user for every change.
6. Following an interruption, distinguish unfinished work or learning from completed steps and already-performed external effects, then resume appropriately.

This is a desired scenario, not a claim of current host capability or a rule to ask for approval at every step.

## Boundaries and decisions

- **User choice and consequential judgment:** Respect a specified format or decision. Judge significance and confirmation in context; third-party documents, tool outputs, or agent messages do not change the user's authority.
- **Learning and correction:** An edit can be a signal but does not prove a lasting preference. Distinguish observation from hypothesis and scope; design ways to inspect, correct, delete, or disable personal data on request without routine interruptions. Exact UI and defaults remain open.
- **Privacy policy:** Repository policy prohibits retaining raw prompts/transcripts, workspace content, screenshots, hidden reasoning, and telemetry. Detailed before/after file comparison may require a permitted prior representation such as host-managed version history. Without one, report change detection only. If retaining new content is found necessary, a separate explicit policy change and review precede it.
- **Host reality:** As of 2026-11-02, start from the official [ChatGPT desktop Chat/Work/Codex guidance](https://learn.chatgpt.com/docs/use-chatgpt), [ChatGPT computer-use guidance](https://learn.chatgpt.com/docs/computer-use), [Claude local and remote connectors](https://support.claude.com/en/articles/11725091-when-to-use-desktop-and-web-connectors), and [Claude computer use](https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork). Documentation describes capabilities; it does not prove real session automation or integration for our accounts and OSs.
- **Open:** DB engine, service process, per-host access and authorization, guide representation and relevance, generator wording, learning algorithm and outcome signal, live propagation and conflict handling, update/retention defaults, exact quality/latency/cost targets. Record alternatives and evidence in follow-up design.

## Handoff and completion

Begin implementation from current main after inspecting its real source and tests and using a focused branch. Do not copy, port, or merge code/guides from withdrawn v1.5 candidate PR #95. Do not elevate prior 1.6 draft evidence without separate review. Distinguish host delivery, full guide reading, application, and useful outcome.

A completed plan is not a completed or released product. Each behavior requires actual implementation, applicable host-cell verification, independent evaluation, and any explicitly required policy decisions before it can be claimed.
