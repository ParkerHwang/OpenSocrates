## Purpose

Use this procedure to update confidence in competing hypotheses when new evidence arrives and the prior basis and likelihood direction can be stated responsibly. It makes base rates, evidence direction, posterior change, and sensitivity visible. Exact probabilities are optional; an ordinal update is honest when numeric inputs lack provenance, but a precise posterior must show its inputs and normalization.

## Use when

Use it for diagnostic signals, test interpretation, sequential evidence, risk estimates, and decisions where a new observation should change confidence in competing hypotheses. It fits questions about how likely a hypothesis is after evidence, especially when base-rate neglect is a risk.

## Do not use when

Do not use it when there is no defensible prior basis or even an ordinal direction for how the evidence differs across hypotheses, or when the task is a strict rule application. Do not confuse `P(E|H)` with `P(H|E)`, reuse the same evidence as independent updates, or invent exact percentages to create false certainty.

## Inputs to establish

Establish mutually exclusive and sufficiently covering hypotheses, the current decision, prior or base-rate basis, new evidence, likelihood direction or values under each hypothesis, dependencies among evidence items, and the action threshold. Ask at most two decisive questions when a missing prior or evidence definition changes the update; otherwise use a labeled ordinal prior.

## Procedure

1. Publish the competing hypothesis set and the decision threshold. State what is being updated and mark hypotheses as user-provided, source-backed, or provisional; this creates the visible update state.
2. Publish the prior basis for each hypothesis, including base-rate source, reference population, or bounded ordinal prior. If priors are unknown, show the uncertainty instead of choosing a convenient number.
3. Publish each evidence item and its direction under every hypothesis: supports, weakens, or is largely neutral. Check whether items are independent or partially reuse the same signal.
4. Publish the posterior change using exact arithmetic only when inputs are defensible; otherwise state a qualitative update or range. Show normalization for competing hypotheses and preserve the prior-to-posterior direction.
5. Publish sensitivity to the prior and likelihood assumptions. Identify the value or direction change that would reverse the ranking or action threshold.
6. Publish the current leading hypothesis, posterior status, and next evidence that would most improve the decision. Keep a lower-ranked but plausible hypothesis visible when it remains material.
7. Publish the updated conclusion and an observable flip condition. If the prior or likelihood direction is missing, hold or keep the result provisional rather than reporting a fabricated posterior.

## Public output contract

Return `hypotheses`, `prior_basis`, `evidence_direction`, `posterior_change`, `normalization_or_update_range`, `sensitivity`, `decision_threshold`, and `flip_condition`. The card must distinguish a computed posterior from an ordinal or inferred update. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels; a base rate is not automatically verified merely because it is numeric.

## Evidence and uncertainty rules

The prior must come from a defensible base rate, expert estimate with provenance, or earlier posterior. The likelihood is `P(E|H)`, not the probability of the hypothesis after evidence. Do not update twice on dependent evidence. If credible inputs disagree, show the conflict and lower or hold the result. If sensitivity crosses the action threshold, state that the decision is fragile.

## Stop conditions

Stop and ask one blocking question when the hypothesis set or evidence definition is missing and different choices would reverse the action. Hold when no defensible prior or likelihood direction exists, or when dependency prevents a trustworthy update. Stop when a strict rule, explanation search, or source-quality ranking is the actual task.

## Complement handoff

Hand off to `abduction` when the main unresolved task is generating and comparing explanations rather than updating a defined hypothesis set. Pass the observed evidence, candidate hypotheses, and discriminating test. The complement should not repeat the posterior calculation.
