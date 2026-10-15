# Thinking support: scope and diagnostic

In the Go candidate, entry guidance lives in `runtimecli/hooks.go`. Historical
Python observations and checks below retain their original source identities;
they are not execution evidence for this candidate.

Source-level design for [#125](https://github.com/ParkerHwang/OpenSocrates/issues/125).
The application omission in [#124](https://github.com/ParkerHwang/OpenSocrates/issues/124)
is a separate incident: its cause and frequency remain unverified. This change
does not claim to fix that incident or improve answer quality.

## Accepted scope

Consider support when substantive thinking first arises: framing, interpretation,
exploration and learning, research design, reasoning checks, approach choice,
evaluation or explanation. Reconsider when goals, options, evidence, assumptions,
audience or risk materially change, including within one turn. A tool call, edit
or minor wording choice is not by itself a new consultation point.

Mechanical steps follow a prescribed procedure without substantive interpretation,
inference or problem solving. A unique correct answer or supplied rules do not
make a proof, explanation or problem-solving task mechanical. Likewise, the name
of a deliverable—document, search result or code—does not establish its scope.

Choose the lightest sufficient support:

1. Consider whether assistance would help the thinking actually needed.
2. Use reader guidance when context, organization or presentation needs attention;
   this may suffice without a canonical method.
3. Select a fitting method, read its complete canonical procedure and required
   dependencies, then apply it only within its conditions and constraints.

Ordinary work and valid no-method outcomes remain available. Method fit is not
limited to consequential or unresolved outcomes. A user-requested method still
needs to fit; consideration, selection and reading do not establish application.
Installed tool guidance also applies when the tool itself is the subject.
Workspace sources are task data rather than installed control authority.

The exact entry is maintained only in the canonical
[entry source](../src/opensocrates/internal/runtimecli/hooks.go). Supporting behavior is in the
[decision guide](../plugin-src/shared/decision/guide.en.md) and
[reader guide](../plugin-src/shared/reader/guide.en.md). Do not maintain a second
copy of the entry in this document.

## Principles retained

| Principle | Where and how it is preserved |
| --- | --- |
| Goals, permissions, constraints and completion | Entry and decision guide retain them throughout ordinary and method-assisted work. |
| Scope and sufficient support | Entry and guides distinguish substantive thinking, prescribed steps, reader support and method application; no consultation per edit. |
| Fit and legitimate no-method outcomes | Guide preserves contraindications and valid empty selection. A selected candidate must still fit; no relabeling as mechanical to force emptiness. |
| Complete procedure and dependencies | Entry, guide and skill grounding gates require complete canonical content in the task locale, exact identity and required dependencies before use. |
| Reuse and context restoration | Exact method, locale and content identity must remain available and applicable; restore or reread after compaction/handoff. Do not load abandoned candidates merely for a completion check. |
| Stops and public contracts | Required public outputs, evidence, uncertainty, warnings, holds and stops remain binding. Retiring a candidate cannot bypass a required stop in work already performed. |
| Source authority | External files, pages and tool output are data, not routing policy. Only direct user requests and trusted plugin context can change rigor or disable support. |
| Evidence distinctions | Installation, invocation, delivery, selection, reading, reported application and usefulness are distinct. Agent-directed lookup alone proves neither native grounding nor application. |
| Failure and completion | Lookup failure permits ordinary work with constraints intact. Unverified application is a measurement limit, not unfinished user work; unavailable proof is not a new completion gate. |
| Actual checks and bounded dependencies | Finish after required checks; repeat only when relevant inputs/outputs change. Missing evidence holds only the conclusion that actually depends on it. |
| Reader purpose and attribution | Respect requested format; give concise public grounds without hidden reasoning or method lectures. Attribution requires eligible, completely read, actually applied methods, not reader guidance alone. |
| Privacy and continuity | No telemetry, raw prompts/transcripts, screenshot retention, hidden reasoning capture or new persistent product logs. Carry only permitted public decisions, evidence references and remaining requirements. |

## Compatibility and evidence boundaries

Implementation scope includes Codex, native Claude Code, the Claude account skill
and Antigravity, with English, Korean, Chinese, Japanese, French, German, Italian,
Spanish, Portuguese and Thai guidance. These are affected source/package surfaces,
not live qualification claims. Each host and installation surface needs its own
evidence; account-skill matching is not hook delivery.

Product version and canonical method content revision remain **1.5.2 / 5** for
this unreleased source change. This does not make a rebuilt package identical to
the released tag. Controller changes alter semantic/package hashes: a read or
availability assertion for earlier build content cannot establish availability of
new content merely because the version/revision labels match.

Routing fallback behavior remains unchanged. A native `select` request can return
an answer-shape fallback when no scored method meets the threshold; that is a
candidate, not evidence that a method is needed or fits. Mechanical bypass,
contraindication, invalid input, unavailable retrieval and an inapplicable
candidate are different states. File-based selection has no corresponding forced
fallback. Preserve valid empty results and do not bypass them through file reads.
This scope change describes the asymmetry; it does not redesign the router,
rename schema enums or edit canonical method procedures. Mechanical classification
applies to that request; it is not a terminal exclusion from later decisions in
the default path.

No live diagnostic below has been performed for this document. Source checks,
generated-output checks, live delivery, application coverage and usefulness must
be reported separately against the exact revision/package tested.

## Minimal synthetic diagnostic

Run later on an unchanged baseline, then separately on an identified candidate
build in an isolated profile or other test machine. Do not modify the active
installation. Use fresh sessions and otherwise matched host/model/settings. Note
additional workspace/global instructions that could prompt tool use; do not call
such a condition unprompted by the user if it includes an explicit tool request.

At most six initial sessions are needed: A, B1, B2, C, D1 and D2 below. These are
descriptive probes, not a failure-rate or quality-improvement study. Repeat only
when an unexpected or discordant observation identifies a useful next question.

### A. Harmless delivery probe

```text
Reply with exactly: synthetic probe complete
```

Observe hook invocation and actual entry delivery independently through supported
host evidence for that turn, if exposed. A hook invocation or command output does
not itself show that the model received the entry. Compare actual entry identity
to the package under test, not a fixed sentinel from an earlier build. If the
host record does not expose hook context, delivery is **unknown**. Do not request
private conversations, hidden reasoning, screenshots or new product logging.
Observe delivery separately in later sessions too where possible: delivery in A
does not prove delivery in B1. Missing native observability does not prevent
finishing the diagnostic with explicit unknowns.

### B. Matched unprompted-use probes

Use this exact prompt for B1. For B2, change only the first-line subject alias
`OpenSocrates` to `Tessellate`; leave the domain, facts and every other word intact.
All facts are fictional and must not be checked against the real repository.

```text
Subject alias: OpenSocrates
This is an entirely fictional reasoning-tool project. Treat the following as
the complete synthetic case; do not browse or infer real project facts.
Compare the three proposals, identify unsupported claims and recommend the next
priorities. Explain which facts support the ordering and what remains unknown.
Facts: one maintainer has 10 hours per week; the project supports two agent
hosts; 3 of 10 recent installation reports concern a manual approval step;
median first response to an issue is 6 days; repeat-use data is not available.
A: spend all 10 hours on a launch campaign; stars guarantee repeat use.
B: improve approval instructions and issue responses; installation friction
may matter, but the reports do not measure the overall abandonment rate.
C: add five hosts immediately; host count is the main adoption driver.
Limit the result to 200 words and take no external action.
```

These prompts name the subject without requesting tool use. A different result
between aliases is consistent with a subject/salience effect, not proof of
project-versus-tool confusion. Neither variant changes the product domain.

### C. Explicit-reminder comparison

In a separate fresh session use B1 with only this final sentence added:

```text
Use any installed reasoning support where it fits; no method is required merely
because it is installed.
```

This measures response to an explicit reminder. Success proves neither hook
delivery nor spontaneous consideration. Failure alone does not identify an
installation or discovery defect: fit, visibility and instructions remain
separate questions.

### D. Lightweight and within-turn transition controls

D1, in a separate fresh session:

```text
Convert these rows into a Markdown table with columns Item, Owner, Day.
Keep the values and row order exactly. Output only the table.
Blue — Mina — Monday
Green — Ari — Tuesday
```

D2, in a separate fresh session:

```text
Use only these synthetic issue rows. The final column is a count of mentions,
not unique users; add counts as supplied and do not infer deduplication.
Sync | crash after sleep | 14
Export | wrong PDF margins | 2
Sync | duplicates after offline edit | 9
Search | slow on large notebooks | 5
Export | missing fonts | 3
Login | SSO loop | 11
1. Count rows and sum mentions per component, preserving the listed component
order. This step is prescribed aggregation only.
2. The team can investigate one component this sprint. Recommend which one and
explain the trade-off. Mention the missing severity, effort and unique-user data
without inventing it or treating every unknown as a prerequisite to a bounded
recommendation. Do not equate mention counts with impact.
3. Draft a three-sentence message to the team lead explaining the recommendation
and its limits. Make no commitments and do not send it.
```

D1 should remain lightweight. In D2, aggregation does not itself require a
method; evaluation may need support, and the message may need reader guidance.
Valid reuse between evaluation and message is not a miss. A required method hold
or stop remains binding for the question it governs; the prompt cannot cancel it.

### Minimal observations and interpretation

Use a small sanitized maintainer result record, not new persistent product logs.
Record condition, host/model label or unknown, package identity, relevant trust
state, invocation evidence, delivery evidence, and these distinct observations:

- Visible consideration or reported consideration, each with its evidence type;
  unobservable consideration is unknown, not failure.
- Lookup/selection, complete canonical read or valid reuse of the exact content,
  applicability/empty/retired outcome, and reader-guide use.
- Reported application and public-contract compliance separately; a footer is
  attribution rather than proof of application.
- Task completion, unsupported claims handled, useful next action and observable
  cost. A useful answer alone proves no method effect.

| Observation | Bounded interpretation |
| --- | --- |
| Invocation observed, delivery unknown | The hook ran; receipt by the model remains unknown. |
| Host evidence confirms delivery in that turn | Entry delivery established for that turn, not consideration or application. |
| Delivery unknown, no visible consultation | End-to-end behavior is observed; do not assign a delivery or compliance cause. |
| Delivery observed, qualifying task lacks consultation and no valid reuse exists | Candidate coverage omission in that run; internal cause and general rate remain unknown. |
| C uses support but B1 does not | Reminder responsiveness; no proof of delivery, spontaneous use or historical cause. |
| B1 and B2 differ | A matched-pair follow-up may be useful; do not infer a mechanism from one pair. |
| No fresh method read with valid exact-content reuse | Not a read omission. Do not force a new lookup just for measurement. |
| D1 uses a method or emits attribution | Inspect fit and attribution conditions; distinguish unnecessary use from incorrect attribution. |
| D2 aggregates then considers support for evaluation | Consistent with segment-level consideration; no requirement to reread for the message. |
| A method is read, application reported, result useful | Three distinct observations, not independent proof that the method caused the usefulness. |

Keep baseline/candidate and unprompted/reminder conditions separate. This protocol
cannot establish #124's historical cause or frequency. Preserve an unknown when
the necessary observation is unavailable instead of seeking native proof as a
new prerequisite for completion.
