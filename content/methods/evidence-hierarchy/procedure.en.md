## Purpose

Use this procedure to calibrate a claim to the quality, directness, applicability, and bias risk of its supporting sources. It classifies the claim type, compares study or evidence designs without treating a rigid hierarchy as universal, and states the resulting evidence state and conclusion strength. A lower-tier source can still be useful when it directly fits the question and stronger designs do not.

## Use when

Use it when research, policy, product experiments, expert opinion, user reports, or other evidence types are mixed and the answer needs a defensible strength label. It fits questions about whether sources support a claim, whether a study applies to the target context, and how wording should change when evidence quality differs.

## Do not use when

Do not use it when the main dispute is a value preference rather than factual support, or when a formal rule, causal model, or source conflict method is more specific. Do not rank evidence by prestige alone, discard relevant lower-tier evidence automatically, or call a source strong without checking directness and limitations.

## Inputs to establish

Establish the claim, target population or context, claim type (effect, forecast, mechanism, or experience), decision threshold, sources, study designs, samples, measures, and known conflicts. Identify whether each source is direct, indirect, or only contextual. Ask at most one decisive question when the target context changes applicability.

## Procedure

1. Publish the claim, target context, and decision threshold. State whether the claim is about effect, prediction, mechanism, or experience; this creates the visible evidence review state.
2. Publish a claim-to-source table with source type, design, sample or basis, directness, and scope. Mark each source as checked, user-provided, inferred, or unavailable.
3. Publish quality dimensions—design rigor, bias risk, measurement validity, completeness, and applicability—using qualitative or ordinal labels with provenance. Do not invent a precise composite score.
4. Publish the hierarchy position and its limits for each source. Explain why a source is strong or weak for this particular claim rather than treating position as universal authority.
5. Publish agreement, inconsistency, and missing evidence across sources. Keep a credible conflict visible; do not average incompatible results into a single number without a justified synthesis rule.
6. Publish the resulting evidence state and calibrated conclusion wording: strongly supported, supported, provisional, unverified, conflicted, or held. State the smallest source or applicability limitation that constrains the wording.
7. Publish the next verification action and an observable flip condition. If decisive support is absent, hold or lower the claim rather than presenting a high-stakes conclusion as established.

## Public output contract

Return `claim`, `claim_type`, `claim_to_source_table`, `quality_limits`, `quality_dimensions`, `hierarchy_position_and_limits`, `agreement_and_conflicts`, `missing_evidence`, `resulting_evidence_state`, `calibrated_conclusion`, and `flip_condition`. The card must show the evidence state and a safe source link or user-provided label when applicable. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels.

## Evidence and uncertainty rules

Design hierarchy is a guide, not a substitute for question fit. Check directness, population, outcome, time, measurement, selection, attrition, and reporting bias. An expert opinion may identify a mechanism while not estimating effect size; a user report may reveal experience while not establish prevalence. If sources disagree materially or the best source is indirect, lower or hold the result and name the limitation.

## Stop conditions

Stop and ask one blocking question when the target context or claim is undefined and applicability would change the decision. Hold when no source directly supports a material claim, a conflict cannot be resolved, or quality limits prevent a safe strength label. Stop when the issue is value choice, formal entailment, or generating explanations rather than evidence calibration.

## Complement handoff

Hand off to `triangulation` when independent evidence streams could corroborate or expose a material conflict. Pass the claim-to-source table, quality limits, and unresolved disagreement. The complement should check independence and convergence without rebuilding source rankings.
