# Change impact

Guide revision: 2

Use this guide before changing shared behavior, a public type or interface,
state ownership, configuration, or registration consumed by another module.
For a local mechanical edit with unchanged contracts, finish directly.

1. Identify the accepted intent and the exact contract being changed. Recheck
   remembered decisions against the current source and configuration.
2. Trace concrete incoming and outgoing relationships from definitions to
   callers, registrations, generated interfaces, and affected tests. Inspect
   relevant data shapes, error propagation, retries, cancellation, side effects,
   resource lifetime, and ordering. For persisted data, distinguish historical facts
   from current source facts: identify information absent from older records before
   promising compatibility, and state the limit rather than inventing past values.
   Record file or symbol locations.
3. Distinguish lexical search hits, structurally established relationships,
   inferred contracts, and unresolved dynamic behavior. A reference does not
   prove a runtime path executes. A search miss does not prove no consumer exists.
   Inspect relevant configuration or runtime evidence for dynamic dispatch.
4. Identify necessary co-edits and the smallest verification that exercises the
   changed contract and affected uses. Widen only when a failure or material
   uncertainty makes the narrower check insufficient.

Refresh a negative caller claim when source inventory, configuration, generated
interfaces, or untracked files change. Stop tracing when the material relationships
are covered sufficiently for the change or the remaining area is explicitly
unknown. Complete with the changed contract, evidenced affected uses and co-edits,
verification results, coverage limit, and unresolved risk. Do not describe a
lexical inventory or green test suite as exhaustive dependency proof.
