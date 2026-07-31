## Purpose

Use this procedure to generalize from observations while keeping the conclusion probabilistic and bounded by the sample. It identifies the induction type, checks sample size, diversity, and representativeness, searches actively for counterexamples, and states the scope and strength of the generalization. Repeated observations increase support only when the sampling and measurement basis justify the extension.

## Use when

Use it for patterns in data, surveys, user feedback, repeated incidents, and claims that move from observed cases to a broader population or future behavior. It fits statistical, enumerative, causal, or analogical generalization when the user needs to know how far the observations support the claim.

## Do not use when

Do not use it for an unrepresentative convenience sample, a strict rule application, or a causal claim that requires a causal design rather than pattern extension. Do not treat many duplicate observations as diversity, infer “all” from a small sample, or turn a plausible trend into a necessary conclusion.

## Inputs to establish

Establish the observations, target population or future scope, sampling process, measurement definition, comparison groups, time window, and decision affected. Identify the induction type and any known selection, survivorship, nonresponse, or measurement bias. Ask at most one decisive question when the population or sample basis is unknown and changes the scope.

## Procedure

1. Publish the observed premises and the proposed generalization as separate statements. Mark each observation’s provenance and evidence state; this creates the visible induction baseline.
2. Publish the induction type—enumerative, statistical, causal, or analogical—and the bridge from sample to target scope. State which assumptions make the bridge plausible.
3. Publish the sample basis: size, diversity, selection, missing cases, measurement quality, and time coverage. Distinguish a source-backed description from an inferred representativeness claim.
4. Publish the strongest counterexample search and its result. Include cases that were not selected, negative results, subgroup differences, and plausible future exceptions where available.
5. Publish the bounded generalization with a scope limit and qualitative strength label such as strong, moderate, or weak. Replace universal wording with a population or proportion range only when that range has defensible provenance.
6. Publish the decision consequence and the next observation that would most improve or challenge the generalization. State whether the result supports action, monitoring, or further sampling.
7. Publish the current conclusion and an observable flip condition. If the sample is too biased, sparse, or mismatched to the target, hold or keep the result provisional rather than extrapolating.

## Public output contract

Return `observations`, `induction_type`, `sample_basis`, `generalization`, `scope_limit`, `counterexample_risk`, `counterexample_search`, `strength`, `decision_consequence`, and `flip_condition`. The result must distinguish observed cases from the broader claim. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels; the generalization is normally inferred, not verified directly.

## Evidence and uncertainty rules

Sample size alone does not establish representativeness. Check selection, coverage, attrition, measurement, subgroup balance, and time relevance. A counterexample can limit a universal claim without proving the opposite trend. Do not reuse the same observation as both independent support and a counterexample test. If the sample basis or target scope is missing, lower or hold the conclusion.

## Stop conditions

Stop and ask one blocking question when the target population or sample process is unknowable and different scopes would change action. Hold when the sample is materially unrepresentative, the causal claim exceeds the design, or decisive counterexample risk is unresolved. Stop when the task is a strict rule, a competing-hypothesis diagnosis, or source-quality comparison.

## Complement handoff

Hand off to `evidence-hierarchy` when the remaining question is whether the sample or study design deserves enough weight for the claim. Pass the sample basis, generalization, scope limit, and main counterexample risk. The complement should not repeat the generalization procedure.
