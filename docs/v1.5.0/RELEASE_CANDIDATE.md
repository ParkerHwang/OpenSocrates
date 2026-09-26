# OpenSocrates 1.5.0 release-candidate handoff

**Release candidate, not published.** Version metadata is synchronized to 1.5.0
on the feature branch. PR [#95](https://github.com/ParkerHwang/OpenSocrates/pull/95)
remains Draft and issue [#94](https://github.com/ParkerHwang/OpenSocrates/issues/94)
contains the exact final commit, CI results, package hashes and validation commands.
No merge, tag, publication, deployment or active-install replacement is implied.

The subsequent [post-review repairs](../../evals/v1.5/repairs/v1/REPORT.md) qualify
the checkpoint caller contract, assistance guide 6 and coding guides 2. Their
source/package identities and new usability results are separate from the
guide-5 qualification below. Earlier comparisons and receipts remain unchanged.

The user's [2026-09-26 completion standard](PRACTICAL_COMPLETION.md) governs this
candidate. Required functional, privacy, authority, migration, deletion and package
checks remain. Statistical studies, human recruitment, billing/backend echoes and
account-side isolation proof are not universal completion gates. Historical study
protocols and results retain their original status and limitations.

## What users can do

- Complete straightforward work directly, with task-based optional support when
  a consequential judgment needs it. No hidden model/effort switching occurs.
- Reuse existing code, inspect affected callers and continue after a source change
  in a fresh session. The 48 authored methods and EN/KO procedures remain intact.
- Enable scoped local continuity for Git or non-Git projects. Inspect accepted
  decisions separately from proposals and revalidate facts against current sources.
- Preserve valid accepted intent, delete the exact record containing withdrawn
  facts, and verify the resulting store. Supersession is not mislabelled forgetting.
- Answer side questions, continue independent authorized work, and ask only about
  a genuinely missing decision without reopening settled permission. Guide 5 adds
  aligned EN/KO wording for those behaviors.
- Continue sensibly with hooks or memory unavailable. Memory stays disabled until
  explicit enrollment and cannot manufacture facts or authorization.

See the user guides: [English](../project-memory.md) / [Korean](../project-memory.ko.md).

## Practical comparison and qualification

The [six-scenario comparison](../../evals/v1.5/practical/RESULTS.md) uses the actual
released v1.4.0 archive, competent instructions and a usable maintained-note control,
with one fixed `gpt-6-sol` / `medium` / `codex-cli 0.158.0-alpha.2` configuration.
All 20 planned model invocations completed; all 12 episode artifact/state checks
passed. Four calls of the initial 24-call ceiling were unused; no outcome was
rerun for a more favorable score.

Correctness tied. The candidate adds structured lifecycle/operation evidence and
avoids a repeated English approval request in this example. The baseline note
also works. Candidate memory-backed episodes cost more observed time/tool/input
work; English prose was sometimes more verbose. These limits are reported rather
than converted into a broad quality or efficiency claim. Model-specific profiles
remain experimental and inactive in normal routing; the task fallback is usable.

The comparison qualified the guide-5 source candidate while its build still
reported 1.4.0. Its manifest preserves that identity. Final RC preparation changes
version/installer metadata to 1.5.0 and checks unchanged runtime logic, canonical
guides and schema sources, plus regenerated and native package bytes. Do not
rewrite the comparison as though it used another archive.

The new checker includes nonempty zero-price orders and an explicit integer-seat
domain. Memory checks require accepted lifecycle, not matching proposal text.
All public messages are retained, including questions before final text. A declared
transparent evaluation adapter records actual native operation/request IDs and
statuses; independent state reads verify scoped deletion and retained records.
These changes repair measurement gaps without editing old generated programs,
old checkers, historical scores or the provisional judge's mistakes.

## Platforms, artifacts and required checks

| Surface | Candidate evidence / support statement |
| --- | --- |
| Apple-silicon macOS | Native frozen-runtime checks and disposable installed-package live episodes; final exact-version package qualification |
| Windows x64 | Native source/package CI, including ownership, locking, reparse and SQLite lifecycle; live Windows Codex unavailable because no host was connected |
| Untrusted/disabled hooks | Explicit installed-skill fallback exercised; installation alone does not prove hook approval or universal application |
| Other targets | No new claim for Windows ARM64/10, macOS Intel, Linux native packages, signing or SmartScreen reputation |

Final required source commands are the complete CONTRIBUTING set:
`make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check`.
Native macOS qualification is `make release-check`; Windows CI runs its documented
native build and `tools/check_windows.py --packages`. These commands' exact commit
and outcomes belong in the PR/issue handoff, not an inferred claim from this list.
No destructive account-home purge/reinstall is run.

The completed [RC qualification receipt](../../evals/v1.5/practical/rc-qualification.json)
anchors the product and native package to `7cf2777bc55e847c77396f46ad9b75835dd30f8c`.
`make release-check` passed, including frozen SQLite and deterministic generation.
The local full source suite passed on the working tree subsequently committed as
that revision; the hosted run also passed all six checks. That handoff was followed
by the separately qualified post-review repairs linked above; its original
functional-source equivalence is not a claim that the current source is unchanged.
The [installed native checks](../../evals/v1.5/practical/rc-acceptance/summary.json)
verify both Git and directory projects, all 41 packaged/internal schemas, both
assistance guides, accepted/proposed state, exact record deletion and project-store
deletion while fixture source files remain unchanged. These checks make zero model
calls and preserve the original active installation, global configuration and agent
definition. The offline practical verifier checks their locked receipts.

The local review artifacts are versioned under `dist/`, including
`opensocrates-1.5.0-codex-plugin.zip`, its SHA-256 file, release manifest,
checksums, limitations and SPDX SBOM. Hosted CI also supplies the Windows x64
archive and source provenance. They are candidate build artifacts, not a GitHub
release or npm publication. Review the final checksums/commit before using them.

The active plugin, global memory/settings and real projects remain untouched.
The user's original agent definition is preserved. Existing model and SDK/CLI
compatibility pins are unchanged. No credential, paid service or usage-reset
credit is created or consumed by qualification.

## Remaining release action

After separately authorizing release: review and merge PR #95 through protected
main, create the exact `v1.5.0` tag at the approved merged commit, and use the
existing guarded release workflow. Verify the published package/npm version,
checksums and provenance before describing 1.5.0 as released. Updating the active
installation is a separate explicit action. The current handoff performs none of
those publication or activation steps.
