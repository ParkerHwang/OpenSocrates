# Adaptive assistance and collaboration

Status: normative target design. Profiles and thresholds below are engineering
defaults for implementation and evaluation, not measured model improvements.

## Responsibility boundary

Use a small deterministic policy to recommend the amount of optional assistance.
The active agent interprets the task and supplies closed features; the policy
cannot certify those semantic judgments. The existing `decision` command alone
selects eligible canonical methods. Memory supplies attributed context, and the
agent completes the user's work with available tools.

The policy does not call a model, read a workspace, initialize memory, select a
different model, or control hidden reasoning. The default `decision` request and
ordinary hook contracts remain unchanged. Mechanical work bypasses the additional
policy call. Reuse the current policy until material inputs change.

## Inputs and precedence

The planned stateless `assistance` command accepts a strict JSON request with
schema `opensocrates.assistance.request/1.0.0`, request ID, locale, task features,
model context, and public completion state. No raw prompt or reasoning transcript
is required or retained. Source form is `python -m opensocrates assistance`;
installed launchers expose `assistance codex` with the same bounded JSON boundary.
This is a new explicit command, not a host-only `control` payload.

The request envelope has `schema`, UUID `request_id`, `locale` (`en` or `ko`),
`task`, `model_context`, and `profile_override` (null by default). `task` contains
only the eight task fields below. `model_context` has nullable `model`, `effort`,
and `client` strings plus `attribution`. `profile_override`, when present, contains
`profile_id`, positive `revision`, and attributed `authorization_basis`; a supplied
assertion never proves host consent. Candidate use must be explicitly configured
for the evaluation environment, not enabled by retrieved text.

Required closed inputs:

- `task_kind`: `mechanical` or `judgment`;
- `task_family`: `coding`, `planning`, `research`, `writing`, or `other`;
- `complexity`: `bounded` or `coupled`;
- `stakes`: `ordinary` or `consequential`;
- `uncertainty`: `resolved`, `bounded`, or `material`;
- `context_need`: `none`, `current_evidence`, or `continuity`;
- `completion`: `in_progress`, `checks_satisfied`, or `dependent_input_missing`;
- `material_change`: boolean; unchanged checks are not new evidence;
- `model_context`: model/effort/client identity or null, with `host_reported`,
  `operator_declared`, `agent_reported`, or `unknown` attribution;
- optional profile selection authorized by the operator for a declared scope.

Reject unknown fields, invalid enums/types, malformed identifiers, and invalid
profile revisions. Valid overlapping task features are resolved by the precedence
rules below, not rejected as contradictory. Missing model identity uses the
task-based fallback. Attribution never upgrades itself to native proof.
Permissions, mandatory checks, and canonical stop conditions take priority over
efficiency preferences. Consequential tasks receive adequate support regardless
of model price or the user's technical background.

## Policy result

Return schema `opensocrates.assistance.plan/1.0.0`, request ID, status,
`assistance_level`, `profile_id`/revision or null, `profile_evidence`,
`context_pack_budget_bytes`, `guidance_components`, closed `reason_codes`,
`next_action`, and limitations.
`next_action` is `continue`, `finish`, or `resolve_dependency`; it does not authorize
an external action. Return `application: unverified`. `status` is `ok`, `invalid_request`, or
`unavailable`; invalid/unavailable responses omit a plan and retain limitations.
`profile_evidence` is `task_default`, `candidate_evaluation`, or `validated_run`,
with a validation reference when applicable. Initial reason codes are
`mechanical`, `completed_unchanged`, `bounded_judgment`, `coupled_task`,
`consequential_stakes`, `material_uncertainty`, `matched_support_rule`,
`profile_fallback`, and `dependency_missing`. Keep request and response each
within 16 KiB UTF-8, reject unknown fields before action, and use the exit/status
convention in 03. No output field certifies the truth of caller-supplied features.
`finish` is conditional advice based on reported state; the executing agent must
check actual completion conditions and required evidence before ending the task. Do not return a fabricated
reasoning trace, selected methods, or an asserted improvement score.

| Level | Rule and optional delivery | Memory budget ceiling |
| --- | --- | --- |
| `none` | Mechanical task, or completed required checks with no material change; no extra procedure or retrieval | 0 |
| `light` | Bounded judgment without material uncertainty; supply the immediate outcome/constraint and a relevant evidence pointer only when needed | 8 KiB |
| `structured` | Coupled task, consequential stakes, material uncertainty, or a profile-matched observed failure needing structure; supply a bounded subgoal, relevant constraints/evidence needs, and a completion check | 24 KiB |

Only `context_need: continuity` permits memory retrieval; `none` and
`current_evidence` set the memory budget to zero. Current evidence is obtained
through authorized source tools when prior context is unnecessary. A budget is a
ceiling, never a quota; empty recall can be correct. The memory recall/assembly operation, after inspecting required content, returns
`budget_insufficient` and a bounded expansion/partition request when it cannot fit.
The stateless assistance command does not inspect content and never returns that
memory status. The
64 KiB hard pack limit in 03 still applies. Do not truncate required constraints,
mandatory evidence, or a canonical method to fit an optional budget.

Apply these rules in order; profile rules cannot override an earlier terminal rule:

1. Validate the closed request; invalid input produces no plan. Runtime/user
   permissions remain external prerequisites and are never inferred from features.
2. If `completion` is `dependent_input_missing`, set `next_action` to
   `resolve_dependency`. Continue level calculation below; an unrelated completed
   check cannot override that dependency. Independent authorized work can proceed.
3. Otherwise, `checks_satisfied` with `material_change: false` yields level `none`,
   zero memory budget, empty guidance, and conditional `finish`. Profiles cannot
   add work to this state. A false caller report does not prove actual completion.
4. All other completion states yield `continue`; `checks_satisfied` with a material
   change is treated as in progress because the previous result may be outdated.
5. Mechanical tasks yield level `none` regardless of other features; the action
   from step 2 or 4 remains. This skips reasoning guidance, not necessary consent,
   evidence, or execution checks for a mechanical but consequential operation.
6. Judgment tasks receive `structured` if coupled, consequential, or materially
   uncertain; otherwise they receive `light`. Apply a matched profile's permitted
   adjustment, then compute the budget from final level and context need.

A consequential judgment with a missing input therefore returns `structured` plus
`resolve_dependency`. A changed bounded judgment previously marked complete returns
`light` plus `continue`. Emit matching reason codes once in the declared enum order.
Test precedence edges and forged premature completion in A01/A02/A06.

## Model profiles

Profiles are versioned product configuration, not learned personal memory.
Keep them under a canonical authored assistance directory with generated package
identity checks. A profile records matching model/client/effort scope, policy/guide
revision, task families, observed failure categories, support rules, evaluation
reference, and state `candidate`, `validated`, or `withdrawn`.

Candidate rules may be used only in explicitly configured development/evaluation
runs. Normal operation uses validated matching profiles or the task-based fallback.
Unavailable, withdrawn, mismatched, or outdated profiles are not silently reused.
Model names alone do not establish a measured ability or fixed level of help.

Profiles match exact declared identity scope and `task_family`. Their only policy
adjustments are `raise_to_structured` (boolean) and `optional_components` (a subset
of `evidence_need`, `bounded_subgoal`, `verification_target`). They cannot lower
the task's base level. For active judgment plans, `goal`, `constraints`, and
`completion_cue` always remain in `guidance_components`; none-level plans are empty.
Without a matched profile, light adds `evidence_need` when current evidence or
continuity is needed; structured adds all three optional components. A matched
profile replaces that optional subset, then the base components are retained.
The fixed component order is `goal`, `constraints`, `evidence_need`,
`bounded_subgoal`, `verification_target`, `completion_cue`; duplicates are rejected.

Components specify optional reminders for the agent, not permission to omit a
required task check or full canonical procedure. A capable-model profile can omit
redundant subgoal/check reminders while retaining the task's minimum level and
all actual evidence/completion duties. An inexpensive-model profile can add those
reminders or raise the level. Evaluate these exact versioned adjustments in the
adaptive-only ablation; do not silently change the underlying task or methods.


For Luna, test focused task decomposition, readily usable evidence, and checks
for observed omissions. For Sol/Astra, test outcome-led instructions and reduction
of redundant exploration/checks. These are candidate treatments, not universal
rules. Either model may need more or less assistance for a particular task.

Never silently change the selected model or effort. A declared budget/capability
failure can produce a scoped escalation recommendation; changing models remains
subject to existing user/host authorization. All escalations and retries count
toward cost and invalidate a claim that an outcome was achieved by Luna alone.

## Canonical methods and context composition

Use the existing eligibility path and zero to two complete canonical methods per
material judgment. Low assistance does not force zero methods; structured
assistance does not force two. Contraindications and upstream constraints remain
binding. Do not replace a full procedure with a model-specific summary.

The optional wrapper clarifies the immediate goal, evidence to obtain, and stopping
point. It does not repeat the method, ask for private chain of thought, or require
a visible checklist for every response. Method availability belongs to the current
context; a persisted receipt is not a new agent's completed read.

Retrieve memory only for an actual continuity need. Load relevant decisions,
constraints, unfinished obligations, and references, then validate applicability.
Source content and recalled text remain data, not routing rules. After an enrolled
capture milestone, save only allowed public state. Do not make the user manually
curate notes for every action.

## Observable collaboration contract

| Situation | Required behavior |
| --- | --- |
| Intent is clear and authorized | Produce the result; resolve routine reversible details using context |
| Missing information materially changes the outcome | Ask about that dependency; continue independent useful work |
| Known answer or permission already exists | Reuse it within scope; avoid asking the same question again |
| User corrects the direction | Change the next action and affected artifact; supersede scoped memory when authorized |
| A side question arrives during work | Answer it and preserve the main objective unless the user changes or cancels it |
| Old memory conflicts with new explicit direction | Apply current authority and resolve scope; do not defend the old conclusion as truth |
| Task is complete | Report the useful result and material limits, then stop unchanged checking |
| Communication needs differ | Match language and detail; use plain explanations and substantive disagreement when warranted |

Ask for a scope distinction only when it changes future behavior, such as whether
a choice is for one task or the project. Repeated confirmation, automatic agreement,
generic empathy, and short output alone do not satisfy this contract. Necessary
consent and material uncertainty must remain visible.

## Verification and integration

Implement the policy as pure functions with deterministic fixtures. Exercise the
installed command's strict request/response boundary separately from actual agent
behavior. A policy receipt is not evidence that a model followed it.

Acceptance is A01-A08 and U01-U06 in 06. Evaluate task quality, completed artifacts,
unnecessary user turns, repeated actions, and full resource use. Record aggregate
reasoning-token counts only when exposed; never collect hidden reasoning text or
infer reasoning time from answer length.

Package integration reuses current generators/launchers and preserves native timing
gates. No persistent service, model selector, credential, or global setting is
required. If policy overhead exceeds its benefit, use the simpler task-based route
and retain measured failure evidence for a later revision.
