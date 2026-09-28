# Change impact

Guide revision: 4

After renaming or splitting a shared entry point, verify affected test callers as
well as application callers. A successful executable build does not establish that
the repository's test targets compile. Use [result verification](../assistance/verification.en.md)
for completion evidence; keep the check scoped to the changed contract.

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
   Exercise a real preceding producer's encoding for compatibility; constructing
   old data with today's type can hide absent fields. Preserve absent, null and
   explicit values before defaults when their contract meanings differ.
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


# Verify the delivered result

Guide revision: 1

Read the relevant section when a task changes shared code, delivers related
artifacts, or asks for performance measurements. Keep checks proportional to the
requested outcome. This reference does not require another policy call or a
visible checklist, and it does not add a canonical reasoning method.

## Code and callers

Identify the changed contract and its actual callers, registrations and test
targets. After a rename or split, build the affected consumers and run the
repository's relevant test command: an executable build or external API pass can
coexist with a broken test caller. Preserve valid existing test intent; update a
stale assertion only when current requirements justify it. Do not remove a test
merely to obtain a pass. Add durable behavioral coverage for a changed nontrivial
invariant; avoid tests that merely restate trivial edits. Prefer cohesive pure
domain rules and explicit side-effect boundaries where they help the project,
without treating module count, abstraction count or a programming style as proof.

## Data, narrative and display

Choose the authoritative source or computed result for each material claim.
Reconcile tables, memo text, alternatives, waitlists and final-message numbers
against it, including excluded options. Check units and actual rendered display:
people, seats and counts must not inherit currency formats. Preserve distinctions
among an absent value, null, zero and a valid zero-price item. Recompute dependent
claims after a correction; a correct JSON/workbook calculation alone does not
validate a copied explanation. Inspect all available public messages when judging
questions or commitments, and mark missing earlier messages unassessable.

## Requested performance

Fix the workload, source, host, concurrency, time limit and acceptance checks
before measuring. Run load after builds/tests finish so unrelated work does not
distort it. Separate correctness from latency, throughput and resource use; retain
warmup failures, timeouts and drain work. Diagnose read/write transaction boundaries,
locking and resource lifetime on the actual driver before tuning concurrency or
pool sizes. Failed or incomplete correctness gates leave performance diagnostic.
Do not generalize one workload's winner or infer internal reasoning from text length.

For coupled work that benefits from explicit completion tracking, use the existing
v1.1 examples [coding](verification-coding.json) or
[artifacts](verification-artifacts.json), with locale `en` or `ko`. Adapt obligations
to the task and report actual observations and evidence IDs. Required failures or
unverified checks remain open even when another check passes. Optional performance
work stays optional unless requested. Runtime `finish` is conditional advice from
caller reports, not an independent build, artifact inspection or permission.
Once relevant required checks pass and inputs are unchanged, deliver and stop.
