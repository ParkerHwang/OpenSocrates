## Purpose

Use this procedure to test whether a familiar rule, cost, workflow, or architecture is genuinely necessary or merely inherited. Decompose the problem into claims and constraints, verify each one, and reconstruct an option from the constraints that survive. The procedure protects against both cargo-culting and reckless reduction: a constraint is not discarded just because it is inconvenient, and a physical possibility is not automatically a viable plan.

## Use when

Use it when “that is how it is done,” an industry convention, a historical dependency, or an assumed cost structure blocks a high-leverage redesign. It fits pricing, product architecture, operating processes, resource allocation, and requirements where the user wants to challenge the basis of an existing choice. It is useful when a stale option set appears to inherit assumptions that no longer hold.

## Do not use when

Do not use it for a validated standard procedure that the task only asks you to execute, or when a binding rule, safety constraint, legal obligation, or externally fixed interface cannot be discarded. Do not treat preference, budget, schedule, or social coordination as purely physical facts. Do not promise a redesign from unverified assumptions or omit implementation constraints after decomposition.

## Inputs to establish

Establish the target outcome, current approach, stated requirements, constraints, resources, dependencies, and the reason the current approach is believed necessary. Separate hard constraints, negotiable constraints, conventions, and unknowns. Ask at most two decisive questions, and only where the answer changes the reconstruction. Identify any high-stakes rule that must remain in force.

## Procedure

1. Publish the target outcome and current approach in one sentence, then state the boundary and success measure. This creates a visible baseline that can be compared with a reconstructed option.
2. Publish a decomposition of the approach into atomic requirements, dependencies, and asserted constraints. Mark each item as user-provided, source-backed, inferred, or assumed; this changes the state from “given” to “to be verified.”
3. Publish a necessity verdict for each constraint: physically or logically necessary, externally binding, contingent, preference-based, or unverified. Attach the test or source that supports the verdict.
4. Publish the surviving constraint set and remove only the assumptions that failed verification. If a disputed item could materially affect safety, legality, or feasibility, keep it as an explicit unresolved constraint rather than silently removing it.
5. Publish a reconstruction built from the surviving constraints. State the resource, time, dependency, and coordination implications so the redesign is not merely physically imaginable.
6. Publish a delta from the conventional approach: what changes, which assumption enabled it, and what new risk or trade-off appears. Add a small validation action for every unverified requirement.
7. Publish the derived requirements, reconstructed option, and an observable flip condition. If an irreducible constraint or decisive input is missing, use a provisional or held conclusion instead of claiming a breakthrough.

## Public output contract

Return `irreducible_constraints`, `derived_requirements`, `reconstructed_option`, `assumptions_reintroduced`, `reintroduced_assumptions`, `conventional_delta`, `new_risks`, and `flip_condition`. The top line states whether the redesign is supported, provisional, or held. Distinguish a physically possible option from one that meets the user’s cost, time, safety, and governance requirements. Card grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels; do not present an unlabeled convention as evidence.

## Evidence and uncertainty rules

“Necessary” requires a logical, physical, contractual, safety, or other named basis; inconvenience is not proof of necessity. A source that describes common practice supports prevalence, not inevitability. Calculations must state inputs and units. If a reconstruction relies on an unverified dependency, the conclusion may be a bounded hypothesis but not a strongly supported recommendation. Preserve conflicts rather than averaging incompatible constraints.

## Stop conditions

Stop and ask one blocking question when the target outcome or non-negotiable safety/legality boundary is unclear and different answers produce different reconstructions. Hold the result when an irreducible constraint or required input cannot be established. Stop the method when every relevant constraint is externally fixed or when the remaining work is ordinary option comparison, evidence verification, or implementation.

## Complement handoff

Hand off to `morphological-analysis` when the surviving requirements can vary across several coherent dimensions and the next task is to explore combinations. Pass the derived requirements, preserved constraints, and feasibility exclusions. The complement should not repeat decomposition or re-litigate which assumptions were removed.
