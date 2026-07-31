## Purpose

Use this procedure to run a bounded Plan–Do–Check–Act cycle for an operational improvement hypothesis. It makes the objective, measure, small execution scope, comparison rule, and standardization decision visible so that improvement accumulates as evidence and organizational memory. It is a controlled learning loop, not a substitute for diagnosing an unknown root condition or for responding to an active safety incident.

## Use when

Use it when a process or service can be changed in a small, reversible scope, the expected improvement can be measured, and repeated cycles can raise a standard. It fits an improvement hypothesis that needs a short observation window and a clear decision about standardize, revise, or abandon. Use it when a team needs to learn from execution without committing the whole operation to an untested change.

## Do not use when

Do not use it when the root condition is unknown and experimentation could hide or worsen harm, when a binding rule leaves no discretion, or when an urgent safety, security, legal, or incident response is required. Do not run a cycle merely to create activity without a check rule. Do not turn a mechanical request into an improvement program, and do not standardize a change because it was announced or completed once.

## Inputs to establish

Establish the improvement objective, observed baseline or process state, hypothesis, scope, owner, and expected direction of change. Define the metric, unit, source, observation window, guardrails, stop condition, and comparison rule before the Do step. Specify the evidence needed to standardize, revise, or abandon the change, plus where the next cycle or versioned standard will be recorded. Ask no more than two concise questions, and only when a missing answer could change the safety boundary, measure, or Act decision; otherwise label the gap unverified and hold when it is decisive.

## Procedure

1. **Publish the Plan card.** State the objective, baseline, improvement hypothesis, expected direction, scope, owner, and time boundary. Mark the baseline as verified, computed, user-provided, inferred, assumed, or unverified. **Visible output/state change:** plan state.
2. **Publish the Check specification.** Name the metric, unit, source, collection method, observation window, comparison rule, guardrails, and stop condition. Predeclare evidence for standardize, revise, or abandon. **Visible output/state change:** check rule.
3. **Publish the Do log.** Execute only within the approved small scope and record the actual change, deviations, exclusions, incidents, and observations. Keep a rollback path and do not expand exposure because the first signal looks favorable. **Visible output/state change:** auditable execution record.
4. **Publish the Check result.** Compare expected and observed values or descriptions using the predeclared rule. Identify missing data, confounders, source limits, and contradictions. **Visible output/state change:** result gap with evidence state.
5. **Publish the Act decision.** Choose standardize, revise, abandon, or hold according to evidence and guardrails. If the result is mixed or the decisive measure is missing, keep the change provisional and record the unresolved condition. **Visible output/state change:** Act decision or hold.
6. **Publish the next cycle.** Record the versioned standard or revised hypothesis, owner, next observation, and one or two observable flip conditions. Carry forward what was learned and what remains unverified. **Visible output/state change:** next-cycle plan or held result.

## Public output contract

Return card-ready fields named `plan_objective_measure`, `do_scope`, `check_rule`, and `act_standardize_decision`, with the evidence state for each material ground. `plan_objective_measure` must include the baseline or its absence; `do_scope` must show the bounded exposure; `check_rule` must show the comparison and stop rule; and `act_standardize_decision` must distinguish standardize, revise, abandon, and hold. Include a next-cycle hypothesis or a clear reason no cycle should continue. A missing decisive measure produces a held result.

## Evidence and uncertainty rules

Treat a direct observation, linked source, reproducible calculation, user-provided record, inference, and adopted working premise as different evidence states. For `computed`, show inputs, expression, units, and rounding where relevant. If there is no defensible baseline or the collection method changed, mark the comparison unverified. Do not invent probabilities, effect sizes, sample counts, or causal certainty. One cycle may support a local learning claim but rarely proves a permanent standard; credible conflicting observations keep the Act decision conflicted or held. Preserve deviations and negative signals rather than reporting only improvement.

## Stop conditions

Hold when the objective, baseline, measure, comparison rule, owner, or safe scope is missing and could change the Act decision. Stop immediately if the cycle creates ongoing harm, weakens a required control, exceeds authorization, or loses a safe rollback. If the root condition is unknown and the cycle could mask it, hand off to `root-cause-analysis`. Stop after a failed or inconclusive check when no revised hypothesis or safe next observation exists; do not repeat Do without learning.

## Complement handoff

Hand off to `root-cause-analysis` when the Check result reveals a repeated failure, competing causal paths, or a control weakness that must be diagnosed before another improvement cycle. Pass the published plan, bounded Do scope, check result, deviations, evidence states, and remaining control question. Do not pass an unsupported blame claim or start a second full method merely because the first cycle was inconclusive.
