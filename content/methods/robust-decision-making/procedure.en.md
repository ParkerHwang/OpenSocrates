## Purpose

Use this procedure to choose an action that remains acceptable across several plausible futures when no single forecast deserves to control the decision. It makes uncertainty, failure criteria, and trade-offs visible, then separates a robust first move from actions that should wait for a signpost. Robust does not mean optimal in every future; it means the action clears the stated floor without relying on an invented probability distribution.

## Use when

Use it for long-lived policy, infrastructure, investment, product, or operating choices exposed to interacting uncertainties. It fits decisions where failure is costly, reversal is slow, or stakeholders cannot agree on one forecast. It is useful when the question is “what can survive several plausible conditions?” rather than “which outcome is most likely?”

## Do not use when

Do not use it when one expected case is reliable and the choice is cheap and fully reversible, or when there is only one feasible action under a binding rule. Do not use a catalogue of arbitrary worst cases, claim that an action is best in all futures, or hide the cost of robustness. If success and failure cannot be defined, first clarify the decision or use an evidence method to establish the criteria.

## Inputs to establish

Establish the decision, feasible actions, time horizon, stakeholders, and minimum acceptable performance. Define failure, unacceptable regret, and material trade-offs before testing. List deep uncertainties, dependencies, known constraints, and a small set of plausible world descriptions; do not assign probabilities unless the user provides a defensible source. Record reversibility, cost, timing, and current commitments. Ask at most two decisive questions, only when their answers would change the action set or acceptance floor.

## Procedure

1. Publish the decision frame, candidate actions, and acceptance criteria. **Visible output/state change:** the task has a bounded choice set and an explicit acceptable/failure floor.
2. Publish an uncertainty register and a set of distinct, internally coherent plausible worlds. **Visible output/state change:** the analysis moves from one forecast to a visible test set; world descriptions carry assumptions and dependencies, not probabilities.
3. Test every candidate action against every world using the stated criteria. **Visible output/state change:** a strategy-by-world result matrix records acceptable, fragile, or failed states with their evidence labels.
4. Publish failure conditions, regret exposure, and clusters of worlds that stress the same action. **Visible output/state change:** vulnerabilities and trade-offs become named rather than hidden inside an overall score.
5. Publish the robust action or the smallest set of actions that clears the acceptance floor across the tested worlds. **Visible output/state change:** the recommendation is separated from its cost, opportunity loss, and residual vulnerability.
6. Publish safeguards, reversible first moves, contingent actions, and monitoring signals with their trigger responses. **Visible output/state change:** the decision becomes adaptive rather than a one-time bet on a preferred world.
7. Publish supported, provisional, or held status, plus an observable flip condition. **Visible output/state change:** missing decisive criteria or worlds produce a hold, not a claim of robustness.

## Public output contract

Return `uncertainties`, `plausible_worlds`, `regret_or_failure_criteria`, `robust_action`, `tradeoffs`, `monitoring_signals`, `flip_condition`, and a supported, provisional, or held status. Describe why the action clears the acceptance floor and where it remains fragile. The card states one conclusion, labels material grounds, names the unresolved uncertainty, and gives an observable condition that would change the action; detailed matrices belong in the trace or supporting artifact.

## Evidence and uncertainty rules

Plausible worlds are structured test cases, not forecasts and not a probability-weighted sample. Ground each material world in an observation, a defensible mechanism, a user constraint, or an explicit assumption. Do not invent world frequencies, expected losses, utility scores, or universal robustness. “Acceptable” must refer to the published criterion. Mark computed comparisons with inputs and units, and preserve conflicting evidence rather than averaging it away. A robust action may still be inferior on cost or upside; keep that trade-off visible.

## Stop conditions

Ask one blocking question and stop when the action set or minimum acceptable performance has materially different interpretations. Hold when a decisive uncertainty, failure threshold, or feasible action is missing. Stop this method when a single forecast is reliable, a binding rule leaves no discretion, or the remaining work is scenario construction, evidence verification, or ordinary option comparison.

## Complement handoff

Hand off to `scenario-planning` when the world set needs a more deliberate external-future structure or signpost narrative. Pass the decision frame, uncertainty register, acceptance floor, vulnerable clusters, and current world descriptions. The complement should enrich the worlds without hiding the failure criteria or turning them into probabilities.
