# Windows typing follow-up to orchestration qualification

Source `6eb8d3774f3a9032f580359b38b8bf11208f70d3` repairs a required CI failure
without expanding the real adapter beyond macOS or rerunning outcome models.
The original [28-call record](../v1/REPORT.md) and its complete public file lock
remain unchanged. Its actual calls retain their original source/package identities.

On `b32dbdba4e53ad08e90e4a4a97a30d4fe57c5a27`,
[CI run 36341810566](https://github.com/ParkerHwang/OpenSocrates/actions/runs/36341810566)
passed Python quality, product contracts, installer and native macOS packaging,
but Windows mypy reported eight errors before its native build. Direct references
to POSIX-only flags and process-group APIs were valid behind runtime guards on the
supported host, but unavailable in Windows typing stubs. [INITIAL_FAILURE.json](INITIAL_FAILURE.json)
retains the exact source locations and errors; [FAILED_CI.json](FAILED_CI.json)
retains all five job results.

The repair makes the capability contract explicit:

- `O_DIRECTORY` and `O_NOFOLLOW` must exist as positive integers. Missing, invalid,
  boolean, zero or negative values raise `directory_capability_unavailable`.
  Supported values are returned unchanged; there is no zero-valued fallback.
- Process-group cleanup uses a type-checker-recognized platform guard. Supported
  POSIX hosts retain termination and forced escalation; Windows retains the
  pre-existing `terminate`/`kill` path.
- The real client probe still rejects non-macOS execution. Schemas, guidance,
  model settings, role context construction and acceptance rules are unchanged.

[Independent static review](STATIC_REVIEW.json) accepts this bounded change.
[Independent execution verification](EXECUTION_VERIFICATION.json) supplies the
16 separately attributed affected checks and their limitations. The initial
mock-signature correction is retained in [HARNESS_CORRECTION.json](HARNESS_CORRECTION.json);
`audit-harness.py` is path-normalized inspection material, not a portable runner.
Neither review is a new
live model outcome or proof of Windows orchestration support.

[Source identity](SOURCE_BRIDGE.json) identifies the two changed runtime files
among 587 package inputs; the other 585, including every schema and guide, are
unchanged. The third changed file adds focused regressions. [Local qualification](VALIDATION.json)
records the complete CONTRIBUTING source suite and `make release-check`, both
successful at the stated source commit. There are now 43 orchestration tests and
32 scanner mutation cases. Local Windows-targeted mypy success is separate from
the final hosted Windows build result recorded in Draft PR #95.

The rebuilt local ZIP is
`01c5c1852a4c6293d835a5cf3b73fee22c6eef3bb62a9ecc2f1e1cd2651cf9c9`;
the native executable is
`329d71719667bebdf42df29d2dc2440429d3c9e70b212ae745f8ebfd949434f9`.
All [176 selected package members](PACKAGE_MEMBERS.json) match source.
These identities supersede the older package for the current candidate; they do
not rewrite which package produced the earlier model results.

Verify this bridge, frozen prior evidence and exact committed files from the repo
root without model calls:

```sh
python3 -B evals/v1.5/orchestration/ci-repair-v1/verify.py --tracked
```

Add `--native` only when the locally qualified `dist/` artifacts are present.
The command checks their hashes; it does not run a new model or substitute for
independent execution evidence. The final commit and exact-head hosted CI belong
to [Draft PR #95](https://github.com/ParkerHwang/OpenSocrates/pull/95). No merge,
tag, publication, active-install replacement or real-project enrollment occurred.
