# Ownership and derived state

Candidate `csp-ownership@0.1.1`. Use with the candidate router; this is not a registered canonical method. Use the questions to make the change. Do not request private reasoning or publish a method recital.

## Load or skip

Load when choosing or changing authoritative state, a cache/projection, mutable shared data, snapshots or resource ownership could make consumers disagree or outlive valid data. Skip a mechanical edit, an unchanged proven ownership boundary, or a pure calculation with already explicit inputs and no competing representation. A variable appearing twice does not itself justify a redesign.

## Minimum task facts

Identify the meaningful value, its source and lifetime, producers/writers, relevant consumers, and the consistency/freshness expectation. Read actual types, update paths, return values and aliases; for resources, find acquisition and release responsibilities. Separate accepted intent, source observations and inferred relationships. If source is new, use explicit proposed ownership. If version, isolation or lifetime is unknown, preserve that uncertainty instead of assuming all readers see the newest value.

## Questions that change the decision

1. Which representation is authoritative for this decision, and which is a derived view, cache, user draft or historical snapshot with its own meaning?
2. Who can mutate or retain each value, and could an alias, early release or late update make another consumer observe an unintended state?
3. What inputs and version must a consumer share to agree with the required result, and where should calculation, invalidation or copying happen?

## Procedure

1. **Trace the relevant dataflow.** Follow the value from input or stored source through mutation, calculation and publication to the affected consumer. Include immediate return paths, later reads, callbacks or render paths only where they consume the changed value. Label source state, derived values and independent snapshots. Do not treat equal-looking fields as interchangeable; historical truth is not necessarily today's recomputation.
2. **Establish authority and ownership.** Identify who can write, who may borrow or retain, and when data or a resource becomes invalid. Check shared references, shallow copies, closures, lazy iteration and transfer semantics when applicable. Decide whether the needed contract calls for a live view, stable snapshot or owned value. Use language/runtime facilities that fit the project; Rust's borrow rules are not a mandatory design for other languages.
3. **Choose the update and calculation boundary.** Prefer deriving redundant values from the appropriate authoritative inputs when that satisfies semantics and cost. If materialization, a draft or cache is justified, define its version/freshness and invalidation/update owner. Place deterministic calculation where affected consumers can share the same rule; keep I/O, mutation, clock/random inputs and lifetime management explicit when they affect the result. This may be a local function or existing method, not a mandatory new layer.
4. **Implement the consistency relation.** Connect producers and consumers to the chosen rule or snapshot. Preserve unaffected public type, error and ownership contracts; when the user explicitly changes one, propagate that authorized change to its affected consumers instead of freezing the previous contract. If consumers must agree at one logical version, identify the snapshot or atomic update that enforces it. If eventual consistency is intended, retain its stated lag/reconciliation semantics instead of silently strengthening them. Inspect actual storage/framework guarantees for concurrent reads; algebraic agreement alone is not atomicity. Do not impose copying everywhere or a universal cache policy.
5. **Check an observable distinction.** Exercise a mutation or lifetime change and the affected consumers under the contractually relevant version. Check that a retained result stays stable when promised, or that a live view changes when promised; test alias mutation, invalidation or cleanup only when implicated. Compare observable values against independently derived expectations, not two paths that reuse the same potentially wrong function. Run affected caller/test targets and preserve any remaining coverage limit.

## Public result and check

Deliver the requested artifact with the material source-of-truth/ownership choice, affected locations and actual check results. A short explanation, meaningful type, focused test or existing design record is sufficient. Identify any freshness/lifetime guarantee still unverified. Passing projection checks does not establish untested historical, concurrent or remote behavior.

## Stop, reuse and limits

Reuse the ownership/dataflow conclusion while sources, writers, consumers and consistency requirements remain unchanged. Stop tracing once material paths support the choice, then complete the change and its checks. If a missing historical fact or external lifetime guarantee blocks one promise, hold that promise and continue independent work. Inspect accessible code before asking; do not invent a new approval or memory requirement.

This is an original proposed composition informed by ownership/borrowing and state-structure guidance. It is not one established universal methodology. Misuse includes deleting meaningful snapshots, flattening independent authorities, excessive cloning and over-normalization. Benefit would be weakened by continued stale/aliased results, loss of legitimate snapshot semantics, or greater work without improved artifacts under equal facts.
