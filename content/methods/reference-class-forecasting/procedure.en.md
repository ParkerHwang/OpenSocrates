## Purpose

Use this procedure to replace an inside-view forecast with an outside-view comparison grounded in a defensible class of completed, comparable cases. It estimates a target from observed outcomes and makes explicit which current facts justify any adjustment. It is a calibration aid, not a promise and not permission to invent a population, a distribution, or a probability.

## Use when

Use it for schedule, cost, demand, adoption, reliability, or delivery forecasts when similar past cases are available and an internal plan may be optimistic. It is especially useful when a proposal says “this case is different” without showing how the difference changes the expected range. It fits a decision that needs a grounded range rather than a single point estimate.

## Do not use when

Do not use it when no defensible reference class of completed cases can be found, when the target and unit are unclear, or when the task is a unique one-off with no comparable outcome. Do not call a few anecdotes a base distribution, select only successful cases, or turn an internal forecast into evidence. If the decision is purely mechanical or the user needs causal diagnosis rather than calibration, stop and redirect.

## Inputs to establish

Establish the target outcome, unit, time horizon, cutoff date, and acceptable boundary. Define inclusion and exclusion rules for the reference class before inspecting results. Gather the observed cases, their outcome definitions, coverage, missingness, and source status. Record the current project’s known differences and the inside-view forecast. Ask at most two decisive questions, and only when their answers would change the class or the target. Label each input as verified, computed, inferred, assumed, unverified, or conflicted.

## Procedure

1. Publish the target, unit, horizon, and decision boundary in one sentence. **Visible output/state change:** a forecast baseline exists, with any ambiguous target marked held rather than silently narrowed.
2. Publish the reference-class rule, including inclusion, exclusion, similarity dimensions, and known coverage gaps. **Visible output/state change:** the comparison set changes from an intuition to an auditable class definition.
3. Publish the observed outcome distribution using only available cases: count, center, spread, range, and tails when they can be computed. **Visible output/state change:** each statistic has stated inputs and a source/evidence label; unavailable statistics remain unverified.
4. Publish the outside-view baseline beside the inside-view plan and explain the direction of their difference. **Visible output/state change:** the judgment records whether the internal plan is within, above, or below the observed distribution without treating that position as a probability.
5. Publish adjustments for material current-case differences, one difference at a time. **Visible output/state change:** every adjustment has a direction, rationale, and evidence state; a numeric adjustment is used only when its scale is defensible.
6. Publish a bounded range and the conditions that make its edges plausible. **Visible output/state change:** the range is widened or held when coverage, selection, or tail evidence is weak, and no fabricated base rate fills the gap.
7. Publish the status as supported, provisional, or held, with a flip condition and one next check. **Visible output/state change:** a missing decisive class or outcome input becomes an explicit hold instead of an arbitrary recommendation.

## Public output contract

Return `target`, `reference_class`, `base_distribution`, `adjustments`, `range`, `inside_view_comparison`, `flip_condition`, and a status of supported, provisional, or held. The conclusion should state what the observed class supports, not claim that the current case will match it. Card grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted**; the uncertainty section names missing coverage or selection risk, and the flip condition is observable rather than “if new information appears.”

## Evidence and uncertainty rules

The class is supported only by completed cases whose target, unit, and inclusion status are defined. A source may verify an observed result but not the comparability of the current project; state that comparison as inferred unless directly supported. Computations must show the cases or references used and the rounding rule. Do not invent a median, tail, sample size, base rate, or probability. Preserve selection bias, missing cases, conflicting definitions, and small-sample limits. “This case is different” is an adjustment hypothesis until its direction and effect are evidenced.

## Stop conditions

Ask one blocking question and stop when the target, unit, or decision boundary has materially different interpretations. Hold the conclusion when no defensible class, outcome definition, or decisive comparison input can be established. Stop this method when the remaining work is causal explanation, a choice among options, or a mechanical calculation; hand off rather than forcing an outside-view forecast.

## Complement handoff

Hand off to `sensitivity-analysis` when the decision depends on how the reference distribution or a current-case adjustment changes the choice. Pass the target, observed baseline, tested adjustment ranges, coverage limits, and switching condition. The complement should perturb those inputs without rebuilding the reference class or treating the result as a new base rate.
