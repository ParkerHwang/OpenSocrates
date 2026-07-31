## Purpose

Use this procedure to test how a model result, comparison, or decision changes when important inputs or weights move within defensible ranges. It identifies influential variables, switching values, interactions, and fragile assumptions. The output is a transparent robustness check, not a license to choose dramatic ranges or imply that a model proves the future.

## Use when

Use it when a calculation, forecast model, business case, scoring rule, or option comparison already exists and uncertain inputs may change the decision. It helps prioritize data collection, expose a hidden threshold, and distinguish a conclusion that survives reasonable variation from one that depends on a narrow assumption. It can use numeric or ordinal changes when the scale is explicit.

## Do not use when

Do not use it when there is no model, comparison, decision rule, or variable relationship to perturb. Do not create a sensitivity result from a purely factual question, an undefined baseline, or ranges with no provenance. Do not vary correlated variables independently, treat a non-linear model as linear without checking, or report a precise switching value when the inputs cannot support that precision.

## Inputs to establish

Establish the baseline model or rule, output metric, decision threshold, inputs or weights, units, and current result. Define a plausible range and provenance for each uncertain input, including dependencies and constraints. State the perturbation design, rounding rule, and whether the test is one-at-a-time, a structured combination, or an ordinal comparison. Record the option or policy that the result is meant to inform. Ask at most two decisive questions, only where the answer changes the baseline or range.

## Procedure

1. Publish the baseline formula or decision rule, inputs, units, and result. **Visible output/state change:** the analysis has a reproducible starting state and a named decision threshold.
2. Publish tested ranges, weights, dependencies, and the evidence behind each range. **Visible output/state change:** every perturbation boundary is marked verified, computed, inferred, assumed, unverified, or conflicted rather than chosen for effect.
3. Run one-at-a-time tests and then only defensible structured combinations. **Visible output/state change:** a result log records each changed input, resulting output, method, units, and rounding; correlated inputs move together when required.
4. Publish response direction, magnitude or ordinal change, interactions, and switching values where the threshold is crossed. **Visible output/state change:** variables are classified as influential, non-influential, robust, or fragile without pretending that rank alone proves causation.
5. Publish the decision implication and research priority for the variables that could change it. **Visible output/state change:** investigation effort is tied to a named flip condition rather than to the largest raw variation.
6. Publish a robust, fragile, provisional, or held conclusion with the next validation check. **Visible output/state change:** missing baseline, range, or threshold becomes an explicit hold instead of a fabricated sensitivity claim.

## Public output contract

Return `baseline`, `tested_ranges`, `perturbation_results`, `switching_values`, `robust_or_fragile_conclusion`, `research_priority`, and `flip_condition`, with a supported, provisional, or held status. State the threshold and the inputs that can cross it. Card grounds identify computed values and their inputs; uncertainty names range or model limits; the flip condition is an observable input or threshold change. Keep the full run log and formulas in the trace or supporting artifact.

## Evidence and uncertainty rules

Ranges require a source, user constraint, historical observation, or explicit assumption; a convenient range is not evidence. Computed results must expose the formula, operands, units, and rounding. Preserve non-linearity, correlation, discontinuity, and model-form uncertainty when they matter. If only ordinal weights are defensible, report direction or threshold order, not pseudo-precise percentages. Do not infer a real-world probability from how often a test case was sampled. A robust model result can still be a fragile decision if the threshold or objective is wrong.

## Stop conditions

Ask one blocking question and stop when the baseline, decision threshold, or target output has materially different interpretations. Hold when a required input range, dependency, or rule cannot be established. Stop this method when no decision would change under any defensible perturbation, or when the remaining work is evidence verification, causal explanation, or a broader option trade-off.

## Complement handoff

Hand off to `trade-off-analysis` when the sensitivity results must be combined with explicit criteria, weights, and stakeholder preferences across options. Pass the baseline, switching values, robust/fragile findings, range provenance, and research priorities. The complement should compare choices using those boundaries without treating sensitivity rank as a preference or a probability.
