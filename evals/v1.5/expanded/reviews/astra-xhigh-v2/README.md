# Provisional Astra review of the 60 prepared packets

This is a new review lane, separate from candidate outcomes. It uses the exact
user-provided `opensocrates_bilingual_reviewer` definition, requested as
`gpt-6-astra` / `xhigh` / `read-only`. The original project agent file is preserved;
[reviewer-definition.toml](reviewer-definition.toml) is the frozen byte copy.
The configuration is loaded through a named disposable Codex CLI profile; only
agent metadata `name`/`description` is omitted from runtime settings. All behavior
fields and developer instructions are preserved, with the requested model, effort
and sandbox also pinned explicitly on the command line. A non-model prompt-input
inspection verified the exact role text and the read-only permission context.

The [manifest](manifest.json) was committed before judging. It freezes the agent,
runtime profile, client, rubric, original packet hashes, derived input/evidence
hashes, assignment order, wall/response limits, failure handling and usage fields.
The rubric remains the unchanged `JUDGE_PROCEDURE.v2.md`. No outcome cell is rerun,
no candidate artifact is repaired, and no ratings are fed into Luna treatments.
Human scores remain unavailable; these are one model configuration's provisional
assessments, not independent human judgments.

## Blinding and phase locks

There are 17 assignments: 12 English and five Korean. Each has at most four
packets, only one language and no repeated task family. EN/KO partners and
competing repetitions are therefore not reviewed in the same first-pass context.
Every call uses a fresh isolated profile/workspace, with native memory, imports,
hooks, plugins, web and delegation disabled. The reviewer receives only repository
constraints, the fixed rubric, assigned packet views, schema and assignment.
Implementation conversation, summaries, unblinding maps and other scores are not
provided. Account-side isolation and backend model echo remain unproven.

Original packets are never edited. Diagnostic packets embed computed checks, so
new first-pass projections withhold those fields while retaining public stored
records as observational artifacts. Both original and view hashes are recorded.
Reviewer `packet_sha256` identifies the actual view it read. The deterministic
preparer performs only the mechanical key lookup necessary to form opaque evidence
files; treatment labels are not delivered. Analytic unblinding is forbidden until
the final lock exists.

All 60 first-pass ratings must validate and lock before any evidence-phase call.
The second phase has a fresh context containing only the same assignment's own
locked first pass, packet views and corresponding opaque deterministic evidence.
First-pass scores, gates, findings and blinding statements must remain exactly
unchanged. Later scores/gates and disagreements have separate fields. Evidence
can correct interpretation without rewriting historical deterministic outcomes.
Clarification is assessed across available public messages; absent earlier
messages cannot prove that no question occurred.

## Execution and validation

The integrator owns persistence. The reviewer returns JSON and cannot edit files,
run candidate code/tests, contact people, or invoke another model. Each attempt
gets started/terminal receipts, public returned text, validation, isolation and
cleanup records. Only concise public assessment grounds are retained; reasoning
events and raw event streams are not stored. Missing usage and billing are null.
Command-pattern checks and unchanged-input hashes supplement the read-only sandbox;
they are not universal native access attestations.

`review.py` validates fixed identities, all six axes, anchored score/null states,
critical gates, actual packet citations and first-pass immutability. One fresh
same-tuple format/citation retry is allowed by the freeze; it gets no previous
rating or semantic direction. Failed attempts remain visible. No model or effort
substitution is permitted.

The prior [v1 manifest](../astra-xhigh-v1/manifest.json) has one rejected assignment
call and one zero-packet transport diagnostic, both with null usage and no accepted
scores. The API required explicit JSON types alongside fixed-value/enum fields.
V2 changes that transport schema and captures error details; agent configuration,
rubric, packets, assignments and model/effort remain unchanged.

Offline verification does not require authentication or a model call:

```sh
python3 evals/v1.5/expanded/reviews/astra-xhigh-v2/verify_review.py
```

During an incomplete phase use `--partial`. Live execution requires the exact
client and original verified definition and runs `review.py first_pass`, then
`review.py evidence` only after the global first-pass lock. Never rerun a started
attempt blindly or modify a lock to make incomplete coverage pass. The final
synthesis joins treatment identities only after all ratings are locked, keeps
per-language/per-lane findings separate, and does not promote profiles or invent
held-out margins from model ratings.
