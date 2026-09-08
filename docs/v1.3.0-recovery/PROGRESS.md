# OpenSocrates v1.3.0 release progress

## Current scope and authorization

The maintainer has authorized completion and distribution of v1.3.0 through the
normal PR, CI, merge, tagged GitHub release and npm workflow. This supersedes the
earlier local-only boundary. A separate local recovery branch preserves the
original development history; this public branch starts from released main and
contains reviewed source plus public-safe evidence only.

The current stable scope is decision-point method retrieval, presentation-only
Response Policy, EN/KO Guided Natural Output, visible-length measurement, and
truthful host capability reporting. The presentation policy must preserve all
required evidence, stop conditions, public outputs, protected values and user
formats. No universal word/ground-count caps, procedure rewriting, automatic
humanizer/detector claims, Compact promotion, new hosts/locales, or research
backend are included. This is a current maintainer-delegated scope decision,
not a claim of historical approval.

## Execution plan

1. Integrate the conservative presentation layer using existing contracts.
2. Freeze and validate current-source EN/KO behavior and interaction overhead.
3. Keep functionality/integrity/security gates before publication; verify exact
   public provenance and published bytes afterward without a release-order cycle.
4. Complete PR checks, merge normally, publish immutable release assets, dispatch
   the established npm workflow on the exact tag, and verify published outputs.

Authenticated installed-path evaluation and current Claude Chat functionality
remain under investigation. No failed or unavailable observation is a pass.
Historical rejected variants and their evaluation results remain preserved in
the maintainer's recovery workspace; they are not silently promoted here.

## Current validation milestone

Tracked work: [issue87](https://github.com/ParkerHwang/OpenSocrates/issues/87) and
[draft PR88](https://github.com/ParkerHwang/OpenSocrates/pull/88).
Source `134c8acbb7d1fd30b7126751f80483ae929a9105` passed local smoke and native
release checks. The installed-study Codex ZIP is
`sha256:6a8378fd0b3c60dfee1f38410f777bcc607f6b02cbd80a898e45cc6aaa3b3bc1`.
The [three-arm EN/KO protocol](../../evals/v1.3/release-guided-20260908/PROTOCOL.md)
is frozen before outcomes. Normal browser login and installation in verified
exclusive OS-home/profile/temp roots succeeded without copying credentials.
Seven candidate hooks were approved through the normal TUI. Outcomes are being
collected; neither completion of the study nor publication is claimed yet.

The first PR CI attempt stopped at an exact handoff-label mismatch in the PR
body (`Last verified commit:`). The field was corrected; no validation assertion
or branch rule was relaxed. A new synchronize event runs the corrected body.
