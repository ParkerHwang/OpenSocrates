## Purpose

Use this procedure to decompose a broad diagnostic, planning, or coverage question into a hierarchy that is mutually clear, collectively adequate, and actionable at the leaves. Select one decomposition axis at each level, keep why and how trees separate, and attach a verification or next action to every terminal branch. The tree structures the search; it does not prove that every branch is true.

## Use when

Use it when the problem is broad, causes are unclear, a plan needs coverage, or a “why,” “how,” or “what” question needs an exhaustive structure. It fits diagnostic work, risk coverage, requirements, and solution exploration where overlapping branches would cause duplicated ownership or missed work.

## Do not use when

Do not use it when the problem is a tightly coupled feedback loop that cannot be represented responsibly as a hierarchy, or when a simple list or direct calculation is enough. Do not mix causes and solutions at the same level, use “other” to hide a material gap, or keep splitting a branch after its next action is already clear.

## Inputs to establish

Establish the root question, tree type (`why`, `how`, or `what`), success measure, scope, known facts, and available checks. Choose a decomposition axis for the first level and record why it fits. Ask at most one decisive question when the root or tree type changes the analysis; otherwise state a bounded root.

## Procedure

1. Publish a measurable root question and the selected tree type. State the scope and success measure; this creates the visible tree baseline.
2. Publish the first-level branches using one decomposition axis and label that axis. Record whether each branch is observed, inferred, or a candidate requiring verification.
3. Publish the next level only where a finer split changes an action or test. At every level, show the mutual-exclusion and coverage check as a state update.
4. Publish the leaves with one verification method, data request, owner, or next action each. A leaf that remains abstract is not terminal; keep the tree open or narrow the root.
5. Publish pruned branches and the reason for each pruning, such as contradictory evidence, out-of-scope status, or duplicate coverage. Do not delete a branch merely because it is inconvenient.
6. Publish a priority order based on materiality, evidence, and actionability, not invented numerical precision. Mark branches that need a separate causal or evidence method.
7. Publish the completed tree, coverage gaps, and an observable flip condition. If a critical branch is neither testable nor bounded, hold the judgment or ask one blocking question.

## Public output contract

Return `root_question`, `tree_type`, `decomposition_axis`, `mutually_clear_branches`, `branches`, `leaf_tests`, `leaves_with_tests`, `pruned_branches_and_reasons`, `coverage_gaps`, `priority_order`, and `flip_condition`. The public result must show mutually clear branches, collectively relevant coverage, and executable leaves. Card grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels. Do not present the tree itself as proof of a causal claim.

## Evidence and uncertainty rules

ME and CE are separate checks: no overlap does not imply coverage, and coverage does not imply no overlap. A familiar formula is a candidate structure until its assumptions fit the domain. Each leaf’s evidence or test must be identifiable; unsupported branches remain hypotheses. If branches conflict or a missing branch could change the decision, disclose the gap and hold or lower the conclusion.

## Stop conditions

Stop and ask one blocking question when the root question or tree type cannot be bounded and alternatives would lead to different work. Hold when a material coverage gap has no test or when branches are interdependent enough that a hierarchy would mislead. Stop when leaves have clear actions and remaining work belongs to a causal, evidence, or decision method.

## Complement handoff

Hand off to `root-cause-analysis` when the tree’s selected branch concerns a recurring failure and needs a causal chain rather than further decomposition. Pass the root, selected branch, evidence gaps, and leaf tests. The complement should not rebuild unrelated branches.
