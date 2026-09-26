# Bounded practical comparison: released v1.4.0 and v1.5 source candidate

Completed under the user's revised practical standard. Six representative matched
scenarios, one episode per version, one fixed **gpt-6-sol / medium** configuration
on **codex-cli 0.158.0-alpha.2**. The exact client/package/task/permission/checker
[manifest](manifest.v1.json) was committed at `415c4d0` before calls.
All **20 planned invocations** completed within the initial 24-call cap, with
**12/12 episode artifact/state checks passing**, no failed model call and no model
retry/substitution. Two implementation-only read audits are recorded separately;
there was no new 60-packet review or human recruitment.

The released baseline ZIP is SHA-256
`74efeab5797de766dabf8394506e29bcb39df3d1b3aac93a5a9ec17a32909a33`, downloaded from
the actual v1.4.0 release. The guide-5 source candidate ZIP is
`57bae131444b0d7c0048ce2369c9fc232994812c758d617fbc7197763a0f5bd2`.
It still reported 1.4.0 while qualifying the v1.5 source. After this functional
qualification, final RC metadata becomes 1.5.0; the old comparison is not relabelled.
The native RC checks verify the metadata transition and unchanged functional
sources/guides/schemas. The historical 60-packet review and every old outcome stay intact.

Both versions received competent instructions, identical initial source and
follow-up transitions, the same model/effort/client and matched per-scenario
permissions. v1.4 received an explicitly named maintained note with the same
accepted/proposed facts as candidate memory. Code and non-Git follow-ups used new
profiles/contexts; collaboration resumed only its own disposable episode.
Planning permitted trusted hooks; all other pairs disabled hooks and explicitly
used the installed controller. No global configuration, active controller or
user-owned agent definition changed ([snapshots](host-after.json)).

| Scenario | v1.4.0 result | v1.5 source candidate result | Model wall seconds (1.4 / candidate) | Tool actions (1.4 / candidate) |
| --- | --- | --- | ---: | ---: |
| mechanical | Exact edit; no question | Same exact edit; no question | 33.0 / 34.0 | 4 / 6 |
| coding | Existing helper + fresh Git follow-up pass; maintained note | Same correctness; native accepted decisions and fresh recall | 122.7 / 235.4 | 22 / 47 |
| continuity | Current-source correction + scoped note update pass | Same plan; exact native deletion, accepted retained intent, unrelated/proposed state preserved | 182.6 / 233.4 | 32 / 46 |
| planning | Correct Bay choice; availability unresolved; unbooked | Same correct source-constrained decision | 80.8 / 86.1 | 13 / 13 |
| collaboration-en | Correct plan/side answer; budget request repeated twice in public turn | Correct plan/side answer; one budget request | 154.1 / 152.2 | 22 / 22 |
| collaboration-ko | Correct plan/side answer; one budget request | Same correctness and one request; readable Korean grounds | 121.7 / 143.9 | 20 / 22 |

## What improved, tied or regressed in these examples

**Added capability:** the candidate recovers project decisions through its native
store and exposes accepted/proposed lifecycle and exact operation/state evidence.
For the non-Git correction, actual adapter receipts record recall, inspect,
record, accept, delete and export. Independent reads confirm the original mixed
record is gone, retained intent is accepted, the unrelated badge record is
unchanged, and the suggestion remains proposed. The baseline's maintained note
also succeeds. This demonstrates a usable built-in memory workflow, not a causal
accuracy advantage over a competent note.

**Observed collaboration difference:** in English the baseline asks the same
$100 increase question once with choices and again in the final public text; the
candidate asks once. Neither reopens the approved $750 ceiling. These are public
question occurrences, not measured human-response turns. Both languages answer
capacity versus attendance and continue the artifact to the correct pending
approval state. Korean candidate explanations are readable; English candidate
explanations are sometimes longer and more field-oriented. The integrator review
is unblinded and qualitative, not an independent human score.

**Ties:** all six scenarios have correct artifacts and required state under both
versions. Existing-code reuse, zero-priced nonempty orders, integer seat validation,
changed tariffs and the new caller pass in both code episodes. No broad quality,
model superiority or noninferiority claim follows.

**Costs and rough edges:** candidate memory-backed episodes require more time,
tools and input than the maintained-note baseline. Mechanical work used two more
tool actions in the candidate, with similar wall time. Some discovery commands
looked for absent instruction files or used Git in non-Git folders. The candidate
tried the evaluation adapter's unsupported `--help` before using its documented
stdin interface; the baseline made two wrong reference-path guesses in continuity.
These tool failures remain in the receipts and were recovered within the planned
calls. Neither artifact correctness nor memory success establishes an efficiency
win. Optional model profiles remain inactive; task fallback and opt-in memory
avoid making every task pay for an unvalidated profile.

The continuity candidate also wrote an additional `notes.md`, duplicating part of
its structured continuity work. Its successful command receipt checks that the
withdrawn number is absent, but that extra file was outside the designated final
artifact snapshot. Do not claim a complete final-filesystem snapshot or verified
benefit from that duplication. The requested plan and native state are independently
verified. This bounded extra-work observation does not justify rerunning for a
more favorable score or extending the study.

## Measurement repairs and preservation

- [New checks](checks.py) catch a deliberately bad nonempty zero-price shipping
  branch, reject fractional/boolean seat counts, distinguish proposed from accepted
  records, and locate questions before final public text. Old checkers are unchanged.
- All public messages are retained; question matching is an index for reading the
  complete public turn rather than a final-message-only semantic verdict.
- [Native-memory adapter](memory_tool.py) forwards unchanged requests to the exact
  installed launcher and records request/response IDs, operation, target/version,
  status and hashes outside product memory. It adds measurement, not permissions
  or stronger-model answers. Independent before/after records verify the result.
- Frozen [outcome lock](outcome-lock.v1.json), [summary](summary.v1.json) and
  [integrator review](integrator-review.v1.json) retain every episode, all calls,
  artifacts, state reads, failures and missing values. No raw event stream, private
  reasoning, credential or real-project content is retained.

Reported input/cache/output/reasoning categories remain distinct in the summary;
cached input is part of input and reasoning output part of output. Model wall time
excludes package installation, native seeding and independent postchecks, which
have separate receipts. Human note-authoring burden is unmeasured. Billing,
independent backend identity and account-side isolation are unverified; they limit
monetary/causal claims and do not block this practical qualification.

Run `python3 evals/v1.5/practical/verify.py` for offline identity, outcome, budget,
usage and host-snapshot checks. It needs no model, authentication or old binary.
Final source/native/CI qualification and the exact publication action are recorded
in [the RC handoff](../../../docs/v1.5.0/RELEASE_CANDIDATE.md), PR #95 and issue #94.
No further model calls are needed for these completed practical scenarios.

Historical package availability is separate from frozen result integrity. The old
local guide-4 ZIP hash was not re-established from current generated outputs; an
isolated reconstruction matches all frozen member hashes but has another archive
hash ([preservation receipt](historical-package-preservation.json)). It is not
relabelled or used in this comparison. Checked-in old protocols, artifacts, scores
and failures pass their unchanged integrity verifiers. The published baseline and
the new comparison archive were copied and pinned before further RC builds.
