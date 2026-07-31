## Purpose

Use this procedure to test whether a classification or decomposition is mutually exclusive and collectively exhaustive at the same level. Fix one classification axis, test overlap and gaps separately, and keep category granularity consistent. The result is a defensible classification rule with known boundary cases, not a promise that every real-world category is naturally clean.

## Use when

Use it when categories, ownership buckets, options, requirements, causes, or issue-tree branches duplicate or omit material cases. It is useful for reviewing an existing classification and as a focused check inside a logic tree or executive structure. Use it when the classification rule itself, rather than a factual source, is the decision bottleneck.

## Do not use when

Do not use it when natural overlap is the phenomenon being studied, when categories intentionally represent different axes, or when a binding taxonomy must simply be applied. Do not mix age, geography, intent, and process stage at one level. Do not hide a large missing class behind “other,” and do not force false exclusivity where membership is genuinely multi-label.

## Inputs to establish

Establish the universe being classified, the decision purpose, the candidate categories, the proposed single axis, inclusion rule, exclusion rule, and known boundary cases. State whether categories are single-label or multi-label. Ask at most one question when the universe or classification purpose is materially ambiguous; otherwise state a bounded universe.

## Procedure

1. Publish the universe, decision purpose, and one classification axis in a single sentence. This fixes the visible classification state and prevents mixed criteria.
2. Publish the candidate categories with one inclusion and one exclusion rule each. Mark category boundaries as explicit, inferred, or unverified.
3. Publish the mutual-exclusion test using plausible cases that could fit two categories. For each overlap, merge, re-cut, or explicitly allow multi-label membership and record the state change.
4. Publish the collective-coverage test using edge cases and known observations. Add a category only when the missing case is relevant to the stated universe; otherwise narrow the universe and disclose the exclusion.
5. Publish a granularity check across the level: compare category abstraction, size, and decision use. Rework a category that is a hidden subcategory of its peers or too broad to support action.
6. Publish boundary cases, the final classification rule, and any intentionally unresolved overlap. Do not use a vague “other” bucket for a material share of the universe.
7. Publish the classified result, overlap/gap verdict, and an observable flip condition. If the axis cannot support the decision or an important case cannot be classified, hold the classification rather than forcing a label.

## Public output contract

Return `classification_universe`, `classification_rule`, `classification_axis`, `categories`, `inclusion_rules`, `exclusion_rules`, `overlap_gap_check`, `overlap_check`, `coverage_check`, `granularity_check`, `boundary_cases`, and `flip_condition`. The public output must distinguish ME from CE and state whether the classification is single-label or multi-label. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels; the categories themselves are not evidence of prevalence.

## Evidence and uncertainty rules

ME and CE are logical coverage tests, not empirical proof that the categories are useful. An example can reveal overlap or a gap without establishing how common it is. Keep source-backed observations separate from category design choices. If a material category is missing, a disputed case remains unresolved, or the axis changes the decision, label the result provisional or held.

## Stop conditions

Stop and ask one blocking question when the universe or classification purpose cannot be bounded. Hold when the category axis cannot represent material cases without misleading overlap, or when a missing category changes the decision. Stop once the rule passes ME/CE at the required scope and the remaining work is structural decomposition or option comparison.

## Complement handoff

Hand off to `logic-tree` when the validated categories are the first level of a broader diagnostic or plan and need recursive branches plus leaf tests. Pass the universe, axis, final categories, boundary cases, and coverage verdict. The complement should not repeat the MECE checks at the same level.
