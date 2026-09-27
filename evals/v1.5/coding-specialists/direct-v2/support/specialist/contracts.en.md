# Contracts and invariants

Candidate `csp-contracts@0.1.1`. Use with the candidate router; this is not a registered canonical method. Apply the procedure to the user's work, without narrating private reasoning or turning these questions into an interview.

## Load or skip

Load before implementing or changing a nontrivial operation, public type, validation rule or reused component when accepted inputs, promised outputs or preserved conditions determine the design. Skip mechanical edits, an unchanged established contract, and decisions dominated only by event order or stale data whose contract is already clear. This procedure does not require those other specialist modules.

## Minimum task facts

Find the requested behavior and scope, relevant operation/type and actual caller, existing input/output/error representations, and the governing requirement or compatibility obligation. For new code, use the proposed interface and intended caller instead of inventing existing source. Distinguish accepted intent from what current code happens to do. Label inferred contracts and unknown consumer behavior; source locations and revisions identify observations, not user acceptance. Inspect available evidence before asking for a missing decision-changing rule.

## Questions that change the decision

1. Which inputs and starting states are valid, and what must be observable after success, rejection or partial failure?
2. Which relation must hold at the boundary where a caller can observe state, and which representation could silently erase a meaningful distinction?
3. Can the proposed reuse preserve this caller's guarantees, errors and ownership without imposing a stronger precondition or an unrelated policy?

## Procedure

1. **Locate the contract.** Connect the requirement to concrete parameters, types, return values, errors and side effects. Separate caller obligations from validation of untrusted input. A missing precondition is not permission to silently accept invalid public input. Record only material unresolved assumptions in the normal task artifact.
2. **Define observable relations.** Express the success postcondition against entry state and inputs, the required failure result and allowed effects, and the invariant's observation boundary. Distinguish invalid, absent, null, empty and zero where the contract does. Intermediate private state may differ if it cannot be observed and the required boundary is restored; do not demand every internal assignment satisfy a boundary invariant.
3. **Find a discriminating case.** Use the smallest valid boundary case and invalid or compatibility case that separate plausible implementations. For a loop or algorithm, connect initialization, each relevant step and the result to the relation; examine termination when progress is part of the task. Do not invent a global formal-proof requirement.
4. **Choose and implement.** Inspect likely existing operations and their real callers. Compare direct reuse, a narrow adaptation and separate behavior only where they are live options. Match defaults, domain meaning, errors, mutability and effects, not just signatures. Keep the shared rule with the responsibility that owns it; use a pure calculation when it clarifies that rule, without imposing a paradigm, abstraction or file count. Change callers and registrations whose contracts actually change.
5. **Check through the boundary.** Derive expected outcomes from the requirement, not from the implementation under test. Exercise the discriminating cases through the affected consumer; add durable coverage for a nontrivial changed rule. Preserve valid existing tests and run relevant consumer/test targets. When persisted compatibility matters, inspect a genuine old producer's encoding rather than constructing it with today's types. Report any untested boundary accurately.

## Public result and check

Deliver the requested patch or design with the resulting behavior, material contract/location, and actual check result or precise missing evidence. A test, type constraint, short contract comment or existing design note can carry the public relation; no separate contract document is mandatory. A green self-authored test does not establish completeness, historical compatibility or every caller's behavior.

## Stop, reuse and limits

Reuse the established contract until its intent, source, interface or affected consumers change. Stop comparing implementations once the material obligations support a choice, then finish implementation and required checks. If a missing business rule changes the behavior, hold that choice and ask only for that rule; continue independent preparation or changes. An unknown unrelated consumer does not automatically block every edit.

This is an LLM-use adaptation of contract reasoning, with proposed task/caller connections. It is not formal verification. Likely misuse includes encoding current bugs as intended contracts, adding assertions everywhere, and forcing distinct policies into one helper. Benefit would be weakened by missed contract defects, unnecessary abstractions, or equal outcomes with less work from current guidance under the same supplied facts.
