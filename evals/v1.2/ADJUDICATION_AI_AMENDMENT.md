# v1.2 adjudication AI-review amendment

Status: maintainer-authorized, development-only amendment

Date: 2026-08-13
Applies to: the 51-pair `v1.2-adjudication-51` development adjudication only

## Purpose and boundary

The frozen `ADJUDICATION_GUIDE.md` requires two output-blind human reviewers for
confirmation-grade gold labels. The maintainer subsequently authorized an AI-assisted
adjudication so the development harness can proceed without waiting for human
availability. This amendment does not rewrite the frozen guide or represent an AI
review as human review.

Results produced under this amendment have the machine-readable evidence grade
`ai_assisted_provisional_development`. They may be used to:

- test the revised insufficiency taxonomy and scoring implementation;
- identify cases that need rewrite, exclusion, or a product-policy decision;
- build the future held-out annotation guide;
- compare historical and post-adjudication development diagnostics side by side.

They may not be used as:

- confirmation-grade independent human adjudication;
- final held-out labels;
- evidence that the selector or OpenSocrates improves answer quality;
- a silent replacement for the historical schema 1.0.0 screening results.

They are not confirmation-grade human gold, not held-out, and not
answer-quality evidence. The original raw screening files, packet bundle,
queue, and reviewer artifacts are maintainer-held and are not repository-
verifiable. Their recorded hashes are historical claims unless the explicit
maintainer-evidence validator mode is run with those files present.

## Review design

1. ChatGPT Pro receives only the 51 blind packets and produces a complete primary
   review.
2. A separate ChatGPT Pro conversation receives the same blind bundle without the
   primary result and produces a compact second review.
3. Claude Opus 5 at high effort receives the same blind bundle in an isolated
   directory. If service limits truncate the run, only complete recoverable records
   may be used as additional evidence; missing records are never imputed as Claude
   decisions.
4. Codex performs schema normalization and disagreement synthesis. Codex is not an
   output-blind adjudicator because it has access to the surrounding evaluation analysis;
   it may resolve reviewer records under the maintainer's authorization but may not
   be recorded as a blind primary or second reviewer.
5. Every final record identifies the actual reviewer surfaces. The manifest reports
   full-review and partial-review coverage separately.

## Decision rule

- Normalize only vocabulary and schema shape before comparison; do not change a
  reviewer's substantive decision during normalization.
- Exact agreement may be adopted directly.
- Compatible differences may be resolved by the frozen common policy, with the
  difference recorded.
- A substantive disagreement is preserved in the disagreement ledger. If the
  maintainer-authorized synthesis cannot choose from the packet contract alone, the
  case is marked `rewrite`, `exclude_from_policy_metric`, or `unresolved` and is not
  policy-metric eligible.
- Legacy `exact_route` and `no_intervention` insufficiency cases are evaluated
  separately. A common default must not erase a case's authored route assertion
  without a recorded reason.
- Existing raw results and legacy labels remain byte-for-byte unchanged.

## Publication disclosure

Any document or artifact using these decisions must call them “AI-assisted provisional
development adjudication.” A later blind human review may confirm or replace them by
creating a new version; it does not edit this decision history in place.
