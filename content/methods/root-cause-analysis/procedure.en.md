## Purpose

Use this procedure to explain a failure that has recurred or has consequences a quick fix cannot safely address. It separates the visible symptom from proximate causes, contributing conditions, and controllable system conditions. The aim is not to assign blame or discover one root. It produces a causal chain, a prevention action with an owner, and a verification signal showing whether recurrence risk changed.

## Use when

Use it for repeated incidents, quality escapes, service degradation, recurring defects, missed handoffs, or a workaround that keeps returning. It fits operational or product failures bounded by an observable event, population, period, and impact. It is useful when a team blames an individual for a predictable interaction between tools, workload, incentives, training, and controls. Use logs, timelines, interviews, samples, or fishbone grouping, but tie claims to an observation or marked assumption.

## Do not use when

Do not use it to adjudicate a binding legal or policy duty, to infer intent from a single mistake, or to redesign a system that has no concrete failure target. A one-off event with no repeat pattern may need causal-reasoning or an incident review instead. Do not call the nearest trigger the root merely because it is easy to name. Do not promise that one intervention will eliminate recurrence when the system has multiple independent pathways or when the underlying evidence is missing.

## Inputs to establish

Write a problem statement with the observable failure, affected scope, time window, impact, and what “recurrence” means. Collect a timeline, the expected versus actual process, relevant records, and known controls. Name people or components as participants in the system, not as presumed causes. Ask no more than two questions that could change the diagnosis, such as “Has the same failure occurred under a different operator?” or “Which control should have detected it?” Mark unavailable logs, retrospective recollections, and untested assumptions explicitly.

## Procedure

1. **Bound the failure.** Describe what happened, where, when, how often, and with what impact; distinguish the event from its interpretation. **Visible output/state change:** publish a one-sentence problem statement and an expected-versus-observed boundary, with unknown scope labelled unverified.
2. **Separate layers.** Classify observations as symptom, proximate cause, contributing condition, control weakness, or system condition. Keep multiple branches when the evidence supports more than one pathway. **Visible output/state change:** create a labelled cause inventory rather than a blame statement.
3. **Build the chain.** Use a timeline, “why” questions, process map, or cause-and-effect grouping to connect each candidate to the next observable condition. Stop a branch when it becomes speculation and record the missing check. **Visible output/state change:** publish a causal chain with support state beside every material link.
4. **Test counterfactual controllability.** For each proposed root condition, ask whether removing or changing it would plausibly prevent this failure while leaving the rest of the context similar. Consider independent paths and controls that could still fail. **Visible output/state change:** mark each candidate as controllable, contributory, unresolved, or contradicted; do not rank it with fabricated numbers.
5. **Select actions and ownership.** Separate containment that limits current harm from prevention that changes the condition, and detection that catches a recurrence. Assign an owner, a due boundary, and a test signal to each material action. **Visible output/state change:** publish an action register linked to the causal chain, including the residual risk if an action is not completed.
6. **Verify and revise.** Define what later observation would show that recurrence decreased or that the diagnosis was wrong. Reopen the chain when new evidence contradicts a link; do not close the analysis because an action was announced. **Visible output/state change:** publish a held, provisional, or supported diagnosis plus a dated verification condition and next check.

## Public output contract

Return the bounded problem statement, causal chain, controllable root condition, and the distinction between containment, prevention, and detection. Show each material link’s evidence state, action owner, verification signal, and residual risk. A Conclusion Card may summarize the diagnosis and a flip condition; detailed branches belong in the trace. If the root condition is not established, say “the leading explanation is” and keep the task provisional rather than presenting a single culprit as fact.

## Evidence and uncertainty rules

A repeated symptom does not prove a repeated cause. Treat a timestamped record, reproducible test, or direct observation differently from a retrospective account or plausible story. Never use “human error” as a complete diagnosis when workload, interface design, incentives, training, handoffs, or missing controls could contribute. Do not calculate a risk priority or recurrence probability without a defensible scale and provenance; use qualitative labels such as material, plausible, unresolved, and low-consequence only when their basis is stated. If branches conflict, show the conflict and hold the root conclusion.

## Stop conditions

Stop and hold when the failure boundary is unknown, the records needed to distinguish causes are unavailable, or every candidate rests on an untested narrative. Stop before naming an individual as the cause unless direct evidence supports that claim and system conditions have been examined. If harm is ongoing, prioritize safe containment and qualified incident or safety procedures over a polished root-cause explanation.

## Complement handoff

Hand off to failure-mode-effects-analysis when the diagnosis should become a forward-looking inventory of how a process or design could fail and which controls should be assigned. Pass the public failure boundary, causal branches, and known controls only; the complement must not restate unsupported blame or invent severity scores.
