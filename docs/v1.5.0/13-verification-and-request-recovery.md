# Verification and decision request recovery

Status: bounded implementation revision after the hard coding/office comparison.
This document records the acceptance rules before implementation checks. The
release candidate remains unpublished; model profiles remain inactive candidates.

## Evidence and scope

The baseline is `08c123a3803d7bfd1ac5e8cfb33c61d02894c98c`, assistance guide 8,
and candidate ZIP SHA-256
`f26b77374e38261acd3296739093a4e388f1cd25cdef48a2b3de16dec0417b7d`.
The [hard-task report](../../evals/v1.5/hard-tasks/v1/REPORT.md) preserves the
18 original calls, timeouts, artifacts and usage. Its
[source review](../../evals/v1.5/hard-tasks/v1/SOURCE_REVIEW.md) distinguishes
generated-program defects from product and measurement defects.

Concrete product changes address opaque request rejection and premature mutation
of decision-session availability on invalid input. Guidance changes address
incomplete caller/test migration and disagreement among data, narrative and units.
They do not fix historical candidate programs or turn their failures into passes.
No subagents, new model calls, model judges or outcome reruns belong to this revision.

## Decision boundary

- Add `prepare` with only `operation` and `locale`. Return a fresh opaque context
  handle, epoch/revision zero, an alphanumeric decision ID and a draft `select`
  envelope. Semantic fields are null placeholders, explicitly requiring review;
  an unchanged draft is rejected rather than silently classified or routed.
- Return the existing closed vocabulary and limits so the caller can fill observed
  participation and routing features, including contraindications. Preparation
  neither selects a method nor changes the current session or acknowledgment state.
  Reuse valid identity fields; preparation is not a new mandatory per-decision call.
- Preserve existing valid requests, reason codes, canonical content, fail-open
  behavior and the 16,384-character input bound. Diagnose rejected requests with
  known field paths and static constraints/allowed values only. Never echo rejected
  values, unknown field names, prompts, paths or supplied digests.
- Validate the full request before changing the current context or delivery state.
  An invalid routing payload or unknown method cannot erase valid acknowledgments.
- One-shot transport accepts one JSON document, including pretty-printed JSON.
  Multiple requests require `--stream` with one complete JSON document per line.
  Reject ambiguous duplicate keys and non-JSON numeric constants, without raw input
  in the diagnostic. Selection remains stateless across processes and zero-model.

## Completion and verification

Use existing v1.1 public obligations for the checks required by the actual task.
Complete coding and office examples use that unchanged schema. A required test
failure or missing artifact reconciliation prevents conditional `finish` even if
the caller reports API/data success. Independent work stays ready; optional checks
do not become required. Evidence references remain caller assertions, never proof
that the runtime compiled code or inspected a workbook.

Load the short EN/KO verification reference only when relevant: changed shared
contracts require caller and test-target checks; multiple artifacts require data,
narrative and unit reconciliation; requested performance requires correctness and
workload qualification before throughput claims. Preserve functional programming
or decomposition when it improves the actual contract, without imposing a style,
module count, thread count, pool size or visible checklist as a quality proxy.

No new schema, SQLite layout, profile, method, hook or model-selection policy is
needed. Existing documentation retrieval and scoped memory contracts are preserved.

## Public improvement cycle

- `plan_objective_measure` — **verified baseline**: historical request failures and
  incomplete verification are recorded above. Measure deterministic request recovery,
  state preservation and completion decisions; model-quality improvement is unverified.
- `do_scope` — primary agent only; reversible source and EN/KO references, disposable
  fixtures, generated packages and feature-branch handoff. Keep all historical evidence,
  the active installation, account settings and user-owned agent definition unchanged.
- `check_rule` — replay malformed envelope cases and corrected requests; reject
  input canaries without echo; preserve previous acknowledgments after rejection;
  verify all 48 canonical methods in both locales; exercise required and optional
  completion transitions through source and native launchers. Run the required
  source/native/package gates, including frozen SQLite and external/embedded schema
  bytes, then reconcile CI on the pushed commit. Stop on privacy or migration failure;
  repair only diagnosed failures, retain them, and do not repeat unchanged passing gates.
- `act_standardize_decision` — **verified**: source/native gates passed; adopt the
  request/state fixes and completion examples as qualified in the [revision report](../../evals/v1.5/revision-v4/REPORT.md).
  Keep revised guidance provisional as model-behavior evidence:
  no new outcome call means no measured quality, efficiency or billing gain. The
  next model evaluation, if separately requested, should target these changed seams
  rather than repeat the entire Sol/Luna matrix.
