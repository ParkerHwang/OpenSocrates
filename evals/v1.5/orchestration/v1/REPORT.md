# Specialized production and independent acceptance: bounded qualification

The optional `orchestrate` command is implemented and locally qualified as an
unpublished v1.5 candidate. It assigns owned design/production work, freezes each
candidate, obtains fresh independent review and execution verification, and sends
failed obligations back to the designated maker. The primary keeps user intent,
permissions, integration and final reporting. This revision is tracked in Draft
[PR #95](https://github.com/ParkerHwang/OpenSocrates/pull/95); no release or active
installation is implied.

The frozen [design contract](../../../../docs/v1.5.0/15-specialized-orchestration.md)
and [user guide](../../../../docs/orchestration.md) define the scope. Text source,
JSON calculations and Markdown are supported. This adapter does not author or
visually verify binary office documents. Semantic domain classification and
attributed authorization remain the primary's responsibility.

## Actual outcomes and their limits

Every actual role and diagnostic uses the same configured **gpt-6-astra / max**
and `codex-cli 0.158.0-alpha.2`. No model substitution, resume/fork, automatic
external retry or model wall-clock cutoff was used. Real workflows invoke the
packaged launcher; each role uses a fresh ephemeral client context. Public
conversation hashes distinguish these contexts without exposing identifiers.
These are fixed synthetic correctness examples, not a randomized comparison,
detection-rate estimate or claim of better general reasoning.

| Frozen episode | Actual result | Evidence boundary |
| --- | --- | --- |
| Software design → implementation, live-v2 | 8 calls. Design qualified; the seeded bad implementation failed its executable check. The maker repaired it, and fresh reviewer/verifier accepted the repaired bytes. | Both initial negative assessments were discarded as `assessment_contract_rejected`. Their bodies are unavailable; they do not establish valid independent defect identification. |
| Calculation → document, live-v2 | 6 calls. Country amounts 6 and 35 and total 41 agree. The document references the exact source and calculation digests. Both units qualified. | Data and document are separately owned domains with a checked dependency. No spreadsheet/PDF rendering claim. |
| Korean continuation, live-v2 | 3 calls. A full 2,185-character accepted constraint and explicit memory-unavailable handoff were retained. Only an English module docstring was added. | Removing the standalone docstring leaves the previous implementation bytes exactly unchanged; all six cost cases still pass. This tests fallback continuity, not actual recalled-memory model benefit. |
| Targeted seeded repair, live-v3 | 5 calls, all completed. Reviewer and verifier independently reject the bad seed with exact path/hash/requirement findings; checker exits 1. The designated maker repairs it, then fresh review/verifier and checker pass. | The prior qualified design is supplied as an exact source. The repaired implementation is byte-identical to the already accepted live-v2 base. |

The supplied bad seed explicitly labels its maximum-cost selection as a synthetic
defect. Reviewers receive its governing contract and source cases. Independence
means distinct authorship/context and no maker self-rating in acceptance input;
it does not make the injected defect hidden or the model judgment objective.

The final live-v2 candidates were copied byte-for-byte into the disposable
[delivery](delivery/) and reconciled by the primary. Five actual native sandbox
checks passed on that combined delivery: design, costs, calculation, report and
documentation-only continuation. [Integration receipts](delivery/integration.json)
retain exact artifact identities. Product responses correctly remain
`integration_pending`; the separate primary integration record closes this
synthetic delivery. The [targeted-repair reconciliation](delivery/reconciliation-v3.json)
binds the later accepted repair to those unchanged implementation and continuation
bytes, without repeating unchanged tests. No real project was changed.

## Failures were retained and repaired separately

1. **Initial native gate failures:** the new subprocess boundary lacked a scanner
   registration, then Python 3.12/3.14 AST rendering differed. The scanner now binds
   the reviewed syntax/environment/call sites with stable canonical AST fields;
   32 mutation cases retain rejection coverage. Original failure reports remain
   in [development/failures](development/failures/).
2. **Independent code review:** candidate publication could lose its intended
   directory identity; late cancellation could discard accumulated receipts; and
   an obligation-only failure could lose maker repair evidence. The designated
   maker repaired each. Directory capabilities, retained run/publication state,
   exact-version obligation feedback and separate fresh acceptance are covered
   by static review and independently attributed execution checks.
3. **Provider schema rejection:** the first two live-v1 producers failed before
   producing artifacts. One separate diagnostic identified HTTP 400
   `invalid_json_schema`: a const field lacked an explicit type. Six type-only
   metadata sites were corrected; two new transport diagnostics succeeded. Their
   hashes/validation flags are retained, but their full output bodies were not
   retained and cannot be independently replayed from those receipts alone.
4. **Finding-location ambiguity:** two initial live-v2 negative assessments were
   invalid. A separate actual diagnostic reproduced a valid defect report using
   `pricing.py:6-7`, rejected by the exact-path binding. This diagnoses the new
   diagnostic's rejection; the original discarded bodies remain unknown. The
   schema description and complete EN/KO acceptance guides now require exactly
   `pricing.py`, with line details in `reproduction`. Runtime validation was not
   weakened. Wrong paths, suffixes, hashes and requirements remain rejected.
5. **Evaluation corrections:** the initial documentation-only oracle incorrectly
   accepted removal of blank lines and CRLF normalization. It remains preserved;
   a separate v2 checker passed 16 positive/adversarial cases before continuation.
   An auxiliary ZIP checker initially confused external and embedded suffix
   matches; the corrected checker compares exact member paths. Neither failure
   is rewritten as an artifact success.

One development code-review recheck turn was automatically safety-screened.
Blocked filesystem probes were not retried. Subsequent code review was narrowed
to static source inspection; execution verification remained a separately
attributed lane. Static acceptance is not presented as an executed security audit.

See [original code review](development/code-review-ca95/review.json),
[static repair review](development/code-review-rechecks/static-review.json),
[provider-type review](development/code-review-rechecks/schema-static-review-7893996.json)
and [location review](development/code-review-rechecks/location-static-review-4053e21.json).
The [diagnosis](diagnostics/assessment-diagnostic-v1/diagnosis.json) distinguishes
verified observations, competing explanations, discriminating evidence and the
remaining unknown original outputs.

The independent [final evidence index](independent/FINAL_EVIDENCE_INDEX.json)
reports no remaining concrete blocker in the bounded execution evidence or
reviewed public snapshot. Its [public reconciliation audit](independent/public-record-a0wl710w/audit.json)
checked all 153 files present at that snapshot against their original bytes and
stated path normalization, and independently reconciled all 28 calls and usage.
The primary then adds those completed audit records and locks the final file set;
the earlier audit does not pre-attest later additions.

## Deterministic, native and live evidence remain separate

[Validation](validation.json) binds product commit
`4053e21932ce126f552ce41ee0004bf7496634ca`, 587 runtime/package inputs, the complete
CONTRIBUTING source suite and `make release-check`. The source suite includes 41
orchestration tests. The local ZIP SHA-256 is
`4a49fb8cffe7d81a26fb28d04c86cd0affbb9e3a42babdd61dfc980db615917a`.
All 176 selected external/embedded schema and guide members match source exactly.
The native executable remains
`ec235d32e2dd6ac4c3ed98b122763b1495c88724589351b57261d8e264e1414a`;
the separately shipped guidance/schema bytes changed the archive identity.

The independent [pre-live index](independent/FINAL_PRELIVE_INDEX.json),
[boundary/repair recheck](independent/PRELIVE_RECHECK_53c5.json) and
[transport recheck](independent/TRANSPORT_RECHECK_789.json) identify their exact
source and data hashes. They cover ownership/dependencies, fresh role identity,
mandatory failed/unknown obligations, source changes, deletion, cancellation,
publication, bounded repairs, provider failures, usage nullability and native
read-only checks. Fake role adapters and real disposable memory APIs are labeled;
none is counted as an actual outcome model call. The 38 deterministic result
entries include a group aggregate and are not 38 independent model samples.

The [targeted live-v3 audit](independent/actual-live-v3-s2fxjeq6/audit.json)
reconstructed all five new assignments, confirmed exact-bound negative findings,
and verified that the designated maker received two findings, two failed
obligation judgments and the failed check. Fresh acceptance did not receive prior
assessments. Independent sandbox checks matched expected exits 1 and 0, and the
repaired implementation equaled the earlier accepted base. Together, the two
actual-workflow audits reconstruct all 22 role assignments without storing their
assembled prompt bodies.

The [actual live-v2 audit](independent/actual-live-v2-0gss_zex/audit.json)
independently reconstructed all 17 full assignment hashes from frozen requests,
committed guide bytes, exact sources/candidates, memory projections and feedback.
All match the native receipts. It confirms distinct contexts and the complete
supplied constraints/role boundaries; it does not prove hidden reading/application.
Seven fixed workflow oracle checks (six passes and the retained bad-seed failure)
and all five integrated-delivery checks were independently re-executed successfully
against their expected outcomes. No new outcome model was called for this audit.

A historical consolidated verifier report recorded HEAD `5b39c76` while already
using the uncommitted adapter bytes later committed as `2951ad4`. Its preserved
file hashes and later reconciliation, rather than the old HEAD alone, establish
provenance. The fixture's extra annotation asking for stale-record exclusion is
not an implemented rule: applicable stale records may be retained with freshness
marked stale. Accepted lifecycle, provenance/support, freshness and independent
review state remain different axes; review state can remain unknown.

[Preservation](development/preservation.json) verifies all 47 older schemas, 240
canonical method files representing 48 methods, and 9,787 historical evaluation
files unchanged from the starting commit. The existing static coding-specialist
library and native EN/KO/zh-CN boundaries remain unchanged. User-owned agent and
historical monitor files are excluded and unchanged. No project-memory migration,
automatic enrollment/capture, global setting or active installation replacement
was performed.

## Accounting, portability and remaining limits

[Usage](usage.json) accounts for **28 actual model invocations**: 24 workflow
roles (including the two failed initial producers) and four separate diagnostics.
All used the fixed tuple. Three provider-failed calls have no terminal usage.
The 25 reported calls sum to **1,726,632 input tokens**, including **1,168,768
cached**, and **50,929 output tokens**, including **21,679 reasoning-output**;
reported cache-write input is zero. Status counts are 23 completed, two rejected
structured assessments and three process failures. A completed negative-review
diagnostic still has `contract_accepted: false`; process completion is not
semantic acceptance. These figures include failures and repairs. Missing provider usage stays null;
measured sums exclude those unknowns. Cached input is a subset of total input,
and reasoning output is a subset of output. Do not add them again. Development
collaboration is separately [accounted](development/development-usage.json);
per-agent and primary token usage and billed cost are unavailable. A development
report's `model_calls: 0` means no outcome model was invoked by that verification
script, not that the development agent consumed no reasoning or tokens. A diagnostic's
`tool_items` is an opaque completed-item count, not a verified tool-call count.

The adapter is initially qualified only on macOS with the stated client version.
Read-only tool checks with controlled environment/network restrictions do not
prove all-filesystem read isolation, account/backend memory isolation or an
independent backend model identity. Windows package CI is not live Windows
orchestration support. Hooks, default decisions and native memory are unchanged;
this opt-in CLI test is not proof of automatic host activation. Clean-machine
installation, signing, publication and active plugin replacement are outside this
revision. No quality/efficiency profile is promoted and no broad matrix is added.

Public exports replace local environment paths with tokens; original receipts
remain unchanged. [Export provenance](export-manifest.json) keeps original and
public hashes, while [pre-export identity checks](development/preexport-identity.json)
confirm retained original assessment/output bindings. A redacted JSON body cannot
reconstruct its original hash by itself. Exact synthetic artifact bytes are
unchanged. Raw user prompts, assembled role prompts, model event streams, reasoning and
credentials are not published. Fixed synthetic task definitions and diagnostic
prompt templates remain inspectable public sources. [README](README.md) provides offline verification and explicit new-run
replay instructions. The PR is the authority for the final pushed commit and exact-head CI; this
local packet alone does not establish either.
Merge, tagging, guarded publication and public-asset/active-install verification
remain separately authorized release work.
