## Purpose

Use this procedure to expose how claims, grounds, objections, and rebuttals support or weaken a conclusion. It creates an auditable argument map rather than a free-form mind map, so shared premises, unsupported links, and unresolved objections remain visible. The procedure can clarify a dispute before a decision, but it does not make a premise true merely by placing it in a neat structure.

## Use when

Use it when a policy, legal, strategic, research, or product argument contains several nested claims and it is unclear which evidence supports which conclusion. It fits disputes with multiple objections, rebuttals, or shared assumptions. Use it when the main task is to disentangle support and attack relationships, then state the resulting strength or hold condition.

## Do not use when

Do not use it for a simple list, direct calculation, or a task whose only issue is source quality. Do not draw association, chronology, or topic similarity as if it were logical support. Do not infer that a conclusion is sound because its map is complete, and do not hide value choices inside neutral-looking premises.

## Inputs to establish

Establish the target conclusion, decision or question, relevant scope, direct grounds, shared premises, objections, rebuttals, and available sources. Identify whether each item is a fact, rule, inference, preference, or assumption. Ask at most two decisive questions when a missing claim or scope would change the map; otherwise mark the gap and proceed.

## Procedure

1. Publish the top-level conclusion and the decision it is meant to support. Mark its current status as supported, provisional, conflicted, or held; this creates the visible argument state.
2. Publish direct supporting premises and distinguish them from jointly required premises. Draw only explicit support links, and label each link as stated, inferred, or unverified.
3. Publish the sub-grounds under each premise, preserving the claim-to-ground hierarchy. Attach source or calculation references where available and record unsupported links as gaps.
4. Publish objections as separate attack branches, then publish rebuttals only where they answer the objection’s actual claim. Mark an objection as unresolved when the rebuttal changes neither its evidence nor its scope.
5. Publish hidden or shared premises and test whether removing each one changes the conclusion. This state change identifies the smallest material weakness rather than counting every sentence equally.
6. Publish a map verdict: strongest supported link, weakest link, unresolved objection, and any redundant or irrelevant branch. Distinguish map completeness from premise truth and inference validity.
7. Publish the conclusion’s current evidence state and an observable flip condition. If a material premise is missing or a decisive objection remains unresolved, lower or hold the conclusion instead of silently repairing the argument.

## Public output contract

Return `claim_ground_objection_map`, `top_level_conclusion`, `direct_grounds`, `shared_premises`, `subgrounds`, `objections`, `rebuttals`, `unsupported_links`, `map_verdict`, and `flip_condition`. The public result should show a compact claim-ground-objection map, not a private reasoning transcript. Grounds carry **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels. Include only material branches in the card and send detail to trace when needed.

## Evidence and uncertainty rules

A source can support a claim without supporting the link from that claim to the conclusion. Evaluate directness, relevance, and scope separately. Shared premises must not be counted as independent support twice. A rebuttal that attacks a witness or measurement may weaken the support link without proving the opposite conclusion. Conflicting credible grounds require a visible conflict and a held or lowered result unless a stated precedence rule resolves it.

## Stop conditions

Stop and ask one blocking question when the target conclusion or decision scope is absent and competing interpretations would create different maps. Hold when a material premise cannot be supported or a decisive objection has no resolution. Stop when the task is only source ranking, simple calculation, or a stable definition; hand off to the more specific method.

## Complement handoff

Hand off to `evidence-hierarchy` when the map shows that source quality, study design, or directness—not argument structure—is the remaining bottleneck. Pass the claim-to-source links, unsupported links, and material conflict only. The complement should not rebuild the full argument map.
