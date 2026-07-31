## Purpose

Use this procedure when the result of a decision depends on how another actor responds, and that actor’s result depends on the decision in return. It makes the players, available actions, incentives, information, timing, and credible commitments visible before recommending a move. It is not a license to invent a payoff table, assign probabilities, or call an outcome an equilibrium when the evidence does not support those claims.

## Use when

Use it for competitive moves, negotiation, bidding, pricing, entry or deterrence, contract design, shared standards, and other choices in which another party can adapt strategically. It is useful when the missing question is “what will they do if we do this?” or when a promise, threat, reputation, or information advantage could change the result. Repeated interaction and the possibility of cooperation should be stated rather than assumed.

## Do not use when

Do not use it for a single-actor optimization problem in which the environment has no meaningful strategic response. Do not use it for a binding rule with no discretion, a purely mechanical choice, or a situation where the supposed opponent cannot affect the outcome. Do not reduce a negotiated relationship to zero-sum competition without evidence. Do not infer rationality, hidden motives, or a numerical payoff merely because an action appears convenient.

## Inputs to establish

Establish the focal decision, the players and their decision rights, each feasible action, the outcome each player values, information available to each player, move order, and whether the interaction is one-shot or repeated. Record credible commitments, constraints, and past behavior only when sourced or supplied. Payoffs may remain ordinal or qualitative when a defensible scale is unavailable. Ask at most two concise questions, only when a missing player, action, incentive, information condition, or timing fact could change the recommended move.

## Procedure

1. Publish the focal decision and player register, including who can act, who is affected, and who can veto or delay. Mark roles as observed, user-provided, inferred, or assumed; this creates the visible game boundary. Visible output/state change: Game boundary published.
2. Publish the action and information record for each player. Show feasible actions, what each player can observe, whether moves are simultaneous or sequential, and whether the interaction repeats; this changes a vague contest to a specified structure. Visible output/state change: Structure record published.
3. Publish an incentive ledger for material outcomes. Use sourced or user-supplied consequences and label each verified, computed, inferred, assumed, unverified, or conflicted; retain ordinal comparisons when exact payoffs are not defensible. Visible output/state change: Incentive ledger published.
4. Publish the response check: compare credible best responses in a simultaneous setting, or work backward from the final decision in a sequential setting. If a dominant action is supported, say why; otherwise show relevant response pairs without pretending every motive is known. Visible output/state change: Response check published.
5. Publish candidate stable outcomes and whether there is one, more than one, or no supported candidate. Use equilibrium only when action, incentive, information, and timing assumptions are sufficiently evidenced; otherwise call it conditional and state what is missing. Visible output/state change: Outcome state published.
6. Publish the intervention levers and recommended move. Explain whether the move changes incentives, information, timing, available actions, or commitment credibility, and attach one observable response signal; this makes the strategy actionable. Visible output/state change: Move and signal published.
7. Publish the conclusion, strongest uncertainty, and observable condition that would flip the move. If a decisive payoff, player, or timing fact is absent, publish a held result and the smallest release check instead of selecting a fictional winner. Visible output/state change: Hold state published.

## Public output contract

Return a compact result with `players`, `actions`, `incentives`, `information`, `timing`, `response_analysis`, `candidate_outcome`, `equilibrium_caveat`, `move`, and `flip_condition`. A candidate outcome is not automatically desirable, fair, efficient, or inevitable. State whether it is supported, conditional, conflicted, or held. Grounds use the card evidence labels, and alternatives summarize materially different moves or commitment designs. Do not expose a private reasoning transcript.

## Evidence and uncertainty rules

Separate observed behavior from a theory about motives. A payoff claim needs a source, user-provided record, reproducible calculation, or explicit assumption; label the source and its scope. Do not fabricate probabilities, discount rates, hidden information, or rationality. A stable response pattern means that no supported unilateral change improves the stated outcome under the stated assumptions; it does not prove social desirability. A threat or promise counts only if the actor would still have a reason to carry it out when the relevant decision arrives. Mark missing, conflicting, or stale incentives as unverified or conflicted and lower the conclusion accordingly.

## Stop conditions

Stop and ask one blocking question when two plausible player sets, action sets, or timings lead to materially different moves and the user’s purpose cannot select between them. Hold when a decisive incentive, information condition, or sequence is missing. Stop without routing when there is no meaningful strategic interdependence. End when the structure, conditional response, move, evidence status, and flip signal are public; do not continue calculating to create false precision.

## Complement handoff

Hand off to `stakeholder-analysis` only when the game structure exposes material power, consent, legitimacy, implementation support, or affected-but-unrepresented groups. Pass the player register, incentives, conflicts, commitments, and unresolved uncertainty. The complement should map actors and engagement needs; it should not repeat the response analysis or manufacture missing payoffs.
