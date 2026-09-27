# State transitions and failure

Candidate `csp-transitions@0.1.1`. Use with the candidate router; this is not a registered canonical method. Use the questions to implement the task, not to narrate private reasoning or demand a user-led design exercise.

## Load or skip

Load when operation order, partial failure, cancellation, retries or concurrent actors can change correctness: a job lifecycle, asynchronous UI update, transaction or resource acquisition. Skip a pure calculation with a clear contract, a mechanical edit, or an unchanged transition already covered. Do not introduce distributed-system machinery into a local operation that has no such boundary.

## Minimum task facts

Identify the relevant state and events, actors that can change it, the required success/failure behavior and externally visible effects. Read the actual entry points, async callbacks, storage/API semantics and resource lifetime relevant to that decision. Establish retry identity, cancellation and visibility requirements only where present. Distinguish accepted guarantees, observed behavior and inferred scheduling assumptions. Missing atomicity or provider guarantees remain unknown; a mock cannot establish them.

## Questions that change the decision

1. Which state-and-event pairs are allowed, and when does an attempted change become visible or durable to each observer?
2. If failure, cancellation or another actor intervenes between two effects, what state and response can remain, and who can recover it?
3. Does a repeated request mean the same intent, and can the caller distinguish rejection, completed work and an unknown outcome without creating a second effect?

## Procedure

1. **Bound the transition.** Use the smallest state representation that distinguishes permitted actions. Map each relevant event to its guard, next state, response/error and effects; keep unchanged fields explicit where omission would hide a bug. Separate a forbidden outcome from a required eventual outcome. Name environmental assumptions for progress instead of promising that a retry loop must succeed.
2. **Place effects and observation points.** Trace actual writes, returned values, notifications, callbacks and acquired resources. Identify which changes must be indivisible and which may be staged. Locate the real transaction, lock, version check or ownership boundary; do not infer it from a function name. A local transaction does not make an external request atomic. Choose staging, reconciliation or compensation only when the task needs it and the operation supports it; some effects cannot be undone.
3. **Challenge the decisive gap.** Examine a successful path and the smallest failure/interleaving that could violate the required relation. Include cancellation before versus after commitment, or an older callback arriving after a newer intent, when applicable. Separate definitely-not-performed from outcome-unknown. Never interpret timeout alone as rollback. Determine who closes, releases or retains a resource on each relevant exit.
4. **Choose recovery and implement.** Preserve operation-specific guards. For retryable effects, establish logical operation identity, its caller/tenant scope, payload mismatch handling, record lifetime and the promised replay response. Inspect whether deduplication and the mutation are committed together; if not, handle the exposed gap without promising exactly-once delivery. Do not derive sameness from equal payloads alone. For competing actors, choose a mechanism supported by actual storage/runtime semantics and make rejected/stale transitions observable as required. Keep the smallest adequate design.
5. **Exercise the boundary.** Check the happy path and the identified negative sequence through the actual consumer. Use controlled ordering, failure injection or a representative concurrency test when relevant; avoid sleeps as the sole proof of order. Assert both state and required response/effect counts, including cleanup. A unit simulation validates its model only; leave real provider/crash durability unverified if not tested. Preserve independent required failures even when a happy-path test passes.

## Public result and check

Deliver the requested change and a concise explanation of the material transition/recovery choice, its source boundary and actual checks. A small transition table, test trace or code comment may expose the contract when useful; no new diagram or state-machine framework is required. Explain an unresolved outcome to its affected caller instead of claiming success or rollback.

## Stop, reuse and limits

Reuse the established transition model until relevant events, effects, source or guarantees change. Stop exploring schedules when the identified risk has an adequate implementation and check within scope; do not claim exhaustive concurrency proof. A missing external guarantee holds only the guarantee-dependent choice. Continue independent local work and identify the smallest needed evidence or user decision without reopening settled authority.

This proposed composition adapts state-machine specification and idempotent-API design. It is not a formal model check or a universal retry recipe. Misuse includes needless locks/state enums, treating all errors as retryable, and adding an outbox without a demonstrated gap. Equal failures, new liveness defects or added machinery without useful outcome improvement under the same facts would weaken its benefit.
