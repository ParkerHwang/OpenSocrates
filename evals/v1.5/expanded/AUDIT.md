# Expanded pilot evidence audit

This is an additive audit of the candidate at `e597c07`, followed by the new
freeze at `9dd94c6f70ec2badd990aa306246e6dc89637b05`. Old manifests and outcomes
remain byte-for-byte unchanged. Run both the original integrity verifier and
`python3 evals/v1.5/expanded/verify_baseline_v2.py` from the repository root.
The latter checks the [audit-time inventory](baseline-inventory.v2.json), every
retained attempt including placeholders, usage missingness, and aggregate shape.
Its [receipt](baseline-audit.v2.json) is a consistency check, not a new outcome.

## Existing attempts and interpretation

The original verifier passes 40 final model/collaboration cells and 21 memory
sessions. The fuller ledger contains **109 declared evaluation calls**: 56 calls
in the final proxy/installed model batches, 32 calls in two failed proxy EVAL-05
batches, and 21 memory/coding calls including the guide-repair pair. Capability
and host probes are separate from this count.

In the first failed EVAL-05 batch, all 16 attempts remain declared. Four developer
follow-up invocations failed at CLI parsing; eight calls across four nondeveloper
cells have placeholder records because a scorer TypeError discarded the receipts.
Their exit, usage, and time values remain null. The second batch contains 16
returned calls but no successful cells: the resumed condition could not write the
required correction. The successful rerun does not erase either batch. Nine
original EVAL-01 sessions also lack wall time after an aggregate-write crash.

EVAL-05's final proxy strict success is 5/8; installed strict success is 4/8.
Developer cells pass in both languages and arms. Installed nondeveloper cells
pass all 12 revised venue/attendance/accessibility field checks but fail all four
booking-action checks. The old checker requires availability and step-free
keywords in the same action string, whereas the frozen request permits describing
accessibility elsewhere. The manifest also names a side-question dimension that
the deterministic success flag does not include. Because raw synthetic artifacts
were discarded, semantic behavior cannot be retrospectively reconstructed. These
are preserved **strict-field failures**, with rubric and missing-review causes
unresolved; they are not rewritten as passes.

The installed EVAL-05 treatment reports 2,106,385 input tokens and 397.368 seconds
versus 1,036,115 and 253.721 for baseline. The 20 reported `policy_calls` are keyword
flags, not 20 proven policy invocations: all are also flagged as retrieval and
their command hashes are distinct. EVAL-04 memory arms report 1,247,173 input
tokens and 49 command actions, versus 265,660/22 disabled and 262,916/17 with a
maintained note; all nine fixtures pass. Cached input is a subset of input.
Neither answer length nor input count measures hidden reasoning or actual billing.

Retained original memory receipts show eight EVAL-01 D recall attempts with one
success, including zero successes in the paired D's three attempts. The separate
guide-revision-2 pair retrieved successfully on its first attempt. Retained
command hashes do not show an exact unchanged retry within a session. The justified
guide repair already exists. Those older receipts alone did not justify another
product or EN/KO guide change; profiles stay candidate and memory remains opt-in.

## Installed-treatment fidelity defect

The old `native_plugin_runner.build_marketplace` uses Python ZIP extraction
without restoring Unix executable modes. New zero-model preflight reproduced
successful installed/enabled inventory followed by `launcher_unavailable`.
The current archive stores launcher/runtime mode 0755; extraction creates 0644.
The second preflight retained per-operation receipts; the first only has a bounded
failure record. Restoring archive modes before the disposable install made the
four enrollment/record/accept operations pass, with matching installed bytes and
executable launcher/runtime. See [preflight receipts](preflight/).

The old exact native ZIP is unavailable for a fresh mode inspection. Old native
results do not record installed modes or a successful explicit runtime receipt.
They establish installation and static guide/prompt exposure; executable policy,
decision, and hook delivery remain unverified. This is a treatment-fidelity limit,
not a claim that every old model failed. The old native EVAL-03 ablation also varies
hooks, whereas the new declared ablation holds hooks disabled and varies only its
extra optional wrapper. Those conditions must not be pooled.

## New measurement repairs and their limits

The new harness writes a started record before each model/setup invocation and
persists the terminal model receipt before artifact scoring. It records incomplete
and failed tool actions, semantic protocol rejections separately from process
exits, all exposed token categories, and hashes of commands. Synthetic tests cover
split started/completed events, Windows launcher syntax, missing executables, and
timeout receipts. A v2 selftest initially assumed receipt ordering; the assertion
was corrected before access probes. The access helper remains immutable. The v3
helper separately repairs the reviewed instrumentation before pilot outcomes.

Only declared synthetic artifacts and public final messages are retained for
review. Raw event streams and hidden reasoning are not persisted by this harness.
The command classifier is deliberately labelled lexical: indirect Python/shell
calls may escape it. Actual policy/memory invocation totals are **null**, with
directly observed counts reported only as lower bounds. An artifact containing a
decision stored only in the synthetic memory demonstrates recovered content; it
does not by itself prove which memory API path supplied it. Full post-run workspace
snapshots and native application receipts are not captured.

## New scoped-forgetting diagnosis

**Best current explanation (provisional):** the mutation guidance did not give
the agent a usable distinction between ordinary correction and requested erasure.
The verified guide gap does not identify every rejected request in the old turn.

**Observation:** `v2-eval04-general-correction--guidance_memory--r2` completed the
correct Harbor plan in 228.702 seconds and 37 tool actions, but its final message
reported failed supersession of the withdrawn capacity fact. Structured output
metadata contains four invalid requests and one unavailable result. Its artifact
gate passes; its requested memory cleanup is incomplete. The original score and
record remain unchanged.

**Candidate explanations and comparison:** malformed mutation requests fit the
invalid-request statuses, but their exact bodies were discarded; a guide gap is
verified from the missing write contracts and generic supersession instruction;
a runtime/permission failure could explain the unavailable response, but valid
source/native lifecycle checks weaken a broad runtime-bug explanation. The
evaluator also lacked a persisted-forgetting gate, so artifact success alone
cannot resolve the memory outcome. These are different mechanisms, not votes.

**Discriminating evidence:** source `supersede` deliberately preserves the old
summary/history. The new bilingual documented-payload test shows that
supersession alone still exports the withdrawn fact, while exact-record deletion
after preserving accepted intent removes it from inspect/export/recall. This
supports conditional guidance repair rather than a storage/schema rewrite.

Assistance guide revision 3 now links separate EN/KO mutation instructions only
for authorized correction/forgetting. It documents inspect/current versions,
record/accept, supersede, exact-record deletion, and verification; it neither
shortens canonical procedures nor changes model profiles. The 50-cell v2 matrix
continues using its frozen guide-2 archive. The guide-3 diagnostic is separately
frozen in [diagnostic-freeze.v3.json](diagnostic-freeze.v3.json).

**Next test and flip condition:** run the frozen EN/KO guide-3 cases and inspect
the persisted public memory after each. Continued failure with valid requests
would reopen the runtime or permission explanation. Success would establish only
the bounded corrected behavior, not a general quality or efficiency gain.

A v2 nondeveloper English cell separately failed a final-message question check.
Its artifact correctly records the pending $100 budget increment. Four public
messages were reported, but only the final message was retained; absence of a
question mark in that final message cannot prove no earlier question occurred.
The old strict result stays failed, and semantic dialogue judgment is missing.
The separate guide-3 dialogue diagnostics retain all public messages and redacted
synthetic command templates, excluding reasoning events. They do not retrofit the
earlier score or create human-review evidence.

## Local and account memory

The later retained v4 trace resolved the acceptance-request question: the agent
sent prose in `acceptance_basis`, but `validate_basis_reference` requires a short
reference. Source reproduction rejects that prose while accepting
`user:current-request`. The request schema previously admitted the broader string.
Guide revision 4 / mutation revision 2 and the generated schema now expose the
existing runtime rule. The separate v5 EN/KO trials both complete the artifact and
the persisted correction; inspect/export/recall independently confirm removal and
preserved accepted intent. This verifies the scoped repair. It does not remove
the four earlier guide-3 failures, repair their missing usage, or establish a
general quality or efficiency effect. The stronger trace evidence supersedes the
earlier provisional diagnosis without changing its underlying frozen records.

The [read-only host audit](host-audit.v2.json) checked the bundled client hash,
safe login status, and three prior disposable profiles with empty native output/job
tables. New profiles disable native memory use, generation, and external import;
single-turn tasks use `--ephemeral`. Two-turn collaboration keeps transient session
state only within its disposable profile, then removes that profile. New per-cell
table counts are recorded. These controls do not establish account-side isolation;
memory-effect comparisons are explicitly confounded.

The documented `memories.use_memories` and `memories.generate_memories` controls
support the local configuration choice, not a backend-isolation claim. See the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
Only Local is connected; live Windows is unavailable. Global memory/settings,
active plugin installation, and destructive account-home lifecycle tests were
outside the execution scope.

## Public evidence reconciliation

**Focal claim:** whether the candidate has enough evidence for a reviewable
implementation handoff and for the separate quality/release claims.
**Evidence needed:** source/privacy contracts, native packaged behavior, actual
client access and task delivery, then independent quality and resource evidence
for each intended claim.

| Evidence stream and origin | Independence check | Result against its own claim |
| --- | --- | --- |
| Source tests and frozen macOS package built from this repository | Package and source checks share implementation; they are not independent quality judges | Verified bounded engineering behavior; no model-quality conclusion |
| Exact-ID bundled-client probes using the existing account | Actual executions are separate from the bundled catalog; backend identity still has no independent echo | Verified request/access completion for Luna, Sol, Astra medium |
| Old and expanded synthetic task artifacts | Runs have distinct freezes; repeated tasks share authored inputs and judge assumptions | Computed fixture outcomes only; guide, hook, wrapper, and memory conditions remain separate |
| Independent task authoring and blinded packet preparation | Author did not inspect old outcomes; no assigned human assessor has supplied scores | Broader preparation, not human corroboration |
| Account-side isolation, billing, independent human quality | Unavailable | Does not address the corresponding causal, monetary, or quality claims |

**Agreement/conflict/gap:** source and package streams agree on engineering
behavior. They do not answer the model-quality question. Old rubric uncertainty,
executable-mode fidelity, overhead, and unavailable independent review constrain
interpretation. **Combined evidence state:** verified source and bounded native
behavior; observed pilot artifacts; unverified causal benefit, noninferiority,
billing, and release readiness. **Calibrated conclusion:** continue the Draft PR
handoff, retain candidate profiles, and make no release or universal improvement
claim. **Flip condition:** a separately frozen, adequately powered outcome study
with the required review and isolation scope could change the quality claim;
separate release authority and platform acceptance would change release status.
