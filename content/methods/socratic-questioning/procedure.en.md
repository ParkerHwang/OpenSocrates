## Purpose

Use this procedure when a few answers from the user can materially change the question, evidence standard, or recommendation. It uses questions to surface assumptions, meanings, grounds, alternatives, and implications while still carrying responsibility for a bounded answer. Questions are a decision aid, not a way to avoid answering or to lead the user toward a predetermined conclusion.

## Use when

Use it when the user’s claim, terms, scope, evidence, or desired consequence is unclear and a small amount of clarification would change the route. It fits coaching, teaching, deliberation, self-review, and collaborative problem definition. Use it for a judgment only when the missing answers are genuinely decisive; otherwise state a reasonable assumption and proceed.

## Do not use when

Do not use it for a mechanical task, a request that can be answered safely with a bounded assumption, or a situation where repeated questions would merely delay action. Do not ask for private reasoning, personal information that is unnecessary for the decision, or an open-ended interview. Do not use leading questions that presuppose the desired answer.

## Inputs to establish

Establish the user’s claim or decision, the terms that need clarification, the current scope, available evidence, alternatives already considered, and the consequence the user cares about. Select no more than three decisive questions. For each question, state what answer would change: the framing, evidence status, option order, or completion state. If the user does not answer, define a safe fallback.

## Procedure

1. Publish a neutral restatement of the claim or decision and the unresolved point. This creates a shared question state without implying agreement.
2. Publish up to three bounded questions, each with its decision effect and a short answer format or allowed range. The visible question set is the only clarification request; do not add a hidden questionnaire.
3. Record each answer as user-provided, unanswered, or ambiguous, and publish the immediate effect on scope, terms, evidence, or alternatives. This makes the judgment state change visible.
4. Publish the strongest supporting ground and one credible counterexample or alternative raised by the answers. Distinguish an answer from evidence about the world.
5. Publish a provisional conclusion or the next bounded action, including what can be done without another question. If an answer changes the route, state the new route in plain language rather than hiding the change.
6. Publish the remaining uncertainty and the observable condition that would flip the conclusion. Mark unanswered questions as assumptions only when the assumption is safe and reversible.
7. Publish the current answer, why it follows from the answered inputs, and whether the task is complete, provisional, or held. If the decisive question remains unanswered, do not manufacture certainty.

## Public output contract

Return `no_more_than_three_decisive_questions`, `decisive_questions` (maximum three), `why_each_matters`, `answers_and_status`, `decision_effects`, `provisional_conclusion`, `remaining_uncertainty`, `next_action`, and `flip_condition`. Questions must be visible and bounded; the final card must not expose a transcript of private deliberation. At most two unresolved uncertainties belong in the card. Grounds carry the evidence-state labels **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted**.

## Evidence and uncertainty rules

User answers establish preferences, scope, or context unless they also provide checkable evidence. Do not upgrade an answer to **verified** without an identifiable supporting source. An unanswered decisive question leaves the affected claim **assumed**, **unverified**, or **held**, depending on materiality. If the answers conflict, show the conflict and ask no additional question unless one short question can resolve it safely.

## Stop conditions

Stop and ask the selected questions when proceeding without them would change the action materially. Ask no more than three; if the user cannot answer, continue with a reversible assumption or hold the judgment. Stop questioning once the route and conclusion are stable enough to act, or when the task is mechanical and no judgment remains.

## Complement handoff

Hand off to `assumption-mapping` only when the answers expose several material assumptions that need prioritization and testing. Pass the answered/unanswered question set, assumption status, and current flip condition. The complement should not repeat the Socratic questions or turn them into an unbounded interview.
