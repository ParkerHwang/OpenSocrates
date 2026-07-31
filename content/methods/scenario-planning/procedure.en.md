## Purpose

Use this procedure to structure several coherent external futures and prepare choices for them. The aim is not to predict one future; it is to expose how a decision behaves when important, uncertain forces diverge. The result separates no-regret actions from contingent actions and keeps signposts visible for later review.

## Use when

Use it for long-horizon strategy, investment, policy, infrastructure, or product choices, especially with a five-year or longer horizon or repeated forecast failure. It fits questions such as “what should we prepare for?” when several external conditions could plausibly shape the outcome. It is useful before an irreversible commitment, not only after a forecast has been selected.

## Do not use when

Do not use it for a short-term point forecast, a simple optimistic/base/pessimistic number change, or a decision that has no meaningful external uncertainty. Do not choose two correlated axes, write four versions of the same good/bad future, assign probabilities, or end with stories that contain no action. If the real task is to compare numeric inputs in one model, use sensitivity analysis instead.

## Inputs to establish

Establish the focal question, time horizon, system boundary, current decision, and common premises that are predictable enough to hold across futures. List candidate drivers with evidence for impact and uncertainty, and identify two independent critical uncertainties. Record constraints, stakeholders, existing commitments, and the observations that could become signposts. Ask at most two decisive questions, only when the answer changes the focal question or axis pair. Mark premises and drivers as verified, computed, inferred, assumed, unverified, or conflicted.

## Procedure

1. Publish the focal question, horizon, boundary, current decision, and common premises. **Visible output/state change:** the work moves from an open-ended future prompt to a bounded preparation question.
2. Publish the two critical-uncertainty axes and why each is high-impact and hard to predict. **Visible output/state change:** correlated, low-impact, or predictable candidates are rejected or moved into common premises.
3. Publish a 2×2 matrix with four named, internally consistent scenarios and a short pathway for how each could arise. **Visible output/state change:** four distinct futures exist as plausible test environments; none receives a probability or preference label.
4. Publish the current decision’s validity and vulnerability in each scenario. **Visible output/state change:** a wind-tunnel record distinguishes no-regret actions, scenario-contingent actions, and choices that fail across the matrix.
5. Publish signposts, trigger responses, and a review cadence for distinguishing the scenarios as conditions evolve. **Visible output/state change:** the scenario set becomes a living monitoring plan rather than a static narrative.
6. Publish the robustness conclusion and an observable flip condition. **Visible output/state change:** if the axes, premises, or action implications are not defensible, the conclusion becomes provisional or held instead of a disguised forecast.

## Public output contract

Return `driving_uncertainties`, `scenarios`, `signposts`, `no_regret_actions`, `contingent_actions`, `decision_check`, and `flip_condition`, with a supported, provisional, or held status. `scenarios` contains four named summaries with pathways and decision implications. The card states the preparation conclusion, the material uncertainty, the observable condition that changes the plan, and a compact alternatives summary. Keep the full matrix and review cadence in the trace or supporting artifact.

## Evidence and uncertainty rules

Common premises should be source-backed or explicitly marked assumed. An axis is a framing hypothesis about impact and uncertainty, not a measured fact unless its evidence says so. Scenarios must be internally coherent and plausible, but they are not forecasts; never attach percentages, rankings, or hidden likelihoods. Separate observed signposts from inferred interpretations. Do not fabricate a trend, trigger date, or external driver. If the two axes are dependent, revise the pair or hold the result.

## Stop conditions

Ask one blocking question and stop when the focal question, horizon, or decision boundary has materially different meanings. Hold when no independent high-impact uncertainties, defensible premises, or actionable decision are available. Stop this method when the task is a short-range forecast, a model perturbation, or a settled operational choice; redirect rather than forcing four scenarios.

## Complement handoff

Hand off to `pestel-analysis` when the scenario drivers need a structured review of political, economic, social, technological, environmental, or legal factors. Pass the focal question, horizon, common premises, candidate drivers, chosen axes, and evidence states. The complement should test the external drivers without collapsing the scenarios into a single predicted future.
