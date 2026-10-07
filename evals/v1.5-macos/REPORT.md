# Mac implementation observations, 2026-10-07

The implementation preserves the v1.4 Codex foundation and introduces Mac-native
Claude entry, a standalone account skill, and Antigravity modular content. This
record separates package correctness from host loading and model-result reliability.
It is a bounded synthetic smoke test, not an efficacy comparison or full release
qualification. [Mac usage](../../docs/macos-v1.5.md) and
[Windows continuation](../../docs/v1.5.0/WINDOWS_HANDOFF.md) describe the next actions.

## Reproducible source and boundary

[sources.md](fixtures/sources.md) contains invented workshop notes. The
[case definitions](fixtures/cases.json) give ordinary requests and the rubric.
The tasks produce drafts only; no recipient was contacted or room booked.
Only public synthetic fixture facts, short observer findings, content digests and
aggregate lifecycle results are stored. No raw private reasoning, account IDs,
user-work transcripts, screenshots or old account skill backup is included.

The request strings in cases.json normalize spacing and wording for reproduction;
they are not raw UI transcripts. All actual attempts remain counted: one initial
Claude R1, then a fresh guide2 Claude R1/R2/R3, and Antigravity R1/R2/R3: **7 model
requests**. There was no independent judge or same-model baseline comparison.

## Practical results

| Surface | Observation | Limit and next action |
| --- | --- | --- |
| Claude Desktop local Code, guide1 R1 | Latest24, tentative booking,30 preference and distinct drafts. Reader-guide read command observed. | Asserted no photographer rather than source uncertainty, and reopened known capacity. Retain this partial outcome. |
| Claude Desktop local Code, guide2 R1 | Fresh folder/marketplace; source reconciliation improved and photography alternatives left unknown. | Draft proposes fallback24 and arranging photography. Fallback has an author-choice caveat; photography promise needs review. |
| Claude Desktop local Code, guide2 R2 | Confirmed booking and18 replace previous facts; updated both drafts without asking to confirm booking again. | Photography assignment was again described as unset instead of unknown in sources. This is an observed regression, not a pass. |
| Claude Desktop local Code, guide2 R3 | Table only; all nine values retained. | Mechanical behavior in this request only. |
| Antigravity conversation application, workspace guide1 | R1/R2 distinguished latest capacity, booking status, organizer preference and volunteer roles; two usable drafts. R3 preserved all values in a table. | R1 also read the parent synthetic plan; source isolation and comparative improvement are unproven. Global discovery remains unobserved. |
| Claude CLI2.1.285 | Actual plugin registration and isolated lifecycle operations confirmed. | CLI is logged out; authenticated ordinary-task delivery remains pending. Existing Desktop login was used separately. |
| Claude account ZIP | ZIP format accepted; existing1.1.2 skill backed up. | Replacement was cancelled while temporary swap/restore approval remained pending. Chat/Desktop Chat/Cowork1.5 treatment is unobserved. |

Host versions and exact guide2 treatment artifact hashes are in
[observations.json](observations.json). Those are local pilot build identities;
the final integration build and exact-head CI supply their own provenance.
Guide1's installed manifest/reader hashes are retained, while its original native
ZIP digest is unavailable in this public observation set.

The displayed reader-file command identifies the installed guide, not complete
canonical-method application. No native application receipt or every-judgment
enforcement is claimed. Missing application proof does not block a finished code
artifact, and it cannot be promoted into proof of improved answers.

## Installer lifecycle

[lifecycle.json](lifecycle.json) records **18 passing actual operations** across
isolated Claude and Antigravity global configurations: install, status, disable,
update while disabled, status, enable, diagnose, remove, and final status.
Unrelated sentinel content was preserved. Claude uses the actual official CLI;
Antigravity checks managed file state, not a global app loading claim.

An earlier nine-operation Claude cycle completed, but the harness incorrectly
expected `false` instead of unavailable `null` after removal. The assertion was
corrected without changing the product; the earlier attempt remains recorded.
Host-owned Claude cache/history cleanup is not claimed by ordinary removal.

## Verification and continuation

The source gates cover native Claude normalization, privacy and fail-open entry,
portable96-procedure parity/inventory, and owned addon lifecycle/rollback. The
native package gate exercises the generated launcher at its actual3s entry and1s
no-op budgets and binds additional profiles, installer dependencies, SBOM and
root checksums. Offline checks do not establish result reliability or cloud
activation. Exact-head local/CI commands are recorded in the implementation PR.

Windows should continue from the Mac Git branch/PR and preserve the known source
and draft limitations. New native Windows profiles, platform-safe ZIP preparation,
real Windows host lifecycle, authenticated terminal delivery, account treatment,
and a broader controlled quality study remain separate follow-up work.
