## Purpose

Use this procedure for conclusions that normally follow but can be withdrawn when an exception or new evidence appears. It states a default rule, applies it provisionally, distinguishes rebutting from undercutting defeaters, and records explicit withdrawal conditions. The result is a controlled provisional judgment, not a weakened way to state an unconditional rule.

## Use when

Use it for law, policy, medicine, operations, common-sense rules, and other domains where a generalization admits exceptions or evidence arrives over time. It fits “normally,” “unless,” and “prima facie” reasoning and any judgment that must remain revisable without becoming arbitrary.

## Do not use when

Do not use it when a strict rule and settled premises entail the result, or when the issue is only source ranking or statistical updating. Do not list every imaginable exception, treat a credibility problem as direct contradiction, or prefer the most recent statement merely because it is recent. Do not claim that absence of a known defeater proves the conclusion.

## Inputs to establish

Establish the default rule, triggering facts, rule scope, known exceptions, possible rebutting and undercutting defeaters, and the decision affected. Identify any more-specific rule that could take precedence. Ask at most two decisive questions when the rule or trigger fact is unclear; otherwise mark the premise as provisional.

## Procedure

1. Publish the default rule in a bounded form such as “normally P implies Q,” with source, scope, and evidence state. This creates the visible rule state.
2. Publish the applicable facts and the prima-facie conclusion. Label it provisional and state the conditions under which the default is being applied.
3. Publish rebutting defeaters that support not-Q separately from undercutting defeaters that weaken the P-to-Q connection. Record whether each is checked, alleged, or unknown.
4. Publish competing rules and apply specificity when one rule is a genuine subset of another. If specificity does not resolve the conflict, set the current status to conflicted or held rather than using recency or confidence tone.
5. Publish explicit withdrawal conditions: the observable fact that would retract Q, weaken the warrant, or require rejudgment. Keep the condition narrower than “new information appears.”
6. Publish the updated status after the known defeaters: provisional, supported, withdrawn, conflicted, or held. State whether the conclusion changed because of a rebuttal, an undercutter, or an unresolved conflict.
7. Publish the current conclusion, applicable defeaters, and flip condition. If a decisive trigger fact or exception is missing, hold or keep the result provisional instead of upgrading it to certainty.

## Public output contract

Return `default_rule`, `applicable_facts`, `prima_facie_conclusion`, `exceptions_defeaters`, `rebutting_defeaters`, `undercutting_defeaters`, `specificity_resolution`, `withdrawal_conditions`, `current_status`, and `flip_condition`. The card must make provisionality and material defeaters visible. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels; never call the default conclusion unconditional.

## Evidence and uncertainty rules

A rebutting defeater conflicts with the conclusion; an undercutting defeater weakens the reason the facts support it without proving the opposite. Specificity is a structural priority, not a recency rule. New evidence must be checked for scope and independence before it changes the status. If a material defeater is unresolved, lower or hold the result and state what check is needed.

## Stop conditions

Stop and ask one blocking question when the default rule or trigger facts cannot be identified and competing rules lead to different actions. Hold when a decisive exception, source, or applicability condition is missing. Stop when the rule is strict and exception-free or when the remaining task is probabilistic evidence updating.

## Complement handoff

Hand off to `premortem-analysis` when the provisional rule is supporting a chosen plan and the remaining concern is how the plan could fail. Pass the default conclusion, known defeaters, and withdrawal conditions. The complement should not reclassify the defeaters or restate the rule inventory.
