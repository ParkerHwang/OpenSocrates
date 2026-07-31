## Purpose

Use this procedure to compare competing explanations for an observed or surprising fact and select the best current explanation without presenting it as proven. It requires at least two live candidates, evaluates explanatory fit and risk, and identifies evidence that would discriminate among them. The result is a provisional diagnosis with a concrete next check, not a license to retrofit one favored story.

## Use when

Use it for debugging, diagnosis, investigation, anomaly interpretation, and other situations where several causes could explain the same observation. It fits incomplete information and questions asking what is most likely happening or why an unexpected result occurred. Use it when a deductive rule does not already settle the result.

## Do not use when

Do not use it when explicit rules and settled premises entail the conclusion, or when no observation can distinguish among explanations. Do not use a single candidate as an explanation set, score a story with invented precision, or treat absence of a disconfirming observation as confirmation. Avoid causal certainty when the candidates are only descriptive interpretations.

## Inputs to establish

Establish the surprising observation, expected baseline, decision or diagnosis it affects, known facts, plausible candidate explanations, and available tests or sources. Identify whether each candidate is a cause, mechanism, data error, or scope explanation. Ask at most one decisive question if the observation or decision target is unclear; otherwise proceed with explicit assumptions.

## Procedure

1. Publish the observation that needs explanation and the baseline it violates. Mark which parts are checked facts, user reports, or assumptions; this creates the visible anomaly state.
2. Publish at least two candidate explanations with their predicted observations and scope. Add a candidate for measurement, selection, or reporting error when it is plausible rather than treating the first substantive story as default.
3. Publish a qualitative comparison for explanatory fit, coverage, simplicity, consistency with established knowledge, and testability. Use ordinal labels such as strong, moderate, weak, or unknown; do not invent probabilities.
4. Publish discriminating evidence: the observation, experiment, or source that would separate the leading candidates. State which result would raise, lower, or leave each candidate unchanged.
5. Publish the best current explanation and why it leads, with a provisional status. Keep alternatives visible and state whether the result is a diagnosis, a working hypothesis, or an unresolved set.
6. Publish the next verification action and the material failure mode, including what would show that the explanation is wrong or that the evidence link is unreliable.
7. Publish the current conclusion, candidate set, and observable flip condition. If no candidate has discriminating support or a decisive observation is missing, hold the result rather than choosing the most vivid narrative.

## Public output contract

Return `observation`, `candidate_explanations`, `comparison_criteria`, `discriminating_evidence`, `provisional_best_explanation`, `next_test`, and `flip_condition`. The top line must say “best current explanation” or equivalent when the result is provisional. Grounds carry **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels; candidate fit is an inference, not direct proof.

## Evidence and uncertainty rules

A surprising fact can motivate a hypothesis but cannot establish its cause. Require independent or discriminating support before upgrading a candidate. Avoid double-counting the same observation under several criteria. If candidates fit equally well, report unresolved competition. If a material test is unavailable, keep the best explanation provisional or held and state the missing evidence.

## Stop conditions

Stop and ask one blocking question when the observation or decision target is too vague to identify candidate explanations. Hold when only one candidate is available, no testable implication exists, or decisive evidence is missing. Stop when explicit premises entail the result or when the remaining task is source quality, formal validity, or option comparison.

## Complement handoff

Hand off to `value-of-information` when the main decision is whether to purchase, collect, or wait for discriminating information. Pass the candidate set, decision-changing evidence, and cost or delay of the next test. The complement should not repeat the explanation comparison.
