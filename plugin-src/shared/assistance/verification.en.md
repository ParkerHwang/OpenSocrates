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
