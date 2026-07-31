## Purpose

Use this procedure to represent a decision that unfolds over time, where an action changes the next possibilities and uncertain events lead to later choices. It separates decision nodes, chance nodes, and outcome nodes so that a recommendation can be traced back to information. It may use arithmetic rollback when values and probabilities are bounded, but it must hold rather than manufacture precision when branches cannot be supported.

## Use when

Use it for staged launches, pilot-versus-scale choices, maintenance or replacement timing, options to wait for a test, and other decisions with conditional branches. It fits when the order of actions matters, later choices depend on an observed result, and outcomes can be described with a source-backed value or a clearly labelled qualitative consequence. A tree is useful when the question is not merely which option scores higher now, but which strategy remains available after new information arrives.

## Do not use when

Do not use it for a static comparison with no meaningful sequence or chance branch, a purely mechanical flowchart, or a binding rule with no discretion. Do not draw independent branches for events that share a cause or depend on an earlier outcome. Do not calculate an expected value when probabilities, outcome values, or conditional actions cannot be bounded. If uncertainty is deep and coherent external futures matter more than branch arithmetic, hand off to scenario-planning.

## Inputs to establish

State the decision point, possible actions, observation times, chance events, terminal outcomes, rollback points, and the person or system that can act at each node. Record probability provenance, outcome units, timing, costs, benefits, and dependencies between branches. Mark whether a probability is verified, computed from a stated dataset, inferred, assumed, unverified, or conflicted. Ask at most two decisive questions, such as “What observation changes the next available action?” and “What source bounds this branch?”

## Procedure

1. **Fix the sequence.** State the decision, the order of actions and observations, the time horizon, and the available rollback or stop points. **Visible output/state change:** publish a tree frame that labels each known node as decision, chance, observation, or outcome.
2. **Enumerate conditional branches.** For every decision node, list the actions that remain feasible; for every chance node, list mutually exclusive outcomes and what they enable next. Preserve dependencies instead of flattening them into unrelated branches. **Visible output/state change:** create a branch register with parent, child, condition, and next-action fields.
3. **Describe terminal outcomes.** Give each terminal branch a consequence, unit, timing, affected group, and evidence state. Keep non-comparable safety or rights constraints outside an aggregate value. **Visible output/state change:** publish an outcome ledger and mark any missing or conflicting value as held or unresolved.
4. **Bound uncertainty.** Attach a source or reproducible calculation to each probability; check that conditional branches are complete and compatible with the earlier event. If a probability cannot be bounded, use a defensible range or qualitative branch only when its basis is stated, and do not pretend the tree has a numeric answer. **Visible output/state change:** publish a probability-provenance map or a hold note for the unbounded branch.
5. **Roll back and stress.** Starting at the terminal outcomes, calculate or compare the parent branches using stated values and units. Vary material probabilities or outcomes within defensible ranges, and show worst-case exposure, regret, or a rollback threshold instead of relying on one expected value. **Visible output/state change:** publish a rollback table with the recommended action, switching condition, and residual risk.
6. **Set the strategy.** Explain which action is supported now, what observation would trigger a different action, and where the decision should pause. If an unresolved branch could change the strategy, hold the recommendation and name the smallest safe observation. **Visible output/state change:** publish decision/chance/outcome nodes, outcome summary, probability provenance, rollback point, uncertainty, and a Conclusion Card flip condition.

## Public output contract

Return the decision nodes, chance nodes, outcome nodes, conditional branches, terminal consequences, and rollback point. Show probability provenance for every numeric branch and show units and expressions for computed values. Include risk exposure, a switching or stop condition, and the next observation when the strategy is provisional. The public conclusion must not imply that a tree proves an outcome; detailed branch arithmetic and dependencies belong in the trace.

## Evidence and uncertainty rules

Use verified only for an identifiable source that supports the branch or outcome. Use computed for transparent arithmetic from stated inputs, inferred for a consequence derived from labelled grounds, assumed for an explicit planning premise, unverified for unchecked inputs, and conflicted when credible sources disagree. Do not invent a base rate, probability, utility, independence assumption, or terminal value. If branches are not mutually exclusive, revise the structure before calculating. Treat a narrow numeric range without provenance as false precision.

## Stop conditions

Hold when the sequence, next action, branch outcome, or probability basis is missing in a way that could change the strategy. Hold when dependencies cannot be represented without double counting or when a binding rule removes discretion. If the branch space is too open to bound, state the missing observation and hand off to scenario-planning rather than producing an unsupported expected value.

## Complement handoff

Hand off to scenario-planning when several coherent external futures, rather than bounded chance branches, determine the preparation. Pass the decision frame, material uncertainties, branch signposts, and no-regret or contingent actions only; keep unsupported probabilities and private deliberation out of the handoff.
