## Purpose

Use this procedure to compare independent evidence streams so that one source, method, theory, or investigator does not carry more confidence than it deserves. It defines the claim and required evidence, checks independence rather than counting citations, and reports convergence, conflict, and gaps. Agreement is informative only when the streams are meaningfully different and relevant to the same claim.

## Use when

Use it when a single source or method may be biased, qualitative and quantitative evidence are mixed, or interested parties provide competing accounts. It fits verification of important claims, program evaluation, research synthesis, and decisions where corroboration or conflict would change the action.

## Do not use when

Do not use it when all sources repeat one underlying dataset, when the issue is a value preference, or when a direct formal rule decides the case. Do not count multiple copies of one report as independent, average a conflict away, or collect streams that answer different claims without stating the mismatch.

## Inputs to establish

Establish the focal claim, decision, required evidence types, candidate streams, common upstream sources, methods, investigators, time windows, and relevant bias risks. Choose the diversity axis—data, method, theory, or investigator—and state why it can test the claim. Ask at most one decisive question when the claim or independence boundary is unclear.

## Procedure

1. Publish the focal claim and the decision it could change. State the evidence needed to support it and the claim scope; this creates the visible corroboration state.
2. Publish each evidence stream with its data origin, method, investigator, population, time, and expected bias. Mark user-provided, checked, inferred, and unavailable inputs.
3. Publish the independence check: shared dataset, shared measurement, common institution, common model, or genuinely separate source. Do not treat methodological variety as independence if all streams inherit the same raw data.
4. Publish the result of each stream against the same claim: converges, conflicts, or does not address. State the direction and materiality of each result rather than counting votes.
5. Publish gaps and plausible explanations for conflict, including scope, timing, measurement, selection, and analysis differences. Keep competing explanations visible until a check resolves them.
6. Publish the combined evidence state and calibrated conclusion. Agreement can strengthen a supported result; material conflict lowers or holds it unless a justified precedence or scope rule resolves the dispute.
7. Publish the next independent check and an observable flip condition. If streams are not independent or do not address the same claim, state that triangulation is insufficient instead of reporting false corroboration.

## Public output contract

Return `focal_claim`, `evidence_needed`, `evidence_streams`, `independence_check`, `stream_results`, `agreement_conflict`, `agreement_conflict_gap`, `combined_evidence_state`, `calibrated_conclusion`, and `flip_condition`. The card must summarize convergence or conflict and name the relevant source links or safe user-provided labels. Grounds use **verified**, **computed**, **inferred**, **assumed**, **unverified**, or **conflicted** labels.

## Evidence and uncertainty rules

Independence is about shared data, measurement, incentives, and analytic lineage, not the number of citations. A stream that fails to address the focal claim is a gap, not negative evidence. Agreement from dependent streams cannot justify strong corroboration. If material streams conflict, preserve the conflict and hold or lower the result until scope, quality, or precedence is justified.

## Stop conditions

Stop and ask one blocking question when the focal claim or independence boundary cannot be defined. Hold when all streams share one unverified source, when a material conflict has no resolution, or when the streams answer different questions. Stop when the task is source ranking alone, value choice, or formal entailment.

## Complement handoff

Hand off to `evidence-hierarchy` when the remaining dispute is the quality, design, or applicability of individual streams. Pass the stream inventory, independence verdict, convergence/conflict summary, and missing check. The complement should not infer independence from the number of sources.
