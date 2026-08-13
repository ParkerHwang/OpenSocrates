# OpenSocrates v1.2 adjudication guide

Guide version: 1.0.0
Protocol version: 1.2.0
Status: frozen before any pair-level adjudication decision
Scope: 51 unique EN/KO semantic pairs (48 development insufficiency pairs plus
three additional boundary pairs; `socratic-questioning-insufficiency-01` is a
member of the insufficiency batch that also carries its own queue item)

This guide is the single annotation contract for evaluation
`v1.2-adjudication-51`.
The current committed SHA-256 is recorded under `committed_artifact_sha256` in
`evals/v1.2/adjudication-manifest-v1.0.0.json`. The freeze record preserves the
different hash of the maintainer-held, pre-public-wording copy used to build
the historical packets; those packet and guide bytes are not repository-
verifiable. Public identifier and validation-boundary wording was corrected
before integration without claiming that the private packet run was replayed.
Any future semantic amendment requires a new guide and decision-file version;
existing decisions are never silently edited in place.

The committed AI-assisted snapshot governed by this guide is not
confirmation-grade human gold, not held-out, and not answer-quality evidence.
Those claims require the independent-human workflow defined below.

The purpose of adjudication is **not** to raise or lower any selector score.
It is to define, independently of model outputs, what the gold policy means:
when the selector must intervene, whether clarification routing is success,
whether owner-route-then-hold is allowed, which method leads when several are
reasonable, and which cases are unfit for a single gold label.

## 1. Roles and blinding

| Role | May see | May not do |
| --- | --- | --- |
| Packet preparer | case texts, legacy labels, queue, raw-result hashes | make gold decisions; pass model results to adjudicators |
| Label author / intent witness | own authored cases and intent | judge outputs; finalize decisions alone; argue from model behavior |
| Primary adjudicator | blind packet contents only (section 7) | see any model output, selection, score, or aggregate before lock |
| Second reviewer | blind packet contents only | see model results before their own independent decision is locked |
| Resolution reviewer | both locked decisions and rationales | delete dissent; pick arbitrarily without recorded reasons |

Hard rules:

1. A person or agent who has seen `v1.2-adjudication-51` case-level outputs or
   aggregates cannot
   be a primary or second adjudicator. They may prepare packets, explain
   intent, implement schemas, and run validation only. The final independent
   adjudicator must be a human who has not seen the relevant model outputs.
2. All 51 pair decisions must be locked (both reviews) before anyone involved
   opens model outputs. The attestation block in every decision records this.
3. Nothing in `build/evidence/v1.2/screening-results.jsonl` or
   `build/evidence/v1.2/screening-max-unbounded-results.jsonl` is modified,
   ever. New decisions are append-only files beside the preserved history.
4. "This is what the model chose, so the gold label should match" is not a
   valid ground anywhere in a rationale.

## 2. Selector contract definitions

Under selector protocol 1.2.0:

- `selected_reasoning_systems[0]` is the **leading method**: the method that
  should lead the user's main judgment or next action. Complementary methods
  follow in application order.
- **intervention** — the selector selects at least one reasoning method
  (`intervene: true`, non-empty selection).
- **non-intervention** — the selector selects nothing
  (`intervene: false`, empty selection).
- **clarification** — the selector routes to a method whose contract is to
  bound and ask decisive questions before analysis (representative candidates:
  `socratic-questioning`, `conceptual-analysis`). Whether a given case's
  clarification role actually fits the method contract must be checked per
  case against the method definitions in the packet.
- **owner-route-then-hold** — the selector identifies the method that owns the
  problem type but the method cannot complete because decisive inputs are
  missing. Allowing this behavior requires deciding whether the selector stage
  is judged on route identification or on immediate executability; record that
  choice in the policy form (section 5), question 4.
- **wrong analytical route** — the selector commits to an unjustified analysis
  path despite missing decisive inputs (e.g., starting a cost-benefit
  computation with no numbers, asserting root-cause analysis with no causal
  data, performing a Bayesian update with no probability inputs, recommending
  a decision outcome with the user's goal unknown).
- **contraindication** — conditions under which applying any analysis method
  is itself unsafe or misleading, so no method may be selected. This is
  distinct from mere missing information; the policy form question 8 fixes the
  distinguishing rule.

Gold-side vocabulary:

- `leading_method` — the single method that must occupy index 0.
- `acceptable_leading_methods` — methods any of which may legitimately occupy
  index 0 when no single leading method can be fixed.
- `acceptable_inclusion_methods` — methods that may appear after the leading
  method without making the answer wrong.
- `prohibited_methods` — methods whose selection is unsafe or distorts the
  problem for this case.

## 3. Pair-level review procedure

For each pair, in order:

1. **Semantic equivalence.** Read EN and KO texts. If they convey the same
   situation, decision pressure, and missing/present information, set
   `en_ko_equivalent: true` and make one semantic decision for both locales.
   If not, set `translation_mismatch: true`; the pair is not policy-metric
   eligible until the mismatch is resolved. A corrected translation becomes a
   new version; the original sentences are preserved.
2. **Case validity.** Decide whether the text, as written, can support a
   single defensible gold policy. If competing readings are irreducible,
   choose `rewrite`, `exclude_from_policy_metric`, or `invalid` — never force
   one reading to fit the existing scorer.
3. **Intervention policy.** Choose `prohibited`, `optional`, `required`, or
   `undetermined` for whether the selector may/must intervene.
4. **Allowed behaviors.** Choose the set from section 6 that product policy
   accepts as safe and reasonable. Multiple behaviors are explicitly allowed
   when each is safe; do not force a single answer.
5. **Leading and inclusion routes.** If exactly one method should lead, set
   `leading_method` and `leading_metric_eligible: true`. If several are
   equally legitimate, leave `leading_method: null`, list
   `acceptable_leading_methods`, and set `leading_metric_eligible: false`
   (or propose a multi-leading metric in notes). Never pick one arbitrarily to
   satisfy the existing scorer.
6. **Prohibited routes.** List methods that must not be selected for this
   case, with the harm named in the rationale.
7. **Metric eligibility.** Set the three eligibility flags (section 6).
8. **Decisive features and rationale.** Record the observable features of the
   text that drove the decision, then a rationale that stands without any
   reference to model behavior.
9. **Status.** Close the pair as `retain`, `relabel`, `multi_valid`,
   `rewrite`, `exclude_from_policy_metric`, or `invalid` (section 4).

Second review repeats steps 1–9 independently, then the comparison is
classified as `exact agreement`, `compatible agreement`,
`substantive disagreement`, or `translation disagreement`. Substantive
disagreements go to the resolution reviewer; an unresolved pair stays
`unresolved`, `rewrite`, or `exclude_from_policy_metric` — never a silent
coin flip.

## 4. Decision status definitions

- `retain` — the case text stands; only the new policy semantics and gold
  fields are added.
- `relabel` — the new decision differs from the legacy gold label. The legacy
  label, new decision, reason, adjudicator, timestamp, and protocol version
  are all recorded; the legacy label is never deleted from its source file.
- `multi_valid` — more than one behavior and/or route is accepted.
- `rewrite` — the text is too ambiguous to evaluate. The rewritten case gets a
  new case ID/version; because rewrites in this workflow are exposed to AI
  tooling, they may enter only development/calibration sets, never the final
  held-out set.
- `exclude_from_policy_metric` — kept for behavior observation but excluded
  from policy accuracy and leading recall; the exclusion reason and affected
  metric scope must be stated.
- `invalid` — unusable as an evaluation case; an invalid decision is appended,
  the original record remains.

## 5. Insufficiency common-policy form (answer before any pair decision)

The primary adjudicator answers the ten questions below in
`evals/v1.2/adjudication-policy-v1.0.0.json` and locks that file **before**
reviewing individual pairs. The second reviewer countersigns or files a
disagreement the same way. Candidate answers are listed; "other" with a
written rule is allowed. This guide deliberately does not pre-answer them.

1. When decisive information is missing, is non-intervention the default
   expectation? (`yes_default` / `no_default` / `case_by_case_rule`)
2. Is selecting a clarification method an intervention?
   (`yes` / `no` / `separate_category`)
3. Is clarifier routing counted as policy success for insufficiency cases?
   (`success` / `failure` / `allowed_but_not_required`)
4. Is owner-route-then-hold allowed? State whether the selector stage is
   judged on route identification or immediate executability.
   (`allowed_route_identification` / `disallowed_executability` / `case_by_case`)
5. When a clarifier and an owner method are both selected, which must lead?
   (`clarifier_leads` / `owner_leads` / `either_leads`)
6. Is a clarifier that appears but not at index 0 still a success?
   (`yes` / `no` / `inclusion_only_success`)
7. Are "merely ambiguous question" and "decisive evidence absent" treated
   under one rule or two? (`one_rule` / `two_rules_defined_below`)
8. What rule separates contraindication (analysis itself unsafe) from plain
   insufficiency? Write the operational rule.
9. When multiple behaviors are allowed, how is ordered-leading recall defined
   for the case? (`excluded_from_leading_metric` / `any_acceptable_leading` /
   `separate_multi_leading_metric`)
10. Which case classes are excluded from the policy conformance metric, and
    why? Write the exclusion rule.

The locked answers apply uniformly to all 48 insufficiency pairs; per-pair
deviations must cite which question's rule they instantiate, or the pair must
be excluded/rewritten.

## 6. Machine-readable decision values

Every decision, disagreement, and manifest carries
`evidence_grade: ai_assisted_provisional_development`. Machine-readable status
values do not use a `_gold` suffix. A consumer that reads an isolated JSONL
record therefore receives the same evidence boundary as a reader of this
guide.

`intervention_policy`: `prohibited` | `optional` | `required` | `undetermined`

`allowed_behaviors` (any subset):
`hold_no_intervention` | `route_clarifier` | `route_owner_then_hold` |
`route_safe_alternative` | `bounded_analysis`

`decision.status`: `retain` | `relabel` | `multi_valid` | `rewrite` |
`exclude_from_policy_metric` | `invalid`

`review.agreement`: `agreement` | `minor_revision` |
`resolved_disagreement` | `unresolved`

Metric eligibility flags:

- `leading_metric_eligible` — `true` only when exactly one leading method is
  fixed; `false` for multi-leading ties and no-intervention cases.
- `inclusion_metric_eligible` — `true` when at least one acceptable method's
  inclusion can be scored; `false` when no method may be selected or the case
  is invalid.
- `policy_metric_eligible` — `true` only when the allowed behavior set is
  final; `false` for incomplete decisions, translation mismatches, ambiguous
  or invalid cases.

Consistency rules (enforced by `tools/check_v12_adjudication.py`):

- `intervention_policy: prohibited` ⇒ no `leading_method`, and
  `allowed_behaviors` must not contain routing behaviors other than
  `hold_no_intervention`.
- `allowed_behaviors == [hold_no_intervention]` ⇒
  `inclusion_metric_eligible: false`.
- `leading_metric_eligible: true` ⇒ `leading_method` is a single method id.
- `policy_metric_eligible: true` ⇒ `allowed_behaviors` is non-empty.
- `translation_mismatch: true` ⇒ `policy_metric_eligible: false` and the pair
  is not confirmation-eligible.
- `status: rewrite` or `invalid` ⇒ original text and IDs remain untouched;
  rewrites use new IDs.

## 7. What adjudicators may and may not see

Provided in the blind packet: pair ID, EN text, KO text, legacy case kind,
legacy owner method, legacy expected route/assertion (the historical label
being adjudicated, which is provenance, not model behavior), authoring intent,
decisive features as authored, definitions (purpose, use-when, do-not-use-when,
stop conditions) of the owner and candidate methods, the selector ordering
contract (section 2), this guide, the adjudication questions, and an empty
decision form.

Never provided before lock: actual selector outputs, selected method lists,
model rationales or instructions, per-case pass/fail, effort-level success
rates, EN/KO model performance, max vs max-unbounded differences, recall
deltas, expected score impact of any decision, pilot results, or arm
aggregates. The packet-visible body follows the shared forbidden-key contract
in `tools/v12_adjudication_contract.py`, including `selected`, `intervene`,
`instructions`, `output`, `status`, `score`, `pass`, `failure`, and `effort`.
The separate empty decision form necessarily names decision fields such as
`status`; the validator checks that none of those fields is pre-filled.

## 8. Boundary-pair adjudication questions

These four pairs carry queue items with case-specific questions. Candidate
resolutions come from `evals/v1.2/adjudication-queue.jsonl`; the adjudicator
may also choose `exclude_from_policy_metric` for any of them.

### `decision-tree-analysis-mechanical-1`

Is executing a fixed, fully specified if-then flowchart a purely mechanical
task (no method), an explicit-rule application owned by `deduction`, or an
irreducibly ambiguous text that must be rewritten? Candidates:
`mechanical_no_intervention`, `deduction_route`,
`rewrite_to_remove_rule_application_ambiguity`, `exclude_from_policy_metric`.

### `lateral-thinking-negative-02`

For mandatory safety-specification testing, which method leads:
`critical-thinking`, `deduction`, or `falsificationism`? May several be
selected with one declared leader, or must the sentence be rewritten to force
a single route? Candidates: `critical-thinking_primary`, `deduction_primary`,
`falsificationism_primary`, `multi_method_with_declared_primary`,
`rewrite_for_single_route`, `exclude_from_policy_metric`.

### `design-thinking-positive-03`

Does the desired-progress wording make `jobs-to-be-done` a legitimate leader
alongside `design-thinking`? Candidates: `design-thinking_primary`,
`jobs-to-be-done_primary`, `either_route_acceptable`,
`multi_method_with_declared_primary`, `rewrite_for_single_route`,
`exclude_from_policy_metric`.

### `socratic-questioning-insufficiency-01`

Under the section-5 policy, is selecting `socratic-questioning` to ask
decisive questions a success, is silence the only success, are both allowed,
or must the case be rewritten with a bounded target? Candidates:
`hold_no_intervention`, `socratic_questioning_clarifier`,
`both_behaviors_allowed`, `rewrite_with_bounded_target`,
`exclude_from_policy_metric`. Note the self-referential hazard: the legacy
label treats selecting the clarification method itself as failure, which is
contradictory under any clarification-permitted policy; the decision here must
be consistent with the answer to policy question 3.

## 9. Relationship to the held-out set

All 51 pairs stay in the development/calibration pool permanently. What moves
to the held-out annotation guide is the policy: intervention definitions,
insufficiency allowed-behavior rules, the contraindication rule, the
leading/inclusion distinction, rewrite criteria, and metric eligibility rules.
Held-out cases are separately authored with no model exposure, EN/KO semantic
pairing, author/translator separated from output judges, labels fixed before
freeze, and per-case leading/inclusion/prohibited routes recorded before any
model output is opened.

## 10. Outputs

- `evals/v1.2/adjudication-policy-v1.0.0.json` — locked section-5 answers.
- `evals/v1.2/adjudication-decisions-v1.0.0.jsonl` — one record per pair,
  append-only, schema
  `evals/v1.2/schemas/adjudication-decision.schema.json`.
- `evals/v1.2/adjudication-disagreements-v1.0.0.jsonl` — one record per
  substantive disagreement with both decisions, resolution or `unresolved`,
  and dissent preserved; schema
  `evals/v1.2/schemas/adjudication-disagreement.schema.json`.
- `evals/v1.2/adjudication-manifest-v1.0.0.json` — counts, reviewer IDs,
  hashes of every committed adjudication artifact, timestamps, git revision,
  and a separately marked set of maintainer-held historical evidence hashes.

The public clean-clone gate is:

```bash
python3 tools/check_v12_adjudication.py
```

It validates only committed files and requires exactly 51 decisions. To also
require the unpublished packet bundle, queue, raw-result files, and reviewer
artifacts, a maintainer must opt in explicitly:

```bash
python3 tools/check_v12_adjudication.py --mode maintainer-evidence
```

That mode fails when any requested evidence is absent; it never reports a
missing required output as skipped. The original packet, queue, reviewer, and
raw-result files are maintainer-held and are not verifiable from this
repository. Post-adjudication numbers are reported beside — never in place of
— historical schema 1.0.0 results.
