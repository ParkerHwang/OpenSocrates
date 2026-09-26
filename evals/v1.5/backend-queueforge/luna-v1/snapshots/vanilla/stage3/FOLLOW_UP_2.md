# Final bounded follow-up: correctness and load feedback

The adjacent FEEDBACK.json contains this implementation's independently collected
API checks and preliminary load results, under the frozen common workload. Use
those observed failures/bottlenecks to make the smallest justified repair or
optimization. You have the same fixed final-session budget as the other version.

Preserve every current API, tenancy, fencing, idempotency, quota, pagination,
migration and durability requirement. In particular keep SQLite WAL and
synchronous=FULL; do not turn off fsync, remove validation, change response meaning,
skip state persistence, fake metrics or special-case evaluator identifiers.

Inspect existing callers, SQL access paths, lock duration, repeated whole-state
work, allocations and indexes. Reuse business rules across endpoints. Improve only
where source evidence or measurements justify it. A load result obtained with
failed correctness gates is diagnostic, not evidence of useful speed.

Run relevant behavior/race tests and document the changed boundary and remaining
limits. Do not read sibling code/results, evaluator source or hidden answers.
No stronger model, subagent, external service or new runtime dependency. Preserve
the supplied dependency lock, Go toolchain, resource limits and artifact contract.
Keep all owned servers within this workspace and stop them before finishing.
This is the last planned development call; do not invent favorable results.
