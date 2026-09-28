# Role-isolated orchestration: proposed comparison

Status: **design only; not an executable or frozen outcome protocol**.
Prepared on 2026-09-28 for the user's request to design testing after the
role-isolated implementation. No outcome calls are authorized by this document.
The primary owns fixture preparation, qualification, observation and synthesis.

## Decision and verified starting point

Test whether the new workflow improves delivered work, and whether any observed
benefit extends beyond assigning more independent agents to the same problem.
Measure final correctness, defects found and repaired, regressions, continuity,
and the entire workflow's exposed usage. A reviewer's approval is an observation,
not the answer key.

The inspected local, remote feature-branch and Draft PR95 head is
`d0156a86cfd4dc197554f1be0261c258cec7da2e`. Remote main is
`5a2ff3c312e92aa8a44d0905465674d9a4e4f645`.
[Exact-head CI 36343827304](https://github.com/ParkerHwang/OpenSocrates/actions/runs/36343827304)
and the displayed governance checks succeeded. This is existing CI evidence,
not checks newly executed for this design. PR95 remains Draft.

The current qualified package SHA-256 recorded by the
[platform follow-up](../ci-repair-v1/README.md) is
`01c5c1852a4c6293d835a5cf3b73fee22c6eef3bb62a9ecc2f1e1cd2651cf9c9`;
its product source is `6eb8d3774f3a9032f580359b38b8bf11208f70d3`.
Rehash the actual execution artifact before freezing new calls. Do not assign
the older live outcomes to these later package bytes.

The prior [28-call qualification](../v1/REPORT.md) established bounded workflow
behavior on `gpt-6-astra/max`, with retained failures. It was not a comparative
quality study. Its deliberately signposted defective seed does not estimate
blinded defect detection. The current 43 orchestration regressions, 32 scanner
mutation cases and 176 packaged schema/guide matches are functional evidence to
reuse where unchanged. They are not new observations in this comparison.

The earlier [36-episode analysis](../../fullstack-consulting/analysis-v1/REPORT.md)
remains immutable and separate. It found concrete calculation, UI and evaluator
defects without a consistent net v1.5 advantage. New tasks and new orchestration
must not be pooled with that cohort or compared as if only one variable changed.

## Questions, comparisons and permitted conclusions

| Question | Proposed comparison | What remains insufficient |
| --- | --- | --- |
| Does the new complete workflow help users on these tasks? | D versus A and B | One episode per task/tuple is not a general superiority estimate. |
| Does OpenSocrates add value beyond role separation? | D versus C | This isolates the added guidance/content layer within the matched workflow, not every component of OpenSocrates. |
| What does generic role separation contribute? | C versus A | Extra calls/context and task decomposition are part of this treatment, not free improvements. |
| Does a reviewer discover real defects? | Locked first review versus external checks of the exact first candidate | Only observed, independently assessable defects enter recall/false-positive denominators. |
| Does repair improve the artifact? | Every first candidate and repaired version, checked after the episode | Repair may introduce a different defect; final pass does not erase the first failure. |
| Does scoped memory preserve valid intent? | Separate memory/maintained-note continuation lane | No account-side isolation or broad memory-effect claim. |

Reconsider the design if an oracle cannot distinguish an allowed alternative
from a defect, if common controls cannot run under the same permissions, or if
the current adapter cannot express a task without changing its semantics.
Hold only the dependent comparison; do not manufacture a result or broaden a
missing measurement into a universal release blocker.

## Recommended arms

| ID | Environment | Workflow | Purpose |
| --- | --- | --- | --- |
| A | Vanilla Codex | One competent author context; self-checks allowed | Practical single-author baseline |
| B | Pre-orchestration v1.5 candidate | One competent author context with that package's relevant complete guidance | Direct comparison with the product before this revision |
| C | Vanilla with role separation | Same two-unit graph, fresh maker/reviewer/verifier contexts and repair machinery as D; competent generic role instructions | Control for decomposition, independent contexts and added work |
| D | Current v1.5 candidate | Actual `orchestrate` with complete selected domain/role/specialist guidance | New product treatment |

B uses product commit `035fafcd208bf9577ca55ff5e42a93df4ca608ea` and the archived
package `52994553d51e8fd65285165d39ea004be819e56da8dab99c22968591a165dc76`.
There is no diff in `src`, `content`, `schemas/source`, `schemas/v1` or
`plugin-src` between that product commit and the pre-implementation handoff
`edab8f8d5c8434a705e706422ce5e8d6dc540e32`. Reverify the execution copy at freeze.

Released v1.4 stays historical context in this revision-focused design. A fresh
v1.4 arm would be another 12 episodes; it is **not silently added**. Historical
v1.4 scores cannot serve as a matched control for these new tasks. This choice
prioritizes the user's immediate question about the completed modification.

C is an evaluation-only control and must be visibly labeled as such. Use an
auditable guidance-provider substitution around the same coordinator mechanics,
without editing the production candidate. Preserve graph/ownership, schemas,
artifact binding, public checks, check order, repair policy and failure handling.
Replace the OpenSocrates domain/role/specialist text with competent generic
instructions. Freeze the substitution diff and full guide hashes; reject a
control that changes acceptance mechanics or accidentally includes product text.
This is not an unmodified installed vanilla product.

All arms receive identical relevant facts, requirements, approved tools, source
bytes, public examples and artifact contracts. A/B receive the complete task and
both units' relevant facts, can reason and self-check freely, and are not told to
avoid modularity, review or testing. Use a common candidate-return interface and
operator-owned materializer with the same tool permissions. Explicitly label
this as a controlled artifact-production comparison, not a claim about every
ordinary writable-workspace Codex experience. Verify that every reference
solution fits the interface; do not invent extra model-output quotas.

Package guidance is explicitly delivered from disposable package copies. Hooks,
native memories and unrelated plugins are disabled uniformly. No active-plugin
replacement occurs. Record this delivery condition; it is not proof of automatic
hook activation. D's own orchestrator is the tested treatment, not an external
primary agent repairing results until they look good.

## Models, episodes and execution scale

Retain the six tuples from the user's previous matrix, without substitution:

1. `gpt-6-sol/high`
2. `gpt-6-luna/max`
3. `gpt-6-luna/high`
4. `gpt-5.6-luna/max`
5. `gpt-5.6-luna/high`
6. `gpt-6-astra/xhigh`

The main comparison is four arms × six tuples × two tasks = **48 episodes**.
Every maker, reviewer, verifier and repair inside an episode uses its exact
tuple. The Astra/max implementation qualification does not establish Astra/xhigh
or any other tuple's current access. The first planned outcome is the actual
access observation; unavailable cells stay unavailable. No catalog-only proof,
paid credentials, reset credits or fallback models.

Each task has two units in C/D. A successful no-repair A/B episode uses one
author process; a successful no-repair C/D episode uses six role processes.
The main design therefore has a **nominal 168 role invocations** before repairs
and failed attempts, not 48 model calls. Early blocked dependencies can reduce
that number; repairs and failures can increase it. The separate eight-case
continuation lane below adds a nominal 24, giving 192 across both lanes.
External deterministic qualification uses no model calls. No additional AI judge
matrix or human recruitment is a prerequisite.

Fast is off. Experimenter-imposed model time, token, tool, output and internal
retry budgets remain null. The current product has real limits: `repair_limit`
0–2, eight units, 16 files per unit, 65,536 bytes per candidate file, a 262,144-byte
candidate envelope, a 262,144-byte request and a 524,288-byte assignment. Checks
also have an existing 1 MiB-per-stream output guard. These are native product
contracts, not a promise of unlimited artifact sizes. Set C/D `repair_limit: 2`,
report every consumed attempt, and do not bypass or silently enlarge these
contracts for a favorable result. Schema character and encoded-byte bounds both
apply. A capability/size rejection is a product-boundary observation, not a
semantic quality failure attributed to the model.

After the common harness is qualified, dispatch independent available episodes
concurrently at the greatest supported host/account concurrency, with atomic
ownership and no duplicates. Do not restore the former arbitrary three-worker
queue. Freeze the dispatch policy and record actual overlaps, resource pressure
and reconnects. Dependent roles within the current product remain sequential.
Run artifact performance checks serially after generation has ended. No elapsed
time alone authorizes cancellation or a retry.

## Task S: IncidentOps, a difficult full-stack change

Use a new synthetic incident-response product, not the earlier inventory/order
project. Supply a competent, tested brownfield starter using Python 3.12 and
browser JavaScript, with deterministic clock and transport adapters. This fixed
stack tests code reuse and contract changes within the supported execution
boundary. It is explicitly **not** a repeat of the earlier language-free
greenfield experiment. A language-free build would require another protocol and
qualified per-language check adapters; do not pretend a fixed-stack task measures
language selection.

The product accepts event webhooks, maintains tenant-scoped incidents and
escalation schedules, and exposes an operator dashboard. Outbound notifications
go only to a fake outbox. No real accounts, messages or production systems.
Complexity comes from interacting invariants rather than a target line count.

Two units:

- **S-design:** a material API/state/ownership change contract, including current
  callers, persisted versus derived state, migration/compatibility intent and
  executable contract examples. Produce `design.json` and `design.md`.
- **S-implementation:** modify the existing backend and frontend against that
  contract, preserve useful helpers, and supply implementation/tests/runbook.
  One owner controls the shared schema, server, UI and test files in this bounded
  unit; it cannot silently revise the accepted design. Freeze exact paths before
  calls, within the existing file/byte contract.

Required scenarios include tenant-scoped idempotency and different-payload
conflicts; duplicate/out-of-order events; acknowledge/resolve/reopen transitions;
effective-dated escalation policies whose later value is lower; overlapping
on-call handovers; cancellation of obsolete outbox work; derived dashboard counts;
read-only viewer permissions; filters that refresh the actual result set; and
form controls that do not accidentally submit/reload. Public requirements state
business behavior, not the implementation trick or hidden edge-case answers.

After production, mechanically stage exact returned bytes into disposable copies
of the same starter. Check API responses and persisted state, concurrent effect
uniqueness, restart continuity, and browser actions tied to actual network results
and rendered records. Await the relevant rendered state before inspecting absence,
counts or mobile width. Distinguish safe rejection from an unauthorized write.

The native read-only checks cover parsable source, public schemas and pure or
in-memory domain operations. HTTP servers, writable databases, browser execution
and performance belong to a separately authorized **external qualification
harness**, applied identically to every locked arm. That harness permits writes
only in disposable copies and loopback networking only. Freeze its sandbox and
commands before outcome calls. A working external server test does not establish
that `orchestrate` itself supports network or writable scratch checks.

Freeze native unit obligations and final integration obligations separately.
Native qualification requires actual native-check coverage of its bounded
obligations. Browser/restart/server obligations remain pending for the external
integration stage after `integration_pending`; parsing is not their substitute.
Overall task acceptance still requires those external obligations. Do not put an
impossible browser execution into a read-only native unit and then count the
resulting capability block as a model's inability to implement a frontend.

Performance uses a request-count workload at concurrency 1/8/32 and the same
Python/browser/runtime versions. At each concurrency, use separate fresh seeded
databases for 1,000 incident-list reads and 1,000 unique event-ingestion writes;
perform 100 warm-up requests for that operation before its measured batch. This
is 6,000 measured requests and 600 separately recorded warm-ups per eligible
artifact. Seed the same 10,000 synthetic incidents through the approved API;
keep seeding, warm-up and measurement counts distinct. Preserve the starter's
fixed SQLite WAL/FULL durability contract. Freeze exact bodies, key distributions,
seeding checks and timing boundaries before model calls. Measure every scheduled,
completed and failed request, throughput, p50/p95/p99, RSS/CPU where observable,
and post-run state.
Transport failures remain failures and are not removed from denominators. Do not
rank a fast incorrect artifact above a correct one, or present survivor-only
throughput as an all-arm result. Any diagnostic workload is separately versioned.

## Task O: service-network analysis and consulting

Use a new synthetic regional repair/service operation with work orders, event
corrections, capacity calendars, dated supplier rates, SLA policies and shared
facility costs. Include zero-charge but nonempty warranty jobs, missing values
distinct from zero, cancellations, late corrections, and policy changes that
decrease a numeric value. Reconcile event grain before aggregation.

Source material is a frozen data room with provenance. Public contextual data,
if used, is archived with URL/date/hash and available identically to every arm;
it does not establish demand for a synthetic company. Collection means reading
and reconciling this controlled source room. Unrestricted live web research is
outside the adapter and is not claimed from this result.

Two units:

- **O-analysis:** reusable calculation code, normalized/metric JSON and a source
  register. Derive backlog, eligible SLA attainment, capacity, service credits
  and costs at explicit grain/key/unit/date/rounding rules. Compare facility
  combinations with shared costs and scoped sensitivity changes.
- **O-document:** a decision memo, recommendation comparison, operating plan and
  risk/assumption register in Markdown, all bound to qualified metric identifiers
  and source references. State decision criteria and uncertainty; a different
  supported recommendation is not automatically wrong.

Classify O-analysis as `software/production` because it authors an executable
analysis program; its numeric/data requirements remain explicit obligations.
Classify O-document as `document/production`. S-design and S-implementation are
`software/design` and `software/production`. All four are judgment work. Do not
ask a document/data role to silently switch into program authoring. This keeps
the two-unit call count faithful to the real domain/role contract.

Verify authoritative revision/date selection, numerator and denominator rules,
per-record calculations before composition, scenario scope, and every material
number in the documents. Independently compute the answer key rather than copying
the subject's formula into a verification script. Validate both numeric and
narrative bindings; polished prose cannot compensate for wrong arithmetic.

PDF/XLSX/PPTX authoring and visual layout are outside the current native adapter.
Optional common deterministic rendering may make a review copy, but its success
is renderer evidence, not the model's native office-authoring score. Markdown
is the primary document artifact for this comparison. Do not encode binary
artifacts as text to evade the declared boundary.

## Separate continuity and bilingual lane

Use two tuples (`gpt-6-sol/high`, `gpt-6-luna/high`) × EN/KO × two equivalent
context conditions = **eight one-unit continuation episodes**. Hold the tuple
fixed across every role. All start from the same known-correct starter and a
preauthored bounded handoff, not whichever main-cohort artifact happened to pass.

The conditions are existing enrolled disposable project memory versus disabled
memory with a competent maintained note containing the same accepted intent and
relevant facts. Keep this lane separate from the 48 memory-off main episodes.
No uninformed control is presented as evidence of a memory advantage.

Before the fresh continuation, replay a frozen source correction and an authorized
scoped deletion. Use the existing memory API to perform and verify the deletion:
`orchestrate` does not enroll, capture or delete memory itself. Retain an unrelated
valid accepted constraint, remove the requested record only, and inspect the
actual persisted state and next projection. Proposed preferences must not become
accepted intent; accepted lifecycle must not become independent review evidence.
Source-dependent accepted intent can survive as explicitly stale; do not expect
all stale records to disappear automatically. A changed/deleted frozen record
invalidates reuse rather than resurrecting a cache entry.

The fresh role task applies the corrected source, respects valid retained intent,
and produces an EN/KO handoff. Include a settled decision it must not reopen and
a side question answerable from the provided public facts. A necessary unresolved
business choice should be marked pending rather than fabricated. Assess artifacts,
all available public messages and state separately. If the adapter did not retain
earlier public messages, clarification timing is unassessable; a final message
alone cannot establish that no question was asked earlier.

The adapter is not an interactive multi-turn chat controller. This lane measures
fresh-context continuation and handoff behavior, not real-time interruption or
human question/answer turn taking. Existing valid broader usability evidence may
be cited with its original conditions, but cannot be relabeled as this adapter's
new end-to-end conversational proof.

## Independent checking and isolation

Before outcomes, author public smoke checks, external answer keys, known-good
solutions and deliberately wrong control implementations. Mutations cover latest
date versus maximum value, product-of-sums versus sum-of-products, missing versus
zero, tenant keys, event ordering, form-submit side effects and misleading UI
readiness. Include allowed alternative implementations. Oracle acceptance must
not depend on source formatting or unspecified rounding precision. These are
mechanical harness checks, not additional model-quality samples.

Keep external answer keys and their expected results outside every subject's
readable filesystem and network surfaces. The native runtime stages each unit's
`source_ids` for makers and reviewers as well as checks; an oracle placed there
is **public**, not hidden. Internal checks intentionally remain public and equal
across arms. External grading feedback must not enter maker repairs.

Use fresh per-episode profiles, fresh per-role contexts and scoped workspaces.
Verify ephemeral/config/history/memory/plugin settings, exact model/effort and
fast-off arguments. Fresh context and a read-only sandbox do not themselves block
unrelated file reads. The native capability probe establishes read/write behavior,
not hidden-oracle isolation. Qualify an evaluation-only isolation wrapper with
synthetic canaries for sibling arms, old outcomes, host memory and private grading
files. Use no real secrets in canaries. Keep the same wrapper in all arms and
freeze its code, permissions, client path and actual executable hashes.

If filesystem separation cannot be enforced, do not claim hidden or blinded
grading. Hold that dependent comparison until the oracle can be kept inaccessible;
continue independent deterministic preparation. Account-side memory isolation,
backend model echo and billing can remain explicitly unproven and do not prevent
a bounded practically usable comparison. Do not change global memory/settings to
manufacture isolation.

Lock each candidate and first-pass review before showing its corresponding
deterministic receipts to an execution verifier. The verifier does not see the
review verdict. Changed versions get fresh review and execution verification.
Internal findings may drive only the designated same-tuple maker's authorized
repair. Save all versions and public accepted findings, including critical and
unknown obligations. Invalid structured responses, unavailable bodies and null
usage remain visible. No integrator patching, external coaching, silent rerun,
cross-model answers or stronger-model help inside Luna episodes.

The external evaluator qualifies locked copies after the episode. Review all
first versions as well as final versions to measure detection/repair, without
leaking results back. The primary's semantic inspection is provisional and
unblinded; human scores stay unavailable. Do not automatically commission another
model-judge matrix. An optional future blind packet review needs its own explicit
protocol and count and is not a completion prerequisite here.

## Metrics and observation contract

| Measure | Unit and source | Interpretation rule |
| --- | --- | --- |
| Required task correctness | Passed/failed/unknown requirement groups; external receipts | Report task/model/arm denominators separately; no blended overall percentage. |
| First versus final correctness | Candidate digests and version-specific receipts | Separate initial error, successful repair, regression and blocked dependency. |
| Review detection and false acceptance | Independently reproduced findings tied to first candidate | Match by requirement/behavior, not wording; exclude unassessable truth from rate denominators. |
| False positives | Findings refuted by the contract and independent reproduction | Keep rubric defects separate from model-review mistakes. |
| Repair behavior | Calls, actionable findings, changed-byte closure and new defects | Count every attempt, including invalid JSON/binding failures. |
| Reuse and structure | Contract/caller/state ownership evidence and change impact | Prefer demonstrated reuse/localized change; no points for abstract functional-programming vocabulary or file count. |
| Document reliability | Metric/source bindings and supported recommendations | Check exact material claims; no preference for a predefined recommendation. |
| Memory operations | Before/after records, API receipts and role projection | Emitted packs and self-reports alone are insufficient. |
| Resources | Per-call and whole-episode exposed usage, wall time, error counts | Compare resources beside correctness; never rank a failed cheap outcome as efficient. |
| Artifact performance | Frozen serial workload plus post-run invariants | Separate generation speed, server speed and semantic correctness. |

Observe role start/end, process identity, candidate/version transitions, check
status, repair causes and exposed error-event counts. The native adapter drops raw
event bodies, prompts, reasoning, stderr and tool-output dumps. Do not add raw
logging to recover them. Tool-action counts, question timing or public-message
analysis must be null/unassessable unless a privacy-safe, explicitly frozen
measurement path genuinely exposes them. This is a known observation limitation
relative to the previous cohort, not permission to reconstruct private traces.

Retain `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`,
`output_tokens`, `reasoning_output_tokens`, missingness, timestamps and failures
at call and episode levels. Cached input and reasoning output are subsets and
must not be added twice. Noncached input is derived only when both needed values
exist. Separate generation, workflow review/verification, repair, native checks,
external qualification and scheduler wait time. All are costs of delivered work
where applicable; none is independently verified billing. Backend retries/attempts
stay null when only aggregate reconnect/error events are exposed.

One episode per cell supports concrete examples, ties, failures and hypotheses.
Do not invent significance, numerical noninferiority margins, power estimates or
default model/profile promotion. Do not rerun selectively until favorable. Any
diagnosed product/harness repair receives a new versioned cohort or diagnostic
record; original outcomes remain unchanged.

## Preparation, stop conditions and completion

Before the first outcome call, prepare and commit a separate executable protocol
with task/source transitions, all owned paths and graphs, positive/negative oracle
controls, arm delivery and guide hashes, package/client/model identities, frozen
assignment order, exact external commands and permissions, resource fields,
failure policy, dispatch ownership and export allowlist. `design.json` here lists
the proposed cells but intentionally has no executable assignments or frozen
fixture hashes. Never call a draft fixture or absent launcher executable evidence.

Reuse existing functional/package evidence where bytes and scope match. Rerun
only checks affected by fixture/harness changes or new findings. New runtime or
package changes need the applicable CONTRIBUTING source/native gates and exact
pushed-head CI, without replacing the active installation. Do not edit the
user-owned `.codex/`, monitor state, frozen earlier results or protocols.

Stop or isolate only affected work for unauthorized filesystem/network access,
credential exposure, changed frozen inputs, loss of candidate identity, an invalid
oracle, client incompatibility or an actual user cancellation. Lack of public
events alone is not a stall. Missing call receipts require PID/start/executable
verification, not an automatic restart. Preserve partial state and usage.

Once all available planned cells are terminal and their artifacts qualified,
finish the report, exact-identity evidence and Draft PR/issue handoff. Do not expand
the matrix or repeat passed gates. No merge, tag, publish, deploy, real-project
enrollment, destructive host test or global installation/settings change follows
from this plan.

Public improvement-cycle record:

- `plan_objective_measure`: verified implementation/CI and prior failures provide
  the baseline; final correctness, review/repair behavior and total usage are the
  proposed measures. Benefit is **unverified**.
- `do_scope`: **not started**. Proposed exposure is 48 main episodes plus eight
  separately reported continuation episodes, on disposable local resources only.
- `check_rule`: freeze inputs and independent checks before calls; compare matched
  task/tuple outcomes; preserve failures, missingness and the stop conditions above.
- `act_standardize_decision`: **hold** any benefit/default-profile claim pending
  new evidence. Retain useful changes with their measured boundaries; diagnose a
  specific failure before any new iteration. No favorable-signal-only expansion.

The next action is fixture/oracle/control/isolation preparation against these
verified source contracts. Model execution follows a separately frozen protocol,
not this draft. The design itself is complete without running the experiment.
