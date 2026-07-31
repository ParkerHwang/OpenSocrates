## Purpose

Use this procedure to turn a favored claim, explanation, or plan into a risky, testable prediction and specify what would count against it. It separates the target claim from auxiliary assumptions and measurement failure, then reports what the observed test can and cannot establish. A failed prediction is evidence against the tested setup; it is not automatically a refutation of every related idea.

## Use when

Use it when a claim should make a risky prediction, when the user asks what could prove an explanation wrong, or when post-hoc stories are being mistaken for forecasts. It fits research hypotheses, product plans, diagnostic explanations, and strong claims that need a decisive disproof attempt.

## Do not use when

Do not use it when no testable implication can be stated, when the task is a value choice or purely mechanical execution, or when the claim is only a definition. Do not treat testability as proof, rescue every failed prediction with an ad hoc auxiliary assumption, or discard a complex theory after one failure without checking the measurement and auxiliary setup.

## Inputs to establish

Establish the target claim, scope, risky prediction, observation window, measurement, auxiliary assumptions, falsifier threshold, and decision affected. State whether the test is planned, observed, or unavailable. Ask at most one decisive question when the prediction or threshold cannot otherwise be bounded.

## Procedure

1. Publish the claim and its scope, then rewrite it as a risky prediction that could fail. This creates the visible test target rather than a post-hoc explanation.
2. Publish the falsifier: an observable result, threshold, or pattern that would count against the claim. Exclude vague conditions such as “unexpected evidence.”
3. Publish auxiliary assumptions and measurement conditions separately from the target claim. Mark which failure would implicate the claim, the setup, or the measurement.
4. Publish the planned or observed test, its provenance, and the result. If the test is unavailable, state the needed observation and keep the status unverified.
5. Publish the interpretation: supported for this test, weakened, not yet tested, or inconclusive. Do not turn a non-falsifying result into strong confirmation.
6. Publish any proposed repair and test whether it was specified before the result or added ad hoc. A repair that immunizes the claim without independent support remains a weakness.
7. Publish the current status, next test, and observable flip condition. If no falsifier can be stated, hold or refuse the method rather than manufacturing scientific-looking language.

## Public output contract

Return `claim`, `scope`, `risky_prediction`, `falsifier`, `auxiliary_assumptions`, `measurement_conditions`, `observed_needed_test`, `test_and_provenance`, `observed_or_needed_result`, `status`, and `flip_condition`. The result must distinguish not tested, inconclusive, weakened, and supported-for-this-test. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels; a non-falsified claim is not automatically verified.

## Evidence and uncertainty rules

A falsifier must be observable and linked to a pre-specified claim scope. A failed test may target an auxiliary assumption or measurement rather than the entire theory. Do not count a post-hoc adjustment as independent support. If the test was not run or the threshold was chosen after seeing the result, label the conclusion unverified or conflicted and state the limitation.

## Stop conditions

Stop and ask one blocking question when the claim or prediction cannot be bounded. Refuse or hold when no testable implication exists, the needed observation is unavailable, or a high-stakes claim has no safe test. Stop when the task is source quality, formal entailment, or explanation generation rather than a disproof attempt.

## Complement handoff

Hand off to `lean-startup` only when the falsifiable claim is a product or market hypothesis and a safe minimum test is the next decision. Pass the risky prediction, falsifier, measurement conditions, and safety exclusions. The complement should not replace a missing falsifier with a generic experiment.
