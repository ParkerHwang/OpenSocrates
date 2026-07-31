## Purpose

Use this procedure to turn a sound judgment or analysis into an executive answer whose governing thought appears first. Group reasons at a common level, verify that each upper statement summarizes its supporting detail, and choose one consistent order for peer points. It improves communication structure; it must not be used to make an unsettled judgment look settled.

## Use when

Use it for reports, decision memos, executive summaries, proposals, presentations, or any request to lead with the answer. It fits a long analysis whose conclusion is already sufficiently supported but whose delivery is difficult to scan. Use it after the underlying judgment and evidence have been checked.

## Do not use when

Do not use it to skip missing evidence, hide a material conflict, or choose a conclusion that the analysis has not made. Do not force reasons into three groups when they overlap or omit a decision-relevant point. Do not place background before the answer when a direct conclusion is available, but do preserve necessary scope and uncertainty in the card.

## Inputs to establish

Establish the governing question, current conclusion, material grounds, alternatives, audience decision, scope, and evidence state. Decide whether peer reasons will use deductive order, time order, structural order, or importance order. Ask at most one question when the audience decision or conclusion is missing; otherwise state the intended audience and proceed.

## Procedure

1. Publish the governing question and a one-sentence governing thought at the top. Mark the conclusion as supported, provisional, conflicted, or held; this creates the visible communication state.
2. Publish three to four reason groups that jointly support the governing thought. Give each group a one-line key message and record overlap or missing coverage as a structural gap.
3. Publish the supporting detail under each group and verify the vertical relationship: the key message must summarize its details, not introduce a new claim.
4. Publish the horizontal order for peer groups—deductive, time, structure, or importance—and apply it consistently. Record any alternative ordering that would materially change the interpretation.
5. Publish the top-line answer, grouped reasons, and supporting detail in top-down order. Keep necessary assumptions, conflicts, and unverified grounds visible rather than polishing them away.
6. Publish the strongest alternative or counterargument and the reason it was not selected. If the underlying judgment is not settled, change the output state to provisional or held instead of presenting a definitive executive answer.
7. Publish the final card-ready structure and an observable flip condition. Confirm that the requested deliverable, explicit constraints, evidence checks, and uncertainty disclosures are present.

## Public output contract

Return `top_line_answer`, `governing_thought`, `grouped_reasons`, `reason_groups`, `supporting_detail_order`, `scope_and_assumptions`, `alternatives_considered`, `completion_check`, and `flip_condition`. The first sentence is the conclusion; background follows only as support. Keep card grounds to material claims and label them **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted**. The structure may be embedded in a memo, but it must retain the conclusion-first order.

## Evidence and uncertainty rules

Good structure does not upgrade evidence. Every reason group must have a visible basis, and inferred links must not be written as direct facts. If peer groups conflict, show the conflict rather than averaging it into a smooth narrative. If a missing ground, alternative, or completion item could change the answer, use a provisional or held conclusion and name the missing item.

## Stop conditions

Stop and ask one blocking question when there is no stable governing question or audience decision and multiple top lines would be materially different. Hold when the underlying judgment is unsupported, conflicted, or incomplete. Stop when the answer is already clear and the remaining task is mechanical formatting; do not add method commentary to that work.

## Complement handoff

Hand off to `argument-mapping` when the reason groups reveal unresolved support, objection, or shared-premise structure. Pass the governing thought, material reason groups, and the single unresolved link. The complement should not reorder the finished executive answer or produce a second full pyramid.
