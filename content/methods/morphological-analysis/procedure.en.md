## Purpose

Use this procedure when a complex solution can be varied across several independent dimensions and the option space needs to be explored systematically. It decomposes the problem into coherent parameters, lists plausible values for each, creates combinations, removes incompatible combinations with explicit rules, and selects representative concepts for further testing. The output is a transparent design space and screened candidates, not a promise that every combination is feasible or equally valuable.

## Use when

Use it for policy, service, product, operating-model, or strategy design where qualitative alternatives matter and no single numeric model captures the problem. It is useful when teams repeatedly optimize one dimension, miss combinations, or need to compare conventional and non-obvious configurations. Use four to eight dimensions when possible, and define each so that changing one does not silently change another.

## Do not use when

Do not use it when dimensions cannot be made coherent, when the problem is a binding rule, or when a small set of known options already answers the question. Do not create a giant combination space that hides infeasibility or overwhelms the decision. Do not score every cell with invented utilities, probabilities, or feasibility percentages. If a combination could create safety, legal, accessibility, or privacy harm, screen it out or escalate before considering it as a candidate.

## Inputs to establish

State the design question, objective, users or affected actors, hard constraints, time horizon, and the decision the option space must support. Propose independent dimensions with definitions and a short set of values for each; record evidence, assumptions, incompatibilities, and resource limits. Ask at most two decisive questions, such as “Which dimension represents a real choice rather than a consequence?” or “Which pairing is impossible for a known safety or operating reason?”

## Procedure

1. **Bound the design space.** State the problem, objective, actors, constraints, and exclusions; decide what counts as a distinct solution. **Visible output/state change:** publish the design boundary and a criterion for keeping dimensions separate.
2. **Define dimensions and values.** Choose coherent dimensions and list meaningful values, including a baseline and at least one non-obvious value where justified. **Visible output/state change:** publish the parameter matrix with definitions, evidence states, and unresolved assumptions.
3. **Generate combinations.** Combine values across dimensions without early preference; use a manageable sample when the full space is large and explain the sampling rule. **Visible output/state change:** publish the candidate combination set and the dimensions represented in each concept.
4. **Check pairwise coherence.** Remove combinations that violate hard constraints, conflict with known dependencies, duplicate another option, or require resources that are unavailable. Keep uncertain combinations flagged rather than silently deleting them. **Visible output/state change:** publish rejected combinations with reasons and an uncertainty list.
5. **Select representative concepts.** Choose conventional, boundary-pushing, and balanced configurations that cover different trade-offs; describe who gains, who bears cost, and which feasibility check matters. **Visible output/state change:** publish a screened shortlist and its comparison criteria without fabricated scores.
6. **Test and decide.** Select a reversible prototype, simulation, consultation, or small pilot for the most decision-relevant unknown. **Visible output/state change:** publish the preferred candidate or hold, the test owner, evidence needed, and the condition that would change the selection.

## Public output contract

Return the design question, parameter matrix, combination rule, coherence exclusions, representative concepts, feasibility screen, and next test. State which dimensions are evidence-backed and which are assumed. The Conclusion Card should show the candidate worth testing and the trade-off or constraint that drives it, with an observable flip condition; keep the full combination space in the trace or build artifact.

## Evidence and uncertainty rules

The matrix organizes possibilities; it does not establish demand, safety, cost, or performance. Do not infer that a combination is valid because each value is valid alone. Record pairwise incompatibilities, dependencies, and unknowns. Use ordinal terms such as plausible, blocked, or needs check only with a stated rule, and avoid false precision. When an untested combination could materially change the recommendation, keep the conclusion provisional and name the smallest safe evaluation.

## Stop conditions

Stop when the dimensions overlap, the values cannot be defined, hard constraints are unknown, or combination growth prevents a meaningful screen. Hold selection when feasibility depends on an unverified dependency or when a candidate could create preventable harm. Escalate specialist safety, accessibility, legal, or privacy constraints before testing.

## Complement handoff

Hand off to first-principles when the dimensions rest on conventional assumptions that should be reduced to irreducible constraints. Pass the public design boundary, matrix, incompatible pairs, shortlist, and open checks; the complement should challenge assumptions without rebuilding the whole combination space.
