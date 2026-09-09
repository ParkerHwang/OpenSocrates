# OpenSocrates v1.3.0 release qualification and handoff

## Post-release review on 2026-09-08

PR [#88](https://github.com/ParkerHwang/OpenSocrates/pull/88) merged as
`45bc7885ba068ff40c2499154a3920494df47eae`. Tag `v1.3.0` resolves to that
commit. The release workflow completed successfully and published 19 assets at
2026-09-08 10:56:56 UTC; npm 1.3.0 followed at 10:59:58 UTC. These facts confirm
publication and the point-in-time byte checks, not every documented behavior.

The GitHub release API reports `immutable: false`, and the repository immutable-
release setting reports `enabled: false`. The workflow's existing collision check
refused to overwrite an existing release, but that is not GitHub platform
immutability. GitHub states that enabling the setting applies only to future
releases in its [immutable-release settings documentation](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes).
Keep the existing v1.3.0 tag and assets unchanged. A future patch
release must first enable the repository setting; the follow-up workflow now
fails closed unless the setting is enabled and verifies the published release's
`immutable` field before npm publication.

The exact public v1.3.0 Codex ZIP and checksum were downloaded and verified during
this review. Its packaged request is 22-line pretty-printed JSON. The documented
one-shot command exited 0 but returned `status: unavailable` and
`reason: decision_unavailable`; the same request serialized on one line selected
`critical-thinking`, and two NDJSON requests under `--stream` produced two native
responses. This confirms a shipped one-shot parser defect. The follow-up reads one
bounded JSON document through EOF outside stream mode and adds source and assembled-
package regressions. Exit 0 alone remains insufficient success evidence.

The follow-up environment has Codex CLI 0.145.0, but its active OpenSocrates plugin
cache contains version 1.2.1 rather than this candidate. The candidate was built
and exercised in isolation and was not installed into the active task. Therefore
this review adds source and real packaged-native evidence, not a same-source live
Codex hook or actor receipt. A live reevaluation still requires a separate
authenticated profile or new task loaded from the exact candidate, with the zero-
method, changed-judgment, missing-prerequisite and separated-question cases kept
distinct. No new external API or paid service is required.

## Prepublication qualification snapshot

Product source `32d0322c73c8c116b961ddb3a68a75473c715466` is accepted for the
scoped v1.3.0 release described below. Its local native `make release-check` and
all five required GitHub PR checks passed. The final evidence/documentation head
must pass fresh required checks before normal protected merge. This snapshot
precedes publication; exact published GitHub/npm identity and byte verification
will be recorded in [PR88](https://github.com/ParkerHwang/OpenSocrates/pull/88)
and the release workflow's public verification artifact. No publication is
inferred from this qualification snapshot.

Tracking: [issue87](https://github.com/ParkerHwang/OpenSocrates/issues/87).
The maintainer authorized PR, protected merge, a non-overwriting tagged release
workflow and npm trusted publishing. GitHub platform immutability was intended
but not verified in this prepublication snapshot and was not active for v1.3.0.
No approval gate, source assertion or existing release may be bypassed. A separate local recovery workspace preserves original development
history and invalid/unsuccessful historical trials; its private history was not
pushed. All five original worktrees' branches/HEADs and794 initially recorded
changed files remain unchanged. The omitted prior comparison-site directory had
no initial hash baseline; preservation is not a complete historical disk snapshot.

## Accepted product scope and validation

The stable scope is decision-point retrieval, presentation-only Response Policy,
EN/KO Guided prose, complete visible-output measurement and truthful host support.
All48 methods and96 authored EN/KO procedure bodies retain the v1.2.1 wording.
No Compact/procedure rewrite, new locale/host, research backend, detector/humanizer,
universal length cap or automated semantic validator is promoted.

Claude/Codex use the existing native selection command first when runtime/shell
are available; an empty eligible set is valid. Genuine failure permits complete
reference fallback with all known constraints intact. Other hosts keep their
existing delivery model. The example has no arbitrary explicit method default.
Ineligible/retired methods cannot export specialized output requirements to other
judgments. The public-output pattern keeps each question's conclusion, missing
inputs and reopening conditions separate while respecting exact user formats.
These are guidance and declared-feature selection, not guaranteed model compliance.

The native build validates all six packages and the complete Chat ZIP, exact
canonical references, policy assets, safe launcher/storage boundaries, cleanup,
installer behavior and bounded timing. Response-policy/guide tests10/10 and
routing tests24/24 passed; source formatting/lint/docs passed. Six credential-free
EN/KO packaged CLI cases separately confirm RCF and Bayesian prerequisite
exclusions plus an eligible evidence-hierarchy judgment.

Local native Codex archive:
`sha256:f51be7c9ce4df606e8df98ed4446377e490d2894c8efaa80ed87e6888044031e`.
Normal isolated update matched its manifest. Browser login used separately owned
OS-home/profile/temp roots without credential copies. Seven native hook commands
were normally approved and their unchanged hashes verified trusted/enabled.
The release job builds and verifies its own public bytes; its archive hash need
not equal this local native build.

## Complete behavioral record and failed attempts

All39 actor invocations use synthetic materials and gpt-5.6-luna/max. Every
300-second deadline remains a deadline even if a correct file already existed.
Do not pool different protocols/sources into a comparative success estimate.

| Study | Source | Final delivery | Primary300 result and disposition |
| --- | --- | --- | --- |
| Initial24 |134c8ac|20/24|4 deadlines; U/G upfront controls16/16, installedJ4/8.|
| Follow-up8 |4ea8542|5/8|3 deadlines; G4/4, J1/4.|
| Diagnostic1 |4ea8542|0/1|300 deadline; no completed turn, no sole-cause inference.|
| Qualification3 |95a96a1|2/3|ChangedKO224.25s, forecastEN232.38s; forecastKO300 deadline.|
| Finite observation1/P09 |8109176|1/1 at369.15s|300 deadline retained; future-condition fidelity failure.|
| Scope verification1/P10 |2339d8a|1/1 at199.58s|300 completion; blind pass later revised on an explicitly nonblind challenge for the restrictive joint gate.|
| Native verification1/P11 |32d0322|1/1 at384.58s|300 deadline retained; exact-source artifact reassessment passes, naturalness2.|

[Outcome index](../../evals/v1.3/release-guided-20260908/outcome-index.json) retains
whole public outputs/artifacts, metrics, usage when available and source/package
identity. Protocols and hashes were frozen before each observation. Initial U/G
controls are transformed upfront content, not live1.2.1. The initial environment
and early audit visibility limit causal inference. Later runs use default-deny
environments, delayed audit facts, explicit optional-premium wording and disabled
multi-agent tooling. These differences are declared, not silently treated as
identical inputs. Later600 ceilings were prospectively authorized finite-completion
observations; the original300 study budget is not a published host latency SLO.
No repeat-until-pass or prior-failure relabeling is used.

Repairs address distinct observed/code-confirmed issues: missing completion
boundaries; optional Strict text without an applicability guard; Bayesian metadata
missing already-authored prerequisites; question-scope ambiguity; and file-first
routing bypassing the available structured selection path. All procedure bodies
remain unchanged. No single causal explanation for model latency is established.

P11 observed an actual supported native invocation selecting critical-thinking
and complete critical-thinking/Socratic references. The actor's exact closed
feature list could not be extracted and no request file remained: semantic
classification is unverified. Controlled typed CLI tests are separate evidence.
Native selection, complete delivery, claimed use and actual application remain
distinct; applied is unverified. This is bounded observed behavior, not every
reasoning transition, all-method coverage or a compliance guarantee.

## Independent review and adjudication

Initial fresh Luna/max EN/KO reviewers assessed16 blinded cross-iteration artifact
packets. Those packets used condensed forecast-source summaries, so they are not
exact-input source-fidelity verification. The known missing KO final delivery
remained a failure. They share the actor's model family and are not human gold.

P09's unsupported universal future prerequisites remain a failure. P10's original
blind pass and separate nonblind adversarial revision are both retained, not
counted as independent votes. P11 was first reviewed by the EN reviewer without
the KO challenge history; its summary-based packet omitted actual source details.
The corrected packet supplies exact whole pilot.txt bytes, verified against the
frozen fixture. Same-artifact corrected-input reassessment passes artifact,
fidelity, authority-content, format and final delivery. It is not a fresh blind
review. The first source-incomplete judgment remains, with the input defect named.

P11 separates the questions and scopes missing base-rate consequences to numeric
estimation in its question table and row qualification. A broad evidence-section
heading can still read ambiguously; this is retained as an editorial limitation,
not promoted to a guarantee that all future advice is perfect. Naturalness remains2
for repetition/structure. No demonstrated quality, naturalness, token-cost or
latency improvement is claimed.

Claude Sonnet5Max supplied a supplementary independent-family16-packet review,
but ran an echo no-op despite the no-tools instruction. An intended small P10
follow-up accidentally repeated old packets due to prompt preparation; it was
interrupted and supplies no P10 judgment. No further Claude calls or account skill
changes were made. All review inputs/results and these failures are preserved in
[judging](../../evals/v1.3/release-guided-20260908/judging/README.md).

## Support and publication boundaries

Native runtimes target Apple-silicon macOS. Claude Chat is export/layout/reference
integrity validated; current cloud upload/activation is unvalidated. No active
account skill was replaced. Other host live behavior, Desktop GUI, a separate Mac,
signing/notarization and verified method application are not inferred from tests.

The v1.3.0 PR, tag, GitHub release, point-in-time public byte validation and npm
publication completed. GitHub platform immutable-release protection did not.
Existing versions and assets must not be overwritten. A patch release still needs
fresh current-head CI, normal protected PR merge, an exact main-ancestor version
tag, the repository immutable-release setting enabled before publication, API
confirmation that the new release is immutable, npm trusted publishing, and an
independent public installer check. Publication receipts remain separate from
cloud activation or answer-quality claims.
