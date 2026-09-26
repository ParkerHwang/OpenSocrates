# Frozen source review procedure

After source snapshots and deterministic results are locked, the primary integrator
reviews all nine coding artifacts unblinded. No model judge panel or repair is
commissioned. Record concrete file/function references and consequences for:

1. Shared business rules and transaction paths across single/batch/capture/reversal.
2. Ownership boundaries among HTTP validation, domain transitions and persistence.
3. Whether retries/optimistic versions preserve operation-specific semantics.
4. Historical reconstruction and irreversible information assumptions.
5. Meaningful self-authored tests versus only supplied driver tests.
6. Index/query behavior and algorithmic work consistent with observed performance.

Report confirmed defects separately from hypotheses. Correlating an index choice
with a faster artifact is not a controlled causal proof. Do not count duplicate
endpoint failures caused by one shared defect as independent architectural bugs.
Do not prefer functional syntax, classes, module count or LOC without a consequence.
Assess correctness and maintainability separately; no arbitrary composite quality
score is needed. Never modify a candidate during review. Missing artifacts or
evidence stay unassessable, and unsafe or incomplete behavior remains visible.
